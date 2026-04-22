# AI局沙盘 (AI War Game) — Game Design Spec

## Overview

**AI局沙盘** — an AI-driven sandbox warfare game built on **[Hermes Agent](https://github.com/nousresearch/hermes-agent)**. Every general is a persistent, autonomous AI agent with its own memory, personality, and ambitions. The player specifies any historical or fictional scenario, and the LLM generates the entire world. Generals communicate asynchronously through file-based message passing coordinated by the Game Master agent. You command through WeChat — like texting a war council.

**Platform**: WeChat personal account via Hermes Gateway (`hermes gateway setup` → scan QR → play in WeChat). CLI also available for development/debugging.
**Language**: Python (Hermes ecosystem).
**Scenario**: Fully LLM-generated — no hardcoded scenario data.

---

## 1. Architecture (Hermes-Based)

### What Hermes Provides (no custom code needed)

| Capability | Hermes Feature |
|---|---|
| LLM backend (Ollama/OpenAI/Claude/200+ models) | Built-in, switch with `hermes model` |
| **WeChat personal account** | Built-in `weixin` adapter (QR scan → iLink Bot API) |
| CLI interface (TUI, history, autocomplete) | Built-in `hermes` command (for dev/debug) |
| Natural language understanding | Built-in LLM conversation |
| Multi-platform messaging | Also supports Telegram/Discord/Slack/WhatsApp/Signal |
| Subagent delegation | `delegate_task` tool |
| Persistent memory | `memory` tool + session search |
| Scheduled tasks | `cronjob` tool |
| Code execution | `execute_code` / `terminal` tools |

### What We Build (Hermes Skills + Python Scripts)

```
~/.hermes/skills/
└── strategy/
    └── ai-war-game/                      # AI局沙盘
        ├── SKILL.md                    # Game master skill (rules, procedures, orchestration)        ├── scripts/
        │   ├── db.py                   # Database layer (SQLite + graph + time-series)
        │   ├── state.py                # Game state CRUD
        │   ├── time_engine.py          # Day advancement + event queue
        │   ├── init_scenario.py        # LLM scenario generation + validation + DB persistence
        │   ├── agent_comm.py           # Multi-agent communication manager (async invoke + collect)
        │   ├── agent_setup.py          # Create/update general profiles (SOUL.md, config.yaml)
        │   ├── battle.py               # Battle synthesis (collect responses → generate outcome)
        │   └── view.py                 # Display generals, cities, maps
        ├── templates/
        │   ├── soul_general.txt        # SOUL.md template for general profiles
        │   └── init_prompt.txt         # Scenario initialization prompt template
        └── references/
            └── commands.md             # Player command reference

~/.hermes/profiles/                     # Each general gets an independent Hermes profile
  caocao/
    SOUL.md                             # 曹操's personality, goals, behavioral rules
    MEMORY.md                           # 曹操's accumulated memories (battles, grudges, ambitions)
    config.yaml                         # Can use different model per general
  liubei/
    SOUL.md                             # 刘备's personality
    MEMORY.md
    config.yaml
  ...

${HERMES_SKILL_DIR}/data/               # Shared game data
  game.db                               # SQLite (relational + time-series)
  graph.json                            # Triple store (relationships, city connections)
  messages/                             # Agent communication
    caocao/
      inbox.json                        # Current situation for 曹操
      outbox.json                       # 曹操's response
    liubei/
      inbox.json
      outbox.json
    ...
```

### Data Flow (Async Multi-Agent)

```
Player types in Hermes CLI/Gateway
  │
  ├── 1. GM agent (default profile) processes natural language
  │     SKILL.md guides all behavior
  │
  ├── 2. State operations via terminal → scripts/
  │     terminal("python3 scripts/state.py read")
  │     terminal("python3 scripts/time_engine.py advance --days 5")
  │
  ├── 3. When general decisions needed:
  │     │
  │     ├── 3a. GM writes situations to inboxes
  │     │   terminal("python3 scripts/agent_comm.py send --general caocao --context '...'")
  │     │
  │     ├── 3b. GM invokes all relevant generals in parallel (async)
  │     │   terminal("python3 scripts/agent_comm.py invoke --generals caocao,liubei",
  │     │             background=true)
  │     │   This script runs N hermes processes concurrently:
  │     │     hermes -p caocao chat -q "$(cat inbox.json)" > outbox.json &
  │     │     hermes -p liubei chat -q "$(cat inbox.json)" > outbox.json &
  │     │
  │     ├── 3c. GM collects responses when ready
  │     │   terminal("python3 scripts/agent_comm.py collect --generals caocao,liubei --timeout 120")
  │     │   Polls outboxes, returns all responses as JSON array
  │     │
  │     └── 3d. GM synthesizes outcome (battle report, event resolution)
  │
  ├── 4. GM persists state changes
  │     terminal("python3 scripts/state.py update ...")
  │
  └── 5. Display result to player
```

### Key Hermes Constraints (Discovered from Source Code)

1. **Profile isolation**: Each `hermes -p <profile>` instance has its own SOUL.md, memory, config, sessions. Generals cannot see each other's data.
2. **Non-interactive mode**: `hermes -p <profile> chat -q "<message>"` runs a single-turn query and outputs the response. Perfect for agent-to-agent calls.
3. **Async via background processes**: GM uses `terminal(background=true)` to spawn the communication script, which manages multiple hermes processes concurrently.
4. **Memory persistence**: Each general's MEMORY.md grows over time — they remember battles, betrayals, rewards. This is the key advantage over sub-agents.
5. **General autonomy**: Generals can have cron jobs for periodic autonomous behavior (e.g., "review my situation every 10 game-days").
6. **Cost**: Each general agent call is a full LLM session. With 10+ generals, a single turn can be expensive. Mitigated by only invoking relevant generals per event.

---

## 2. Game Design

### 2.1 Setting

- **Scenario**: Player-chosen — any historical era (黄巾之乱, 赤壁之战, etc.) or fictional setting. LLM generates everything.
- **Default example**: Yellow Turban Rebellion (used for development and testing)
- **Map**: LLM-generated cities with coordinates, terrain, and inter-city distances
- **Generals**: LLM-generated historically/scenario-relevant figures (~10-20)
- **Player identity**: Player specifies who they want to play (e.g., "我要当曹操"), LLM validates and initializes

### 2.2 General Attributes (6 core stats)

| Attribute | Abbr | Description | Gameplay Impact |
|-----------|------|-------------|-----------------|
| 武 (War) | war | Combat strength, duel ability, charge power | Battle lethality, duel outcomes |
| 统 (Command) | cmd | Troop leadership, formation, casualty control | Army capacity, siege efficiency, loss reduction |
| 智 (Intel) | int | Strategy quality, detecting plots, ambush tactics | Advice quality, countering enemy plans, tactical surprises |
| 政 (Politics) | pol | Administration, training efficiency, logistics | Recruit speed, training gains, food production |
| 魅 (Charm) | cha | Recruitment, diplomacy, maintaining subordinate loyalty | Talent acquisition, persuasion, loyalty retention |
| 忠 (Loyalty) | loy | Obedience level | Command compliance; player characters have "—" |

Plus two per-general resource fields:
- **兵 (Troops)**: current troop count (core war resource)
- **粮草 (Food)**: days of rations remaining for that general's army

No morale, stamina, or other derived stats. All 8 values (6 attributes + troops + food) are injected into each agent's context to inform LLM decision-making.

### 2.3 Food Mechanism

- Food is tracked **per general**, not globally
- Food depletion → combat effectiveness drops, movement slows
- Food never causes instant collapse, mutiny, or game over
- LLM agents reflect food shortage in narrative (tired troops, higher casualties)
- **政** affects food production rate when a general is assigned to manage a city

### 2.4 Combat Resolution

- No skills, no magic, no special tactics
- Battle outcomes are **LLM-generated** — agents on both sides respond with their decisions
- LLM considers: war + command + intel + troops + weather + food status
- Intelligence (智) influences tactical surprise, detecting enemy plans, and advisor quality
- Charm (魅) affects diplomatic persuasion and loyalty maintenance
- Pure strategy: deployment, training, siege, defense, rewards/punishments

**Battle Resolution Flow:**
1. Battle event triggers → orchestrator identifies all participants (attacker, defender, allies)
2. Each participant agent is called with battle context (enemy strength, terrain, weather, own status)
3. Agents return: action (fight/retreat/negotiate), effort (0.0-1.0, how hard they try), narrative
4. Main agent makes one final LLM call with all agent responses + raw stats to generate:
   - Battle outcome (win/lose/stalemate)
   - Casualty numbers for each side
   - Narrative battle report (simple or complex based on player preference)
5. State manager updates troops, city ownership, and logs the event

The `effort` field influences the final LLM call: a general with low loyalty who puts in 0.3 effort contributes less than one at 0.9.

### 2.5 Weather

- Changes daily, influenced by season
- Seasons rotate every 30 days (spring → summer → autumn → winter)
- Weather affects battle outcomes (LLM considers it)

### 2.6 Battle Reports

Two modes, globally toggleable:
- **Simple**: 2-3 line summary (weather, sides, result, casualties)
- **Complex**: narrative paragraph with tactical details

---

## 3. Database Layer (Python Scripts)

### 3.1 Relational Database (SQLite via stdlib `sqlite3`)

```
generals
  id, name, war, command, intel, politics, charm, loyalty, position_city, faction, is_player, personality

cities
  id, name, x, y, terrain, owner

garrisons
  general_id, city_id, troops, food

game_state
  key, value, updated_day
  (stores: current_day, season, weather, battle_report_mode, player_identity, scenario_name)
```

### 3.2 Graph Database (Python dict-based triple store, persisted to JSON)

For the MVP, use a lightweight in-memory triple store backed by a JSON file rather than a separate database process:

```python
# triples stored as: (subject, predicate, object, metadata)
# Examples:
("caocao", "serves", "han", {})
("caocao", "trusts", "liubei", {"level": 60})
("luoyang", "connects", "yingchuan", {"distance": 5})
```

This avoids external dependencies while providing the same query capability. If performance becomes an issue, can migrate to `rdflib` or `networkx` later.

### 3.3 Time-Series (SQLite, same file, separate table)

```
events_log
  id, game_day, seq, event_type, actor_id, target_id, details_json, created_at
```

Records every battle, arrival, food warning, rebellion, etc. Used for:
- Agent memory (recent events)
- Battle report replay
- Historical analysis

### 3.4 Database File Location

All data stored in a single directory managed by the skill:
```
${HERMES_SKILL_DIR}/data/
  game.db          # SQLite (relational + time-series)
  graph.json       # Triple store
```

---

## 4. Agent Architecture (Multi-Agent via Hermes Profiles)

### 4.1 General as Independent Hermes Agent

Each general is a **persistent Hermes agent** with its own profile directory. The general's identity, memories, and behavioral rules survive across game sessions.

**Profile structure per general:**
```
~/.hermes/profiles/caocao/
  SOUL.md           # 曹操的性格、目标、决策风格
  MEMORY.md         # 累积记忆：战役、恩怨、野心、密谋
  config.yaml       # 可选：不同武将用不同模型
```

**SOUL.md template (templates/soul_general.txt):**
```
# {name}

你是{name}，{personality_description}。

## 身份
- 阵营：{faction}
- 核心利益：{goals}
- 性格特质：{traits}

## 属性
武：{war}  统：{cmd}  智：{int}  政：{pol}  魅：{cha}
忠诚度：{loyalty_display}

## 决策规则
- 忠诚度 > 80：全力执行命令，主动建言
- 忠诚度 50-80：执行但打折扣，可能阳奉阴违
- 忠诚度 < 50：可能抗命、拖延、密谋叛变
- 粮草不足时战斗力下降，行动力受限
- 智力高时能识破计策、发现伏击

## 输出格式
收到局势描述时，你必须返回严格JSON（无其他文字）：
{"action": "fight|retreat|negotiate|idle|rebel|advise|...", "effort": 0.0-1.0, "target": "...", "narrative": "..."}
```

### 4.2 Communication Architecture (Async File-Based)

**agent_comm.py** manages all inter-agent communication:

```
GM Agent                              General Agents
   │                                      │
   │  1. Write situation to inbox          │
   │  ──────────────────────────►  inbox.json
   │                                      │
   │  2. Invoke hermes processes           │
   │  (background, parallel)               │
   │  ──────────────────────────►  hermes -p caocao chat -q "..."
   │                                hermes -p liubei chat -q "..."
   │                                      │
   │  3. Agents process & respond          │
   │                          outbox.json ◄────────
   │                                      │
   │  4. Collect responses                 │
   │  ◄──────────────────────────  outbox.json
   │                                      │
   │  5. Synthesize outcome                │
   │  Update state + generate report       │
```

**agent_comm.py commands:**

| Command | Description |
|---------|-------------|
| `send --general <id> --context <json>` | Write situation to general's inbox.json |
| `invoke --generals <id1,id2,...>` | Start parallel hermes processes (background) |
| `collect --generals <id1,...> --timeout <sec>` | Poll outboxes, return collected responses |
| `status` | Show which agents are running / responded |

**Parallel invocation (inside agent_comm.py):**
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

### 4.3 Agent Invocation Flow

```
Main Hermes Agent (Game Master, default profile)
  │
  ├── Player command received (natural language)
  │
  ├── 1. Read current state
  │     terminal("python3 scripts/state.py read")
  │
  ├── 2. Advance time if needed
  │     terminal("python3 scripts/time_engine.py advance --days N")
  │     → returns triggered events
  │
  ├── 3. For each event requiring general decisions:
  │     │
  │     ├── 3a. Build context for each relevant general
  │     │   terminal("python3 scripts/agent_comm.py send --general caocao --context '{...}'")
  │     │   terminal("python3 scripts/agent_comm.py send --general liubei --context '{...}'")
  │     │
  │     ├── 3b. Invoke all generals in parallel
  │     │   terminal("python3 scripts/agent_comm.py invoke --generals caocao,liubei",
  │     │             background=true, notify_on_complete=true)
  │     │
  │     ├── 3c. Wait for completion notification
  │     │   terminal("python3 scripts/agent_comm.py collect --generals caocao,liubei --timeout 120")
  │     │   → returns [{general: "caocao", action: "fight", effort: 0.9, ...}, ...]
  │     │
  │     └── 3d. Parse JSON responses from each general
  │
  ├── 4. Synthesize outcome (GM agent's own LLM reasoning)
  │     - Combine all agent responses + raw stats + weather + terrain
  │     - Generate battle outcome + casualties + narrative
  │
  ├── 5. Persist state changes
  │     terminal("python3 scripts/state.py update ...")
  │     terminal("python3 scripts/db.py log-event ...")
  │
  └── 6. Display result to player
```

### 4.4 Memory System

Each general accumulates memories independently. This creates **information asymmetry** — a key strategic element:

- **曹操** remembers his own battles and grudges
- **刘备** has different memories of the same events
- **张飞** doesn't know what 曹操 and 刘备 discussed privately
- Memories grow organically through each agent interaction

**Memory update flow:**
1. GM generates battle outcome / event result
2. GM writes a memory entry to each involved general's inbox
3. `agent_comm.py invoke` triggers each general to "reflect" on the event
4. Each general's Hermes memory system (MEMORY.md) is updated via the chat interaction
5. Next time that general is invoked, it has the accumulated memories

**Memory conventions (prefix in MEMORY.md):**
```
TK:BATTLE: Day 15, defeated 黄巾 at 颍川, lost 1200 troops
TK:REWARD: Day 16, received gold from player, loyalty +5
TK:BETRAYAL: Day 20, discovered 刘备's secret negotiation with 袁绍
TK:GOAL: Conquer 颍川 and secure supply lines
```

### 4.5 Agent Autonomy

Generals can act independently through Hermes cron:

```bash
# Each general has periodic self-review cron jobs
hermes -p caocao cron add "Every 10 game-days, review my situation and suggest actions"
hermes -p liubei cron add "Every 10 game-days, assess my loyalty and ambitions"
```

This enables:
- **主动建言**: A loyal general periodically suggests strategies
- **密谋**: A disloyal general might secretly build alliances
- **粮草请求**: A general running low on food sends a supply request

### 4.6 Agent Invocation Triggers

| Scenario | Generals Invoked | Mode |
|----------|-----------------|------|
| Player orders a general | That general (+ related) | Async parallel |
| Troops arrive at destination | Arriving + defending | Async parallel |
| Battle triggers | Both sides + allies | Async parallel |
| Food warning | That general | Single async |
| Idle day | All non-combat generals | Async parallel (batch) |
| Periodic autonomy | Each general independently | Cron-triggered |

### 4.7 Battle Resolution (Detailed)

1. GM identifies all battle participants
2. GM writes battle context to each participant's inbox (including enemy intel that the general would know)
3. `agent_comm.py invoke --generals attacker,defender,ally1,ally2` (parallel)
4. Each general agent responds with its decision JSON
5. GM collects all responses via `agent_comm.py collect`
6. GM synthesizes battle outcome using its own LLM reasoning:
   - Inputs: all agent decisions + effort levels + raw stats + weather + terrain + food
   - Output: win/lose/stalemate + casualties per side + narrative
7. GM writes battle results to each general's inbox for memory update
8. `agent_comm.py invoke` again for memory reflection (optional, can be deferred)
9. State persisted, battle report displayed to player

---

## 5. Time/Event Engine

### 5.1 Time Model

- **Granularity**: days (day 1, day 2, ...)
- **Seasons**: rotate every 30 days
- **Weather**: random daily, season-influenced

### 5.2 Time Advancement

1. **Implicit**: player command implies time passage (e.g., "march to 颍川" = advance 5 days)
2. **Explicit**: "wait" / "rest N days" → advance to next event
3. **Event interrupt**: during advancement, events pause time for player decisions

### 5.3 Event Queue

Priority queue (Python `heapq`) sorted by (day, priority). Managed by `scripts/time_engine.py`.

**Scheduled events** (created by player commands or game logic):
- March orders → `arrival` event
- Training/recruiting → `completion` event
- Diplomatic actions → `response` event

**Daily check events** (evaluated every time a day passes):
- Food threshold: if any general's food drops below 5 → `food_warning`; below 2 → `food_critical`
- Loyalty threshold: if any general's loyalty drops very low + high ambition → `rebellion` risk
- Idle agents: each day, non-combat generals may trigger `agent_decision`

Event types:

| Type | Trigger | Agents |
|------|---------|--------|
| `arrival` | March days complete | Arriving + defending general |
| `battle` | Armies meet / siege begins | Both sides |
| `food_warning` | Food < 5 days | That general |
| `food_critical` | Food < 2 days | That general + superior |
| `agent_decision` | Idle general autonomous action | That general |
| `weather_change` | Random / seasonal | None (global) |
| `season_change` | Every 30 days | None (global) |
| `rebellion` | Very low loyalty + ambition | Rebelling general |

### 5.4 March/Distance System

City connections stored in graph store with distance in days. On march:
1. Calculate travel days from graph store
2. Deduct food budget for travel duration
3. Schedule `arrival` event in event queue
4. Potential random events en route

---

## 6. Player Commands (via Natural Language)

Hermes' built-in LLM handles natural language understanding. The SKILL.md instructs the agent how to handle each type of command.

### 6.1 Command Categories

| Category | Examples | Time Impact |
|----------|----------|-------------|
| **View** | "查看曹操", "地图", "粮草情况" | No time advance |
| **Military** | "命曹操攻打颍川", "全军撤退" | Advances time |
| **Domestic** | "训练部队", "招兵", "赏赐刘备" | May advance time |
| **Diplomacy** | "劝降张角", "离间吕布" | Subagent dialogue |
| **System** | "简单战报", "复杂战报", "存档", "读档" | Meta operations |

### 6.2 SKILL.md Command Routing

The SKILL.md contains explicit procedures for each command type, telling the agent which scripts to run and how to use subagents. This replaces a traditional command parser.

---

## 7. Scenario Initialization (Fully LLM-Generated)

No scenario data is hardcoded. The game engine is scenario-agnostic.

### 7.1 Initialization Flow

1. **Player specifies scenario**: e.g., "黄巾之乱", "赤壁之战", "楚汉争霸", or a custom description
2. **Player specifies identity**: e.g., "我要当曹操" (optional, LLM can suggest options)
3. **SKILL.md instructs agent to run `scripts/init_scenario.py`** with the scenario and identity as arguments
4. **init_scenario.py** makes one LLM call via Hermes' built-in LLM to generate the entire world as JSON
5. **Validation**: Python code checks required fields, value ranges, referential integrity
6. **Persist**: write to SQLite (generals, cities, garrisons, game_state), graph.json (relationships, connections), events_log (initial state)
7. **Game begins**

### 7.2 Initialization Prompt Template

```
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

### 7.3 Validation Rules

- All general `position` values must reference valid city IDs
- All connection `from`/`to` must reference valid city IDs
- Troops: 100–100000, war/cmd/int/pol/cha: 1–100, loyalty: 1–100 (null for player)
- Food: 1–365 (days of rations)
- At least 3 cities and 5 generals required
- Player general must have `is_player: true` and `loyalty: null`

---

## 8. WeChat Setup (Primary Player Interface)

The player interacts with the game entirely through WeChat. Setup is a one-time operation:

```bash
# 1. Install Hermes
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash

# 2. Choose LLM backend
hermes model    # Select Ollama/OpenAI/Claude/etc.

# 3. Connect WeChat
hermes gateway setup
# → Select "weixin" platform
# → Terminal displays QR code
# → Scan with WeChat
# → Connected!

# 4. Start the gateway
hermes gateway start

# 5. In WeChat, send a message to start playing
# "我要玩黄巾之乱，当曹操"
```

Hermes `weixin` adapter (`gateway/platforms/weixin.py`) uses Tencent's iLink Bot API:
- **Inbound**: Long-poll `getupdates` for player messages (text, voice, images)
- **Outbound**: `sendmessage` API for game responses (markdown auto-formatted for WeChat)
- **Media**: Supports images, voice memos (useful for voice commands)
- **Message splitting**: Long battle reports auto-split into multiple chat bubbles
- **Security**: DM policy configurable (open/allowlist/disabled)

### Player Experience in WeChat

```
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

## 9. Sub-Project Decomposition (Multi-Agent Hermes)

Build order:

| Phase | Sub-project | Scope | Dependencies |
|-------|------------|-------|-------------|
| **P1** | Hermes Setup + SKILL.md | Install Hermes, create skill skeleton, write SKILL.md with game rules | Hermes installed |
| **P2** | Database + State Scripts | `db.py`, `state.py`, `view.py` — SQLite schema, graph store, CRUD APIs | P1 |
| **P3** | Scenario Init | `init_scenario.py` + `init_prompt.txt` — LLM generates world, validates, persists | P2 |
| **P4** | General Profile Setup | `agent_setup.py` + `soul_general.txt` — create Hermes profiles per general with SOUL.md | P1, P3 |
| **P5** | Multi-Agent Communication | `agent_comm.py` — inbox/outbox file system, parallel hermes invocation, response collection | P1, P4 |
| **P6** | Time Engine + Events | `time_engine.py` — day advancement, event queue, daily checks, march system | P2 |
| **P7** | Battle System | `battle.py` — collect general responses, synthesize outcome, generate report | P5, P6 |
| **P8** | Full Game Loop + Autonomy | Wire everything in SKILL.md, add cron-based general autonomy, end-to-end testing | All |

P2-P3 and P4-P5 can be built in parallel after P1.

### Key Difference from Original Design

| Original (Node.js from scratch) | Multi-Agent Hermes |
|---|---|
| 8 phases, ~2000+ lines infrastructure | 8 phases, but each building on Hermes |
| Custom LLM layer, CLI, agent system | Hermes provides all infrastructure |
| Sub-agents (stateless) | Independent agents (persistent memory) |
| 武将像NPC（被调用才响应） | 武将有自主性（cron、记忆、密谋） |
| 武将之间信息透明 | 武将之间信息不对称（战略深度） |
| ~500 lines of game scripts | ~800 lines of game scripts + agent_comm.py |
