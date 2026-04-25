"""autonomy.py — General AI decision making (replaces agent_comm.py Hermes subprocess)."""

from __future__ import annotations

import contextlib
import json
import sqlite3

from ai_war_game.db import add_memory, get_general, get_memories, log_event
from ai_war_game.llm import get_decision_model, llm_call_json


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
- 做决策时优先遵循你的人格与作风
- 粮草不足时战斗力下降
- 忠诚度低时可能抗命或叛变
- 根据局势和自身状态选择行动

输出格式: 严格JSON
{"action": "fight|retreat|negotiate|idle|rebel|advise|...",
 "effort": 0.0-1.0, "target": "...", "narrative": "..."}
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
    """Trigger autonomous decision for a single general."""
    general = get_general(conn, general_id)
    if general is None:
        return {"general": general_id, "status": "error", "error": "not found"}

    cursor = conn.execute("SELECT value FROM game_state WHERE key='current_day'")
    day_row = cursor.fetchone()
    current_day = int(day_row[0]) if day_row else 1
    cursor = conn.execute("SELECT value FROM game_state WHERE key='season'")
    season_row = cursor.fetchone()
    season = season_row[0] if season_row else "春"

    recent_memories = get_memories(conn, general_id, limit=5)
    memory_text = "\n".join(
        f"第{m['game_day']}日 [{m['event_type']}] {m['summary']}" for m in recent_memories
    )

    context = {
        "type": "autonomy_check",
        "current_day": current_day,
        "season": season,
        "your_status": {
            "troops": general["troops"],
            "food": general["food"],
            "loyalty": general["loyalty"],
        },
        "instruction": (
            "Review your situation and decide what action to take. "
            "Consider your loyalty, troops, food supplies, and ambitions."
        ),
    }

    decision = general_decide(general, context, memory_text)
    action = decision.get("action", "idle")
    narrative = decision.get("narrative", "")

    add_memory(
        conn,
        general_id,
        current_day,
        f"autonomy_{action}",
        f"{general['name']}决定{action}: {narrative[:100]}",
    )
    log_event(
        conn,
        current_day,
        0,
        f"autonomy_{action}",
        general_id,
        None,
        json.dumps(
            {"name": general["name"], "action": action, "narrative": narrative[:200]},
            ensure_ascii=False,
        ),
    )

    return {"general": general_id, "name": general["name"], "decision": decision}


def trigger_all_autonomy(conn: sqlite3.Connection) -> list[dict]:
    """Trigger autonomous decisions for all non-player generals."""
    cursor = conn.execute("SELECT id FROM generals WHERE is_player=0")
    results = []
    for row in cursor.fetchall():
        result = trigger_autonomy(conn, row[0])
        results.append(result)
    return results
