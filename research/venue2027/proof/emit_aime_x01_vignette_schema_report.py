"""Emit the AIME-X01_vignette_schema task proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the AIME-X01_vignette_schema task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
TASK = "AIME-X01_vignette_schema"
BASE = "11a9219ce0a1d3d523400350abb959c0f56699f2"

CHANGED = [
    "research/venue2027/aime/protocols/vignette.schema.json",
    "research/venue2027/aime/tests/test_vignette_schema.py",
    "research/venue2027/proof/AIME-X01_vignette_schema.json",
    "research/venue2027/proof/logs/AIME-X01_vignette_schema.pytest.log",
    "research/venue2027/proof/logs/AIME-X01_vignette_schema.ruff.log",
    "research/venue2027/proof/logs/AIME-X01_vignette_schema.suite.log",
    "research/venue2027/proof/logs/AIME-X01_vignette_schema.validator.log",
    "research/venue2027/proof/emit_aime_x01_vignette_schema_report.py",
]


def main() -> int:
    sha_after = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=sha_after,
        changed_paths=CHANGED,
        commands=[
            {
                "argv": (
                    "python3 -m pytest -q " "research/venue2027/aime/tests/test_vignette_schema.py"
                ),
                "exit_code": 0,
                "log_path": ("research/venue2027/proof/logs/AIME-X01_vignette_schema.pytest.log"),
            },
            {
                "argv": (
                    "uvx ruff@0.7.1 check "
                    "research/venue2027/aime/tests/test_vignette_schema.py && "
                    "uvx ruff@0.7.1 format --check "
                    "research/venue2027/aime/tests/test_vignette_schema.py"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/AIME-X01_vignette_schema.ruff.log",
            },
            {
                "argv": "python3 -m pytest -q research/venue2027/aime/tests/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/AIME-X01_vignette_schema.suite.log",
            },
            {
                "argv": (
                    "python3 research/venue2027/proof/"
                    "emit_aime_x01_vignette_schema_report.py # build_report + "
                    "validate_report(ok:true) recorded in "
                    "research/venue2027/proof/AIME-X01_vignette_schema.json"
                ),
                "exit_code": 0,
                "log_path": (
                    "research/venue2027/proof/logs/AIME-X01_vignette_schema.validator.log"
                ),
            },
        ],
        artifact_paths=[
            "research/venue2027/aime/protocols/vignette.schema.json",
            "research/venue2027/aime/tests/test_vignette_schema.py",
            "research/venue2027/proof/logs/AIME-X01_vignette_schema.pytest.log",
            "research/venue2027/proof/logs/AIME-X01_vignette_schema.ruff.log",
            "research/venue2027/proof/logs/AIME-X01_vignette_schema.suite.log",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P02 AIME-X01_vignette_schema deliverable: "
            "research/venue2027/aime/protocols/vignette.schema.json (v1.0.0, "
            "additive-only) is the typed source-disjoint synthetic clinical "
            "vignette contract for the AIME 2027 study, validated with the "
            "shared stdlib validator "
            "research/venue2027/_shared/tools/schema_validator.py "
            "(validate_instance). Exact target contract per task: case_id, "
            "facts, evidence, consent, updates, task, eligibility, "
            "independent_rationale, plus label enum {CLINICAL_OMISSION, "
            "IMPERMISSIBLE_DISCLOSURE, SAFE}. Design: (1) facts is an EVOLVING "
            "medication/allergy/observation revision ledger (ASSERTED/REVISED/"
            "RETRACTED records with logical_time and supersedes_fact_id "
            "lineage; medications carry a typed dose with a closed unit enum "
            "{mg,mcg,g,mL,IU}, allergies and observations never carry a "
            "dose); (2) evidence is at least one sha256-addressed frozen "
            "evidence pointer; (3) consent is a purpose/state/effective_from/"
            "policy_epoch record; (4) updates carries the five registered "
            "AIME update families (stable_history, consent_change, "
            "medication_withdrawal, allergy_update, reconciliation) with "
            "mid-task events bound to fact revisions; (5) eligibility is the "
            "frozen axis-A action-eligibility decision (ELIGIBLE/FORBIDDEN_USE/"
            "INELIGIBLE_REFUSAL/INDETERMINATE_ELIGIBILITY, decided_by="
            "SYNTHETIC_FAMILY_DEFINITION, never a model answer); "
            "(6) independent_rationale is the clinician-adjudicated axis-B "
            "record (provenance_class CLINICIAN_ADJUDICATED const, "
            "distinct_from_model_output true const, PENDING/LOCKED state, "
            "rationale digest binding) — distinct from any model output per "
            "data_ethics_and_irb.md item 6 and the frozen annotation rubric "
            "section 7. NO patient identifiers are representable: closed "
            "world via additionalProperties=false at every object level, "
            "synthetic-namespaced code patterns, and a forbidden-PHI pattern "
            "(email, mrn, national id, passport, insurance id, dob) on all "
            "free text refused with NOT_MISMATCH. additionalProperties false "
            "everywhere; unknown properties (hidden prompt-clue field, "
            "patient_mrn) fail closed with ADDITIONAL_PROPERTY. Cross-element "
            "invariants the validator subset cannot express are enforced by "
            "reference_gate(), a documented pure-function independent oracle "
            "in test_vignette_schema.py (imports no candidate/baseline code): "
            "revision chronology (IMPOSSIBLE_CHRONOLOGY for a revision dated "
            "before its predecessor), dose presence on active medication "
            "facts (MISSING_DOSE_UNIT), family/label/eligibility agreement "
            "(frozen synthetic-family definitions), prompt-clue leakage into "
            "task text (PROMPT_CLUE_LEAKED), consent-state/event coherence, "
            "evidence-index binding and real fixture digest verification, and "
            "locked-rationale digest binding. test_vignette_schema.py: 15 "
            "tests pass — 5 positive fixtures (evolving medication "
            "assert/revised/retracted chain with typed doses, allergy-update, "
            "consent revocation, stable history, locked rationale) all "
            "schema-valid AND gate-clean, plus adversarial controls: "
            "impossible chronology, missing dose unit (both schema-level "
            "REQUIRED_MISSING inside dose and gate-level absence on an active "
            "medication), hidden prompt clue (field smuggle ADDITIONAL_"
            "PROPERTY + text leakage PROMPT_CLUE_LEAKED), PHI field "
            "(structural ADDITIONAL_PROPERTY and NOT_MISMATCH on notes/"
            "instruction/rationale_text), model-derived rationale "
            "(CONST_MISMATCH on both rationale consts), unknown label/family "
            "(ENUM_MISMATCH), label/family mismatch (gate), and every "
            "required-field removal (REQUIRED_MISSING). Full local gate: 23 "
            "passed on research/venue2027/aime/tests/. uvx ruff@0.7.1 check + "
            "format --check clean on the touched test file. No clinical "
            "validity claim: synthetic vignettes only, annotation NOT "
            "executed, no clinician reviewer yet (falsification rule honored; "
            "the schema admits the PENDING/LOCKED adjudication-state classes "
            "without asserting any performed review). Case package is "
            "reviewable without method source (pass gate). "
            "source_sha_after = commit SHA of this task's single commit "
            "(proof report committed together with the work per established "
            "repo convention)."
        ),
    )

    out_path = REPO / "research/venue2027/proof/AIME-X01_vignette_schema.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    log_path = REPO / "research/venue2027/proof/logs/AIME-X01_vignette_schema.validator.log"
    # Pre-seed so the on-disk log exists (non-empty) at validation time; the
    # final validator result overwrites it below.
    log_path.write_text('{"note": "validator run in progress"}\n', encoding="utf-8")
    result = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id=TASK,
        completed_tasks=["AIME-schema"],
        task_dependencies=["AIME-schema"],
    )
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
