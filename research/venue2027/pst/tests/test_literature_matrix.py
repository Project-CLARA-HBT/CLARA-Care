"""Structural gate for PST-prior (literature_matrix.csv).

Purpose
-------
Machine-checks task ``PST-prior`` (venue ``pst``, phase ``P01``) against the
deliverable contract: ``research/venue2027/pst/literature_matrix.csv`` must be
a valid comparator matrix under the SHARED validator
``research/venue2027/_shared/tools/comparator_matrix.py`` (imported, not
reimplemented), and must additionally contain the venue-specific comparators
the PST novelty contract names:

- registry ids ``ct9162`` (CL-1 transparency-log arm B3 source),
  ``macaroons14`` (CL-2 HMAC commitment lineage), ``zanzibar19`` (CL-7
  consistency reference), ``fhir5`` (CL-3 audit schema), ``muse`` (CL-4
  unlearning boundary), ``rats9334`` (CL-5 evidence roles), ``nistabac``
  (CL-6 ABAC vocabulary), ``who21`` (CL-8 governance), ``openfga``
  (executable Zanzibar-consistency comparator), ``injecagent24``
  (dispatch-path attack boundary);
- every blueprint arm ``B0``-``B4`` (B4 = ReceiptMin candidate, recorded for
  falsification transparency, never presented as an external comparator).

Primary-endpoint framing: the suite asserts the deliverable is a
*reconstructability* measurement ledger - the endpoint is the forensic
reconstructability score on the reconstruction-versus-linkability frontier -
and NOT a new access-control or authorization enforcement mechanism (the
novelty contract forbids exactly that claim pattern).

Adversarial controls (executed against the shared validator, not copies of
it): an unknown comparator id, an ``available_code=yes`` row without
``code_url``, a thin ``mechanism_analysis``, and an ``ORIGINAL_UPSTREAM`` row
without code must all fail loudly with the shared validator's stable reason
codes - citing a nonexistent implementation must never pass silently.

Allowed input
-------------
Read-only access to the matrix CSV, ``MANIFESTS/literature_registry.json`` and
``_shared/baselines/registry.yaml``. No network, no database, no provider
calls, no randomness.

Version
-------
``pst-literature-matrix-test-v1``
"""

from __future__ import annotations

import csv
import json
import pathlib
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[2] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import comparator_matrix as cm  # noqa: E402

PST_DIR = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = PST_DIR.parents[2]

MATRIX = PST_DIR / "literature_matrix.csv"
NOVELTY_CONTRACT = PST_DIR / "novelty_contract.md"
THREAT_MODEL = PST_DIR / "threat_model.md"
LITERATURE_REGISTRY = (
    REPO_ROOT / "research" / "venue2027" / "MANIFESTS" / "literature_registry.json"
)
BASELINE_REGISTRY = REPO_ROOT / "research" / "venue2027" / "_shared" / "baselines" / "registry.yaml"

# Novelty-contract claim matrix (CL-1..CL-10) anchors that MUST appear as rows.
REQUIRED_REGISTRY_IDS = (
    "ct9162",  # CL-1: RFC 9162 transparency-log integrity (arm B3 source)
    "macaroons14",  # CL-2: Macaroon HMAC capability / commitment identifier lineage
    "zanzibar19",  # CL-7: Zanzibar-consistency design reference
    "fhir5",  # CL-3: FHIR R5 AuditEvent/Provenance schema boundary
    "muse",  # CL-4: machine-unlearning evaluation boundary
    "rats9334",  # CL-5: RATS evidence/attester/verifier role boundary
    "nistabac",  # CL-6: NIST ABAC purpose/attribute vocabulary
    "who21",  # CL-8: WHO ethics/governance guidance boundary
    "openfga",  # executable Zanzibar-consistency comparator (CL-7 cross-check)
    "injecagent24",  # dispatch-path prompt-injection boundary (excluded domain)
)

# Blueprint arms (B4 is the candidate itself, still required as a row).
REQUIRED_ARM_PREFIXES = ("B0-", "B1-", "B2-", "B3-", "B4-")

