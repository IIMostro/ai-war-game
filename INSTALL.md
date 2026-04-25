# AI War Game 安装指南

## 环境要求

- Python 3.12+
- [Hermes Agent](https://github.com/nousresearch/hermes-agent) — 已安装并可执行
- [uv](https://docs.astral.sh/uv/) — Python 包管理器

## 安装步骤

### 1. 克隆仓库

```bash
git clone <repo-url>
cd ai-war-game
```

### 2. 安装项目依赖

```bash
uv sync
```

此命令会安装测试工具链（pytest, ruff）。

### 3. 安装 & 配置 Hermes

如果尚未安装 Hermes：

```bash
# 安装 Hermes
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
```

配置 Hermes 模型：

```bash
hermes model    # 选择 LLM 后端（Ollama/OpenAI/Claude 等）
```

### 4. 注册 AI War Game Skill

```bash
bash tools/install-skill.sh
```

此命令将 `hermes-skill/` 目录软链接到 `~/.hermes/skills/strategy/ai-war-game/`。确认注册成功：

```bash
ls -la ~/.hermes/skills/strategy/ai-war-game/
# 应显示 SKILL.md, lib/, scripts/, data/
```

### 5. 配置环境变量

```bash
export AI_WAR_GAME_HERMES_MODEL=<你的模型ID>
export AI_WAR_GAME_HERMES_CONFIG=<hermes 配置文件路径>
```

建议写入 shell profile (`~/.zshrc` 或 `~/.bashrc`)：

```bash
echo 'export AI_WAR_GAME_HERMES_MODEL=<你的模型ID>' >> ~/.zshrc
echo 'export AI_WAR_GAME_HERMES_CONFIG=<hermes 配置文件路径>' >> ~/.zshrc
```

### 6. 验证安装

```bash
# 运行测试
uv run pytest

# 确认 Hermes 可访问 skill
hermes chat
# 在 hermes 中输入: 我要玩黄巾之乱，当曹操
```

```
