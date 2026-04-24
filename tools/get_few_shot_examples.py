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
import re
from pathlib import Path

_OVERRIDE_PATH = Path(__file__).parent.parent / "data" / "overrides.json"
_MAX_EXAMPLES = 10
_VALID_QUEUES = {"accounts", "networking", "hardware", "software", "security", "infrastructure"}
_VALID_PRIORITIES = {"P1", "P2", "P3", "P4"}
_MAX_REASON_LEN = 300


def _sanitize_reason(reason: str) -> str:
    """Strip control characters and truncate to prevent prompt injection via stored override reasons."""
    sanitized = re.sub(r'[\x00-\x1f\x7f]', ' ', str(reason)).strip()
    return sanitized[:_MAX_REASON_LEN]


def _safe_queue(val) -> str:
    return str(val) if val in _VALID_QUEUES else "unknown"


def _safe_priority(val) -> str:
    return str(val) if val in _VALID_PRIORITIES else "unknown"


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
        pred = o.get("agent_prediction", {})
        corr = o.get("human_correction", {})
        # Sanitize every field that originates from user-supplied data before
        # injecting it into a prompt, to block stored prompt-injection payloads.
        lines.append(
            f"\nExample {i}:\n"
            f"  Agent predicted: queue={_safe_queue(pred.get('queue'))}, priority={_safe_priority(pred.get('priority'))}, confidence={pred.get('confidence', '?')}\n"
            f"  Human corrected: queue={_safe_queue(corr.get('queue'))}, priority={_safe_priority(corr.get('priority'))}, escalate={bool(corr.get('should_escalate'))}\n"
            f"  Reason: {_sanitize_reason(o.get('override_reason', ''))}"
        )

    return {"examples": "\n".join(lines), "count": len(recent)}
