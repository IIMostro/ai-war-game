"""new-game 子命令实现."""

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from ai_war_game.application.create_game import CreateGameService
from ai_war_game.application.dto import CreateGameInput
from ai_war_game.cli import exit_codes
from ai_war_game.infrastructure.hermes.client import HermesScenarioGenerator
from ai_war_game.infrastructure.hermes.health import (
    DEFAULT_BIN,
    ENV_BIN,
    ENV_CONFIG,
    ENV_MODEL,
    HermesEnvironmentCheck,
)
from ai_war_game.infrastructure.persistence.file_repository import FileGameRepository
from ai_war_game.infrastructure.persistence.paths import SaveLocator


def register(sub) -> None:
    p = sub.add_parser("new-game", help="创建一局新游戏")
    p.add_argument("--save-id", required=True)
    p.add_argument("--theme", required=True)
    p.add_argument("--player-id", required=True)
    p.add_argument("--player-name", required=True)
    p.set_defaults(handler=_handler)


def _handler(args: argparse.Namespace, *, save_root: Path) -> int:
    repo = FileGameRepository(SaveLocator(root=save_root))
    health = HermesEnvironmentCheck()
    bin_path = os.environ.get(ENV_BIN, DEFAULT_BIN)
    model = os.environ.get(ENV_MODEL, "")
    config_path = os.environ.get(ENV_CONFIG, "")
    generator = HermesScenarioGenerator(bin_path=bin_path, model=model, config_path=config_path)
    service = CreateGameService(
        hermes_health=health,
        scenario_generator=generator,
        repository=repo,
    )
    output = service.execute(
        CreateGameInput(
            save_id=args.save_id,
            theme=args.theme,
            player_id=args.player_id,
            player_display_name=args.player_name,
            issued_at=datetime.now(UTC),
        )
    )
    sys.stdout.write(
        f"已创建存档 {output.save_id} (第 {output.starting_day} 天)\n摘要: {output.summary}\n"
    )
    return exit_codes.OK
