"""
Tool: record_override

Records a human agent's correction to an agent decision. These overrides feed two places:
  1. The labeled-example store (data/overrides.json) — grows the ground-truth eval set
  2. Few-shot examples injected into the triage prompt on the next coordinator run

DOES: Appends the human correction with the original agent prediction and the ticket context
      to the override store. The entry is tagged so eval_harness.py can include it in
      regression runs.
DOES NOT: Immediately retrain or modify the agent. Does not delete the original ticket record.
          Does not affect tickets already resolved or in-flight.

Input format:
  ticket_id         (str): ticket being corrected
  correct_queue     (str): the queue the human says it should be
  correct_priority  (str): the priority the human says it should be
  should_escalate   (bool): whether the human says this needed escalation
  override_reason   (str): plain-English reason for the correction (required for audit)

Edge cases:
  - ticket_id must exist in the ticket store; unknown IDs return NOT_FOUND
  - Invalid queue/priority values return INVALID_FIELD
  - Re-overriding an already-overridden ticket appends a new entry (history preserved)

Example:
  record_override("TKT-ADV-003", "hardware", "P4", False, "Subject was inflated — body is P4 printer location question")
  -> {"ticket_id": "TKT-ADV-003", "status": "override_recorded", "override_count": 1}

Returns structured error on failure:
  {"isError": True, "code": "NOT_FOUND", "guidance": "Ticket TKT-ADV-003 does not exist in the ticket store."}
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

_STORE_PATH = Path(__file__).parent.parent / "data" / "ticket_store.json"
_OVERRIDE_PATH = Path(__file__).parent.parent / "data" / "overrides.json"

_VALID_QUEUES = {"accounts", "networking", "hardware", "software", "security", "infrastructure"}
_VALID_PRIORITIES = {"P1", "P2", "P3", "P4"}
_MAX_REASON_LEN = 300


def _load_json(path: Path, default):
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return default


def _save_json(path: Path, data) -> None:
    import os
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    # Restrict to owner read/write only — override data feeds LLM prompts.
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass  # Windows does not support POSIX permissions; best-effort only


def record_override(
    ticket_id: str,
    correct_queue: str,
    correct_priority: str,
    should_escalate: bool,
    override_reason: str,
) -> dict:
    # Sanitize and cap reason length before it enters the override store.
    # Stored reasons are later injected into LLM prompts as few-shot examples,
    # so any injection payload here would affect all future triage decisions.
    override_reason = re.sub(r'[\x00-\x1f\x7f]', ' ', str(override_reason)).strip()
    if not override_reason:
        return {"isError": True, "code": "INVALID_FIELD", "guidance": "override_reason is required and cannot be empty."}
    override_reason = override_reason[:_MAX_REASON_LEN]

    if correct_queue not in _VALID_QUEUES:
        return {"isError": True, "code": "INVALID_FIELD", "guidance": f"Queue '{correct_queue}' is not valid. Use one of: {sorted(_VALID_QUEUES)}"}
    if correct_priority not in _VALID_PRIORITIES:
        return {"isError": True, "code": "INVALID_FIELD", "guidance": f"Priority '{correct_priority}' is not valid. Use P1, P2, P3, or P4."}

    store = _load_json(_STORE_PATH, {})
    if ticket_id not in store:
        return {"isError": True, "code": "NOT_FOUND", "guidance": f"Ticket {ticket_id} does not exist in the ticket store. Verify the ticket ID."}

    original = store[ticket_id]
    overrides = _load_json(_OVERRIDE_PATH, [])

    entry = {
        "ticket_id": ticket_id,
        "override_at": datetime.now(timezone.utc).isoformat(),
        "agent_prediction": {
            "queue": original.get("queue"),
            "priority": original.get("priority"),
            "confidence": original.get("confidence"),
        },
        "human_correction": {
            "queue": correct_queue,
            "priority": correct_priority,
            "should_escalate": should_escalate,
        },
        "override_reason": override_reason,
        # These fields make the entry usable directly in eval harness as a labeled example
        "expected_queue": correct_queue,
        "expected_priority": correct_priority,
        "expected_escalate": should_escalate,
        "label": "override",
    }

    overrides.append(entry)
    _save_json(_OVERRIDE_PATH, overrides)

    override_count = sum(1 for o in overrides if o["ticket_id"] == ticket_id)
    return {"ticket_id": ticket_id, "status": "override_recorded", "override_count": override_count}