# Shared-baseline-registry arm entries backing the B-prefixed rows.
REQUIRED_ARM_REGISTRY_NAMES = (
    "full-plaintext-append-only-log",
    "hash-only-log-digests",
    "encrypted-log-role-gated-deletion",
    "ct-merkle-append-only-integrity",
)

FORBIDDEN_MECHANISM_CLAIMS = (
    "we introduce a new access-control mechanism",
    "we propose a new access-control mechanism",
    "novel access-control mechanism",
    "new authorization enforcement mechanism",
)


def _load_matrix() -> list[dict[str, str]]:
    if not MATRIX.is_file():
        raise AssertionError(f"MISSING_MATRIX: expected {MATRIX}")
    with MATRIX.open(newline="", encoding="utf-8") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _baseline_registry_names() -> set[str]:
    if not BASELINE_REGISTRY.is_file():
        raise AssertionError(f"MISSING_BASELINE_REGISTRY: expected {BASELINE_REGISTRY}")
    names: set[str] = set()
    for line in BASELINE_REGISTRY.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("- name:") or stripped.startswith("name:"):
            names.add(stripped.split("name:", 1)[1].strip().strip('"'))
    return names


def _validate_shared() -> cm.MatrixResult:
    """Run the shared comparator-matrix validator over the real CSV."""
    known = cm.load_registry_ids(LITERATURE_REGISTRY)
    return cm.validate_matrix(MATRIX.read_text(encoding="utf-8"), known_registry_ids=known)


def test_shared_validator_passes_on_real_matrix() -> None:
    result = _validate_shared()
    assert result.ok is True, result.to_dict()
    assert result.row_count >= len(REQUIRED_REGISTRY_IDS) + len(REQUIRED_ARM_PREFIXES), (
        f"TOO_FEW_ROWS: {result.row_count}"
    )


def test_matrix_uses_exactly_the_shared_required_columns() -> None:
    with MATRIX.open(newline="", encoding="utf-8") as fh:
        columns = next(csv.reader(fh))
    assert tuple(columns) == cm.REQUIRED_COLUMNS, f"unexpected columns: {columns}"


def test_required_registry_ids_present() -> None:
    ids = {row["comparator_id"] for row in _load_matrix()}
    for lit_id in REQUIRED_REGISTRY_IDS:
        assert lit_id in ids, f"MISSING_REGISTRY_ROW:{lit_id}"


def test_all_blueprint_arms_present() -> None:
    ids = [row["comparator_id"] for row in _load_matrix()]
    for prefix in REQUIRED_ARM_PREFIXES:
        assert any(cid.startswith(prefix) for cid in ids), f"MISSING_ARM:{prefix}"


def test_arm_rows_map_to_shared_baseline_registry_entries() -> None:
    registry_names = _baseline_registry_names()
    for arm_name in REQUIRED_ARM_REGISTRY_NAMES:
        assert arm_name in registry_names, f"REGISTRY_ANCHOR_MISSING:{arm_name}"


def test_candidate_arm_b4_not_claimed_as_external_comparator() -> None:
    for row in _load_matrix():
        if row["comparator_id"].startswith("B4-"):
            assert row["available_code"] != "yes", (
                "B4_CANDIDATE_CLAIMS_AVAILABLE_CODE: candidate must not be "
                "presented as a runnable external comparator"
            )
            assert "candidate" in (row["mechanism_analysis"] or "").lower(), (
                "B4_CANDIDATE_NOT_LABELLED"
            )


def test_available_code_yes_rows_cite_verified_upstream_code() -> None:
    for row in _load_matrix():
        if row["available_code"] == "yes":
            url = row["code_url"].strip()
            assert url.startswith(("http://", "https://")), (
                f"AVAILABLE_CODE_WITHOUT_CODE_URL:{row['comparator_id']}"
            )
            assert row["fidelity_status"] in cm.FIDELITY_STATUSES


