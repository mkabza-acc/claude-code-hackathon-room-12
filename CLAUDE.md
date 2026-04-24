# InstantDesk — IT Helpdesk Triage Agent

## What This Is

InstantDesk triages inbound IT helpdesk tickets using Claude on AWS Bedrock.
A coordinator agent ingests requests, classifies priority (P1–P4), enriches
with context, and routes to the correct specialist. Specialists handle triage
and auto-resolution. A deterministic PreToolUse hook guards all write actions.

Hackathon: Scenario 5 — Agentic Solution
Team: Anna (BA), Krzysztof (PM), Lukasz (Dev), Mateusz (Dev), Rafal (QA), M.Ch (QA)

---

## Architecture

```
agents/
  coordinator.py              — entry point; ingests, enriches, routes, escalates
  specialists/
    triage_agent.py           — classifies queue + priority; owns the retry loop
    resolver_agent.py         — auto-resolves approved request types
hooks/
  pre_tool_use.py             — deterministic gate before any write tool call
tools/
  create_ticket.py            — persists classified ticket to ticket_store.json
  resolve_ticket.py           — marks ticket resolved, records steps
  escalate_to_human.py        — flags ticket for human review
  get_user_context.py         — looks up requestor in users.json (C-suite flag)
  lookup_knowledge.py         — keyword search over knowledge_base.json
models/
  ticket.py                   — all Pydantic models (TicketInput, TriageResult, …)
evals/
  harness.py                  — accuracy, precision/queue, escalation, adversarial
data/
  sample_tickets.json         — 8 normal + 5 adversarial labeled test cases
  users.json                  — mock directory (is_csuite flag, account_status)
  knowledge_base.json         — 7 KB articles (auto_resolvable flag)
  ticket_store.json           — runtime output; written by create/resolve/escalate tools
decisions/                    — Architecture Decision Records (ADR-001 to ADR-003)
dashboard.html                — static visualization; data is hard-coded, not live
```

**Key constraints:**
- Specialist subagents have no access to coordinator state — pass all context explicitly
- Max 5 tools per specialist — do not add more without removing one first
- All structured outputs use Pydantic models — never return raw dicts
- Model: `us.anthropic.claude-haiku-4-5-20251001-v1:0` via `AnthropicBedrock(aws_region="us-west-2")`

---

## Queues

| Queue | Handles |
|---|---|
| `accounts` | Password resets, account lockouts, MFA issues, access requests |
| `networking` | VPN, WiFi, connectivity, firewall requests |
| `hardware` | Laptop issues, monitors, peripherals, office equipment |
| `software` | App installs, licenses, crashes, compatibility |
| `security` | Suspicious emails, malware, data breach suspicions, compromised accounts |
| `infrastructure` | Servers down, database issues, cloud outages |

---

## Priority Rules

| Priority | Criteria |
|---|---|
| P1 | Full outage, security breach, exec affected, >50 users impacted |
| P2 | Partial outage, key business system degraded, deadline at risk |
| P3 | Single user impacted, workaround exists |
| P4 | How-to questions, minor inconvenience, future requests |

---

## Auto-Resolve (no human required)

Handled automatically by `resolver_agent.py` for queues: `accounts`, `networking`, `software`.

- Password reset
- Account unlock
- MFA reset
- VPN reconnect instructions
- Standard software install (pre-approved list only)

The security queue is **never** auto-resolved — hard-blocked in both the resolver and the PreToolUse hook.

---

## Escalation Rules

Escalate when **any** of these triggers fire — all six are checked on every ticket:

| Trigger | Constant |
|---|---|
| Queue is `security` | `SECURITY_QUEUE` |
| Priority is P1 | `P1_PRIORITY` |
| Body mentions: GDPR, data breach, legal, audit, lawsuit, compliance, Article 17, DSAR | `LEGAL_MENTION` |
| Requestor is C-suite (CEO, CFO, CTO, COO, CISO) | `CSUITE_REQUESTOR` |
| Classifier confidence < 0.70 | `LOW_CONFIDENCE` |
| Retry count > 2 on validation loop | `RETRY_LIMIT` |

Escalation urgency: `immediate` if P1 or C-suite, else `high`.

---

## PreToolUse Hook (`hooks/pre_tool_use.py`)

Called by the coordinator **before** every write tool (`create_ticket`, `resolve_ticket`, `escalate_to_human`). Returns `{"allowed": True}` or `{"allowed": False, "code": "...", "reason": "..."}`.

Hard-blocked patterns (deterministic, no LLM involved):

| Code | Condition |
|---|---|
| `BLOCKED_SECURITY_QUEUE` | `resolve_ticket` called on a security-queue ticket |
| `BLOCKED_FROZEN_ACCOUNT` | Any write tool when `account_status == "frozen"` |
| `BLOCKED_PII_EXFIL_PATTERN` | `resolve_ticket` when body matches prompt-injection or credential-dump regex |

A blocked hook forces escalation — the coordinator treats it as a hard stop and calls `escalate_to_human` instead.

---

## Validation-Retry Loop

Implemented inside `triage_agent.py` (not the coordinator):

- Claude returns JSON; the specialist parses and validates against the Pydantic schema
- On failure: the bad response and the specific error are fed back to Claude in the next turn
- Max 3 attempts per ticket
- `retry_count` is carried on `TriageResult` and logged on every attempt — required for evals

---

## Tool Design Rules

Every tool in `/tools` must follow these conventions:

1. **Docstring must state what the tool does NOT do** — not just what it does
2. **All failures return structured errors:**
   ```python
   {"isError": True, "code": "ERROR_CODE", "guidance": "what the agent should try instead"}
   ```
3. **Never return a plain string error** — the agent cannot parse strings reliably
4. **Include input format, edge cases, and one example in the docstring**
5. One file per tool in `/tools`, named for what it does

---

## Code Style

- Python 3.11+
- Pydantic v2 for all structured outputs
- No inline comments unless the WHY is non-obvious
- No docstrings that just restate the function name
- `python-dotenv` for env vars — never hardcode credentials
- `structlog` for structured JSON logs — every decision must be replayable from logs alone

---

## Running Locally

**1. Authenticate to AWS (required before every session):**
```bash
aws login --profile bootcamp --region us-east-1
export AWS_PROFILE=bootcamp          # macOS/WSL
# set AWS_PROFILE=bootcamp           # Windows non-WSL
```

**2. Set up environment:**
```bash
cp .env.example .env                 # already has AWS_PROFILE and AWS_DEFAULT_REGION
pip install -r requirements.txt
```

**3. Run:**
```bash
# All tickets
python agents/coordinator.py --ticket data/sample_tickets.json

# Single ticket (useful for testing)
python agents/coordinator.py --ticket data/sample_tickets.json --id TKT-001
```

`ticket_store.json` is the live output — tickets are appended on each run. Clear it with `echo {} > data/ticket_store.json` for a clean run.

---

## Running Evals

```bash
python evals/harness.py                  # all cases: accuracy + precision per queue
python evals/harness.py --adversarial    # adversarial set only
```

Metrics: overall accuracy, queue accuracy, priority accuracy, precision per queue, escalation accuracy, adversarial pass rate, false-confidence rate (≥0.80 and wrong).

---

## What NOT to Do

- Do not auto-resolve anything in the `security` queue
- Do not assign P1 without logging a reason
- Do not skip the validation-retry loop to save tokens
- Do not pass the full coordinator context to a specialist — be explicit, be minimal
- Do not add tools beyond 5 per specialist without discussion
- Do not use `anthropic.Anthropic()` — this repo uses `AnthropicBedrock`; no API key is needed
