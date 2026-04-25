# AI War Game Hermes Skill 迁移设计 (P1-P3)

## 背景

第一版可运行骨架已完成，实现了以下能力：

- CLI 入口 (new-game / show / command / list-saves)
- 基于 JSON 文件的多目录存档结构
- Hermes 健康检查与子进程调用生成剧本
- 最小领域模型 (Faction / Character / Settlement / GameSession / WorldState)

根据主规格 `2026-04-23-three-kingdoms-game-design.md` 的子项目拆分，下一阶段的目标是向 **Hermes Skill 架构** 迁移。具体范围为 **P1-P3**：

- **P1**: 创建 Hermes Skill 骨架 + SKILL.md
- **P2**: SQLite 数据库 + state/view 脚本
- **P3**: LLM 驱动的完整剧本初始化 + 武将 Profile 创建

## 架构决策

### 代码位置

开发代码保留在 git 仓库中，通过 `uv run install-skill` 命令在 `~/.hermes/skills/strategy/ai-war-game/` 建立 symlink。

### 入口变更

从 "Python argparse CLI 入口" 变更为 "Hermes Agent 通过 SKILL.md 调度脚本"。玩家通过 `hermes chat` 或微信与 GM Agent 交互，不再维护独立 CLI。

## 目录结构

```
~/.hermes/skills/strategy/ai-war-game/    (symlink → repo/hermes-skill/)
├── SKILL.md                               # Game Master 规则书 & 脚本路由
├── scripts/
│   ├── db.py                              # SQLite schema + CRUD + 事件日志
│   ├── view.py                            # 展示格式化
│   ├── init_scenario.py                   # LLM 剧本生成 + 校验 + 持久化
│   ├── init_prompt.txt                    # LLM prompt 模板
│   └── soul_general.txt                   # SOUL.md 渲染模板
└── data/
    ├── game.db                            # SQLite (运行时生成)
    └── graph.json                         # 三元组存储 (运行时生成)

~/.hermes/profiles/
  └── <general_id>/
      ├── SOUL.md                          # 武将人格 & 决策规则
      ├── MEMORY.md                        # 累积记忆
      └── config.yaml                      # 模型配置
```

## P1: SKILL.md 设计

### 定位

SKILL.md 是 Hermes Agent 的"游戏规则书"。它约束 GM Agent 的 LLM 行为，指引它在面对玩家命令时调用正确的脚本。

### 核心结构

```markdown
# AI War Game - Game Master Skill

## 概述
你是三国沙盘战争的 Game Master。玩家通过自然语言向你下令。
你负责: 读取状态、调用脚本处理逻辑、向玩家展示结果。

## 命令路由
每个玩家命令走以下流程:
1. 调用 `terminal("python3 scripts/db.py state read")` 读取当前状态
2. 识别命令类型: 查看 / 军事 / 内政 / 外交 / 系统
3. 按类型调用对应脚本
4. 向玩家展示结果

## 查看命令
- "查看当前局势" → terminal("python3 scripts/view.py show")
- "查看曹操" → terminal("python3 scripts/view.py general caocao")
- "查看地图" → terminal("python3 scripts/view.py map")

## 核心规则 (约束 GM Agent 行为)
- 武将属性: 武/统/智/政/魅 1-100, 忠 1-100
- 玩家角色 loyalty = null, 且 is_player = true
- 粮草按武将独立追踪, 不足 5 天预警, 不足 2 天危急
- 战斗结果由 LLM 综合数值、天气、地形、人格生成
- ...
```

### 不包含的内容

P1 的 SKILL.md 不包含多 Agent 编排、战斗结算、时间引擎流程。这些在后续 P4-P8 逐步添加。

## P2: 数据库层设计

### SQLite Schema

