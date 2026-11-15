"""PST venue2027 ex-ante frozen forensic query set (task PST-X02_forensic_queries).

Purpose
-------
Primary-endpoint denominator of the PST 2027 study "ReceiptMin: Measuring
Forensic Reconstructability under Purpose-Bound Audit Minimization"
(``research/venue2027/VENUES/pst/RESEARCH_BLUEPRINT.md`` RQ1; task contract
``research/venue2027/VENUES/pst/TASKS/PST-X02_forensic_queries.md``; frozen
registry ``research/venue2027/pst/rq_and_estimands.yaml`` forensic_query_set).
The RQ1 estimand — forensic query answerability — is the population mean over
independent synthetic case histories of the per-history fraction of THIS set
answered exactly, per arm and retention stage, scored against the trusted
offline oracle ledger. The set is therefore fixed EX ANTE and frozen: any
post-hoc addition, removal, rewording or reordering of queries is query-set
tuning and must be refused mechanically (``assert_frozen_query_set``).
Deliberately over-redacted views (PST-CASE-05), missing retention-epoch proofs
(PST-CASE-12) and absent receipts (PST-CASE-09) must classify as
INDETERMINATE / NOT_ANSWERABLE, never be coerced into a successful answer.

Query classes (frozen in the rq_registry): ``authorization`` (who authorized
what under which purpose/epoch), ``provenance`` (was the action committed and
witnessed; what content was projected), ``commit_eligibility`` (was consent
and policy active at action time).

Each query declares the minimum evidence field set its class requires from an
audit view (the mandatory-field rule of the threat model: a committer cannot
withhold a mandatory field without forcing INDETERMINATE). Field names are
structural and PHI-free; the synthetic field vocabulary matches the PST
receipt contract (``RECEIPT_FIELDS`` in :mod:`.generate_dataset`).

Allowed input
-------------
:func:`answerable` takes an :class:`AuditView` — a read-only projection of
retained audit evidence with ``event_id`` plus the subset of fields
(``retained_fields``) that survived minimization at the reader's epoch, and
an ``epoch_active`` map for consent/policy freshness. No network, no clock,
no randomness, no database; the view is injected by the caller.

Failure semantics
-----------------
Every judgment is one of the three typed :class:`Answerability` values.
ANSWERABLE requires every witness field of the query class to be present and
internally coherent; NOT_ANSWERABLE means the evidence needed is provably
absent under the queried retention mode (a true reconstruction loss);
INDETERMINATE means evidence exists but a load-bearing proof (consent/policy
epoch attestation, witness, retention-epoch key-custody attestation) is
missing, so neither success nor loss may be claimed (fail closed,
PST-CASE-05/07/12 discipline; INDETERMINATE is retained and counted, never
coerced). Unknown query ids raise :class:`ForensicQueryError` with stable
reason codes; a view without a stable event identity is refused outright.

Freeze contract
---------------
``FROZEN_QUERY_SET_SHA256`` is the canonical-JSON SHA256 of the serialized
query list (``queries_sha256``). It was computed from
``FORENSIC_QUERIES`` at freeze time and committed; the tests recompute it and
``assert_frozen_query_set`` refuses any drift with reason code
``QUERY_SET_DRIFT``. This constant is the pre-registration lock: changing a
query without changing the constant fails the suite, and changing both is a
protocol violation visible in review as a diff to a frozen constant.

Version
-------
``FORENSIC_QUERY_SET_VERSION = "1.0.0"`` (additive-only within 1.x; any
addition creates a new frozen constant and a new major/minor freeze entry).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, Literal

FORENSIC_QUERY_SET_VERSION = "1.0.0"

QUERY_SET_SCHEMA_VERSION = "clara.venue2027.pst.forensic_query_set.v1"

#: Frozen query classes from the preregistered RQ registry
#: (``research/venue2027/pst/rq_and_estimands.yaml`` forensic_query_set).
QUERY_CLASSES: tuple[str, ...] = ("authorization", "provenance", "commit_eligibility")

#: Structural receipt-field vocabulary (PST receipt contract, task
#: PST-X01/PST-dataset). PHI-free by construction; guards the fixture layer.
RECEIPT_FIELDS: tuple[str, ...] = (
    "commitment_digest",
    "purpose_tag",
    "consent_epoch",
    "policy_epoch",
    "witness_id",
    "retention_mode",
)

Answerability = Literal["ANSWERABLE", "NOT_ANSWERABLE", "INDETERMINATE"]

ANSWERABLE: Answerability = "ANSWERABLE"
NOT_ANSWERABLE: Answerability = "NOT_ANSWERABLE"
INDETERMINATE: Answerability = "INDETERMINATE"

#: Stable machine-checkable reason codes (never bare exceptions).
REASON_UNKNOWN_QUERY_ID = "UNKNOWN_QUERY_ID"
REASON_BAD_QUERY = "MALFORMED_QUERY"
REASON_BAD_VIEW = "MALFORMED_AUDIT_VIEW"
REASON_QUERY_SET_DRIFT = "QUERY_SET_DRIFT"


class ForensicQueryError(ValueError):
    """Refusal with a stable, machine-checkable reason code."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(f"{reason_code}: {message}")
        self.reason_code = reason_code


