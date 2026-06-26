"""Role-gated research telemetry sanitizer + PII allow-list serializer.

This module implements the API side of Requirement 3 (Role-Gated Research
Telemetry) and the telemetry half of Requirement 15.4 (PII-safe personalization).

``sanitize_telemetry(payload, *, role)`` produces up to two views of a raw
research telemetry payload:

- A sanitized progress **summary** (returned for every *valid* role) whose stage
  labels are drawn **only** from :data:`FLOW_STAGE_ALIAS_MAP`. Internal pipeline
  labels such as ``"RAG mode"`` and ``"retrieval"`` are never exposed
  (Requirements 3.2, 3.5).
- A **detailed** telemetry rail, included **iff** the role is ``admin``
  (Requirements 3.1, 3.3). The detailed rail is passed through
  :func:`strip_pii`, a recursive scrubber that removes PHR / medicine-cabinet
  PII so no personal data reaches any client (Requirements 3.4, 15.4).

Fail-closed semantics (Requirement 3.6 / 13.4 / 19.4): if the role cannot be
evaluated — it is missing, not a string, or not one of the known roles — **no**
telemetry is exposed at all (an empty mapping is returned).

The ``FLOW_STAGE_ALIAS_MAP`` here mirrors the canonical map in
``apps/web/lib/research.ts`` so the API and the web surface agree on the public,
sanitized stage vocabulary.
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Valid roles (mirrors clara_api.schemas.Role). A payload is only ever surfaced
# for one of these; anything else is treated as "cannot be evaluated".
# ---------------------------------------------------------------------------
VALID_ROLES: frozenset[str] = frozenset({"normal", "researcher", "doctor", "admin"})

# ---------------------------------------------------------------------------
# Sanitized stage vocabulary. Mirror of FLOW_STAGE_ALIAS_MAP in
# apps/web/lib/research.ts. Maps a raw stage/label key -> (stage_id, label).
# Only labels in this map's value set are ever emitted in a sanitized summary.
# ---------------------------------------------------------------------------
FLOW_STAGE_ALIAS_MAP: dict[str, tuple[str, str]] = {
    "input_gateway": ("input_gateway", "Input Gateway"),
    "dispatch_ml": ("input_gateway", "Input Gateway"),
    "session_guard": ("session_guard", "Session Guard"),
    "safety_ingress": ("safety_ingress", "Safety Ingress"),
    "legal_guard": ("legal_guard", "Legal Hard Guard"),
    "legal_hard_guard": ("legal_guard", "Legal Hard Guard"),
    "role_router": ("role_router", "Role Router"),
    "intent_router": ("intent_router", "Intent Router"),
    "query_canonicalizer": ("query_canonicalizer", "Query Canonicalizer"),
    "query_canonicalization": ("query_canonicalizer", "Query Canonicalizer"),
    "query_rewrite": ("query_canonicalizer", "Query Canonicalizer"),
    "query_decomposition": ("query_decomposition", "Query Decomposition"),
    "query_plan": ("planner", "Research Planner"),
    "planner": ("planner", "Research Planner"),
    "planner_v1": ("planner", "Research Planner"),
    "retrieval_v2": ("retrieval_orchestrator", "Retrieval Orchestrator"),
    "collect_evidence": ("retrieval_orchestrator", "Retrieval Orchestrator"),
    "source_attempts": ("retrieval_orchestrator", "Retrieval Orchestrator"),
    "retrieval_orchestrator": ("retrieval_orchestrator", "Retrieval Orchestrator"),
    "deep_research": ("deep_research", "Deep Research Loop"),
    "deep_retrieval_pass": ("deep_research", "Deep Research Loop"),
    "deep_beta": ("deep_beta_router", "Deep Beta Router"),
    "deep_beta_router": ("deep_beta_router", "Deep Beta Router"),
    "deep_beta_gate": ("deep_beta_router", "Deep Beta Router"),
    "deep_beta_planner": ("deep_beta_router", "Deep Beta Router"),
    "deep_beta_scope": ("deep_beta_router", "Deep Beta Scope Lock"),
    "deep_beta_loop": ("deep_beta_hypothesis", "Deep Beta Hypothesis Graph"),
    "beta_hypothesis_graph": ("deep_beta_hypothesis", "Deep Beta Hypothesis Graph"),
    "hypothesis_graph": ("deep_beta_hypothesis", "Deep Beta Hypothesis Graph"),
    "deep_beta_hypothesis": ("deep_beta_hypothesis", "Deep Beta Hypothesis Graph"),
    "deep_beta_hypothesis_map": ("deep_beta_hypothesis", "Deep Beta Hypothesis Map"),
    "deep_beta_debate": ("deep_beta_critic", "Deep Beta Critic Loop"),
    "cross_source_debate": ("deep_beta_critic", "Deep Beta Critic Loop"),
    "debate_refiner": ("deep_beta_critic", "Deep Beta Critic Loop"),
    "uncertainty_probe": ("deep_beta_critic", "Deep Beta Critic Loop"),
    "deep_beta_critic": ("deep_beta_critic", "Deep Beta Critic Loop"),
    "deep_beta_retrieval_budget": ("deep_beta_critic", "Deep Beta Retrieval Budget"),
    "deep_beta_consensus": ("deep_beta_consensus", "Deep Beta Consensus"),
    "consensus_builder": ("deep_beta_consensus", "Deep Beta Consensus"),
    "evidence_consensus": ("deep_beta_consensus", "Deep Beta Consensus"),
    "deep_beta_multi_pass_retrieval": ("deep_beta_consensus", "Deep Beta Multi-pass Retrieval"),
    "deep_beta_retrieval_pass": ("deep_beta_consensus", "Deep Beta Retrieval Pass"),
    "deep_beta_parallel_reasoning": ("deep_beta_reasoning", "Deep Beta Parallel Reasoning"),
    "deep_beta_evidence_audit": ("deep_beta_reasoning", "Deep Beta Evidence Audit"),
    "deep_beta_claim_graph": ("deep_beta_reasoning", "Deep Beta Claim Graph"),
    "deep_beta_gap_fill": ("deep_beta_reasoning", "Deep Beta Gap Fill"),
    "deep_beta_llm_gap_analyzer": ("deep_beta_reasoning", "Deep Beta Evidence Audit"),
    "deep_beta_llm_contradiction_hunter": ("deep_beta_reasoning", "Deep Beta Claim Graph"),
    "deep_beta_llm_risk_calibrator": ("deep_beta_reasoning", "Deep Beta Gap Fill"),
    "deep_beta_chain_synthesis": ("synthesis", "Deep Beta Chain Synthesis"),
    "deep_beta_report_synthesis": ("synthesis", "Deep Beta Report Synthesis"),
    "deep_report_synthesis": ("synthesis", "Deep Report Synthesis"),
    "deep_beta_quality_gate": ("verification", "Deep Beta Quality Gate"),
    "deep_beta_chain_verification": ("verification", "Deep Beta Chain Verification"),
    "llm_query_planner": ("planner", "LLM Query Planner"),
    "retrieval_internal": ("retrieval_internal", "Internal Corpus"),
    "internal_retrieval": ("retrieval_internal", "Internal Corpus"),
    "retrieval_scientific": ("retrieval_scientific", "Scientific Retrieval"),
    "external_scientific_retrieval": ("retrieval_scientific", "Scientific Retrieval"),
    "retrieval_web": ("retrieval_web", "Web Retrieval"),
    "retrieval_file": ("retrieval_file", "File Retrieval"),
    "evidence_search": ("retrieval_orchestrator", "Retrieval Orchestrator"),
    "evidence_index": ("evidence_index", "Evidence Index + Rerank"),
    "graphrag_sidecar": ("evidence_index", "GraphRAG Sidecar"),
    "contradiction_miner": ("contradiction_miner", "Contradiction Miner"),
    "synthesis": ("synthesis", "Answer Synthesis"),
    "answer_synthesis": ("synthesis", "Answer Synthesis"),
    "llm_generation": ("synthesis", "LLM Generation"),
    "llm_generation_retry": ("synthesis", "LLM Generation Retry"),
    "rag_generation": ("synthesis", "Answer Synthesis"),
    "verification": ("verification", "FIDES Verification"),
    "safety_override": ("verification_matrix", "Safety Override"),
    "verifier_v1": ("verification", "FIDES Verification"),
    "verification_matrix": ("verification_matrix", "Claim Matrix"),
    "citation_selection": ("citation_selection", "Citation Selection"),
    "policy_gate": ("policy_gate", "Policy Gate"),
    "policy_action": ("policy_gate", "Policy Gate"),
    "deepseek_fallback": ("deepseek_fallback", "DeepSeek Fallback"),
    "fallback_response": ("deepseek_fallback", "DeepSeek Fallback"),
    "responder": ("responder", "Responder"),
    "final_response": ("responder", "Responder"),
    "evaluation_feedback": ("evaluation_feedback", "Eval + Feedback Loop"),
}

# The complete set of public stage labels. Nothing outside this set may ever be
# emitted in a sanitized summary (Requirement 3.2 / 3.5).
ALLOWED_STAGE_LABELS: frozenset[str] = frozenset(
    label for _stage_id, label in FLOW_STAGE_ALIAS_MAP.values()
)

# Bounded vocabulary of progress statuses. Anything else is normalized to
# "unknown" so a raw, possibly-internal status string can never leak.
_ALLOWED_STATUSES: frozenset[str] = frozenset(
    {
        "pending",
        "active",
        "running",
        "in_progress",
        "complete",
        "completed",
        "done",
        "error",
        "failed",
        "skipped",
    }
)

# ---------------------------------------------------------------------------
# PII scrubbing for the detailed (admin) rail. PHR / medicine-cabinet data only
# ever enters telemetry under these container/field key names (see
# ``_build_personal_context_payload`` in endpoints/research.py). Dropping the
# whole subtree guarantees none of its values survive (Requirements 3.4, 15.4).
# ---------------------------------------------------------------------------
_PII_KEY_DENYLIST: frozenset[str] = frozenset(
    {
        # PHR / personalization containers
        "phr",
        "personal",
        "personal_context",
        "personal_context_payload",
        "personalization",
        "patient",
        "profile",
        "profile_payload",
        "summary_markdown",
        # medicine cabinet
        "cabinet",
        "medicine_cabinet",
        "medicine_cabinet_items",
        "cabinet_items",
        # clinical PHR collections
        "allergies",
        "conditions",
        "diagnoses",
        "medications",
        "medication",
        "meds",
        "lab_results",
        "labs",
        "vitals",
        "immunizations",
        # direct identity fields
        "name",
        "full_name",
        "fullname",
        "first_name",
        "last_name",
        "given_name",
        "family_name",
        "dob",
        "date_of_birth",
        "birthdate",
        "birth_date",
        "age",
        "gender",
        "sex",
        "address",
        "phone",
        "telephone",
        "mobile",
        "email",
        "national_id",
        "citizen_id",
        "ssn",
        "mrn",
        "insurance",
        "contact",
    }
)

_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
# Long digit runs (phone / id numbers): 7+ consecutive digits.
_LONG_DIGITS_RE = re.compile(r"\d{7,}")


def _normalize_key(key: Any) -> str:
    return str(key).strip().lower()


def _value_has_pii_markers(value: str) -> bool:
    """Defense-in-depth: drop string values that look like an email or id/phone."""

    return bool(_EMAIL_RE.search(value) or _LONG_DIGITS_RE.search(value))


def strip_pii(value: Any) -> Any:
    """Recursively project a payload to a PII-free form.

    Drops any mapping key in :data:`_PII_KEY_DENYLIST` (along with its entire
    subtree) and any string value that carries an email / phone / id marker.
    Mappings and sequences are recursed into; scalars pass through unchanged.
    """

    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            if _normalize_key(raw_key) in _PII_KEY_DENYLIST:
                continue
            projected = strip_pii(raw_value)
            out[str(raw_key)] = projected
        return out
    if isinstance(value, (list, tuple)):
        return [strip_pii(item) for item in value]
    if isinstance(value, str):
        if _value_has_pii_markers(value):
            return ""
        return value
    return value


def _normalize_status(raw_status: Any) -> str:
    status = str(raw_status or "").strip().lower()
    if not status:
        return "pending"
    return status if status in _ALLOWED_STATUSES else "unknown"


def _resolve_stage(raw_stage: Any, raw_label: Any = None) -> tuple[str, str] | None:
    """Resolve a raw stage/label to its public ``(stage_id, label)`` via the alias
    map. Returns ``None`` when neither token is a known public stage so internal /
    unknown labels are never surfaced."""

    for candidate in (raw_stage, raw_label):
        if not isinstance(candidate, str):
            continue
        key = candidate.strip().lower().replace(" ", "_").replace("-", "_")
        if not key:
            continue
        mapped = FLOW_STAGE_ALIAS_MAP.get(key)
        if mapped is not None:
            return mapped
    return None


def _iter_stage_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Collect candidate stage records from the known telemetry locations."""

    records: list[dict[str, Any]] = []
    for container_key in ("flow_stages", "flow_events", "stages"):
        container = payload.get(container_key)
        if isinstance(container, list):
            records.extend(item for item in container if isinstance(item, dict))
    return records


