# AI War Game Hermes 移除设计

## 背景

当前项目深度依赖 [Hermes Agent](https://github.com/nousresearch/hermes-agent)：

- **入口**: 玩家通过 `hermes chat` 进入游戏，Hermes 加载 `SKILL.md` 作为 GM Agent
- **LLM 调用**: `hermes_client.py` 通过 Hermes CLI subprocess 调用 LLM
- **多 Agent**: 每位武将是独立 Hermes profile，通过 `hermes -p <id> chat` 子进程通信
- **安装**: 需要用户预先安装 Hermes，配置 3 个环境变量

目标：**移除 Hermes 依赖，简化架构，去掉多 Agent 子系统**，使项目自包含、pip installable。

## 架构变化

### 当前

```
hermes chat → SKILL.md (GM) → terminal("python3 scripts/xxx") → hermes -p <id> chat
```

### 新架构

```
uv run python -m ai_war_game → Python CLI (GM 逻辑内嵌)
                                   │
                              ┌────┴────┐
                              │         │
                        同进程函数调用    LLM 调用 (litellm)
                        (engine,        ├── init_scenario (世界生成)
                         battle,        └── general_decide (武将决策)
                         view, db)
                              │
                         SQLite + JSON
```

### 核心变化

| 维度 | 当前 (Hermes) | 新方案 |
|------|--------------|--------|
| 玩家入口 | `hermes chat` → SKILL.md | Python REPL CLI (`python -m ai_war_game`) |
| GM Agent | Hermes 加载 SKILL.md 作为系统提示 | Python 代码内嵌 GM 提示词 + 命令路由 |
| LLM 调用 | `hermes_client.py` → `subprocess(["hermes", ...])` | `llm.py` → `litellm` SDK 直接调用 |
| 武将决策 | `agent_comm.py` → `hermes -p <id> chat` | `general_decide()` 同进程 LLM 调用 |
| 武将记忆 | `~/.hermes/profiles/<id>/MEMORY.md` | `general_memories` SQLite 表 |
| 武将人格 | `~/.hermes/profiles/<id>/SOUL.md` | SQLite `generals.personality` JSON 字段（已有） |
| 安装方式 | 安装 Hermes + 配置 3 个 env var + `install-skill.sh` | `uv sync` + 配 1 个 API key |

## 新目录结构

```
src/ai_war_game/
├── __init__.py
├── __main__.py            # python -m ai_war_game 入口
├── cli.py                 # REPL 循环 + 命令路由 (原 SKILL.md 职责)
├── llm.py                 # litellm 统一 LLM 封装 (原 hermes_client.py)
├── db.py                  # SQLite 层 (从 hermes-skill/scripts/db.py 移入, 去掉 CLI main)
├── view.py                # 展示格式化 (从 hermes-skill/scripts/view.py 移入, 去掉 CLI main)
├── engine.py              # 时间推进 + 事件 (从 time_engine.py 移入, 去掉 CLI main)
├── battle.py              # 战斗系统 (从 battle.py 移入, 去掉 agent_comm 依赖)
├── autonomy.py            # 武将自主决策 (从 autonomy.py 移入, 改用 llm.py)
├── init_scenario.py       # LLM 剧本生成 (从 init_scenario.py 移入, 改用 llm.py)
├── models.py              # 数据类: Faction, General, City

data/
├── game.db                # SQLite (不变)
└── graph.json             # 三元组 (不变)
```

## 各模块设计

### 1. LLM 抽象层 (`llm.py`)

```python
# 环境变量
AI_WAR_GAME_LLM_MODEL="openai/gpt-4"          # litellm 格式: provider/model
AI_WAR_GAME_LLM_API_KEY="sk-..."              # 也可用标准 OPENAI_API_KEY

# 接口
def llm_call(system_prompt: str, user_message: str, **kwargs) -> str
def llm_call_json(system_prompt: str, user_message: str, **kwargs) -> dict
```

- `llm_call` 基于 `litellm.completion()`，支持 100+ 模型（OpenAI/Anthropic/Ollama/vLLM 等）
- `llm_call_json` 在 system prompt 注入 JSON schema 约束，响应不是合法 JSON 时自动重试（最多 3 次）
- 错误处理：分别处理网络错误、速率限制、无效 JSON

### 2. CLI 入口 (`__main__.py` + `cli.py`)

GM 提示词（原 SKILL.md 内容）作为 Python 常量内嵌：

```python
GM_SYSTEM_PROMPT = """
你是三国沙盘战争的 Game Master。玩家通过自然语言向你下令。
- 查看局势 → python 函数调用
- 推进时间 → python 函数调用
- 发动战斗 → python 函数调用
- 无法识别的命令 → 调用 LLM 解释
"""
```

命令路由规则：

| 玩家输入 | 路由目标 |
|----------|---------|
| `查看局势` / `status` | `view.show()` |
| `查看武将 <name>` | `view.general(id)` |
| `查看地图` / `map` | `view.map()` |
| `查看事件` / `events` | `view.events(limit=10)` |
| `推进 N 天` / `等待 N 天` | `engine.advance(days=N)` |
| `攻击 <id> --city <id>` | `battle.start(attacker, defender, city)` |
| 其他 | `llm_call(GM_SYSTEM_PROMPT, cmd)` fallback |

CLI 运行模式：

```
$ uv run python -m ai_war_game
【AI 沙盘战争】
⚔ 创建新局 --theme 黄巾之乱 --player 曹操
[世界生成完成]
⚔ 查看局势
[当前局势展示]
⚔ help
[命令列表]
⚔ exit
```

### 3. 武将决策系统（替换 `agent_comm.py`）

**不再需要**：
- `~/.hermes/profiles/<id>/` 目录结构
- 文件 inbox/outbox 通信
- Hermes 子进程调用

**新的决策流程**：

```python
def general_decide(general: dict, context: dict, memory: str = "") -> dict:
    system_prompt = _build_personality_prompt(general, memory)
    user_message = json.dumps(context, ensure_ascii=False)
    return llm_call_json(system_prompt, user_message)
```

- `general["personality"]`（SQLite 已有 JSON 字段）替代 SOUL.md
- 新增 `general_memories` 表替代 MEMORY.md
- `battle.py` 和 `autonomy.py` 改为直接调用 `general_decide()` 函数

#### `general_memories` 表

```sql
CREATE TABLE IF NOT EXISTS general_memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    general_id TEXT NOT NULL REFERENCES generals(id),
    game_day INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    summary TEXT NOT NULL,
    details_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### 4. 剧本初始化（`init_scenario.py`）

变化最小：`hermes_client.call_hermes(prompt)` → `llm.llm_call_json(system_prompt, prompt)`

不再创建 Hermes profile 目录。武将人格数据直接存入 SQLite `generals.personality` 字段。

### 5. 战斗系统（`battle.py`）

`start_battle()` 不再 import `agent_comm` 的 `send_to_inbox/invoke_generals/collect_responses`。

替换为：

```python
def start_battle(conn, attacker_id, defender_id, city_id) -> dict:
    participants = identify_participants(conn, attacker_id, defender_id)
    # 直接调 general_decide 收集决策
    for gid in all_participant_ids:
        context = build_battle_context(participants, side, gid)
        decision = general_decide(general_data, context, memory)
        decisions[gid] = decision
    return {"participants": participants, "decisions": decisions}
```

### 6. 武将自主行为（`autonomy.py`）

同样替换 agent_comm 依赖：

```python
def trigger_autonomy(conn, general_id) -> dict:
    general = get_general(conn, general_id)
    context = build_autonomy_context(general, current_day, season)
    memory = get_memory(conn, general_id)
    decision = general_decide(general, context, memory)
    # 处理决策结果
```

## 删除内容

| 文件/目录 | 处理 |
|-----------|------|
| `hermes-skill/` 整个目录 | 删除（代码已迁移到 `src/ai_war_game/`） |
| `vendors/hermes-agent/` | 删除 git submodule |
| `tools/install-skill.sh` | 删除 |
| `src/ai_war_game/interfaces/` | 删除（CommandSource.HERMES 不再需要） |
| `INSTALL.md` | 删除（内容并入 README） |
| `README.md` | 重写，移除 Hermes 安装说明 |
| `AGENTS.md` | 更新架构描述 |
| `pyproject.toml` | 更新 description + test paths + src |
| 所有 Hermes 相关测试 | 删除或重写 |

## 新增/修改依赖

```toml
# pyproject.toml
[project]
dependencies = [
    "litellm>=1.60",
]

[project.scripts]
ai-war-game = "ai_war_game.__main__:main"
```

仅新增 `litellm` 一个运行时依赖（去掉了整个 Hermes Agent）。

## 测试策略

### 删除的测试
- `tests/unit/hermes_skill/test_hermes_client.py` — hermes_client 不再存在

### 修改的测试
- `tests/unit/hermes_skill/test_init_scenario.py` — 改为测试 `llm_call_json` mocking
- `tests/unit/hermes_skill/test_agent_comm.py` — 改为测试 `general_decide()` 函数
- `tests/unit/hermes_skill/test_battle.py` — 更新 mocking（no agent_comm）
- `tests/unit/hermes_skill/test_autonomy.py` — 更新 mocking（no agent_comm）

### 新增的测试
- `tests/unit/test_llm.py` — `llm_call` 和 `llm_call_json` 单元测试
- `tests/unit/test_cli.py` — 命令路由逻辑测试

### 保留的测试
- `tests/unit/hermes_skill/test_db.py` — 数据库层逻辑不变
- `tests/unit/hermes_skill/test_view.py` — 展示逻辑不变
- `tests/unit/hermes_skill/test_time_engine.py` — 时间引擎逻辑不变
- `tests/unit/hermes_skill/test_game_loop.py` — 更新模拟层即可

## 实施顺序

### Phase 1: LLM 抽象 + 核心模块迁移
1. 创建 `src/ai_war_game/llm.py`（litellm 封装）
2. 创建 `src/ai_war_game/models.py`（数据类）
3. 将 `db.py` 迁移为纯库模块（去掉 CLI main）
4. 将 `view.py` 迁移为纯库模块
5. 将 `engine.py` 从 `time_engine.py` 迁移
6. 更新 `pyproject.toml` 和 `__init__.py`

### Phase 2: CLI 入口 + 武将决策
7. 创建 `cli.py` + `__main__.py`（REPL + 命令路由）
8. 创建 `general_decide()` + `general_memories` 表
9. 重写 `battle.py`（去掉 agent_comm 依赖）
10. 重写 `autonomy.py`（改用 general_decide）
11. 重写 `init_scenario.py`（改用 llm.py）

### Phase 3: 清理
12. 删除 `hermes-skill/`、`vendors/hermes-agent/`、`tools/`
13. 删除 `interfaces/`、`INSTALL.md`
14. 重写 `README.md`、更新 `AGENTS.md`
15. 更新测试
16. 全面验证

## 不包含

- 保留 WeChat 接入能力（但需要适配新的入口）
- 不改变 SQLite schema（仅新增 `general_memories` 表）
- 不改变游戏逻辑和数值体系
- 不改变 JSON 三元组图存储
