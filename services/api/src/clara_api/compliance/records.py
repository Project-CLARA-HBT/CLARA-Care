"""Compliance records manifest (Req 6).

Assembles an auditor-facing manifest from the source-of-truth artifacts rather
than duplicating them: the human-authored governance documents under
``docs/compliance/``, the live ``TransferRegistry``, and the declared retention
policy. Served read-only to admins (Req 6.6 / Correctness Property 7).
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from clara_api.compliance.retention import policy_manifest
from clara_api.compliance.transfer import list_processors

# Governance documents that make up the statutory record set. Paths are relative
# to the repository root; the manifest reports presence without reading content.
GOVERNANCE_DOCUMENTS: tuple[dict[str, str], ...] = (
    {
        "id": "ropa",
        "title": "Record of Processing Activities (ROPA)",
        "path": "docs/compliance/ropa.md",
        "legal_basis": "PDPD 13/2023 Art. 24; AI Law 134/2025 record-keeping",
    },
    {
        "id": "risk_management_file",
        "title": "AI Risk-Management File",
        "path": "docs/compliance/risk-management-file.md",
        "legal_basis": "AI Law 134/2025 high-risk-system documentation",
    },
    {
        "id": "dpia",
        "title": "Data Protection Impact Assessment (DPIA)",
        "path": "docs/compliance/dpia.md",
        "legal_basis": "PDPD 13/2023 Art. 24 (sensitive-data DPIA)",
    },
    {
        "id": "transfer_impact_assessments",
        "title": "Transfer Impact Assessments (TIA)",
        "path": "docs/compliance/transfer-impact-assessments.md",
        "legal_basis": "PDPD 13/2023 Arts. 25-27 (cross-border transfer)",
    },
    {
        "id": "incident_log",
        "title": "Incident Log",
        "path": "docs/compliance/incident-log.md",
        "legal_basis": "AI Law 134/2025 serious-incident reporting",
    },
)


def _repo_root() -> Path:
    # compliance/records.py -> clara_api -> src -> api -> services -> <root>
    return Path(__file__).resolve().parents[5]


def _document_manifest() -> list[dict[str, object]]:
    root = _repo_root()
    out: list[dict[str, object]] = []
    for doc in GOVERNANCE_DOCUMENTS:
        present = (root / doc["path"]).is_file()
        out.append(
            {
                "id": doc["id"],
                "title": doc["title"],
                "path": doc["path"],
                "legal_basis": doc["legal_basis"],
                "present": present,
            }
        )
    return out


def records_manifest(db: Session) -> dict[str, object]:
    """Build the admin compliance-records manifest (Req 6.1-6.4)."""

    return {
        "ai_system_classification": {
            "system": "CLARA-Care clinical decision-support assistant",
            "classification": "high-risk AI system (health domain)",
            "device_status": "decision-support software; not a medical device; not an EMR/EHR",
            "legal_frameworks": [
                "AI Law No. 134/2025/QH15",
                "Decree No. 13/2023/ND-CP (PDPD)",
            ],
        },
        "documents": _document_manifest(),
        "transfer_registry": list_processors(db, active_only=False),
        "retention_policy": policy_manifest(),
    }
