"""
Tool: create_ticket

Creates a new ticket record in the helpdesk system of record with triage results attached.

DOES: Persists a classified ticket (queue, priority, triage reasoning) to the ticket store.
      Returns the assigned ticket ID and creation timestamp.
DOES NOT: Send notifications to users. Does not assign a human agent. Does not auto-resolve.
          Does not modify an existing ticket — use resolve_ticket for that.

Input format:
  ticket_id  (str): original ticket ID from intake
  queue      (str): one of accounts | networking | hardware | software | security | infrastructure
  priority   (str): one of P1 | P2 | P3 | P4
  summary    (str): 1-2 sentence triage summary for the queue agent who picks this up
  confidence (float): classifier confidence 0.0–1.0

Edge cases:
  - Duplicate ticket_id: returns DUPLICATE_TICKET error (do not silently overwrite)
  - Invalid queue or priority values are rejected with INVALID_FIELD error

Example:
  create_ticket("TKT-001", "accounts", "P3", "User locked out after 5 failed attempts. Standard unlock.", 0.95)
  -> {"ticket_id": "TKT-001", "status": "created", "created_at": "2026-04-24T10:00:00Z"}

Returns structured error on failure:
  {"isError": True, "code": "DUPLICATE_TICKET", "guidance": "Ticket TKT-001 already exists. Fetch the existing record instead of creating a new one."}
"""

import json
from datetime import datetime, timezone
from pathlib import Path

_STORE_PATH = Path(__file__).parent.parent / "data" / "ticket_store.json"

_VALID_QUEUES = {"accounts", "networking", "hardware", "software", "security", "infrastructure"}
_VALID_PRIORITIES = {"P1", "P2", "P3", "P4"}


def _load_store() -> dict:
    if _STORE_PATH.exists():
        with open(_STORE_PATH) as f:
            return json.load(f)
    return {}


def _save_store(store: dict) -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_STORE_PATH, "w") as f:
        json.dump(store, f, indent=2)


def create_ticket(ticket_id: str, queue: str, priority: str, summary: str, confidence: float) -> dict:
    if queue not in _VALID_QUEUES:
        return {"isError": True, "code": "INVALID_FIELD", "guidance": f"Queue '{queue}' is not valid. Use one of: {sorted(_VALID_QUEUES)}"}
    if priority not in _VALID_PRIORITIES:
        return {"isError": True, "code": "INVALID_FIELD", "guidance": f"Priority '{priority}' is not valid. Use one of: P1, P2, P3, P4"}

    store = _load_store()
    if ticket_id in store:
        return {"isError": True, "code": "DUPLICATE_TICKET", "guidance": f"Ticket {ticket_id} already exists. Do not overwrite — fetch or update the existing record."}

    record = {
        "ticket_id": ticket_id,
        "queue": queue,
        "priority": priority,
        "summary": summary,
        "confidence": confidence,
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    store[ticket_id] = record
    _save_store(store)
    return {"ticket_id": ticket_id, "status": "created", "created_at": record["created_at"]}
