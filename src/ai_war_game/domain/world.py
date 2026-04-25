"""第一版世界状态模型: 势力、角色、聚落、世界快照。"""

from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True)
class Faction:
    faction_id: str
    name: str
    leader_character_id: str


@dataclass(frozen=True, slots=True)
class Character:
    character_id: str
    name: str
    faction_id: str


@dataclass(frozen=True, slots=True)
class Settlement:
    settlement_id: str
    name: str
    controlling_faction_id: str


@dataclass(frozen=True, slots=True)
class WorldState:
    """第一版世界快照 (不可变)."""

    current_day: int
    factions: tuple[Faction, ...]
    characters: tuple[Character, ...]
    settlements: tuple[Settlement, ...]
    player_settlement_id: str

    def __post_init__(self) -> None:
        if self.current_day < 1:
            raise ValueError("current_day 必须 >= 1")
        if not self.factions:
            raise ValueError("factions 不能为空")
        if not self.characters:
            raise ValueError("characters 不能为空")
        if not self.settlements:
            raise ValueError("settlements 不能为空")
        settlement_ids = {s.settlement_id for s in self.settlements}
        if self.player_settlement_id not in settlement_ids:
            raise ValueError(
                f"player_settlement_id={self.player_settlement_id} 不存在于 settlements"
            )

    def faction(self, faction_id: str) -> Faction:
        for faction in self.factions:
            if faction.faction_id == faction_id:
                return faction
        raise KeyError(faction_id)

    def character(self, character_id: str) -> Character:
        for character in self.characters:
            if character.character_id == character_id:
                return character
        raise KeyError(character_id)

    def settlement(self, settlement_id: str) -> Settlement:
        for settlement in self.settlements:
            if settlement.settlement_id == settlement_id:
                return settlement
        raise KeyError(settlement_id)

    def advance_day(self) -> "WorldState":
        return replace(self, current_day=self.current_day + 1)
