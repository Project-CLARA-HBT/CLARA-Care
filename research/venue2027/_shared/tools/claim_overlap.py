"""CLARA-Care 2027 shared task SH-claim_overlap.

Purpose
-------
Enforce publication-overlap and scope firewalls between the nine 2027 venue
studies and historical CLARA-Care publications, as required by
``GATES/ANTI_SALAMI_REVIEW.md``.

Each study declares: research question, primary endpoint, dataset, baseline set,
and whether it reuses an archived study. :func:`audit_overlap` blocks pairs that
share the *same* question+endpoint (salami) and blocks any study that reuses
frozen archived evidence as if it were new.

Allowed input
-------------
A list of study declarations (``StudyClaim``) — typically loaded from the
registry file this module writes.

Failure semantics
-----------------
Returns :class:`OverlapFindings` with ``ok=False`` and per-pair ``reason_code``
when a disclosure collides. Never silently merges an overlap.

Version
-------
``CLAIM_OVERLAP_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path

CLAIM_OVERLAP_VERSION = "1.0.0"

VENUES: tuple[str, ...] = (
    "compsac",
    "popets",
    "aime",
    "ifp_sec",
    "sacmat",
    "acns",
    "dsn",
    "dimva",
    "pst",
)

# Historical / already-published work that must never be re-presented as a new
# independent 2027 study. Sourced from research/publication_registry.yaml.
HISTORICAL_ARCHIVE: tuple[str, ...] = (
    "glhs_r4",
    "govred_rivf",
    "govmut_soict",
    "careguard_vn",
    "healthinf_2026",
    "e15_e22_frozen",
)


@dataclasses.dataclass(frozen=True)
class StudyClaim:
    study: str
    research_question: str
    primary_endpoint: str
    dataset: str
    baselines: tuple[str, ...]
    reuses_archive: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "study": self.study,
            "research_question": self.research_question,
            "primary_endpoint": self.primary_endpoint,
            "dataset": self.dataset,
            "baselines": list(self.baselines),
            "reuses_archive": list(self.reuses_archive),
        }


@dataclasses.dataclass(frozen=True)
class OverlapFinding:
    pair: tuple[str, str]
    severity: str
    reason_code: str
    detail: str

    def to_dict(self) -> dict[str, object]:
        return {
            "pair": list(self.pair),
            "severity": self.severity,
            "reason_code": self.reason_code,
            "detail": self.detail,
        }


@dataclasses.dataclass(frozen=True)
class OverlapFindings:
    ok: bool
    findings: tuple[OverlapFinding, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "schema_version": CLAIM_OVERLAP_VERSION,
            "finding_count": len(self.findings),
            "findings": [f.to_dict() for f in self.findings],
        }


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _normalize_archive(name: str) -> str:
    """Canonicalize an archive id so case/whitespace/suffix variants cannot evade.

    ``E15_E22_FROZEN``, ``" e15_e22_frozen "`` and ``e15_e22_frozen_v2`` all
    canonicalize to ``e15_e22_frozen`` (auditor defect F6).
    """

    canonical = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    # Strip trailing version/part suffixes: _v2, _v3, _part1, _copy, _frozen when
    # repeated, etc. Repeat until stable so chained suffixes are removed.
    while True:
        stripped = re.sub(r"_(v\d+|part\d+|copy|dup|dup\d+|rev\d*)$", "", canonical)
        if stripped == canonical:
            break
        canonical = stripped
    return canonical


def audit_overlap(studies: list[StudyClaim]) -> OverlapFindings:
    """Audit pairwise publication overlap and archive reuse."""

    findings: list[OverlapFinding] = []
    known_archives = {_normalize_archive(a) for a in HISTORICAL_ARCHIVE}

    for study in studies:
        for archive in study.reuses_archive:
            if _normalize_archive(archive) in known_archives:
                findings.append(
                    OverlapFinding(
                        pair=(study.study, archive),
                        severity="BLOCK",
                        reason_code="ARCHIVE_REUSE_AS_NEW",
                        detail=(
                            f"{study.study} reuses archived evidence '{archive}' "
                            "as if independent; declare an extension sub-study instead"
                        ),
                    )
                )

    for i, left in enumerate(studies):
        for right in studies[i + 1 :]:
            same_q = _normalize(left.research_question) == _normalize(right.research_question)
            same_ep = _normalize(left.primary_endpoint) == _normalize(right.primary_endpoint)
            if same_q and same_ep:
                findings.append(
                    OverlapFinding(
                        pair=(left.study, right.study),
                        severity="BLOCK",
                        reason_code="SALAMI_SAME_QUESTION_AND_ENDPOINT",
                        detail=(
                            f"{left.study} and {right.study} share research question and "
                            "primary endpoint; one must be a transfer target or joint paper"
                        ),
                    )
                )
            elif same_ep:
                findings.append(
                    OverlapFinding(
                        pair=(left.study, right.study),
                        severity="WARN",
                        reason_code="SHARED_PRIMARY_ENDPOINT",
                        detail=(
                            f"{left.study} and {right.study} share the primary endpoint "
                            f"'{left.primary_endpoint}'; document the shared measurement"
                        ),
                    )
                )
            elif same_q:
                findings.append(
                    OverlapFinding(
                        pair=(left.study, right.study),
                        severity="WARN",
                        reason_code="SHARED_RESEARCH_QUESTION",
                        detail=(
                            f"{left.study} and {right.study} share a research question; "
                            "differentiate the estimand"
                        ),
                    )
                )

    blocked = any(f.severity == "BLOCK" for f in findings)
    return OverlapFindings(ok=not blocked, findings=tuple(findings))


def load_claims(path: str | Path) -> list[StudyClaim]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = payload.get("studies", payload) if isinstance(payload, dict) else payload
    claims: list[StudyClaim] = []
    for entry in entries:
        claims.append(
            StudyClaim(
                study=entry["study"],
                research_question=entry["research_question"],
                primary_endpoint=entry["primary_endpoint"],
                dataset=entry["dataset"],
                baselines=tuple(entry.get("baselines", ())),
                reuses_archive=tuple(entry.get("reuses_archive", ())),
            )
        )
    return claims


def to_yaml(claims: list[StudyClaim], findings: OverlapFindings) -> str:
    """Render a deterministic YAML registry (no external dependency needed)."""

    lines = [
        "# CLARA-Care 2027 publication overlap registry",
        f"# schema_version: {CLAIM_OVERLAP_VERSION}",
        f"audit_ok: {str(findings.ok).lower()}",
        "studies:",
    ]
    for claim in sorted(claims, key=lambda c: c.study):
        lines.append(f"  - study: {claim.study}")
        lines.append(f"    research_question: {json.dumps(claim.research_question)}")
        lines.append(f"    primary_endpoint: {json.dumps(claim.primary_endpoint)}")
        lines.append(f"    dataset: {json.dumps(claim.dataset)}")
        lines.append("    baselines:")
        for baseline in claim.baselines:
            lines.append(f"      - {json.dumps(baseline)}")
        lines.append("    reuses_archive: []" if not claim.reuses_archive else "    reuses_archive:")
        for archive in claim.reuses_archive:
            lines.append(f"      - {archive}")
    lines.append("findings:")
    for finding in findings.findings:
        lines.append(f"  - pair: {list(finding.pair)}")
        lines.append(f"    severity: {finding.severity}")
        lines.append(f"    reason_code: {finding.reason_code}")
        lines.append(f"    detail: {json.dumps(finding.detail)}")
    return "\n".join(lines) + "\n"
