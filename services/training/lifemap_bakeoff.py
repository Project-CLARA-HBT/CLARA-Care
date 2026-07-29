"""Offline-only classical LifeMap champion/challenger trainer.

Input is a governed JSON snapshot exported outside OLTP. This program never
connects to CLARA services and never promotes a model. It emits candidate
artifacts and predictions for the governed evaluator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from statistics import median
from typing import Any

PROHIBITED_TARGETS = (
    "disease",
    "diagnosis",
    "deterioration",
    "hospital",
    "mortality",
    "treatment",
    "medication",
    "drug_effect",
    "emergency",
    "triage",
)


def _read_snapshot(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    snapshot = json.loads(raw)
    if not isinstance(snapshot, dict):
        raise TypeError("snapshot_must_be_object")
    target = str(snapshot.get("target_key", "")).lower().replace("-", "_")
    if any(fragment in target for fragment in PROHIBITED_TARGETS):
        raise ValueError("research_only_target_forbidden")
    if not snapshot.get("target_approval_id"):
        raise ValueError("target_approval_required")
    if snapshot.get("split_policy") not in {
        "person_household_site_source_device_time",
        "person_household_source_device_time",
    }:
        raise ValueError("leakage_safe_split_required")
    if snapshot.get("leakage_audit") != "passed":
        raise ValueError("leakage_audit_required")
    snapshot["_input_sha256"] = hashlib.sha256(raw).hexdigest()
    return snapshot


def _fit_candidates(snapshot: dict[str, Any], output: Path) -> dict[str, Any]:
    import joblib
    import numpy as np
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    task_kind = snapshot.get("task_kind")
    if task_kind != "binary":
        raise ValueError("initial_offline_trainer_supports_binary_only")
    train = snapshot.get("train") or {}
    evaluation = snapshot.get("evaluation") or {}
    x_train = np.asarray(train.get("features"), dtype=float)
    y_train = np.asarray(train.get("labels"), dtype=int)
    x_eval = np.asarray(evaluation.get("features"), dtype=float)
    if (
        x_train.ndim != 2
        or x_eval.ndim != 2
        or len(x_train) != len(y_train)
        or len(x_train) < 30
        or x_train.shape[1] != x_eval.shape[1]
    ):
        raise ValueError("feature_or_sample_shape_invalid")
    if set(np.unique(y_train)) - {0, 1}:
        raise ValueError("binary_labels_invalid")

    prevalence = float(median(y_train.tolist()))
    candidates: list[tuple[str, str, Any, list[float]]] = [
        (
            "deterministic-robust-v1",
            "deterministic_robust",
            {"prevalence": prevalence},
            [prevalence] * len(x_eval),
        )
    ]
    models = (
        (
            "regularized-logistic-v1",
            "regularized_logistic",
            make_pipeline(
                StandardScaler(),
                LogisticRegression(
                    C=1.0,
                    class_weight="balanced",
                    max_iter=1000,
                    random_state=1729,
                ),
            ),
        ),
        (
            "hist-gradient-boosting-v1",
            "gradient_boosting",
            HistGradientBoostingClassifier(
                learning_rate=0.05,
                max_depth=3,
                max_iter=100,
                l2_regularization=1.0,
                random_state=1729,
            ),
        ),
    )
    output.mkdir(parents=True, exist_ok=False)
    for candidate_id, family, model in models:
        model.fit(x_train, y_train)
        predictions = model.predict_proba(x_eval)[:, 1].astype(float).tolist()
        artifact = output / f"{candidate_id}.joblib"
        joblib.dump(model, artifact, compress=3)
        candidates.append((candidate_id, family, artifact, predictions))

    records = []
    for candidate_id, family, artifact, predictions in candidates:
        artifact_sha = None
        artifact_path = None
        if isinstance(artifact, Path):
            artifact_sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
            artifact_path = artifact.name
        records.append(
            {
                "candidate_id": candidate_id,
                "model_family": family,
                "artifact_path": artifact_path,
                "artifact_sha256": artifact_sha,
                "predictions": predictions,
                "release_state": "research",
            }
        )
    return {
        "use_case_id": snapshot["use_case_id"],
        "target_key": snapshot["target_key"],
        "target_approval_id": snapshot["target_approval_id"],
        "feature_schema_version": snapshot["feature_schema_version"],
        "dataset_version": snapshot["dataset_version"],
        "input_sha256": snapshot["_input_sha256"],
        "seed": 1729,
        "candidates": records,
        "promotion_authority": "none_offline_evaluation_only",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    snapshot = _read_snapshot(args.snapshot)
    report = _fit_candidates(snapshot, args.output)
    (args.output / "bakeoff-manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
