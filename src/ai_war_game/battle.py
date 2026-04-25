"""battle.py — Battle resolution for AI War Game."""

from __future__ import annotations

import json
import sqlite3

from ai_war_game.autonomy import general_decide
from ai_war_game.llm import get_decision_model, llm_call_json


def _get_general(conn: sqlite3.Connection, general_id: str) -> dict | None:
    cursor = conn.execute("SELECT * FROM generals WHERE id=?", (general_id,))
    cols = [d[0] for d in cursor.description]
    row = cursor.fetchone()
    return dict(zip(cols, row, strict=False)) if row else None


def _get_city(conn: sqlite3.Connection, city_id: str) -> dict | None:
    cursor = conn.execute("SELECT * FROM cities WHERE id=?", (city_id,))
    cols = [d[0] for d in cursor.description]
    row = cursor.fetchone()
    return dict(zip(cols, row, strict=False)) if row else None


def identify_participants(conn: sqlite3.Connection, attacker_id: str, defender_id: str) -> dict:
    attacker = _get_general(conn, attacker_id)
    if not attacker:
        raise ValueError(f"未找到攻击方武将: {attacker_id}")
    defender = _get_general(conn, defender_id)
    if not defender:
        raise ValueError(f"未找到防守方武将: {defender_id}")

    city = _get_city(conn, defender["position_city_id"])
    city_id = city["id"] if city else defender["position_city_id"]

    cursor = conn.execute(
        "SELECT * FROM generals WHERE position_city_id=? AND id!=? AND id!=?",
        (attacker["position_city_id"], attacker_id, defender_id),
    )
    cols = [d[0] for d in cursor.description]
    attacker_allies = [dict(zip(cols, row, strict=False)) for row in cursor.fetchall()]

    cursor = conn.execute(
        "SELECT * FROM generals WHERE position_city_id=? AND id!=? AND id!=?",
        (defender["position_city_id"], attacker_id, defender_id),
    )
    defender_allies = [dict(zip(cols, row, strict=False)) for row in cursor.fetchall()]

    cursor = conn.execute("SELECT value FROM game_state WHERE key='season'")
    season_row = cursor.fetchone()
    cursor = conn.execute("SELECT value FROM game_state WHERE key='weather'")
    weather_row = cursor.fetchone()
    cursor = conn.execute("SELECT value FROM game_state WHERE key='current_day'")
    day_row = cursor.fetchone()

    return {
        "attacker": attacker,
        "defender": defender,
        "attacker_allies": attacker_allies,
        "defender_allies": defender_allies,
        "city": city or {"id": city_id, "name": city_id, "terrain": "平原"},
        "terrain": city["terrain"] if city else "平原",
        "season": season_row[0] if season_row else "春",
        "weather": weather_row[0] if weather_row else "晴",
        "current_day": int(day_row[0]) if day_row else 1,
    }


def build_battle_context(participants: dict, side: str, general_id: str) -> str:
    if side == "attacker":
        general = next(
            (
                g
                for g in [participants["attacker"]] + participants["attacker_allies"]
                if g["id"] == general_id
            ),
            participants["attacker"],
        )
        enemy = participants["defender"]
        objective = "capture_city"
    else:
        general = next(
            (
                g
                for g in [participants["defender"]] + participants["defender_allies"]
                if g["id"] == general_id
            ),
            participants["defender"],
        )
        enemy = participants["attacker"]
        objective = "hold_city"

    context = {
        "type": "battle_command",
        "side": side,
        "current_day": participants["current_day"],
        "season": participants["season"],
        "weather": participants["weather"],
        "terrain": participants["terrain"],
        "city": {
            "id": participants["city"]["id"],
            "name": participants["city"].get("name", participants["city"]["id"]),
        },
        "your_forces": {
            "troops": general["troops"],
            "food": general["food"],
            "war": general["war"],
            "command": general["cmd"],
            "intel": general["intel"],
            "politics": general["politics"],
            "charm": general["charm"],
        },
        "enemy_forces": {
            "general": enemy["name"],
            "troops": enemy["troops"],
            "war": enemy["war"],
            "command": enemy["cmd"],
            "intel": enemy["intel"],
        },
        "allies": [
            {"name": a["name"], "troops": a["troops"]}
            for a in (
                participants["attacker_allies"]
                if side == "attacker"
                else participants["defender_allies"]
            )
            if a["id"] != general_id
        ],
        "objective": objective,
    }

    return json.dumps(context, ensure_ascii=False)


