"""list-saves 子命令."""

import argparse
import sys
from pathlib import Path

from ai_war_game.application.list_saves import ListSavesService
from ai_war_game.cli import exit_codes
from ai_war_game.cli.formatting import format_save_summaries
from ai_war_game.infrastructure.persistence.file_repository import FileGameRepository
from ai_war_game.infrastructure.persistence.paths import SaveLocator


def register(sub) -> None:
    p = sub.add_parser("list-saves", help="列出本地所有存档")
    p.set_defaults(handler=_handler)


def _handler(args: argparse.Namespace, *, save_root: Path) -> int:
    repo = FileGameRepository(SaveLocator(root=save_root))
    summaries = ListSavesService(repository=repo).execute()
    sys.stdout.write(format_save_summaries(summaries) + "\n")
    return exit_codes.OK
