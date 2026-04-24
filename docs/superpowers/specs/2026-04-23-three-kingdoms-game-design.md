# AI局沙盘（AI War Game）设计规格

## 概述

**AI局沙盘** 是一款基于 **[Hermes Agent](https://github.com/nousresearch/hermes-agent)** 构建的 AI 驱动沙盘战争游戏。每位武将都是一个持久化、自主运行的 AI Agent，拥有各自的记忆、性格与野心。玩家可以指定任意历史或虚构剧本，整个世界由 LLM 自动生成。武将之间通过由 Game Master Agent 协调的文件式消息传递进行异步通信。你通过微信下达命令，体验就像在给军议群发消息。

**平台**：通过 Hermes Gateway 连接微信个人号（`hermes gateway setup` → 扫码 → 在微信中游玩）。同时提供 CLI 用于开发与调试。  
**语言**：Python（Hermes 生态）。  
**剧本**：完全由 LLM 生成，不内置任何硬编码剧本数据。

## 文档导航

当前规格文档采用“主规格 + 专题补充”的组织方式：

- 主规格：本文档，负责整体架构、核心玩法和基础模块划分
- 玩家接管扩展：[2026-04-24-player-takeover-design.md](./2026-04-24-player-takeover-design.md)
- 聚落网络扩展：[2026-04-24-settlement-network-design.md](./2026-04-24-settlement-network-design.md)
- 规格索引：[index.md](./index.md)

阅读建议如下：

1. 先阅读主规格，理解整体架构与基础循环
2. 再阅读玩家接管扩展，理解多人接入与 AI 托管切换
3. 最后阅读聚落网络扩展，理解地图纵深、行军路径和城镇系统

---

## 1. 架构（基于 Hermes）

### Hermes 已提供的能力（无需自定义实现）

| 能力 | Hermes 功能 |
|---|---|
| LLM 后端（Ollama/OpenAI/Claude/200+ 模型） | 内置，使用 `hermes model` 切换 |
| **微信个人号接入** | 内置 `weixin` 适配器（扫码 → iLink Bot API） |
| CLI 界面（TUI、历史记录、自动补全） | 内置 `hermes` 命令（用于开发/调试） |
| 自然语言理解 | 内置 LLM 对话能力 |
| 多平台消息接入 | 同时支持 Telegram/Discord/Slack/WhatsApp/Signal |
| Subagent 委派 | `delegate_task` 工具 |
| 持久化记忆 | `memory` 工具 + session 搜索 |
| 定时任务 | `cronjob` 工具 |
| 代码执行 | `execute_code` / `terminal` 工具 |

### 我们需要构建的部分（Hermes Skills + Python 脚本）

```text
~/.hermes/skills/
└── strategy/
    └── ai-war-game/                      # AI局沙盘
        ├── SKILL.md                    # Game Master 技能（规则、流程、编排）
        ├── scripts/
        │   ├── db.py                   # 数据库层（SQLite + 图结构 + 时序日志）
        │   ├── state.py                # 游戏状态 CRUD
        │   ├── time_engine.py          # 天数推进 + 事件队列
        │   ├── init_scenario.py        # LLM 剧本生成 + 校验 + 数据持久化
        │   ├── agent_comm.py           # 多 Agent 通信管理器（异步调用 + 收集）
        │   ├── agent_setup.py          # 创建/更新武将档案（SOUL.md、config.yaml）
        │   ├── battle.py               # 战斗综合（收集响应 → 生成结果）
        │   └── view.py                 # 展示武将、城池、地图
        ├── templates/
        │   ├── soul_general.txt        # 武将档案 SOUL.md 模板
        │   └── init_prompt.txt         # 剧本初始化提示词模板
        └── references/
            └── commands.md             # 玩家命令参考

~/.hermes/profiles/                     # 每位武将拥有独立 Hermes profile
  caocao/
    SOUL.md                             # 曹操的性格、目标、行为规则
    MEMORY.md                           # 曹操积累的记忆（战役、恩怨、野心）
    config.yaml                         # 每位武将可使用不同模型
  liubei/
    SOUL.md                             # 刘备的性格
    MEMORY.md
    config.yaml
  ...

${HERMES_SKILL_DIR}/data/               # 共享游戏数据
  game.db                               # SQLite（关系数据 + 时序数据）
  graph.json                            # 三元组存储（关系、城池连接）
  messages/                             # Agent 通信目录
    caocao/
      inbox.json                        # 当前局势输入给曹操
      outbox.json                       # 曹操的响应输出
    liubei/
      inbox.json
      outbox.json
    ...
```

### 数据流（异步多 Agent）

```text
玩家在 Hermes CLI/Gateway 中输入
  │
  ├── 1. GM Agent（默认 profile）处理自然语言
  │     所有行为由 SKILL.md 指导
  │
  ├── 2. 通过 terminal 调用 scripts/ 做状态操作
  │     terminal("python3 scripts/state.py read")
  │     terminal("python3 scripts/time_engine.py advance --days 5")
  │
  ├── 3. 当需要武将决策时：
  │     │
  │     ├── 3a. GM 将局势写入各武将 inbox
  │     │   terminal("python3 scripts/agent_comm.py send --general caocao --context '...'")
  │     │
  │     ├── 3b. GM 并行异步调用所有相关武将
  │     │   terminal("python3 scripts/agent_comm.py invoke --generals caocao,liubei",
  │     │             background=true)
  │     │   该脚本会并发运行多个 hermes 进程：
  │     │     hermes -p caocao chat -q "$(cat inbox.json)" > outbox.json &
  │     │     hermes -p liubei chat -q "$(cat inbox.json)" > outbox.json &
  │     │
  │     ├── 3c. GM 在响应准备完成后收集结果
  │     │   terminal("python3 scripts/agent_comm.py collect --generals caocao,liubei --timeout 120")
  │     │   轮询 outbox，并以 JSON 数组返回全部响应
  │     │
  │     └── 3d. GM 综合生成结果（战报、事件结算）
  │
  ├── 4. GM 持久化状态变化
  │     terminal("python3 scripts/state.py update ...")
  │
  └── 5. 向玩家展示结果
```

### Hermes 的关键约束（从源码梳理得到）

1. **Profile 隔离**：每个 `hermes -p <profile>` 实例都拥有独立的 SOUL.md、记忆、配置与会话。武将之间无法直接看到彼此数据。
2. **非交互模式**：`hermes -p <profile> chat -q "<message>"` 会执行一次单轮查询并输出结果，非常适合 Agent 间调用。
3. **通过后台进程实现异步**：GM 使用 `terminal(background=true)` 启动通信脚本，由脚本并发管理多个 hermes 进程。
4. **记忆可持久化**：每位武将的 `MEMORY.md` 会随着时间持续增长，记录战役、背叛、奖赏等。这是相较普通 sub-agent 的关键优势。
5. **武将具备自主性**：武将可以通过 cron job 执行周期性自主行为，例如“每经过 10 个游戏日就复盘当前局势”。
6. **成本问题**：每次武将 Agent 调用本质上都是一次完整 LLM 会话。若存在 10 名以上武将，单回合成本可能较高。缓解方式是仅在相关事件中调用相关武将。

---

## 2. 游戏设计

### 2.1 设定

- **剧本**：由玩家指定，可为任意历史时代（黄巾之乱、赤壁之战等）或虚构背景，所有内容均由 LLM 生成。
- **默认示例**：黄巾之乱（用于开发与测试）。
- **地图**：由 LLM 生成城池坐标、地形与城际距离。
- **武将**：由 LLM 生成与历史/剧本相关的人物，规模约 10 到 20 人。
- **玩家身份**：玩家指定自己扮演谁（例如“我要当曹操”），由 LLM 进行校验与初始化。

### 2.2 武将属性（6 个核心数值）

| 属性 | 缩写 | 说明 | 对玩法的影响 |
|-----------|------|-------------|-----------------|
| 武 | war | 战斗能力、单挑水平、冲锋强度 | 决定战斗杀伤、单挑结果 |
| 统 | cmd | 带兵能力、阵型控制、伤亡管理 | 决定部队承载力、攻城效率、减伤能力 |
| 智 | int | 谋略水平、识破阴谋、伏击运用 | 决定建议质量、反制敌计、战术奇袭能力 |
| 政 | pol | 内政能力、训练效率、后勤水平 | 决定征兵速度、训练收益、粮草产出 |
| 魅 | cha | 招募能力、外交说服、维持部下忠诚 | 决定招贤成功率、游说效果、忠诚维持 |
| 忠 | loy | 服从程度 | 决定命令执行度；玩家角色显示为“—” |

每位武将还包含两个资源字段：

- **兵**：当前兵力（核心战争资源）。
- **粮草**：该武将所部剩余口粮天数。

不设士气、体力或其他派生属性。全部 8 个值（6 项属性 + 兵力 + 粮草）都会注入每个 Agent 的上下文中，用于辅助 LLM 做决策。

除数值属性外，每位武将还必须拥有**人格设定**，并持久化写入各自的 `SOUL.md`。  
人格设定不是装饰信息，而是该武将一切 AI 决策的行为约束来源。相同数值的武将，因为人格不同，也应在战斗、外交、服从和风险偏好上表现出明显差异。

人格设定至少应覆盖以下维度：

- 性格基调：谨慎、激进、残酷、仁厚、傲慢、务实等
- 战争风格：偏好强攻、诱敌、固守、奇袭、稳扎稳打等
- 权力倾向：忠于主公、功名心强、自保优先、野心外露等
- 人际风格：重义气、重利益、多疑、善笼络、记仇等
- 风险偏好：敢赌、保守、临机应变、厌恶高损耗等

这些人格描述应与数值共同作用，而不是互相替代：

- 数值决定“能做到什么”
- 人格决定“倾向于怎么做”

### 2.3 粮草机制

- 粮草按 **武将维度** 追踪，而不是全局统一库存。
- 粮草不足会导致战斗效率下降、行军速度变慢。
- 粮草短缺不会立刻引发崩溃、哗变或游戏失败。
- LLM Agent 需要在叙事中体现缺粮影响，例如“士卒疲惫”“伤亡上升”。
- 当武将被安排治理城池时，**政** 会影响粮草产出速度。

### 2.4 战斗结算

- 没有技能、没有魔法、没有额外特技系统。
- 战斗结果由 **LLM 生成**，交战双方 Agent 都会先给出各自决策。
- LLM 会综合考虑：武、统、智、兵力、天气、粮草状况，以及武将 `SOUL.md` 中的人格与作战风格。
- 智会影响奇袭、识破敌计与军师建议质量。
- 魅会影响外交说服与忠诚维持。
- 玩法核心是纯策略：布阵、训练、攻城、防守、赏罚。

同样兵力和属性下，不同性格的武将应给出不同风格的战斗决策。例如：

- 激进型武将更可能选择强攻、追击、冒险压上
- 谨慎型武将更可能选择试探、固守、等待援军
- 重名声的武将可能避免临阵撤退
- 自保型或多疑型武将在局势不利时更可能保留实力

**战斗结算流程：**

1. 战斗事件触发后，编排器识别全部参战方（进攻方、防守方、援军等）。
2. 调用每个参战 Agent，并传入战场上下文（敌方兵力、地形、天气、自身状态）。
3. Agent 返回：动作（fight/retreat/negotiate）、投入程度（0.0-1.0）、叙事说明。
4. 主 Agent 再做一次最终 LLM 调用，基于所有响应与原始数值生成：
   - 战斗结果（胜/负/平）
   - 双方伤亡数字
   - 战斗叙事战报（由玩家选择简略或详细）
5. 状态管理器更新兵力、城池归属，并记录事件日志。

`effort` 字段会影响最终结算：一个忠诚度低、仅投入 0.3 的武将，对结果的贡献应显著弱于投入 0.9 的武将。

### 2.5 天气

- 天气每天变化，并受到季节影响。
- 每 30 天轮换一个季节（春 → 夏 → 秋 → 冬）。
- 天气会影响战斗结果，具体由 LLM 在结算时综合考虑。

### 2.6 战报

提供两种全局可切换模式：

- **简洁**：2 到 3 行摘要（天气、双方、结果、伤亡）。
- **详细**：用自然语言段落描述战术细节。

---

## 3. 数据库层（Python 脚本）

### 3.1 关系数据库（使用标准库 `sqlite3` 的 SQLite）

```text
generals
  id, name, war, command, intel, politics, charm, loyalty, position_city, faction, is_player, personality

cities
  id, name, x, y, terrain, owner

garrisons
  general_id, city_id, troops, food

game_state
  key, value, updated_day
  （用于存储：current_day、season、weather、battle_report_mode、player_identity、scenario_name）
```

### 3.2 图数据库（基于 Python dict 的三元组存储，持久化到 JSON）

在 MVP 阶段，不使用独立图数据库进程，而采用轻量级内存三元组存储，并将其落盘到 JSON 文件：

```python
# 三元组格式：(subject, predicate, object, metadata)
# 示例：
("caocao", "serves", "han", {})
("caocao", "trusts", "liubei", {"level": 60})
("luoyang", "connects", "yingchuan", {"distance": 5})
```

这样可以避免额外外部依赖，同时保留相同的查询表达能力。若后续性能成为瓶颈，可再迁移到 `rdflib` 或 `networkx`。

### 3.3 时序数据（同样使用 SQLite，存储在同一个文件中）

```text
events_log
  id, game_day, seq, event_type, actor_id, target_id, details_json, created_at
```

记录所有战斗、抵达、缺粮预警、叛变等事件，用于：

- Agent 记忆注入（近期事件）
- 战报回放
- 历史分析

### 3.4 数据文件位置

所有数据存储在 skill 管理的单一目录中：

```text
${HERMES_SKILL_DIR}/data/
  game.db          # SQLite（关系数据 + 时序数据）
  graph.json       # 三元组存储
```

---

## 4. Agent 架构（基于 Hermes Profile 的多 Agent）

### 4.1 武将作为独立 Hermes Agent

每位武将都是一个 **持久化 Hermes Agent**，拥有独立 profile 目录。武将身份、记忆与行为规则会跨游戏会话保存下来。

**每位武将的 profile 结构：**

```text
~/.hermes/profiles/caocao/
  SOUL.md           # 曹操的性格、目标、决策风格
  MEMORY.md         # 累积记忆：战役、恩怨、野心、密谋
  config.yaml       # 可选：不同武将可绑定不同模型
```

`SOUL.md` 是武将人格的唯一权威来源。  
所有 AI 托管阶段的行为，包括战斗决策、外交表态、忠诚波动下的执行力度、是否冒险、是否记仇，都必须优先受 `SOUL.md` 约束，而不是只根据数值做静态计算。

**SOUL.md 模板（`templates/soul_general.txt`）：**

```text
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

### 4.2 通信架构（基于文件的异步通信）

**`agent_comm.py`** 负责管理全部 Agent 间通信：

```text
GM Agent                              General Agents
   │                                      │
   │  1. 将局势写入 inbox                  │
   │  ──────────────────────────►  inbox.json
   │                                      │
   │  2. 调起 hermes 进程                  │
   │  （后台、并行）                       │
   │  ──────────────────────────►  hermes -p caocao chat -q "..."
   │                                hermes -p liubei chat -q "..."
   │                                      │
   │  3. Agent 处理并回应                  │
   │                          outbox.json ◄────────
   │                                      │
   │  4. 收集响应                         │
   │  ◄──────────────────────────  outbox.json
   │                                      │
   │  5. 综合生成结果                     │
   │  更新状态 + 生成战报                  │
```

**`agent_comm.py` 支持的命令：**

| 命令 | 说明 |
|---------|-------------|
| `send --general <id> --context <json>` | 将局势写入武将的 `inbox.json` |
| `invoke --generals <id1,id2,...>` | 启动并行 hermes 进程（后台运行） |
| `collect --generals <id1,...> --timeout <sec>` | 轮询 outbox，并返回已收集响应 |
| `status` | 展示哪些 Agent 正在运行 / 已响应 |

**并行调用示例（位于 `agent_comm.py` 内部）：**

```python
import subprocess, concurrent.futures

def invoke_generals(general_ids, inbox_dir, outbox_dir):
    def run_general(gid):
        inbox = f"{inbox_dir}/{gid}/inbox.json"
        outbox = f"{outbox_dir}/{gid}/outbox.json"
        with open(inbox) as f:
            context = f.read()
        result = subprocess.run(
            ["hermes", "-p", gid, "chat", "-q", context],
            capture_output=True, text=True, timeout=300
        )
        with open(outbox, "w") as f:
            f.write(result.stdout)
        return {"general": gid, "response": result.stdout, "status": "ok"}

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(run_general, gid): gid for gid in general_ids}
        return [f.result() for f in concurrent.futures.as_completed(futures)]
