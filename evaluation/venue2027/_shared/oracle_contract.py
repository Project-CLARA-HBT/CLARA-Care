"""CLARA-Care 2027 shared task SH-independent_oracle — independent truth boundary.

Purpose
-------
Program-level independent-oracle contract reused by all nine venue2027 studies
(``research/venue2027/GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md`` rule 2: an
independent oracle must not import any candidate code; rule 8: paired
endpoints are recomputed from raw events against independent oracle/baseline
signatures). Ground truth derives ONLY from frozen oracle labels and observed
persisted state — never from candidate reason codes.

Components
----------
- :class:`Case` — typed, validated mirror of ``case.v1.schema.json`` (required
  fields only; fail closed on any missing/ill-typed/unknown field).
- :class:`OracleVerdict` — the only truth type an oracle may emit
  (``ADMIT | REJECT | INDETERMINATE`` plus a stable reason code and frozen
  evidence pointers). ``INDETERMINATE`` is a first-class outcome and is never
  counted as a safe rejection or a completion.
- :class:`Oracle` — :class:`typing.Protocol` for ``evaluate(case) -> OracleVerdict``.
- :class:`DeterministicReferenceOracle` — pure, clock-free, randomness-free
  reference implementation driven ONLY by a frozen label table; it never reads
  candidate outputs or candidate-supplied reason codes.
- :func:`assert_oracle_independence` — parses the oracle *source* with
  :mod:`ast` and refuses any oracle that imports a candidate/baseline module
  (stable reason codes ``CANDIDATE_IMPORT`` / ``BASELINE_LABEL_EXCHANGE``),
  including constant-string dynamic imports; dynamic imports whose target
  cannot be proven static fail closed with ``DYNAMIC_IMPORT_UNRESOLVABLE``.
- :class:`HumanAdjudicationRecord` — blinded independent human adjudication
  record (reviewer pseudonym, blinded flag, UTC timestamp, verdict) for
  ambiguous clinical/SoK cases.

Allowed input
-------------
JSON-serializable ``case.v1`` dicts and Python source files for the
independence scan. No network, no database, no live provider access.

Failure semantics
-----------------
Fail closed with stable uppercase reason codes. An unadjudicated
``INDETERMINATE`` verdict is refused by :func:`assert_countable` and is never
silently tallied as a safe rejection (mirror of the outcome contract's
false-zero ban).

Version
-------
``ORACLE_CONTRACT_VERSION = "1.0.0"`` (additive-only within 1.x).
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import datetime
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

ORACLE_CONTRACT_VERSION = "1.0.0"

OUTCOME_ADMIT = "ADMIT"
OUTCOME_REJECT = "REJECT"
OUTCOME_INDETERMINATE = "INDETERMINATE"

#: First-class verdict outcomes (``INDETERMINATE`` included, never collapsed).
VERDICT_OUTCOMES: frozenset[str] = frozenset(
    {OUTCOME_ADMIT, OUTCOME_REJECT, OUTCOME_INDETERMINATE}
)

REASON_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SOURCE_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
INDEPENDENT_UNIT_ID_RE = re.compile(r"^[A-Za-z0-9._:.-]{1,128}$")
BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")

UNIT_KINDS: frozenset[str] = frozenset(
    {"case", "history", "run", "session", "subject", "benchmark_run"}
)
BACKENDS: frozenset[str] = frozenset({"postgresql", "sqlite", "synthetic"})
EVIDENCE_POINTER_KINDS: frozenset[str] = frozenset(
    {
        "fixture_path",
        "dataset_snapshot",
        "consent_receipt",
        "policy_epoch",
        "oracle_label",
        "provider_trace",
    }
)

CASE_SCHEMA_VERSION = "1"
_CASE_REQUIRED_FIELDS: tuple[str, ...] = (
    "schema_version",
    "case_id",
    "case_family",
    "independent_unit_id",
    "unit_kind",
    "backend",
    "source_sha",
    "seed",
    "branch",
    "arm_id",
    "evidence",
)
_CASE_OPTIONAL_FIELDS: tuple[str, ...] = ("created_at", "notes")
_EVIDENCE_REQUIRED_FIELDS: tuple[str, ...] = ("pointer_kind", "uri", "sha256")
_EVIDENCE_OPTIONAL_FIELDS: tuple[str, ...] = ("frozen_at",)


class OracleContractError(ValueError):
    """Fail-closed contract violation carrying a stable machine-checkable reason code."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


