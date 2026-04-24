# ADR-004: PreToolUse Hook and Human Override Feedback Loop

**Status:** Accepted
**Date:** 2026-04-24
**Authors:** M.Ch (QA)

---

## Context

Two gaps remained after the initial build:

1. **Challenge 5 (The Brake):** Escalation rules in `coordinator.py` are soft stops — the agent checks rules and routes, but nothing prevents it from calling `resolve_ticket` on a security ticket if the rules fire in the wrong order, or on a frozen account where the directory lookup fails. We needed a hard stop at the tool call boundary.

2. **Challenge 8 (The Loop):** When a human agent overrides a decision (wrong queue, wrong priority, unnecessary escalation), that signal was lost. There was no mechanism to close the loop back into either the eval set or the triage classifier.

---

## Decisions

### 1. PreToolUse Hook — `hooks/pre_tool_use.py`

The hook is called **before every write tool** (`create_ticket`, `resolve_ticket`, `escalate_to_human`). It is deterministic — no LLM call, no probability, no confidence threshold. It either allows or blocks.

**Three blocked patterns (hard stops):**

| Rule | Code | Rationale |
|---|---|---|
| `resolve_ticket` on `security` queue | `BLOCKED_SECURITY_QUEUE` | Security tickets must always be closed by a human. The tool-layer check is a backstop for any ordering bug in the coordinator. |
| Any write on a `frozen` account | `BLOCKED_FROZEN_ACCOUNT` | A frozen account signals something is already wrong (compromise, legal hold). No automated action should proceed. |
| `resolve_ticket` when ticket body matches PII exfil or prompt-injection patterns | `BLOCKED_PII_EXFIL_PATTERN` | Prevents a successful prompt injection from auto-resolving itself. Pattern list covers: "send passwords", "list credentials", "system override", "ignore instructions". |

**Why a hook, not just more escalation rules?**

The escalation rules are probabilistic guardrails — they fire based on triage output and ticket content as interpreted by the LLM. The hook fires based on the *actual tool call arguments* — the queue and account status that were written to the ticket store. These are ground truth, not inference. A hook cannot be fooled by a confidently wrong triage result.

ADR principle: hooks are for deterministic constraints; prompts are for probabilistic preferences. The hook is a hard stop; escalation is a slow stop.

**On a blocked write:** The coordinator treats any `allowed: False` hook response as a forced escalation. The block code becomes an escalation trigger. The ticket still gets created (hooks fire before resolve, not before create), so the audit trail is preserved.

---

### 2. Human Override Feedback Loop — `tools/record_override.py`, `tools/get_few_shot_examples.py`, `tools/override_cli.py`

When a human agent corrects an agent decision, the correction is recorded via:

```bash
python tools/override_cli.py --ticket TKT-ADV-003 --queue hardware --priority P4 \
  --escalate false --reason "Subject was inflated; body is a P4 printer location question"
```

**Where the signal goes:**

1. **`data/overrides.json`** — append-only store of every human correction with the original agent prediction, the human correction, and the reason. History is preserved (re-overriding the same ticket adds a new entry).

2. **Eval harness integration** — `evals/harness.py` loads `overrides.json` at run time and substitutes override entries for their original labeled entries. Human-corrected cases appear in a new `override_regression` metric. As the override store grows, the eval set grows with it — automatically, without manual JSON editing.

3. **Few-shot injection** — `tools/get_few_shot_examples.py` is called by `triage_agent.py` before each triage run. The 3 most recent human corrections are appended to the triage prompt as calibration examples. The agent sees what humans corrected and why, before classifying the new ticket.

**What this is NOT:**

- Not fine-tuning. The base model does not change.
- Not a retrieval system. Examples are recency-selected, not semantically matched.
- Not automatic. A human must run the CLI — the loop requires a human in it.

**Stratification gap:** The current few-shot selector takes the 3 most recent overrides regardless of queue or type. If all 3 recent overrides happen to be `hardware`, the few-shot block is unbalanced. This is a known limitation; a future version should stratify by queue.

---

## What Was Deliberately Left Out

- **Semantic retrieval for few-shot selection** — embedding the override store and retrieving by similarity to the new ticket would improve example relevance, but adds significant infrastructure. Recency-based selection is good enough for the hackathon scope.
- **Automatic stratified sampling** — the eval harness does not yet guarantee even distribution across queues when overrides dominate one category.
- **Override notification to the queue** — `record_override` updates the store but does not re-route the ticket in the downstream system (there is none; the store is the system).

---

## Files Changed

| File | Change |
|---|---|
| `hooks/pre_tool_use.py` | New — deterministic PreToolUse gate |
| `agents/coordinator.py` | Wired hook before `create_ticket` and `resolve_ticket` calls |
| `tools/record_override.py` | New — records human corrections to override store |
| `tools/get_few_shot_examples.py` | New — formats recent overrides as few-shot prompt text |
| `tools/override_cli.py` | New — CLI for human agents to record and list overrides |
| `agents/specialists/triage_agent.py` | Injects few-shot examples from override store into triage prompt |
| `evals/harness.py` | Loads override entries into eval set; reports override regression metric |
| `decisions/004-hook-and-feedback-loop.md` | This document |
