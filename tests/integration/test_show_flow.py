from ai_war_game.cli import exit_codes
from ai_war_game.cli.app import run

from .test_new_game_flow import _scenario_payload, _setup_fake_hermes


def test_should_show_existing_save(tmp_path, monkeypatch, capsys):
    _setup_fake_hermes(tmp_path, monkeypatch, _scenario_payload())
    save_root = tmp_path / "saves"
    run(
        argv=[
            "--save-root", str(save_root),
            "new-game",
            "--save-id", "save-1",
            "--theme", "三国",
            "--player-id", "p1",
            "--player-name", "刘备",
        ]
    )
    capsys.readouterr()
    rc = run(argv=["--save-root", str(save_root), "show", "--save-id", "save-1"])
    out = capsys.readouterr().out
    assert rc == exit_codes.OK
    assert "刘备" in out
    assert "蜀汉" in out
    assert "第 1 天" in out


def test_should_return_error_when_save_missing(tmp_path, capsys):
    save_root = tmp_path / "saves"
    rc = run(argv=["--save-root", str(save_root), "show", "--save-id", "missing"])
    assert rc == exit_codes.SAVE_NOT_FOUND