class CaseValidationError(OracleContractError):
    """The case record is not a valid ``case.v1`` document."""


class OracleIndependenceError(OracleContractError):
    """The oracle source is not provably independent of candidate/baseline code."""


def _check_rfc3339_utc(value: str, code: str) -> datetime.datetime:
    """Parse an RFC 3339 timestamp and require an explicit UTC offset (fail closed)."""
    try:
        parsed = datetime.datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise OracleContractError(code, f"invalid RFC 3339 timestamp {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != datetime.timedelta(0):
        raise OracleContractError(code, f"timestamp {value!r} must be UTC (Z or +00:00)")
    return parsed


@dataclasses.dataclass(frozen=True)
class EvidenceRef:
    """Frozen evidence pointer (``case.v1`` ``evidence_pointer``): hash-addressed input."""

    pointer_kind: str
    uri: str
    sha256: str
    frozen_at: str | None = None

    def __post_init__(self) -> None:
        if self.pointer_kind not in EVIDENCE_POINTER_KINDS:
            raise OracleContractError(
                "EVIDENCE_BAD_KIND",
                f"pointer_kind {self.pointer_kind!r} not in {sorted(EVIDENCE_POINTER_KINDS)}",
            )
        if not isinstance(self.uri, str) or not self.uri:
            raise OracleContractError("EVIDENCE_BAD_URI", "uri must be a non-empty string")
        if not SHA256_RE.match(self.sha256):
            raise OracleContractError(
                "EVIDENCE_BAD_SHA256", f"sha256 {self.sha256!r} must be 64 lowercase hex chars"
            )
        if self.frozen_at is not None:
            _check_rfc3339_utc(self.frozen_at, "EVIDENCE_BAD_TIMESTAMP")

    def to_dict(self) -> dict[str, str | None]:
        return {
            "pointer_kind": self.pointer_kind,
            "uri": self.uri,
            "sha256": self.sha256,
            "frozen_at": self.frozen_at,
        }


@dataclasses.dataclass(frozen=True)
class Case:
    """Typed mirror of the required ``case.v1.schema.json`` fields (fail closed)."""

    schema_version: str
    case_id: str
    case_family: str
    independent_unit_id: str
    unit_kind: str
    backend: str
    source_sha: str
    seed: int
    branch: str
    arm_id: str
    evidence: tuple[EvidenceRef, ...]
    created_at: str | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != CASE_SCHEMA_VERSION:
            raise CaseValidationError(
                "CASE_SCHEMA_VERSION", f"schema_version {self.schema_version!r} != '1'"
            )
        for field_name in ("case_id", "case_family", "arm_id"):
            if not isinstance(getattr(self, field_name), str) or not getattr(self, field_name):
                raise CaseValidationError(
                    "CASE_EMPTY_FIELD", f"field {field_name!r} must be a non-empty string"
                )
        if not INDEPENDENT_UNIT_ID_RE.match(self.independent_unit_id):
            raise CaseValidationError(
                "CASE_BAD_UNIT_ID",
                f"independent_unit_id {self.independent_unit_id!r} violates the v1 pattern",
            )
        if self.unit_kind not in UNIT_KINDS:
            raise CaseValidationError(
                "CASE_BAD_UNIT_KIND", f"unit_kind {self.unit_kind!r} not in {sorted(UNIT_KINDS)}"
            )
        if self.backend not in BACKENDS:
            raise CaseValidationError(
                "CASE_BAD_BACKEND", f"backend {self.backend!r} not in {sorted(BACKENDS)}"
            )
        if not SOURCE_SHA_RE.match(self.source_sha):
            raise CaseValidationError(
                "CASE_BAD_SOURCE_SHA", f"source_sha {self.source_sha!r} must be 40 lowercase hex"
            )
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise CaseValidationError("CASE_BAD_SEED", f"seed {self.seed!r} must be an integer")
        if not 0 <= self.seed <= 18446744073709551615:
            raise CaseValidationError(
                "CASE_BAD_SEED", f"seed {self.seed} outside [0, 2**64-1]"
            )
        if not BRANCH_RE.match(self.branch):
            raise CaseValidationError(
                "CASE_BAD_BRANCH", f"branch {self.branch!r} violates the v1 pattern"
            )
        if not self.evidence:
            raise CaseValidationError(
                "CASE_NO_EVIDENCE", "at least one frozen evidence pointer is required"
            )
        for ref in self.evidence:
            if not isinstance(ref, EvidenceRef):
                raise CaseValidationError(
                    "CASE_BAD_EVIDENCE", "evidence entries must be EvidenceRef instances"
                )
        if self.created_at is not None:
            _check_rfc3339_utc(self.created_at, "CASE_BAD_TIMESTAMP")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Case:
        """Build a validated :class:`Case` from a ``case.v1`` dict; fail closed."""
        if not isinstance(data, Mapping):
            raise CaseValidationError(
                "CASE_NOT_AN_OBJECT", f"expected an object, got {type(data).__name__}"
            )
        unknown = sorted(set(data) - set(_CASE_REQUIRED_FIELDS) - set(_CASE_OPTIONAL_FIELDS))
        if unknown:
            raise CaseValidationError(
                "CASE_UNKNOWN_FIELD", f"unexpected additionalProperties: {unknown}"
            )
        missing = [field for field in _CASE_REQUIRED_FIELDS if field not in data]
        if missing:
            raise CaseValidationError("CASE_MISSING_FIELD", f"missing required fields: {missing}")
        raw_evidence = data["evidence"]
        if not isinstance(raw_evidence, list) or not raw_evidence:
            raise CaseValidationError(
                "CASE_NO_EVIDENCE", "evidence must be a non-empty array of evidence pointers"
            )
        evidence = tuple(_evidence_ref_from_dict(item) for item in raw_evidence)
        return cls(
            schema_version=data["schema_version"],
            case_id=data["case_id"],
            case_family=data["case_family"],
            independent_unit_id=data["independent_unit_id"],
            unit_kind=data["unit_kind"],
            backend=data["backend"],
            source_sha=data["source_sha"],
            seed=data["seed"],
            branch=data["branch"],
            arm_id=data["arm_id"],
            evidence=evidence,
            created_at=data.get("created_at"),
            notes=data.get("notes", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "case_id": self.case_id,
            "case_family": self.case_family,
            "independent_unit_id": self.independent_unit_id,
            "unit_kind": self.unit_kind,
            "backend": self.backend,
            "source_sha": self.source_sha,
            "seed": self.seed,
            "branch": self.branch,
            "arm_id": self.arm_id,
            "evidence": [ref.to_dict() for ref in self.evidence],
            "created_at": self.created_at,
            "notes": self.notes,
        }


def _evidence_ref_from_dict(item: Any) -> EvidenceRef:
    if not isinstance(item, Mapping):
        raise CaseValidationError(
            "EVIDENCE_NOT_AN_OBJECT", f"expected an object, got {type(item).__name__}"
        )
    unknown = sorted(set(item) - set(_EVIDENCE_REQUIRED_FIELDS) - set(_EVIDENCE_OPTIONAL_FIELDS))
    if unknown:
        raise CaseValidationError(
            "EVIDENCE_UNKNOWN_FIELD", f"unexpected additionalProperties: {unknown}"
        )
    missing = [field for field in _EVIDENCE_REQUIRED_FIELDS if field not in item]
    if missing:
        raise CaseValidationError(
            "EVIDENCE_MISSING_FIELD", f"evidence pointer missing fields: {missing}"
        )
    return EvidenceRef(
        pointer_kind=item["pointer_kind"],
        uri=item["uri"],
        sha256=item["sha256"],
        frozen_at=item.get("frozen_at"),
    )


@dataclasses.dataclass(frozen=True)
class HumanAdjudicationRecord:
    """Blinded independent human adjudication of an ambiguous clinical/SoK case.

    Required by ``GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md`` rule 2: for clinical
    vignettes the reviewer must be blinded to the model arm. The reviewer is
    identified by pseudonym only (no emails or real names — PII hygiene).
    """

    reviewer_pseudonym: str
    blinded: bool
    adjudicated_at: str
    verdict: str
    reason_code: str
    case_id: str
    oracle_id: str
    note: str = ""

    def __post_init__(self) -> None:
        pseudonym = self.reviewer_pseudonym
        if not isinstance(pseudonym, str) or not pseudonym.strip():
            raise OracleContractError(
                "ADJUDICATOR_MISSING", "reviewer_pseudonym must be a non-empty pseudonym"
            )
        if "@" in pseudonym or len(pseudonym) > 64:
            raise OracleContractError(
                "ADJUDICATOR_PII",
                "pseudonym must not carry email/real-identity content and must be <= 64 chars",
            )
        if self.blinded is not True:
            raise OracleContractError(
                "REVIEWER_NOT_BLINDED",
                "independent adjudication requires blinding to the model arm (protocol rule 2)",
            )
        _check_rfc3339_utc(self.adjudicated_at, "ADJUDICATION_TIMESTAMP_INVALID")
        if self.verdict not in VERDICT_OUTCOMES:
            raise OracleContractError(
                "ADJUDICATED_VERDICT_INVALID",
                f"verdict {self.verdict!r} not in {sorted(VERDICT_OUTCOMES)}",
            )
        if not REASON_CODE_RE.match(self.reason_code):
            raise OracleContractError(
                "ADJUDICATION_REASON_CODE_INVALID",
                f"reason_code {self.reason_code!r} violates the stable-code pattern",
            )
        if not isinstance(self.case_id, str) or not self.case_id:
            raise OracleContractError("ADJUDICATION_BAD_ID", "case_id must be non-empty")
        if not isinstance(self.oracle_id, str) or not self.oracle_id:
            raise OracleContractError("ADJUDICATION_BAD_ID", "oracle_id must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "reviewer_pseudonym": self.reviewer_pseudonym,
            "blinded": self.blinded,
            "adjudicated_at": self.adjudicated_at,
            "verdict": self.verdict,
            "reason_code": self.reason_code,
            "case_id": self.case_id,
            "oracle_id": self.oracle_id,
            "note": self.note,
        }


@dataclasses.dataclass(frozen=True)
class OracleVerdict:
    """The only truth type an independent oracle may emit.

    ``INDETERMINATE`` means reconcilable ground truth is absent or ambiguous;
    it must be resolved by a blinded :class:`HumanAdjudicationRecord` before
    tallying and is never counted as a safe rejection or a completion.
    """

    outcome: str
    reason_code: str
    evidence_refs: tuple[EvidenceRef, ...]
    oracle_id: str
    case_id: str
    resolved_by: tuple[HumanAdjudicationRecord, ...] = ()

    def __post_init__(self) -> None:
        if self.outcome not in VERDICT_OUTCOMES:
            raise OracleContractError(
                "VERDICT_BAD_OUTCOME", f"outcome {self.outcome!r} not in {sorted(VERDICT_OUTCOMES)}"
            )
        if not REASON_CODE_RE.match(self.reason_code):
            raise OracleContractError(
                "VERDICT_BAD_REASON_CODE",
                f"reason_code {self.reason_code!r} violates the stable-code pattern",
            )
        if not self.evidence_refs:
            raise OracleContractError(
                "VERDICT_NO_EVIDENCE", "at least one frozen evidence pointer is required"
            )
        for ref in self.evidence_refs:
            if not isinstance(ref, EvidenceRef):
                raise OracleContractError(
                    "VERDICT_BAD_EVIDENCE", "evidence_refs entries must be EvidenceRef instances"
                )
        if not isinstance(self.oracle_id, str) or not self.oracle_id:
            raise OracleContractError("VERDICT_BAD_ORACLE_ID", "oracle_id must be non-empty")
        if not isinstance(self.case_id, str) or not self.case_id:
            raise OracleContractError("VERDICT_BAD_CASE_ID", "case_id must be non-empty")

    @property
    def needs_human_adjudication(self) -> bool:
        """True while the outcome is still an unresolvable-by-code INDETERMINATE."""
        return self.outcome == OUTCOME_INDETERMINATE

    def with_human_adjudication(self, record: HumanAdjudicationRecord) -> OracleVerdict:
        """Return a NEW verdict resolved by an independent blinded adjudication.

        The oracle itself is never repaired to match a candidate post hoc: the
        adjudication is recorded as provenance on a fresh immutable verdict.
        """
        if self.outcome != OUTCOME_INDETERMINATE:
            raise OracleContractError(
                "ADJUDICATION_NOT_NEEDED",
                f"outcome {self.outcome} is already countable; adjudication is not applicable",
            )
        if record.case_id != self.case_id:
            raise OracleContractError(
                "ADJUDICATION_CASE_MISMATCH",
                f"record case_id {record.case_id!r} != verdict case_id {self.case_id!r}",
            )
        if record.oracle_id != self.oracle_id:
            raise OracleContractError(
                "ADJUDICATION_ORACLE_MISMATCH",
                f"record oracle_id {record.oracle_id!r} != verdict oracle_id {self.oracle_id!r}",
            )
        outcome = record.verdict
        reason_code = record.reason_code if outcome in (OUTCOME_ADMIT, OUTCOME_REJECT) else (
            self.reason_code
        )
        return dataclasses.replace(
            self, outcome=outcome, reason_code=reason_code, resolved_by=(*self.resolved_by, record)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "reason_code": self.reason_code,
            "evidence_refs": [ref.to_dict() for ref in self.evidence_refs],
            "oracle_id": self.oracle_id,
            "case_id": self.case_id,
            "resolved_by": [record.to_dict() for record in self.resolved_by],
            "needs_human_adjudication": self.needs_human_adjudication,
        }


def assert_countable(verdict: OracleVerdict) -> None:
    """Refuse to tally a verdict that is not a counted ADMIT/REJECT decision.

    An ``INDETERMINATE`` verdict without at least one blinded independent human
    adjudication — or still ambiguous after adjudication — is refused with a
    stable reason code (never a silent safe rejection; outcome-contract
    false-zero ban).
    """
    if verdict.outcome == OUTCOME_INDETERMINATE:
        if not verdict.resolved_by:
            raise OracleContractError(
                "INDETERMINATE_UNADJUDICATED",
                f"case {verdict.case_id!r}: INDETERMINATE requires a blinded "
                "HumanAdjudicationRecord before tallying",
            )
        if verdict.resolved_by[-1].verdict == OUTCOME_INDETERMINATE:
            raise OracleContractError(
                "INDETERMINATE_STILL_AMBIGUOUS",
                f"case {verdict.case_id!r}: latest adjudication did not resolve the outcome",
            )
    if verdict.outcome not in (OUTCOME_ADMIT, OUTCOME_REJECT):
        raise OracleContractError(
            "VERDICT_BAD_OUTCOME", f"uncountable outcome {verdict.outcome!r}"
        )


@runtime_checkable
class Oracle(Protocol):
    """Independent truth source contract: ``evaluate(case) -> OracleVerdict``.

    Implementations must be pure (no hidden clock/randomness/network), must
    derive truth only from frozen labels/persisted state, and must never
    import candidate code (enforced by :func:`assert_oracle_independence`).
    """

    oracle_id: str

    def evaluate(self, case: Case) -> OracleVerdict: ...


@dataclasses.dataclass(frozen=True)
class DeterministicReferenceOracle:
    """Pure reference oracle driven ONLY by a frozen label table.

    The table is keyed by ``(case_family, case_id)`` and copied at construction
    so later external mutation cannot change verdicts. Unlabeled cases yield
    ``INDETERMINATE`` with reason code ``UNLABELED_CASE`` — never a silent
    rejection. ``evaluate`` performs no I/O and uses no clock or randomness.
    """

    oracle_id: str
    labels: Mapping[tuple[str, str], tuple[str, str]]
    evidence_refs: tuple[EvidenceRef, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.oracle_id, str) or not self.oracle_id:
            raise OracleContractError("ORACLE_ID_MISSING", "oracle_id must be non-empty")
        if not self.evidence_refs:
            raise OracleContractError(
                "ORACLE_NO_EVIDENCE", "oracle must declare >= 1 frozen evidence pointer"
            )
        object.__setattr__(self, "labels", dict(self.labels))
        for key, labelled in self.labels.items():
            family, case_id = key
            if not family or not case_id:
                raise OracleContractError(
                    "ORACLE_LABEL_BAD_KEY", f"label key {key!r} must be (family, case_id)"
                )
            outcome, reason_code = labelled
            if outcome not in VERDICT_OUTCOMES:
                raise OracleContractError(
                    "ORACLE_LABEL_BAD_OUTCOME",
                    f"frozen label outcome {outcome!r} not in {sorted(VERDICT_OUTCOMES)}",
                )
            if not REASON_CODE_RE.match(reason_code):
                raise OracleContractError(
                    "ORACLE_LABEL_BAD_REASON",
                    f"frozen label reason_code {reason_code!r} violates the stable-code pattern",
                )

    def evaluate(self, case: Case) -> OracleVerdict:
        labelled = self.labels.get((case.case_family, case.case_id))
        if labelled is None:
            return OracleVerdict(
                outcome=OUTCOME_INDETERMINATE,
                reason_code="UNLABELED_CASE",
                evidence_refs=self.evidence_refs,
                oracle_id=self.oracle_id,
                case_id=case.case_id,
            )
        outcome, reason_code = labelled
        return OracleVerdict(
            outcome=outcome,
            reason_code=reason_code,
            evidence_refs=self.evidence_refs,
            oracle_id=self.oracle_id,
            case_id=case.case_id,
        )


@dataclasses.dataclass(frozen=True)
class IndependenceScanResult:
    """Machine-checkable record of one independence source scan (for audit logs)."""

    ok: bool
    reason_code: str
    oracle_path: str
    candidate_paths: tuple[str, ...]
    imported_module_names: tuple[str, ...]
    dynamic_import_expressions: tuple[str, ...]
    oracle_sha256: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "reason_code": self.reason_code,
            "oracle_path": self.oracle_path,
            "candidate_paths": list(self.candidate_paths),
            "imported_module_names": list(self.imported_module_names),
            "dynamic_import_expressions": list(self.dynamic_import_expressions),
            "oracle_sha256": self.oracle_sha256,
            "detail": self.detail,
            "version": ORACLE_CONTRACT_VERSION,
        }


def _module_tokens(path: Path) -> frozenset[str]:
    """All dotted module names that could address ``path`` (absolute-path suffixes)."""
    parts = path.resolve().with_suffix("").parts
    return frozenset(".".join(parts[index:]) for index in range(len(parts)))


def _classify_candidate(path: Path) -> str:
    """Baseline label modules (stem starting with ``baseline``) get their own code."""
    return "baseline" if path.stem.startswith("baseline") else "candidate"


def _name_matches_token(name: str, token: str) -> bool:
    return name == token or name.endswith("." + token) or token.startswith(name + ".")


def _imported_targets(
    tree: ast.Module, oracle_path: Path
) -> tuple[set[str], set[str], set[str]]:
    """Collect (static import targets, unresolved dynamic imports, unresolved relative).

    Relative imports are resolved against the scanned file's own directory
    chain, so ``from ._fixtures import candidate_arm`` inside the oracle
    package yields the same dotted suffixes as the candidate file itself.
    """
    package_parts = [part for part in oracle_path.resolve().parent.parts if part not in ("/",)]
    names: set[str] = set()
    dynamic: set[str] = set()
    unresolved: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            level = node.level or 0
            if level:
                drop = level - 1
                if drop > len(package_parts):
                    unresolved.add(f"relative import level {level} in {oracle_path.name}")
                    continue
                base_parts = package_parts[: len(package_parts) - drop]
            else:
                base_parts = []
            if node.module is not None:
                base_parts = base_parts + node.module.split(".")
                names.add(".".join(base_parts))
            for alias in node.names:
                if alias.name != "*":
                    names.add(".".join(base_parts + [alias.name]))
        elif isinstance(node, ast.Call):
            func = node.func
            is_import_module = (isinstance(func, ast.Attribute) and func.attr == "import_module") or (
                isinstance(func, ast.Name) and func.id in ("import_module", "__import__")
            )
            if is_import_module and node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    names.add(arg.value)
                else:
                    dynamic.add(ast.unparse(arg))
    return names, dynamic, unresolved


def assert_oracle_independence(
    oracle_path: str | Path,
    candidate_paths: Sequence[str | Path],
) -> IndependenceScanResult:
    """Prove the oracle source imports no candidate/baseline module; else fail closed.

    The oracle source is parsed with :mod:`ast` (never executed) and every
    static import, relative import and constant-string dynamic import target
    is matched against the dotted module names addressable by each
    candidate/baseline path. Raises :class:`OracleIndependenceError` with
    reason code ``CANDIDATE_IMPORT`` (candidate code in the oracle) or
    ``BASELINE_LABEL_EXCHANGE`` (baseline truth labels in the oracle);
    unparseable/missing sources and unresolvable dynamic imports also fail
    closed. Returns an :class:`IndependenceScanResult` for audit logs.
    """
    path = Path(oracle_path)
    if not path.is_file():
        raise OracleIndependenceError(
            "ORACLE_SOURCE_MISSING", f"oracle source not found: {path}"
        )
    source = path.read_text(encoding="utf-8")
    oracle_sha256 = hashlib.sha256(source.encode("utf-8")).hexdigest()
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        raise OracleIndependenceError(
            "ORACLE_SOURCE_UNPARSEABLE", f"{path}:{exc.lineno}: {exc.msg}"
        ) from exc

    candidates = [Path(item) for item in candidate_paths]
    missing = [str(item) for item in candidates if not item.is_file()]
    if missing:
        raise OracleIndependenceError(
            "CANDIDATE_PATH_MISSING", f"candidate/baseline modules not found: {missing}"
        )

    names, dynamic, unresolved = _imported_targets(tree, path)
    forbidden = [(_module_tokens(item), _classify_candidate(item), item) for item in candidates]
    for name in sorted(names):
        for tokens, kind, candidate in forbidden:
            for token in sorted(tokens):
                if _name_matches_token(name, token):
                    code = "BASELINE_LABEL_EXCHANGE" if kind == "baseline" else "CANDIDATE_IMPORT"
                    raise OracleIndependenceError(
                        code,
                        f"oracle {path.name} imports {name!r}, which resolves to "
                        f"{kind} module {candidate}",
                    )
    if dynamic:
        raise OracleIndependenceError(
            "DYNAMIC_IMPORT_UNRESOLVABLE",
            f"oracle {path.name} uses dynamic imports whose targets cannot be proven "
            f"independent: {sorted(dynamic)}",
        )
    if unresolved:
        raise OracleIndependenceError(
            "RELATIVE_IMPORT_UNRESOLVABLE",
            f"oracle {path.name} has relative imports outside its package: {sorted(unresolved)}",
        )
    return IndependenceScanResult(
        ok=True,
        reason_code="OK",
        oracle_path=str(path),
        candidate_paths=tuple(str(item) for item in candidates),
        imported_module_names=tuple(sorted(names)),
        dynamic_import_expressions=(),
        oracle_sha256=oracle_sha256,
        detail=(
            f"clean scan: {len(names)} static import target(s) parsed from {path.name}, "
            f"no candidate/baseline module overlap"
        ),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI: ``scan <oracle_path> <candidate_path>...`` — exit 0 clean, 1 refused."""
    parser = argparse.ArgumentParser(description="CLARA 2027 independent-oracle contract CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)
    scan = sub.add_parser("scan", help="assert oracle source independence (AST import scan)")
    scan.add_argument("oracle_path")
    scan.add_argument("candidate_paths", nargs="+")
    args = parser.parse_args(argv)
    if args.cmd == "scan":
        try:
            result = assert_oracle_independence(args.oracle_path, args.candidate_paths)
        except OracleIndependenceError as exc:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "reason_code": exc.reason_code,
                        "detail": exc.detail,
                        "version": ORACLE_CONTRACT_VERSION,
                    }
                )
            )
            return 1
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    import sys

    sys.exit(main())
