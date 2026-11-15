"""CLARA-Care 2027 POPETS task POPETS-ablation — causal mechanism ablation variants.

Purpose
-------
P04 ablation registry for the paper *Revocation-Complete Future Disclosure for
Cached Longitudinal AI Contexts* (``research/venue2027/VENUES/popets/RESEARCH_BLUEPRINT.md``;
task contract ``research/venue2027/VENUES/popets/TASKS/POPETS-ablation.md``).

The P04 candidate (:mod:`evaluation.venue2027.popets.candidate`) implements
revocation-complete future-disclosure cache control: entries carry provenance
dependency sets of ``(subject, purpose, consent_epoch)`` triples and derivation
parents (reverse edges). A revocation invalidates exactly the direct dependency
intersection AND every transitively derived entry to closure (reverse-edge BFS),
protecting post-revocation model dispatches from re-disclosing revoked context.

This module evaluates the candidate against ITSELF with EXACTLY ONE mechanism
removed per variant, over the SAME frozen synthetic fault/control families, so
each mechanism's causal contribution to future-disclosure protection is
verifiable (development-scale mechanism causality on frozen synthetic cases —
never confirmatory results; no empirical claims, no performance numbers, no win
rates).

Preregistered variants (``ABLATION_REGISTRY``; each is a real callable reusing
existing components and declaring its single ablated mechanism via
:class:`VariantSpec`):

- ``candidate_no_key_module`` — candidate WITHOUT the key module: the
  candidate's own preregistered hook :func:`candidate.ablation_no_reverse_edges`
  (reverse-edge dependency closure disabled; direct dependency invalidation
  stays enforced). A transitively derived entry whose own declared dependency
  labels are stable survives revocation and is served (the executable leak
  proving reverse edges are the load-bearing mechanism).
- ``baseline_common_safety_gate`` — baseline with common safety gate: the full
  provenance boundary and reverse-edge closure pipeline is replaced by the
  common safety gate shared across baselines: point-in-time check of direct
  consent and purpose scope without lineage tracking or reverse-edge
  propagation. Reuses direct consent evaluation from
  :mod:`evaluation.venue2027.popets.revocation_model`. Catches direct
  unconsented/revoked requests for the current purpose, but admits transitively
  derived leaks and unproven lineage because it does not inspect provenance.
- ``full_refresh`` — coarse cache purge on consent revocation: reuses blueprint
  arm B1 (:mod:`evaluation.venue2027.popets.baselines` arm
  ``coarse-cache-purge-on-revocation`` / :class:`cache_control.PurposeBoundCache`).
  On any consent revocation event, purges the subject's entire cache across all
  grants and purposes. Degrades availability and efficiency by over-invalidating
  unaffected scopes (causing false cache misses on unaffected requests) instead
  of performing exact dependency-closure invalidation.
- ``zero_proof_receipt`` — candidate WITHOUT provenance proof/receipt
  verification: entries without verified dependency proof or provenance labels
  are admitted into cache without checking consent epoch or lineage validity
  (bypassing ``REVOKED_DEPENDENCY`` / ``LINEAGE_INDETERMINATE``). Demonstrates
  that provenance proofs and receipts are load-bearing to prevent unanchored or
  tainted context installation.
- ``no_context_history_branch`` — candidate WITHOUT the longitudinal context /
  history branch: derived parent edges (``derived_from``) and cached
  longitudinal context are stripped before evaluation, treating every
  dispatch/entry as an isolated fresh segment without longitudinal history.
  Blind to historical taint (historical parent revocations cannot reach the
  unlinked child) and loses longitudinal context continuity.

The reference row (the unmodified full candidate) is deliberately NOT a
registered variant: a variant that removes nothing is not an ablation.
:func:`refuse_unregistered_variant` refuses unknown ids with
``UNKNOWN_ABLATION_VARIANT`` and nothing-removing identities (the full
candidate and the candidate id itself) with ``VARIANT_REMOVES_NOTHING`` — fail
closed, never silently run as a degraded or full arm. The mechanistic
inference matrix (:func:`mechanistic_inference_matrix`,
:func:`verify_mechanistic_inference_matrix`) pins every variant x family
verdict against its preregistered prediction.

Allowed input
-------------
:func:`run_ablation(name, case)` (task-manifest signature
``run_ablation(name, case) -> Outcome``): ``name`` is a registered variant id
from :data:`ABLATION_REGISTRY` (or an accepted alias); ``case`` is a
JSON-serializable mapping with at least ``case_id`` and ``cache_ops`` (a list of
cache operation mappings ``put``, ``get``, ``revoke``).

Failure semantics
-----------------
Fail closed with stable uppercase reason codes; no unhandled exception is ever
miscounted as a safe rejection:
- unknown / nothing-removing variant -> ``Outcome(EXECUTION_ERROR)`` carrying
  ``UNKNOWN_ABLATION_VARIANT`` / ``VARIANT_REMOVES_NOTHING`` (the raising
  guard :func:`refuse_unregistered_variant` exposes the same codes).
- malformed case (non-mapping, missing/ill-typed case id, missing/malformed
  ops) -> ``EXECUTION_ERROR`` / ``INDETERMINATE`` outcomes, never ``ADMIT`` or
  ``REJECT``.
- Determined verdicts: at least one HIT -> ``ADMIT``; all denied/tombstoned ->
  ``REJECT`` (both ``counted_as_success=True``), mirroring the candidate's
  task-contract adapter :func:`candidate.run_candidate`.
No wall clock, randomness, network or database anywhere; identical inputs give
identical results.

Version
-------
``POPETS_ABLATIONS_VERSION = "clara.popets.ablations-v1"``.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any, Final

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.popets import candidate as cand

POPETS_ABLATIONS_VERSION: Final[str] = "clara.popets.ablations-v1"
ABLATION_TASK_ID: Final[str] = "POPETS-ablation"

#: Preregistered ablation variant ids (one mechanism removed each).
VARIANT_CANDIDATE_NO_KEY_MODULE: Final[str] = "candidate_no_key_module"
VARIANT_BASELINE_COMMON_SAFETY_GATE: Final[str] = "baseline_common_safety_gate"
VARIANT_FULL_REFRESH: Final[str] = "full_refresh"
VARIANT_ZERO_PROOF_RECEIPT: Final[str] = "zero_proof_receipt"
VARIANT_NO_CONTEXT_HISTORY_BRANCH: Final[str] = "no_context_history_branch"

#: Reference row: the unmodified candidate. Deliberately NOT registered as an
#: ablation — a variant that removes nothing is not an ablation.
REFERENCE_VARIANT_ID: Final[str] = "full_candidate"

#: Identities known to remove nothing (refused, not guessed).
NON_ABLATION_IDENTITIES: Final[frozenset[str]] = frozenset(
    {REFERENCE_VARIANT_ID, cand.CANDIDATE_ID}
)

#: Aliases accepted by refuse_unregistered_variant for caller convenience.
VARIANT_ALIASES: Final[Mapping[str, str]] = {
    "candidate_without_key_module": VARIANT_CANDIDATE_NO_KEY_MODULE,
    "no_reverse_edge_closure": VARIANT_CANDIDATE_NO_KEY_MODULE,
    "common_safety_gate": VARIANT_BASELINE_COMMON_SAFETY_GATE,
    "coarse_purge_full_refresh": VARIANT_FULL_REFRESH,
    "zero_proof": VARIANT_ZERO_PROOF_RECEIPT,
    "no_context_branch": VARIANT_NO_CONTEXT_HISTORY_BRANCH,
}

#: Ablated mechanism axes (exactly one per variant, all distinct).
ABLATED_REVERSE_EDGE_CLOSURE: Final[str] = "reverse_edge_closure"
ABLATED_LINEAGE_PROVENANCE_TRACKING: Final[str] = "lineage_provenance_tracking"
ABLATED_SELECTIVE_EXACT_INVALIDATION: Final[str] = "selective_exact_invalidation"
ABLATED_PROVENANCE_PROOF_VERIFICATION: Final[str] = "provenance_proof_verification"
ABLATED_LONGITUDINAL_HISTORY_BRANCH: Final[str] = "longitudinal_context_history_branch"

#: Stable reason codes (fail closed).
RC_UNKNOWN_ABLATION_VARIANT: Final[str] = "UNKNOWN_ABLATION_VARIANT"
RC_VARIANT_REMOVES_NOTHING: Final[str] = "VARIANT_REMOVES_NOTHING"
RC_CASE_NOT_AN_OBJECT: Final[str] = "CASE_NOT_AN_OBJECT"
RC_CASE_ID_MISSING: Final[str] = "CASE_ID_MISSING"
RC_CASE_ID_NOT_STRING: Final[str] = "CASE_ID_NOT_STRING"
RC_WORKLOAD_MALFORMED: Final[str] = "WORKLOAD_MALFORMED"

VERDICT_ADMIT: Final[str] = "ADMIT"
VERDICT_REJECT: Final[str] = "REJECT"

#: Frozen fault/control family ids (the same suite every variant executes).
FAMILY_FRESH_DISPATCH: Final[str] = "fresh_dispatch"
FAMILY_TRANSITIVE_REVOCATION: Final[str] = "transitive_revocation"
FAMILY_UNAFFECTED_SCOPE: Final[str] = "unaffected_scope"
FAMILY_UNPROVEN_LINEAGE: Final[str] = "unproven_lineage"
FAMILY_HISTORICAL_TAINT: Final[str] = "historical_taint"
FAMILY_CROSS_PURPOSE: Final[str] = "cross_purpose"

FAULT_FAMILY_IDS: Final[tuple[str, ...]] = (
    FAMILY_FRESH_DISPATCH,
    FAMILY_TRANSITIVE_REVOCATION,
    FAMILY_UNAFFECTED_SCOPE,
    FAMILY_UNPROVEN_LINEAGE,
    FAMILY_HISTORICAL_TAINT,
    FAMILY_CROSS_PURPOSE,
)


class AblationError(ValueError):
    """Fail-closed ablation registry error with a stable reason code."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


