"""
Tool: get_user_context

Looks up a user in the directory (Active Directory / CMDB) by email address.

DOES: Returns the user's name, title, department, manager, account status (active/locked),
      and whether they are C-suite (CEO, CFO, CTO, COO, CISO, VP).
DOES NOT: Modify account state. Does not return passwords, MFA secrets, or audit logs.
          Does not search by name — only by exact email address.

Input format:
  email (str): the requestor's email, e.g. "john.doe@company.com"

Edge cases:
  - Returns NOT_FOUND if email is not in directory (not necessarily an error — could be contractor)
  - is_csuite flag is set for: CEO, CFO, CTO, COO, CISO, and any title containing "VP" or "Vice President"

Example:
  get_user_context("cto@company.com")
  -> {"email": "cto@company.com", "name": "Alex Kim", "title": "CTO", "department": "Technology",
      "account_status": "active", "is_csuite": True, "manager": null}

Returns structured error on failure:
  {"isError": True, "code": "DIRECTORY_UNAVAILABLE", "guidance": "AD lookup is offline. Treat requestor as standard user and flag for manual verification."}
"""

import json
from pathlib import Path


_USERS_PATH = Path(__file__).parent.parent / "data" / "users.json"

_CSUITE_TITLES = {"ceo", "cfo", "cto", "coo", "ciso"}


def get_user_context(email: str) -> dict:
    try:
        with open(_USERS_PATH) as f:
            users = json.load(f)
    except FileNotFoundError:
        return {"isError": True, "code": "DIRECTORY_UNAVAILABLE", "guidance": "User directory file not found. Treat requestor as standard user and flag for manual verification."}
    except json.JSONDecodeError:
        return {"isError": True, "code": "DIRECTORY_CORRUPT", "guidance": "Directory data is malformed. Escalate to infrastructure queue."}

    user = users.get(email.lower())
    if not user:
        return {"isError": True, "code": "USER_NOT_FOUND", "guidance": "Email not in directory. Requestor may be a contractor or external user. Proceed with standard priority."}

    title_lower = user.get("title", "").lower()
    user["is_csuite"] = (
        any(t in title_lower for t in _CSUITE_TITLES)
        or "vp" in title_lower
        or "vice president" in title_lower
    )
    return user
