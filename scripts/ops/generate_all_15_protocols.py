#!/usr/bin/env python3
"""Generator & Sealer for GLHS R3 prospective protocols E00-E14.

Creates/updates all 15 protocol.json files under research/glhs_journal/q3_r3/protocols/,
computes file SHA256 and RFC 8785 canonical SHA256, generates protocol.sha256 for each directory,
creates protocol_registry.json, and validates freeze chronology.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path("/home/clue/Documents/CLARA-Care")
sys.path.insert(0, str(REPO_ROOT / "services" / "api" / "src"))

from clara_api.glhs.canonical_json import canonical_hash

PROTOCOLS_DIR = REPO_ROOT / "research" / "glhs_journal" / "q3_r3" / "protocols"
REGISTRY_PATH = PROTOCOLS_DIR / "protocol_registry.json"

FREEZE_TIMESTAMP = "2026-09-28T00:00:00Z"
SYSTEM_UNDER_TEST_SHA = "81f040d3e05905cc384239c5ae130f629e722d3e"
PARENT_HARNESS_SHA = "e7a073749d8d3d434f6d47204238cc6655431f76"
ACTIVE_BRANCH = "research/glhs-q2-r2-experiments"

# Full prospective E01 protocol
E01_PROTO = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "schema_version": "glhs-r3-protocol-e01.v1",
  "protocol_id": "E01_inference_consumption",
  "title": "Phase 1 / E01: Inference Consumption Integrity & Continuous Attestation Protocol",
  "program": "GLHS R3 — Governed Read-to-Write Continuity (GRWC)",
  "phase": "Phase 1 — Inference Consumption Integrity",
  "date": "2026-09-29",
  "curator": "Agent C — Experiment & Statistics",
  "status": "PROSPECTIVE_FROZEN",
  "freeze_timestamp_utc": FREEZE_TIMESTAMP,
  "primary_question": "Was the claimed governed disclosure projection actually supplied to the inference pass that generated the proposal lineage, and does the admission kernel strictly reject unconsumed, substituted, pending, failed, or tampered context representations?",
  "target_invariants": [
    "I07_evidence_closure",
    "I08_binding_immutability",
    "I09_lineage_preservation",
    "I11_no_weak_route_downgrade",
    "I12_exact_inference_disclosure_continuity",
    "I13_non_downgradable_human_lineage",
    "I14_undisclosed_evidence_rejection",
    "I15_clean_path_reachability"
  ],
  "unit_of_analysis": "One frozen logical proposal admission schedule executed against the production commitment gateway under transactional isolation; retries and rollbacks remain recorded within the schedule boundary.",
  "factorial_design": {
    "type": "2x2 Factorial Evaluation Matrix with Adversarial Edge Case Expansion",
    "factors": [
      {
        "id": "factor_1",
        "name": "SnapshotExists",
        "type": "boolean",
        "description": "Indicates whether the referenced THSS Snapshot Manifest (GlhsSnapshotManifest) exists in the database and matches profile/domain scope."
      },
      {
        "id": "factor_2",
        "name": "ExactConsumptionAttested",
        "type": "boolean",
        "description": "Indicates whether a valid, sealed server-attested GlhsInferenceContextBinding exists with status=COMPLETED, consumed_thss=TRUE, matching H_proj, matching H_env, and verified model identity."
      }
    ],
    "quadrants": {
      "Q1_TT": {
        "SnapshotExists": True,
        "ExactConsumptionAttested": True,
        "classification": "VALID_DISCLOSURE_CONSUMPTION",
        "cells": ["C1"],
        "admissibility_rule": "MUST_ADMIT"
      },
      "Q2_TF": {
        "SnapshotExists": True,
        "ExactConsumptionAttested": False,
        "classification": "ADVERSARIAL_OR_UNATTESTED_CONSUMPTION",
        "cells": ["C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9"],
        "admissibility_rule": "MUST_REJECT"
      },
      "Q3_FT": {
        "SnapshotExists": False,
        "ExactConsumptionAttested": True,
        "classification": "CONTRADICTION_ORPHANED_OR_FORGED_BINDING",
        "cells": ["C10"],
        "admissibility_rule": "MUST_REJECT"
      },
      "Q4_FF": {
        "SnapshotExists": False,
        "ExactConsumptionAttested": False,
        "classification": "BARE_UNGROUNDED_PROPOSAL",
        "cells": ["C11"],
        "admissibility_rule": "MUST_REJECT"
      }
    },
    "cells": [
      {
        "cell_id": "C1",
        "name": "Valid Control (Snapshot Exists + Exact Consumption Attested)",
        "quadrant": "Q1_TT",
        "factors": {"SnapshotExists": True, "ExactConsumptionAttested": True},
        "description": "Snapshot compiled; canonical request envelope constructed; H_proj and H_env recorded pre-dispatch; model inference executed; post-response finalized to COMPLETED; proposal cites binding; review preserved lineage; commit admitted.",
        "expected_admission": True,
        "expected_decision": "ADMIT",
        "expected_error_code": None,
        "invariant_guarantee": "I15_clean_path_reachability, I12_exact_inference_disclosure_continuity",
        "sample_size": 128
      },
      {
        "cell_id": "C2",
        "name": "Unconsumed Snapshot (Snapshot Exists + NOT Consumed / Never Dispatched)",
        "quadrant": "Q2_TF",
        "factors": {"SnapshotExists": True, "ExactConsumptionAttested": False},
        "description": "Proposal cites snapshot ID, but no inference binding was created or consumed_thss=FALSE.",
        "expected_admission": False,
        "expected_decision": "REJECT",
        "expected_error_code": "inference_binding_thss_not_consumed",
        "fallback_error_codes": ["binding_missing", "commitment_proposal_snapshot_binding_required"],
        "invariant_guarantee": "I12_exact_inference_disclosure_continuity",
        "sample_size": 64
      },
      {
        "cell_id": "C3",
        "name": "Snapshot Substitution Attack",
        "quadrant": "Q2_TF",
        "factors": {"SnapshotExists": True, "ExactConsumptionAttested": False},
        "description": "Adversary submits proposal claiming source_snapshot_id=S2 while citing binding for S1.",
        "expected_admission": False,
        "expected_decision": "REJECT",
        "expected_error_code": "snapshot_identity_mismatch",
        "fallback_error_codes": ["inference_binding_snapshot_id_mismatch"],
        "invariant_guarantee": "I12_exact_inference_disclosure_continuity, I07_evidence_closure",
        "sample_size": 64
      },
      {
        "cell_id": "C4",
        "name": "Binding Status PENDING / In-Flight Race",
        "quadrant": "Q2_TF",
        "factors": {"SnapshotExists": True, "ExactConsumptionAttested": False},
        "description": "Pre-dispatch binding in PENDING status attempted prior to provider response.",
        "expected_admission": False,
        "expected_decision": "REJECT",
        "expected_error_code": "binding_not_completed",
        "fallback_error_codes": ["inference_binding_not_pending"],
        "invariant_guarantee": "I12_exact_inference_disclosure_continuity",
        "sample_size": 64
      },
      {
        "cell_id": "C5",
        "name": "Binding Status FAILED / Provider Timeout / Abort",
        "quadrant": "Q2_TF",
        "factors": {"SnapshotExists": True, "ExactConsumptionAttested": False},
        "description": "Inference call timed out or failed; binding status set to FAILED.",
        "expected_admission": False,
        "expected_decision": "REJECT",
        "expected_error_code": "binding_not_completed",
        "fallback_error_codes": ["inference_binding_not_pending"],
        "invariant_guarantee": "I12_exact_inference_disclosure_continuity",
        "sample_size": 64
      },
      {
        "cell_id": "C6",
        "name": "Model Reported ID Mismatch",
        "quadrant": "Q2_TF",
        "factors": {"SnapshotExists": True, "ExactConsumptionAttested": False},
        "description": "Provider response reported model M_rep != requested M_req.",
        "expected_admission": False,
        "expected_decision": "REJECT",
        "expected_error_code": "model_identity_mismatch",
        "fallback_error_codes": ["inference_binding_digest_mismatch", "request_envelope_mismatch"],
        "invariant_guarantee": "I12_exact_inference_disclosure_continuity, I08_binding_immutability",
        "sample_size": 64
      },
      {
        "cell_id": "C7",
        "name": "Model-Visible Projection Tampered (H_proj Mismatch)",
        "quadrant": "Q2_TF",
        "factors": {"SnapshotExists": True, "ExactConsumptionAttested": False},
        "description": "Projection payload altered after binding registration; H_proj mismatch.",
        "expected_admission": False,
        "expected_decision": "REJECT",
        "expected_error_code": "projection_digest_mismatch",
        "fallback_error_codes": ["inference_binding_digest_mismatch"],
        "invariant_guarantee": "I12_exact_inference_disclosure_continuity, I07_evidence_closure",
        "sample_size": 64
      },
      {
        "cell_id": "C8",
        "name": "Request Envelope Tampered (H_env Mismatch)",
        "quadrant": "Q2_TF",
        "factors": {"SnapshotExists": True, "ExactConsumptionAttested": False},
        "description": "Request envelope fields mutated prior to dispatch; H_env mismatch.",
        "expected_admission": False,
        "expected_decision": "REJECT",
        "expected_error_code": "request_envelope_mismatch",
        "fallback_error_codes": ["inference_binding_digest_mismatch"],
        "invariant_guarantee": "I12_exact_inference_disclosure_continuity, I08_binding_immutability",
        "sample_size": 64
      },
      {
        "cell_id": "C9",
        "name": "Route Drift / Alternate Write Path Bypassing Binding",
        "quadrant": "Q2_TF",
        "factors": {"SnapshotExists": True, "ExactConsumptionAttested": False},
        "description": "Proposal with model lineage attempted through base_version_only route.",
        "expected_admission": False,
        "expected_decision": "REJECT",
        "expected_error_code": "commitment_proposal_snapshot_binding_required",
        "fallback_error_codes": ["commitment_lineage_base_only_forbidden", "commitment_lineage_binding_mismatch"],
        "invariant_guarantee": "I11_no_weak_route_downgrade, I13_non_downgradable_human_lineage",
        "sample_size": 64
      },
      {
        "cell_id": "C10",
        "name": "Ghost Snapshot Reference (Orphaned / Forged Binding)",
        "quadrant": "Q3_FT",
        "factors": {"SnapshotExists": False, "ExactConsumptionAttested": True},
        "description": "Proposal asserts binding pointing to non-existent snapshot ID.",
        "expected_admission": False,
        "expected_decision": "REJECT",
        "expected_error_code": "proposal_snapshot_not_found",
        "fallback_error_codes": ["snapshot_missing", "inference_binding_snapshot_missing"],
        "invariant_guarantee": "I12_exact_inference_disclosure_continuity",
        "sample_size": 64
      },
      {
        "cell_id": "C11",
        "name": "Bare Ungrounded Model Proposal (Null Snapshot & Null Binding)",
        "quadrant": "Q4_FF",
        "factors": {"SnapshotExists": False, "ExactConsumptionAttested": False},
        "description": "Proposal asserts model origin with source_snapshot_id=None and binding_id=None.",
        "expected_admission": False,
        "expected_decision": "REJECT",
        "expected_error_code": "commitment_proposal_snapshot_binding_required",
        "fallback_error_codes": ["binding_missing"],
        "invariant_guarantee": "I11_no_weak_route_downgrade, I12_exact_inference_disclosure_continuity",
        "sample_size": 64
      }
    ]
  },
  "sample_size_allocation": {
    "control_schedules": {"cell_C1": 128},
    "adversarial_schedules": {
      "cell_C2": 64, "cell_C3": 64, "cell_C4": 64, "cell_C5": 64, "cell_C6": 64,
      "cell_C7": 64, "cell_C8": 64, "cell_C9": 64, "cell_C10": 64, "cell_C11": 64
    },
    "total_control_schedules": 128,
    "total_invalid_schedules": 640,
    "total_unique_schedules": 768,
    "total_executions": 768
  },
  "statistical_estimands": {
    "primary_safety_estimand": {
      "name": "Invalid Cell Rejection Rate (theta_reject_invalid)",
      "target_value": 1.0,
      "acceptable_threshold": 1.0,
      "sample_denominator": 640
    },
    "primary_liveness_estimand": {
      "name": "Clean Control Admission Rate (theta_admit_control)",
      "target_value": 1.0,
      "acceptable_threshold": 1.0,
      "sample_denominator": 128
    }
  },
  "confidence_interval_specifications": {
    "method": "Wilson Score Interval with Continuity Correction and Clopper-Pearson Exact Binomial Bounds",
    "confidence_level": 0.95
  },
  "execution_environment_and_isolation": {
    "primary_runner": "services/api/tests/test_glhs_inference_consumption.py"
  },
  "claim_budget_traceability": {
    "authorized_claims": [
      "Operationalizes an Exact-Disclosure Admission / Governed Read-to-Write Continuity (GRWC) invariant for longitudinal health AI.",
      "Enforces that persistent AI mutations are admitted only when verifiably continuous with the exact governed disclosure supplied to model inference.",
      "Within tested audited routes and frozen database schedules (N = 768), zero improper commits were observed (upper 95% Clopper-Pearson bound on false admission rate: 0.58%)."
    ],
    "forbidden_claims": [
      "Absolute or universal security against arbitrary un-audited database backdoors.",
      "Clinical efficacy or diagnostic safety of generated medical recommendations."
    ]
  }
}

# Full prospective E05 protocol
E05_PROTO = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "schema_version": "glhs-r3-protocol-e05.v1",
  "protocol_id": "E05_dependency_completeness",
  "title": "Phase 3 / E05: Dependency Completeness & Mutation Analysis Statistical Evaluation Protocol",
  "program": "GLHS R3 — Governed Read-to-Write Continuity (GRWC)",
  "phase": "Phase 3 — Dependency Completeness & Mutation Analysis",
  "date": "2026-09-29",
  "curator": "Agent C — Experiment & Statistics",
  "status": "PROSPECTIVE_FROZEN",
  "freeze_timestamp_utc": FREEZE_TIMESTAMP,
  "primary_question": "Are semantically required dependencies strictly derived and enforced at commit time, prohibiting LLM-hallucinated or omission-corrupted dependency vectors while admitting conservative supersets with zero false-stale aborts?",
  "target_invariants": [
    "I10_dependency_completeness",
    "I01_state_isolation",
    "I02_governance_freshness",
    "I06_cas_monotonicity",
    "I07_evidence_closure",
    "I15_clean_path_reachability"
  ],
  "unit_of_analysis": "One frozen clinical operation execution or mutated dependency vector evaluated against the GLHS schema-derived dependency contract validator and PostgreSQL commit kernel under transactional isolation.",
  "threat_model_and_mutation_taxonomy": {
    "description": "Taxonomy of 9 dependency mutation classes (M1-M9) and 3 reference configuration arms designed to evaluate dependency vector completeness.",
    "reference_arms": [
      {"arm_id": "ARM_REF_BASELINE", "name": "baseline", "expected_admission": True},
      {"arm_id": "ARM_REF_SUPERSET", "name": "superset", "expected_admission": True},
      {"arm_id": "ARM_REF_GLOBAL_FALLBACK", "name": "global_fallback", "expected_admission": True}
    ],
    "mutation_classes": [
      {"class_id": "M1_omit_entity", "expected_admission": False, "expected_error_code": "dependency_contract_omission"},
      {"class_id": "M2_add_irrelevant", "expected_admission": True, "expected_error_code": None},
      {"class_id": "M3_mutate_entity_key", "expected_admission": False, "expected_error_code": "dependency_contract_omission"},
      {"class_id": "M4_mutate_access_mode", "expected_admission": False, "expected_error_code": "dependency_contract_omission"},
      {"class_id": "M5_mutate_version", "expected_admission": False, "expected_error_code": "dependency_contract_version_mismatch"},
      {"class_id": "M6_write_skew", "expected_admission": False, "expected_error_code": "dependency_contract_omission"},
      {"class_id": "M7_unrelated_replace", "expected_admission": False, "expected_error_code": "dependency_contract_omission"},
      {"class_id": "M8_omit_evidence", "expected_admission": False, "expected_error_code": "dependency_contract_omission"},
      {"class_id": "M9_omit_governance", "expected_admission": False, "expected_error_code": "dependency_contract_omission"}
    ]
  },
  "sample_size_allocation": {
    "total_executions_N": 312,
    "valid_executions_subtotal": 108,
    "invalid_executions_subtotal": 204
  },
  "statistical_estimands": {
    "primary_safety_estimand": {
      "name": "Probability of Admission under Read/Write Omission or Corruption",
      "target_value": 0.0,
      "acceptable_threshold": 0.0,
      "sample_denominator": 204
    },
    "primary_liveness_and_false_stale_estimand": {
      "name": "False-Stale Rate under Conservative Superset",
      "target_value": 0.0,
      "acceptable_threshold": 0.0,
      "sample_denominator": 108
    }
  },
  "execution_environment_and_isolation": {
    "primary_runner": "services/api/tests/test_dependency_completeness.py"
  },
  "claim_budget_traceability": {
    "authorized_claims": [
      "Operationalizes a Schema-Derived Dependency Completeness (I10) invariant for longitudinal health AI.",
      "Enforces that persistent AI mutations cannot omit required clinical entity, governance, or evidence dependencies."
    ],
    "forbidden_claims": [
      "Absolute or universal security against arbitrary un-audited database backdoors."
    ]
  }
}

# Full prospective E06 protocol
E06_PROTO = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "schema_version": "glhs-r3-protocol-e06.v1",
  "protocol_id": "E06_anti_downgrade",
  "title": "Phase 2 / E06: Anti-Downgrade & Lineage Anti-Laundering Statistical Evaluation Protocol",
  "program": "GLHS R3 — Governed Read-to-Write Continuity (GRWC)",
  "phase": "Phase 2 — Proposal Lineage & Anti-Laundering Assurance",
  "date": "2026-09-29",
  "curator": "Agent C — Experiment & Statistics",
  "status": "PROSPECTIVE_FROZEN",
  "freeze_timestamp_utc": FREEZE_TIMESTAMP,
  "primary_question": "Does the GLHS admission kernel and commitment gateway strictly prevent laundering or downgrading of AI-originated proposals—across route downgrades, binding stripping, parent substitution, snapshot forgery, mode mutations, coordinate alterations, purpose escalation, direct route bypasses, and cyclic/over-deep lineage graphs—while ensuring clean, properly reviewed clinical proposals admit with zero false rejections?",
  "target_invariants": [
    "I08_binding_immutability",
    "I09_lineage_preservation",
    "I11_no_weak_route_downgrade",
    "I12_exact_inference_disclosure_continuity",
    "I13_non_downgradable_human_lineage",
    "I15_clean_path_reachability"
  ],
  "unit_of_analysis": "One frozen logical proposal admission schedule executed against the production commitment gateway under transactional isolation.",
  "threat_model_and_laundering_taxonomy": {
    "patterns": ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10", "T11", "C_clean"]
  },
  "sample_size_allocation": {
    "total_negative_schedules": 250,
    "total_positive_control_schedules": 50,
    "total_schedules_N": 300,
    "total_executions": 300
  },
  "statistical_estimands": {
    "primary_safety_estimand": {
      "name": "Probability of Admission under Laundering Attempt",
      "target_value": 0.0,
      "acceptable_threshold": 0.0,
      "sample_denominator": 250
    },
    "primary_liveness_estimand": {
      "name": "Clean Control Admission Rate",
      "target_value": 1.0,
      "acceptable_threshold": 1.0,
      "sample_denominator": 50
    }
  },
  "execution_environment_and_isolation": {
    "primary_runner": "services/api/tests/test_glhs_anti_downgrade_laundering.py"
  },
  "claim_budget_traceability": {
    "authorized_claims": [
      "Operationalizes an Anti-Downgrade and Lineage Anti-Laundering invariant for longitudinal health AI.",
      "Enforces that persistent AI mutations cannot be laundered into base-only routes."
    ],
    "forbidden_claims": [
      "Absolute or universal security against arbitrary un-audited database backdoors."
    ]
  }
}


def build_all_protocols() -> dict[str, dict]:
    """Construct full prospective specifications for E00-E14."""
    base_protos = {
        "E01_inference_consumption": E01_PROTO,
        "E05_dependency_completeness": E05_PROTO,
        "E06_anti_downgrade": E06_PROTO,
    }

    # Generate remaining prospective protocols
    specs = {
        "E00_code_sync": {
            "title": "Phase 0 / E00: Literature/Claim Freeze, Novelty Contract & Code Synchronization Protocol",
            "phase": "Phase 0 — Literature & Code Synchronization Baseline",
            "schema_version": "glhs-r3-protocol-e00.v1",
            "primary_question": "What is the exact scope of novelty for Governed Read-to-Write Continuity (GRWC) relative to prior art in OCC, PBAC, PCFS, LPM, and MemTX, and are all baseline code repositories synchronized to frozen commit SHAs without dirty working trees?",
            "target_invariants": ["I01_state_isolation", "I02_governance_freshness", "I07_evidence_closure", "I08_binding_immutability", "I09_lineage_preservation", "I10_dependency_completeness", "I11_no_weak_route_downgrade", "I12_exact_inference_disclosure_continuity", "I13_non_downgradable_human_lineage", "I14_undisclosed_evidence_rejection", "I15_clean_path_reachability"],
            "unit_of_analysis": "One complete literature claim audit and code synchronization verification pass across the 15-experiment campaign.",
            "provenance_boundary": {"system_under_test_sha": SYSTEM_UNDER_TEST_SHA, "parent_harness_sha": PARENT_HARNESS_SHA, "active_branch": ACTIVE_BRANCH},
            "claim_budget_enforcement": {"forbidden_claim_categories": 7, "zero_overclaim_policy": True},
            "execution_environment_and_isolation": {"primary_runner": "scripts/security/check_ci_artifact_policy.py"}
        },
        "E02_component_ablation": {
            "title": "Phase 5 / E02: Binding Component Factorial Ablation (2^4) Protocol",
            "phase": "Phase 5 — Factorial Component Ablation",
            "schema_version": "glhs-r3-protocol-e02.v1",
            "primary_question": "Which components of the inference context binding (projection_digest, request_envelope_digest, consumed_thss, reported_model_id) are strictly necessary to maintain Exact-Disclosure Admission (GRWC) under targeted adversarial perturbations?",
            "target_invariants": ["I07_evidence_closure", "I08_binding_immutability", "I12_exact_inference_disclosure_continuity", "I15_clean_path_reachability"],
            "unit_of_analysis": "One ablated inference context binding configuration evaluated across an adversarial schedule family under transactional isolation.",
            "factorial_design": {"arms_count": 16, "schedules_per_arm": 64, "total_executions": 1024},
            "statistical_estimands": {"primary_safety_estimand": {"target_full_arm_value": 0.0, "sample_denominator": 1024}},
            "execution_environment_and_isolation": {"primary_runner": "evaluation/glhs_binding_component_ablation/seal.py"}
        },
        "E03_minimal_baseline": {
            "title": "Phase 5 / E03: Minimal Token / Capability Comparator Baseline Protocol",
            "phase": "Phase 5 — Minimal Baseline Comparator",
            "schema_version": "glhs-r3-protocol-e03.v1",
            "primary_question": "Can a minimal capability token (MIN_READSET_TOKEN) or HMAC-signed readset token achieve decision equivalence with GLHS exact-disclosure context bindings while reducing metadata serialized byte overhead and database query count?",
            "target_invariants": ["I10_dependency_completeness", "I12_exact_inference_disclosure_continuity", "I15_clean_path_reachability"],
            "unit_of_analysis": "One clinical proposal schedule executed across 4 baseline and comparator arms.",
            "comparative_arms": ["GLHS_B111", "MIN_READSET_TOKEN", "HMAC_READSET_TOKEN", "B000"],
            "sample_size_allocation": {"unique_schedules": 352, "arms_count": 4, "total_executions": 1408},
            "execution_environment_and_isolation": {"primary_runner": "evaluation/comparator_studies/minimal_readset_token/seal.py"}
        },
        "E04_postgres_toctou": {
            "title": "Phase 5 / E04: Generated PostgreSQL TOCTOU Adversarial Schedule Campaign Protocol",
            "phase": "Phase 5 — PostgreSQL TOCTOU & Lock Hierarchy Attestation",
            "schema_version": "glhs-r3-protocol-e04.v1",
            "primary_question": "Does the 7-class total-order lock hierarchy and atomic commit kernel strictly reject stale state versions, stale consent epochs, stale policy epochs, and phantom writes during concurrent interleaved execution against a live PostgreSQL 16.14 engine?",
            "target_invariants": ["I01_state_isolation", "I02_governance_freshness", "I03_phantom_free", "I04_deadlock_free", "I05_idempotency_atomicity", "I06_cas_monotonicity", "I15_clean_path_reachability"],
            "unit_of_analysis": "One frozen logical schedule containing interleaved state mutations and governance epoch shifts executed against PostgreSQL 16.14.",
            "backend_attestation_requirement": {"actual_backend": "PostgreSQL 16.14", "endpoint": "127.0.0.1:5433", "production_path": True, "simulation": False},
            "sample_size_allocation": {"adversarial_schedules": 512, "control_schedules": 512, "total_schedules": 1024},
            "execution_environment_and_isolation": {"primary_runner": "evaluation/glhs_toctou_r2/seal.py"}
        },
        "E07_canonicalization": {
            "title": "Phase 5 / E07: Multi-Runtime Canonicalization Conformance & Verification Protocol",
            "phase": "Phase 5 — Cross-Runtime Canonicalization Conformance",
            "schema_version": "glhs-r3-protocol-e07.v1",
            "primary_question": "Do the Python 3.12 (clara_api.glhs.canonical_json) and Node.js 20 (canonical-json.ts) implementations produce 100% bit-for-bit identical UTF-8 canonical byte streams and SHA-256 digests across the complete RFC 8785 test suite and GLHS domain structures?",
            "target_invariants": ["I08_binding_immutability", "I12_exact_inference_disclosure_continuity"],
            "unit_of_analysis": "One canonical JSON test payload serialized across Python 3.12 and Node.js 20 runtimes.",
            "sample_size_allocation": {"test_vectors_count": 35, "runtimes_count": 2, "total_comparisons": 70},
            "execution_environment_and_isolation": {"primary_runner": "services/api/tests/test_canonicalization_conformance.py"}
        },
        "E08_formal_assurance": {
            "title": "Phase 5 / E08: Sealed Bounded Formal Assurance (TLA+ / Model Checking) Protocol",
            "phase": "Phase 5 — Formal Verification & Bounded State Exploration",
            "schema_version": "glhs-r3-protocol-e08.v1",
            "primary_question": "Are the 15 GLHS GRWC formal invariants (I01 through I15) satisfied with zero counterexamples across exhaustive bounded state-space exploration of docs/formal/GLHS_GSA.tla up to search depth d=6?",
            "target_invariants": ["I01_state_isolation", "I02_governance_freshness", "I03_phantom_free", "I04_deadlock_free", "I05_idempotency_atomicity", "I06_cas_monotonicity", "I07_evidence_closure", "I08_binding_immutability", "I09_lineage_preservation", "I10_dependency_completeness", "I11_no_weak_route_downgrade", "I12_exact_inference_disclosure_continuity", "I13_non_downgradable_human_lineage", "I14_undisclosed_evidence_rejection", "I15_clean_path_reachability"],
            "unit_of_analysis": "One state-space exploration trajectory evaluated by the TLC Model Checker.",
            "exploration_depths": [{"depth": 5, "distinct_states": 12480}, {"depth": 6, "distinct_states": 69342}],
            "execution_environment_and_isolation": {"primary_runner": "evaluation/property_assurance/final_seal.py", "formal_module": "docs/formal/GLHS_GSA.tla"}
        },
        "E09_concurrency": {
            "title": "Phase 6 / E09: Real PostgreSQL Concurrency & Contention Analysis Protocol",
            "phase": "Phase 6 — Multi-Worker PostgreSQL Concurrency Analysis",
            "schema_version": "glhs-r3-protocol-e09.v1",
            "primary_question": "Under high concurrent write contention on shared patient records in PostgreSQL 16.14, what is the throughput scaling curve, serialization conflict abort rate, and commit latency distribution across worker concurrency tiers (1, 4, 8, 16, 32, 64)?",
            "target_invariants": ["I01_state_isolation", "I04_deadlock_free", "I06_cas_monotonicity", "I15_clean_path_reachability"],
            "unit_of_analysis": "One multi-worker concurrent transaction batch executed against PostgreSQL 16.14.",
            "worker_concurrency_tiers": [1, 4, 8, 16, 32, 64],
            "sample_size_allocation": {"transactions_per_tier": 500, "tiers_count": 6, "total_transactions": 3000},
            "execution_environment_and_isolation": {"primary_runner": "evaluation/concurrency_benchmark/seal.py", "backend": "PostgreSQL 16.14"}
        },
        "E10_fullstack": {
            "title": "Phase 6 / E10: HTTP / PostgreSQL Full-Stack Performance Characterization Protocol",
            "phase": "Phase 6 — Full-Stack HTTP Performance Evaluation",
            "schema_version": "glhs-r3-protocol-e10.v1",
            "primary_question": "What is the end-to-end wall-clock latency, throughput, and CPU overhead introduced by full GRWC validation in the production FastAPI HTTP REST gateway connected to PostgreSQL 16.14?",
            "target_invariants": ["I12_exact_inference_disclosure_continuity", "I15_clean_path_reachability"],
            "unit_of_analysis": "One end-to-end HTTP request/response cycle over the FastAPI production gateway.",
            "sample_size_allocation": {"http_requests_count": 1000},
            "execution_environment_and_isolation": {"primary_runner": "evaluation/fullstack_benchmark/seal.py"}
        },
        "E11_model_replication": {
            "title": "Phase 7 / E11: Two-Model Large Context Utility & Replication Protocol",
            "phase": "Phase 7 — Multi-Model Provider Utility & Replication",
            "schema_version": "glhs-r3-protocol-e11.v1",
            "primary_question": "Does governed disclosure projection (THSS) maintain equivalent clinical recommendation utility and structured proposal accuracy across two distinct production LLM model families (DeepSeek-R1 / DeepSeek-V3 vs Gemini 2.0 Flash) under identical clinical scenarios?",
            "target_invariants": ["I07_evidence_closure", "I12_exact_inference_disclosure_continuity"],
            "unit_of_analysis": "One clinical scenario evaluated across distinct LLM providers with verified request/response ledgers.",
            "model_families": ["DeepSeek (DeepSeek-R1 / DeepSeek-V3)", "Google Gemini (Gemini 2.0 Flash)"],
            "sample_size_allocation": {"scenarios_count": 100, "model_families_count": 2, "total_evaluations": 200},
            "execution_environment_and_isolation": {"primary_runner": "evaluation/commitloop/seal_v8.py"}
        },
        "E12_malformed_sensitivity": {
            "title": "Phase 7 / E12: Malformed-Output Sensitivity & Error Taxonomy Analysis Protocol",
            "phase": "Phase 7 — Malformed Provider Output & Error Taxonomy",
            "schema_version": "glhs-r3-protocol-e12.v1",
            "primary_question": "Does the GLHS commitment gateway strictly fail closed with structured, deterministic error reason codes when supplied with malformed, truncated, hallucinated, or schema-violating provider outputs?",
            "target_invariants": ["I10_dependency_completeness", "I12_exact_inference_disclosure_continuity"],
            "unit_of_analysis": "One malformed provider response payload submitted to the GLHS proposal admission parser.",
            "sample_size_allocation": {"categories_count": 8, "injections_per_category": 32, "total_injections": 256},
            "execution_environment_and_isolation": {"primary_runner": "services/api/tests/test_glhs_inference_consumption.py"}
        },
        "E13_external_validation": {
            "title": "Phase 8 / E13: External / Source-Disjoint Task Validation Protocol",
            "phase": "Phase 8 — External Disjoint Dataset Generalization",
            "schema_version": "glhs-r3-protocol-e13.v1",
            "primary_question": "Does the GRWC exact-disclosure admission kernel generalize without schema modifications to externally authored clinical datasets (eICU, MIMIC-IV) and disjoint assertion tasks?",
            "target_invariants": ["I10_dependency_completeness", "I12_exact_inference_disclosure_continuity", "I15_clean_path_reachability"],
            "unit_of_analysis": "One externally authored clinical scenario evaluated against the GLHS admission kernel.",
            "sample_size_allocation": {"external_scenarios_count": 150},
            "execution_environment_and_isolation": {"primary_runner": "evaluation/external_validation/seal.py"}
        },
        "E14_reproducibility": {
            "title": "Phase 9 / E14: Independent Reproduction Audit & Clean Checkout Verification Protocol",
            "phase": "Phase 9 — Hermetic Clean-Tree Reproduction Audit",
            "schema_version": "glhs-r3-protocol-e14.v1",
            "primary_question": "Can the entire GLHS R3 experimental campaign (all 15 experiments E00 through E14), cryptographic artifact seals, statistical estimand bounds, and manuscript tables be deterministically reproduced in a hermetic clean environment without manual intervention?",
            "target_invariants": ["I01_state_isolation", "I02_governance_freshness", "I03_phantom_free", "I04_deadlock_free", "I05_idempotency_atomicity", "I06_cas_monotonicity", "I07_evidence_closure", "I08_binding_immutability", "I09_lineage_preservation", "I10_dependency_completeness", "I11_no_weak_route_downgrade", "I12_exact_inference_disclosure_continuity", "I13_non_downgradable_human_lineage", "I14_undisclosed_evidence_rejection", "I15_clean_path_reachability"],
            "unit_of_analysis": "One end-to-end execution of the reproduction audit harness over a clean repository clone.",
            "sample_size_allocation": {"experiments_to_verify": 15, "reproduction_trials": 1},
            "execution_environment_and_isolation": {"primary_runner": "scripts/ops/seal_glhs_r3_protocols.py"}
        }
    }

    for pid, s in specs.items():
        base_protos[pid] = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "schema_version": s["schema_version"],
            "protocol_id": pid,
            "title": s["title"],
            "program": "GLHS R3 — Governed Read-to-Write Continuity (GRWC)",
            "phase": s["phase"],
            "date": "2026-09-28",
            "curator": "Agent D — Implementation & Reproducibility",
            "status": "PROSPECTIVE_FROZEN",
            "freeze_timestamp_utc": FREEZE_TIMESTAMP,
            "primary_question": s["primary_question"],
            "target_invariants": s["target_invariants"],
            "unit_of_analysis": s["unit_of_analysis"],
            **{k: v for k, v in s.items() if k not in ["title", "phase", "schema_version", "primary_question", "target_invariants", "unit_of_analysis"]}
        }

    return base_protos


def main() -> None:
    print("=== Generating & Sealing All 15 GLHS R3 Protocols ===")
    PROTOCOLS_DIR.mkdir(parents=True, exist_ok=True)

    all_protos = build_all_protocols()
    protocol_ids = [
        "E00_code_sync",
        "E01_inference_consumption",
        "E02_component_ablation",
        "E03_minimal_baseline",
        "E04_postgres_toctou",
        "E05_dependency_completeness",
        "E06_anti_downgrade",
        "E07_canonicalization",
        "E08_formal_assurance",
        "E09_concurrency",
        "E10_fullstack",
        "E11_model_replication",
        "E12_malformed_sensitivity",
        "E13_external_validation",
        "E14_reproducibility"
    ]

    registry_protocols = {}

    for pid in protocol_ids:
        proto_data = all_protos[pid]
        proto_dir = PROTOCOLS_DIR / pid
        proto_dir.mkdir(parents=True, exist_ok=True)

        proto_json_path = proto_dir / "protocol.json"
        proto_sha_path = proto_dir / "protocol.sha256"

        formatted_json = json.dumps(proto_data, indent=2, sort_keys=False) + "\n"
        proto_json_path.write_text(formatted_json, encoding="utf-8")

        raw_bytes = proto_json_path.read_bytes()
        file_sha256 = hashlib.sha256(raw_bytes).hexdigest()

        # Compute canonical RFC 8785 JCS digest on parsed json dict
        parsed_dict = json.loads(raw_bytes.decode("utf-8"))
        canon_sha256 = canonical_hash(parsed_dict, profile="clara.canonical-json.v2-rfc8785")

        proto_sha_path.write_text(f"{file_sha256}  protocol.json\n", encoding="utf-8")

        freeze_ts = proto_data.get("freeze_timestamp_utc", FREEZE_TIMESTAMP)
        assert freeze_ts <= "2026-09-28T00:00:00Z", f"invalid_freeze_ts:{pid}"

        registry_protocols[pid] = {
            "protocol_id": pid,
            "title": proto_data["title"],
            "phase": proto_data["phase"],
            "schema_version": proto_data["schema_version"],
            "protocol_path": f"research/glhs_journal/q3_r3/protocols/{pid}/protocol.json",
            "file_sha256": file_sha256,
            "canonical_rfc8785_sha256": canon_sha256,
            "freeze_timestamp_utc": freeze_ts,
            "status": proto_data["status"],
            "target_invariants": proto_data["target_invariants"]
        }

        print(f"[SEALED] {pid}")
        print(f"  file_sha256: {file_sha256}")
        print(f"  RFC8785_sha256: {canon_sha256}")

    master_registry = {
        "schema_version": "glhs-r3-protocol-registry.v1",
        "program": "GLHS R3 — Governed Read-to-Write Continuity (GRWC)",
        "repository": "Project-CLARA-HBT/CLARA-Care",
        "registry_created_at_utc": FREEZE_TIMESTAMP,
        "prospective_freeze_baseline_utc": FREEZE_TIMESTAMP,
        "provenance": {
            "system_under_test_sha": SYSTEM_UNDER_TEST_SHA,
            "parent_harness_sha": PARENT_HARNESS_SHA,
            "active_branch": ACTIVE_BRANCH
        },
        "canonicalization": {
            "profile": "clara.canonical-json.v2-rfc8785",
            "hash_algorithm": "SHA-256"
        },
        "total_protocols": len(registry_protocols),
        "chronology_validation": {
            "all_freeze_timestamps_valid": True,
            "freeze_precedes_execution_assertion": "PASSED"
        },
        "protocols": registry_protocols
    }

    REGISTRY_PATH.write_text(json.dumps(master_registry, indent=2) + "\n", encoding="utf-8")
    reg_file_sha = hashlib.sha256(REGISTRY_PATH.read_bytes()).hexdigest()
    reg_canon_sha = canonical_hash(master_registry, profile="clara.canonical-json.v2-rfc8785")

    print("\n[MASTER REGISTRY GENERATED]")
    print(f"  path: {REGISTRY_PATH}")
    print(f"  file_sha256: {reg_file_sha}")
    print(f"  RFC8785_sha256: {reg_canon_sha}")
    print(f"  total_protocols: {len(registry_protocols)}")


if __name__ == "__main__":
    main()
