# Dockerfile — Self-contained AI War Game
#
# Build:
#   docker build -t ai-war-game .
#
# Run (with local Ollama):
#   docker run -it --rm \
#     -e AI_WAR_GAME_LLM_MODEL="ollama/qwen3.5:9b" \
#     --network=host \
#     ai-war-game
#
# Run (with remote API):
#   docker run -it --rm \
#     -e AI_WAR_GAME_LLM_MODEL="openai/gpt-4o-mini" \
#     -e AI_WAR_GAME_LLM_API_KEY="sk-..." \
#     ai-war-game

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY . .

RUN uv sync --no-dev --frozen

VOLUME ["/app/data"]

ENTRYPOINT ["uv", "run", "python", "-m", "ai_war_game"]
