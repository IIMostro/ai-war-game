# AGENTS.md

## Project Status

全阶段实现完成。Hermes Skill 架构下可运行的沙盘战争游戏。

- Skill 注册后通过 Hermes Agent 入口交互（微信 / Hermes CLI）
- 建局、推进时间、战斗、多 Agent 通信、武将自主行为均已实现
- Game design spec in `docs/superpowers/specs/`

## Tech Stack

- Language: Python 3.12+
- Package manager: [uv](https://docs.astral.sh/uv/)
- Runtime: [Hermes Agent](https://github.com/nousresearch/hermes-agent) (vendored in `vendors/hermes-agent`)
- Storage: SQLite (stdlib `sqlite3`) + JSON graph triple store

## Commands

```bash
bash tools/install-skill.sh      # 注册 skill 到 Hermes
uv run pytest                    # Run tests (104 tests)
uv run ruff check .              # Lint
uv run ruff format .             # Format
```

## Architecture

### Hermes Skill (`hermes-skill/` → `~/.hermes/skills/strategy/ai-war-game/`)

```
hermes-skill/
├── SKILL.md                       # Game Master 规则书 & 脚本路由
├── lib/
│   └── hermes_client.py           # Hermes 环境检查 + subprocess 调用
├── scripts/
│   ├── db.py                      # SQLite 数据库层 (5 表 + 图存储 + CRUD CLI)
│   ├── view.py                    # 展示格式化 (局势/武将/地图/事件)
│   ├── init_scenario.py           # LLM 剧本生成 → 校验 → 持久化 → Hermes profiles
│   ├── agent_comm.py              # 多 Agent 通信 (send/invoke/collect/status/reflect)
│   ├── time_engine.py             # 时间推进 + 事件队列 + 天气/季节 + 粮草消耗
│   ├── battle.py                  # 战斗系统 (start/apply/report/mode)
│   └── autonomy.py                # 武将自主行为 (check/trigger/trigger-all)
└── data/                          # 运行时目录
    ├── game.db                    # SQLite 数据库
    └── graph.json                 # 三元组存储 (城池连接 + 关系)
```

### 数据流

```
玩家 (Hermes CLI / 微信)
  │
  ├── GM Agent (SKILL.md)
  │     全部行为由 SKILL.md 指导
  │
  ├── terminal("python3 scripts/<script> <args>") 调用脚本
  │     db.py          — 数据库 CRUD
  │     view.py        — 展示格式化
  │     time_engine.py — 推进时间、处理事件
  │     battle.py      — 战斗编排
  │     agent_comm.py  — 与武将 Agent 通信
  │     autonomy.py    — 武将自主决策
  │
  └── hermes -p <general> chat  (由 agent_comm invoke 触发)
        每位武将是独立 Hermes Agent，拥有 SOUL.md + MEMORY.md
```

### 游戏循环

1. 玩家下令 → GM 识别命令类型
2. 推进时间 (`time_engine.py advance`)
3. 处理触发事件（战斗、粮草预警、到达等）
4. 武将自主行为 (`autonomy.py trigger-all`)
5. 内存反思 (`agent_comm.py reflect`)
6. 展示结果 (`view.py show`)

## Hermes 环境变量

| 变量 | 必填 | 含义 |
|---|---|---|
| `AI_WAR_GAME_HERMES_BIN` | 否 | hermes 可执行文件路径, 默认 `hermes` |
| `AI_WAR_GAME_HERMES_MODEL` | 是 | 模型标识 |
| `AI_WAR_GAME_HERMES_CONFIG` | 是 | hermes 配置文件路径, 必须可读 |

## Conventions

- Use `uv` for all dependency management (no pip/poetry)
- Keep README.md in sync with actual setup commands
- When adding tools (linter, formatter, test runner), update commands above
