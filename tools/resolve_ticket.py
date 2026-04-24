"""
Tool: resolve_ticket

Marks an existing ticket as resolved and records the resolution details.

DOES: Updates ticket status to "resolved", stores resolution steps taken, and timestamps closure.
DOES NOT: Perform the actual resolution action (password reset, unlock, etc.) — those are
          separate system calls. Does not notify the requestor. Does not close P1 tickets
          without a resolution_summary — that field is required for P1.

Input format:
  ticket_id          (str):  ticket to close
  resolution_summary (str):  what was done, in plain English, for audit log
  steps_taken        (list[str]): ordered list of actions performed

Edge cases:
  - Attempting to resolve a security-queue ticket will return FORBIDDEN — security tickets
    must be closed by a human, not the agent
  - Ticket must exist; resolving a non-existent ID returns NOT_FOUND

Example:
  resolve_ticket("TKT-001", "Account unlocked via AD reset", ["Verified identity via manager", "Reset AD account"])
  -> {"ticket_id": "TKT-001", "status": "resolved", "resolved_at": "2026-04-24T10:05:00Z"}

Returns structured error on failure:
  {"isError": True, "code": "FORBIDDEN", "guidance": "Security tickets cannot be auto-resolved. Escalate to the security queue for human review."}
"""

import json
from datetime import datetime, timezone
from pathlib import Path

_STORE_PATH = Path(__file__).parent.parent / "data" / "ticket_store.json"


def _load_store() -> dict:
    if _STORE_PATH.exists():
        with open(_STORE_PATH) as f:
            return json.load(f)
    return {}


def _save_store(store: dict) -> None:
    with open(_STORE_PATH, "w") as f:
        json.dump(store, f, indent=2)


def resolve_ticket(ticket_id: str, resolution_summary: str, steps_taken: list[str]) -> dict:
    store = _load_store()

    if ticket_id not in store:
        return {"isError": True, "code": "NOT_FOUND", "guidance": f"Ticket {ticket_id} does not exist. Verify the ticket ID and use create_ticket if this is a new request."}

    record = store[ticket_id]

    if record.get("queue") == "security":
        return {"isError": True, "code": "FORBIDDEN", "guidance": "Security tickets cannot be auto-resolved. Escalate to the security queue for human review."}

    record["status"] = "resolved"
    record["resolution_summary"] = resolution_summary
    record["steps_taken"] = steps_taken
    record["resolved_at"] = datetime.now(timezone.utc).isoformat()

    store[ticket_id] = record
    _save_store(store)
    return {"ticket_id": ticket_id, "status": "resolved", "resolved_at": record["resolved_at"]}
