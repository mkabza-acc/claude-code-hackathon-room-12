"""
Tool: lookup_knowledge

Searches the internal IT knowledge base for articles matching a query.

DOES: Returns article titles, summaries, and resolution steps for known IT issues.
DOES NOT: Create, update, or delete KB articles. Does not access live system state
          or verify whether a fix worked. Does not search user data or ticket history.

Input format:
  query (str): natural-language description of the issue, e.g. "VPN not connecting after password change"

Edge cases:
  - Returns empty list when no articles match (not an error)
  - Partial keyword matches are included; caller should pick the most relevant

Example:
  lookup_knowledge("account locked after failed login attempts")
  -> [{"id": "KB-042", "title": "Unlock Active Directory Account", "summary": "...", "steps": [...]}]

Returns structured error on failure:
  {"isError": True, "code": "KB_UNAVAILABLE", "guidance": "Knowledge base is offline. Try get_user_context to check account status directly."}
"""

import json
import os
from pathlib import Path


_KB_PATH = Path(__file__).parent.parent / "data" / "knowledge_base.json"


def lookup_knowledge(query: str) -> list[dict] | dict:
    try:
        with open(_KB_PATH) as f:
            articles = json.load(f)
    except FileNotFoundError:
        return {"isError": True, "code": "KB_UNAVAILABLE", "guidance": "Knowledge base file not found. Try get_user_context to check account status directly."}
    except json.JSONDecodeError:
        return {"isError": True, "code": "KB_CORRUPT", "guidance": "Knowledge base data is malformed. Escalate to infrastructure queue."}

    query_lower = query.lower()
    results = [
        a for a in articles
        if any(kw in query_lower for kw in a.get("keywords", []))
    ]
    return results
