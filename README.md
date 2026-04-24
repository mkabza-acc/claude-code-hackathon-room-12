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

**What runs:** coordinator pipeline end-to-end, triage + resolver specialists, all 5 core tools with mock data,
PreToolUse hook (blocks write tools on security queue, frozen accounts, and PII exfiltration patterns),
human-override CLI with few-shot feedback loop, eval harness with metrics output.

**What's mocked:** user directory and knowledge base are JSON files (no real AD/ServiceNow).

## Challenges Attempted

| # | Challenge | Status | Notes |
|---|---|---|---|
| 1 | The Mandate | done | `decisions/001-mandate.md` — escalation matrix, what we're not automating |
| 2 | The Bones | done | `decisions/002-coordinator-specialist-split.md` — architecture ADR + agent loop diagram |
| 3 | The Tools | done | 5 tools in `/tools`, each with boundary docstrings + structured error returns |
| 4 | The Triage | done | Coordinator + triage specialist + validation-retry loop + structlog |
| 5 | The Brake | done | 6 deterministic escalation triggers + `hooks/pre_tool_use.py` wired into coordinator (hard-stops on security queue, frozen accounts, PII exfil patterns) |
| 6 | The Attack | done | 5 adversarial cases in `data/sample_tickets.json` (injection, buried legal, inflated urgency) |
| 7 | The Scorecard | done | `evals/harness.py` — accuracy, precision/queue, escalation rate, adversarial-pass, false-confidence + override regression |
| 8 | The Loop | done | `tools/override_cli.py` records human corrections → `data/overrides.json` → injected as few-shot examples into next triage run via `tools/get_few_shot_examples.py` |

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
- **PreToolUse hook as hard stop** — `hooks/pre_tool_use.py` blocks write tools deterministically before
  the agent can act; a hook denial forces escalation. Complements the soft escalation-check in the coordinator.
  See [decisions/004-hook-and-feedback-loop.md](decisions/004-hook-and-feedback-loop.md)
- **Human-override feedback loop** — `tools/override_cli.py` records human corrections; `tools/get_few_shot_examples.py`
  injects the 3 most recent overrides into the triage prompt on the next run; `evals/harness.py` tracks `override_regression`.

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

1. **Real ServiceNow / AD integration** — swap the JSON mock data for real CMDB and directory lookups.
   The tool interfaces are already designed for this; it's a config change, not a rewrite.
2. **Confidence calibration** — the current confidence score is self-reported by the LLM; we'd add
   post-hoc calibration against eval labels to make the 0.70 threshold meaningful.
3. **Stratified sampling in evals** — current test set is small; would expand to 100+ tickets with
   even distribution across all six queues and all four priorities.
4. **Semantic few-shot retrieval** — current override injection is recency-based (last 3); a vector
   similarity search would surface more relevant past corrections for edge cases.
5. **Automated override ingestion** — currently overrides are recorded via CLI; a Slack bot or
   ServiceNow webhook would close the loop without manual human steps.

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
