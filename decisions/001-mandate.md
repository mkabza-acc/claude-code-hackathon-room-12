# ADR-001: The Mandate — What InstantDesk Decides Alone vs. Escalates

**Status:** Accepted
**Date:** 2026-04-24
**Authors:** Anna (BA), Krzysztof (PM)

---

## What the Agent Decides Alone

InstantDesk classifies and routes every inbound IT ticket without human involvement when:

1. **Ticket can be auto-resolved** — the request type is on the approved list (password reset, account unlock, MFA reset, VPN reconnect instructions, standard software install from pre-approved catalog) AND no escalation trigger is present.
2. **Ticket requires routing only** — the issue is clearly classifiable into one of the six queues (accounts, networking, hardware, software, security, infrastructure) with confidence ≥ 0.70, and no escalation trigger fires.

The agent creates the ticket record, logs its reasoning, and either resolves it or routes it to the correct queue — all without paging a human.

---

## What the Agent Always Escalates to a Human

The agent escalates and blocks any write action whenever ANY of the following triggers are present:

| Trigger | Code | Rationale |
|---|---|---|
| Ticket routed to `security` queue | `SECURITY_QUEUE` | All security incidents need human judgment regardless of apparent simplicity |
| Priority is P1 | `P1_PRIORITY` | Full outages and breaches move too fast and carry too much risk for automation |
| Body contains GDPR / legal / compliance / audit / data breach / lawsuit | `LEGAL_MENTION` | Legal exposure cannot be auto-resolved; Legal team must be in the loop |
| Requestor is C-suite (CEO, CFO, CTO, COO, CISO, VP) | `CSUITE_REQUESTOR` | Executive issues carry reputational risk; a human should own the response |
| Classifier confidence < 0.70 | `LOW_CONFIDENCE` | Agent uncertainty is itself a signal; rather than guess, escalate |
| Retry count > 2 on validation loop | `RETRY_LIMIT` | Persistent output failures indicate an edge case the agent cannot handle cleanly |

**All six criteria are checked on every ticket.** A single trigger is sufficient to escalate.

---

## What We Are Deliberately NOT Automating

| Area | Why Not |
|---|---|
| Any action in the `security` queue | The blast radius of a wrong decision (unblocking a compromised account, missing a breach) is too high. A human always owns security. |
| MFA reset for C-suite, even if it looks routine | Impersonation risk. An attacker could pose as an assistant to reset CEO MFA. Human verification required. |
| Access grants to production systems | Scope creep and privilege escalation risk. Access requests beyond standard apps go to a human. |
| Vendor or external user requests | Our directory doesn't cover contractors reliably; we can't verify identity or authority. |
| Anything touching GDPR / data subjects | Any data subject request (DSAR) or GDPR inquiry requires DPO involvement. The agent flags and routes; it does not respond. |
| Billing, procurement, or contract questions | Out of IT scope entirely. Agent routes to Finance or Procurement. |

---

## Escalation Matrix

| Queue | P1 | P2 | P3 | P4 |
|---|---|---|---|---|
| accounts | Escalate | Route | Auto-resolve if eligible | Auto-resolve if eligible |
| networking | Escalate | Route | Route | Route |
| hardware | Escalate | Route | Route | Route |
| software | Escalate | Route | Route | Auto-resolve if eligible |
| security | **Always escalate** | **Always escalate** | **Always escalate** | **Always escalate** |
| infrastructure | Escalate | Route | Route | Route |

C-suite requestor → always escalate regardless of queue or priority.
Legal/GDPR mention → always escalate regardless of queue or priority.
