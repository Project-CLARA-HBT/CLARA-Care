from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from evaluation.clara_eval.run import build_report, main
from evaluation.clara_eval.tracks import REQUIRED_TRACK_IDS

ROOT = Path(__file__).resolve().parents[2]


class EvalRunnerTests(unittest.TestCase):
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
            self.assertEqual(
                {track["track_id"] for track in report["tracks"]}, REQUIRED_TRACK_IDS
            )
            self.assertTrue(
                all(track["state"] == "not_measured" for track in report["tracks"])
            )
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
                row
                for row in metrics["metrics"]
                if row["track_id"] != "evaluation_governance"
            ]
            self.assertTrue(product_metrics)
            self.assertTrue(
                all(row["state"] == "not_measured" for row in product_metrics)
            )
            self.assertTrue(all(row["measurement_command"] for row in product_metrics))

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
