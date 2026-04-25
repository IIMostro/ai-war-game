"""CLI 入口与子命令分发."""

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from ai_war_game.cli import exit_codes
from ai_war_game.cli.commands import command as command_cmd
from ai_war_game.cli.commands import list_saves as list_saves_cmd
from ai_war_game.cli.commands import new_game as new_game_cmd
from ai_war_game.cli.commands import show as show_cmd
from ai_war_game.domain.errors import (
    AIWarGameError,
    HermesUnavailableError,
    InvalidCommandError,
    SaveCorruptedError,
    SaveNotFoundError,
    ScenarioGenerationError,
    ScenarioInvalidError,
)

DEFAULT_SAVE_ROOT = "data/saves"
ENV_SAVE_ROOT = "AI_WAR_GAME_SAVE_ROOT"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-war-game", description="AI 沙盘战争游戏 CLI")
    parser.add_argument(
        "--save-root",
        default=None,
        help=f"存档根目录 (默认 {DEFAULT_SAVE_ROOT}, 可被环境变量 {ENV_SAVE_ROOT} 覆盖)",
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")
    sub.required = False  # 手动处理缺命令, 以便打印自定义用法
    new_game_cmd.register(sub)
    show_cmd.register(sub)
    command_cmd.register(sub)
    list_saves_cmd.register(sub)
    return parser


def resolve_save_root(args: argparse.Namespace) -> Path:
    if args.save_root:
        return Path(args.save_root)
    env_value = os.environ.get(ENV_SAVE_ROOT)
    if env_value:
        return Path(env_value)
    return Path(DEFAULT_SAVE_ROOT)


def run(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        parser.print_usage(sys.stderr)
        sys.stderr.write("错误: 缺少子命令. 可用: new-game / show / command / list-saves\n")
        return exit_codes.USAGE_ERROR
    args = parser.parse_args(list(argv))
    if not getattr(args, "handler", None):
        parser.print_usage(sys.stderr)
        sys.stderr.write("错误: 缺少子命令. 可用: new-game / show / command / list-saves\n")
        return exit_codes.USAGE_ERROR
    save_root = resolve_save_root(args)
    try:
        return args.handler(args, save_root=save_root)
    except HermesUnavailableError as exc:
        sys.stderr.write(f"Hermes 环境不满足: {exc}\n")
        return exit_codes.HERMES_UNAVAILABLE
    except ScenarioGenerationError as exc:
        sys.stderr.write(f"剧本生成失败: {exc}\n")
        return exit_codes.SCENARIO_GENERATION_FAILED
    except ScenarioInvalidError as exc:
        sys.stderr.write(f"剧本结构无效: {exc}\n")
        return exit_codes.SCENARIO_INVALID
    except SaveNotFoundError as exc:
        sys.stderr.write(f"存档不存在: {exc}\n")
        return exit_codes.SAVE_NOT_FOUND
    except SaveCorruptedError as exc:
        sys.stderr.write(f"存档损坏: {exc}\n")
        return exit_codes.SAVE_CORRUPTED
    except InvalidCommandError as exc:
        sys.stderr.write(f"命令无效: {exc}\n")
        return exit_codes.INVALID_COMMAND
    except AIWarGameError as exc:
        sys.stderr.write(f"运行错误: {exc}\n")
        return exit_codes.UNKNOWN_ERROR
