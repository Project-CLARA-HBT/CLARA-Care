from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evaluation.clara_eval.config import SuiteConfigError, load_suite_config
from evaluation.clara_eval.datasets.manifest import (
    ManifestValidationError,
    load_dataset_manifest,
)
from evaluation.clara_eval.tracks import REQUIRED_TRACK_IDS

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "evaluation/clara_eval/datasets/manifest.json"


class DatasetManifestTests(unittest.TestCase):
    def test_checked_in_manifest_covers_each_required_track_with_honest_metadata(
        self,
    ) -> None:
        manifest = load_dataset_manifest(MANIFEST, repository_root=ROOT)

        self.assertEqual({entry.track_id for entry in manifest.datasets}, REQUIRED_TRACK_IDS)
        self.assertTrue(manifest.data_policy["synthetic_fixtures_only"])
        for entry in manifest.datasets:
            self.assertFalse(entry.contains_phi)
            self.assertFalse(entry.contains_secrets)
            self.assertFalse(entry.clinically_representative)
            self.assertEqual(entry.provenance, "synthetic_safety_fixture")
            self.assertTrue(entry.measurements)
            for measurement in entry.measurements:
                self.assertEqual(measurement.state, "not_measured")
                self.assertTrue(measurement.reason)
                self.assertTrue(measurement.command)

    def test_checksum_tampering_fails_closed(self) -> None:
        raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
        raw["datasets"][0]["sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as temporary_directory:
            candidate = Path(temporary_directory) / "manifest.json"
            candidate.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(ManifestValidationError, "dataset_checksum_mismatch"):
                load_dataset_manifest(candidate, repository_root=ROOT)

    def test_metric_without_measurement_reason_and_command_is_rejected(self) -> None:
        raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
        raw["datasets"][0]["measurements"][0].pop("reason")
        with tempfile.TemporaryDirectory() as temporary_directory:
            candidate = Path(temporary_directory) / "manifest.json"
            candidate.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(ManifestValidationError, "dataset_entry_invalid"):
                load_dataset_manifest(candidate, repository_root=ROOT)


class SuiteConfigTests(unittest.TestCase):
    def test_checked_in_suite_configs_cover_all_tracks_without_synthetic_metrics(
        self,
    ) -> None:
        for suite in ("smoke", "nightly", "release", "judge_demo"):
            loaded = load_suite_config(ROOT / f"evaluation/configs/{suite}.yaml")
            self.assertEqual(loaded.suite, suite)
            self.assertEqual(set(loaded.enabled_tracks), REQUIRED_TRACK_IDS)
            self.assertFalse(loaded.allow_synthetic_metrics)
            self.assertEqual(
                loaded.dataset_manifest, "evaluation/clara_eval/datasets/manifest.json"
            )

    def test_release_config_fails_without_locked_mode(self) -> None:
        source = ROOT / "evaluation/configs/release.yaml"
        raw = source.read_text(encoding="utf-8").replace(
            '"release_locked": true', '"release_locked": false'
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "release.yaml"
            path.write_text(raw, encoding="utf-8")
            with self.assertRaisesRegex(SuiteConfigError, "release_must_be_locked"):
                load_suite_config(path)


if __name__ == "__main__":
    unittest.main()
