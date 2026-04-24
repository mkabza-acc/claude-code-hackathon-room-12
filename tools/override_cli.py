"""
CLI for recording human overrides to agent decisions.

Usage:
  python tools/override_cli.py --ticket TKT-ADV-003 --queue hardware --priority P4 --escalate false --reason "Subject inflated; body is a P4 printer location question"
  python tools/override_cli.py --list
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.record_override import record_override

_OVERRIDE_PATH = Path(__file__).parent.parent / "data" / "overrides.json"


def cmd_record(args):
    escalate = args.escalate.lower() in ("true", "yes", "1")
    result = record_override(
        ticket_id=args.ticket,
        correct_queue=args.queue,
        correct_priority=args.priority,
        should_escalate=escalate,
        override_reason=args.reason,
    )
    print(json.dumps(result, indent=2))
    if result.get("isError"):
        sys.exit(1)


def cmd_list(_args):
    if not _OVERRIDE_PATH.exists():
        print("No overrides recorded yet.")
        return
    with open(_OVERRIDE_PATH) as f:
        overrides = json.load(f)
    if not overrides:
        print("No overrides recorded yet.")
        return
    print(f"{'Ticket':15} {'Agent Queue':16} {'→':2} {'Human Queue':16} {'Agent Pri':10} {'→':2} {'Human Pri':10} Reason")
    print("-" * 100)
    for o in overrides:
        pred = o["agent_prediction"]
        corr = o["human_correction"]
        print(
            f"{o['ticket_id']:15} {pred.get('queue','?'):16} {'→':2} {corr['queue']:16} "
            f"{pred.get('priority','?'):10} {'→':2} {corr['priority']:10} {o['override_reason'][:40]}"
        )


def main():
    parser = argparse.ArgumentParser(description="InstantDesk human override recorder")
    sub = parser.add_subparsers(dest="command")

    rec = sub.add_parser("record", help="Record a human correction")
    rec.add_argument("--ticket", required=True)
    rec.add_argument("--queue", required=True)
    rec.add_argument("--priority", required=True)
    rec.add_argument("--escalate", required=True, help="true or false")
    rec.add_argument("--reason", required=True)

    sub.add_parser("list", help="List all recorded overrides")

    # Also support flat flags (no subcommand) for convenience
    parser.add_argument("--ticket")
    parser.add_argument("--queue")
    parser.add_argument("--priority")
    parser.add_argument("--escalate")
    parser.add_argument("--reason")
    parser.add_argument("--list", action="store_true")

    args = parser.parse_args()

    if args.command == "record" or (args.ticket and not args.list):
        cmd_record(args)
    elif args.command == "list" or args.list:
        cmd_list(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
