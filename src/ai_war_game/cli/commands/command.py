"""command 子命令."""

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from ai_war_game.application.execute_command import ExecuteCommandService
from ai_war_game.cli import exit_codes
from ai_war_game.infrastructure.persistence.file_repository import FileGameRepository
from ai_war_game.infrastructure.persistence.paths import SaveLocator
from ai_war_game.interfaces.envelope import CommandEnvelope, CommandSource


def register(sub) -> None:
    p = sub.add_parser("command", help="向当前存档执行一条玩家命令")
    p.add_argument("--save-id", required=True)
    p.add_argument("--player-id", required=True)
    p.add_argument("--text", required=True)
    p.set_defaults(handler=_handler)


def _handler(args: argparse.Namespace, *, save_root: Path) -> int:
    repo = FileGameRepository(SaveLocator(root=save_root))
    envelope = CommandEnvelope(
        source=CommandSource.CLI,
        player_id=args.player_id,
        save_id=args.save_id,
        command_text=args.text,
        timestamp=datetime.now(UTC),
    )
    service = ExecuteCommandService(repository=repo)
    result = service.execute(envelope.to_command_request())
    sys.stdout.write(
        f"{result.message} (accepted={result.accepted}, 第 {result.new_day} 天)\n"
    )
    return exit_codes.OK
