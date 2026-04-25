from ai_war_game.cli import exit_codes
from ai_war_game.cli.app import run

from .test_new_game_flow import _scenario_payload, _setup_fake_hermes


def test_should_list_existing_saves(tmp_path, monkeypatch, capsys):
    _setup_fake_hermes(tmp_path, monkeypatch, _scenario_payload())
    save_root = tmp_path / "saves"
    for sid in ("save-a", "save-b"):
        run(
            argv=[
                "--save-root", str(save_root),
                "new-game",
                "--save-id", sid,
                "--theme", "三国",
                "--player-id", "p1",
                "--player-name", "刘备",
            ]
        )
    capsys.readouterr()
    rc = run(argv=["--save-root", str(save_root), "list-saves"])
    out = capsys.readouterr().out
    assert rc == exit_codes.OK
    assert "save-a" in out
    assert "save-b" in out


def test_should_print_empty_marker(tmp_path, capsys):
    save_root = tmp_path / "saves"
    save_root.mkdir()
    rc = run(argv=["--save-root", str(save_root), "list-saves"])
    out = capsys.readouterr().out
    assert rc == exit_codes.OK
    assert "无存档" in out
