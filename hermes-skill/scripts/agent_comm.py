"""hermes-skill/scripts/agent_comm.py — Multi-agent communication orchestration."""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from llm_client import llm_chat

HERMES_ROOT = os.path.join(os.path.expanduser("~"), ".hermes")
OUTBOX_FILE = "outbox.json"


def general_profile_dir(general_id: str) -> str:
    return os.path.join(HERMES_ROOT, "profiles", general_id)


def send_to_inbox(general_id: str, context: str) -> None:
    prof_dir = Path(general_profile_dir(general_id))
    prof_dir.mkdir(parents=True, exist_ok=True)
    (prof_dir / "inbox.json").write_text(context, encoding="utf-8")


def _process_general(general_id: str, timeout: int) -> dict:
    prof_dir = Path(general_profile_dir(general_id))
    inbox = prof_dir / "inbox.json"
    soul_path = prof_dir / "SOUL.md"

    try:
        user_message = inbox.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {"general": general_id, "status": "error", "error": f"inbox 不存在: {inbox}"}

    soul_content = ""
    if soul_path.is_file():
        soul_content = soul_path.read_text(encoding="utf-8")

    try:
        response = llm_chat(system_prompt=soul_content, user_message=user_message)
    except Exception as e:
        return {"general": general_id, "status": "error", "error": str(e)}

    (prof_dir / "outbox.json").write_text(response, encoding="utf-8")
    return {"general": general_id, "response": response, "status": "ok"}


def invoke_generals(general_ids: list[str], timeout: int = 120) -> list[dict]:
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_process_general, gid, timeout): gid for gid in general_ids}
        for future in as_completed(futures):
            results.append(future.result())
    return results


def collect_responses(general_ids: list[str]) -> list[dict]:
    results: list[dict] = []
    for gid in general_ids:
        outbox_path = os.path.join(general_profile_dir(gid), OUTBOX_FILE)
        try:
            with open(outbox_path, encoding="utf-8") as f:
                response = f.read()
            results.append({"general": gid, "response": response, "status": "ready"})
        except FileNotFoundError:
            results.append({"general": gid, "status": "pending"})
        except OSError as e:
            results.append({"general": gid, "status": "error", "error": str(e)})
    return results


def reflect(general_ids: list[str], event_description: str, timeout: int = 120) -> list[dict]:
    """Send event results to generals for memory reflection.

    Writes event summary to each general's inbox as a "memory" type context,
    then invokes them to process it (updating MEMORY.md via Hermes chat).
    Returns invoke results.
    """
    for gid in general_ids:
        context = json.dumps({
            "type": "memory_reflection",
            "event": event_description,
        }, ensure_ascii=False)
        send_to_inbox(gid, context)
    return invoke_generals(general_ids, timeout=timeout)


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

    p_reflect = sub.add_parser("reflect", help="Send event to generals for memory reflection")
    p_reflect.add_argument("--generals", required=True)
    p_reflect.add_argument("--event", required=True)
    p_reflect.add_argument("--timeout", type=int, default=120)

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
        results = collect_responses(gids)
        print(json.dumps(results, ensure_ascii=False, indent=2))
    elif args.command == "reflect":
        gids = [g.strip() for g in args.generals.split(",") if g.strip()]
        results = reflect(gids, args.event, timeout=args.timeout)
        print(json.dumps(results, ensure_ascii=False, default=str))
    elif args.command == "status":
        results = get_status()
        print(json.dumps(results, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
