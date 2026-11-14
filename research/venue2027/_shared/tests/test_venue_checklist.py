"""Tests for SH-venue_formats (research/venue2027/_shared/tools/venue_checklist.py).

Positive controls:
- check_venue returns a fully-populated Checklist for every program venue.
- The real registry audits clean: all facts UNVERIFIED is an expected, OK state.
- A properly-cited VERIFIED fact (URL + date) passes the audit.
- The generated markdown lists all nine venues with a VERIFICATION STATUS.

Adversarial controls (each must FAIL the audit, never silently pass):
- A deadline/cost fact presented as VERIFIED/CONFIRMED without a citation
  (no URL, no date, or both missing).
- A required venue missing from the registry.
- A registry entry lacking a required fact field.
- An unknown venue or invalid date refused by check_venue with stable codes.
- A malformed registry fails closed.
"""

from __future__ import annotations

import copy
import json
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[3]
TOOLS_DIR = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import venue_checklist as vc  # noqa: E402

# parents[3] is the worktree root only because this file sits four levels deep
# (research/venue2027/_shared/tests/); resolve relative to the shared dir instead.
REGISTRY = pathlib.Path(__file__).resolve().parents[1] / "venue_checklist.json"


# --------------------------------------------------------------- positive controls
def test_check_venue_all_nine_venues() -> None:
    for venue in vc.VENUES:
        c = vc.check_venue(venue, "2026-11-15", registry_path=REGISTRY)
        assert c.venue == venue
        assert c.date == "2026-11-15"
        for field in vc.REQUIRED_FACT_FIELDS:
            fact = getattr(c, field)
            assert isinstance(fact, vc.Fact)
            assert fact.value, f"{venue}.{field} must carry a value"
            assert fact.status == vc.UNVERIFIED


def test_check_venue_json_serializable() -> None:
    c = vc.check_venue("popets", "2026-11-15", registry_path=REGISTRY)
    payload = json.loads(json.dumps(c.to_dict()))
    assert payload["venue"] == "popets"
    assert payload["status"] == "UNVERIFIED"


def test_real_registry_audit_ok_with_all_unverified() -> None:
    audit = vc.audit_checklist(registry_path=REGISTRY)
    assert audit.ok is True
    assert audit.reason_code == "OK"
    assert audit.findings == ()


def test_properly_cited_verified_fact_passes() -> None:
    entries = vc.load_registry(REGISTRY)
    mutated = copy.deepcopy(entries)
    mutated["dsn"]["registration_fee"] = {
        "value": "EUR 500 early author registration",
        "status": vc.VERIFIED,
        "verification_url": "https://dsn2027-berlin.github.io/important-dates/",
        "verification_date": "2026-11-15",
    }
    audit = vc.audit_checklist(entries=mutated)
    assert audit.ok is True


def test_markdown_lists_all_venues_with_status() -> None:
    checklists = [vc.check_venue(v, "2026-11-15", registry_path=REGISTRY) for v in vc.VENUES]
    audit = vc.audit_checklist(registry_path=REGISTRY)
    text = vc.to_markdown(checklists, audit=audit)
    for venue in vc.VENUES:
        assert f"| {venue} |" in text
    assert "VERIFICATION STATUS" in text
    assert text.count("| UNVERIFIED |") == len(vc.VENUES)