```sql
CREATE TABLE factions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE cities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    x INTEGER NOT NULL CHECK(x >= 0 AND x <= 1000),
    y INTEGER NOT NULL CHECK(y >= 0 AND y <= 1000),
    terrain TEXT NOT NULL CHECK(terrain IN ('平原', '山地', '水域', '森林')),
    owner_faction_id TEXT REFERENCES factions(id)
);

CREATE TABLE generals (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    war INTEGER NOT NULL CHECK(war >= 1 AND war <= 100),
    cmd INTEGER NOT NULL CHECK(cmd >= 1 AND cmd <= 100),
    intel INTEGER NOT NULL CHECK(intel >= 1 AND intel <= 100),
    politics INTEGER NOT NULL CHECK(politics >= 1 AND politics <= 100),
    charm INTEGER NOT NULL CHECK(charm >= 1 AND charm <= 100),
    loyalty INTEGER CHECK(loyalty IS NULL OR (loyalty >= 1 AND loyalty <= 100)),
    troops INTEGER NOT NULL CHECK(troops >= 100 AND troops <= 100000),
    food INTEGER NOT NULL CHECK(food >= 1 AND food <= 365),
    position_city_id TEXT NOT NULL REFERENCES cities(id),
    faction_id TEXT NOT NULL REFERENCES factions(id),
    is_player INTEGER NOT NULL DEFAULT 0,
    personality TEXT NOT NULL
);

CREATE TABLE game_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_day INTEGER NOT NULL
);

CREATE TABLE events_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_day INTEGER NOT NULL,
    seq INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    actor_id TEXT,
    target_id TEXT,
    details_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### 初始化数据

建局时插入 `game_state` 表：
- `current_day` → 1
- `season` → "春"
- `weather` → "晴"
- `scenario_name` → 用户指定
- `player_identity` → 用户指定的武将 ID

### 图数据 (graph.json)

```json
[
  ["caocao", "serves", "han", {}],
  ["luoyang", "connects", "yingchuan", {"distance": 5}],
  ["caocao", "trusts", "liubei", {"level": 60}]
]
```

存储城池连接和关系数据。运行时全部加载到内存，操作后写回 JSON。

### db.py API

| 命令 | 说明 |
|------|------|
| `db.py init` | 创建或迁移 schema |
| `db.py state read` | 读取全部 game_state |
| `db.py state write <key> <value> <day>` | 写入一条 game_state |
| `db.py general list` | 列出所有武将摘要 |
| `db.py general get <id>` | 获取武将详情 |
| `db.py general update <id> <field> <value>` | 更新武将字段 |
| `db.py city list` | 列出所有城池摘要 |
| `db.py log-event <type> [--actor] [--target] [--details]` | 写入事件日志 |
| `db.py events [--limit N]` | 查询最近事件 |
| `db.py graph read` | 读取全部三元组 |
| `db.py graph add <s> <p> <o>` | 添加三元组 |
| `db.py graph query <s> <p> <o>` | 查询三元组 (支持通配符) |

### view.py API

| 命令 | 说明 |
|------|------|
| `view.py show` | 展示当前局势摘要 (玩家身份、势力、日期、天气、主要武将与城池) |
| `view.py general <id>` | 展示武将详细面板 |
| `view.py map` | 展示 ASCII 简略地图示意 |
| `view.py events [--limit N]` | 展示最近事件列表 |

## P3: 剧本初始化设计

### 流程

```
init_scenario.py --theme "黄巾之乱" --player-name "曹操"
```

1. **环境检查**: 复用第一版的 Hermes 健康检查逻辑
2. **调用 LLM 生成完整世界**: 将 `init_prompt.txt` 发送给 Hermes
3. **校验输出**:
   - 所有武将 `position` 引用有效城池 ID
   - 城池连接 `from` / `to` 引用有效城池 ID
   - 兵力 100-100000；武/统/智/政/魅 1-100；忠诚 1-100 (玩家 null)
   - 粮草 1-365
   - 至少 3 座城池与 5 名武将
   - 玩家武将 `is_player: true` 且 `loyalty: null`
4. **持久化到 SQLite**: 插入 factions, cities, generals, game_state, events_log(初始事件)
5. **持久化到 graph.json**: 写入城池连接和关系三元组
6. **创建 Hermes Profiles**: 为每位武将创建 `~/.hermes/profiles/<id>/` 目录，写入 SOUL.md 和 config.yaml
7. **输出初始化摘要**: 展示建局成功信息

### LLM Prompt 模板示例

```
Given the following scenario theme, generate a complete Three Kingdoms game world as JSON.

Theme: {theme}
Player's chosen identity: {player_name}

The JSON must include:
- scenario: name of the scenario
- player_identity: player's general info
- cities: array of {id, name, x, y, terrain, owner}
- connections: array of {from, to, distance}
- generals: array of {id, name, war, command, intel, politics, charm, loyalty, troops, food, position, faction, is_player, personality}
- relationships: array of {subject, predicate, object, metadata}
- initial_state: {day, season, weather}

