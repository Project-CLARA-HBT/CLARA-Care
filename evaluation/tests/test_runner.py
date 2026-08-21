from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from evaluation.clara_eval.config import load_suite_config
from evaluation.clara_eval.live import LiveEvaluationError, maybe_execute_live
from evaluation.clara_eval.run import _ablation_rows, build_report, main
from evaluation.clara_eval.tracks import REQUIRED_TRACK_IDS

ROOT = Path(__file__).resolve().parents[2]


class EvalRunnerTests(unittest.TestCase):
    def test_opt_in_live_execution_records_only_sanitized_observation_metadata(self) -> None:
        manifest = {
            "schema_version": "clara-eval-vn.live-execution-manifest.v1",
            "approval": {
                "approved_for_live_execution": True,
                "reference": "approved-eval-change-42",
            },
            "contains_phi": False,
            "contains_secrets": False,
            "records": [
                {
                    "case_id": "eval-vcu-001",
                    "track_id": "vietnamese_clinical_understanding",
                    "endpoint": "ml",
                    "path": "/v1/eval-safe-route",
                    "request": {"scenario": "deidentified-emergency-contract"},
                    "critical_error_type": "missed_emergency",
                    "scorer": {
                        "type": "json_path_equals",
                        "metric_id": "emergency_recall",
                        "json_path": "policy.emergency",
                        "expected": True,
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            manifest_path = temporary_root / "approved-live.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            output = temporary_root / "nightly"
            response = MagicMock()
            response.status = 200
            response.read.return_value = b'{"policy":{"emergency":true}}'
            response.__enter__.return_value = response
            with (
                patch.dict(
                    "os.environ",
                    {
                        "CLARA_EVAL_LIVE_EXECUTION_ENABLED": "true",
                        "CLARA_EVAL_LIVE_MANIFEST": str(manifest_path),
                        "CLARA_EVAL_ML_BASE_URL": "https://approved-ml.example",
                    },
                    clear=False,
                ),
                patch("evaluation.clara_eval.live.request.urlopen", return_value=response),
            ):
                report, _ = build_report(
                    config_path=ROOT / "evaluation/configs/nightly.yaml",
                    output=output,
                    repository_root=ROOT,
                )

            metric = next(
                row for row in report["metrics"] if row["metric_id"] == "emergency_recall"
            )
            self.assertEqual(metric["state"], "measured")
            self.assertEqual(metric["value"], 1.0)
            self.assertEqual(metric["confidence_interval"]["method"], "wilson")
            live_artifact = json.loads((output / "live-execution.json").read_text(encoding="utf-8"))
            serialized = json.dumps(live_artifact, ensure_ascii=False)
            self.assertNotIn("deidentified-emergency-contract", serialized)
            self.assertNotIn("eval-vcu-001", serialized)
            self.assertNotIn("policy", serialized)
            trace = live_artifact["traces"][0]
            self.assertEqual(trace["outcome"], "pass")
            self.assertTrue(trace["case_ref"])

            intervals = json.loads(
                (output / "confidence-intervals.json").read_text(encoding="utf-8")
            )
            measured_ids = {row["metric_id"] for row in intervals["measured"]}
            unavailable_ids = {row["metric_id"] for row in intervals["not_measured"]}
            self.assertIn("emergency_recall", measured_ids)
            self.assertNotIn("emergency_recall", unavailable_ids)

            with (output / "critical-errors.csv").open(encoding="utf-8") as handle:
                critical_rows = list(csv.DictReader(handle))
            observed_critical = [
                row for row in critical_rows if row["critical_error_type"] == "missed_emergency"
            ]
            self.assertEqual(len(observed_critical), 1)
            self.assertEqual(observed_critical[0]["state"], "measured")
            self.assertEqual(observed_critical[0]["count"], "0")

    def test_live_manifest_with_sensitive_request_key_is_rejected_before_http(self) -> None:
        manifest = {
            "schema_version": "clara-eval-vn.live-execution-manifest.v1",
            "approval": {"approved_for_live_execution": True, "reference": "approved"},
            "contains_phi": False,
            "contains_secrets": False,
            "records": [
                {
                    "case_id": "eval-vcu-002",
                    "track_id": "vietnamese_clinical_understanding",
                    "endpoint": "ml",
                    "path": "/v1/eval-safe-route",
                    "request": {"email": "must-not-be-accepted"},
                    "scorer": {
                        "type": "json_path_equals",
                        "metric_id": "emergency_recall",
                        "json_path": "policy.emergency",
                        "expected": True,
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest_path = Path(temporary_directory) / "approved-live.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with (
                patch.dict(
                    "os.environ",
                    {
                        "CLARA_EVAL_LIVE_EXECUTION_ENABLED": "true",
                        "CLARA_EVAL_LIVE_MANIFEST": str(manifest_path),
                        "CLARA_EVAL_ML_BASE_URL": "https://approved-ml.example",
                    },
                    clear=False,
                ),
                self.assertRaisesRegex(ValueError, "live_manifest_request_has_sensitive_key"),
            ):
                build_report(
                    config_path=ROOT / "evaluation/configs/nightly.yaml",
                    output=Path(temporary_directory) / "nightly",
                    repository_root=ROOT,
                )

    def test_observed_ablation_replaces_its_not_measured_placeholder(self) -> None:
        rows = _ablation_rows(
            load_suite_config(ROOT / "evaluation/configs/nightly.yaml"),
            [
                {
                    "ablation_variant": "C2",
                    "metric_id": "red_flag_recall",
                    "passed": True,
                }
            ],
        )
        c2_rows = [
            row for row in rows if row["variant"] == "C2" and row["metric_id"] == "red_flag_recall"
        ]
        self.assertEqual(len(c2_rows), 1)
        self.assertEqual(c2_rows[0]["state"], "measured")
        self.assertEqual(c2_rows[0]["value"], "1.000000")

    def test_release_live_manifest_binds_dataset_snapshot_and_release_sha(
        self,
    ) -> None:
        """Locked runs reject a manifest that is not bound to this release context."""
        release_ref = "a" * 40
        manifest = {
            "schema_version": "clara-eval-vn.live-execution-manifest.v1",
            "approval": {
                "approved_for_live_execution": True,
                "reference": "approved",
            },
            "contains_phi": False,
            "contains_secrets": False,
            "retrieval_snapshot": {
                "reference": "snapshot-2026-07",
                "sha256": "b" * 64,
            },
            "release_binding": {
                "locked_dataset_ref": "approved-dataset-revision-7",
                "release_ref": release_ref,
            },
            "records": [
                {
                    "case_id": "eval-vcu-003",
                    "track_id": "vietnamese_clinical_understanding",
                    "endpoint": "ml",
                    "path": "/v1/eval-safe-route",
                    "request": {"scenario": "deidentified"},
                    "scorer": {
                        "type": "json_path_equals",
                        "metric_id": "emergency_recall",
                        "json_path": "policy.emergency",
                        "expected": True,
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest_path = Path(temporary_directory) / "approved-release.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            response = MagicMock()
            response.status = 200
            response.read.return_value = b'{"policy":{"emergency":true}}'
            response.__enter__.return_value = response
            environment = {
                "CLARA_EVAL_LIVE_EXECUTION_ENABLED": "true",
                "CLARA_EVAL_LIVE_MANIFEST": str(manifest_path),
                "CLARA_EVAL_ML_BASE_URL": "https://approved-ml.example",
                "CLARA_EVAL_LOCKED_DATASET_REF": "approved-dataset-revision-7",
                "CLARA_EVAL_RELEASE_REF": release_ref,
            }
            with (
                patch.dict("os.environ", environment, clear=False),
                patch(
                    "evaluation.clara_eval.live.request.urlopen",
                    return_value=response,
                ),
            ):
                metadata, traces = maybe_execute_live(
                    load_suite_config(ROOT / "evaluation/configs/release.yaml"),
                    repository_root=ROOT,
                )
            self.assertEqual(metadata["release_binding"]["state"], "validated")
            self.assertEqual(metadata["release_binding"]["release_ref"], release_ref)
            self.assertNotIn("approved-dataset-revision-7", json.dumps(metadata))
            self.assertEqual(len(traces), 1)

            environment["CLARA_EVAL_RELEASE_REF"] = "c" * 40
            with (
                patch.dict("os.environ", environment, clear=False),
                self.assertRaisesRegex(LiveEvaluationError, "live_release_ref_mismatch"),
            ):
                maybe_execute_live(
                    load_suite_config(ROOT / "evaluation/configs/release.yaml"),
                    repository_root=ROOT,
                )

    def test_smoke_emits_evidence_without_claiming_clinical_quality(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "smoke"
            report, target = build_report(
                config_path=ROOT / "evaluation/configs/smoke.yaml",
                output=output,
                repository_root=ROOT,
            )

            self.assertEqual(target, output)
            self.assertEqual(report["integrity"]["state"], "measured")
            self.assertEqual(report["integrity"]["value"], 1.0)
            self.assertEqual({track["track_id"] for track in report["tracks"]}, REQUIRED_TRACK_IDS)
            self.assertTrue(all(track["state"] == "not_measured" for track in report["tracks"]))
            for filename in (
                "metrics.json",
                "dataset-manifest.json",
                "model-manifest.json",
                "retrieval-snapshot.json",
                "confidence-intervals.json",
                "critical-errors.csv",
                "ablations.csv",
                "summary.md",
                "index.html",
                "examples/README.json",
            ):
                self.assertTrue((output / filename).is_file(), filename)

            metrics = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
            product_metrics = [
                row for row in metrics["metrics"] if row["track_id"] != "evaluation_governance"
            ]
            self.assertTrue(product_metrics)
            self.assertTrue(all(row["state"] == "not_measured" for row in product_metrics))
            self.assertTrue(all(row["measurement_command"] for row in product_metrics))
            model_manifest = json.loads(
                (output / "model-manifest.json").read_text(encoding="utf-8")
            )
            contracts = model_manifest["task_contract_snapshot"]
            self.assertEqual(contracts["state"], "configured_not_executed")
            self.assertEqual(contracts["schema_version"], "clara.task-contracts.v2")
            self.assertTrue(contracts["sha256"])
            self.assertTrue(contracts["contracts"])
            self.assertTrue(
                all(row["model_profile"] in {"pro", "flash"} for row in contracts["contracts"])
            )
            self.assertEqual(
                model_manifest["model_registry"]["state"],
                "configured_not_executed",
            )

    def test_judge_report_has_the_required_machine_and_human_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "judge-report"
            code = main(
                [
                    "--config",
                    str(ROOT / "evaluation/configs/judge_demo.yaml"),
                    "--output",
                    str(output),
                    "--repository-root",
                    str(ROOT),
                ]
            )
            self.assertEqual(code, 0)
            self.assertTrue((output / "index.html").is_file())
            self.assertTrue((output / "summary.md").is_file())
            self.assertTrue((output / "examples").is_dir())
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            headlines = summary["judge_headlines"]
            self.assertEqual(len(headlines), 6)
            self.assertEqual(
                [row["metric_id"] for row in headlines],
                [
                    "emergency_recall",
                    "medication_normalization_top1",
                    "critical_ddi_recall",
                    "unsupported_claim_rate",
                    "clinician_edit_time_reduction",
                    "large_llm_cost_reduction",
                ],
            )
            self.assertTrue(all(row["state"] == "not_measured" for row in headlines))
            self.assertTrue(all(row["value"] is None for row in headlines))
            index = (output / "index.html").read_text(encoding="utf-8")
            self.assertIn("Sáu chỉ số chính cho BGK", index)
            self.assertEqual(index.count('class="headline"'), 6)
            with (output / "critical-errors.csv").open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertTrue(rows)
            self.assertTrue(all(row["state"] == "not_measured" for row in rows))
            self.assertTrue(all(not row["count"] for row in rows))

    def test_release_locked_config_fails_closed_after_writing_diagnostic_artifacts(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "release"
            code = main(
                [
                    "--config",
                    str(ROOT / "evaluation/configs/release.yaml"),
                    "--output",
                    str(output),
                    "--repository-root",
                    str(ROOT),
                ]
            )
            self.assertEqual(code, 2)
            self.assertTrue((output / "metrics.json").is_file())
            self.assertIn(
                "not measured",
                (output / "summary.md").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
