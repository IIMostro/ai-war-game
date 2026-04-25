import json
from pathlib import Path

from ai_war_game.cli import exit_codes
from ai_war_game.cli.app import run


def _scenario_payload() -> str:
    return json.dumps(
        {
            "summary": "群雄逐鹿, 蜀汉初立.",
            "starting_day": 1,
            "player": {"display_name": "刘备", "faction_id": "shu"},
            "factions": [
                {"faction_id": "shu", "name": "蜀汉", "leader_character_id": "liubei"}
            ],
            "characters": [
                {"character_id": "liubei", "name": "刘备", "faction_id": "shu"}
            ],
            "settlements": [
                {"settlement_id": "chengdu", "name": "成都", "controlling_faction_id": "shu"}
            ],
            "player_settlement_id": "chengdu",
        },
        ensure_ascii=False,
    )


def _setup_fake_hermes(tmp_path: Path, monkeypatch, payload: str) -> None:
    bin_path = tmp_path / "hermes"
    bin_path.write_text(
        "#!/bin/sh\ncat > /dev/null\nprintf '%s' \"$AI_WAR_GAME_HERMES_FAKE_OUTPUT\"\n"
    )
    bin_path.chmod(0o755)
    config = tmp_path / "config.yaml"
    config.write_text("ok")
    monkeypatch.setenv("AI_WAR_GAME_HERMES_BIN", str(bin_path))
    monkeypatch.setenv("AI_WAR_GAME_HERMES_MODEL", "fake-model")
    monkeypatch.setenv("AI_WAR_GAME_HERMES_CONFIG", str(config))
    monkeypatch.setenv("AI_WAR_GAME_HERMES_FAKE_OUTPUT", payload)


def test_new_game_creates_save(tmp_path, monkeypatch, capsys):
    _setup_fake_hermes(tmp_path, monkeypatch, _scenario_payload())
    save_root = tmp_path / "saves"
    rc = run(
        argv=[
            "--save-root", str(save_root),
            "new-game",
            "--save-id", "save-1",
            "--theme", "三国",
            "--player-id", "p1",
            "--player-name", "刘备",
        ]
    )
    assert rc == exit_codes.OK
    assert (save_root / "save-1" / "session.json").is_file()
    assert (save_root / "save-1" / "scenario.json").is_file()
    out = capsys.readouterr().out
    assert "save-1" in out


def test_new_game_fails_when_hermes_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("AI_WAR_GAME_HERMES_BIN", str(tmp_path / "absent"))
    monkeypatch.delenv("AI_WAR_GAME_HERMES_MODEL", raising=False)
    monkeypatch.delenv("AI_WAR_GAME_HERMES_CONFIG", raising=False)
    save_root = tmp_path / "saves"
    rc = run(
        argv=[
            "--save-root", str(save_root),
            "new-game",
            "--save-id", "save-1",
            "--theme", "三国",
            "--player-id", "p1",
            "--player-name", "刘备",
        ]
    )
    assert rc == exit_codes.HERMES_UNAVAILABLE
    err = capsys.readouterr().err
    assert "Hermes" in err
    assert not (save_root / "save-1").exists()
