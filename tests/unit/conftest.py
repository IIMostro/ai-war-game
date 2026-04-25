"""单元测试共享 fixture。"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ai_war_game.domain.errors import HermesUnavailableError, SaveNotFoundError
from ai_war_game.domain.events import GameEvent
from ai_war_game.domain.scenario import Scenario
from ai_war_game.domain.session import GameSession


class FakeHermesHealth:
    def __init__(self, *, ok: bool, reasons: tuple[str, ...] = ()) -> None:
        self._ok = ok
        self._reasons = reasons

    def check(self) -> None:
        if not self._ok:
            raise HermesUnavailableError("; ".join(self._reasons) or "fake unavailable")


class FakeScenarioGenerator:
    def generate(self, *, theme: str, player_display_name: str) -> Scenario:
        return Scenario(
            theme=theme,
            summary=f"{player_display_name} 加入 {theme} 战局。",
            starting_day=1,
            raw_payload={
                "summary": f"{player_display_name} 加入 {theme} 战局。",
                "starting_day": 1,
                "player": {
                    "display_name": player_display_name,
                    "faction_id": "shu",
                },
                "factions": [
                    {
                        "faction_id": "shu",
                        "name": "蜀汉",
                        "leader_character_id": "liubei",
                    }
                ],
                "characters": [
                    {
                        "character_id": "liubei",
                        "name": "刘备",
                        "faction_id": "shu",
                    }
                ],
                "settlements": [
                    {
                        "settlement_id": "chengdu",
                        "name": "成都",
                        "controlling_faction_id": "shu",
                    }
                ],
                "player_settlement_id": "chengdu",
            },
        )


class InMemoryGameRepository:
    def __init__(self) -> None:
        self._sessions: dict[str, GameSession] = {}
        self._events: dict[str, list[GameEvent]] = {}

    def save_session(self, session: GameSession) -> None:
        self._sessions[session.save_id] = session
        self._events.setdefault(session.save_id, [])

    def load_session(self, save_id: str) -> GameSession:
        if save_id not in self._sessions:
            raise SaveNotFoundError(save_id)
        return self._sessions[save_id]

    def append_event(self, save_id: str, event: GameEvent) -> None:
        self._events.setdefault(save_id, []).append(event)

    def list_save_ids(self) -> list[str]:
        return list(self._sessions)

    def events(self, save_id: str) -> list[GameEvent]:
        return list(self._events.get(save_id, []))


@pytest.fixture
def now_utc() -> datetime:
    return datetime(2026, 4, 25, 12, 0, tzinfo=UTC)


@pytest.fixture
def fake_hermes_ok() -> FakeHermesHealth:
    return FakeHermesHealth(ok=True)


@pytest.fixture
def fake_hermes_failing() -> FakeHermesHealth:
    return FakeHermesHealth(ok=False, reasons=("hermes 未安装", "缺少 model 配置"))


@pytest.fixture
def fake_scenario_generator() -> FakeScenarioGenerator:
    return FakeScenarioGenerator()


@pytest.fixture
def in_memory_repo() -> InMemoryGameRepository:
    return InMemoryGameRepository()


@pytest.fixture
def save_root(tmp_path: Path) -> Path:
    root = tmp_path / "saves"
    root.mkdir()
    return root
