# AI War Game

AI-driven sandbox warfare game (AI 局沙盘) built on [Hermes Agent](https://github.com/nousresearch/hermes-agent).

## Quick Start

```bash
# 安装依赖
uv sync

# 查看 CLI 帮助
uv run ai-war-game --help

# 创建一局新游戏 (需先配置 Hermes 环境变量)
export AI_WAR_GAME_HERMES_BIN=/path/to/hermes
export AI_WAR_GAME_HERMES_MODEL=your-model-id
export AI_WAR_GAME_HERMES_CONFIG=/path/to/hermes/config.yaml
uv run ai-war-game new-game \
  --save-id demo --theme 三国 --player-id me --player-name 刘备

# 查看 / 执行命令 / 列表
uv run ai-war-game show --save-id demo
uv run ai-war-game command --save-id demo --player-id me --text "进军洛阳"
uv run ai-war-game list-saves
```

## 环境变量

| 变量 | 必填 | 含义 |
|---|---|---|
| `AI_WAR_GAME_HERMES_BIN` | 否 | hermes 可执行文件路径, 默认 `hermes` |
| `AI_WAR_GAME_HERMES_MODEL` | 是 | 模型标识 |
| `AI_WAR_GAME_HERMES_CONFIG` | 是 | hermes 配置文件路径, 必须可读 |
| `AI_WAR_GAME_SAVE_ROOT` | 否 | 存档根目录, 默认 `./data/saves`. 也可通过 `--save-root` 覆盖 |

## 存档目录结构

```
data/saves/<save-id>/
  session.json     # 会话元数据 + 玩家 + 剧本头 + 世界
  world.json       # 当前世界镜像 (便于阅读)
  scenario.json    # Hermes 原始剧本
  events.jsonl     # 事件追加日志
```

## 设计文档

- 第一版可运行版本设计: `docs/superpowers/specs/2026-04-24-first-runnable-version-design.md`

## Development

```bash
uv run pytest                # 运行全部测试
uv run ruff check .          # Lint
uv run ruff format .         # Format
uv run pip-audit             # 依赖审计
prek run --all-files         # 所有 git hook
```