def apply_battle_result(conn: sqlite3.Connection, result: dict) -> list[dict]:
    events = []

    conn.execute(
        "UPDATE generals SET troops=? WHERE id=?",
        (result["attacker_final_troops"], result["attacker_id"]),
    )
    conn.execute(
        "UPDATE generals SET troops=? WHERE id=?",
        (result["defender_final_troops"], result["defender_id"]),
    )

    if result.get("new_owner") and result["outcome"] != "draw":
        conn.execute(
            "UPDATE cities SET owner_faction_id=? WHERE id=?",
            (result["new_owner"], result["city_id"]),
        )

    log_entry = {
        "outcome": result["outcome"],
        "attacker_id": result["attacker_id"],
        "defender_id": result["defender_id"],
        "city_id": result["city_id"],
        "attacker_troops_lost": result["attacker_troops_lost"],
        "defender_troops_lost": result["defender_troops_lost"],
        "new_owner": result.get("new_owner"),
    }
    if "narrative_concise" in result:
        log_entry["narrative_concise"] = result["narrative_concise"]
    if "narrative_detailed" in result:
        log_entry["narrative_detailed"] = result["narrative_detailed"]
    if "attacker_name" in result:
        log_entry["attacker_name"] = result["attacker_name"]
    if "defender_name" in result:
        log_entry["defender_name"] = result["defender_name"]
    if "city_name" in result:
        log_entry["city_name"] = result["city_name"]
    if "weather" in result:
        log_entry["weather"] = result["weather"]

    cursor = conn.execute("SELECT value FROM game_state WHERE key='current_day'")
    day_row = cursor.fetchone()
    current_day = int(day_row[0]) if day_row else 1

    cursor = conn.execute(
        "SELECT COALESCE(MAX(seq), 0) + 1 FROM events_log WHERE game_day=?", (current_day,)
    )
    seq = cursor.fetchone()[0]

    conn.execute(
        "INSERT INTO events_log (game_day, seq, event_type, actor_id, target_id, details_json) "
        "VALUES (?, ?, 'battle', ?, ?, ?)",
        (
            current_day,
            seq,
            result["attacker_id"],
            result["defender_id"],
            json.dumps(log_entry, ensure_ascii=False),
        ),
    )
    conn.commit()

    events.append(
        {
            "day": current_day,
            "event_type": "battle",
            "details": log_entry,
        }
    )
    return events


def get_report_mode(conn: sqlite3.Connection) -> str:
    cursor = conn.execute("SELECT value FROM game_state WHERE key='report_mode'")
    row = cursor.fetchone()
    return row[0] if row else "concise"


def set_report_mode(conn: sqlite3.Connection, mode: str) -> None:
    if mode not in ("concise", "detailed"):
        raise ValueError(f"无效模式: {mode}，必须为 concise 或 detailed")
    conn.execute(
        "INSERT OR REPLACE INTO game_state (key, value, updated_day) VALUES ('report_mode', ?, ?)",
        (mode, 1),
    )
    conn.commit()


