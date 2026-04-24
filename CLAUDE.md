# InstantDesk — IT Helpdesk Triage Agent

## What This Is

InstantDesk is a Claude Agent SDK application that triages inbound IT helpdesk
tickets. A coordinator agent ingests requests, classifies priority (P1–P4),
enriches with context, and routes to the correct specialist subagent. Specialists
handle triage and auto-resolution. Human-in-the-loop hooks guard high-risk actions.

Hackathon: Scenario 5 — Agentic Solution
Team: Anna (BA), Krzysztof (PM), Lukasz (Dev), Mateusz (Dev), Rafal (QA), M.Ch (QA)

---

## Architecture

- `agents/coordinator.py` — entry point; ingests ticket, classifies, routes to specialist
- `agents/specialists/triage_agent.py` — assigns P1–P4 and target queue
- `agents/specialists/resolver_agent.py` — auto-resolves known request types
- Specialist subagents do NOT inherit coordinator context — always pass context
  explicitly in every Task prompt, never assume the specialist knows anything
- Max 5 tools per specialist — do not add more without removing one first
- All structured outputs use Pydantic models — never return raw dicts

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

These are resolved automatically by the resolver specialist:
- Password reset
- Account unlock
- MFA reset
- VPN reconnect instructions
- Standard software install (pre-approved list only)

---

## Escalation Rules (always send to human)

Escalate when ANY of these are true — all three criteria must be checked:
- Queue is `security`
- Priority is P1
- Ticket mentions: GDPR, data breach, legal, audit, lawsuit, compliance
- Requestor is C-suite (CEO, CFO, CTO, COO, CISO, VP)
- Coordinator confidence < 0.70
- Retry count > 2 on validation loop

---

## Tool Design Rules

Every tool in `/tools` must follow these conventions:

1. **Docstring must state what the tool does NOT do** — not just what it does
2. **All failures return structured errors:**
   ```python
   {"isError": True, "code": "ERROR_CODE", "guidance": "what the agent should try instead"}
   ```
3. **Never return a plain string error** — the agent cannot parse strings reliably
4. **Include input format, edge cases, and one example query in the docstring**
5. Tool files live in `/tools` — one file per tool, named for what it does

---

## Validation-Retry Loop

The coordinator wraps all structured outputs in a retry loop:
- Validator checks output against the ticket schema (Pydantic)
- On failure: feed the specific error back to Claude with context
- Retry up to 3 times maximum
- Log retry count and error type for every request — this is required for The Scorecard

---

## Code Style

- Python 3.11+
- Pydantic v2 for all structured outputs
- No inline comments unless the WHY is non-obvious
- No docstrings that just restate the function name
- Use `python-dotenv` for env vars — never hardcode keys
- Logging: use `structlog` for structured JSON logs — every decision must be replayable from logs alone

---

## Running Locally

```bash
cp .env.example .env        # add ANTHROPIC_API_KEY
pip install -r requirements.txt
python agents/coordinator.py --ticket data/sample_tickets.json
```

---

## Running Evals

```bash
python evals/harness.py     # runs all cases, prints accuracy + precision per queue
python evals/harness.py --adversarial   # runs adversarial set only
```

---

## What NOT to Do

- Do not auto-resolve anything in the `security` queue
- Do not assign P1 without logging a reason
- Do not skip the validation-retry loop to save tokens
- Do not pass the full coordinator context to a specialist — be explicit, be minimal
- Do not add tools beyond 5 per specialist without discussion
