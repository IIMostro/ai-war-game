# Dockerfile — AI War Game on Hermes Agent
#
# Build (from project root):
#   docker build -t ai-war-game .
#
# First run — setup Hermes config (API keys, etc.):
#   docker run -it --rm \
#     -v ~/.hermes:/opt/data \
#     ai-war-game setup
#
# Play:
#   docker run -it --rm \
#     -v ~/.hermes:/opt/data \
#     -e AI_WAR_GAME_HERMES_MODEL="anthropic/claude-sonnet-4-20250514" \
#     ai-war-game chat
#
#   (Once inside Hermes, type: 我要玩黄巾之乱，当曹操)
#
# Advanced — with custom env and resource limits:
#   docker run -it --rm \
#     --name ai-war-game \
#     --memory=4g --cpus=2 \
#     -v ~/.hermes:/opt/data \
#     -e AI_WAR_GAME_HERMES_MODEL="openrouter/anthropic/claude-sonnet-4" \
#     -e ANTHROPIC_API_KEY="sk-ant-..." \
#     ai-war-game chat
#

FROM nousresearch/hermes-agent:v2026.4.23

# --------------------------------------------------
# Copy AI War Game skill into the bundled skills directory.
# The entrypoint's skills_sync auto-installs it to the
# data volume (/opt/data/skills/strategy/ai-war-game/)
# on first container start.
# --------------------------------------------------
COPY hermes-skill /opt/hermes/skills/strategy/ai-war-game/

# --------------------------------------------------
# Custom entrypoint: auto-detect host IP, configure
# Ollama provider, then bootstrap + run hermes.
# --------------------------------------------------
COPY --chmod=0755 docker-entrypoint.sh /opt/hermes/docker/entrypoint-ai-war-game.sh

# Switch back to root — the Hermes entrypoint normally drops privileges
# via gosu, but we skip that so host-mounted volumes with mismatched UIDs
# work correctly. Hermes runs fine as root.
USER root

# --------------------------------------------------
# Set terminal working directory to the game skill directory.
# The SKILL.md references python3 scripts/*.py with relative
# paths — this ensures they resolve correctly.
# --------------------------------------------------
ENV TERMINAL_CWD=/opt/data/skills/strategy/ai-war-game

# --------------------------------------------------
# Default env vars for game subprocesses
# (agent_comm.py needs to invoke hermes from Python scripts)
# --------------------------------------------------
ENV AI_WAR_GAME_HERMES_BIN=hermes
ENV AI_WAR_GAME_HERMES_CONFIG=/opt/data/config.yaml

# AI_WAR_GAME_HERMES_MODEL is configured automatically to
# "ollama/deepseek-r1:8b". Override at runtime if needed:
#   -e AI_WAR_GAME_HERMES_MODEL="anthropic/claude-sonnet-4-20250514"

# OLLAMA_HOST: if set, uses this IP for the Ollama base URL.
# If unset, auto-detects the Docker host IP from the default gateway.

ENTRYPOINT ["/opt/hermes/docker/entrypoint-ai-war-game.sh"]
CMD ["chat"]
