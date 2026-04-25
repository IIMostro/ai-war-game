# AGENTS.md

## Project Status

Python CLI game. 第一版可运行骨架已完成 (new-game / show / command / list-saves).
Game design spec in `docs/superpowers/specs/`.

## Tech Stack

- Language: Python 3.12+
- Package manager: [uv](https://docs.astral.sh/uv/)
- Interface: CLI (+ WeChat via Hermes Agent gateway)
- Dependency: [Hermes Agent](https://github.com/nousresearch/hermes-agent) (vendored in `vendors/hermes-agent`)

## Commands

```bash
uv run ai-war-game --help      # CLI entry point
uv add <package>               # Add dependency
uv run pytest                  # Run tests
uv run ruff check .            # Lint
uv run ruff format .           # Format
```

## Architecture (第一版)

- `src/ai_war_game/cli`: argparse 子命令分发与终端输出
- `src/ai_war_game/application`: 用例服务 (CreateGame / Show / ExecuteCommand / ListSaves)
- `src/ai_war_game/domain`: 纯领域模型与最小规则
- `src/ai_war_game/infrastructure/persistence`: 文件型存档 (session/world/scenario.json + events.jsonl)
- `src/ai_war_game/infrastructure/hermes`: Hermes 环境检查 / prompt / subprocess 客户端
- `src/ai_war_game/interfaces`: CommandEnvelope (CLI / WeChat 共用入口模型)

## Hermes 环境变量

| 变量 | 必填 | 含义 |
|---|---|---|
| `AI_WAR_GAME_HERMES_BIN` | 否 | hermes 可执行文件路径, 默认 `hermes` |
| `AI_WAR_GAME_HERMES_MODEL` | 是 | 模型标识 |
| `AI_WAR_GAME_HERMES_CONFIG` | 是 | hermes 配置文件路径, 必须可读 |
| `AI_WAR_GAME_SAVE_ROOT` | 否 | 存档根目录, 默认 `./data/saves` |

## Conventions

- Use `uv` for all dependency management (no pip/poetry)
- Keep README.md in sync with actual setup commands
- When adding tools (linter, formatter, test runner), update commands above
