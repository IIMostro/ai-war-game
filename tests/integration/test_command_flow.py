import json

from ai_war_game.cli import exit_codes
from ai_war_game.cli.app import run

from .test_new_game_flow import _scenario_payload, _setup_fake_hermes


def test_should_advance_day_and_persist(tmp_path, monkeypatch, capsys):
    _setup_fake_hermes(tmp_path, monkeypatch, _scenario_payload())
    save_root = tmp_path / "saves"
    run(
        argv=[
            "--save-root",
            str(save_root),
            "new-game",
            "--save-id",
            "save-1",
            "--theme",
            "三国",
            "--player-id",
            "p1",
            "--player-name",
            "刘备",
        ]
    )
    capsys.readouterr()
    rc = run(
        argv=[
            "--save-root",
            str(save_root),
            "command",
            "--save-id",
            "save-1",
            "--player-id",
            "p1",
            "--text",
            "进军洛阳",
        ]
    )
    assert rc == exit_codes.OK
    out = capsys.readouterr().out
    assert "第 2 天" in out
    session_payload = json.loads(
        (save_root / "save-1" / "session.json").read_text(encoding="utf-8")
    )
    assert session_payload["world"]["current_day"] == 2
    events_text = (save_root / "save-1" / "events.jsonl").read_text(encoding="utf-8")
    assert "进军洛阳" in events_text


def test_should_return_error_when_save_missing(tmp_path):
    save_root = tmp_path / "saves"
    rc = run(
        argv=[
            "--save-root",
            str(save_root),
            "command",
            "--save-id",
            "missing",
            "--player-id",
            "p1",
            "--text",
            "x",
        ]
    )
    assert rc == exit_codes.SAVE_NOT_FOUND
