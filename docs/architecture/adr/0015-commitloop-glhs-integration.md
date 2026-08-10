# ADR 0015: CommitLoop uses the canonical GLHS ledger

## Context

CommitLoop needs durable, bitemporal clinical commitments and deterministic
reconciliation of later evidence. Creating a separate patient state database
would bypass existing GST concurrency, profile scope, consent, provenance and
audit guarantees.

## Decision

Add normalized commitment/version/proposal/transition records that reference
the existing `phr_profiles`, `glhs_evidence`, `glhs_state_versions`, and GLHS
policy/consent metadata. Commitment transitions advance the same profile state
counter through API-owned gateway code. Predicate definitions are a bounded,
versioned JSON DSL interpreted by deterministic code only.

## Consequences

- Model output is persisted only as a candidate proposal and cannot activate
  or confirm a commitment.
- THSS snapshots retain exact commitment inputs, exclusions, and sufficiency.
- Evaluator packets and construction gold remain derived artifacts, isolated
  from End_User and canonical API paths.
- A later migration can be downgraded without altering existing GLHS records.
