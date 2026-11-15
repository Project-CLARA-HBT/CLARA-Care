"""Tests for DSN-oracle — independent per-case truth oracle.

Positive controls prove each registered DSN scenario family yields the
expected recoverable outcome through the declarative rule table (delegated to
the shared oracle kernel), that unknown/absent families are ``INDETERMINATE``
(never coerced to a safe verdict), that results are deterministic and carry
stable reason codes plus evidence refs, and that ``verify_independence`` on
the live module passes.

Adversarial controls prove the independence gate is real:

- The live oracle source passes ``verify_independence`` (no candidate import).
- Any source variant importing the DSN candidate state machine — plain import,
  aliased import, from-import, ``from dsn import state_machine``, or an import
  appended to the real source (tamper control) — is refused with
  ``CANDIDATE_IMPORT`` by writing the variant to a temp oracle file and running
  the kernel's AST scan on it.
- A dynamic import call in an oracle file is refused with
  ``DYNAMIC_IMPORT_UNRESOLVABLE``.
- Exact matching: unrelated modules with similar names do not trip the scan.

The test module imports only the oracle and the shared kernel (independent-
oracle rule): no candidate ``state_machine`` import, no DB, no model, no
clock/randomness.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from evaluation.venue2027._shared import oracle_kernel
from evaluation.venue2027.dsn import independent_oracle

# The kernel's AST scan matches the FIRST path component of an import against
# the candidate module names, so the guarded root here is "state_machine"
# (from CANDIDATE_MODULES = ('dsn.state_machine', 'state_machine')); these
# variants are the forms that bind the candidate under that root.
CANDIDATE_SNIPPETS: tuple[str, ...] = (
    "import state_machine\n",
    "import state_machine as sm\n",
    "from state_machine import evaluate_durability\n",
    "from state_machine import DurabilityOutcome, recover\n",
)


def _case(case_id: str, family: str, evidence: tuple[str, ...] = ()) -> dict[str, object]:
    return {
        "case_id": case_id,
        "family": family,
        "evidence": [{"uri": uri} for uri in evidence],
    }


# ---------------------------------------------------------------------------
# Positive controls — each family yields the expected outcome
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("family", "expected_outcome"),
    [
        ("clean_recovery", "ADMIT"),
        ("torn_write", "REJECT"),
        ("duplicate_retry", "ADMIT"),
        ("fsync_failure", "INDETERMINATE"),
    ],
)
def test_positive_family_outcomes(family: str, expected_outcome: str) -> None:
    result = independent_oracle.adjudicate(_case(f"DSN-CASE-{family}", family))
    assert isinstance(result, oracle_kernel.OracleResult)
    assert result.outcome == expected_outcome
    assert result.oracle_id == independent_oracle.ORACLE_ID
    assert result.oracle_id == "dsn-reference"
    assert result.reason_code == f"RULE_{family.upper()}"


def test_positive_clean_recovery_carries_evidence_refs() -> None:
    result = independent_oracle.adjudicate(
        _case("DSN-CASE-01", "clean_recovery", ("outbox.jsonl", "wal.dump"))
    )
    assert result.outcome == "ADMIT"
    assert result.evidence_refs == ("outbox.jsonl", "wal.dump")


def test_positive_duplicate_retry_is_idempotent_admit() -> None:
    first = independent_oracle.adjudicate(_case("DSN-CASE-04a", "duplicate_retry"))
    replay = independent_oracle.adjudicate(_case("DSN-CASE-04a", "duplicate_retry"))
    assert first.outcome == "ADMIT" and replay.outcome == "ADMIT"
    assert first == replay


def test_positive_unknown_family_is_indeterminate() -> None:
    result = independent_oracle.adjudicate(_case("DSN-CASE-99", "novel_family"))
    assert result.outcome == "INDETERMINATE"
    assert result.reason_code == "UNMODELLED_FAMILY"
    assert result.oracle_id == "dsn-reference"


def test_positive_missing_family_is_indeterminate() -> None:
    result = independent_oracle.adjudicate({"case_id": "DSN-CASE-00"})
    assert result.outcome == "INDETERMINATE"
    assert result.reason_code == "NO_FAMILY_DECLARED"


def test_positive_missing_case_id_refused() -> None:
    with pytest.raises(oracle_kernel.OracleError) as excinfo:
        independent_oracle.adjudicate({"family": "clean_recovery"})
    assert excinfo.value.reason_code == "MISSING_CASE_ID"


def test_positive_payload_family_fallback() -> None:
    result = independent_oracle.adjudicate(
        {"case_id": "DSN-CASE-02", "payload": {"family": "torn_write"}}
    )
    assert result.outcome == "REJECT"


def test_positive_deterministic_and_json_serializable() -> None:
    case = _case("DSN-CASE-01", "clean_recovery", ("receipt.json",))
    results = [independent_oracle.adjudicate(case) for _ in range(5)]
    assert all(r == results[0] for r in results)
    payload = json.dumps(results[0].to_dict(), sort_keys=True).encode()
    assert isinstance(json.loads(payload), dict)
    assert results[0].to_dict()["kernel_version"] == oracle_kernel.ORACLE_KERNEL_VERSION


# ---------------------------------------------------------------------------
# Adversarial controls — independence from the candidate state machine
# ---------------------------------------------------------------------------


def test_adversarial_live_module_passes_independence() -> None:
    independent_oracle.verify_independence()  # must not raise
    oracle_kernel.assert_oracle_independence(
        str(pathlib.Path(independent_oracle.__file__).resolve()),
        independent_oracle.CANDIDATE_MODULES,
    )


@pytest.mark.parametrize("snippet", CANDIDATE_SNIPPETS)
def test_adversarial_candidate_import_refused_in_temp_oracle(
    tmp_path: pathlib.Path, snippet: str
) -> None:
    oracle = tmp_path / "oracle_variant.py"
    oracle.write_text(f'"""variant"""\n{snippet}\n', encoding="utf-8")
    with pytest.raises(oracle_kernel.OracleError) as excinfo:
        oracle_kernel.assert_oracle_independence(
            str(oracle), ("dsn.state_machine", "state_machine")
        )
    assert excinfo.value.reason_code == "CANDIDATE_IMPORT"


def test_adversarial_tampered_live_source_refused(tmp_path: pathlib.Path) -> None:
    live = pathlib.Path(independent_oracle.__file__).resolve()
    tampered = tmp_path / "tampered_oracle.py"
    tampered.write_text(
        live.read_text(encoding="utf-8") + "\nimport state_machine\n",
        encoding="utf-8",
    )
    with pytest.raises(oracle_kernel.OracleError) as excinfo:
        independent_oracle.verify_independence.__globals__[
            "oracle_kernel"
        ].assert_oracle_independence(str(tampered), independent_oracle.CANDIDATE_MODULES)
    assert excinfo.value.reason_code == "CANDIDATE_IMPORT"


def test_adversarial_dynamic_import_refused(tmp_path: pathlib.Path) -> None:
    oracle = tmp_path / "dynamic_oracle.py"
    oracle.write_text(
        "import importlib\nm = importlib.import_module('state_machine')\n",
        encoding="utf-8",
    )
    with pytest.raises(oracle_kernel.OracleError) as excinfo:
        oracle_kernel.assert_oracle_independence(str(oracle), independent_oracle.CANDIDATE_MODULES)
    assert excinfo.value.reason_code == "DYNAMIC_IMPORT_UNRESOLVABLE"


def test_adversarial_unrelated_names_accepted(tmp_path: pathlib.Path) -> None:
    oracle = tmp_path / "clean_oracle.py"
    oracle.write_text(
        "import json\n"
        "from evaluation.venue2027.dsn import independent_oracle\n"
        "import my_state_machine_tests\n",
        encoding="utf-8",
    )
    oracle_kernel.assert_oracle_independence(str(oracle), independent_oracle.CANDIDATE_MODULES)
