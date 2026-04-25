"""遗留入口. 请使用 `ai-war-game` 命令或 `uv run python -m ai_war_game`."""

from ai_war_game.cli.app import run

if __name__ == "__main__":
    raise SystemExit(run())