def format_battle_report(events: list[dict], mode: str = "concise") -> str:
    for evt in reversed(events):
        if evt.get("event_type") != "battle":
            continue
        try:
            details = json.loads(evt.get("details_json", "{}"))
        except (json.JSONDecodeError, TypeError):
            details = evt.get("details", {})

        outcome = details.get("outcome", "?")
        attacker_name = details.get("attacker_name", details.get("attacker_id", "?"))
        defender_name = details.get("defender_name", details.get("defender_id", "?"))
        city_name = details.get("city_name", details.get("city_id", "?"))
        weather = details.get("weather", "?")

        if mode == "detailed" and details.get("narrative_detailed"):
            return details["narrative_detailed"]

        if details.get("narrative_concise"):
            narrative = details["narrative_concise"]
        elif outcome == "draw":
            narrative = f"{attacker_name}与{defender_name}在{city_name}交战，不分胜负。"
        elif outcome == "attacker_win":
            narrative = f"{attacker_name}击败{defender_name}，攻克{city_name}。"
        else:
            narrative = f"{defender_name}击退{attacker_name}，守住{city_name}。"

        attacker_lost = details.get("attacker_troops_lost")
        defender_lost = details.get("defender_troops_lost")
        losses = ""
        if attacker_lost is not None or defender_lost is not None:
            al = attacker_lost or 0
            dl = defender_lost or 0
            losses = f" 攻击方损失: {al}，防守方损失: {dl}"

        return f"\u3010{city_name}\u4e4b\u6218\u3011\u5929\u6c14: {weather}{losses}\n{narrative}"

    return "(无战斗记录)"


def start_battle(
    conn: sqlite3.Connection,
    queue_path: str,
    graph_path: str,
    attacker_id: str,
    defender_id: str,
    city_id: str,
) -> dict:
    participants = identify_participants(conn, attacker_id, defender_id)

    attacker = participants["attacker"]
    defender = participants["defender"]

    # Bugfix: cross-faction validation — player can only attack other factions
    if attacker["faction_id"] == defender["faction_id"]:
        raise ValueError(f"不能攻击己方阵营的武将 ({attacker['name']} → {defender['name']})")

    # Bugfix: geography check — schedule march if cities differ
    if attacker["position_city_id"] != defender["position_city_id"]:
        from ai_war_game.engine import march_days, schedule_event

        distance = march_days(
            graph_path, attacker["position_city_id"], defender["position_city_id"]
        )
        if distance is None:
            atk_city = attacker["position_city_id"]
            def_city = defender["position_city_id"]
            raise ValueError(f"从 {atk_city} 到 {def_city} 没有可通行的路线")

        cursor = conn.execute("SELECT value FROM game_state WHERE key='current_day'")
        current_day = int(cursor.fetchone()[0])
        arrival_day = current_day + distance

        schedule_event(
            queue_path,
            arrival_day,
            0,
            "battle",
            actor_id=attacker_id,
            target_id=defender_id,
            details={
                "attacker_id": attacker_id,
                "defender_id": defender_id,
                "attacker_city_id": attacker["position_city_id"],
                "defender_city_id": defender["position_city_id"],
            },
        )

        return {
            "scheduled": True,
            "attacker_name": attacker["name"],
            "defender_name": defender["name"],
            "attacker_city_id": attacker["position_city_id"],
            "defender_city_id": defender["position_city_id"],
            "march_days": distance,
        }

    all_participant_ids = [attacker_id, defender_id]
    for ally in participants.get("attacker_allies", []):
        if ally["id"] not in all_participant_ids:
            all_participant_ids.append(ally["id"])
    for ally in participants.get("defender_allies", []):
        if ally["id"] not in all_participant_ids:
            all_participant_ids.append(ally["id"])

    decisions = {}
    for gid in all_participant_ids:
        side = (
            "attacker"
            if gid == attacker_id or gid in [a["id"] for a in participants["attacker_allies"]]
            else "defender"
        )
        context_str = build_battle_context(participants, side, gid)
        general_data = _get_general(conn, gid)
        if general_data:
            decisions[gid] = general_decide(general_data, json.loads(context_str))

    return {
        "participants": participants,
        "decisions": decisions,
    }


