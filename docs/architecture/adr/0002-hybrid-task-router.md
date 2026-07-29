# ADR 0002: Hybrid task and risk router

Status: accepted for PR-04–06 implementation.

The deterministic router remains the emergency/safety floor and fallback. A typed
contract router adds Vietnamese normalization, optional classifier/generative
analysis and LLM planning only for permitted complex tasks. When layers disagree,
policy chooses the safer route. Models cannot decide consent, RBAC, LifeMap
confirmation, dosage, or final DDI safety.

Rollback: select the deterministic contract through a feature flag; shadow
metadata contains only coarse, non-PII routing information.

Implementation note (2026-07-30): `clara_ml.model_router` now provides the
closed Pydantic `TaskRoute` contract and a shadow adapter over the existing
deterministic route plus closed-schema semantic safety signal. It is integrated
into routed chat as metadata-only shadow output. It cannot lower a route's risk,
does not publish confidence/reasons, and does not alter the active emergency,
legal, consent, RBAC, DrugBank or LifeMap decision path. An evaluated encoder
SLM and a generative SLM remain separate future model integrations, not claims
made by this adapter.
