"""PST-X03_minimization — purpose-bound receipt minimizer (ReceiptMin B4).

Purpose
-------
Field-level purpose-bound minimization of synthetic audit-receipt records for
the PST 2027 study "ReceiptMin: Measuring Forensic Reconstructability under
Purpose-Bound Audit Minimization" (``research/venue2027/VENUES/pst/
RESEARCH_BLUEPRINT.md`` RQ2; task contract ``research/venue2027/VENUES/pst/
TASKS/PST-X03_minimization.md``; threat model ``research/venue2027/pst/
threat_model.md``). :func:`minimize` projects one synthetic commit record onto
the field-level allowlist of the declared processing purpose:

- **Field-level allowlist per purpose** — only fields registered for the
  purpose survive; anything else present in the record is dropped
  observably (``dropped_fields`` with ``NOT_IN_ALLOWLIST``), never silently.
- **Keyed one-way pseudonyms** — the raw subject reference never reaches the
  receipt; it is replaced by ``psn_<hex>`` computed as HMAC-SHA256 under an
  injected key. Unsalted digests of patient identifiers (bare 32/40/64-hex
  strings or ``md5:``/``sha1:``/``sha256:``-prefixed forms) are REFUSED with
  ``UNSALTED_HASH_REFUSED``: an unkeyed digest of a low-entropy identifier is
  dictionary-attackable under the P2 auxiliary-join adversary (threat model,
  linkability_leakage family) and must never pose as pseudonymization.
- **Retention-window enforcement** — decaying content fields
  (``evidence_digest`` 30 days, ``witness_id`` 90 days) are dropped once
  ``now >= created_at + window`` (``RETENTION_EXPIRED``) while commitment and
  consent/policy-epoch proofs persist (the ReceiptMin design point: at the
  retention deadline the retention map drops declared content, the
  commitment and epoch proofs remain).
- **Controlled escape for authorized audits** — an explicit
  :class:`EscapeRequest` against the registered grant registry can restore
  allowlisted-out or decayed fields, but only when the grant id, the
  authority id, the purpose coverage, the validity window and a non-empty
  justification all check out, and only when the caller supplies an
  escape-log sink. The decision — granted or refused — is appended to that
  sink with a keyed ``escape_ref``; a sink-less escape is refused outright
  (``ESCAPE_LOG_REQUIRED``). An escape is never silent and never implicit.

Allowed input
-------------
``record``: a JSON-serializable mapping over the fixed synthetic field
vocabulary :data:`RECORD_FIELDS` (identity fields ``operation_id``,
``subject_ref``, ``created_at`` required; values must be strings; unknown
field names are refused with ``UNRECOGNIZED_FIELD`` so no hidden-ID side
channel exists; PHI-marker field names are refused with
``PHI_FIELD_PRESENT``). ``purpose``: one of :data:`PURPOSES` (the PST
receipt-contract enum). ``now``: the injected audit clock as an RFC 3339 UTC
``Z`` timestamp — no hidden clock. ``pseudonym_key``: injected HMAC key
(``bytes``); when omitted a documented synthetic evaluation key is used
(this is an evaluation instrument, X6 synthetic-only; production deployments
must inject a custody-managed key). ``escape`` / ``escape_log``: the explicit
escape request and its mandatory injected log sink. No network, no database,
no randomness, no environment reads; all fixtures are synthetic and PHI-free.

Failure semantics
-----------------
Every refusal is a :class:`MinimizationError` carrying a stable uppercase
reason code: ``UNKNOWN_PURPOSE``, ``UNSALTED_HASH_REFUSED``,
``MALFORMED_RECORD``, ``UNRECOGNIZED_FIELD``, ``PHI_FIELD_PRESENT``,
``PSEUDONYM_KEY_REQUIRED``, ``MALFORMED_ESCAPE``, ``ESCAPE_NOT_AUTHORIZED``,
``ESCAPE_LOG_REQUIRED``. Committer under-commitment (a missing mandatory
proof field, the model_agency surface of the threat model) is NOT a refusal:
it is reported as ``missing_mandatory_fields`` incompleteness on the receipt
and is never silently repaired nor coerced into a complete receipt.

Version
-------
``PURPOSE_MINIMIZER_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
import datetime
import hashlib
import hmac
import json
import re
from collections.abc import Mapping
from typing import Any, Final

from evaluation.venue2027._shared.dataset_kernel import PHI_FIELD_MARKERS

PURPOSE_MINIMIZER_VERSION: Final[str] = "1.0.0"

MINIMIZED_RECEIPT_SCHEMA_VERSION: Final[str] = "clara.venue2027.pst.minimized_receipt.v1"

# --- stable reason codes (never bare exceptions) ------------------------------

REASON_UNKNOWN_PURPOSE: Final[str] = "UNKNOWN_PURPOSE"
REASON_UNSALTED_HASH_REFUSED: Final[str] = "UNSALTED_HASH_REFUSED"
REASON_MALFORMED_RECORD: Final[str] = "MALFORMED_RECORD"
REASON_UNRECOGNIZED_FIELD: Final[str] = "UNRECOGNIZED_FIELD"
REASON_PHI_FIELD_PRESENT: Final[str] = "PHI_FIELD_PRESENT"
REASON_PSEUDONYM_KEY_REQUIRED: Final[str] = "PSEUDONYM_KEY_REQUIRED"
REASON_MALFORMED_ESCAPE: Final[str] = "MALFORMED_ESCAPE"
REASON_ESCAPE_NOT_AUTHORIZED: Final[str] = "ESCAPE_NOT_AUTHORIZED"
REASON_ESCAPE_LOG_REQUIRED: Final[str] = "ESCAPE_LOG_REQUIRED"

# --- observable drop reasons (a dropped field is always explained) ------------

DROP_NOT_IN_ALLOWLIST: Final[str] = "NOT_IN_ALLOWLIST"
DROP_RETENTION_EXPIRED: Final[str] = "RETENTION_EXPIRED"

ESCAPE_DECISION_GRANTED: Final[str] = "GRANTED"
ESCAPE_DECISION_REFUSED: Final[str] = "REFUSED"


class MinimizationError(ValueError):
    """Refusal with a stable, machine-checkable reason code."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(f"{reason_code}: {message}")
        self.reason_code = reason_code


