# AI War Game

AI 驱动的沙盘战争游戏。每位武将是独立 AI Agent，拥有独立人格与记忆。玩家通过自然语言指挥全局。

## Quick Start

```bash
# 1. 安装依赖
uv sync

# 2. 配置 LLM
export AI_WAR_GAME_LLM_MODEL="openai/gpt-4o-mini"
export AI_WAR_GAME_LLM_API_KEY="sk-..."

# 3. 开始游戏
uv run python -m ai_war_game
```

## 环境变量

| 变量 | 必填 | 含义 |
|---|---|---|
| `AI_WAR_GAME_LLM_MODEL` | 否 | LLM 模型标识 (默认 `openai/gpt-4o-mini`) |
| `AI_WAR_GAME_LLM_API_KEY` | 否 | API key (也支持标准 `OPENAI_API_KEY`) |
| `AI_WAR_GAME_LLM_API_BASE` | 否 | 自定义 API base URL |

支持 litellm 所有格式: `openai/gpt-4`, `anthropic/claude-sonnet-4`, `ollama/llama3` 等。

## 架构

```
玩家输入
  │
  ├── CLI (src/ai_war_game/cli.py)
  │     命令路由规则 → Python 函数直接调用
  │     无法识别的命令 → LLM fallback
  │
  ├── 核心模块
  │     db.py      — SQLite 数据库层
  │     view.py    — 展示格式化
  │     engine.py  — 时间推进 + 事件队列
  │     battle.py  — 战斗结算
  │     autonomy.py — 武将 LLM 决策
  │
  └── LLM 层 (litellm)
        llm.py — 统一 LLM 调用接口
```

## 数据存储

```
data/
├── game.db              # SQLite: factions, cities, generals, game_state, events_log, general_memories
└── graph.json           # 三元组: 城池连接 + 武将关系
```

## 模块说明

| 模块 | 功能 |
|---|---|
| `db.py` | SQLite 数据库层 (6 表 + 图存储 + 事件日志) |
| `view.py` | 展示格式化 (局势/武将/地图/事件) |
| `init_scenario.py` | LLM 生成游戏世界 → 校验 → 持久化 |
| `engine.py` | 时间推进 + 事件队列 + 天气/季节 + 粮草消耗 |
| `battle.py` | 战斗系统 (战场识别/LLM 决策/战果应用/战报) |
| `autonomy.py` | 武将自主决策 (同进程 LLM 调用) |
| `llm.py` | litellm 统一 LLM 封装 |

## Development

```bash
uv run python -m ai_war_game    # 启动游戏
uv run pytest                    # 运行测试
uv run ruff check .              # Lint
uv run ruff format .             # Format
```

## 设计文档

- [主规格](docs/superpowers/specs/2026-04-23-three-kingdoms-game-design.md)
- [Hermes 移除设计](docs/superpowers/specs/2026-04-25-hermes-removal-design.md)
