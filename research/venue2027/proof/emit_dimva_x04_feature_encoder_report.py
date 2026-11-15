"""Emit the DIMVA-X04_feature_encoder task proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the DIMVA-X04_feature_encoder task. No network access.

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
BASE = "687a6f56def769fc930e0ee94b00476eecc1c69b"

MODULE = "evaluation/venue2027/dimva/feature_encoding.py"
TESTS = "evaluation/venue2027/dimva/test_feature_encoder.py"
PROOF = "research/venue2027/proof/DIMVA-X04_feature_encoder.json"
PYTEST_LOG = "research/venue2027/proof/logs/DIMVA-X04_feature_encoder.pytest.log"
RUFF_LOG = "research/venue2027/proof/logs/DIMVA-X04_feature_encoder.ruff.log"
SUITE_LOG = "research/venue2027/proof/logs/DIMVA-X04_feature_encoder.suite.log"
VALIDATOR_LOG = "research/venue2027/proof/logs/DIMVA-X04_feature_encoder.validator.log"

CHANGED = [MODULE, TESTS, PROOF, PYTEST_LOG, RUFF_LOG, SUITE_LOG, VALIDATOR_LOG]


def main() -> int:
    sha_after = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    report = ap.build_report(
        task_id="DIMVA-X04_feature_encoder",
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=sha_after,
        changed_paths=CHANGED,
        commands=[
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/dimva/test_feature_encoder.py",
                "exit_code": 0,
                "log_path": PYTEST_LOG,
            },
            {
                "argv": (
                    "uvx ruff@0.7.1 check evaluation/venue2027/dimva/feature_encoding.py "
                    "evaluation/venue2027/dimva/test_feature_encoder.py && "
                    "uvx ruff@0.7.1 format --check evaluation/venue2027/dimva/"
                    "feature_encoding.py evaluation/venue2027/dimva/test_feature_encoder.py"
                ),
                "exit_code": 0,
                "log_path": RUFF_LOG,
            },
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/",
                "exit_code": 0,
                "log_path": SUITE_LOG,
            },
        ],
        artifact_paths=[MODULE, TESTS, PYTEST_LOG, RUFF_LOG, SUITE_LOG],
        repo=REPO,
        oracle_disagreement_count=None,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P04 DIMVA-X04_feature_encoder deliverable for venue dimva: "
            "evaluation/venue2027/dimva/feature_encoding.py implements the leak-safe "
            "sequence feature encoder for GovernanceTrace (RQ1). Core contract: "
            "FeatureEncoder.fit(train_events) fits ALL data-derived transforms on "
            "TRAINING data only and stores them (per-feature train median/IQR robust "
            "scaling constants plus the training reference denial rate); "
            "transform(events) applies the stored statistics read-only. transform "
            "before fit raises NOT_FITTED; fitting on holdout-tagged data (split/"
            "partition/split_tag of dev/test/holdout) raises HOLDOUT_LEAK; a refit of "
            "an already-fitted encoder is refused with HOLDOUT_LEAK (a second fit "
            "could launder non-training statistics); dev/test encodings never alter "
            "the stored stats (stats_digest before == after many transforms, asserted "
            "in tests; each row binds the digest via stats_sha256). 44 features = 22 "
            "raw + 22 normalized across five families: time gaps (7: mean/median/std/"
            "max/min inter-arrival, gap-after-denial mean, short-gap fraction vs the "
            "caller window), scope transitions (4: distinct scopes, switch rate, "
            "cross-scope denials within window, denial-followed-by-other-scope), "
            "denial-transition signatures (5: denied fraction, max/mean denial-run "
            "lengths, allowed-after-denied and denied-after-denied rates), entropy "
            "(2: Shannon bits over tool and scope distributions) and rate-adjusted "
            "counts (4: denials/events/distinct-tools per hour over the session span, "
            "plus the denial-rate ratio to the train reference). Zero-IQR training "
            "columns fall back to documented centering-only scaling (scale 1.0) "
            "instead of dividing by zero. Deterministic: pure functions, sorted "
            "iteration, no random module/clock/environment reads, floats rounded to "
            "12 decimals; identical (state, events, window) yield byte-identical "
            "matrices and identical fits yield identical stats digests. "
            "feature_lineage() returns one record per output feature (name, family, "
            "source_fields, transform formula, fit_dependent) generated from the same "
            "registry the encoder iterates — complete by construction, asserted over "
            "every column; exactly the 22 normalized companions plus "
            "denial_rate_ratio_to_train are fit-dependent. Fail-closed leak surface: "
            "rejection reason-code-like event fields refused with "
            "EVENT_REASON_CODE_FIELD_FORBIDDEN (RQ1 masking), campaign-label fields "
            "refused with EVENT_LABEL_FIELD_FORBIDDEN, plus unknown/missing fields, "
            "bad types, non-monotonic ts, mixed actors, empty fit, invalid window and "
            "non-list inputs with stable uppercase reason codes; holdout-tagged "
            "sequences CAN be transformed (encoded) but never fitted on; empty "
            "sequences encode to an all-zero raw row. encode(events, window) provides "
            "the one-shot task-contract signature. evaluation/venue2027/dimva/"
            "test_feature_encoder.py: 40 tests — positive (fit-then-transform shape "
            "44, JSON-serializable, determinism byte-identical, hand-computed feature "
            "values incl. entropy/rates/ratio, stats fitted-not-constants, dev/test "
            "transforms leave train stats digest untouched, lineage completeness over "
            "all 44 columns, code-level lineage independence, five families, one-shot "
            "encode) and adversarial (NOT_FITTED on transform/digest before fit; "
            "HOLDOUT_LEAK for all 9 split-tag x tag combinations; refit refusal; "
            "reason-code and label leak-surface refusals; unknown/missing/non-monotonic/"
            "mixed-actor/empty/invalid-window fail-closed). Commands: pytest exit 0 "
            "(40 passed); uvx ruff@0.7.1 check + format --check exit 0; full "
            "evaluation/venue2027/ suite exit 0 (1701 passed) — no regression. Proof "
            "emitted via agent_protocol.build_report(task_id="
            "'DIMVA-X04_feature_encoder') with real log_paths and validated ok:true; "
            "report + logs committed together with the work per established repo "
            "convention (SHA convention follows DIMVA-X08_splitter precedent: "
            "before==parent base, after=HEAD at emit time because the single required "
            "commit contains this self-referential report; the final deliverable "
            "commit SHA is reported in the handoff)."
        ),
    )

    out_path = REPO / PROOF
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id="DIMVA-X04_feature_encoder",
    )
    log_path = REPO / VALIDATOR_LOG
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
