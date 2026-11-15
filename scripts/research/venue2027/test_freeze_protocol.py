"""Tests for SH-freeze_tool (scripts/research/venue2027/freeze_protocol.py).

Positive and adversarial controls required by the task contract:
- Positive: freeze then verify reports OK and a stable freeze_id.
- Positive: amendments append without rewriting prior history; verify still OK.
- Adversarial: tampered bundled file after freeze -> FREEZE_DRIFT.
- Adversarial: attempt to rewrite/truncate amendment history -> AMENDMENT_REWRITE.
- Adversarial: holdout access without a verified freeze -> HOLDOUT_UNFROZEN.
- Adversarial: missing bundled artifact at freeze time -> FREEZE_INPUT_MISSING.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import sys

TOOLS_DIR = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

import freeze_protocol as fp  # noqa: E402


def _clock() -> str:
    return "2026-11-15T00:00:00Z"


def _make_study(tmp_path: pathlib.Path) -> dict[str, pathlib.Path]:
    """Create a minimal study tree: protocol, cohort, oracle, baselines, analysis."""

    files = {
        "protocol/protocol.md": "# Preregistered protocol\nnull: A vs B\n",
        "cohorts/cohort_manifest.json": json.dumps({"units": 598, "split": "main"}),
        "oracle/oracle_source.py": "def truth(events):\n    return events\n",
        "baselines/registry.yaml": "name: strong-baseline\nrevision: r1\n",
        "analysis/analysis_policy.py": "ANALYSIS_SCHEMA_VERSION = '1.0.0'\n",
    }
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return files


def _config(tmp_path: pathlib.Path) -> fp.FreezeConfig:
    return fp.FreezeConfig(
        study_id="study-01",
        stage="pre-holdout",
        root=tmp_path,
        paths=(
            "protocol/protocol.md",
            "cohorts/cohort_manifest.json",
            "oracle/oracle_source.py",
            "baselines/registry.yaml",
            "analysis/analysis_policy.py",
        ),
        now_fn=_clock,
    )


# ---------------------------------------------------------------------------
# Positive controls
# ---------------------------------------------------------------------------


def test_freeze_then_verify_ok(tmp_path: pathlib.Path) -> None:
    _make_study(tmp_path)
    manifest = fp.freeze(_config(tmp_path))
    assert manifest.ok, manifest.detail
    assert manifest.reason_code == "OK"
    assert manifest.freeze_id
    assert len(manifest.entries) == 5
    assert all(e.timestamp_utc == "2026-11-15T00:00:00Z" for e in manifest.entries)

    verified = fp.verify_freeze(manifest, tmp_path)
    assert verified.ok, verified.detail
    assert verified.reason_code == "OK"
    assert verified.freeze_id == manifest.freeze_id


def test_freeze_id_order_independent_and_content_sensitive(tmp_path: pathlib.Path) -> None:
    _make_study(tmp_path)
    cfg = _config(tmp_path)
    m1 = fp.freeze(cfg)
    m2 = fp.freeze(dataclasses.replace(cfg, paths=tuple(reversed(cfg.paths))))
    assert m1.freeze_id == m2.freeze_id  # sorted (path, hash) pairs

    (tmp_path / "protocol/protocol.md").write_text(
        "# Preregistered protocol v2\n", encoding="utf-8"
    )
    m3 = fp.freeze(cfg)
    assert m3.freeze_id != m1.freeze_id  # content change -> new freeze_id


def test_amendment_appends_without_rewriting_history(tmp_path: pathlib.Path) -> None:
    _make_study(tmp_path)
    manifest = fp.freeze(_config(tmp_path))
    first = fp.amend(
        manifest, {"kind": "variance_update", "note": "n/a"}, tmp_path
    )
    assert first.ok, first.detail
    history_after_first = first.amendments
    assert len(history_after_first) == 1

    second = fp.amend(
        first, {"kind": "planned_comparison_add", "note": "secondary"}, tmp_path
    )
    assert second.ok, second.detail
    # Prior entries immutable: the first appended entry is preserved verbatim.
    assert list(second.amendments) == [
        *history_after_first,
        {
            "index": 1,
            "amendment": {"kind": "planned_comparison_add", "note": "secondary"},
            "timestamp_utc": None,
        },
    ]
    # The on-disk log contains exactly the merged, append-only history.
    on_disk = json.loads(
        (tmp_path / fp.AMENDMENT_LOG_BASENAME).read_text(encoding="utf-8")
    )
    assert on_disk == list(second.amendments)
    # Bundled artifacts untouched -> freeze_id unchanged by amendment.
    assert second.freeze_id == manifest.freeze_id
    assert fp.verify_freeze(second, tmp_path).ok


# ---------------------------------------------------------------------------
# Adversarial controls
# ---------------------------------------------------------------------------


def test_tampered_file_drifts_to_freeze_drift(tmp_path: pathlib.Path) -> None:
    _make_study(tmp_path)
    manifest = fp.freeze(_config(tmp_path))
    # Backdated edit after seeing results: rewrite the cohort manifest.
    (tmp_path / "cohorts/cohort_manifest.json").write_text(
        json.dumps({"units": 300, "split": "regenerated"}), encoding="utf-8"
    )
    verified = fp.verify_freeze(manifest, tmp_path)
    assert not verified.ok
    assert verified.reason_code == "FREEZE_DRIFT"
    assert "cohort_manifest.json" in verified.detail

    # Holdout stays closed on drift.
    blocked = fp.assert_holdout_allowed(manifest, tmp_path)
    assert not blocked.ok
    assert blocked.reason_code == "HOLDOUT_UNFROZEN"


def test_history_rewrite_refused(tmp_path: pathlib.Path) -> None:
    _make_study(tmp_path)
    manifest = fp.freeze(_config(tmp_path))
    amended = fp.amend(manifest, {"kind": "variance_update"}, tmp_path)
    assert amended.ok

    # Adversary hands back a manifest whose embedded history was truncated.
    truncated = dataclasses.replace(amended, amendments=())
    refused = fp.amend(truncated, {"kind": "sneaky"}, tmp_path)
    assert not refused.ok
    assert refused.reason_code == "AMENDMENT_REWRITE"
    # On-disk log must be untouched by the refused attempt.
    on_disk = json.loads(
        (tmp_path / fp.AMENDMENT_LOG_BASENAME).read_text(encoding="utf-8")
    )
    assert len(on_disk) == 1


def test_corrupted_amendment_log_refused(tmp_path: pathlib.Path) -> None:
    _make_study(tmp_path)
    manifest = fp.freeze(_config(tmp_path))
    log = tmp_path / fp.AMENDMENT_LOG_BASENAME
    log.write_text("{not json", encoding="utf-8")
    refused = fp.amend(manifest, {"kind": "anything"}, tmp_path)
    assert not refused.ok
    assert refused.reason_code == "AMENDMENT_REWRITE"


def test_holdout_without_freeze_refused(tmp_path: pathlib.Path) -> None:
    _make_study(tmp_path)
    # A manifest that never froze cannot unlock the holdout.
    never_froze = fp.FreezeManifest(
        ok=False,
        reason_code="OK",
        schema_version=fp.FREEZE_PROTOCOL_SCHEMA_VERSION,
        study_id="study-01",
        stage="pre-holdout",
        freeze_id="",
        entries=(),
        amendments=(),
        detail="",
    )
    blocked = fp.assert_holdout_allowed(never_froze, tmp_path)
    assert not blocked.ok
    assert blocked.reason_code == "HOLDOUT_UNFROZEN"

    # A fabricated manifest claiming OK but binding no entries is also refused.
    fabricated = dataclasses.replace(never_froze, ok=True, freeze_id="0" * 64)
    blocked2 = fp.assert_holdout_allowed(fabricated, tmp_path)
    assert not blocked2.ok
    assert blocked2.reason_code == "HOLDOUT_UNFROZEN"


def test_missing_bundled_artifact_fails_freeze(tmp_path: pathlib.Path) -> None:
    _make_study(tmp_path)
    (tmp_path / "oracle/oracle_source.py").unlink()
    manifest = fp.freeze(_config(tmp_path))
    assert not manifest.ok
    assert manifest.reason_code == "FREEZE_INPUT_MISSING"
    assert "oracle_source.py" in manifest.detail
    assert manifest.freeze_id == ""
    # Missing dependency is never silently dropped from the bundle.
    assert manifest.entries == ()


def test_path_escape_refused(tmp_path: pathlib.Path) -> None:
    _make_study(tmp_path)
    outside = tmp_path / ".." / "outside.txt"
    outside.write_text("host secret", encoding="utf-8")
    cfg = dataclasses.replace(_config(tmp_path), paths=("protocol/../protocol.md",))
    cfg_escaped = dataclasses.replace(
        _config(tmp_path), paths=("../../outside.txt",)
    )
    for bad_cfg in (cfg_escaped, dataclasses.replace(cfg, paths=("/etc/hostname",))):
        result = fp.freeze(bad_cfg)
        assert not result.ok
        assert result.reason_code == "FREEZE_INPUT_INVALID"
