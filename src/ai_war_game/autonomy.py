"""autonomy.py — General AI decision making with actual game effects."""

from __future__ import annotations

import contextlib
import json
import random
import sqlite3

from ai_war_game.db import add_memory, get_general, log_event
from ai_war_game.llm import get_decision_model, llm_call_json

LOYALTY_REBEL_THRESHOLD = 40
FOOD_DESPERATE = 3


def _build_personality_prompt(general: dict, memory_summary: str) -> str:
    """Build system prompt from general's personality JSON (equivalent to SOUL.md)."""
    name = general["name"]
    personality: dict = {}
    with contextlib.suppress(json.JSONDecodeError, TypeError):
        personality = (
            json.loads(general["personality"])
            if isinstance(general["personality"], str)
            else general["personality"]
        )

    lines = [f"你 是{name}，一位三国时代的武将。"]
    if personality.get("temperament"):
        lines.append(f"\n性格: {personality['temperament']}")
    if personality.get("battle_style"):
        lines.append(f"用兵风格: {personality['battle_style']}")
    if personality.get("risk_preference"):
        lines.append(f"风险偏好: {personality['risk_preference']}")
    if personality.get("lord_attitude"):
        lines.append(f"对主态度: {personality['lord_attitude']}")
    if personality.get("ally_attitude"):
        lines.append(f"对盟友: {personality['ally_attitude']}")
    if personality.get("enemy_attitude"):
        lines.append(f"对敌人: {personality['enemy_attitude']}")

    lines.append("\n数值:")
    lines.append(f"  武力: {general['war']}  统帅: {general['cmd']}  智力: {general['intel']}")
    lines.append(f"  政治: {general['politics']}  魅力: {general['charm']}")
    if general.get("loyalty") is not None:
        lines.append(f"  忠诚: {general['loyalty']}")
    lines.append(f"  兵力: {general['troops']}  粮草: {general['food']}日")

    if memory_summary:
        lines.append(f"\n近期记忆:\n{memory_summary}")

    lines.append("""
决策规则:
- 做出真实决策，不要每次都做同样的选择
- 粮草不足时考虑就食或掠夺
- 忠诚度低且有机会时考虑叛变
- 根据局势和自身状态选择行动

输出格式: 严格JSON
{"action": "idle|train|recruit|forage|raid|rebel", "target": "", "narrative": ""}
""")
    return "\n".join(lines)


def general_decide(
    general: dict,
    context: dict,
    memory_summary: str = "",
    model: str | None = None,
) -> dict:
    """Call LLM with general personality + context, return structured decision."""
    if model is None:
        model = get_decision_model()
    system_prompt = _build_personality_prompt(general, memory_summary)
    user_message = json.dumps(context, ensure_ascii=False)
    return llm_call_json(system_prompt, user_message, model=model)


def trigger_autonomy(conn: sqlite3.Connection, general_id: str) -> dict:
    """Trigger autonomous decision and APPLY effects to game state."""
    general = get_general(conn, general_id)
    if general is None:
        return {"general": general_id, "status": "error", "error": "not found"}

    cursor = conn.execute("SELECT value FROM game_state WHERE key='current_day'")
    day_row = cursor.fetchone()
    current_day = int(day_row[0]) if day_row else 1
    loyalty = general["loyalty"] if general["loyalty"] is not None else 100
    food = general["food"]
    troops = general["troops"]
    name = general["name"]
    faction_id = general["faction_id"]

    action = "idle"
    narrative = ""
    changed = False

    if loyalty < LOYALTY_REBEL_THRESHOLD and troops > 5000 and random.random() < 0.15:
        new_faction = general_id + "_rebels"
        conn.execute(
            "INSERT OR IGNORE INTO factions (id, name) VALUES (?, ?)",
            (new_faction, f"{name}军"),
        )
        conn.execute(
            "UPDATE generals SET faction_id=? WHERE id=?",
            (new_faction, general_id),
        )
        conn.execute(
            "UPDATE cities SET owner_faction_id=? WHERE owner_faction_id=?",
            (new_faction, faction_id),
        )
        conn.commit()
        action = "rebel"
        narrative = f"{name}叛离原势力，自立门户!"
        add_memory(conn, general_id, current_day, "rebel", narrative)
        log_event(
            conn,
            current_day,
            0,
            "rebel",
            general_id,
            None,
            json.dumps({"name": name, "new_faction": new_faction}, ensure_ascii=False),
        )
        changed = True
        return {
            "general": general_id,
            "name": name,
            "decision": {"action": "rebel", "narrative": narrative},
            "changed": True,
        }

    # Rule: very low food → forage (move toward nearest city)
    if food < FOOD_DESPERATE:
        cursor = conn.execute(
            "SELECT id, name FROM cities WHERE id!=? LIMIT 1",
            (general["position_city_id"],),
        )
        dest = cursor.fetchone()
        if dest:
            conn.execute(
                "UPDATE generals SET position_city_id=? WHERE id=?",
                (dest[0], general_id),
            )
            conn.commit()
            action = "forage"
            narrative = f"{name}率部前往{dest[1]}就食"
            add_memory(conn, general_id, current_day, "forage", narrative)
            log_event(
                conn,
                current_day,
                0,
                "forage",
                general_id,
                dest[0],
                json.dumps({"name": name, "to": dest[1]}, ensure_ascii=False),
            )
            changed = True
            return {
                "general": general_id,
                "name": name,
                "decision": {"action": "forage", "narrative": narrative},
                "changed": True,
            }

    # Rule: high loyalty → train troops (slowly increase)
    if loyalty > 70 and troops < 80000 and random.random() < 0.3:
        gain = random.randint(100, 500)
        conn.execute(
            "UPDATE generals SET troops=troops+? WHERE id=?",
            (gain, general_id),
        )
        conn.commit()
        action = "train"
        narrative = f"{name}操练兵马，兵力+{gain}"
        add_memory(conn, general_id, current_day, "train", narrative[:100])
        changed = True

    # Rule: idle generals sometimes forage automatically
    if action == "idle" and food < 15 and random.random() < 0.2:
        gain = random.randint(1, 3)
        conn.execute(
            "UPDATE generals SET food=food+? WHERE id=?",
            (gain, general_id),
        )
        conn.commit()
        action = "forage"
        narrative = f"{name}征集粮草，粮草+{gain}日"
        add_memory(conn, general_id, current_day, "forage", narrative[:100])
        changed = True

    if changed:
        log_event(
            conn,
            current_day,
            0,
            f"autonomy_{action}",
            general_id,
            None,
            json.dumps(
                {"name": name, "action": action, "narrative": narrative}, ensure_ascii=False
            ),
        )

    return {
        "general": general_id,
        "name": name,
        "decision": {"action": action, "narrative": narrative},
        "changed": changed,
    }


def trigger_all_autonomy(conn: sqlite3.Connection) -> list[dict]:
    """Trigger autonomous decisions for all non-player generals."""
    cursor = conn.execute("SELECT id FROM generals WHERE is_player=0")
    results = []
    for row in cursor.fetchall():
        result = trigger_autonomy(conn, row[0])
        results.append(result)
    return results
