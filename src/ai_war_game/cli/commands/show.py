"""show 子命令."""

import argparse
import sys
from pathlib import Path

from ai_war_game.application.show_game import ShowGameService
from ai_war_game.cli import exit_codes
from ai_war_game.cli.formatting import format_show_output
from ai_war_game.infrastructure.persistence.file_repository import FileGameRepository
from ai_war_game.infrastructure.persistence.paths import SaveLocator


def register(sub) -> None:
    p = sub.add_parser("show", help="展示当前存档状态")
    p.add_argument("--save-id", required=True)
    p.set_defaults(handler=_handler)


def _handler(args: argparse.Namespace, *, save_root: Path) -> int:
    repo = FileGameRepository(SaveLocator(root=save_root))
    service = ShowGameService(repository=repo)
    view = service.execute(save_id=args.save_id)
    sys.stdout.write(format_show_output(view) + "\n")
    return exit_codes.OK
