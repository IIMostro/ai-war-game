"""cli.py — REPL entry point for AI War Game."""

from __future__ import annotations

import json
import sqlite3

from ai_war_game import db as war_db
from ai_war_game import view as war_view
from ai_war_game.autonomy import trigger_all_autonomy
from ai_war_game.engine import advance_time, get_event_queue_path
from ai_war_game.init_scenario import init_scenario
from ai_war_game.llm import LLMError, llm_call

GM_SYSTEM_PROMPT = """你是三国沙盘战争的 Game Master。
每次玩家下令的处理流程:
1. 识别命令类型并调用对应函数
2. 推进时间(time_engine advance)
3. 处理触发事件(战斗/粮草预警/到达)
4. 武将自主行为(autonomy trigger-all)
5. 展示结果(view show)

核心规则:
- 武/统/智/政/魅: 1-100, 忠: 1-100(玩家null)
- 粮草不足5天预警，不足2天危急
- 战斗由你综合数值、天气、地形、人格生成结果
- 中文输出，简洁为主"""


def _run_with_db(func, db_path: str, *args, **kwargs):
    conn = sqlite3.connect(db_path)
    try:
        return func(conn, *args, **kwargs)
    finally:
        conn.close()


def show_help() -> str:
    return """可用命令:
  new-game --theme <主题> --player <武将名>  创建新局
  status / 查看局势                         查看当前局势
  generals / 武将列表                       列出所有武将
  general <名字> / 查看武将 <名字>          查看武将详情
  map / 查看地图                           查看地图
  events / 查看事件                        查看最近事件
  advance --days N / 推进 N 天              推进时间
  battle --attacker <id> --defender <id>   发动战斗
  help                                     显示帮助
  exit / quit                              退出"""


