"""CLARA-Care 2027 shared task SH-research_ethics.

Purpose
-------
Enforce the synthetic-only data policy for every 2027 study. Before any dataset
may be used, :func:`check_data_policy` must return a PASS verdict.

The policy blocks:
- real patient data (any declared provenance that is not synthetic),
- datasets without an explicit license/permission,
- datasets containing PHI-like fields unless they are provably synthetic,
- model-provider use without recorded terms acknowledgment.

Allowed input
-------------
A :class:`DatasetDeclaration`.

Failure semantics
-----------------
Returns :class:`EthicsVerdict` with ``ok=False`` and stable reason codes. A
blocked dataset must never be run; there is no override parameter.

Version
-------
``RESEARCH_ETHICS_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

RESEARCH_ETHICS_VERSION = "1.0.0"

SYNTHETIC_SOURCES: tuple[str, ...] = (
    "generated_synthetic",
    "deterministic_fixture",
    "public_deidentified_benchmark",
)

# Field names that indicate PHI/PII. Their presence is allowed only for datasets
# whose provenance is a recognized synthetic/deidentified source.
PHI_LIKE_FIELDS: tuple[str, ...] = (
    "name",
    "full_name",
    "email",
    "phone",
    "address",
    "national_id",
    "passport",
    "mrn",
    "insurance_id",
    "dob",
    "date_of_birth",
    "face_image",
)


@dataclasses.dataclass(frozen=True)
class DatasetDeclaration:
    dataset_id: str
    provenance: str
    license: str
    phi_fields: tuple[str, ...] = ()
    synthetic_verifiable: bool = False
    provider_terms_acknowledged: bool = False
    clinical_claim_allowed: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "dataset_id": self.dataset_id,
            "provenance": self.provenance,
            "license": self.license,
            "phi_fields": list(self.phi_fields),
            "synthetic_verifiable": self.synthetic_verifiable,
            "provider_terms_acknowledged": self.provider_terms_acknowledged,
            "clinical_claim_allowed": self.clinical_claim_allowed,
        }


@dataclasses.dataclass(frozen=True)
class EthicsVerdict:
    ok: bool
    reason_codes: tuple[str, ...]
    dataset_id: str

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "reason_codes": list(self.reason_codes),
            "dataset_id": self.dataset_id,
            "version": RESEARCH_ETHICS_VERSION,
        }


def check_data_policy(declaration: DatasetDeclaration) -> EthicsVerdict:
    """Return PASS only for fully licensed synthetic/deidentified datasets."""

    reasons: list[str] = []

    if declaration.provenance not in SYNTHETIC_SOURCES:
        reasons.append("NON_SYNTHETIC_PROVENANCE")

    if not declaration.license.strip():
        reasons.append("MISSING_LICENSE")

    if declaration.phi_fields:
        if declaration.provenance != "generated_synthetic":
            reasons.append("PHI_FIELDS_WITHOUT_SYNTHETIC_PROVENANCE")
        elif not declaration.synthetic_verifiable:
            reasons.append("PHI_FIELDS_REQUIRE_VERIFIABLE_SYNTHESIS")

    if declaration.provenance == "public_deidentified_benchmark" and not declaration.synthetic_verifiable:
        reasons.append("DEIDENTIFICATION_NOT_VERIFIED")

    # A synthetic dataset can never justify a clinical efficacy claim.
    if declaration.clinical_claim_allowed:
        reasons.append("CLINICAL_CLAIM_FROM_SYNTHETIC_DATA")

    return EthicsVerdict(ok=not reasons, reason_codes=tuple(reasons), dataset_id=declaration.dataset_id)


def check_provider_use(declaration: DatasetDeclaration) -> EthicsVerdict:
    """Separate gate for paid model-provider use (terms + budget acknowledgment)."""

    reasons: list[str] = []
    if not declaration.provider_terms_acknowledged:
        reasons.append("PROVIDER_TERMS_NOT_ACKNOWLEDGED")
    return EthicsVerdict(ok=not reasons, reason_codes=tuple(reasons), dataset_id=declaration.dataset_id)


def load_declarations(path: str | Path) -> list[DatasetDeclaration]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = payload.get("datasets", payload) if isinstance(payload, dict) else payload
    return [
        DatasetDeclaration(
            dataset_id=e["dataset_id"],
            provenance=e["provenance"],
            license=e.get("license", ""),
            phi_fields=tuple(e.get("phi_fields", ())),
            synthetic_verifiable=bool(e.get("synthetic_verifiable", False)),
            provider_terms_acknowledged=bool(e.get("provider_terms_acknowledged", False)),
            clinical_claim_allowed=bool(e.get("clinical_claim_allowed", False)),
        )
        for e in entries
    ]


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="CLARA 2027 SH-research_ethics")
    parser.add_argument("--declarations", default=None)
    parser.add_argument(
        "--out", default="research/venue2027/_shared/data_ethics_and_irb.md"
    )
    args = parser.parse_args(argv)

    verdicts: list[EthicsVerdict] = []
    declarations: list[DatasetDeclaration] = []
    if args.declarations:
        declarations = load_declarations(args.declarations)
        verdicts = [check_data_policy(d) for d in declarations]

    ok = all(v.ok for v in verdicts)
    lines = [
        "# Data ethics, IRB and synthetic-data policy",
        "",
        f"> Generated by `research/venue2027/_shared/tools/research_ethics.py` (version `{RESEARCH_ETHICS_VERSION}`).",
        "",
        "## Non-negotiable policy",
        "",
        "1. **No real PHI/PII.** Every 2027 study runs exclusively on synthetic or",
        "   public de-identified benchmark data. Provenance must be one of:",
        "   " + ", ".join(f"`{p}`" for p in SYNTHETIC_SOURCES) + ".",
        "2. **License required.** A dataset with no recorded license/permission is blocked.",
        f"3. **PHI-like fields** ({', '.join(PHI_LIKE_FIELDS)}) are permitted only when",
        "   provenance is `generated_synthetic` AND synthesis is verifiable.",
        "4. **No clinical-efficacy claims from synthetic data.** Synthetic action",
        "   correctness is a systems/engineering result, never clinical efficacy.",
        "5. **Provider terms + budget** must be acknowledged before any paid model call.",
        "6. **Human clinical review** must be performed by an independent, blinded",
        "   reviewer; a candidate-model agent may never certify its own oracle labels.",
        "",
        "## Dataset verdicts",
        "",
    ]
    if not verdicts:
        lines.append("_No dataset declarations supplied to this run._")
    for declaration, verdict in zip(declarations, verdicts, strict=True):
        state = "PASS" if verdict.ok else "BLOCKED"
        detail = ", ".join(verdict.reason_codes) if verdict.reason_codes else "compliant"
        lines.append(
            f"- `{declaration.dataset_id}` ({declaration.provenance}) — **{state}** ({detail})"
        )
    lines += [
        "",
        "## Reviewer consent and blinding",
        "",
        "- Clinical annotators consent to the study protocol; compensation and",
        "  eligibility are frozen before main-case release.",
        "- Reviewers are blinded to model arm; adjudication is independent of the",
        "  candidate implementation.",
        "",
        "## Result",
        "",
        f"Policy verdict: **{'PASS' if ok else 'BLOCKED'}**",
    ]
    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": ok,
                "verdicts": [v.to_dict() for v in verdicts],
                "out": args.out,
                "version": RESEARCH_ETHICS_VERSION,
            },
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
