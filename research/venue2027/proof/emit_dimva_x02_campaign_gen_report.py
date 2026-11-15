"""Emit the DIMVA-X02_campaign_gen task proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the DIMVA-X02_campaign_gen task. No network access.

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
BASE = "e373f6e46465917ad4fbd7d6656e77e51c4805db"

CHANGED = [
    "evaluation/venue2027/dimva/campaign_generator.py",
    "evaluation/venue2027/dimva/test_campaign_generator.py",
    "research/venue2027/proof/DIMVA-X02_campaign_gen.json",
    "research/venue2027/proof/emit_dimva_x02_campaign_gen_report.py",
    "research/venue2027/proof/logs/DIMVA-X02_campaign_gen.pytest.log",
    "research/venue2027/proof/logs/DIMVA-X02_campaign_gen.ruff.log",
    "research/venue2027/proof/logs/DIMVA-X02_campaign_gen.validator.log",
]


def main() -> int:
    sha_after = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    report = ap.build_report(
        task_id="DIMVA-X02_campaign_gen",
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=sha_after,
        changed_paths=CHANGED,
        commands=[
            {
                "argv": (
                    "python3 -m pytest -q "
                    "evaluation/venue2027/dimva/test_campaign_generator.py"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/"
                "DIMVA-X02_campaign_gen.pytest.log",
            },
            {
                "argv": (
                    "uvx ruff@0.7.1 check "
                    "evaluation/venue2027/dimva/campaign_generator.py "
                    "evaluation/venue2027/dimva/test_campaign_generator.py"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/"
                "DIMVA-X02_campaign_gen.ruff.log",
            },
        ],
        artifact_paths=[
            "evaluation/venue2027/dimva/campaign_generator.py",
            "evaluation/venue2027/dimva/test_campaign_generator.py",
            "research/venue2027/proof/logs/DIMVA-X02_campaign_gen.pytest.log",
            "research/venue2027/proof/logs/DIMVA-X02_campaign_gen.ruff.log",
        ],
        repo=REPO,
        oracle_disagreement_count=None,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P02 DIMVA-X02_campaign_gen deliverable for venue dimva: "
            "evaluation/venue2027/dimva/campaign_generator.py implements the exact "
            "generate(seed, family, tenant) -> Campaign contract, producing "
            "deterministic PHI-free multi-stage campaigns over the five registered "
            "families purpose_probe, cross_principal_retry, expired_token_replay, "
            "cadence_shift and harmless_control (FamilySpec registry maps each family "
            "to its campaign_label ATTACK/BENIGN and violated_invariant, with NONE for "
            "the control). Every event is exactly the seven-field minimal surface of "
            "research/venue2027/dimva/protocols/event.schema.json (actor/scope opaque "
            "SHA-256 hex digests, coarse snake_case tool token, boolean allowed, closed "
            "purpose enum, 60 s bucket ts, opaque camp-<16 hex> campaign_id), asserted "
            "in tests by validating every generated event against the frozen schema "
            "through the shared stdlib validator schema_validator.validate_instance. "
            "LABELS EXIST ONLY AT CAMPAIGN LEVEL: campaign_label and violated_invariant "
            "live on the Campaign object; the event builder structurally refuses any "
            "label-like field (label, campaign_label, violated_invariant, "
            "attacker_label, is_attack) with EVENT_LABEL_FIELD_FORBIDDEN and the "
            "seven-field gate fails closed with EVENT_FIELD_MISMATCH, so no event ever "
            "carries ground truth and campaign ids/tenants/families/invariant strings "
            "never appear inside event payloads (template-leak-safe across splits). "
            "Determinism: all entropy derives from SHA-256 digests over stable "
            "coordinate strings (version, seed, tenant, family, stage index) — no "
            "random module, no clock, no environment reads; same (seed, family, tenant) "
            "yields byte-identical to_dict output. Fail-closed error surface: stable "
            "reason codes INVALID_SEED, INVALID_TENANT, UNKNOWN_FAMILY, "
            "PHI_FIELD_PRESENT (tenant and serialized-output PHI scan over the shared "
            "kernel markers plus patient/diagnosis/ssn/symptom/prescription), "
            "EVENT_LABEL_FIELD_FORBIDDEN, EVENT_FIELD_MISMATCH; no clear-text "
            "principals, no reason codes on the event surface, no live provider. "
            "test_campaign_generator.py (43 tests): positive vectors cover per-family "
            "generation for all five families, determinism/idempotence across call "
            "order, seed/tenant sensitivity, required top-level campaign fields, "
            "campaign-level-only labeling, schema-shape conformance of every event, "
            "opaque leak-free campaign_id, per-family stage semantics (single principal "
            "rotating purposes; >=3 principals denied retries; replay resuming beyond "
            "TOKEN_EXPIRY_HORIZON_BUCKETS=10; cadence gaps all > "
            "PACE_WINDOW_BUCKETS=5; control with steady pacing, one transient denial "
            "and single actor) and JSON serializability; adversarial vectors prove "
            "per-event label fields are refused (all five label-like names), off-schema "
            "fields refused, tampered events fail the schema-shape gate, unknown family "
            "refused with UNKNOWN_FAMILY, invalid seeds/tenants refused, PHI-like "
            "tenant refused, all generated campaigns PHI-free and reason-code-free on "
            "the event surface. Commands: python3 -m pytest -q "
            "evaluation/venue2027/dimva/test_campaign_generator.py exit 0 (43 passed); "
            "uvx ruff@0.7.1 check on both touched files exit 0 (All checks passed). "
            "Proof emitted via agent_protocol.build_report(task_id='DIMVA-X02_campaign_gen') "
            "with real log_paths and validated ok:true; report + logs committed together "
            "with the work per established repo convention."
        ),
    )

    out_path = REPO / "research/venue2027/proof/DIMVA-X02_campaign_gen.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id="DIMVA-X02_campaign_gen",
    )
    log_path = REPO / "research/venue2027/proof/logs/DIMVA-X02_campaign_gen.validator.log"
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