Validation rules:
- war/cmd/intel/politics/charm: 1-100
- loyalty: 1-100 (null for player)
- troops: 100-100000
- food: 1-365 (days)
- personality must include temperament, battle_style, risk_preference, lord_attitude, ally_attitude, enemy_attitude
- at least 3 cities
- at least 5 generals
- exactly one general with is_player=true
```

### SOUL.md 模板

从主规格 `templates/soul_general.txt` 提取，渲染后写入每位武将的 Hermes profile：

```markdown
# {name}

你是{name}，{personality_description}。

## 身份
- 阵营：{faction}
- 核心利益：{goals}
- 性格特质：{traits}

## 人格与作风
- 性格基调：{temperament}
- 用兵偏好：{battle_style}
- 风险偏好：{risk_preference}
- 对主公态度：{lord_attitude}
- 对盟友态度：{ally_attitude}
- 对敌人态度：{enemy_attitude}

## 属性
武：{war}  统：{cmd}  智：{int}  政：{pol}  魅：{cha}
忠诚度：{loyalty_display}

## 决策规则
- 忠诚度 > 80：全力执行命令，主动建言
- 忠诚度 50-80：执行但打折扣，可能阳奉阴违
- 忠诚度 < 50：可能抗命、拖延、密谋叛变
- 粮草不足时战斗力下降，行动力受限
- 智力高时能识破计策、发现伏击
- 做决策时，优先遵循你的人格与作风，再结合当前数值、局势和忠诚度输出行动
- 战斗叙事必须体现你的个人风格，而不是使用统一模板化措辞

## 输出格式
收到局势描述时，你必须返回严格JSON（无其他文字）：
{"action": "fight|retreat|negotiate|idle|rebel|advise|...", "effort": 0.0-1.0, "target": "...", "narrative": "..."}
```

## 与第一版的代码复用关系

| 第一版模块 | 复用方式 |
|-----------|---------|
| `infrastructure/hermes/health.py` | 直接复用为 init_scenario.py 环境检查 |
| `infrastructure/hermes/client.py` | 直接复用为 LLM 调用客户端 |
| `infrastructure/hermes/prompts.py` | 重构为 `init_prompt.txt` 模板文件 |
| `infrastructure/hermes/parser.py` | 重构为 init_scenario.py 中的校验逻辑 |
| `domain/*` | 模型定义被 SQLite schema 替代 |
| `application/*` | 服务逻辑被 scripts/db.py + scripts/view.py 替代 |
| `cli/*` | 移除，不再维护独立 CLI |
| `infrastructure/persistence/*` | 被 SQLite + graph.json 替代 |
| `interfaces/*` | 暂不迁移 (等微信接入时再用) |

## 测试策略

### 单元测试 (tests/unit/hermes-skill/)

- `test_db.py`: SQLite schema 创建、CRUD 操作、约束校验
- `test_view.py`: 展示格式化输出
- `test_init_scenario.py`: LLM 输出解析、校验逻辑、错误处理

### 集成测试

- 模拟 Hermes 响应，验证 `init_scenario.py` 能正确持久化完整世界
- 验证生成的 Hermes profiles 目录结构与内容
- 验证 SKILL.md 能被 Hermes Agent 正确加载

### 手工验收

1. 运行 `uv run install-skill` 确认 symlink 创建
2. 在 `hermes chat` 中输入 "我要玩黄巾之乱，当曹操"
3. 确认世界生成成功，SQLite 数据库写入完整数据
4. 确认武将 profiles 目录创建
5. 输入 "查看当前局势" 确认 `view.py` 输出
6. 输入 "查看曹操" 确认武将面板输出
7. 输入 "查看地图" 确认地图展示

## 验收标准

1. `uv run install-skill` 成功注册 skill 到 Hermes
2. Hermes 加载 SKILL.md 后，玩家可通过 `hermes chat` 创建新游戏
3. `init_scenario.py` 能通过 LLM 生成包含 3+ 城池、5+ 武将的完整世界
4. 所有数据持久化到 SQLite 的 5 张表 + graph.json
5. 每位武将拥有独立的 Hermes profile 目录 (SOUL.md + config.yaml)
6. `view.py` 能正确展示局势摘要、武将面板、地图示意
7. 事件日志正确记录建局初始事件

## 不包含 (后续版本范围)

- P4: 武将 Profile 初始化 (但 P3 中预先创建 profiles)
- P5: 多 Agent 通信 (inbox/outbox, agent_comm.py)
- P6: 时间引擎 + 事件队列 (time_engine.py)
- P7: 战斗系统 (battle.py)
- P8: 完整游戏循环 + 自主性
- 玩家接管扩展
- 聚落网络扩展
- 微信接入