# --- synthetic record vocabulary (PST receipt contract, PHI-free) -------------

RECORD_IDENTITY_FIELDS: Final[tuple[str, ...]] = ("operation_id", "subject_ref", "created_at")

RECORD_CONTENT_FIELDS: Final[tuple[str, ...]] = (
    "commitment_digest",
    "purpose_tag",
    "consent_epoch",
    "policy_epoch",
    "witness_id",
    "retention_mode",
    "evidence_digest",
)

RECORD_FIELDS: Final[tuple[str, ...]] = RECORD_IDENTITY_FIELDS + RECORD_CONTENT_FIELDS

#: Proof fields a complete receipt must carry (the forensic-query mandatory
#: set: commitment + consent/policy epoch proofs). Absence is reported as
#: incompleteness (``missing_mandatory_fields``), never repaired.
MANDATORY_PROOF_FIELDS: Final[tuple[str, ...]] = (
    "commitment_digest",
    "consent_epoch",
    "policy_epoch",
)

PURPOSES: Final[tuple[str, ...]] = (
    "self_care",
    "clinical_care",
    "forensic_review",
    "security_audit",
    "research_analytics",
)

_PROOF_ONLY: Final[frozenset[str]] = frozenset(
    {"commitment_digest", "purpose_tag", "consent_epoch", "policy_epoch", "retention_mode"}
)

#: Field-level allowlist per declared purpose (PST receipt-contract enum).
#: Proof fields persist under every purpose; content fields are granted only
#: where the purpose legitimately needs them.
PURPOSE_ALLOWLISTS: Final[Mapping[str, frozenset[str]]] = {
    "self_care": _PROOF_ONLY,
    "clinical_care": _PROOF_ONLY | {"witness_id", "evidence_digest"},
    "forensic_review": _PROOF_ONLY | {"witness_id"},
    "security_audit": _PROOF_ONLY | {"witness_id"},
    "research_analytics": _PROOF_ONLY,
}

