from pathlib import Path

from evaluation.evidence_program.status import audit


def test_status_audit_never_releases_without_sealed_run() -> None:
    report = audit(Path("."), Path("/nonexistent/evidence-program"))
    assert report["headline_ready"] is False
    assert report["headline_claims_permitted"] is False
    assert not report["sealed_runs"]
