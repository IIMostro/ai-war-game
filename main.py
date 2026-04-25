"""Entry point. Use `uv run python -m ai_war_game` or `ai-war-game` CLI."""
from ai_war_game.cli import run_cli

if __name__ == "__main__":
    raise SystemExit(run_cli())
