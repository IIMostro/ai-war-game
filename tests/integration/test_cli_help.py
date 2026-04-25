from ai_war_game.cli import exit_codes
from ai_war_game.cli.app import build_parser, run


def test_should_render_help_with_all_commands():
    parser = build_parser()
    help_text = parser.format_help()
    for cmd in ("new-game", "show", "command", "list-saves"):
        assert cmd in help_text


def test_should_exit_with_usage_error_when_no_command(capsys):
    rc = run(argv=[])
    assert rc == exit_codes.USAGE_ERROR
    captured = capsys.readouterr()
    assert "usage" in captured.err.lower() or "用法" in captured.err or "缺少" in captured.err
