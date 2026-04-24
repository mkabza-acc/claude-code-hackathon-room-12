"""
Eval harness for InstantDesk triage agent.

Runs all labeled tickets through the coordinator and reports:
  - Overall accuracy (queue + priority correct)
  - Precision per queue
  - Escalation rate (correct vs. needless)
  - Adversarial-pass rate
  - False-confidence rate (confident AND wrong)

Usage:
  python evals/harness.py
  python evals/harness.py --adversarial       # adversarial set only
  python evals/harness.py --tickets path/to/custom.json
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import structlog

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.ticket import TicketInput
from agents.coordinator import process_ticket

log = structlog.get_logger()

_DEFAULT_TICKETS = Path(__file__).parent.parent / "data" / "sample_tickets.json"
_OVERRIDES_PATH = Path(__file__).parent.parent / "data" / "overrides.json"
_CONFIDENCE_THRESHOLD = 0.80  # "confident" for false-confidence calculation


def _load_override_tickets() -> list[dict]:
    """Load human-override records and convert them into eval-compatible ticket dicts."""
    if not _OVERRIDES_PATH.exists():
        return []
    with open(_OVERRIDES_PATH) as f:
        overrides = json.load(f)

    # Deduplicate: for each ticket_id keep only the most recent override
    seen: dict = {}
    for o in overrides:
        seen[o["ticket_id"]] = o

    # Load original ticket bodies from the ticket store so we can re-run them
    store_path = Path(__file__).parent.parent / "data" / "ticket_store.json"
    store = {}
    if store_path.exists():
        with open(store_path) as f:
            store = json.load(f)

    result = []
    for o in seen.values():
        tid = o["ticket_id"]
        if tid not in store:
            continue
        # Merge stored ticket context with the human-corrected labels
        entry = {
            "ticket_id": tid,
            "subject": store[tid].get("subject", ""),
            "body": store[tid].get("body", ""),
            "requestor_email": store[tid].get("requestor_email", "unknown@company.com"),
            "requestor_name": store[tid].get("requestor_name", "Unknown"),
            "requestor_title": store[tid].get("requestor_title", ""),
            "channel": store[tid].get("channel", "email"),
            "expected_queue": o["expected_queue"],
            "expected_priority": o["expected_priority"],
            "expected_escalate": o["expected_escalate"],
            "label": "override",
        }
        result.append(entry)
    return result


def _load_tickets(path: Path, adversarial_only: bool, include_overrides: bool = True) -> list[dict]:
    with open(path) as f:
        tickets = json.load(f)
    if adversarial_only:
        tickets = [t for t in tickets if t.get("label") == "adversarial"]
    elif include_overrides:
        override_tickets = _load_override_tickets()
        if override_tickets:
            existing_ids = {t["ticket_id"] for t in tickets}
            # Overrides replace the original labeled entry so ground truth stays authoritative
            tickets = [t for t in tickets if t["ticket_id"] not in {o["ticket_id"] for o in override_tickets}]
            tickets.extend(override_tickets)
            log.info("overrides_loaded", count=len(override_tickets))
    return tickets


def _evaluate(raw: dict, result) -> dict:
    triage = result.triage
    escalation = result.escalation

    queue_correct = triage.queue.value == raw.get("expected_queue")
    priority_correct = triage.priority.value == raw.get("expected_priority")
    escalation_correct = escalation.should_escalate == raw.get("expected_escalate", False)
    confident = triage.confidence >= _CONFIDENCE_THRESHOLD
    false_confident = confident and not (queue_correct and priority_correct)

    return {
        "ticket_id": raw["ticket_id"],
        "label": raw.get("label", "normal"),
        "adversarial_type": raw.get("adversarial_type"),
        "queue_correct": queue_correct,
        "priority_correct": priority_correct,
        "escalation_correct": escalation_correct if "expected_escalate" in raw else None,
        "false_confident": false_confident,
        "predicted_queue": triage.queue.value,
        "expected_queue": raw.get("expected_queue"),
        "predicted_priority": triage.priority.value,
        "expected_priority": raw.get("expected_priority"),
        "confidence": triage.confidence,
        "retry_count": result.total_retry_count,
    }


def run_evals(tickets_path: Path, adversarial_only: bool) -> None:
    raw_tickets = _load_tickets(tickets_path, adversarial_only)
    print(f"\nRunning evals on {len(raw_tickets)} tickets...\n")

    eval_results = []
    for raw in raw_tickets:
        ticket = TicketInput(**{k: v for k, v in raw.items() if k in TicketInput.model_fields})
        result = process_ticket(ticket)
        ev = _evaluate(raw, result)
        eval_results.append(ev)
        status = "PASS" if ev["queue_correct"] and ev["priority_correct"] else "FAIL"
        print(f"  [{status}] {raw['ticket_id']:12} queue={ev['predicted_queue']:15} priority={ev['predicted_priority']}  confidence={ev['confidence']:.2f}  retries={ev['retry_count']}")

    _print_summary(eval_results)


def _print_summary(results: list[dict]) -> None:
    total = len(results)
    if total == 0:
        print("No results.")
        return

    queue_correct = sum(1 for r in results if r["queue_correct"])
    priority_correct = sum(1 for r in results if r["priority_correct"])
    both_correct = sum(1 for r in results if r["queue_correct"] and r["priority_correct"])
    false_confident = sum(1 for r in results if r["false_confident"])

    escalation_evals = [r for r in results if r["escalation_correct"] is not None]
    escalation_correct = sum(1 for r in escalation_evals if r["escalation_correct"])

    adversarial = [r for r in results if r["label"] == "adversarial"]
    adversarial_pass = sum(1 for r in adversarial if r["queue_correct"] and r["priority_correct"])
    overrides = [r for r in results if r["label"] == "override"]
    override_pass = sum(1 for r in overrides if r["queue_correct"] and r["priority_correct"])

    print("\n" + "=" * 60)
    print("EVAL SUMMARY")
    print("=" * 60)
    print(f"  Total tickets:        {total}")
    print(f"  Overall accuracy:     {both_correct}/{total} = {both_correct/total:.1%}")
    print(f"  Queue accuracy:       {queue_correct}/{total} = {queue_correct/total:.1%}")
    print(f"  Priority accuracy:    {priority_correct}/{total} = {priority_correct/total:.1%}")
    print(f"  False-confidence:     {false_confident}/{total} = {false_confident/total:.1%}  (confident+wrong)")
    if escalation_evals:
        print(f"  Escalation accuracy: {escalation_correct}/{len(escalation_evals)} = {escalation_correct/len(escalation_evals):.1%}")
    if adversarial:
        print(f"  Adversarial pass:    {adversarial_pass}/{len(adversarial)} = {adversarial_pass/len(adversarial):.1%}")
    if overrides:
        print(f"  Override regression: {override_pass}/{len(overrides)} = {override_pass/len(overrides):.1%}  (human-corrected cases)")

    print("\nPrecision per queue:")
    queue_tp: dict = defaultdict(int)
    queue_fp: dict = defaultdict(int)
    for r in results:
        if r["queue_correct"]:
            queue_tp[r["predicted_queue"]] += 1
        else:
            queue_fp[r["predicted_queue"]] += 1
    all_queues = sorted(set(list(queue_tp.keys()) + list(queue_fp.keys())))
    for q in all_queues:
        tp = queue_tp[q]
        fp = queue_fp[q]
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        print(f"  {q:16} precision={precision:.1%}  (tp={tp}, fp={fp})")
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="InstantDesk eval harness")
    parser.add_argument("--tickets", default=str(_DEFAULT_TICKETS), help="Path to labeled ticket JSON")
    parser.add_argument("--adversarial", action="store_true", help="Run adversarial set only")
    args = parser.parse_args()

    run_evals(Path(args.tickets), args.adversarial)


if __name__ == "__main__":
    main()