#: Proof fields that never decay (the ReceiptMin design point: the retention
#: deadline drops declared content while commitment and epoch proofs persist).
PERSISTENT_PROOF_FIELDS: Final[frozenset[str]] = _PROOF_ONLY

#: Retention windows of decaying content fields, counted from ``created_at``.
DECAYING_FIELD_WINDOWS: Final[Mapping[str, datetime.timedelta]] = {
    "evidence_digest": datetime.timedelta(days=30),
    "witness_id": datetime.timedelta(days=90),
}

# --- keyed one-way pseudonyms ---------------------------------------------------

PSEUDONYM_PREFIX: Final[str] = "psn_"

#: Synthetic evaluation key used when the caller injects none. Constant and
#: documented on purpose: this is a PHI-free evaluation instrument, never a
#: production secret. Real deployments must inject a custody-managed key.
DEFAULT_PSEUDONYM_KEY: Final[bytes] = b"clara-pst-2027-receiptmin-synthetic-evaluation-key"

#: Bare MD5/SHA-1/SHA-256 hex digests — unsalted hashes of patient
#: identifiers are dictionary-attackable weak identifiers and are refused.
_UNSALTED_DIGEST: Final[re.Pattern[str]] = re.compile(
    r"^(?:[0-9a-fA-F]{32}|[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$"
)

#: The same digests behind common algorithm prefixes.
_UNSALTED_PREFIXED: Final[re.Pattern[str]] = re.compile(
    r"^(?:md5|sha-?1|sha-?256)[:_][0-9a-fA-F]+$"
)


def _refuse_unsalted_hash(subject_ref: str) -> None:
    """Refuse unkeyed digests of patient identifiers (``UNSALTED_HASH_REFUSED``)."""

    if _UNSALTED_DIGEST.match(subject_ref) or _UNSALTED_PREFIXED.match(subject_ref):
        raise MinimizationError(
            REASON_UNSALTED_HASH_REFUSED,
            "subject_ref is an unkeyed digest of a patient identifier "
            "(dictionary-attackable under auxiliary joins); pseudonymization "
            "must go through the keyed HMAC path",
        )


def pseudonymize(subject_ref: str, key: bytes) -> str:
    """Keyed one-way pseudonym: ``psn_`` + HMAC-SHA256(key, subject_ref)[:32].

    Stable for the same (subject, key) pair, unlinkable across keys, and
    unverifiable by anyone without the key. Refuses empty/ill-typed keys
    (``PSEUDONYM_KEY_REQUIRED``) and unsalted patient-hash inputs
    (``UNSALTED_HASH_REFUSED``).
    """

    if not isinstance(subject_ref, str) or not subject_ref.strip():
        raise MinimizationError(REASON_MALFORMED_RECORD, "subject_ref must be a non-empty string")
    if not isinstance(key, bytes) or not key:
        raise MinimizationError(
            REASON_PSEUDONYM_KEY_REQUIRED, "pseudonym key must be non-empty bytes"
        )
    _refuse_unsalted_hash(subject_ref)
    digest = hmac.new(key, subject_ref.encode("utf-8"), hashlib.sha256).hexdigest()
    return PSEUDONYM_PREFIX + digest[:32]


# --- timestamps (RFC 3339 UTC 'Z' only, receipt-contract discipline) -----------

_TIMESTAMP_PATTERN: Final[re.Pattern[str]] = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _parse_timestamp(value: Any, field: str) -> datetime.datetime:
    if not isinstance(value, str) or not _TIMESTAMP_PATTERN.match(value):
        raise MinimizationError(
            REASON_MALFORMED_RECORD, f"{field} must be an RFC 3339 UTC timestamp with 'Z' suffix"
        )
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))


