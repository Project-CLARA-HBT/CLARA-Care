# ADR 0002: Hybrid task and risk router

Status: accepted for PR-04–06 implementation.

The deterministic router remains the emergency/safety floor and fallback. A typed
contract router adds Vietnamese normalization, optional classifier/generative
analysis and LLM planning only for permitted complex tasks. When layers disagree,
policy chooses the safer route. Models cannot decide consent, RBAC, LifeMap
confirmation, dosage, or final DDI safety.

Rollback: select the deterministic contract through a feature flag; shadow
metadata contains only coarse, non-PII routing information.