@dataclasses.dataclass(frozen=True)
class ForensicQuery:
    """One ex-ante frozen forensic question.

    - ``query_id``: stable identifier (``FQ-<class-abbrev>-<nn>``); the
      denominator key of every RQ1 computation.
    - ``query_class``: one of :data:`QUERY_CLASSES`.
    - ``statement``: the question in exact, frozen wording; rewording is a
      freeze breach, visible as a sha256 change.
    - ``witnesses_needed``: minimum retained-evidence fields the query's
      class requires to be ANSWERABLE from an audit view (the mandatory
      field set; a withheld field forces INDETERMINATE, PST-CASE-05).
    - ``oracle_answer``: the trusted offline complete ledger's answer for the
      reference case history the query was authored against (the signature
      triple ``query_id, witnesses_needed, trusted oracle answer`` of the
      task contract). ``INDETERMINATE`` marks queries whose reference truth
      is itself incomplete — they measure the utility floor, never a pass.
    - ``oracle_pointer``: address of the frozen oracle label for the
      reference history (evidence-pointer discipline of the venue schema).
    """

    query_id: str
    query_class: str
    statement: str
    witnesses_needed: tuple[str, ...]
    oracle_answer: Answerability
    oracle_pointer: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "query_class": self.query_class,
            "statement": self.statement,
            "witnesses_needed": list(self.witnesses_needed),
            "oracle_answer": self.oracle_answer,
            "oracle_pointer": self.oracle_pointer,
        }


@dataclasses.dataclass(frozen=True)
class AuditView:
    """Read-only projection of retained audit evidence at the reader's epoch.

    - ``event_id``: stable logical operation id of the audited action.
    - ``retained_fields``: mapping field name -> retained value for whatever
      survived minimization (an empty mapping models the no-log comparator,
      PST-CASE-09; a partial mapping models over-redaction, PST-CASE-05).
    - ``retention_mode``: one of ``full`` / ``selective`` / ``hash_only``.
    - ``epoch_active``: map of epoch-kind (``consent_epoch`` /
      ``policy_epoch``) -> attested-active epoch id; absence of the kind the
      query needs forces INDETERMINATE, never a silent affirmative.
    - ``key_custody_attested``: False models the missing key-custody /
      key-deletion attestation of PST-CASE-07/12; commitment and epoch
      proofs alone then cannot establish content reconstruction.
    """

    event_id: str
    retained_fields: Mapping[str, str]
    retention_mode: str = "full"
    epoch_active: Mapping[str, str] = dataclasses.field(default_factory=dict)
    key_custody_attested: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, str) or not self.event_id.strip():
            raise ForensicQueryError(REASON_BAD_VIEW, "event_id must be a non-empty string")
        if self.retention_mode not in ("full", "selective", "hash_only"):
            raise ForensicQueryError(
                REASON_BAD_VIEW, f"unknown retention_mode {self.retention_mode!r}"
            )


