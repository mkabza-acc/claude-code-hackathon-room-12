"""
Resolver specialist: attempts to auto-resolve a ticket from the approved auto-resolve list.

Context must be passed explicitly — this agent has no access to coordinator state.
Only resolves: password reset, account unlock, MFA reset, VPN reconnect, standard software install.
NEVER auto-resolves security queue tickets.
Returns a ResolutionResult.
"""

import json
import sys
from pathlib import Path

import anthropic
import structlog

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from models.ticket import TicketInput, TriageResult, ResolutionResult, Queue

log = structlog.get_logger()

_CLIENT = anthropic.AnthropicBedrock(aws_region="us-west-2")
_MODEL = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

_AUTO_RESOLVABLE_QUEUES = {Queue.ACCOUNTS, Queue.NETWORKING, Queue.SOFTWARE}

_SYSTEM_PROMPT = """You are an IT helpdesk resolver specialist. You resolve IT tickets
that fall into the auto-resolvable category.

Auto-resolvable request types (and ONLY these):
1. Password reset
2. Account unlock
3. MFA reset
4. VPN reconnect instructions
5. Standard software install from the pre-approved catalog

For each resolvable request, provide step-by-step resolution instructions that an
IT technician can execute immediately.

If the request is NOT in the auto-resolvable list, respond with CANNOT_AUTO_RESOLVE
and a brief reason.

Respond with valid JSON:
{
  "resolved": true/false,
  "resolution_steps": ["step1", "step2", ...],
  "cannot_auto_resolve_reason": "reason if resolved is false, else null"
}"""


def run_resolver(ticket: TicketInput, triage: TriageResult) -> ResolutionResult:
    if triage.queue == Queue.SECURITY:
        log.info("resolver_skipped_security", ticket_id=ticket.ticket_id)
        return ResolutionResult(
            ticket_id=ticket.ticket_id,
            resolved=False,
            cannot_auto_resolve_reason="Security queue tickets are never auto-resolved.",
        )

    if triage.queue not in _AUTO_RESOLVABLE_QUEUES:
        log.info("resolver_skipped_queue", ticket_id=ticket.ticket_id, queue=triage.queue)
        return ResolutionResult(
            ticket_id=ticket.ticket_id,
            resolved=False,
            cannot_auto_resolve_reason=f"Queue '{triage.queue}' is not in the auto-resolve list.",
        )

    context = f"""Ticket ID: {ticket.ticket_id}
Queue: {triage.queue}
Priority: {triage.priority}
Subject: {ticket.subject}
From: {ticket.requestor_name} ({ticket.requestor_title or "Unknown"})

Body:
{ticket.body}

Triage summary: {triage.reasoning}"""

    try:
        response = _CLIENT.messages.create(
            model=_MODEL,
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": context}],
        )
        raw = response.content[0].text.strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        parsed = json.loads(raw)
        result = ResolutionResult(
            ticket_id=ticket.ticket_id,
            resolved=parsed["resolved"],
            resolution_steps=parsed.get("resolution_steps", []),
            cannot_auto_resolve_reason=parsed.get("cannot_auto_resolve_reason"),
        )
        log.info("resolver_result", ticket_id=ticket.ticket_id, resolved=result.resolved)
        return result

    except (json.JSONDecodeError, KeyError) as exc:
        log.warning("resolver_parse_error", ticket_id=ticket.ticket_id, error=str(exc))
        return ResolutionResult(
            ticket_id=ticket.ticket_id,
            resolved=False,
            cannot_auto_resolve_reason=f"Resolver output parse error: {exc}",
        )
