"""hermes-skill/scripts/agent_comm.py — Multi-agent communication orchestration."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERMES_ROOT = os.path.join(os.path.expanduser("~"), ".hermes")


def general_profile_dir(general_id: str) -> str:
    return os.path.join(HERMES_ROOT, "profiles", general_id)


def send_to_inbox(general_id: str, context: str) -> None:
    prof_dir = Path(general_profile_dir(general_id))
    prof_dir.mkdir(parents=True, exist_ok=True)
    (prof_dir / "inbox.json").write_text(context, encoding="utf-8")


def _process_general(general_id: str, timeout: int) -> dict:
    prof_dir = Path(general_profile_dir(general_id))
    inbox = prof_dir / "inbox.json"

    if not inbox.is_file():
        return {"general": general_id, "status": "error", "error": "inbox not found"}

    context = inbox.read_text(encoding="utf-8")
    try:
        result = subprocess.run(
            ["hermes", "-p", general_id, "chat", "-q", context],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        response = result.stdout
        (prof_dir / "outbox.json").write_text(response, encoding="utf-8")
        return {"general": general_id, "response": response, "status": "ok"}
    except FileNotFoundError:
        return {"general": general_id, "status": "error", "error": "hermes binary not found"}
    except subprocess.TimeoutExpired:
        return {"general": general_id, "status": "timeout"}
    except Exception as e:
        return {"general": general_id, "status": "error", "error": str(e)}


def invoke_generals(general_ids: list[str], timeout: int = 120) -> list[dict]:
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(_process_general, gid, timeout): gid for gid in general_ids
        }
        for future in as_completed(futures):
            results.append(future.result())
    return results


def collect_responses(general_ids: list[str], timeout: int = 30) -> list[dict]:
    results: list[dict] = []
    for gid in general_ids:
        prof_dir = Path(general_profile_dir(gid))
        outbox = prof_dir / "outbox.json"
        if outbox.is_file():
            content = outbox.read_text(encoding="utf-8")
            results.append({"general": gid, "response": content, "status": "ready"})
        else:
            results.append({"general": gid, "status": "pending"})
    return results


def get_status() -> list[dict]:
    profiles_dir = Path(HERMES_ROOT) / "profiles"
    if not profiles_dir.is_dir():
        return []

    results: list[dict] = []
    for entry in sorted(profiles_dir.iterdir()):
        if not entry.is_dir():
            continue
        gid = entry.name
        results.append(
            {
                "general_id": gid,
                "has_inbox": (entry / "inbox.json").is_file(),
                "has_outbox": (entry / "outbox.json").is_file(),
                "has_soul": (entry / "SOUL.md").is_file(),
                "has_memory": (entry / "MEMORY.md").is_file(),
                "has_config": (entry / "config.yaml").is_file(),
            }
        )
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Multi-agent communication tool")
    sub = parser.add_subparsers(dest="command", required=True)

    send_p = sub.add_parser("send", help="Send context to a general's inbox")
    send_p.add_argument("--general", required=True, help="General ID")
    send_p.add_argument("--context", required=True, help="JSON context string")

    invoke_p = sub.add_parser("invoke", help="Invoke generals to process their inbox")
    invoke_p.add_argument("--generals", required=True, help="Comma-separated general IDs")
    invoke_p.add_argument("--timeout", type=int, default=120, help="Timeout per general")

    collect_p = sub.add_parser("collect", help="Collect responses from generals")
    collect_p.add_argument("--generals", required=True, help="Comma-separated general IDs")
    collect_p.add_argument("--timeout", type=int, default=30, help="Timeout (unused)")

    sub.add_parser("status", help="Show status of all general profiles")

    args = parser.parse_args(argv)

    if args.command == "send":
        send_to_inbox(args.general, args.context)
        print(json.dumps({"general": args.general, "status": "sent"}, ensure_ascii=False))
    elif args.command == "invoke":
        gids = [g.strip() for g in args.generals.split(",") if g.strip()]
        results = invoke_generals(gids, timeout=args.timeout)
        print(json.dumps(results, ensure_ascii=False, indent=2))
    elif args.command == "collect":
        gids = [g.strip() for g in args.generals.split(",") if g.strip()]
        results = collect_responses(gids, timeout=args.timeout)
        print(json.dumps(results, ensure_ascii=False, indent=2))
    elif args.command == "status":
        results = get_status()
        print(json.dumps(results, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