```

### 4.3 Agent 调用流程

```text
主 Hermes Agent（Game Master，默认 profile）
  │
  ├── 收到玩家命令（自然语言）
  │
  ├── 1. 读取当前状态
  │     terminal("python3 scripts/state.py read")
  │
  ├── 2. 如有需要推进时间
  │     terminal("python3 scripts/time_engine.py advance --days N")
  │     → 返回触发的事件
  │
  ├── 3. 对每个需要武将决策的事件：
  │     │
  │     ├── 3a. 为每位相关武将构造上下文
  │     │   terminal("python3 scripts/agent_comm.py send --general caocao --context '{...}'")
  │     │   terminal("python3 scripts/agent_comm.py send --general liubei --context '{...}'")
  │     │
  │     ├── 3b. 并行调用全部武将
  │     │   terminal("python3 scripts/agent_comm.py invoke --generals caocao,liubei",
  │     │             background=true, notify_on_complete=true)
  │     │
  │     ├── 3c. 等待完成通知
  │     │   terminal("python3 scripts/agent_comm.py collect --generals caocao,liubei --timeout 120")
  │     │   → 返回 [{general: "caocao", action: "fight", effort: 0.9, ...}, ...]
  │     │
  │     └── 3d. 解析每位武将返回的 JSON
  │
  ├── 4. 综合生成结果（由 GM 自身的 LLM 推理完成）
  │     - 合并所有 Agent 响应 + 原始数值 + 天气 + 地形
  │     - 生成战斗结果、伤亡与叙事
  │
  ├── 5. 持久化状态变更
  │     terminal("python3 scripts/state.py update ...")
  │     terminal("python3 scripts/db.py log-event ...")
  │
  └── 6. 向玩家展示结果