def _coerce_witness(view: AuditView, field: str) -> str | None:
    """Return the witness value for ``field`` if provably present.

    ``hash_only`` retention keeps digests alone: every non-digest witness is
    provably absent (NOT_ANSWERABLE evidence level), while a digest witness
    survives. Nothing is guessed.
    """

    if field not in view.retained_fields:
        return None
    if view.retention_mode == "hash_only" and field != "commitment_digest":
        return None
    value = view.retained_fields[field]
    return value if isinstance(value, str) and value.strip() else None


def answerable(query: ForensicQuery, audit_view: AuditView) -> Answerability:
    """Classify one frozen query against one audit projection.

    Fail-closed semantics per evidence level:

    - ANSWERABLE — every witness field of the query class is retained and
      coherent, and the class's epoch attestation (if any) is active.
    - INDETERMINATE — witnesses are retained but a load-bearing proof is
      missing: the class's consent/policy epoch attestation is absent from
      the view, or key custody for the commitment is not attested while the
      query needs the committed content. Neither success nor loss is claimed.
    - NOT_ANSWERABLE — a witness field is provably absent under the queried
      retention mode or was dropped by minimization: a true reconstruction
      loss of the arm under test (PST-CASE-05 over-redaction shape).
    """

    if query.query_class not in QUERY_CLASSES:
        raise ForensicQueryError(REASON_BAD_QUERY, f"unknown query_class {query.query_class!r}")
    missing_witnesses = [
        f for f in query.witnesses_needed if _coerce_witness(audit_view, f) is None
    ]
    if missing_witnesses:
        return NOT_ANSWERABLE
    # Authorization / commit-eligibility queries additionally require the
    # consent and/or policy epoch attestation to be active at action time.
    needed_epochs: tuple[str, ...] = ()
    if query.query_class in ("authorization", "commit_eligibility"):
        needed_epochs = ("consent_epoch", "policy_epoch")
    missing_epochs = [e for e in needed_epochs if e not in audit_view.epoch_active]
    if missing_epochs:
        return INDETERMINATE
    # Provenance queries that read the committed CONTENT (any witness beyond
    # the bare commitment digest) require key custody; a commitment digest
    # without a custody attestation proves existence of a commitment, not
    # recoverability of its content (PST-CASE-07/12). An existence query over
    # the bare digest is answered by the digest alone: hash chains and
    # transparency logs prove exactly this without any content key.
    if (
        query.query_class == "provenance"
        and "commitment_digest" in query.witnesses_needed
        and any(field != "commitment_digest" for field in query.witnesses_needed)
        and not audit_view.key_custody_attested
    ):
        return INDETERMINATE
    return ANSWERABLE


def answerable_by_id(query_id: str, audit_view: AuditView) -> Answerability:
    """Classify by frozen query id; unknown ids fail closed."""

    query = QUERY_BY_ID.get(query_id)
    if query is None:
        raise ForensicQueryError(REASON_UNKNOWN_QUERY_ID, f"no frozen query {query_id!r}")
    return answerable(query, audit_view)


# --------------------------------------------------------------------------
# The ex-ante frozen set (N=12). Do not edit below this line without a new
# freeze version; the tests recompute FROZEN_QUERY_SET_SHA256.
# --------------------------------------------------------------------------

