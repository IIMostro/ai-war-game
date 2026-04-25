# AGENTS.md

## Project Status

全阶段实现完成。自包含 Python 沙盘战争游戏，无外部 Agent 依赖。

- CLI 入口 (`uv run python -m ai_war_game`)
- 建局、推进时间、战斗、武将自主行为均已实现
- Game design spec in `docs/superpowers/specs/`

## Tech Stack

- Language: Python 3.12+
- Package manager: [uv](https://docs.astral.sh/uv/)
- LLM: [litellm](https://github.com/BerriAI/litellm) (OpenAI/Claude/Ollama 等 100+ 模型)
- Storage: SQLite (stdlib `sqlite3`) + JSON graph triple store

## Commands

```bash
uv run python -m ai_war_game    # 启动游戏
uv run pytest                    # Run tests
uv run ruff check .              # Lint
uv run ruff format .             # Format
```

## Architecture

```
src/ai_war_game/
├── __init__.py
├── __main__.py            # python -m 入口
├── cli.py                 # REPL 循环 + 命令路由
├── llm.py                 # litellm LLM 封装
├── db.py                  # SQLite 数据库层
├── view.py                # 展示格式化
├── engine.py              # 时间推进 + 事件队列
├── battle.py              # 战斗系统
├── autonomy.py            # 武将自主决策
├── init_scenario.py       # LLM 剧本生成
└── models.py              # 数据类

data/
├── game.db                # SQLite 数据库
└── graph.json             # 三元组存储 (城池连接 + 关系)
```

### 数据流

```
玩家 (CLI)
  │
  ├── cli.py 识别命令
  │     规则路由 (str.startswith) + LLM fallback
  │
  ├── Python 函数直接调用
  │     db.py           — 数据库 CRUD
  │     view.py         — 展示格式化
  │     engine.py       — 推进时间、处理事件
  │     battle.py       — 战斗编排
  │     autonomy.py     — 武将自主决策 (同进程 LLM 调用)
  │
  └── llm.py (litellm)
        init_scenario — 剧本生成
        general_decide — 武将决策
```

### 游戏循环

1. 玩家下令 → CLI 识别命令类型
2. 推进时间 (`engine.advance`)
3. 处理触发事件（战斗、粮草预警、到达等）
4. 武将自主行为 (`autonomy.trigger_all_autonomy`)
5. 展示结果 (`view.format_show`)

## Conventions

- Use `uv` for all dependency management (no pip/poetry)
- Keep README.md in sync with actual setup commands
- When adding tools (linter, formatter, test runner), update commands above
