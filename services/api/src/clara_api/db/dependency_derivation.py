"""Clinical Dependency Derivation Rules by Mutation Kind.

Spec: PH08 / A02 (Data Model & Migrations).
Formalizes normalized dependency derivation for Optimistic Concurrency Control:
- Medications mutations derive WRITE partition on "medications:{patient_id}" and READ on "careguard:policy".
- Vitals / Lab measurements derive WRITE partition on "vitals:{patient_id}" and READ on "phr:baseline".
- Clinical note transitions derive WRITE partition on "notes:{session_id}" and READ on "scribe:consent".
"""

from __future__ import annotations

import dataclasses
from typing import Any


@dataclasses.dataclass(frozen=True)
class DerivedDependencyVector:
    mutation_kind: str
    target_entity_key: str
    read_dependencies: list[str]
    write_dependencies: list[str]


MUTATION_DEPENDENCY_RULES: dict[str, dict[str, list[str]]] = {
    "MEDICATION_COURSE_CREATE": {
        "read": ["governance:medication_safety", "policy_epoch:medications"],
        "write_suffix": "medications",
    },
    "MEDICATION_COURSE_UPDATE": {
        "read": ["governance:medication_safety", "policy_epoch:medications"],
        "write_suffix": "medications",
    },
    "SCRIBE_NOTE_SIGN": {
        "read": ["consent:scribe", "policy_epoch:clinical_notes"],
        "write_suffix": "notes",
    },
    "COUNCIL_CONSENSUS_APPLY": {
        "read": ["governance:council_rules", "policy_epoch:council"],
        "write_suffix": "council_case",
    },
    "LIFEMAP_TASK_COMPLETE": {
        "read": ["consent:lifemap", "policy_epoch:tasks"],
        "write_suffix": "tasks",
    },
}


class DependencyDerivationEngine:
    """Derives required read and write partition dependencies for a given mutation."""

    @staticmethod
    def derive(mutation_kind: str, patient_or_session_id: str) -> DerivedDependencyVector:
        rule = MUTATION_DEPENDENCY_RULES.get(mutation_kind)
        if not rule:
            # Default fallback for unclassified mutations
            return DerivedDependencyVector(
                mutation_kind=mutation_kind,
                target_entity_key=f"default:{patient_or_session_id}",
                read_dependencies=["policy_epoch:default"],
                write_dependencies=[f"entity:{patient_or_session_id}"],
            )

        write_key = f"{rule['write_suffix']}:{patient_or_session_id}"
        return DerivedDependencyVector(
            mutation_kind=mutation_kind,
            target_entity_key=write_key,
            read_dependencies=rule["read"],
            write_dependencies=[write_key],
        )