FORENSIC_QUERIES: tuple[ForensicQuery, ...] = (
    ForensicQuery(
        query_id="FQ-AUTH-01",
        query_class="authorization",
        statement="Which principal authorized the action committed under event E?",
        witnesses_needed=("purpose_tag", "witness_id"),
        oracle_answer="ANSWERABLE",
        oracle_pointer=("research/venue2027/pst/protocols/forensic_query_catalog.yaml#FQ-AUTH-01"),
    ),
    ForensicQuery(
        query_id="FQ-AUTH-02",
        query_class="authorization",
        statement="Which declared purpose justified the action committed under event E?",
        witnesses_needed=("purpose_tag",),
        oracle_answer="ANSWERABLE",
        oracle_pointer=("research/venue2027/pst/protocols/forensic_query_catalog.yaml#FQ-AUTH-02"),
    ),
    ForensicQuery(
        query_id="FQ-AUTH-03",
        query_class="authorization",
        statement="Was the purpose authorization active at the action time of event E?",
        witnesses_needed=("purpose_tag", "witness_id"),
        oracle_answer="ANSWERABLE",
        oracle_pointer=("research/venue2027/pst/protocols/forensic_query_catalog.yaml#FQ-AUTH-03"),
    ),
    ForensicQuery(
        query_id="FQ-AUTH-04",
        query_class="authorization",
        statement=(
            "Which consent epoch was the action of event E committed under, "
            "and was it active at action time?"
        ),
        witnesses_needed=("purpose_tag", "consent_epoch"),
        oracle_answer="ANSWERABLE",
        oracle_pointer=("research/venue2027/pst/protocols/forensic_query_catalog.yaml#FQ-AUTH-04"),
    ),
    ForensicQuery(
        query_id="FQ-PROV-01",
        query_class="provenance",
        statement="Was a witnessed commitment created for the action of event E?",
        witnesses_needed=("commitment_digest",),
        oracle_answer="ANSWERABLE",
        oracle_pointer=("research/venue2027/pst/protocols/forensic_query_catalog.yaml#FQ-PROV-01"),
    ),
    ForensicQuery(
        query_id="FQ-PROV-02",
        query_class="provenance",
        statement=(
            "Reconstruct the omitted receipt field value for event E from the "
            "retained receipts and retention map."
        ),
        witnesses_needed=("commitment_digest", "retention_mode"),
        oracle_answer="INDETERMINATE",
        oracle_pointer=("research/venue2027/pst/protocols/forensic_query_catalog.yaml#FQ-PROV-02"),
    ),
    ForensicQuery(
        query_id="FQ-PROV-03",
        query_class="provenance",
        statement=(
            "Which projection of the record content was disclosed to the " "assistant for event E?"
        ),
        witnesses_needed=("purpose_tag", "retention_mode"),
        oracle_answer="ANSWERABLE",
        oracle_pointer=("research/venue2027/pst/protocols/forensic_query_catalog.yaml#FQ-PROV-03"),
    ),
    ForensicQuery(
        query_id="FQ-PROV-04",
        query_class="provenance",
        statement="Was the retained receipt chain for event E falsified after commit?",
        witnesses_needed=("commitment_digest", "witness_id"),
        oracle_answer="ANSWERABLE",
        oracle_pointer=("research/venue2027/pst/protocols/forensic_query_catalog.yaml#FQ-PROV-04"),
    ),
    ForensicQuery(
        query_id="FQ-ELIG-01",
        query_class="commit_eligibility",
        statement="Was medical consent active at the action time of event E?",
        witnesses_needed=("purpose_tag", "consent_epoch"),
        oracle_answer="ANSWERABLE",
        oracle_pointer=("research/venue2027/pst/protocols/forensic_query_catalog.yaml#FQ-ELIG-01"),
    ),
    ForensicQuery(
        query_id="FQ-ELIG-02",
        query_class="commit_eligibility",
        statement="Which policy epoch governed the action of event E at commit?",
        witnesses_needed=("purpose_tag", "policy_epoch"),
        oracle_answer="ANSWERABLE",
        oracle_pointer=("research/venue2027/pst/protocols/forensic_query_catalog.yaml#FQ-ELIG-02"),
    ),
    ForensicQuery(
        query_id="FQ-ELIG-03",
        query_class="commit_eligibility",
        statement=(
            "Did the retention map of event E attest key custody for the "
            "committed content at the reader's epoch?"
        ),
        witnesses_needed=("commitment_digest", "retention_mode"),
        oracle_answer="ANSWERABLE",
        oracle_pointer=("research/venue2027/pst/protocols/forensic_query_catalog.yaml#FQ-ELIG-03"),
    ),
    ForensicQuery(
        query_id="FQ-ELIG-04",
        query_class="commit_eligibility",
        statement=(
            "Was the write of event E committed to the witnessed append-only "
            "chain, or only dispatched?"
        ),
        witnesses_needed=("commitment_digest", "witness_id", "policy_epoch"),
        oracle_answer="NOT_ANSWERABLE",
        oracle_pointer=("research/venue2027/pst/protocols/forensic_query_catalog.yaml#FQ-ELIG-04"),
    ),
)