def test_registry_rows_cite_the_registered_source_locator() -> None:
    registry = json.loads(LITERATURE_REGISTRY.read_text(encoding="utf-8"))
    for row in _load_matrix():
        entry = registry.get(row["comparator_id"])
        if entry is None:
            continue
        registered = entry.get("url", "").strip()
        cited = row["doi_or_url"].strip()
        assert cited == registered, (
            f"{row['comparator_id']} cites {cited!r} but the registry has {registered!r}"
        )


def test_primary_endpoint_is_reconstructability_not_disclosure() -> None:
    """Endpoint framing: the study's primary endpoint is forensic
    reconstructability (RQ1 answerability of the frozen forensic query set,
    scored against the independent oracle ledger), reported jointly with
    RQ2 exposure bounds - not a disclosure rate, crash-consistency rate,
    replay acceptance rate or any other venue's endpoint."""
    contract = NOVELTY_CONTRACT.read_text(encoding="utf-8")
    assert "forensic reconstructability score" in contract, (
        "ENDPOINT_NOT_DECLARED: primary endpoint must be the forensic reconstructability score"
    )
    assert "reconstruction-versus-linkability frontier" in contract, "FRONTIER_NOT_DECLARED"
    # The measured object is reconstructability, explicitly not sibling endpoints.
    for other in (
        "not a disclosure rate",
        "not a crash-consistency",
        "not a replay acceptance rate",
        "not an evidence-coverage matrix",
        "not a conformance-divergence rate",
        "not a detection AUC",
        "not an unsafe-clinical-action rate",
    ):
        assert other in contract, f"ENDPOINT_DISAMBIGUATION_MISSING:{other}"


def test_primary_endpoint_is_not_a_new_access_control_mechanism() -> None:
    """Novelty-contract boundary: ReceiptMin is a measurement framework plus an
    evaluation artifact; the receipt format (B4) is an experimental instrument,
    never a new access-control or authorization enforcement mechanism."""
    contract = NOVELTY_CONTRACT.read_text(encoding="utf-8")
    assert "does not propose a new access-control mechanism" in contract, (
        "ACCESS_CONTROL_BOUNDARY_NOT_DECLARED"
    )
    # No row may state a forbidden claim pattern.
    for row in _load_matrix():
        blob = " ".join(row.values()).lower()
        for pattern in FORBIDDEN_MECHANISM_CLAIMS:
            assert pattern not in blob, (
                f"FORBIDDEN_ACCESS_CONTROL_CLAIM:{row['comparator_id']}:{pattern}"
            )
    # The B4 candidate row and the threat model must state the instrument boundary.
    b4_rows = [r for r in _load_matrix() if r["comparator_id"].startswith("B4-")]
    assert len(b4_rows) == 1, "B4 arm must appear exactly once"
    b4_blob = b4_rows[0]["mechanism_analysis"].lower()
    assert "evaluation instrument" in b4_blob and "not a new access-control" in b4_blob, (
        "B4_BOUNDARY_NOT_ASSERTED"
    )
    threat = THREAT_MODEL.read_text(encoding="utf-8")
    assert "no new access-control or authorization enforcement mechanism" in threat, (
        "THREAT_MODEL_BOUNDARY_NOT_ASSERTED"
    )


def test_oracle_and_baseline_falsification_framing_intact() -> None:
    """The deliverable must preserve the strongest competing explanation (B2
    encrypted full log) and the study-level falsification rule - the matrix
    may never pre-empt the falsification path."""
    contract = NOVELTY_CONTRACT.read_text(encoding="utf-8")
    assert "study-level falsification rule" in contract
    matrix_text = MATRIX.read_text(encoding="utf-8").lower()
    assert "falsification" in matrix_text or "dominates" in matrix_text, (
        "FALSIFICATION_FRAMING_MISSING in matrix"
    )
    b2 = [r for r in _load_matrix() if r["comparator_id"].startswith("B2-")]
    assert len(b2) == 1
    assert "falsification" in b2[0]["mechanism_analysis"].lower() or "dominan" in (
        b2[0]["mechanism_analysis"].lower()
    ), "B2 must carry the dominant-competing-explanation framing"