```

### 4.4 记忆系统

每位武将都会独立积累记忆，从而形成 **信息不对称**，这是游戏策略深度的核心来源之一：

- **曹操** 记得自己经历的战役与恩怨。
- **刘备** 对同一事件会形成不同记忆。
- **张飞** 不知道曹操和刘备私下谈了什么。
- 记忆会通过每次 Agent 交互自然增长。

**记忆更新流程：**

1. GM 生成战斗结果或事件结算。
2. GM 将一条记忆写入每个相关武将的 inbox。
3. 执行 `agent_comm.py invoke`，触发每位武将对事件进行“反思”。
4. 每位武将的 Hermes 记忆系统（`MEMORY.md`）通过该次 chat 交互完成更新。
5. 下次调用该武将时，它已携带这些累积记忆。

**记忆约定（写入 `MEMORY.md` 时使用前缀）：**

```text
TK:BATTLE: Day 15, defeated 黄巾 at 颍川, lost 1200 troops
TK:REWARD: Day 16, received gold from player, loyalty +5
TK:BETRAYAL: Day 20, discovered 刘备's secret negotiation with 袁绍
TK:GOAL: Conquer 颍川 and secure supply lines
```

### 4.5 Agent 自主性

武将可通过 Hermes 的 cron 机制独立行动：

```bash
# 每位武将都有周期性自检 cron job
hermes -p caocao cron add "Every 10 game-days, review my situation and suggest actions"
hermes -p liubei cron add "Every 10 game-days, assess my loyalty and ambitions"
```

这将支持以下行为：

- **主动建言**：忠诚武将会定期给出策略建议。
- **密谋**：不忠武将可能暗中拉拢盟友。
- **粮草请求**：缺粮武将会主动请求补给。

### 4.6 Agent 调用触发条件

| 场景 | 触发的武将 | 模式 |
|----------|-----------------|------|
| 玩家命令某位武将 | 该武将（以及必要相关方） | 异步并行 |
| 部队抵达目的地 | 到达方 + 防守方 | 异步并行 |
| 战斗触发 | 双方 + 盟友 | 异步并行 |
| 粮草预警 | 该武将 | 单 Agent 异步 |
| 空闲日 | 所有未作战武将 | 异步并行（批处理） |
| 周期性自主行为 | 各武将独立执行 | Cron 触发 |

### 4.7 战斗结算（详细版）

1. GM 识别全部参战方。
2. GM 将战斗上下文写入每位参战方的 inbox（包含该武将“理应知道”的敌情）。
3. 执行 `agent_comm.py invoke --generals attacker,defender,ally1,ally2` 并行调用。
4. 每位武将 Agent 返回自己的决策 JSON。
5. GM 通过 `agent_comm.py collect` 收集全部响应。
6. GM 依靠自身 LLM 推理综合战斗结果：
   - 输入：全部 Agent 决策、投入程度、原始数值、天气、地形、粮草。
   - 输出：胜/负/平、双方伤亡、叙事战报。
7. GM 将战斗结果写回各武将 inbox，以便更新记忆。
8. 再次执行 `agent_comm.py invoke` 进行记忆反思（可选，也可延后）。
9. 持久化状态，并向玩家展示战报。

---

## 5. 时间 / 事件引擎

### 5.1 时间模型

- **粒度**：按天推进（第 1 天、第 2 天……）。
- **季节**：每 30 天轮换一次。
- **天气**：每日随机生成，并受季节影响。

### 5.2 时间推进方式

1. **隐式推进**：玩家命令本身意味着时间流逝，例如“行军至颍川”= 推进 5 天。
2. **显式推进**：如“等待”/“休整 N 天”，推进到下一事件出现。
3. **事件中断**：推进过程中若发生事件，会暂停时间并等待玩家决策。

### 5.3 事件队列

使用 Python `heapq` 实现按 `(day, priority)` 排序的优先队列，由 `scripts/time_engine.py` 管理。

**计划事件**（由玩家命令或游戏逻辑创建）：

- 行军命令 → `arrival` 事件
- 训练/征兵 → `completion` 事件
- 外交行为 → `response` 事件

**每日检查事件**（每推进一天都要评估）：

- 粮草阈值：若任一武将粮草低于 5 天 → `food_warning`；低于 2 天 → `food_critical`
- 忠诚阈值：若某武将忠诚极低且野心高 → 存在 `rebellion` 风险
- 空闲武将：未作战武将每天都可能触发 `agent_decision`

事件类型如下：

| 类型 | 触发条件 | 涉及 Agent |
|------|---------|--------|
| `arrival` | 行军天数结束 | 到达方 + 防守方 |
| `battle` | 部队遭遇 / 围城开始 | 双方 |
| `food_warning` | 粮草 < 5 天 | 该武将 |
| `food_critical` | 粮草 < 2 天 | 该武将 + 上级 |
| `agent_decision` | 空闲武将自主行动 | 该武将 |
| `weather_change` | 随机 / 季节变化 | 无（全局） |
| `season_change` | 每 30 天 | 无（全局） |
| `rebellion` | 忠诚极低且野心过高 | 叛变武将 |

### 5.4 行军 / 距离系统

城池之间的连接关系与距离天数存储于图结构中。执行行军时：

1. 从图结构计算旅行天数。
2. 扣除对应行军期间所需粮草。
3. 在事件队列中安排 `arrival` 事件。
4. 路途中可能触发随机事件。

---

## 6. 玩家命令（通过自然语言）

Hermes 内置的 LLM 负责自然语言理解，SKILL.md 负责告诉 Agent 如何处理不同类型的命令。

### 6.1 命令分类

| 分类 | 示例 | 时间影响 |
|----------|----------|-------------|
| **查看** | “查看曹操”、“地图”、“粮草情况” | 不推进时间 |
| **军事** | “命曹操攻打颍川”、“全军撤退” | 会推进时间 |
| **内政** | “训练部队”、“招兵”、“赏赐刘备” | 可能推进时间 |
| **外交** | “劝降张角”、“离间吕布” | 触发 Subagent 对话 |
| **系统** | “简单战报”、“复杂战报”、“存档”、“读档” | 元操作 |

### 6.2 SKILL.md 的命令路由

SKILL.md 会为每类命令写出明确流程，指示 Agent 应调用哪些脚本、如何使用 subagent。它将取代传统命令解析器。

---

## 7. 剧本初始化（完全由 LLM 生成）

不硬编码任何剧本数据，游戏引擎本身对剧本保持无关。

### 7.1 初始化流程

1. **玩家指定剧本**：例如“黄巾之乱”“赤壁之战”“楚汉争霸”，或任意自定义描述。
2. **玩家指定身份**：例如“我要当曹操”（可选，LLM 也可给出推荐项）。
3. **SKILL.md 指导 Agent 调用 `scripts/init_scenario.py`**，并将剧本与身份作为参数传入。
4. **`init_scenario.py`** 借助 Hermes 内置 LLM 发起一次调用，生成完整世界 JSON。
5. **校验**：Python 代码检查必填字段、数值范围与引用完整性。
6. **持久化**：写入 SQLite（`generals`、`cities`、`garrisons`、`game_state`）、`graph.json`（关系、连接）、`events_log`（初始状态）。
7. **游戏开始**。

### 7.2 初始化提示词模板

```text
Given the following prompt, generate a complete game world as JSON:

