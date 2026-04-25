"""玩家身份值对象。"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlayerIdentity:
    """游戏中代表玩家在某局内的身份与所属势力。"""

    player_id: str
    display_name: str
    faction_id: str

    def __post_init__(self) -> None:
        if not self.player_id.strip():
            raise ValueError("player_id 不能为空")
        if not self.display_name.strip():
            raise ValueError("display_name 不能为空")
        if not self.faction_id.strip():
            raise ValueError("faction_id 不能为空")