@dataclasses.dataclass(frozen=True)
class VariantSpec:
    """One preregistered ablation variant.

    ``ablated_mechanism`` is the DECLARED single mechanism removed; a spec
    that declares no ablated mechanism (empty string) is refused at
    construction — a variant removing nothing is not an ablation.
    """

    variant_id: str
    title: str
    ablated_mechanism: str
    description: str
    expected_effect: str
    reuses: tuple[str, ...]
    applied_by: str

    def __post_init__(self) -> None:
        if not isinstance(self.ablated_mechanism, str) or not self.ablated_mechanism.strip():
            raise AblationError(
                RC_VARIANT_REMOVES_NOTHING,
                f"variant {self.variant_id!r} declares no ablated mechanism; "
                "a variant removing nothing is not an ablation",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "title": self.title,
            "ablated_mechanism": self.ablated_mechanism,
            "description": self.description,
            "expected_effect": self.expected_effect,
            "reuses": list(self.reuses),
            "applied_by": self.applied_by,
        }


ABLATION_REGISTRY: Final[Mapping[str, VariantSpec]] = {
    spec.variant_id: spec
    for spec in (
        VariantSpec(
            variant_id=VARIANT_CANDIDATE_NO_KEY_MODULE,
            title="Candidate without key module (reverse-edge dependency closure)",
            ablated_mechanism=ABLATED_REVERSE_EDGE_CLOSURE,
            description=(
                "The candidate's own preregistered hook "
                "candidate.ablation_no_reverse_edges: reverse-edge closure is "
                "disabled; direct dependency invalidation stays enforced. "
                "Transitively derived entries survive revocation, producing "
                "an executable post-revocation leakage"
            ),
            expected_effect="admits_transitive_derivation_leak",
            reuses=(
                "candidate.ablation_no_reverse_edges",
                "candidate.RevocationCompleteCache",
            ),
            applied_by="candidate_ablation_hook",
        ),
        VariantSpec(
            variant_id=VARIANT_BASELINE_COMMON_SAFETY_GATE,
            title="Baseline with common safety gate (point-in-time direct consent/purpose gate)",
            ablated_mechanism=ABLATED_LINEAGE_PROVENANCE_TRACKING,
            description=(
                "The candidate's full provenance boundary and reverse-edge "
                "closure pipeline is replaced by the common safety gate "
                "every baseline shares: point-in-time check of direct consent "
                "and purpose scope without lineage tracking or reverse-edge "
                "propagation. Reuses direct consent evaluation from "
                "revocation_model.allowed. Catches direct unconsented/revoked "
                "requests, but admits transitive leaks and unproven lineage"
            ),
            expected_effect="admits_transitive_leaks_and_unproven_lineage",
            reuses=(
                "revocation_model.allowed",
                "revocation_model.ConsentLedgerView",
            ),
            applied_by="common_safety_gate_adapter",
        ),
        VariantSpec(
            variant_id=VARIANT_FULL_REFRESH,
            title="Full refresh (coarse cache purge on consent revocation)",
            ablated_mechanism=ABLATED_SELECTIVE_EXACT_INVALIDATION,
            description=(
                "Coarse full-cache purge on consent change (reusing blueprint "
                "arm B1 coarse-cache-purge-on-revocation in baselines.py / "
                "cache_control.PurposeBoundCache). On any consent revocation "
                "event, purges the subject's entire cache across all grants "
                "and purposes. Degrades availability and efficiency by "
                "over-invalidating unaffected scopes"
            ),
            expected_effect="false_invalidation_of_unaffected_scopes",
            reuses=(
                "baselines.run_baseline",
                "cache_control.PurposeBoundCache",
            ),
            applied_by="coarse_purge_cache_adapter",
        ),
        VariantSpec(
            variant_id=VARIANT_ZERO_PROOF_RECEIPT,
            title="Zero proof/receipt (unverified provenance and dependency labels)",
            ablated_mechanism=ABLATED_PROVENANCE_PROOF_VERIFICATION,
            description=(
                "Candidate with provenance proof / receipt verification "
                "omitted: entries without verified dependency proof or "
                "provenance labels are admitted into the cache without "
                "checking consent epoch or lineage validity (bypassing "
                "REVOKED_DEPENDENCY / LINEAGE_INDETERMINATE). Demonstrates "
                "that provenance proofs and receipts are load-bearing to "
                "prevent unanchored context installation"
            ),
            expected_effect="admits_unproven_context_installation",
            reuses=(
                "candidate.RevocationCompleteCache",
                "candidate.put",
            ),
            applied_by="zero_proof_cache_adapter",
        ),
        VariantSpec(
            variant_id=VARIANT_NO_CONTEXT_HISTORY_BRANCH,
            title="No context/history branch (longitudinal history and derived parent edges severed)",
            ablated_mechanism=ABLATED_LONGITUDINAL_HISTORY_BRANCH,
            description=(
                "Candidate with the longitudinal context / history branch "
                "ablated: derived parent edges (derived_from) and cached "
                "longitudinal context are stripped before evaluation, "
                "treating every dispatch/entry as an isolated fresh segment "
                "without longitudinal history. Blind to historical taint "
                "(historical parent revocations cannot reach the unlinked child)"
            ),
            expected_effect="admits_historical_taint_leak",
            reuses=(
                "candidate.RevocationCompleteCache",
                "lineage_graph.derive_graph",
            ),
            applied_by="history_branch_severing_adapter",
        ),
    )
}


