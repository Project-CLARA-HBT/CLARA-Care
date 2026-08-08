"""Render the completed full-Synthea Q2 result into the evidence report.

This is intentionally a narrow, fail-closed report renderer.  It refuses to
write a manuscript-facing markdown section unless the external-stream artifact
passes the independent accounting/release validator.  It does not derive any
new metric or make a clinical claim.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Support the documented direct-script invocation as well as ``python -m``.
# When Python receives a file below ``scripts/``, the repository root is not
# automatically on sys.path, while the validator is deliberately a package
# module under ``evaluation/``.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evaluation.glhs_q2.validate_artifact import validate

_START = "<!-- FULL_SYNTHEA_MACHINE_RESULTS:START -->"
_END = "<!-- FULL_SYNTHEA_MACHINE_RESULTS:END -->"


def _ratio(metrics: dict[str, object], system: str) -> str:
    system_metrics = metrics.get(system)
    if not isinstance(system_metrics, dict):
        raise TypeError(f"missing_system_metrics:{system}")
    state = system_metrics.get("state_correct")
    if not isinstance(state, dict):
        raise TypeError(f"missing_state_correct:{system}")
    numerator, denominator = state.get("numerator"), state.get("denominator")
    if not isinstance(numerator, int) or not isinstance(denominator, int):
        raise TypeError(f"invalid_state_correct:{system}")
    return f"{numerator:,}/{denominator:,}"


def render(*, artifact: Path, report: Path) -> None:
    audit = validate(artifact)
    if audit.get("valid") is not True:
        raise ValueError("artifact_validation_not_true")
    summary = json.loads((artifact / "summary.json").read_text(encoding="utf-8"))
    source = json.loads((artifact / "source-manifest.json").read_text(encoding="utf-8"))
    metrics = summary.get("metrics")
    source_scan = source.get("source_scan")
    if not isinstance(metrics, dict) or not isinstance(source_scan, dict):
        raise TypeError("summary_or_source_manifest_shape_invalid")
    cases = audit.get("cases")
    selected = source_scan.get("selected_cases")
    bundles = source_scan.get("fhir_patient_bundles")
    if not all(isinstance(value, int) for value in (cases, selected, bundles)):
        raise ValueError("source_counts_invalid")
    # Reports are committed and reviewed across machines.  Preserve a concise,
    # repository-relative artifact location whenever both paths share a root;
    # only retain an absolute location for an intentionally external artifact.
    try:
        artifact_label = artifact.resolve().relative_to(report.resolve().parents[2]).as_posix()
    except ValueError:
        artifact_label = artifact.as_posix()
    section = "\n".join(
        [
            _START,
            "## Full Synthea FHIR STU3 result (machine-rendered)",
            "",
            f"Artifact: `{artifact_label}/`; validation: `publication-validation.json`.",
            "",
            f"- Source FHIR patient bundles scanned: **{bundles:,}**",
            f"- Selected tokenized structural cases / evaluated subjects: **{selected:,} / {cases:,}**",
            "- Partition: **development**; synthetic structural conformance only; no final score or clinical-validation claim.",
            "",
            "| Comparator | State correct |",
            "|---|---:|",
            f"| LWW | {_ratio(metrics, 'lww')} |",
            f"| Temporal/provenance resolver | {_ratio(metrics, 'temporal_provenance_resolver')} |",
            f"| GLHS-full reference policy | {_ratio(metrics, 'glhs_full')} |",
            "",
            "The values above are rendered directly from checksum-validated machine artifacts. They are not pooled with MIMIC, are not a sealed external holdout, and do not establish clinical effectiveness or safety.",
            _END,
        ]
    )
    original = report.read_text(encoding="utf-8")
    if _START in original or _END in original:
        if _START not in original or _END not in original:
            raise ValueError("full_synthea_report_marker_unbalanced")
        prefix, remainder = original.split(_START, 1)
        _, suffix = remainder.split(_END, 1)
        updated = f"{prefix}{section}{suffix}"
    else:
        updated = f"{original.rstrip()}\n\n{section}\n"
    temporary = report.with_suffix(report.suffix + ".tmp")
    temporary.write_text(updated, encoding="utf-8")
    temporary.replace(report)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    render(artifact=args.artifact, report=args.report)


if __name__ == "__main__":
    main()
