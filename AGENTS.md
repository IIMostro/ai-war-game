# AGENTS.md

## Project Status

Python CLI game initialized with `uv`. Game design spec in `docs/superpowers/specs/`.

## Tech Stack

- Language: Python 3.12+
- Package manager: [uv](https://docs.astral.sh/uv/)
- Interface: CLI (+ WeChat via Hermes Agent gateway)
- Dependency: [Hermes Agent](https://github.com/nousresearch/hermes-agent) (vendored in `vendors/hermes-agent`)

## Commands

```bash
uv run python main.py          # Run the game
uv add <package>               # Add dependency
uv run pytest                  # Run tests
uv run ruff check .            # Lint
uv run ruff format .           # Format
```

## Conventions

- Use `uv` for all dependency management (no pip/poetry)
- Keep README.md in sync with actual setup commands
- When adding tools (linter, formatter, test runner), update commands above