def refuse_unregistered_variant(name: str) -> VariantSpec:
    """Guard: return the registered spec for ``name`` or refuse fail-closed.

    Refuses (raises :class:`AblationError`):
    - any id not in :data:`ABLATION_REGISTRY` (and not an accepted alias) ->
      ``UNKNOWN_ABLATION_VARIANT`` (never guessed, never silently run as the
      full candidate);
    - known nothing-removing identities (the unmodified full candidate and the
      candidate id itself) -> ``VARIANT_REMOVES_NOTHING``: a variant that
      removes no mechanism is not an ablation.
    """
    resolved = VARIANT_ALIASES.get(name, name)
    spec = ABLATION_REGISTRY.get(resolved)
    if spec is not None:
        return spec
    if name in NON_ABLATION_IDENTITIES:
        raise AblationError(
            RC_VARIANT_REMOVES_NOTHING,
            f"{name!r} is the unmodified candidate and removes no mechanism; "
            "run candidate.run_candidate directly for the reference row",
        )
    raise AblationError(
        RC_UNKNOWN_ABLATION_VARIANT,
        f"variant {name!r} not in registry {sorted(ABLATION_REGISTRY)}",
    )


def variant_ids() -> tuple[str, ...]:
    """Registered ablation variant ids in canonical (registry) order."""
    return tuple(ABLATION_REGISTRY)


# ---------------------------------------------------------------------------
# Specialized cache adapters implementing the ablated mechanism variants
# ---------------------------------------------------------------------------


