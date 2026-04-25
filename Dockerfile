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

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com litellm

VOLUME ["/app/data"]

ENTRYPOINT ["python", "-m", "ai_war_game"]
