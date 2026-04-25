"""基于本地文件系统的存档实现."""

import json
from dataclasses import dataclass
from pathlib import Path

from ai_war_game.domain.errors import SaveCorruptedError, SaveNotFoundError
from ai_war_game.domain.events import GameEvent
from ai_war_game.domain.session import GameSession
from ai_war_game.infrastructure.persistence.codecs import (
    decode_event,
    decode_session,
    encode_event,
    encode_session,
)
from ai_war_game.infrastructure.persistence.paths import SaveLocator


@dataclass(slots=True)
class FileGameRepository:
    locator: SaveLocator

    def save_session(self, session: GameSession) -> None:
        self.locator.ensure_root()
        save_dir = self.locator.dir_for(session.save_id)
        save_dir.mkdir(parents=True, exist_ok=True)
        session_payload = encode_session(session)
        _atomic_write_json(save_dir / "session.json", session_payload)
        _atomic_write_json(save_dir / "world.json", session_payload["world"])
        _atomic_write_json(save_dir / "scenario.json", session_payload["scenario"])
        events_path = save_dir / "events.jsonl"
        if not events_path.exists():
            events_path.touch()

    def load_session(self, save_id: str) -> GameSession:
        save_dir = self.locator.dir_for(save_id)
        session_path = save_dir / "session.json"
        if not session_path.exists():
            raise SaveNotFoundError(save_id)
        try:
            payload = json.loads(session_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SaveCorruptedError(f"session.json 不是合法 JSON: {exc}") from exc
        return decode_session(payload)

    def append_event(self, save_id: str, event: GameEvent) -> None:
        save_dir = self.locator.dir_for(save_id)
        if not save_dir.exists():
            raise SaveNotFoundError(save_id)
        events_path = save_dir / "events.jsonl"
        with events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(encode_event(event), ensure_ascii=False))
            fh.write("\n")

    def events(self, save_id: str) -> list[GameEvent]:
        save_dir = self.locator.dir_for(save_id)
        events_path = save_dir / "events.jsonl"
        if not events_path.exists():
            return []
        events: list[GameEvent] = []
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                events.append(decode_event(json.loads(line)))
            except json.JSONDecodeError as exc:
                raise SaveCorruptedError(f"events.jsonl 行无法解析: {exc}") from exc
        return events

    def list_save_ids(self) -> list[str]:
        return sorted(self.locator.iter_save_ids())


def _atomic_write_json(path: Path, payload: dict | list) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