def _has_game(db_path: str) -> bool:
    """Check if a game exists (has player_identity in DB)."""
    """Check if a game exists (has player_identity in DB)."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT 1 FROM game_state WHERE key='player_identity'")
        exists = cursor.fetchone() is not None
        conn.close()
        return exists
    except (sqlite3.OperationalError, FileNotFoundError):
        return False


def _list_generals(conn: sqlite3.Connection) -> list[dict]:
    cursor = conn.execute(
        "SELECT g.id, g.name, g.troops, g.food, g.loyalty, g.is_player, "
        "c.name AS city, f.name AS faction "
        "FROM generals g "
        "LEFT JOIN cities c ON g.position_city_id = c.id "
        "LEFT JOIN factions f ON g.faction_id = f.id "
        "ORDER BY g.is_player DESC, g.name"
    )
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row, strict=False)) for row in cursor.fetchall()]


def _find_general(conn: sqlite3.Connection, text: str) -> dict | None:
    """Search general by ID or name (partial match). Returns first match."""
    general = war_db.get_general(conn, text)
    if general:
        return general
    cursor = conn.execute(
        "SELECT * FROM generals WHERE name LIKE ?",
        (f"%{text}%",),
    )
    row = cursor.fetchone()
    if row:
        cols = [desc[0] for desc in cursor.description]
        return dict(zip(cols, row, strict=False))
    return None


def run_cli(argv: list[str] | None = None) -> int:
    db_path = war_db.get_db_path(None)
    print("【AI 沙盘战争】输入 'help' 查看命令")

    while True:
        try:
            cmd = input("⚔ ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not cmd:
            continue
        if cmd in ("exit", "quit", "q"):
            break
        if cmd == "help":
            print(show_help())
            continue

        if cmd.startswith("new-game"):
            parts = cmd.split()
            try:
                theme_idx = parts.index("--theme") + 1
                player_idx = parts.index("--player") + 1
                theme = parts[theme_idx]
                player = parts[player_idx]
            except (ValueError, IndexError):
                print("用法: new-game --theme <主题> --player <武将名>")
                print("  例如: new-game --theme 黄巾之乱 --player 曹操")
                continue
            try:
                result = init_scenario(theme, player, db_path)
                print(f"世界生成完成: {result['scenario']}")
                print(
                    f"  势力: {len(result['factions'])}  "
                    f"城池: {result['cities']}  "
                    f"武将: {result['generals']}"
                )
            except LLMError as e:
                print(f"剧本生成失败: {e}")

        elif cmd in ("status", "查看局势"):
            if not _has_game(db_path):
                print("还没有游戏。输入 new-game --theme <主题> --player <武将名> 创建新局")
                continue
            conn = sqlite3.connect(db_path)
            try:
                cursor = conn.execute("SELECT value FROM game_state WHERE key='player_identity'")
                player_identity = json.loads(cursor.fetchone()[0])
                player_id = player_identity.get("id", "")
                general = war_db.get_general(conn, player_id)
                if not general:
                    print(f"错误: 未找到武将 {player_id}")
                    continue
                lines = war_view.format_show(
                    conn, general["faction_id"], player_id, general["name"]
                )
                print("\n".join(lines))
            finally:
                conn.close()

        elif cmd in ("generals", "武将列表"):
            if not _has_game(db_path):
                print("还没有游戏。输入 new-game --theme <主题> --player <武将名> 创建新局")
                continue
            conn = sqlite3.connect(db_path)
            try:
                rows = _list_generals(conn)
                if not rows:
                    print("(无武将)")
                    continue
                print(f"【武将列表】共 {len(rows)} 人")
                for g in rows:
                    player_tag = " ★" if g["is_player"] else ""
                    city = g["city"] or g["faction"] or "?"
                    food_warn = " ⚠" if g["food"] and g["food"] < 5 else ""
                    print(
                        f"  {g['name']}{player_tag}"
                        f"  兵 {g['troops']}  粮 {g['food']}日{food_warn}"
                        f"  [{city}]"
                    )
            finally:
                conn.close()

        elif cmd.startswith("general ") or cmd.startswith("查看武将"):
            parts = cmd.split(maxsplit=1)
            if len(parts) < 2:
                print("用法: general <武将名>")
                continue
            name = parts[1]
            conn = sqlite3.connect(db_path)
            try:
                general = _find_general(conn, name)
                if not general:
                    print(f"未找到武将: {name}")
                    continue
                lines = war_view.format_general(conn, general["id"])
                print("\n".join(lines))
            finally:
                conn.close()

        elif cmd in ("map", "查看地图"):
            if not _has_game(db_path):
                print("还没有游戏。输入 new-game --theme <主题> --player <武将名> 创建新局")
                continue
            lines = _run_with_db(war_view.format_map, db_path)
            print("\n".join(lines))

        elif cmd in ("events", "查看事件"):
            if not _has_game(db_path):
                print("还没有游戏。输入 new-game --theme <主题> --player <武将名> 创建新局")
                continue
            conn = sqlite3.connect(db_path)
            try:
                events = war_db.get_events(conn, limit=10)
                lines = war_view.format_events(events)
                print("\n".join(lines))
            finally:
                conn.close()

        elif cmd.startswith("advance") or cmd.startswith("推进"):
            if not _has_game(db_path):
                print("还没有游戏。输入 new-game --theme <主题> --player <武将名> 创建新局")
                continue
            days = 1
            try:
                parts = cmd.split()
                if "--days" in parts:
                    days = int(parts[parts.index("--days") + 1])
                else:
                    for p in parts:
                        if p.isdigit():
                            days = int(p)
                            break
            except (ValueError, IndexError):
                pass

            queue_path = get_event_queue_path(db_path)
            graph_path = war_db.get_graph_path(db_path)
            conn = sqlite3.connect(db_path)
            try:
                events = advance_time(conn, queue_path, graph_path, days)

                cursor = conn.execute("SELECT value FROM game_state WHERE key='current_day'")
                current_day = cursor.fetchone()[0]
                cursor = conn.execute("SELECT value FROM game_state WHERE key='season'")
                season = cursor.fetchone()[0]
                cursor = conn.execute("SELECT value FROM game_state WHERE key='weather'")
                weather = cursor.fetchone()[0]

                print(f"▶ 第 {current_day} 天  {season}  {weather}")

                food_events = [e for e in events if "food" in e.get("event_type", "")]
                other_events = [e for e in events if "food" not in e.get("event_type", "")]

                for evt in other_events:
                    etype = evt["event_type"]
                    details = evt.get("details", {})
                    name = details.get("name", evt.get("actor_id", ""))
                    if etype == "food_critical":
                        print(f"  ⛔ {name} 粮草危急! (仅剩 {details.get('food', '?')} 天)")
                    elif etype == "food_warning":
                        print(f"  ⚠ {name} 粮草不足 (仅剩 {details.get('food', '?')} 天)")
                    else:
                        print(f"  [{etype}] {name}")

                if food_events:
                    warning_count = len(
                        [e for e in food_events if e["event_type"] == "food_warning"]
                    )
                    critical_count = len(
                        [e for e in food_events if e["event_type"] == "food_critical"]
                    )
                    parts_str = []
                    if warning_count:
                        parts_str.append(f"{warning_count} 个粮草预警")
                    if critical_count:
                        parts_str.append(f"{critical_count} 个粮草危急")
                    print(f"  {'，'.join(parts_str)}")

                autonomy_results = trigger_all_autonomy(conn)
                if autonomy_results:
                    print("\n  ── 武将动向 ──")
                    for r in autonomy_results:
                        name = r.get("name", r.get("general", "?"))
                        decision = r.get("decision", {})
                        action = decision.get("action", "idle")
                        narrative = decision.get("narrative", "")
                        effort = decision.get("effort", 0)
                        ai_actions = {
                            "idle": "按兵不动",
                            "fight": "准备出战",
                            "retreat": "准备撤退",
                            "negotiate": "寻求交涉",
                            "rebel": "图谋不轨!!",
                            "advise": "有所建言",
                            "train": "操练兵马",
                            "recruit": "招募兵勇",
                            "fortify": "修筑城防",
                        }
                        action_label = ai_actions.get(action, action)
                        effort_bar = "█" * int(effort * 10) + "░" * (10 - int(effort * 10))
                        print(f"  {name}: {action_label} [{effort_bar}]")
                        if narrative and len(narrative) < 80:
                            print(f"          {narrative}")
                    print()
            finally:
                conn.close()

        elif cmd.startswith("battle") or cmd.startswith("攻击"):
            print("战斗系统: 正在开发中，请使用 'advance' 推进时间")

        else:
            try:
                response = llm_call(GM_SYSTEM_PROMPT, cmd)
                print(response)
            except LLMError as e:
                print(f"无法理解命令: {e}")
                print("输入 'help' 查看可用命令")

    return 0