#: Stable query ids, in frozen order.
QUERY_IDS: tuple[str, ...] = tuple(q.query_id for q in FORENSIC_QUERIES)

QUERY_BY_ID: Mapping[str, ForensicQuery] = {q.query_id: q for q in FORENSIC_QUERIES}


def serialize_query_set(queries: Sequence[ForensicQuery] = FORENSIC_QUERIES) -> str:
    """Canonical JSON serialization of a query list (freeze hash input)."""

    return json.dumps([q.to_dict() for q in queries], sort_keys=True, separators=(",", ":"))


def queries_sha256(queries: Sequence[ForensicQuery] = FORENSIC_QUERIES) -> str:
    """Canonical SHA256 of a query list; the freeze constant is its digest."""

    return hashlib.sha256(serialize_query_set(queries).encode("utf-8")).hexdigest()


def _assert_internal_consistency(queries: Sequence[ForensicQuery] = FORENSIC_QUERIES) -> None:
    """Fail closed on malformed members of a query list."""

    seen: set[str] = set()
    for query in queries:
        if not query.query_id or query.query_id in seen:
            raise ForensicQueryError(
                REASON_BAD_QUERY, f"duplicate or empty query_id {query.query_id!r}"
            )
        seen.add(query.query_id)
        if query.query_class not in QUERY_CLASSES:
            raise ForensicQueryError(
                REASON_BAD_QUERY, f"{query.query_id}: unknown query_class {query.query_class!r}"
            )
        if not query.witnesses_needed:
            raise ForensicQueryError(
                REASON_BAD_QUERY, f"{query.query_id}: witness set must be non-empty"
            )
        unknown_fields = [f for f in query.witnesses_needed if f not in RECEIPT_FIELDS]
        if unknown_fields:
            raise ForensicQueryError(
                REASON_BAD_QUERY, f"{query.query_id}: unknown witness fields {unknown_fields!r}"
            )
        if query.oracle_answer not in (ANSWERABLE, NOT_ANSWERABLE, INDETERMINATE):
            raise ForensicQueryError(
                REASON_BAD_QUERY, f"{query.query_id}: bad oracle_answer {query.oracle_answer!r}"
            )


def frozen_query_set_sha256() -> str:
    """SHA256 of the shipped frozen set (must equal the freeze constant)."""

    return queries_sha256(FORENSIC_QUERIES)


#: ---------------------------------------------------------------------------
#: FREEZE LOCK. Computed once from the N=12 set above and committed; the
#: test suite recomputes it and refuses any drift (QUERY_SET_DRIFT). Editing
#: any query, adding or removing one, or reordering the tuple changes this
#: digest and is a protocol violation visible in review.
#: ---------------------------------------------------------------------------
FROZEN_QUERY_SET_SHA256 = "16801af9c1f00bd6ca64fc48b3e0013873069e9de446a9bb87978b7b16cdbab2"


def assert_frozen_query_set(queries: Sequence[ForensicQuery]) -> None:
    """Refuse a drifted query set (stable reason code QUERY_SET_DRIFT).

    The candidate denominator actually used downstream must hash to the
    committed freeze constant. Any post-hoc addition, removal, rewording or
    reordering is refused here, mirroring ``assert_frozen_analysis`` in the
    shared analysis policy.
    """

    actual = queries_sha256(queries)
    if actual != FROZEN_QUERY_SET_SHA256:
        raise ForensicQueryError(
            REASON_QUERY_SET_DRIFT,
            f"query set hash {actual} != frozen {FROZEN_QUERY_SET_SHA256}",
        )


_assert_internal_consistency(FORENSIC_QUERIES)
