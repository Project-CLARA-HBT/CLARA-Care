"""Emit the DIMVA-X03_benign_gen task proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the DIMVA-X03_benign_gen task. No network access.

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
BASE = "6fe5fe193a5a55f456f163a853c1b2c41c0c869f"

CHANGED = [
    "evaluation/venue2027/dimva/benign_fault_generator.py",
    "evaluation/venue2027/dimva/test_benign_fault_generator.py",
    "research/venue2027/proof/DIMVA-X03_benign_gen.json",
    "research/venue2027/proof/emit_dimva_x03_benign_gen_report.py",
    "research/venue2027/proof/logs/DIMVA-X03_benign_gen.pytest.log",
    "research/venue2027/proof/logs/DIMVA-X03_benign_gen.ruff.log",
    "research/venue2027/proof/logs/DIMVA-X03_benign_gen.validator.log",
]


def main() -> int:
    sha_after = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    report = ap.build_report(
        task_id="DIMVA-X03_benign_gen",
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=sha_after,
        changed_paths=CHANGED,
        commands=[
            {
                "argv": (
                    "python3 -m pytest -q "
                    "evaluation/venue2027/dimva/test_benign_fault_generator.py"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/"
                "DIMVA-X03_benign_gen.pytest.log",
            },
            {
                "argv": (
                    "uvx ruff@0.7.1 check "
                    "evaluation/venue2027/dimva/benign_fault_generator.py "
                    "evaluation/venue2027/dimva/test_benign_fault_generator.py"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/"
                "DIMVA-X03_benign_gen.ruff.log",
            },
        ],
        artifact_paths=[
            "evaluation/venue2027/dimva/benign_fault_generator.py",
            "evaluation/venue2027/dimva/test_benign_fault_generator.py",
            "research/venue2027/proof/logs/DIMVA-X03_benign_gen.pytest.log",
            "research/venue2027/proof/logs/DIMVA-X03_benign_gen.ruff.log",
        ],
        repo=REPO,
        oracle_disagreement_count=None,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P02 DIMVA-X03_benign_gen deliverable for venue dimva: "
            "evaluation/venue2027/dimva/benign_fault_generator.py implements the "
            "exact generate_benign(seed, workload) -> Campaign contract, producing "
            "deterministic PHI-free BENIGN fault sessions over the five registered "
            "fault types rate_limit_retry, network_retry, ux_confusion_retry, "
            "consent_edit and delayed_timestamps — realistic nonmalicious retries "
            "that superficially resemble probing (rate-limit bursts resemble "
            "burst_probe pacing, network backoffs resemble replay probing, "
            "mis-scoped UX confusion purposes resemble purpose_probe, consent/epoch "
            "edits resemble scope rotation, long legitimate stalls resemble "
            "low-and-slow horizons) while never violating an authorization "
            "invariant (campaign_label=BENIGN, violated_invariant=NONE, campaign "
            "level only). VOLUME PARITY (critical property): generate_benign accepts "
            "a target event-volume/cadence profile WorkloadProfile(tenant, "
            "target_events, pace_bucket_lo, pace_bucket_hi); the emitted campaign "
            "contains EXACTLY target_events events (one baseline plus the fault "
            "repertoire filling the remaining budget via a deterministic "
            "seed-rotated allocation) and every non-delayed inter-arrival gap lies "
            "inside the requested cadence profile; over-production is structurally "
            "refused fail closed with VOLUME_BUDGET_EXCEEDED whenever the budget is "
            "below the minimum realizable genuine-repertoire campaign "
            "(MIN_TARGET_EVENTS = 1 baseline + 2 rate-limit retries + 2 network "
            "retries + 2 UX confusion retries + 1 consent edit + 1 delayed stall, so "
            "the benign arm always contains real repeated attempts and is never "
            "trivially easy), proving volume parity is mechanically enforced rather "
            "than conventional. Every event is exactly the seven-field minimal "
            "surface of research/venue2027/dimva/protocols/event.schema.json "
            "(actor/scope opaque SHA-256 hex digests, coarse snake_case tool token, "
            "boolean allowed, closed purpose enum, 60 s bucket ts, opaque camp-<16 "
            "hex> campaign_id), asserted in tests by validating every generated "
            "event against the frozen schema through the shared stdlib validator "
            "schema_validator.validate_instance. LABELS EXIST ONLY AT CAMPAIGN "
            "LEVEL: events are built through the shared campaign_generator._make_event "
            "builder, which structurally refuses any label-like field with "
            "EVENT_LABEL_FIELD_FORBIDDEN, and the seven-field gate fails closed with "
            "EVENT_FIELD_MISMATCH, so no event ever carries ground truth and "
            "tenant/family/label/invariant strings never appear inside event "
            "payloads (template-leak-safe across splits). Determinism: all entropy "
            "derives from SHA-256 digests over stable coordinate strings (generator "
            "version, seed, tenant, target volume, fault index) — no random module, "
            "no clock, no environment reads; same (seed, workload) yields "
            "byte-identical to_dict output. Fail-closed error surface: stable reason "
            "codes INVALID_SEED, INVALID_TENANT, INVALID_WORKLOAD, "
            "VOLUME_BUDGET_EXCEEDED, CADENCE_PROFILE_VIOLATED, PHI_FIELD_PRESENT, "
            "EVENT_LABEL_FIELD_FORBIDDEN, EVENT_FIELD_MISMATCH; a fail-closed "
            "post-build volume/cadence gate re-verifies exact budget conformance and "
            "cadence-profile membership (delayed-timestamp stalls are the only "
            "admissible class beyond the profile, disjoint from profile bounds by "
            "construction: MAX_PACE_GAP_BUCKETS=12 < DELAYED_GAP_MIN_BUCKETS=30); no "
            "clear-text principals, no reason codes on the event surface, no live "
            "provider. test_benign_fault_generator.py (56 tests): positive vectors "
            "cover BENIGN labeling with invariant NONE across seeds, determinism/"
            "idempotence across call order, seed sensitivity, every benign fault "
            "type present in one campaign (denials confined to retry segments, "
            "single actor, multi-purpose/multi-scope churn, delayed stalls beyond "
            "the profile), EXACT volume parity for budgets spanning "
            "MIN_TARGET_EVENTS..MAX_TARGET_EVENTS and volume-matching to every "
            "attack family's stage range in campaign_generator.FAMILY_SPECS, "
            "cadence-profile conformance across seeds and pace bounds, frozen-schema "
            "conformance of every event, opaque leak-free campaign_id and JSON "
            "serializability of both WorkloadProfile and Campaign; adversarial "
            "vectors prove a benign campaign exceeding the requested volume budget "
            "is refused (all budgets below MIN_TARGET_EVENTS raise "
            "VOLUME_BUDGET_EXCEEDED without silent trimming, so volume parity is "
            "enforced), per-event label fields are refused (all five label-like "
            "names), off-schema fields refused, non-WorkloadProfile and malformed "
            "targets/cadence bounds refused with INVALID_WORKLOAD, invalid seeds/"
            "tenants refused, PHI-like tenant refused, tampered campaigns fail the "
            "volume and cadence gates, all generated campaigns PHI-free and "
            "reason-code-free on the event surface. Commands: python3 -m pytest -q "
            "evaluation/venue2027/dimva/test_benign_fault_generator.py exit 0 (56 "
            "passed); uvx ruff@0.7.1 check on both touched files exit 0 (All checks "
            "passed). Proof emitted via agent_protocol.build_report("
            "task_id='DIMVA-X03_benign_gen') with real log_paths and validated "
            "ok:true; report + logs committed together with the work per "
            "established repo convention."
        ),
    )

    out_path = REPO / "research/venue2027/proof/DIMVA-X03_benign_gen.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id="DIMVA-X03_benign_gen",
    )
    log_path = REPO / "research/venue2027/proof/logs/DIMVA-X03_benign_gen.validator.log"
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
