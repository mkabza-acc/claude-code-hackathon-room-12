"""
Tool: get_few_shot_examples

Loads human-override records and formats the most recent N as few-shot examples
for the triage prompt. Called by the coordinator before invoking the triage specialist
when overrides exist.

DOES: Reads overrides.json and returns the most recent N entries as formatted
      prompt text showing what the human corrected and why.
DOES NOT: Modify the override store. Does not filter by queue or type.
          Does not guarantee the examples are stratified.

Input format:
  n (int): number of examples to return (default 3, max 10)

Returns:
  {"examples": "<formatted prompt text>", "count": <int>}
  or {"examples": "", "count": 0} if no overrides exist yet.
"""

import json
from pathlib import Path

_OVERRIDE_PATH = Path(__file__).parent.parent / "data" / "overrides.json"
_MAX_EXAMPLES = 10


def get_few_shot_examples(n: int = 3) -> dict:
    n = min(max(n, 1), _MAX_EXAMPLES)

    if not _OVERRIDE_PATH.exists():
        return {"examples": "", "count": 0}

    with open(_OVERRIDE_PATH) as f:
        overrides = json.load(f)

    if not overrides:
        return {"examples": "", "count": 0}

    recent = overrides[-n:]

    lines = ["Recent human corrections (use these as calibration examples):"]
    for i, o in enumerate(recent, 1):
        pred = o["agent_prediction"]
        corr = o["human_correction"]
        lines.append(
            f"\nExample {i} — Ticket {o['ticket_id']}:\n"
            f"  Agent predicted: queue={pred.get('queue')}, priority={pred.get('priority')}, confidence={pred.get('confidence', '?')}\n"
            f"  Human corrected: queue={corr['queue']}, priority={corr['priority']}, escalate={corr['should_escalate']}\n"
            f"  Reason: {o['override_reason']}"
        )

    return {"examples": "\n".join(lines), "count": len(recent)}
