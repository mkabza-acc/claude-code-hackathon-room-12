# ADR-002: Coordinator + Specialist Architecture

**Status:** Accepted
**Date:** 2026-04-24
**Authors:** Lukasz (Dev), Mateusz (Dev)

---

## Decision

Use a two-level agent architecture: a **coordinator** that handles intake, enrichment, and routing, and **specialist subagents** (triage, resolver) that handle classification and resolution. Specialists are called as isolated functions — they receive only what they need, not the coordinator's full context.

---

## Context Isolation Rule

Task subagents in the Claude Agent SDK do NOT inherit the coordinator's context. Every specialist call must include all information it needs to operate, passed explicitly in the prompt. The coordinator never assumes a specialist "knows" the ticket content or the user context.

What gets passed to **triage_agent**:
- ticket_id, subject, body, requestor name/email/title, channel

What gets passed to **resolver_agent**:
- All of the above, PLUS the TriageResult (queue, priority, reasoning)

The resolver needs triage output to decide whether auto-resolution applies. This is the only context that crosses the boundary.

---

## Agent Loop and stop_reason Handling

```
Ticket arrives
    │
    ▼
[Coordinator]
    │── get_user_context(email)       ← enrich before triage
    │── run_triage(ticket)            ← specialist call
    │       └── validation-retry loop (max 3)
    │── _check_escalation(...)        ← deterministic rules, no LLM
    │── create_ticket(...)            ← write to store
    │── run_resolver(ticket, triage)  ← specialist call (if not escalated)
    │── resolve_ticket / escalate_to_human
    └── CoordinatorOutput
```

The coordinator loop does not use `stop_reason` in the Claude SDK sense — it is orchestrated Python code, not an agentic loop. The specialists use `stop_reason: end_turn` as the normal exit. If a specialist returns `stop_reason: max_tokens`, the coordinator treats the output as unparseable and increments the retry counter.

---

## Why Not One Big Agent?

| Concern | Single agent | Coordinator + specialists |
|---|---|---|
| Tool count | Grows unbounded | Capped at 5 per specialist |
| Context window | Accumulates all intermediate steps | Each specialist gets only what it needs |
| Reliability | Tool selection degrades >5 tools | Stays reliable at small tool sets |
| Auditability | Hard to replay a single long trace | Each specialist call is independently replayable |

---

## Tool Assignments

| Specialist | Tools |
|---|---|
| triage_agent | lookup_knowledge, get_user_context (read-only; enriches classification) |
| resolver_agent | lookup_knowledge, resolve_ticket (reads KB, writes resolution) |
| coordinator (orchestration only) | get_user_context, create_ticket, escalate_to_human |

Max 5 tools per specialist is a hard constraint per CLAUDE.md. Do not exceed it without an ADR.