{templates/init_prompt.txt}

The LLM returns:
{
  "scenario": "黄巾之乱",
  "player_identity": "曹操",
  "cities": [
    { "id": "luoyang", "name": "洛阳", "x": 0, "y": 0, "terrain": "平原", "owner": "汉室" },
    ...
  ],
  "connections": [
    { "from": "luoyang", "to": "yingchuan", "distance": 5 },
    ...
  ],
  "generals": [
    { "id": "caocao", "name": "曹操", "war": 72, "command": 86, "intel": 91, "politics": 88, "charm": 80, "loyalty": null, "troops": 8000, "food": 15, "position": "luoyang", "faction": "汉室", "is_player": true, "personality": "..." },
    ...
  ],
  "relationships": [
    { "subject": "caocao", "predicate": "serves", "object": "han", "metadata": {} },
    { "subject": "caocao", "predicate": "trusts", "object": "liubei", "metadata": { "level": 60 } },
    ...
  ],
  "initial_state": {
    "day": 1,
    "season": "春",
    "weather": "晴"
  }
}
```

### 7.3 校验规则

- 所有武将的 `position` 必须引用有效城池 ID。
- 所有连接的 `from` / `to` 必须引用有效城池 ID。
- 兵力范围：100–100000；武/统/智/政/魅：1–100；忠诚：1–100（玩家为 `null`）。
- 粮草范围：1–365（按口粮天数计）。
- 至少需要 3 座城池与 5 名武将。
- 玩家武将必须满足 `is_player: true` 且 `loyalty: null`。

---

## 8. 微信接入（主要玩家界面）

玩家通过微信完整体验游戏。初始化接入仅需一次：

```bash
# 1. 安装 Hermes
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash

