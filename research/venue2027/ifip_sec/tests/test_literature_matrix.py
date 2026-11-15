"""Structural gate for IFIP_SEC-prior (literature_matrix.csv).

Purpose
-------
Machine-checks task ``IFIP_SEC-prior`` (venue ``ifip_sec``, phase ``P01``)
against the deliverable contract: ``research/venue2027/ifip_sec/literature_matrix.csv``
must be a valid comparator matrix under the SHARED validator
``research/venue2027/_shared/tools/comparator_matrix.py`` (imported, not
reimplemented), and must additionally contain the venue-specific comparators
the IFIP_SEC novelty contract names:

- registry ids ``macaroons14`` (M1/M5 strong token baseline),
  ``zanzibar19`` (M1/M4 consistency design reference), ``openfga``/``cedar``/
  ``opa`` (executable policy-engine comparators), ``rats9334`` (M3 evidence
  boundary), ``nistabac`` (M2 vocabulary), ``elle20`` (RQ2 oracle substrate);
- every blueprint arm ``B0``-``B4`` (B4 = candidate, recorded for falsification
  transparency, never presented as an external comparator).

Adversarial controls (executed against the shared validator, not copies of it):
an unknown comparator id, an ``available_code=yes`` row without ``code_url``,
an ``ORIGINAL_UPSTREAM`` row without code, and a thin ``mechanism_analysis``
must all fail loudly with the shared validator's stable reason codes - citing
a nonexistent implementation must never pass silently.

Allowed input
-------------
Read-only access to the matrix CSV, ``MANIFESTS/literature_registry.json``,
``_shared/baselines/registry.yaml`` and the shared tools directory. No network,
no database, no provider calls, no randomness.

Version
-------
``ifip-sec-literature-matrix-test-v1``
"""

from __future__ import annotations

import csv
import json
import pathlib
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[2] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import comparator_matrix as cm  # noqa: E402

IFIP_DIR = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = IFIP_DIR.parents[2]

MATRIX = IFIP_DIR / "literature_matrix.csv"
LITERATURE_REGISTRY = (
    REPO_ROOT / "research" / "venue2027" / "MANIFESTS" / "literature_registry.json"
)
BASELINE_REGISTRY = REPO_ROOT / "research" / "venue2027" / "_shared" / "baselines" / "registry.yaml"

# Novelty-contract claim matrix (M1-M6) anchors that MUST appear as rows.
REQUIRED_REGISTRY_IDS = (
    "macaroons14",  # M1/M5: Macaroon HMAC caveat strong token baseline (B1 source)
    "zanzibar19",  # M1/M4: consistency-aware authorization design reference
    "openfga",  # M2/M4: executable Zanzibar-consistency comparator (arm B2)
    "cedar",  # M2/M4: executable policy-engine comparator (arm B3 Cedar PDP)
    "opa",  # M2/M4: executable policy-engine comparator (arm B3 alternative PDP)
    "rats9334",  # M3: attester/verifier evidence boundary for lineage binding
    "nistabac",  # M2: normative ABAC purpose/epoch vocabulary
    "elle20",  # RQ2: independent black-box history-checking oracle substrate
)

# Blueprint arms (B4 is the candidate itself, still required as a row).
REQUIRED_ARM_PREFIXES = ("B0-", "B1-", "B2-", "B3-", "B4-")

# Shared-baseline-registry arm entries backing the B-prefixed rows.
REQUIRED_ARM_REGISTRY_NAMES = (
    "bearer-signed-receipt",
    "macaroon-hmac-caveats",
    "zanzibar-openfga",
    "cedar-opa-policy-decision-nonce-registry",
)


def _load_matrix() -> list[dict[str, str]]:
    if not MATRIX.is_file():
        raise AssertionError(f"MISSING_MATRIX: expected {MATRIX}")
    with MATRIX.open(newline="", encoding="utf-8") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _literature_ids() -> set[str]:
    if not LITERATURE_REGISTRY.is_file():
        raise AssertionError(f"MISSING_REGISTRY: expected {LITERATURE_REGISTRY}")
    data = json.loads(LITERATURE_REGISTRY.read_text(encoding="utf-8"))
    return set(cm.load_registry_ids(LITERATURE_REGISTRY)) & set(data) | set(data)


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
        columns = tuple(fh.readline().strip().split(","))
    assert columns == cm.REQUIRED_COLUMNS, f"unexpected columns: {columns}"


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
    for row in _load_matrix():
        cid = row["comparator_id"]
        if not cid.startswith(REQUIRED_ARM_PREFIXES):
            continue
        if cid.startswith("B4-"):
            continue  # candidate arm, no registry baseline exists by design
        matched = any(
            frag in cid
            for frag in (
                "bearer-signed-receipt",
                "macaroon-hmac-caveats",
                "zanzibar-openfga",
                "cedar",
                "nonce-registry",
            )
        )
        assert matched, f"ARM_ROW_WITHOUT_REGISTRY_ANCHOR:{cid}"


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
            "comparator_id": "made-up-macaroon-framework-2049",
            "title": "Fabricated citation",
            "venue": "Nowhere",
            "doi_or_url": "https://example.org/fake",
            "code_url": "",
            "algorithm_class": "capability tokens",
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
            "comparator_id": "B0-bearer-signed-receipt",
            "title": "Broken provenance",
            "venue": "test",
            "doi_or_url": "https://example.org/x",
            "code_url": "",
            "algorithm_class": "capability tokens",
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
            "comparator_id": "macaroons14",
            "title": "Macaroons",
            "venue": "NDSS 2014",
            "doi_or_url": "https://example.org/macaroons",
            "code_url": "",
            "algorithm_class": "capability tokens",
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
            "comparator_id": "openfga",
            "title": "OpenFGA",
            "venue": "test",
            "doi_or_url": "https://github.com/openfga/openfga",
            "code_url": "",
            "algorithm_class": "relationship authorization",
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