# ---------------------------------------------------------------------------
# Adversarial controls: the SHARED validator must reject each tampered matrix.
# ---------------------------------------------------------------------------


def _tampered(tamper_row: dict[str, str]) -> str:
    """Serialize one tampered row appended after the real matrix rows."""
    lines = [",".join(cm.REQUIRED_COLUMNS)]
    for row in _load_matrix():
        quoted = [f'"{v}"' if ("," in v or '"' in v) else v for v in row.values()]
        lines.append(",".join(quoted))
    quoted = [f'"{v}"' if ("," in v or '"' in v) else v for v in tamper_row.values()]
    lines.append(",".join(quoted))
    return "\n".join(lines) + "\n"


def test_adversarial_unknown_comparator_id_fails() -> None:
    known = cm.load_registry_ids(LITERATURE_REGISTRY)
    bad = _tampered(
        {
            "comparator_id": "made-up-audit-frontier-2049",
            "title": "Fabricated citation",
            "venue": "Nowhere",
            "doi_or_url": "https://example.org/fake",
            "code_url": "",
            "algorithm_class": "audit minimization",
            "supported_guarantee": "guarantee",
            "limitations_vs_candidate": "limits",
            "available_code": "no",
            "fidelity_status": "UNAVAILABLE_NOT_RUN",
            "mechanism_analysis": "x" * 60,
        }
    )
    result = cm.validate_matrix(bad, known_registry_ids=known)
    assert result.ok is False, result.to_dict()
    assert "UNKNOWN_COMPARATOR_ID" in result.reason_codes


def test_adversarial_available_code_yes_without_code_url_fails() -> None:
    known = cm.load_registry_ids(LITERATURE_REGISTRY)
    bad = _tampered(
        {
            "comparator_id": "B0-full-plaintext-append-only-log",
            "title": "Broken provenance",
            "venue": "test",
            "doi_or_url": "https://example.org/x",
            "code_url": "",
            "algorithm_class": "audit log",
            "supported_guarantee": "guarantee",
            "limitations_vs_candidate": "limits",
            "available_code": "yes",
            "fidelity_status": "ORIGINAL_UPSTREAM",
            "mechanism_analysis": "x" * 60,
        }
    )
    result = cm.validate_matrix(bad, known_registry_ids=known)
    assert result.ok is False, result.to_dict()
    assert "AVAILABLE_CODE_WITHOUT_URL" in result.reason_codes


def test_adversarial_thin_mechanism_analysis_fails() -> None:
    known = cm.load_registry_ids(LITERATURE_REGISTRY)
    bad = _tampered(
        {
            "comparator_id": "ct9162",
            "title": "Certificate Transparency",
            "venue": "IETF RFC 9162",
            "doi_or_url": "https://www.rfc-editor.org/rfc/rfc9162.html",
            "code_url": "",
            "algorithm_class": "transparency log",
            "supported_guarantee": "guarantee",
            "limitations_vs_candidate": "limits",
            "available_code": "no",
            "fidelity_status": "UNAVAILABLE_NOT_RUN",
            "mechanism_analysis": "weak",
        }
    )
    result = cm.validate_matrix(bad, known_registry_ids=known)
    assert result.ok is False, result.to_dict()
    assert "MECHANISM_ANALYSIS_MISSING" in result.reason_codes


def test_adversarial_original_upstream_without_code_fails() -> None:
    known = cm.load_registry_ids(LITERATURE_REGISTRY)
    bad = _tampered(
        {
            "comparator_id": "macaroons14",
            "title": "Macaroons",
            "venue": "NDSS 2014",
            "doi_or_url": "https://example.org/macaroons",
            "code_url": "",
            "algorithm_class": "capability tokens",
            "supported_guarantee": "guarantee",
            "limitations_vs_candidate": "limits",
            "available_code": "no",
            "fidelity_status": "ORIGINAL_UPSTREAM",
            "mechanism_analysis": "x" * 60,
        }
    )
    result = cm.validate_matrix(bad, known_registry_ids=known)
    assert result.ok is False, result.to_dict()
    assert "UPSTREAM_WITHOUT_CODE" in result.reason_codes
