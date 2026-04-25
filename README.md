# AI War Game

AI-driven sandbox warfare game (AI 局沙盘) built on [Hermes Agent](https://github.com/nousresearch/hermes-agent).
每位武将是持久化 AI Agent，拥有独立人格与记忆。玩家通过自然语言指挥全局。

## Quick Start

```bash
# 1. 安装依赖
uv sync

# 2. 注册 Hermes Skill
bash tools/install-skill.sh

# 3. 配置 Hermes 环境变量
export AI_WAR_GAME_HERMES_MODEL=your-model-id
export AI_WAR_GAME_HERMES_CONFIG=/path/to/hermes/config.yaml

# 4. 通过 Hermes CLI 游玩
hermes chat

# 在 hermes 中输入:
# > 我要玩黄巾之乱，当曹操
```

## 环境变量

| 变量 | 必填 | 含义 |
|---|---|---|
| `AI_WAR_GAME_HERMES_BIN` | 否 | hermes 可执行文件路径, 默认 `hermes` |
| `AI_WAR_GAME_HERMES_MODEL` | 是 | 模型标识 |
| `AI_WAR_GAME_HERMES_CONFIG` | 是 | hermes 配置文件路径, 必须可读 |

## 模块说明

| 脚本 | 功能 |
|---|---|
| `scripts/db.py` | SQLite 数据库 (5 表 + 图存储 + 事件日志 + CLI) |
| `scripts/view.py` | 展示格式化 (局势/武将/地图/事件) |
| `scripts/init_scenario.py` | LLM 生成游戏世界 → 校验 → 持久化 → 创建武将 Hermes profiles |
| `scripts/agent_comm.py` | 多 Agent 文件通信 (send/invoke/collect/status/reflect) |
| `scripts/time_engine.py` | 按天推进 + 事件队列 + 天气/季节 + 粮草消耗 |
| `scripts/battle.py` | 战斗系统 (战场识别/Agent 决策收集/战果应用/战报) |
| `scripts/autonomy.py` | 武将自主决策 (空闲检查/触发决策) |

## SKILL.md

`hermes-skill/SKILL.md` 是 Game Master Agent 的行为规则书。它定义了 GM 如何响应玩家命令、调用哪些脚本、以及游戏核心约束。玩家通过 `hermes chat` 交互时，GM Agent 按 SKILL.md 的规则运作。

## 数据存储

```
~/.hermes/skills/strategy/ai-war-game/data/
  game.db              # SQLite: factions, cities, generals, game_state, events_log
  graph.json           # 三元组: 城池连接 (含距离) + 武将关系

~/.hermes/profiles/<general_id>/
  SOUL.md              # 武将人格 & 决策规则
  MEMORY.md            # 累积记忆
  config.yaml          # 模型配置
```

## 设计文档

- [主规格](docs/superpowers/specs/2026-04-23-three-kingdoms-game-design.md)
- [P1-P3 Hermes Skill 迁移设计](docs/superpowers/specs/2026-04-25-hermes-skill-migration-design.md)

## Development

```bash
uv run pytest                # 运行全部测试 (104 tests)
uv run ruff check .          # Lint
uv run ruff format .         # Format
```
