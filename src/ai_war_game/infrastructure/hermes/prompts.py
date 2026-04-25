"""第一版剧本生成 prompt 模板."""

import json

PROMPT_TEMPLATE = """你是 AI 沙盘战争游戏的剧本生成器. 请基于以下设定生成一份初始剧本.

主题: {theme}
玩家显示名: {player_display_name}

要求严格输出单一 JSON 对象, 不要任何额外说明或 Markdown 代码块.
JSON 必须包含以下字段:
- summary: string
- starting_day: int >= 1
- player: {{ display_name: string, faction_id: string }}
- factions: 至少 1 项, 元素 {{ faction_id, name, leader_character_id }}
- characters: 至少 1 项, 元素 {{ character_id, name, faction_id }}
- settlements: 至少 1 项, 元素 {{ settlement_id, name, controlling_faction_id }}
- player_settlement_id: 必须存在于 settlements 中
"""


def render_prompt(*, theme: str, player_display_name: str) -> str:
    return PROMPT_TEMPLATE.format(
        theme=json.dumps(theme, ensure_ascii=False)[1:-1],
        player_display_name=json.dumps(player_display_name, ensure_ascii=False)[1:-1],
    )
