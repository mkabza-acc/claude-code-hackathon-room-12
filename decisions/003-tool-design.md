# ADR-003: Tool Design Principles

**Status:** Accepted
**Date:** 2026-04-24
**Authors:** Lukasz (Dev), Mateusz (Dev)

---

## Decision

All tools follow four invariants. Deviation requires this ADR to be updated first.

### 1. Docstrings teach boundaries, not just capabilities

Every tool docstring includes:
- What the tool does
- What the tool does **NOT** do (explicit negative scope)
- Input format with types
- Edge cases and failure modes
- One example query with example output

Reason: The LLM uses the docstring to decide when to call a tool and when not to. Vague descriptions produce both over-use and under-use. The "does not" section is the most important part.

### 2. Structured error returns — no plain strings

All failure paths return:
```python
{"isError": True, "code": "ERROR_CODE", "guidance": "what the agent should try instead"}
```

The `guidance` field tells the agent its next move. The agent cannot parse a plain string error reliably — it may hallucinate a fix or retry incorrectly. Structured errors produce deterministic recovery behavior.

Error code vocabulary:
| Code | Meaning |
|---|---|
| `NOT_FOUND` | Record does not exist |
| `FORBIDDEN` | Operation not permitted for this ticket type |
| `DUPLICATE_*` | Write would overwrite existing record |
| `INVALID_FIELD` | Input value not in allowed set |
| `*_UNAVAILABLE` | External system offline |
| `*_CORRUPT` | Data malformed; escalate |

### 3. Tool count discipline

Each specialist has at most 5 tools. Beyond that, tool-selection reliability drops measurably. If a new tool is needed:
- Can it replace an existing tool?
- Can it be a parameter variant of an existing tool?
- Only add if neither option works, and update this ADR.

### 4. Write tools are blocked by the PreToolUse hook for high-risk patterns

The `create_ticket`, `resolve_ticket`, and `escalate_to_human` tools are write operations. The coordinator's `PreToolUse` hook inspects the arguments before execution and blocks if:
- Target queue is `security` and action is `resolve_ticket`
- Ticket `account_status` is `frozen` and action is any write
- Ticket body matches PII exfiltration patterns

This is a hard stop — the hook fires before the tool executes, not after.
