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

# Patterns detect credential exfiltration and prompt-injection signals in raw ticket text.
# These are defence-in-depth only — tickets are processed as opaque data, so these
# patterns catch obvious attempts that slipped past input validation.
# Patterns use broad synonyms and allow for spacing/obfuscation variations.
_PII_EXFIL_PATTERNS = [
    # Credential retrieval / listing
    re.compile(r"\b(send|share|give|show|reveal|display|print|output|return|provide|fetch|get)\b.{0,60}\b(password|passwd|passphrase|secret|credential|token|api.?key)\b", re.IGNORECASE),
    re.compile(r"\b(list|dump|export|extract|enumerate|harvest)\b.{0,60}\b(password|passwd|credential|credentials|account|accounts|user|users|secret|secrets|token|tokens)\b", re.IGNORECASE),
    # Prompt injection / instruction override signals
    re.compile(r"\bignore\b.{0,50}\b(instruction|instructions|previous|prior|above|all)\b", re.IGNORECASE),
    re.compile(r"\b(system|admin|root)\s*(override|prompt|instruction)\b", re.IGNORECASE),
    re.compile(r"\bforget\b.{0,30}\b(instruction|instructions|rule|rules|constraint|constraints|above)\b", re.IGNORECASE),
    re.compile(r"\bnew\s+instruction\b", re.IGNORECASE),
    re.compile(r"\bdo not\s+(follow|obey|respect)\b", re.IGNORECASE),
    re.compile(r"\bact\s+as\b.{0,30}\b(admin|root|superuser|system)\b", re.IGNORECASE),
    # Exfiltration via resolution steps
    re.compile(r"\b(email|send|forward|transmit)\b.{0,60}\b(result|output|response|data|record|log)\b.{0,40}\b(external|outside|attacker|me|my)\b", re.IGNORECASE),
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