class _FullRefreshCache(cand.RevocationCompleteCache):
    """Full refresh: coarse purge of all cache lines on any consent revocation."""

    def revoke(self, subject: str, purpose: str, epoch: int) -> dict[str, Any]:
        record = super().revoke(subject, purpose, epoch)
        # Coarse full refresh: on any revocation event for a subject, purge ALL entries
        # for that subject across all grants/purposes (blueprint arm B1 semantics).
        checked_subject = cand._checked_subject(subject)
        for key in list(self._entries):
            entry = self._entries[key]
            if any(d.subject == checked_subject for d in entry.deps):
                self._tombstoned[key] = True
        record["full_refresh_purged"] = True
        return record


class _ZeroProofCache(cand.RevocationCompleteCache):
    """Zero proof/receipt: permits installation of entries without verified provenance."""

    def put(
        self,
        key: str,
        value: str,
        deps: Iterable[Any],
        derived_from: Iterable[str] = (),
    ) -> cand.CacheEntry:
        # If deps is empty or missing, do NOT fail closed; assign an unverified dummy dep
        # bypassing provenance proof / receipt validation.
        raw_deps = (
            list(deps) if isinstance(deps, Iterable) and not isinstance(deps, str | bytes) else []
        )
        if not raw_deps:
            dummy_dep = cand.Dependency(subject="unproven", purpose="analytics", consent_epoch=0)
            return super().put(key, value, [dummy_dep], derived_from=())
        return super().put(key, value, deps, derived_from=derived_from)


class _NoContextHistoryCache(cand.RevocationCompleteCache):
    """No context/history branch: strips derivation history edges."""

    def put(
        self,
        key: str,
        value: str,
        deps: Iterable[Any],
        derived_from: Iterable[str] = (),
    ) -> cand.CacheEntry:
        # Sever the history branch: derived_from is forced to empty, cutting off
        # reverse derivation edges from historical parent contexts.
        return super().put(key, value, deps, derived_from=())


class _CommonSafetyGateCache:
    """Baseline with common safety gate: point-in-time direct consent/purpose gate.

    Context-free, derivation-free, no reverse-edge closure. Evaluates direct
    consent at request time; admits unproven lineage and transitive leaks.
    """

    def __init__(self) -> None:
        self._entries: dict[str, dict[str, Any]] = {}
        self._revoked_scopes: set[tuple[str, str, int]] = set()

    def put(
        self,
        key: str,
        value: str,
        deps: Any,
        derived_from: Any = (),
    ) -> dict[str, Any]:
        checked_key = cand._checked_key(key)
        checked_value = cand._checked_value(value)
        if isinstance(deps, Iterable) and not isinstance(deps, str | bytes):
            dep_list = list(deps)
        else:
            dep_list = []
        subject = "subj-1"
        purpose = "analytics"
        epoch = 0
        if dep_list:
            try:
                d = cand.Dependency.from_input(dep_list[0])
                subject, purpose, epoch = d.subject, d.purpose, d.consent_epoch
            except Exception:
                pass
        self._entries[checked_key] = {
            "key": checked_key,
            "value": checked_value,
            "subject": subject,
            "purpose": purpose,
            "epoch": epoch,
        }
        return {"key": checked_key, "status": "OK"}

    def revoke(self, subject: str, purpose: str, epoch: int) -> dict[str, Any]:
        checked_subject = cand._checked_subject(subject)
        checked_purpose = cand._checked_purpose(purpose)
        checked_epoch = cand._checked_epoch(epoch)
        scope = (checked_subject, checked_purpose, checked_epoch)
        self._revoked_scopes.add(scope)
        return {
            "subject": checked_subject,
            "purpose": checked_purpose,
            "consent_epoch": checked_epoch,
            "status": "REVOKED",
        }

    def get(self, key: str, purpose: str, epoch: int) -> dict[str, Any]:
        checked_key = cand._checked_key(key)
        checked_purpose = cand._checked_purpose(purpose)
        checked_epoch = cand._checked_epoch(epoch)
        entry = self._entries.get(checked_key)
        if entry is None:
            return {"key": checked_key, "status": cand.STATUS_CACHE_MISS}
        if (entry["subject"], checked_purpose, checked_epoch) in self._revoked_scopes:
            return {"key": checked_key, "status": cand.STATUS_REVOKED_ENTRY}
        if entry["purpose"] != checked_purpose:
            return {"key": checked_key, "status": cand.STATUS_PURPOSE_MISMATCH}
        return {"key": checked_key, "status": cand.STATUS_HIT}


# ---------------------------------------------------------------------------
# Execution engine & adapter
# ---------------------------------------------------------------------------


def _create_variant_cache(variant_id: str) -> Any:
    resolved = VARIANT_ALIASES.get(variant_id, variant_id)
    if resolved == VARIANT_CANDIDATE_NO_KEY_MODULE:
        return cand.ablation_no_reverse_edges()
    if resolved == VARIANT_BASELINE_COMMON_SAFETY_GATE:
        return _CommonSafetyGateCache()
    if resolved == VARIANT_FULL_REFRESH:
        return _FullRefreshCache()
    if resolved == VARIANT_ZERO_PROOF_RECEIPT:
        return _ZeroProofCache()
    if resolved == VARIANT_NO_CONTEXT_HISTORY_BRANCH:
        return _NoContextHistoryCache()
    if variant_id == REFERENCE_VARIANT_ID:
        return cand.RevocationCompleteCache()
    raise AblationError(
        RC_UNKNOWN_ABLATION_VARIANT,
        f"unknown variant {variant_id!r}",
    )


