# Team InstantDesk

## Participants
- Anna (Business Analyst)
- Krzysztof (Product Manager)
- Lukasz (Developer)
- Mateusz (Developer)
- Rafal (QA)
- M.Ch (QA)

## Scenario
Scenario 5: Agentic Solution — IT Helpdesk Triage Agent

## What We Built

InstantDesk is a working IT helpdesk triage agent built on the Claude API. It ingests support tickets
(email, Slack, chat, web form), classifies them into one of six queues (accounts, networking, hardware,
software, security, infrastructure) with a P1–P4 priority, enriches the ticket with user context from
the directory, applies deterministic escalation rules, auto-resolves eligible requests, and logs every
decision in structured JSON so every routing choice is replayable from the log alone.

The agent uses a coordinator + specialist split: the coordinator handles intake, enrichment, and routing;
two specialist subagents (triage, resolver) handle classification and resolution. Specialists receive only
the context they need — no implicit inheritance from the coordinator. Five tools back the specialists,
each with explicit "does not do" docstrings and structured error returns so the agent can recover without
parsing error strings.

The eval harness runs 13 labeled tickets (8 normal + 5 adversarial) through the full pipeline and reports
accuracy, precision per queue, escalation correctness, adversarial-pass rate, and false-confidence rate.

**What runs:** coordinator pipeline end-to-end, triage + resolver specialists, all 5 tools with mock data,
eval harness with metrics output.

**What's scaffolded / mocked:** user directory and knowledge base are JSON files (no real AD/ServiceNow).
The PreToolUse hook is documented in ADR-003 but not yet wired into the SDK hook interface.

## Challenges Attempted

| # | Challenge | Status | Notes |
|---|---|---|---|
| 1 | The Mandate | done | `decisions/001-mandate.md` — escalation matrix, what we're not automating |
| 2 | The Bones | done | `decisions/002-coordinator-specialist-split.md` — architecture ADR + agent loop diagram |
| 3 | The Tools | done | 5 tools in `/tools`, each with boundary docstrings + structured error returns |
| 4 | The Triage | done | Coordinator + triage specialist + validation-retry loop + structlog |
| 5 | The Brake | partial | Escalation rules are deterministic + documented; PreToolUse hook not wired yet |
| 6 | The Attack | done | 5 adversarial cases in `data/sample_tickets.json` (injection, buried legal, inflated urgency) |
| 7 | The Scorecard | done | `evals/harness.py` — accuracy, precision/queue, escalation rate, adversarial-pass, false-confidence |
| 8 | The Loop | skipped | Stretch goal — would close the human-override → few-shot example loop |

## Key Decisions

- **Coordinator + specialist split** — specialists are isolated; context is always passed explicitly.
  See [decisions/002-coordinator-specialist-split.md](decisions/002-coordinator-specialist-split.md)
- **Deterministic escalation, not probabilistic** — six explicit trigger codes fire before any LLM call.
  See [decisions/001-mandate.md](decisions/001-mandate.md)
- **Structured error returns in every tool** — `{"isError": true, "code": "...", "guidance": "..."}` so
  the agent can recover without parsing strings.
  See [decisions/003-tool-design.md](decisions/003-tool-design.md)
- **Max 5 tools per specialist** — tool-selection reliability drops beyond that; enforced as a hard rule
  in CLAUDE.md.

## How to Run It

```bash
# 1. Clone and set up
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env

pip install -r requirements.txt

# 2. Run the coordinator on all sample tickets
python agents/coordinator.py --ticket data/sample_tickets.json

# 3. Run on a single ticket
python agents/coordinator.py --ticket data/sample_tickets.json --id TKT-001

# 4. Run the eval harness
python evals/harness.py

# 5. Adversarial cases only
python evals/harness.py --adversarial
```

No Docker required. Python 3.11+ and an Anthropic API key are the only dependencies.

## If We Had More Time

1. **Wire the PreToolUse hook** — block write tools on security queue + PII patterns at the SDK level,
   not just in the escalation check. This is the "hard stop" vs "slow stop" distinction from Challenge 5.
2. **The Loop (Challenge 8)** — capture human overrides as labeled examples; feed back into the eval
   set and as few-shot examples for the triage classifier.
3. **Real ServiceNow / AD integration** — swap the JSON mock data for real CMDB and directory lookups.
4. **Confidence calibration** — the current confidence score is self-reported by the LLM; we'd add
   post-hoc calibration against eval labels.
5. **Stratified sampling in evals** — current test set is small; would expand to 100+ tickets with
   even distribution across all six queues and all four priorities.

## How We Used Claude Code

- **CLAUDE.md first** — writing the architecture constraints into CLAUDE.md before any code meant every
  team member got consistent scaffolding without meetings.
- **Parallel scaffolding** — Claude generated all 5 tool stubs, Pydantic models, and specialist agents
  in a single session while the BA/PM were writing the Mandate doc.
- **Adversarial test design** — asked Claude to generate prompt-injection and buried-legal-exposure
  tickets; it caught the impersonation case (TKT-ADV-005) that we hadn't thought of.
- **ADR drafts** — Claude drafted the architecture ADRs from the CLAUDE.md conventions; the team
  reviewed and added the escalation matrix table.
- **Biggest time save** — the validation-retry loop and structured error return pattern took about
  10 minutes to implement correctly once Claude had the full context from CLAUDE.md.