def _format_timestamp(moment: datetime.datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


# --- controlled escape for authorized audits ------------------------------------


@dataclasses.dataclass(frozen=True)
class EscapeRequest:
    """Explicit, caller-declared escape attempt (never implicit, never silent)."""

    grant_id: str
    authority_id: str
    justification: str


@dataclasses.dataclass(frozen=True)
class EscapeGrant:
    """One registered authorized-audit grant."""

    grant_id: str
    authority_id: str
    purposes: tuple[str, ...]
    allowed_fields: frozenset[str]
    valid_from: datetime.datetime
    valid_until: datetime.datetime


#: Registered authorized-audit grants (synthetic evaluation registry). Every
#: escape attempt is checked against exactly this registry; anything not
#: registered here is refused.
AUTHORIZED_ESCAPE_GRANTS: Final[Mapping[str, EscapeGrant]] = {
    "ESC-GRANT-PST-FORENSIC-01": EscapeGrant(
        grant_id="ESC-GRANT-PST-FORENSIC-01",
        authority_id="pst-evaluation-adjudicator",
        purposes=("forensic_review",),
        allowed_fields=frozenset({"witness_id", "evidence_digest"}),
        valid_from=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        valid_until=datetime.datetime(2030, 1, 1, tzinfo=datetime.UTC),
    ),
}


def _log_escape(
    escape_log: list[dict[str, Any]] | None,
    entry: dict[str, Any],
    key: bytes,
) -> None:
    """Append one sanitized escape-log entry to the injected sink.

    The log never carries the escaped values themselves, only field names and
    the decision; the keyed ``escape_ref`` (HMAC over the decision payload)
    lets an authorized auditor correlate entries without exposing content.
    """

    if escape_log is None:
        return
    payload = json_canonical(entry)
    digest = hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    logged = dict(entry)
    logged["escape_ref"] = "esc_" + digest[:32]
    escape_log.append(logged)


def _authorize_escape(
    escape: EscapeRequest,
    purpose: str,
    now_dt: datetime.datetime,
    key: bytes,
    escape_log: list[dict[str, Any]] | None,
) -> tuple[EscapeGrant, dict[str, Any]]:
    """Grant or refuse an explicit escape attempt; log the decision either way.

    Authorization requires ALL of: a registered grant id, the matching
    authority id, purpose coverage, a valid window at the audit clock, and a
    non-empty justification. Refusals are logged when a sink exists and then
    raise ``ESCAPE_NOT_AUTHORIZED``; a missing sink is refused before any
    authorization check with ``ESCAPE_LOG_REQUIRED`` (an unlogged escape
    could otherwise bypass the controlled-audit discipline silently).
    """

    if escape_log is None:
        raise MinimizationError(
            REASON_ESCAPE_LOG_REQUIRED,
            "an explicit escape requires an injected, durable escape-log sink; "
            "unlogged escapes are refused",
        )
    base_entry: dict[str, Any] = {
        "decision": ESCAPE_DECISION_REFUSED,
        "purpose": purpose,
        "at": _format_timestamp(now_dt),
    }
    if not isinstance(escape, EscapeRequest):
        base_entry["reason_code"] = REASON_MALFORMED_ESCAPE
        _log_escape(escape_log, base_entry, key)
        raise MinimizationError(REASON_MALFORMED_ESCAPE, "escape must be an EscapeRequest")
    base_entry["grant_id"] = escape.grant_id
    base_entry["authority_id"] = escape.authority_id
    if not isinstance(escape.grant_id, str) or not escape.grant_id.strip():
        base_entry["reason_code"] = REASON_MALFORMED_ESCAPE
        _log_escape(escape_log, base_entry, key)
        raise MinimizationError(REASON_MALFORMED_ESCAPE, "grant_id must be a non-empty string")
    if not isinstance(escape.authority_id, str) or not escape.authority_id.strip():
        base_entry["reason_code"] = REASON_MALFORMED_ESCAPE
        _log_escape(escape_log, base_entry, key)
        raise MinimizationError(REASON_MALFORMED_ESCAPE, "authority_id must be a non-empty string")
    if not isinstance(escape.justification, str) or not escape.justification.strip():
        base_entry["reason_code"] = REASON_MALFORMED_ESCAPE
        _log_escape(escape_log, base_entry, key)
        raise MinimizationError(REASON_MALFORMED_ESCAPE, "justification must be a non-empty string")
    grant = AUTHORIZED_ESCAPE_GRANTS.get(escape.grant_id)
    if (
        grant is None
        or grant.authority_id != escape.authority_id
        or purpose not in grant.purposes
        or not (grant.valid_from <= now_dt < grant.valid_until)
    ):
        base_entry["reason_code"] = REASON_ESCAPE_NOT_AUTHORIZED
        _log_escape(escape_log, base_entry, key)
        raise MinimizationError(
            REASON_ESCAPE_NOT_AUTHORIZED,
            f"escape grant {escape.grant_id!r} is not registered for purpose "
            f"{purpose!r} at the audit clock, or the authority does not match",
        )
    granted_entry = {
        **base_entry,
        "decision": ESCAPE_DECISION_GRANTED,
        "reason_code": "OK",
    }
    _log_escape(escape_log, granted_entry, key)
    return grant, granted_entry


# --- minimized receipt ----------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class MinimizedRecord:
    """Schema-approved minimized receipt (JSON-serializable by construction).

    - ``receipt``: only allowlisted/retained fields survive here; the raw
      ``subject_ref`` never appears (replaced by the keyed pseudonym).
    - ``dropped_fields``: field name -> stable drop reason; a dropped field
      is always explained, never silently filtered.
    - ``missing_mandatory_fields``: committer under-commitment reported as
      incompleteness (threat-model model_agency surface), never repaired.
    - ``escape``: ``None`` or the logged escape decision (``GRANTED`` with
      the escaped field names, or the refusal record).
    """

    schema_version: str
    minimizer_version: str
    purpose: str
    minimized_at: str
    operation_id: str
    pseudonym: str
    receipt: dict[str, Any]
    dropped_fields: dict[str, str]
    missing_mandatory_fields: tuple[str, ...]
    escape: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "minimizer_version": self.minimizer_version,
            "purpose": self.purpose,
            "minimized_at": self.minimized_at,
            "operation_id": self.operation_id,
            "pseudonym": self.pseudonym,
            "receipt": dict(self.receipt),
            "dropped_fields": dict(self.dropped_fields),
            "missing_mandatory_fields": list(self.missing_mandatory_fields),
            "escape": dict(self.escape) if self.escape is not None else None,
        }


