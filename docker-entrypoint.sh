#!/bin/bash
# docker-entrypoint.sh — AI War Game entrypoint for Hermes Agent
#
# Bootstraps Hermes, installs the AI War Game skill, and starts the agent.
# Model/provider configuration is left to the user inside Hermes.

set -e

HERMES_HOME="${HERMES_HOME:-/opt/data}"
INSTALL_DIR="/opt/hermes"

# ============================================================================
# Running as root — stay as root.
# The gosu privilege drop is skipped so that the container can write to
# host-mounted volumes regardless of UID mismatch.
# ============================================================================
if [ "$(id -u)" = "0" ]; then
    echo "Running as root (skipping privilege drop)"
fi

# ============================================================================
# Bootstrap (replicating original Hermes entrypoint logic)
# ============================================================================
source "${INSTALL_DIR}/.venv/bin/activate"

mkdir -p "$HERMES_HOME"/{cron,sessions,logs,hooks,memories,skills,skins,plans,workspace,home}

if [ ! -f "$HERMES_HOME/.env" ]; then
    cp "$INSTALL_DIR/.env.example" "$HERMES_HOME/.env"
fi

if [ ! -f "$HERMES_HOME/config.yaml" ]; then
    cp "$INSTALL_DIR/cli-config.yaml.example" "$HERMES_HOME/config.yaml"
fi

if [ ! -f "$HERMES_HOME/SOUL.md" ]; then
    cp "$INSTALL_DIR/docker/SOUL.md" "$HERMES_HOME/SOUL.md"
fi

# Sync bundled skills (installs ai-war-game skill)
if [ -d "$INSTALL_DIR/skills" ]; then
    python3 "$INSTALL_DIR/tools/skills_sync.py"
fi

# ============================================================================
# AI War Game: set AI_WAR_GAME_HERMES_MODEL for game subprocesses
# ============================================================================
# The game scripts (agent_comm.py) invoke hermes subprocesses and need to
# know which model to use for general agents.
# Set via -e AI_WAR_GAME_HERMES_MODEL=<model> at runtime, e.g.:
#   -e AI_WAR_GAME_HERMES_MODEL="ollama/qwen2.5:7b"
if [ -n "$AI_WAR_GAME_HERMES_MODEL" ]; then
    export AI_WAR_GAME_HERMES_MODEL
    env_path="$HERMES_HOME/.env"
    if ! grep -q "AI_WAR_GAME_HERMES_MODEL" "$env_path" 2>/dev/null; then
        echo "# Set by ai-war-game entrypoint" >> "$env_path"
        echo "AI_WAR_GAME_HERMES_MODEL=$AI_WAR_GAME_HERMES_MODEL" >> "$env_path"
    fi
    echo "✓ AI_WAR_GAME_HERMES_MODEL=$AI_WAR_GAME_HERMES_MODEL"
fi

# ============================================================================
# Run Hermes
# ============================================================================
echo ""
echo "────────────────────────────────────────────────────"
echo " AI War Game ready!"
echo ""
echo " Configure your model inside Hermes: hermes model"
echo " Or with environment variables at runtime:"
echo "   -e AI_WAR_GAME_HERMES_MODEL=..."
echo ""
echo " Start playing: 我要玩黄巾之乱，当曹操"
echo "────────────────────────────────────────────────────"
echo ""
exec hermes "$@"
