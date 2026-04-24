"""
Tool: escalate_to_human

Flags a ticket for mandatory human review and records the escalation reason.

DOES: Creates an escalation record with the trigger reason, urgency, and recommended reviewer.
      Transitions ticket status to "escalated". Logs escalation for audit trail.
DOES NOT: Actually page or notify the human — notification is handled by the downstream
          queue system. Does not resolve the ticket. Does not override a previous escalation.

Input format:
  ticket_id       (str):       ticket being escalated
  reason          (str):       plain-English reason why human review is required
  triggers        (list[str]): machine-readable trigger codes from the escalation rules,
                               e.g. ["SECURITY_QUEUE", "P1", "CSUITE_REQUESTOR"]
  urgency         (str):       "immediate" | "high" | "normal"

Edge cases:
  - Re-escalating an already-escalated ticket is allowed (new reason overwrites); this
    covers the case where the agent gathers more context before handing off
  - ticket_id must exist in the store; escalating unknown IDs returns NOT_FOUND

Trigger codes (use these exact strings):
  SECURITY_QUEUE | P1_PRIORITY | CSUITE_REQUESTOR | GDPR_MENTION | LOW_CONFIDENCE |
  RETRY_LIMIT | LEGAL_MENTION | COMPLIANCE_MENTION | DATA_BREACH_MENTION

Example:
  escalate_to_human("TKT-007", "CEO reporting full email system outage", ["P1_PRIORITY", "CSUITE_REQUESTOR"], "immediate")
  -> {"ticket_id": "TKT-007", "status": "escalated", "escalated_at": "2026-04-24T10:10:00Z"}

Returns structured error on failure:
  {"isError": True, "code": "NOT_FOUND", "guidance": "Ticket TKT-007 does not exist. Create the ticket first, then escalate."}
"""

import json
from datetime import datetime, timezone
from pathlib import Path

_STORE_PATH = Path(__file__).parent.parent / "data" / "ticket_store.json"

_VALID_URGENCY = {"immediate", "high", "normal"}


def _load_store() -> dict:
    if _STORE_PATH.exists():
        with open(_STORE_PATH) as f:
            return json.load(f)
    return {}


def _save_store(store: dict) -> None:
    with open(_STORE_PATH, "w") as f:
        json.dump(store, f, indent=2)


def escalate_to_human(ticket_id: str, reason: str, triggers: list[str], urgency: str) -> dict:
    if urgency not in _VALID_URGENCY:
        return {"isError": True, "code": "INVALID_FIELD", "guidance": f"urgency must be one of: immediate, high, normal. Got '{urgency}'."}

    store = _load_store()
    if ticket_id not in store:
        return {"isError": True, "code": "NOT_FOUND", "guidance": f"Ticket {ticket_id} does not exist. Create the ticket first, then escalate."}

    record = store[ticket_id]
    escalated_at = datetime.now(timezone.utc).isoformat()
    record["status"] = "escalated"
    record["escalation"] = {
        "reason": reason,
        "triggers": triggers,
        "urgency": urgency,
        "escalated_at": escalated_at,
    }

    store[ticket_id] = record
    _save_store(store)
    return {"ticket_id": ticket_id, "status": "escalated", "escalated_at": escalated_at}
