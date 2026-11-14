"""Tests for SH-baseline_registry (research/venue2027/_shared/tools/baseline_registry.py).

Positive controls:
- A correctly registered ORIGINAL_UPSTREAM entry (pinned revision + license)
  audits clean.
- A FAITHFUL_PORT entry with a parity fixture reference audits clean.
- The REAL shared registry (all nine venues) audits ok with the expected
  entry count and honest UNAVAILABLE_NOT_RUN labels.

Adversarial controls (each must FAIL the audit, never pass silently):
- THE canonical negative control: a fake stub returning a constant deny
  presented as a full baseline -> STUB_PRESENTED_AS_BASELINE.
- FAITHFUL_PORT without a parity fixture -> FAITHFUL_PORT_WITHOUT_FIXTURE.
- VERIFIED fidelity with UNAVAILABLE revision ->
  VERIFIED_FIDELITY_UNAVAILABLE_REVISION.
- Runnable entry with missing license -> MISSING_LICENSE.
- Replacing an unavailable baseline with a toy while keeping the same name
  (contract rule 8 end-to-end) -> refused.
- Unknown fidelity status -> UNKNOWN_FIDELITY_STATUS.
- register_baseline with a bogus revision string (not a pin, not UNAVAILABLE
  label semantics) -> refused via revision contract.
- JSON round-trip of entries (typed objects must be JSON-serializable).
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

TOOLS_DIR = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import baseline_registry as br  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
REGISTRY_PATH = REPO_ROOT / "research" / "venue2027" / "_shared" / "baselines" / "registry.yaml"

EXPECTED_ENTRY_COUNT = 40


def _full_entry(**overrides: object) -> br.Entry:
    base: dict[str, object] = dict(
        name="some-upstream-baseline",
        revision="deadbeef" * 8,
        venues=("sacmat",),
        upstream_url="https://github.com/example/upstream",
        license="MIT",
        algorithm_class="strong comparator algorithm",
        config="pinned config values",
        data_rights="synthetic dataset only",
        parity_fixture="evaluation/venue2027/sacmat/fixtures/parity.json",
        exec_command="python3 -m evaluation.venue2027.sacmat.baselines --baseline some-upstream-baseline",
        fidelity_status="ORIGINAL_UPSTREAM",
        notes="",
    )
    base.update(overrides)
    return br.register_baseline(**base)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# Positive controls
# --------------------------------------------------------------------------
def test_original_upstream_with_pin_and_license_passes() -> None:
    entries = [_full_entry()]
    result = br.audit_registry(entries)
    assert result.ok is True
    assert result.reason_code == "OK"
    assert result.findings == ()
    assert result.entries_audited == 1


def test_faithful_port_with_fixture_passes() -> None:
    entry = _full_entry(
        fidelity_status="FAITHFUL_PORT",
        parity_fixture="evaluation/venue2027/compsac/fixtures/silo_parity.json",
    )
    assert br.audit_registry([entry]).ok is True


def test_unavailable_not_run_is_honest_and_passes() -> None:
    entry = _full_entry(
        fidelity_status="UNAVAILABLE_NOT_RUN",
        revision="UNAVAILABLE",
        parity_fixture="",
    )
    result = br.audit_registry([entry])
    assert result.ok is True


def test_real_registry_audits_ok() -> None:
    assert REGISTRY_PATH.is_file(), f"missing {REGISTRY_PATH}"
    entries = br.load_registry(REGISTRY_PATH)
    assert len(entries) == EXPECTED_ENTRY_COUNT
    result = br.audit_registry(entries)
    assert result.ok is True, result.to_json()
    assert result.reason_code == "OK"
    # All nine venues must be covered.
    venues = {v for e in entries for v in e.venues}
    assert venues == {
        "acns",
        "aime",
        "compsac",
        "dimva",
        "dsn",
        "ifip_sec",
        "popets",
        "pst",
        "sacmat",
    }


def test_real_registry_has_no_invented_hashes() -> None:
    entries = br.load_registry(REGISTRY_PATH)
    for e in entries:
        if e.fidelity_status in ("FAITHFUL_PORT", "ORIGINAL_UPSTREAM"):
            assert e.upstream_revision != br.REVISION_UNAVAILABLE
        # Every runnable entry has a license and an exec command.
        if e.fidelity_status != "UNAVAILABLE_NOT_RUN":
            assert e.license.strip()
            assert e.exec_command.strip()
            assert e.parity_fixture.strip()


def test_register_baseline_rejects_bad_fidelity_status() -> None:
    with pytest.raises(br.BaselineRegistryError) as exc:
        br.register_baseline(
            name="x",
            revision="UNAVAILABLE",
            venues=("dsn",),
            upstream_url="https://x",
            license="MIT",
            algorithm_class="a",
            config="c",
            data_rights="d",
            parity_fixture="f",
            exec_command="e",
            fidelity_status="BEST_EVER",  # type: ignore[arg-type]
        )
    assert exc.value.reason_code == "UNKNOWN_FIDELITY_STATUS"


def test_entry_is_json_serializable_round_trip() -> None:
    entry = _full_entry()
    payload = json.loads(entry.to_json())
    assert payload["name"] == entry.name
    assert payload["fidelity_status"] == "ORIGINAL_UPSTREAM"
    assert payload["venues"] == ["sacmat"]


# --------------------------------------------------------------------------
# Adversarial controls
# --------------------------------------------------------------------------
def test_fake_constant_deny_stub_presented_as_full_baseline_fails() -> None:
    """THE canonical negative control from the task definition."""
    stub = _full_entry(
        name="silo-style-entity-readset-occ",
        fidelity_status="ORIGINAL_UPSTREAM",
        config="returns constant deny for all requests; not implemented",
    )
    result = br.audit_registry([stub])
    assert result.ok is False
    codes = {f.reason_code for f in result.findings}
    assert "STUB_PRESENTED_AS_BASELINE" in codes


def test_stub_via_declared_flag_fails() -> None:
    stub = _full_entry(declared_stub=True)
    result = br.audit_registry([stub])
    assert result.ok is False
    assert any(f.reason_code == "STUB_PRESENTED_AS_BASELINE" for f in result.findings)


def test_stub_disclosed_in_notes_fails() -> None:
    stub = _full_entry(notes="toy baseline: merely returns a constant deny decision")
    result = br.audit_registry([stub])
    assert result.ok is False
    assert any(f.reason_code == "STUB_PRESENTED_AS_BASELINE" for f in result.findings)


def test_faithful_port_without_fixture_fails() -> None:
    entry = _full_entry(fidelity_status="FAITHFUL_PORT", parity_fixture="")
    result = br.audit_registry([entry])
    assert result.ok is False
    assert any(f.reason_code == "FAITHFUL_PORT_WITHOUT_FIXTURE" for f in result.findings)


def test_verified_fidelity_with_unavailable_revision_fails() -> None:
    entry = _full_entry(revision="UNAVAILABLE")
    result = br.audit_registry([entry])
    assert result.ok is False
    assert any(f.reason_code == "VERIFIED_FIDELITY_UNAVAILABLE_REVISION" for f in result.findings)


def test_faithful_port_with_unavailable_revision_fails() -> None:
    entry = _full_entry(fidelity_status="FAITHFUL_PORT", revision="UNAVAILABLE")
    result = br.audit_registry([entry])
    assert result.ok is False
    codes = {f.reason_code for f in result.findings}
    assert "VERIFIED_FIDELITY_UNAVAILABLE_REVISION" in codes


def test_missing_license_fails() -> None:
    entry = _full_entry(license="")
    result = br.audit_registry([entry])
    assert result.ok is False
    assert any(f.reason_code == "MISSING_LICENSE" for f in result.findings)


def test_license_placeholder_fails() -> None:
    entry = _full_entry(license="TBD")
    result = br.audit_registry([entry])
    assert result.ok is False
    assert any(f.reason_code == "MISSING_LICENSE" for f in result.findings)


def test_toy_replacement_keeping_same_name_fails() -> None:
    """Contract rule 8: unavailable upstream must not become a toy with the same name."""
    toy = _full_entry(
        name="zanzibar-openfga",
        fidelity_status="FAITHFUL_PORT",
        revision="UNAVAILABLE",  # upstream unavailable...
        parity_fixture="x.json",
        notes="toy replacement used because upstream server is hard to build",
    )
    result = br.audit_registry([toy])
    assert result.ok is False
    codes = {f.reason_code for f in result.findings}
    # Both rules fire: no verified revision for a fidelity claim AND the toy disclosure.
    assert "VERIFIED_FIDELITY_UNAVAILABLE_REVISION" in codes
    assert "STUB_PRESENTED_AS_BASELINE" in codes


def test_unavailable_not_run_may_not_claim_verified_fidelity_later_without_revision() -> None:
    """An entry can only upgrade from UNAVAILABLE_NOT_RUN by pinning a real revision."""
    upgraded = _full_entry(fidelity_status="ORIGINAL_UPSTREAM", revision="UNAVAILABLE")
    result = br.audit_registry([upgraded])
    assert result.ok is False
    assert any(f.reason_code == "VERIFIED_FIDELITY_UNAVAILABLE_REVISION" for f in result.findings)


def test_duplicate_name_fails() -> None:
    a = _full_entry(name="dup", venues=("pst",))
    b = _full_entry(name="dup", venues=("dsn",))
    result = br.audit_registry([a, b])
    assert result.ok is False
    assert any(f.reason_code == "DUPLICATE_BASELINE_NAME" for f in result.findings)


def test_audit_rejects_non_entry_object() -> None:
    result = br.audit_registry(["not-an-entry"])  # type: ignore[list-item]
    assert result.ok is False
    assert any(f.reason_code == "MISSING_FIELD" for f in result.findings)


def test_register_baseline_rejects_empty_revision_string() -> None:
    with pytest.raises(br.BaselineRegistryError) as exc:
        br.register_baseline(
            name="x",
            revision="   ",
            venues=("dsn",),
            upstream_url="https://x",
            license="MIT",
            algorithm_class="a",
            config="c",
            data_rights="d",
            parity_fixture="f",
            exec_command="e",
            fidelity_status="ORIGINAL_UPSTREAM",
        )
    assert exc.value.reason_code == "MISSING_FIELD"


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def test_cli_audit_real_registry_exit_zero() -> None:
    proc = subprocess.run(
        [sys.executable, str(TOOLS_DIR / "baseline_registry.py"), "--registry", str(REGISTRY_PATH)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["entries_audited"] == EXPECTED_ENTRY_COUNT
