"""终端文本格式化辅助."""

from collections.abc import Iterable

from ai_war_game.application.dto import SaveSummary, ShowGameOutput


def format_show_output(view: ShowGameOutput) -> str:
    lines = [
        f"存档: {view.save_id}",
        f"当前日期: 第 {view.current_day} 天",
        f"玩家: {view.player_display_name} ({view.faction_name})",
        f"摘要: {view.summary}",
    ]
    if view.recent_events:
        lines.append("最近事件:")
        for entry in view.recent_events:
            lines.append(f"  - {entry}")
    else:
        lines.append("最近事件: (无)")
    return "\n".join(lines)


def format_save_summaries(items: Iterable[SaveSummary]) -> str:
    rows = list(items)
    if not rows:
        return "(无存档)"
    lines = ["save_id\t当前日\t玩家\t创建时间\t更新时间"]
    for r in rows:
        lines.append(
            f"{r.save_id}\t{r.current_day}\t{r.player_display_name}\t"
            f"{r.created_at.isoformat()}\t{r.updated_at.isoformat()}"
        )
    return "\n".join(lines)