def test_cli_generates_markdown_and_exits_zero(tmp_path: pathlib.Path) -> None:
    out = tmp_path / "checklist.md"
    res = subprocess.run(
        [
            sys.executable,
            str(TOOLS_DIR / "venue_checklist.py"),
            "--registry",
            str(REGISTRY),
            "--out",
            str(out),
            "--date",
            "2026-11-15",
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stderr
    payload = json.loads(res.stdout)
    assert payload["ok"] is True
    assert payload["venue_count"] == 9
    assert out.is_file()


# ----------------------------------------------------------- adversarial controls
def _mutated_registry() -> dict[str, dict[str, object]]:
    return copy.deepcopy(vc.load_registry(REGISTRY))


def test_confirmed_cost_without_citation_fails() -> None:
    entries = _mutated_registry()
    entries["sacmat"]["registration_fee"] = {
        "value": "USD 500 APC",
        "status": vc.VERIFIED,
    }
    audit = vc.audit_checklist(entries=entries)  # type: ignore[arg-type]
    assert audit.ok is False
    assert any(
        f.reason_code == "CONFIRMED_WITHOUT_CITATION" and f.venue == "sacmat"
        for f in audit.findings
    )


def test_confirmed_deadline_without_date_fails() -> None:
    entries = _mutated_registry()
    entries["aime"]["registration_fee"] = {
        "value": "EUR 700 full registration",
        "status": vc.VERIFIED,
        "verification_url": "https://aime27.aimedicine.info/call-for-papers/",
    }
    audit = vc.audit_checklist(entries=entries)  # type: ignore[arg-type]
    assert audit.ok is False
    assert any(f.reason_code == "CONFIRMED_WITHOUT_CITATION" for f in audit.findings)


def test_confirmed_deadline_without_url_fails() -> None:
    entries = _mutated_registry()
    entries["dsn"]["registration_fee"] = {
        "value": "EUR 600",
        "status": vc.VERIFIED,
        "verification_date": "2026-11-15",
    }
    audit = vc.audit_checklist(entries=entries)  # type: ignore[arg-type]
    assert audit.ok is False


def test_missing_required_venue_fails() -> None:
    entries = _mutated_registry()
    del entries["pst"]
    audit = vc.audit_checklist(entries=entries)  # type: ignore[arg-type]
    assert audit.ok is False
    assert any(f.reason_code == "MISSING_VENUE" and f.venue == "pst" for f in audit.findings)


def test_missing_required_fact_field_fails() -> None:
    entries = _mutated_registry()
    del entries["compsac"]["artifact_policy"]
    audit = vc.audit_checklist(entries=entries)  # type: ignore[arg-type]
    assert audit.ok is False
    assert any(f.reason_code == "MISSING_REQUIRED_FIELD" for f in audit.findings)


def test_illegal_status_value_fails_closed() -> None:
    entries = _mutated_registry()
    entries["acns"]["page_limit"] = {"value": "14 pages", "status": "CONFIRMED_BY_VIBES"}
    audit = vc.audit_checklist(entries=entries)  # type: ignore[arg-type]
    assert audit.ok is False
    assert any(f.reason_code == "REGISTRY_MALFORMED" and f.venue == "acns" for f in audit.findings)


def test_malformed_registry_entry_fails() -> None:
    entries = _mutated_registry()
    entries["dimva"]["artifact_policy"] = "just a string"
    audit = vc.audit_checklist(entries=entries)  # type: ignore[arg-type]
    assert audit.ok is False


# --------------------------------------------------------- input validation errors
def test_unknown_venue_refused() -> None:
    with pytest.raises(vc.VenueChecklistError) as exc:
        vc.check_venue("neurips", "2026-11-15", registry_path=REGISTRY)
    assert exc.value.reason_code == "UNKNOWN_VENUE"


def test_invalid_date_refused() -> None:
    with pytest.raises(vc.VenueChecklistError) as exc:
        vc.check_venue("dsn", "", registry_path=REGISTRY)
    assert exc.value.reason_code == "INVALID_DATE"


def test_unreadable_registry_fails_closed() -> None:
    with pytest.raises(vc.VenueChecklistError) as exc:
        vc.load_registry("/nonexistent/registry.json")
    assert exc.value.reason_code == "REGISTRY_MALFORMED"


def test_registry_covers_exactly_program_venues() -> None:
    entries = vc.load_registry(REGISTRY)
    assert set(entries) == set(vc.VENUES)