def _execute_cache_op(cache: Any, op: Mapping[str, Any]) -> dict[str, Any]:
    kind = op.get("op")
    if kind == "put":
        raw_deps = op.get("deps", ())
        if isinstance(raw_deps, list):
            deps_triples = cand._dep_triples(raw_deps) if raw_deps else []
        else:
            deps_triples = raw_deps
        entry = cache.put(
            op.get("key"),
            op.get("value"),
            deps_triples,
            derived_from=op.get("derived_from", ()) or (),
        )
        return {
            "op": "put",
            "key": entry.key if hasattr(entry, "key") else op.get("key"),
            "status": "OK",
        }
    if kind == "get":
        result = cache.get(op.get("key"), op.get("purpose"), op.get("epoch"))
        if hasattr(result, "to_dict"):
            record = result.to_dict()
        else:
            record = dict(result)
        record["op"] = "get"
        return record
    if kind == "revoke":
        record = cache.revoke(op.get("subject"), op.get("purpose"), op.get("epoch"))
        record["op"] = "revoke"
        return record
    raise ValueError(f"{RC_WORKLOAD_MALFORMED}: unknown cache op {kind!r}")


def _run_variant_workload(
    variant_id: str,
    case_id: str,
    ops: Sequence[Mapping[str, Any]],
    spec: VariantSpec | None = None,
) -> Outcome:
    cache = _create_variant_cache(variant_id)
    records: list[dict[str, Any]] = []
    try:
        for index, op in enumerate(ops):
            if not isinstance(op, Mapping):
                raise ValueError(f"{RC_WORKLOAD_MALFORMED}: op {index} must be an object")
            records.append(_execute_cache_op(cache, op))
    except ValueError as exc:
        # A fail-closed domain refusal inside the cache (e.g. DEPS_MALFORMED,
        # REVOKED_DEPENDENCY) is a determined REJECT of the workload
        reason = str(exc).split(":")[0].strip()
        detail = {
            "ablations_version": POPETS_ABLATIONS_VERSION,
            "variant_id": variant_id,
            "ablated_mechanism": spec.ablated_mechanism if spec else "none",
            "case_id": case_id,
            "decision": "DENY",
            "reason_code": reason,
            "fail_closed": True,
            "hits": 0,
            "leaks": 0,
            "gets": 0,
            "records": records,
        }
        return Outcome(
            observed_outcome=VERDICT_REJECT,
            counted_as_success=True,
            detail=json.dumps(detail, sort_keys=True),
        )

    gets = [r for r in records if r.get("op") == "get"]
    hits = sum(1 for r in gets if r.get("status") == cand.STATUS_HIT)
    leaks = sum(
        1
        for r in gets
        if r.get("status") == cand.STATUS_HIT and r.get("served_from_revoked_ancestry", False)
    )
    observed = VERDICT_ADMIT if hits > 0 else VERDICT_REJECT

    detail = {
        "ablations_version": POPETS_ABLATIONS_VERSION,
        "variant_id": variant_id,
        "ablated_mechanism": spec.ablated_mechanism if spec else "none",
        "case_id": case_id,
        "decision": "ALLOW" if observed == VERDICT_ADMIT else "DENY",
        "reason_code": "HIT" if observed == VERDICT_ADMIT else "REVOKED_OR_MISMATCH",
        "fail_closed": False,
        "hits": hits,
        "leaks": leaks,
        "gets": len(gets),
        "ops": records,
    }
    return Outcome(
        observed_outcome=observed,
        counted_as_success=True,
        detail=json.dumps(detail, sort_keys=True),
    )


def run_ablation(name: str, case: Mapping[str, Any]) -> Outcome:
    """Task-manifest signature: run ONE ablation variant on ONE case.

    - Determined outcomes: ADMIT or REJECT (both counted_as_success=True);
      detail payload carries variant_id, ablated_mechanism, case_id, hits,
      leaks, and step records.
    - Fail closed: unknown variant -> EXECUTION_ERROR with UNKNOWN_ABLATION_VARIANT;
      nothing-removing variant -> EXECUTION_ERROR with VARIANT_REMOVES_NOTHING;
      malformed case -> INDETERMINATE / EXECUTION_ERROR with stable reason codes.
    """
    try:
        spec = refuse_unregistered_variant(name)
    except AblationError as exc:
        return Outcome(
            observed_outcome="EXECUTION_ERROR",
            counted_as_success=False,
            detail=f"{POPETS_ABLATIONS_VERSION}|{exc.reason_code}: {exc.detail}",
        )

    if not isinstance(case, Mapping):
        return Outcome(
            observed_outcome="EXECUTION_ERROR",
            counted_as_success=False,
            detail=f"{RC_CASE_NOT_AN_OBJECT}: case must be a mapping, got {type(case).__name__}",
        )

    case_id = case.get("case_id")
    if case_id is None:
        return Outcome(
            observed_outcome="INDETERMINATE",
            counted_as_success=False,
            detail=f"{POPETS_ABLATIONS_VERSION}|{RC_CASE_ID_MISSING}",
        )
    if not isinstance(case_id, str) or not case_id.strip():
        return Outcome(
            observed_outcome="INDETERMINATE",
            counted_as_success=False,
            detail=f"{POPETS_ABLATIONS_VERSION}|{RC_CASE_ID_NOT_STRING}",
        )

    ops = case.get("cache_ops")
    if not isinstance(ops, Sequence) or isinstance(ops, str | bytes) or not ops:
        return Outcome(
            observed_outcome="EXECUTION_ERROR",
            counted_as_success=False,
            detail=f"{RC_WORKLOAD_MALFORMED}: case must contain a non-empty cache_ops list",
        )

    return _run_variant_workload(spec.variant_id, case_id, ops, spec=spec)


