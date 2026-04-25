"""tests/unit/test_cli.py"""

from ai_war_game.cli import show_help


class TestShowHelp:
    def test_contains_key_commands(self):
        text = show_help()
        assert "new-game" in text
        assert "status" in text
        assert "advance" in text
        assert "help" in text
        assert "exit" in text