GM_RESOLUTION_PROMPT = (
    "You are a Three Kingdoms battle resolution judge.\n\n"
    "Given battle context (stats, terrain, weather, decisions, effort),"
    " determine outcome.\n\n"
    "Rules:\n"
    '- outcome: "attacker_win", "defender_win", or "draw"\n'
    "- attacker/defender troops lost must be 0..starting troops\n"
    "- attacker_win -> new_owner = attacker's faction_id\n"
    "- defender_win/draw -> new_owner = null\n"
    "- effort (0.0-1.0): higher = more committed\n"
    "- Consider: troop counts, war/cmd/intel, terrain, weather, effort\n\n"
    "Output JSON:\n"
    '{"outcome":"...", "attacker_troops_lost":N, '
    '"defender_troops_lost":N, "new_owner":..., '
    '"narrative_concise":"...", "narrative_detailed":"..."}'
)


def resolve_battle(battle_data: dict) -> dict:
    """GM final LLM call: synthesize participant decisions into battle outcome.

    Returns result dict ready for apply_battle_result().
    """
    participants = battle_data["participants"]
    decisions = battle_data["decisions"]
    atk = participants["attacker"]
    dfd = participants["defender"]

    context_parts = [
        f"战场: {participants['city'].get('name', participants['city']['id'])}",
        (
            f"地形: {participants['terrain']}  季节: {participants['season']}"
            f"  天气: {participants['weather']}"
        ),
        f"第 {participants['current_day']} 天",
        "",
        "── 进攻方 ──",
        f"主将: {atk['name']}  武:{atk['war']} 统:{atk['cmd']} 智:{atk['intel']}",
        f"兵力: {atk['troops']}  粮草: {atk['food']}日",
        f"决策: {json.dumps(decisions.get(atk['id'], {}), ensure_ascii=False)}",
    ]
    if participants["attacker_allies"]:
        context_parts.append("进攻方援军:")
        for ally in participants["attacker_allies"]:
            d = decisions.get(ally["id"], {})
            context_parts.append(
                f"  {ally['name']}  兵:{ally['troops']}  武:{ally['war']}  "
                f"决策:{json.dumps(d, ensure_ascii=False)}"
            )

    context_parts.extend(
        [
            "",
            "── 防守方 ──",
            f"主将: {dfd['name']}  武:{dfd['war']} 统:{dfd['cmd']} 智:{dfd['intel']}",
            f"兵力: {dfd['troops']}  粮草: {dfd['food']}日",
            f"决策: {json.dumps(decisions.get(dfd['id'], {}), ensure_ascii=False)}",
        ]
    )
    if participants["defender_allies"]:
        context_parts.append("防守方援军:")
        for ally in participants["defender_allies"]:
            d = decisions.get(ally["id"], {})
            context_parts.append(
                f"  {ally['name']}  兵:{ally['troops']}  武:{ally['war']}  "
                f"决策:{json.dumps(d, ensure_ascii=False)}"
            )

    context_parts.append("")
    context_parts.append("基于以上战况，判定战斗结果。")
    user_message = "\n".join(context_parts)

    model = get_decision_model()
    gm_result = llm_call_json(GM_RESOLUTION_PROMPT, user_message, model=model)

    city = participants["city"]
    atk_lost = gm_result.get("attacker_troops_lost", 0)
    dfd_lost = gm_result.get("defender_troops_lost", 0)
    outcome = gm_result.get("outcome", "draw")
    new_owner = None
    if outcome == "attacker_win":
        new_owner = gm_result.get("new_owner") or atk["faction_id"]

    return {
        "attacker_id": atk["id"],
        "defender_id": dfd["id"],
        "city_id": city["id"],
        "attacker_final_troops": max(0, atk["troops"] - atk_lost),
        "defender_final_troops": max(0, dfd["troops"] - dfd_lost),
        "outcome": outcome,
        "attacker_troops_lost": atk_lost,
        "defender_troops_lost": dfd_lost,
        "new_owner": new_owner,
        "narrative_concise": gm_result.get("narrative_concise", ""),
        "narrative_detailed": gm_result.get("narrative_detailed", ""),
        "attacker_name": atk["name"],
        "defender_name": dfd["name"],
        "city_name": city.get("name", city["id"]),
        "weather": participants.get("weather", "?"),
    }
