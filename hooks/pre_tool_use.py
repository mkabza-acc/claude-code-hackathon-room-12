"""
PreToolUse hook for InstantDesk.

Hard-blocks write tools on known high-risk patterns before the agent executes them.
This is a deterministic stop — no LLM judgment involved.

Called by: coordinator.py via check_pre_tool_use() before any write tool call.

Blocked patterns:
  1. resolve_ticket on a security-queue ticket  (blast radius too high)
  2. Any write tool on a frozen account          (account_status == "frozen")
  3. resolve_ticket when body matches PII exfil  (passwords, credential dump patterns)

Returns:
  {"allowed": True}                                       — proceed
  {"allowed": False, "code": "...", "reason": "..."}     — hard stop, do not call the tool
"""

import re

_PII_EXFIL_PATTERNS = [
    re.compile(r"\bsend\b.{0,40}\bpassword", re.IGNORECASE),
    re.compile(r"\blist\b.{0,40}\bpassword", re.IGNORECASE),
    re.compile(r"\bdump\b.{0,40}\bcredential", re.IGNORECASE),
    re.compile(r"\bexport\b.{0,40}\b(user|account|credential)", re.IGNORECASE),
    re.compile(r"\bignore\b.{0,30}\b(instructions|previous|prior)", re.IGNORECASE),
    re.compile(r"\bsystem\s+override\b", re.IGNORECASE),
]

_WRITE_TOOLS = {"resolve_ticket", "escalate_to_human", "create_ticket"}


def check_pre_tool_use(tool_name: str, ticket_body: str, queue: str, account_status: str) -> dict:
    """
    Gate called before any write tool executes.

    Args:
        tool_name:       name of the tool about to be called
        ticket_body:     combined subject + body of the original ticket
        queue:           triage queue assigned to this ticket
        account_status:  account_status from get_user_context ("active" | "frozen" | "suspended" | ...)

    Returns dict with "allowed" bool and, when False, "code" and "reason".
    """
    if tool_name not in _WRITE_TOOLS:
        return {"allowed": True}

    # Rule 1: Never auto-resolve a security-queue ticket
    if tool_name == "resolve_ticket" and queue == "security":
        return {
            "allowed": False,
            "code": "BLOCKED_SECURITY_QUEUE",
            "reason": "resolve_ticket is forbidden on security-queue tickets. Escalate to a human security analyst.",
        }

    # Rule 2: Block all writes on frozen accounts — something is already wrong
    if account_status == "frozen":
        return {
            "allowed": False,
            "code": "BLOCKED_FROZEN_ACCOUNT",
            "reason": "The requestor's account is frozen. No write actions are allowed until a human reviews the account status.",
        }

    # Rule 3: Block resolve when ticket body contains PII exfiltration or prompt injection signals
    if tool_name == "resolve_ticket":
        for pattern in _PII_EXFIL_PATTERNS:
            if pattern.search(ticket_body):
                return {
                    "allowed": False,
                    "code": "BLOCKED_PII_EXFIL_PATTERN",
                    "reason": f"Ticket body matches a known PII exfiltration or prompt-injection pattern (pattern: '{pattern.pattern}'). Escalate for human review — do not auto-resolve.",
                }

    return {"allowed": True}
