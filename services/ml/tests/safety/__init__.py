"""Shared safety-guardrail test support for Epic 11 (RAG knowledge pipeline).

This package hosts the *medical-safety invariant* test harness for the RAG
knowledge-pipeline overhaul. The RAG changes are rolled out behind a family of
``RAG_*`` persistent feature flags (see ``clara_ml.config.Settings``). Epic 11
locks the guarantee that **none** of those flags can change a medical-safety
guardrail decision.

Modules:

- ``fixtures``  — reusable, import-friendly fixtures (roles, consent state,
  cookie-vs-bearer auth markers, emergency keywords vi/en, CRITICAL-claim
  payloads, DDI payloads, openFDA severity windows). These are consumed by the
  golden-output harness (task 11.1) *and* by the Epic 11 property tests
  (tasks 11.2-11.6).
- ``harness``   — the flag-toggling + decision-capture helpers used to prove
  flag-OFF (legacy) and flag-ON (persistent RAG enabled) produce identical
  guardrail decisions.

Only end-user-facing copy in the product is Vietnamese; this test code and its
identifiers are intentionally English.
"""
