#!/bin/bash
# tools/install-skill.sh — Symlink hermes-skill/ into ~/.hermes/skills/

set -euo pipefail

SKILL_SOURCE="$(cd "$(dirname "$0")/.." && pwd)/hermes-skill"
SKILL_TARGET="${HERMES_SKILL_DIR:-$HOME/.hermes/skills/strategy/ai-war-game}"

if [ ! -d "$SKILL_SOURCE" ]; then
    echo "错误: 未找到 hermes-skill/ 目录 ($SKILL_SOURCE)"
    exit 1
fi

mkdir -p "$(dirname "$SKILL_TARGET")"

if [ -L "$SKILL_TARGET" ] || [ -d "$SKILL_TARGET" ]; then
    echo "正在移除现有 skill: $SKILL_TARGET"
    rm -rf "$SKILL_TARGET"
fi

ln -s "$SKILL_SOURCE" "$SKILL_TARGET"
echo "Skill 已注册: $SKILL_TARGET → $SKILL_SOURCE"