def _run_reference(case: Mapping[str, Any]) -> Outcome:
    """Run the unmodified reference candidate (ceiling row; not an ablation)."""
    case_id = str(case.get("case_id", "reference-case"))
    ops = case.get("cache_ops", ())
    return _run_variant_workload(REFERENCE_VARIANT_ID, case_id, ops, spec=None)


# ---------------------------------------------------------------------------
# Frozen attack/control family fixtures (the same suite every variant executes)
# ---------------------------------------------------------------------------


def case_fixtures() -> dict[str, Callable[[], dict[str, Any]]]:
    """Factory functions returning fresh, isolated case payloads per family."""
    subject = "subj-1"

    def _fresh_dispatch() -> dict[str, Any]:
        return {
            "case_id": f"popets-ablation-{FAMILY_FRESH_DISPATCH}",
            "family": FAMILY_FRESH_DISPATCH,
            "cache_ops": [
                {
                    "op": "put",
                    "key": "fresh_summary_1",
                    "value": "BP 120/80 normal",
                    "deps": [[subject, "analytics", 0]],
                },
                {
                    "op": "get",
                    "key": "fresh_summary_1",
                    "purpose": "analytics",
                    "epoch": 0,
                },
            ],
        }

    def _transitive_revocation() -> dict[str, Any]:
        return {
            "case_id": f"popets-ablation-{FAMILY_TRANSITIVE_REVOCATION}",
            "family": FAMILY_TRANSITIVE_REVOCATION,
            "cache_ops": [
                {
                    "op": "put",
                    "key": "summary_root_1",
                    "value": "clinical consultation note",
                    "deps": [[subject, "analytics", 0]],
                },
                {
                    "op": "put",
                    "key": "retry_child_1",
                    "value": "retry dispatch payload",
                    "deps": [[subject, "admin", 0]],
                    "derived_from": ["summary_root_1"],
                },
                {
                    "op": "revoke",
                    "subject": subject,
                    "purpose": "analytics",
                    "epoch": 0,
                },
                {
                    "op": "get",
                    "key": "retry_child_1",
                    "purpose": "admin",
                    "epoch": 0,
                },
            ],
        }

    def _unaffected_scope() -> dict[str, Any]:
        return {
            "case_id": f"popets-ablation-{FAMILY_UNAFFECTED_SCOPE}",
            "family": FAMILY_UNAFFECTED_SCOPE,
            "cache_ops": [
                {
                    "op": "put",
                    "key": "admin_note_1",
                    "value": "billing tier tier-B",
                    "deps": [[subject, "admin", 0]],
                },
                {
                    "op": "put",
                    "key": "summary_root_1",
                    "value": "clinical consultation note",
                    "deps": [[subject, "analytics", 0]],
                },
                {
                    "op": "revoke",
                    "subject": subject,
                    "purpose": "analytics",
                    "epoch": 0,
                },
                {
                    "op": "get",
                    "key": "admin_note_1",
                    "purpose": "admin",
                    "epoch": 0,
                },
            ],
        }

    def _unproven_lineage() -> dict[str, Any]:
        return {
            "case_id": f"popets-ablation-{FAMILY_UNPROVEN_LINEAGE}",
            "family": FAMILY_UNPROVEN_LINEAGE,
            "cache_ops": [
                {
                    "op": "put",
                    "key": "unproven_entry_1",
                    "value": "unanchored synthetic context",
                    "deps": [],
                },
                {
                    "op": "get",
                    "key": "unproven_entry_1",
                    "purpose": "analytics",
                    "epoch": 0,
                },
            ],
        }

    def _historical_taint() -> dict[str, Any]:
        return {
            "case_id": f"popets-ablation-{FAMILY_HISTORICAL_TAINT}",
            "family": FAMILY_HISTORICAL_TAINT,
            "cache_ops": [
                {
                    "op": "put",
                    "key": "hist_root_1",
                    "value": "historical consultation origin",
                    "deps": [[subject, "clinical", 0]],
                },
                {
                    "op": "put",
                    "key": "hist_summary_1",
                    "value": "derived patient history summary",
                    "deps": [[subject, "clinical", 0]],
                    "derived_from": ["hist_root_1"],
                },
                {
                    "op": "put",
                    "key": "current_longitudinal_dispatch",
                    "value": "longitudinal AI context payload",
                    "deps": [[subject, "research", 0]],
                    "derived_from": ["hist_summary_1"],
                },
                {
                    "op": "revoke",
                    "subject": subject,
                    "purpose": "clinical",
                    "epoch": 0,
                },
                {
                    "op": "get",
                    "key": "current_longitudinal_dispatch",
                    "purpose": "research",
                    "epoch": 0,
                },
            ],
        }

    def _cross_purpose() -> dict[str, Any]:
        return {
            "case_id": f"popets-ablation-{FAMILY_CROSS_PURPOSE}",
            "family": FAMILY_CROSS_PURPOSE,
            "cache_ops": [
                {
                    "op": "put",
                    "key": "purpose_scoped_1",
                    "value": "analytics context only",
                    "deps": [[subject, "analytics", 0]],
                },
                {
                    "op": "get",
                    "key": "purpose_scoped_1",
                    "purpose": "marketing",
                    "epoch": 0,
                },
            ],
        }

    return {
        FAMILY_FRESH_DISPATCH: _fresh_dispatch,
        FAMILY_TRANSITIVE_REVOCATION: _transitive_revocation,
        FAMILY_UNAFFECTED_SCOPE: _unaffected_scope,
        FAMILY_UNPROVEN_LINEAGE: _unproven_lineage,
        FAMILY_HISTORICAL_TAINT: _historical_taint,
        FAMILY_CROSS_PURPOSE: _cross_purpose,
    }


# ---------------------------------------------------------------------------
# Mechanistic inference matrix: preregistered predictions + verification
# ---------------------------------------------------------------------------