# 2. 选择 LLM 后端
hermes model    # 选择 Ollama/OpenAI/Claude 等

# 3. 连接微信
hermes gateway setup
# → 选择 "weixin" 平台
# → 终端显示二维码
# → 使用微信扫码
# → 连接完成

# 4. 启动 gateway
hermes gateway start

# 5. 在微信中发送消息开始游戏
# "我要玩黄巾之乱，当曹操"
```

Hermes 的 `weixin` 适配器（`gateway/platforms/weixin.py`）基于腾讯 iLink Bot API：

- **入站**：通过长轮询 `getupdates` 接收玩家消息（文本、语音、图片）。
- **出站**：通过 `sendmessage` API 发送游戏响应（Markdown 会自动适配微信格式）。
- **媒体支持**：支持图片和语音消息，适合语音下令。
- **消息拆分**：超长战报会自动拆分成多个聊天气泡。
- **安全策略**：私聊策略可配置（开放 / 白名单 / 禁用）。

### 微信中的玩家体验

```text
你: 我要玩黄巾之乱，当曹操

GM: 正在生成世界...

    【黄巾之乱 · 剧本初始化完成】
    你是曹操，坐镇洛阳，兵力8000，粮草15日。
    
    【你的麾下】
    刘备：武75 统78 智68 政72 魅92 忠90
          兵5000 洛阳 粮草12日
    
    【地图】
    洛阳 ──5日── 颍川 ──4日── 巨鹿
    洛阳 ──8日── 宛城
    
    第1天，春天，天气晴。
    下令吧，主公。

