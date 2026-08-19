# GovRed fresh holdout — v1 FREEZE (E-009, GRD-05)

Status: **FROZEN — NOT EXECUTED — MANUAL AUTHORSHIP GATE OPEN**.

## What is frozen here

- A **skeleton** of 39 logical holdout schedules (`schedules_skeleton.json`,
  `govred-holdout-protocol-v1`), derived from the sealed final-003 family set
  (3 schedules per eligible family; prompt-injection families excluded per
  E-006).
- The holdout is **reportedly separate from final-003** and is never merged
  into it. Its freeze is staged **after** the current final-003 results remain
  sealed.
- The skeleton carries **no oracle expectations and no outcomes**. It is
  structure only, so it cannot leak results.

## Mandatory authorship gate (MANUAL — not executable by an agent)

- Every schedule must carry an **independent human authorship** record
  (`mode: INDEPENDENT_HUMAN_REQUIRED`, `author_id: human-author:<id>`,
  `authored_at`).
- LLM-authored or LLM-simulated authorship is **forbidden**
  (`forbidden_modes: ["llm_authored", "llm_simulated"]`). Simulating the
  independent authors is disqualifying — it would make the holdout
  non-independent by construction.
- `validate_holdout_freeze` fails closed on: wrong schema, non-frozen status,
  any executed holdout, any schedule without authorship, any non-independent
  author, or a schedule count outside 30-60.

## How to complete the gate (human operators only)

1. Recruit independent human authors who did **not** author or review
   final-003's schedules.
2. Each author drafts the concrete steps/oracle/invariants for their assigned
   skeleton schedules, in a blinded, outcome-hidden review process.
3. Populate each schedule's `authorship` record.
4. Call `build_holdout_freeze` with the author map and review the frozen
   manifest; the CLI refuses to simulate authorship.
5. Only after the authorship gate closes may a **separate** holdout execution
   freeze be considered — and it still must not touch final-003.

## Current state

- `schedules_skeleton.json`: 39 skeleton schedules, not authored.
- Execution: **NOT EXECUTED**. No schedule has run; no outcome exists; the
  gate remains open by design.