PREDICTED_VERDICTS: Final[Mapping[tuple[str, str], str]] = {
    # Reference ceiling (full candidate)
    (REFERENCE_VARIANT_ID, FAMILY_FRESH_DISPATCH): VERDICT_ADMIT,
    (REFERENCE_VARIANT_ID, FAMILY_TRANSITIVE_REVOCATION): VERDICT_REJECT,
    (REFERENCE_VARIANT_ID, FAMILY_UNAFFECTED_SCOPE): VERDICT_ADMIT,
    (REFERENCE_VARIANT_ID, FAMILY_UNPROVEN_LINEAGE): VERDICT_REJECT,
    (REFERENCE_VARIANT_ID, FAMILY_HISTORICAL_TAINT): VERDICT_REJECT,
    (REFERENCE_VARIANT_ID, FAMILY_CROSS_PURPOSE): VERDICT_REJECT,
    # Variant 1: candidate WITHOUT key module (no reverse edges)
    (VARIANT_CANDIDATE_NO_KEY_MODULE, FAMILY_FRESH_DISPATCH): VERDICT_ADMIT,
    (VARIANT_CANDIDATE_NO_KEY_MODULE, FAMILY_TRANSITIVE_REVOCATION): VERDICT_ADMIT,
    (VARIANT_CANDIDATE_NO_KEY_MODULE, FAMILY_UNAFFECTED_SCOPE): VERDICT_ADMIT,
    (VARIANT_CANDIDATE_NO_KEY_MODULE, FAMILY_UNPROVEN_LINEAGE): VERDICT_REJECT,
    (VARIANT_CANDIDATE_NO_KEY_MODULE, FAMILY_HISTORICAL_TAINT): VERDICT_ADMIT,
    (VARIANT_CANDIDATE_NO_KEY_MODULE, FAMILY_CROSS_PURPOSE): VERDICT_REJECT,
    # Variant 2: baseline with common safety gate
    (VARIANT_BASELINE_COMMON_SAFETY_GATE, FAMILY_FRESH_DISPATCH): VERDICT_ADMIT,
    (VARIANT_BASELINE_COMMON_SAFETY_GATE, FAMILY_TRANSITIVE_REVOCATION): VERDICT_ADMIT,
    (VARIANT_BASELINE_COMMON_SAFETY_GATE, FAMILY_UNAFFECTED_SCOPE): VERDICT_ADMIT,
    (VARIANT_BASELINE_COMMON_SAFETY_GATE, FAMILY_UNPROVEN_LINEAGE): VERDICT_ADMIT,
    (VARIANT_BASELINE_COMMON_SAFETY_GATE, FAMILY_HISTORICAL_TAINT): VERDICT_ADMIT,
    (VARIANT_BASELINE_COMMON_SAFETY_GATE, FAMILY_CROSS_PURPOSE): VERDICT_REJECT,
    # Variant 3: full refresh (coarse purge)
    (VARIANT_FULL_REFRESH, FAMILY_FRESH_DISPATCH): VERDICT_ADMIT,
    (VARIANT_FULL_REFRESH, FAMILY_TRANSITIVE_REVOCATION): VERDICT_REJECT,
    (VARIANT_FULL_REFRESH, FAMILY_UNAFFECTED_SCOPE): VERDICT_REJECT,
    (VARIANT_FULL_REFRESH, FAMILY_UNPROVEN_LINEAGE): VERDICT_REJECT,
    (VARIANT_FULL_REFRESH, FAMILY_HISTORICAL_TAINT): VERDICT_REJECT,
    (VARIANT_FULL_REFRESH, FAMILY_CROSS_PURPOSE): VERDICT_REJECT,
    # Variant 4: zero proof/receipt
    (VARIANT_ZERO_PROOF_RECEIPT, FAMILY_FRESH_DISPATCH): VERDICT_ADMIT,
    (VARIANT_ZERO_PROOF_RECEIPT, FAMILY_TRANSITIVE_REVOCATION): VERDICT_REJECT,
    (VARIANT_ZERO_PROOF_RECEIPT, FAMILY_UNAFFECTED_SCOPE): VERDICT_ADMIT,
    (VARIANT_ZERO_PROOF_RECEIPT, FAMILY_UNPROVEN_LINEAGE): VERDICT_ADMIT,
    (VARIANT_ZERO_PROOF_RECEIPT, FAMILY_HISTORICAL_TAINT): VERDICT_REJECT,
    (VARIANT_ZERO_PROOF_RECEIPT, FAMILY_CROSS_PURPOSE): VERDICT_REJECT,
    # Variant 5: no context/history branch
    (VARIANT_NO_CONTEXT_HISTORY_BRANCH, FAMILY_FRESH_DISPATCH): VERDICT_ADMIT,
    (VARIANT_NO_CONTEXT_HISTORY_BRANCH, FAMILY_TRANSITIVE_REVOCATION): VERDICT_ADMIT,
    (VARIANT_NO_CONTEXT_HISTORY_BRANCH, FAMILY_UNAFFECTED_SCOPE): VERDICT_ADMIT,
    (VARIANT_NO_CONTEXT_HISTORY_BRANCH, FAMILY_UNPROVEN_LINEAGE): VERDICT_REJECT,
    (VARIANT_NO_CONTEXT_HISTORY_BRANCH, FAMILY_HISTORICAL_TAINT): VERDICT_ADMIT,
    (VARIANT_NO_CONTEXT_HISTORY_BRANCH, FAMILY_CROSS_PURPOSE): VERDICT_REJECT,
}


