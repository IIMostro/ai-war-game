#!/bin/bash
# run.sh — Quick start: source .env and launch game
set -a
source "$(dirname "$0")/.env" 2>/dev/null || echo "No .env file, using env vars"
set +a
exec uv run python -m ai_war_game "$@"