def json_canonical(value: Any) -> str:
    """Canonical JSON (sorted keys, tight separators) for digests and logs."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def minimize(
    record: Mapping[str, Any],
    purpose: str,
    now: str,
    *,
    pseudonym_key: bytes = DEFAULT_PSEUDONYM_KEY,
    escape: EscapeRequest | None = None,
    escape_log: list[dict[str, Any]] | None = None,
) -> MinimizedRecord:
    """Minimize one synthetic audit record under a declared purpose.

    The pipeline is order-fixed so the outcome is deterministic:

    1. Purpose validation — unknown purposes fail closed (``UNKNOWN_PURPOSE``).
    2. Record validation — mapping shape, identity fields, string values,
       closed field vocabulary (``UNRECOGNIZED_FIELD``), PHI-marker names
       (``PHI_FIELD_PRESENT``), RFC 3339 timestamps.
    3. Escape authorization — when ``escape`` is declared, an injected
       ``escape_log`` sink is mandatory (``ESCAPE_LOG_REQUIRED``) and the
       grant must authorize (``ESCAPE_NOT_AUTHORIZED``); the decision is
       always logged.
    4. Field selection — allowlist per purpose drops out-of-scope fields
       (``NOT_IN_ALLOWLIST``); retention windows drop expired decaying
       content (``RETENTION_EXPIRED``); persistent proofs survive both.
    5. Pseudonymization — HMAC pseudonym replaces the raw subject reference.
    6. Completeness report — missing mandatory proofs are listed, never
       repaired.
    """

    if purpose not in PURPOSES:
        raise MinimizationError(REASON_UNKNOWN_PURPOSE, f"unknown purpose {purpose!r}")
    if not isinstance(record, Mapping):
        raise MinimizationError(REASON_MALFORMED_RECORD, "record must be a mapping")
    phi_fields = sorted(
        field for field in record if any(marker in field.lower() for marker in PHI_FIELD_MARKERS)
    )
    if phi_fields:
        raise MinimizationError(
            REASON_PHI_FIELD_PRESENT, f"fields carrying PHI/PII markers: {phi_fields}"
        )
    unknown_fields = sorted(set(record) - set(RECORD_FIELDS))
    if unknown_fields:
        raise MinimizationError(
            REASON_UNRECOGNIZED_FIELD,
            f"fields outside the closed record vocabulary: {unknown_fields}",
        )
    for identity in RECORD_IDENTITY_FIELDS:
        if identity not in record or not isinstance(record[identity], str) or not record[identity]:
            raise MinimizationError(
                REASON_MALFORMED_RECORD, f"identity field {identity!r} must be a non-empty string"
            )
    for field, value in record.items():
        if not isinstance(value, str):
            raise MinimizationError(
                REASON_MALFORMED_RECORD, f"field {field!r} must carry a string value"
            )
    _refuse_unsalted_hash(record["subject_ref"])
    created_dt = _parse_timestamp(record["created_at"], "created_at")
    now_dt = _parse_timestamp(now, "now")

    escape_decision: dict[str, Any] | None = None
    escaped_fields: frozenset[str] = frozenset()
    if escape is not None:
        grant, escape_decision = _authorize_escape(
            escape, purpose, now_dt, pseudonym_key, escape_log
        )
        escaped_fields = grant.allowed_fields

    allowlist = PURPOSE_ALLOWLISTS[purpose]
    receipt: dict[str, Any] = {}
    dropped: dict[str, str] = {}
    for field in RECORD_CONTENT_FIELDS:
        if field not in record:
            continue
        window = DECAYING_FIELD_WINDOWS.get(field)
        if field not in allowlist and field not in escaped_fields:
            dropped[field] = DROP_NOT_IN_ALLOWLIST
            continue
        if window is not None and field not in escaped_fields:
            deadline = created_dt + window
            if now_dt >= deadline:
                dropped[field] = DROP_RETENTION_EXPIRED
                continue
        receipt[field] = record[field]
    missing_mandatory = tuple(f for f in MANDATORY_PROOF_FIELDS if f not in receipt)
    if escape_decision is not None and escaped_fields:
        escaped_now = sorted(f for f in escaped_fields if f in record and f not in receipt)
        if escaped_now:
            receipt.update({f: record[f] for f in escaped_now})
            for f in escaped_now:
                dropped.pop(f, None)
        escape_decision = {**escape_decision, "escaped_fields": escaped_now}
    return MinimizedRecord(
        schema_version=MINIMIZED_RECEIPT_SCHEMA_VERSION,
        minimizer_version=PURPOSE_MINIMIZER_VERSION,
        purpose=purpose,
        minimized_at=_format_timestamp(now_dt),
        operation_id=record["operation_id"],
        pseudonym=pseudonymize(record["subject_ref"], pseudonym_key),
        receipt=receipt,
        dropped_fields=dropped,
        missing_mandatory_fields=missing_mandatory,
        escape=escape_decision,
    )


__all__ = [
    "AUTHORIZED_ESCAPE_GRANTS",
    "DEFAULT_PSEUDONYM_KEY",
    "DECAYING_FIELD_WINDOWS",
    "DROP_NOT_IN_ALLOWLIST",
    "DROP_RETENTION_EXPIRED",
    "ESCAPE_DECISION_GRANTED",
    "ESCAPE_DECISION_REFUSED",
    "EscapeGrant",
    "EscapeRequest",
    "MANDATORY_PROOF_FIELDS",
    "MINIMIZED_RECEIPT_SCHEMA_VERSION",
    "MinimizationError",
    "MinimizedRecord",
    "PERSISTENT_PROOF_FIELDS",
    "PSEUDONYM_PREFIX",
    "PURPOSES",
    "PURPOSE_ALLOWLISTS",
    "PURPOSE_MINIMIZER_VERSION",
    "REASON_ESCAPE_LOG_REQUIRED",
    "REASON_ESCAPE_NOT_AUTHORIZED",
    "REASON_MALFORMED_ESCAPE",
    "REASON_MALFORMED_RECORD",
    "REASON_PHI_FIELD_PRESENT",
    "REASON_PSEUDONYM_KEY_REQUIRED",
    "REASON_UNKNOWN_PURPOSE",
    "REASON_UNRECOGNIZED_FIELD",
    "REASON_UNSALTED_HASH_REFUSED",
    "RECORD_FIELDS",
    "json_canonical",
    "minimize",
    "pseudonymize",
]