你: 命刘备率军攻打颍川

GM: 刘备领命出征！（忠诚90，全力执行）
    
    行军5日... 推进到第6天。
    
    【颍川之战】
    天气：晴
    刘备军 5000 vs 黄巾军 8000
    
    刘备身先士卒，虽有兵力劣势但军纪严明。
    黄巾军号令不一，阵型混乱。
    激战后黄巾溃败。
    
    刘备军损失1200，攻克颍川。

你: 简单战报

GM: 已切换为简单战报模式。

你: 查看刘备

GM: 【刘备】
    位置：颍川
    武75 统78 智68 政72 魅92 忠95
    兵力：3800
    粮草：7日
    
    近期：第6天攻克颍川，损失1200人
```

---

## 9. 子项目拆分（多 Agent Hermes 方案）

建议构建顺序如下：

| 阶段 | 子项目 | 范围 | 依赖 |
|-------|------------|-------|-------------|
| **P1** | Hermes Setup + SKILL.md | 安装 Hermes，创建 skill 骨架，编写包含游戏规则的 SKILL.md | 已安装 Hermes |
| **P2** | 数据库 + 状态脚本 | `db.py`、`state.py`、`view.py`：SQLite Schema、图存储、CRUD API | P1 |
| **P3** | 剧本初始化 | `init_scenario.py` + `init_prompt.txt`：用 LLM 生成世界、校验并持久化 | P2 |
| **P4** | 武将 Profile 初始化 | `agent_setup.py` + `soul_general.txt`：为每位武将创建带 SOUL.md 的 Hermes profile | P1、P3 |
| **P5** | 多 Agent 通信 | `agent_comm.py`：inbox/outbox 文件系统、并行 hermes 调用、响应收集 | P1、P4 |
| **P6** | 时间引擎 + 事件系统 | `time_engine.py`：天数推进、事件队列、每日检查、行军系统 | P2 |
| **P7** | 战斗系统 | `battle.py`：收集武将响应、综合结果、生成战报 | P5、P6 |
| **P8** | 完整游戏循环 + 自主性 | 在 SKILL.md 中串联全部流程，增加基于 cron 的武将自主行为，完成端到端测试 | 全部 |

在 P1 完成后，P2-P3 与 P4-P5 可以并行推进。

### 与原始设计的关键差异

| 原始方案（Node.js 从零实现） | 多 Agent Hermes 方案 |
|---|---|
| 8 个阶段，约 2000+ 行基础设施代码 | 同样 8 个阶段，但建立在 Hermes 之上 |
| 自建 LLM 层、CLI、Agent 系统 | Hermes 已提供底层基础设施 |
| 使用无状态 Sub-agent | 使用有持久记忆的独立 Agent |
| 武将更像 NPC（被调用才响应） | 武将具备自主性（cron、记忆、密谋） |
| 武将之间信息透明 | 武将之间信息不对称（策略深度更高） |
| 约 500 行游戏脚本 | 约 800 行游戏脚本 + `agent_comm.py` |
