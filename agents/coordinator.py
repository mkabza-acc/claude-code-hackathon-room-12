"""
Coordinator agent: ingests an IT helpdesk ticket, classifies it, enriches with context,
applies escalation rules, routes to the correct specialist, and logs every decision.

Entry point:
  python agents/coordinator.py --ticket data/sample_tickets.json
  python agents/coordinator.py --ticket data/sample_tickets.json --id TKT-001
"""

import argparse
import json
import os
import sys
from pathlib import Path

import structlog
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.ticket import TicketInput, EscalationDecision, CoordinatorOutput, Queue, Priority
from agents.specialists.triage_agent import run_triage
from agents.specialists.resolver_agent import run_resolver
from tools.get_user_context import get_user_context
from tools.create_ticket import create_ticket
from tools.resolve_ticket import resolve_ticket
from tools.escalate_to_human import escalate_to_human

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
log = structlog.get_logger()

_LEGAL_KEYWORDS = {"gdpr", "data breach", "legal", "audit", "lawsuit", "compliance", "article 17", "dsar"}
_CSUITE_TITLES = {"ceo", "cfo", "cto", "coo", "ciso"}


def _check_escalation(ticket: TicketInput, triage, user_ctx: dict, retry_count: int) -> EscalationDecision:
    triggers = []

    if triage.queue == Queue.SECURITY:
        triggers.append("SECURITY_QUEUE")

    if triage.priority == Priority.P1:
        triggers.append("P1_PRIORITY")

    body_lower = (ticket.subject + " " + ticket.body).lower()
    if any(kw in body_lower for kw in _LEGAL_KEYWORDS):
        triggers.append("LEGAL_MENTION")

    is_csuite = user_ctx.get("is_csuite", False)
    if not user_ctx.get("isError") and is_csuite:
        triggers.append("CSUITE_REQUESTOR")

    if triage.confidence < 0.70:
        triggers.append("LOW_CONFIDENCE")

    if retry_count > 2:
        triggers.append("RETRY_LIMIT")

    should_escalate = len(triggers) > 0
    reason = (
        f"Escalation required: {', '.join(triggers)}"
        if should_escalate
        else "No escalation triggers met."
    )
    return EscalationDecision(
        ticket_id=ticket.ticket_id,
        should_escalate=should_escalate,
        reason=reason,
        escalation_triggers=triggers,
    )


def process_ticket(ticket: TicketInput) -> CoordinatorOutput:
    tlog = log.bind(ticket_id=ticket.ticket_id)
    tlog.info("coordinator_start", subject=ticket.subject, channel=ticket.channel)

    user_ctx = get_user_context(ticket.requestor_email)
    if user_ctx.get("isError"):
        tlog.warning("user_context_failed", error_code=user_ctx["code"])
    else:
        tlog.info("user_context_loaded", title=user_ctx.get("title"), is_csuite=user_ctx.get("is_csuite"))

    triage = run_triage(ticket)
    tlog.info("triage_complete", queue=triage.queue, priority=triage.priority, confidence=triage.confidence, retry_count=triage.retry_count)

    escalation = _check_escalation(ticket, triage, user_ctx, triage.retry_count)
    tlog.info("escalation_decision", should_escalate=escalation.should_escalate, triggers=escalation.escalation_triggers)

    create_result = create_ticket(
        ticket_id=ticket.ticket_id,
        queue=triage.queue.value,
        priority=triage.priority.value,
        summary=triage.reasoning,
        confidence=triage.confidence,
    )
    if create_result.get("isError"):
        tlog.warning("create_ticket_failed", error_code=create_result["code"])

    resolution = None
    if not escalation.should_escalate:
        resolution = run_resolver(ticket, triage)
        if resolution.resolved:
            resolve_ticket(
                ticket_id=ticket.ticket_id,
                resolution_summary="; ".join(resolution.resolution_steps[:2]),
                steps_taken=resolution.resolution_steps,
            )
            tlog.info("auto_resolved", steps=len(resolution.resolution_steps))
        else:
            tlog.info("cannot_auto_resolve", reason=resolution.cannot_auto_resolve_reason)

    if escalation.should_escalate:
        urgency = "immediate" if Priority.P1 in [triage.priority] or "CSUITE_REQUESTOR" in escalation.escalation_triggers else "high"
        escalate_to_human(
            ticket_id=ticket.ticket_id,
            reason=escalation.reason,
            triggers=escalation.escalation_triggers,
            urgency=urgency,
        )
        tlog.info("escalated_to_human", urgency=urgency)

    output = CoordinatorOutput(
        ticket_id=ticket.ticket_id,
        triage=triage,
        escalation=escalation,
        resolution=resolution,
        total_retry_count=triage.retry_count,
    )
    tlog.info("coordinator_complete", escalated=escalation.should_escalate, resolved=resolution.resolved if resolution else False)
    return output


def main():
    parser = argparse.ArgumentParser(description="InstantDesk coordinator agent")
    parser.add_argument("--ticket", required=True, help="Path to ticket JSON file")
    parser.add_argument("--id", help="Process only this ticket ID (optional)")
    args = parser.parse_args()

    with open(args.ticket) as f:
        raw = json.load(f)

    tickets = raw if isinstance(raw, list) else [raw]
    if args.id:
        tickets = [t for t in tickets if t["ticket_id"] == args.id]
        if not tickets:
            print(f"Ticket {args.id} not found in {args.ticket}")
            sys.exit(1)

    results = []
    for t in tickets:
        ticket = TicketInput(**t)
        result = process_ticket(ticket)
        results.append(result.model_dump())

    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