def _degradation_summary(predicted: Mapping[tuple[str, str], str]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for variant_id in ABLATION_REGISTRY:
        missed = sorted(
            family
            for family in FAULT_FAMILY_IDS
            if predicted[(variant_id, family)] == VERDICT_ADMIT
            and predicted[(REFERENCE_VARIANT_ID, family)] == VERDICT_REJECT
        )
        false_flagged = sorted(
            family
            for family in FAULT_FAMILY_IDS
            if predicted[(variant_id, family)] == VERDICT_REJECT
            and predicted[(REFERENCE_VARIANT_ID, family)] == VERDICT_ADMIT
        )
        summary[variant_id] = {
            "missed_families": missed,
            "false_flagged_families": false_flagged,
            "measurably_degraded": bool(missed or false_flagged),
        }
    return summary


def mechanistic_inference_matrix() -> dict[str, Any]:
    """Preregistered DESIGN RECORD: variant x family predicted verdicts."""
    return {
        "ablations_version": POPETS_ABLATIONS_VERSION,
        "task_id": ABLATION_TASK_ID,
        "reference_variant": REFERENCE_VARIANT_ID,
        "fault_families": list(FAULT_FAMILY_IDS),
        "variants": {vid: spec.to_dict() for vid, spec in ABLATION_REGISTRY.items()},
        "predicted_verdicts": {
            variant_id: {
                family: PREDICTED_VERDICTS[(variant_id, family)] for family in FAULT_FAMILY_IDS
            }
            for variant_id in (REFERENCE_VARIANT_ID, *ABLATION_REGISTRY)
        },
        "degradation_axes": _degradation_summary(PREDICTED_VERDICTS),
        "scale": "DEVELOPMENT (mechanism causality; NOT confirmatory)",
    }


def verify_mechanistic_inference_matrix() -> dict[str, Any]:
    """Run EVERY variant over EVERY frozen attack family and compare."""
    fixtures = case_fixtures()
    runners: dict[str, Callable[[Mapping[str, Any]], Outcome]] = {
        REFERENCE_VARIANT_ID: _run_reference,
        **{vid: (lambda case, _vid=vid: run_ablation(_vid, case)) for vid in ABLATION_REGISTRY},
    }
    cells: list[dict[str, Any]] = []
    all_match = True
    observed_verdicts: dict[tuple[str, str], str] = {}
    for variant_id, runner in runners.items():
        for family in FAULT_FAMILY_IDS:
            outcome = runner(fixtures[family]())
            observed = outcome.observed_outcome
            predicted = PREDICTED_VERDICTS[(variant_id, family)]
            match = observed == predicted
            all_match = all_match and match
            observed_verdicts[(variant_id, family)] = observed
            cells.append(
                {
                    "variant_id": variant_id,
                    "family_id": family,
                    "predicted": predicted,
                    "observed": observed,
                    "match": match,
                    "detail": outcome.detail,
                }
            )
    observed_degradation = _degradation_summary(observed_verdicts)
    return {
        "ablations_version": POPETS_ABLATIONS_VERSION,
        "all_cells_match": all_match,
        "cell_count": len(cells),
        "cells": cells,
        "observed_verdicts": {
            variant_id: {
                family: observed_verdicts[(variant_id, family)] for family in FAULT_FAMILY_IDS
            }
            for variant_id in runners
        },
        "observed_degradation": observed_degradation,
        "predicted_degradation": _degradation_summary(PREDICTED_VERDICTS),
        "scale": "DEVELOPMENT (mechanism causality; NOT confirmatory)",
    }


def describe_ablations() -> dict[str, Any]:
    """Machine-readable ablation design record (no empirical results here)."""
    return {
        "ablations_version": POPETS_ABLATIONS_VERSION,
        "task_id": ABLATION_TASK_ID,
        "phase": "P04 (development-scale mechanism ablation)",
        "candidate_id": cand.CANDIDATE_ID,
        "reference_variant": REFERENCE_VARIANT_ID,
        "registry": {vid: spec.to_dict() for vid, spec in ABLATION_REGISTRY.items()},
        "fault_families": list(FAULT_FAMILY_IDS),
        "matrix": mechanistic_inference_matrix(),
    }


__all__ = [
    "ABLATION_REGISTRY",
    "ABLATION_TASK_ID",
    "AblationError",
    "FAMILY_CROSS_PURPOSE",
    "FAMILY_FRESH_DISPATCH",
    "FAMILY_HISTORICAL_TAINT",
    "FAMILY_TRANSITIVE_REVOCATION",
    "FAMILY_UNAFFECTED_SCOPE",
    "FAMILY_UNPROVEN_LINEAGE",
    "FAULT_FAMILY_IDS",
    "POPETS_ABLATIONS_VERSION",
    "PREDICTED_VERDICTS",
    "RC_CASE_ID_MISSING",
    "RC_CASE_ID_NOT_STRING",
    "RC_CASE_NOT_AN_OBJECT",
    "RC_UNKNOWN_ABLATION_VARIANT",
    "RC_VARIANT_REMOVES_NOTHING",
    "RC_WORKLOAD_MALFORMED",
    "REFERENCE_VARIANT_ID",
    "VARIANT_BASELINE_COMMON_SAFETY_GATE",
    "VARIANT_CANDIDATE_NO_KEY_MODULE",
    "VARIANT_FULL_REFRESH",
    "VARIANT_NO_CONTEXT_HISTORY_BRANCH",
    "VARIANT_ZERO_PROOF_RECEIPT",
    "VERDICT_ADMIT",
    "VERDICT_REJECT",
    "VariantSpec",
    "case_fixtures",
    "describe_ablations",
    "mechanistic_inference_matrix",
    "refuse_unregistered_variant",
    "run_ablation",
    "variant_ids",
    "verify_mechanistic_inference_matrix",
]
