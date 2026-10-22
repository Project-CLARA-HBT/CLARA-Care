"""Control-Plane Database Schema Architecture Plan.

Spec: PH41 / A02 (Data & Migrations).
Details the physical segregation of the control plane database from the
data plane (clinical PHI database).
"""

from __future__ import annotations

CONTROL_PLANE_TABLES = [
    "control_tenants",
    "control_admin_users",
    "control_audit_logs",
    "control_feature_flags",
]

ISOLATION_INVARIANTS = {
    "zero_phi": "Control-plane schema has zero columns for patient clinical records, notes, prescriptions, or vitals.",
    "separate_database": "Uses separate DATABASE_CONTROL_URL connection pool and independent Alembic version directory.",
    "append_only_audit": "control_audit_logs enforces append-only immutability for governance defense.",
}
