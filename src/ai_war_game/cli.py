"""cli.py — REPL entry point for AI War Game (replaces hermes chat + SKILL.md)."""

from __future__ import annotations

import sqlite3

from ai_war_game import db as war_db
from ai_war_game import view as war_view
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


def show_help() -> str:
    return """可用命令:
  new-game --theme <主题> --player <武将名>  创建新局
  status / 查看局势                         查看当前局势
  general <id> / 查看武将 <id>          查看武将详情
  map / 查看地图                           查看地图
  events / 查看事件                        查看最近事件
  advance --days N / 推进 N 天          推进时间
  battle --attacker <id> --defender <id>   发动战斗
  help                                     显示帮助
  exit / quit                              退出"""


def _run_with_db(func, db_path: str, *args, **kwargs):
    conn = sqlite3.connect(db_path)
    try:
        return func(conn, *args, **kwargs)
    finally:
        conn.close()


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
            conn = sqlite3.connect(db_path)
            try:
                cursor = conn.execute("SELECT value FROM game_state WHERE key='player_identity'")
                row = cursor.fetchone()
                if not row:
                    print("错误: 未找到玩家身份。先创建新局: new-game --theme ... --player ...")
                    continue
                player_id = row[0]
                general = war_db.get_general(conn, player_id)
                if not general:
                    print(f"错误: 未找到武将 {player_id}")
                    continue
                player_name = general["name"]
                faction_id = general["faction_id"]
                lines = war_view.format_show(conn, faction_id, player_id, player_name)
                print("\n".join(lines))
            finally:
                conn.close()

        elif cmd.startswith("general ") or cmd.startswith("查看武将"):
            parts = cmd.split()
            gid = parts[-1]
            lines = _run_with_db(war_view.format_general, db_path, gid)
            print("\n".join(lines))

        elif cmd in ("map", "查看地图"):
            lines = _run_with_db(war_view.format_map, db_path)
            print("\n".join(lines))

        elif cmd in ("events", "查看事件"):
            conn = sqlite3.connect(db_path)
            try:
                events = war_db.get_events(conn, limit=10)
                lines = war_view.format_events(events)
                print("\n".join(lines))
            finally:
                conn.close()

        elif cmd.startswith("advance") or cmd.startswith("推进"):
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
                print(f"推进了 {days} 天，触发 {len(events)} 个事件")
                if events:
                    for evt in events:
                        print(f"  第{evt['day']}日 [{evt['event_type']}]")
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