def build_sanitized_summary(payload: Any) -> dict[str, Any]:
    """Build the everyone-visible progress summary.

    Stages are mapped through :data:`FLOW_STAGE_ALIAS_MAP`; only public labels are
    emitted, deduplicated by ``stage_id`` in first-seen order with the latest
    status retained. Stages that do not resolve to a public alias are dropped.
    """

    if not isinstance(payload, dict):
        return {"stages": [], "active_stage": ""}

    ordered_ids: list[str] = []
    by_id: dict[str, dict[str, Any]] = {}
    for record in _iter_stage_records(payload):
        resolved = _resolve_stage(
            record.get("stage") or record.get("id") or record.get("phase"),
            record.get("label"),
        )
        if resolved is None:
            continue
        stage_id, label = resolved
        status = _normalize_status(
            record.get("status") or record.get("state") or record.get("active_status")
        )
        if stage_id not in by_id:
            ordered_ids.append(stage_id)
            by_id[stage_id] = {"stage_id": stage_id, "label": label, "status": status}
        else:
            by_id[stage_id]["status"] = status

    active_resolved = _resolve_stage(payload.get("active_stage"))
    active_stage = active_resolved[0] if active_resolved is not None else ""

    return {"stages": [by_id[stage_id] for stage_id in ordered_ids], "active_stage": active_stage}


def sanitize_telemetry(payload: Any, *, role: Any) -> dict[str, Any]:
    """Role-gate and sanitize a raw research telemetry payload.

    Returns ``{}`` when the role cannot be evaluated (fail-closed). Otherwise
    returns ``{"summary": ...}`` for non-admin roles, and additionally
    ``{"detailed": ...}`` (PII-scrubbed) for ``admin``.
    """

    normalized_role = str(role).strip().lower() if isinstance(role, str) else ""
    if normalized_role not in VALID_ROLES:
        # Fail-closed: deny all telemetry when the role is unknown/unavailable.
        return {}

    summary = build_sanitized_summary(payload)
    if normalized_role == "admin":
        detailed = strip_pii(payload) if isinstance(payload, dict) else {}
        return {"summary": summary, "detailed": detailed}
    return {"summary": summary}
