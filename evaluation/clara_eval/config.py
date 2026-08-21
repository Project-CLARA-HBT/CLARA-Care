"""Typed validation for the four CLARA-Eval VN suite configurations.

Configurations are intentionally declarative: they say what evidence a suite
needs, but do not manufacture metric values when the approved data, provider
or reviewer is unavailable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .tracks import REQUIRED_TRACK_IDS


class SuiteConfigError(ValueError):
    """A suite configuration is malformed or violates an evaluation policy."""


SuiteKind = Literal["smoke", "nightly", "release", "judge_demo"]

# The checked-in v1 configs are JSON-compatible YAML so PR CI does not need a
# YAML package.  This catalog makes every required measurement explicit even
# before credentialed data is installed.  The runner reports each as
# ``not_measured`` rather than inventing a value.
DEFAULT_REQUIRED_METRICS: dict[str, tuple[str, ...]] = {
    "vietnamese_clinical_understanding": (
        "intent_macro_f1",
        "negation_scope_f1",
        "emergency_recall",
    ),
    "medical_qa_patient_communication": (
        "unsafe_recommendation_rate",
        "appropriate_abstention_rate",
        "plain_language_score",
    ),
    "research_rag": (
        "retrieval_recall_at_10",
        "citation_precision",
        "unsupported_claim_rate",
    ),
    "careguard_drugbank": (
        "critical_ddi_recall",
        "required_source_fail_closed",
        "vietnamese_normalization_critical_recall",
        "medication_normalization_top1",
    ),
    "scribe_asr": (
        "medical_term_wer",
        "safety_term_recall",
        "pii_redaction_pass_rate",
        "clinician_edit_time_reduction",
    ),
    "lifemap_invariants": (
        "invariant_pass_rate",
        "owner_scope_pass_rate",
        "emergency_fast_path_recall",
    ),
    "council_ablation": ("safety_regression_rate", "red_flag_recall"),
    "wording_usability": ("unsafe_wording_rate", "plain_language_score"),
    "model_routing_latency_cost": (
        "route_policy_pass_rate",
        "latency_p95_ms",
        "estimated_cost_usd",
        "large_llm_cost_reduction",
    ),
}


def _default_required_artifacts(suite: str) -> tuple[str, ...]:
    common = (
        "summary.json",
        "summary.md",
        "metrics.json",
        "critical-errors.csv",
        "ablations.csv",
        "model-manifest.json",
        "dataset-manifest.json",
        "retrieval-snapshot.json",
        "latency-cost.json",
        "confidence-intervals.json",
        "examples",
    )
    if suite == "judge_demo":
        return ("index.html", *common)
    return common


@dataclass(frozen=True)
class TrackConfig:
    track_id: str
    dataset: str | None
    mode: str | None
    required_metrics: tuple[str, ...]


@dataclass(frozen=True)
class SuiteConfig:
    schema_version: str
    suite: SuiteKind
    display_name: str
    execution_mode: str
    strict_gate: bool
    requires_live_dependencies: bool
    output_dir: str
    pii_policy: str
    required_artifacts: tuple[str, ...]
    tracks: tuple[TrackConfig, ...]
    gates: dict[str, bool]
    dataset_manifest: str = "evaluation/clara_eval/datasets/manifest.json"
    allow_synthetic_metrics: bool = False

    @property
    def enabled_tracks(self) -> tuple[str, ...]:
        return tuple(track.track_id for track in self.tracks)

    @property
    def release_locked(self) -> bool:
        return self.suite == "release" and self.execution_mode == "locked-live"


def _read_config(path: Path) -> Any:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SuiteConfigError("suite_config_unreadable") from exc
    # JSON is valid YAML. Keeping this path dependency-free permits a minimal
    # PR runner to load JSON-compatible suite configurations.
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SuiteConfigError(
            "yaml_parser_unavailable_install_pyyaml_or_use_json_compatible_yaml"
        ) from exc
    try:
        return yaml.safe_load(raw)
    except yaml.YAMLError as exc:  # type: ignore[attr-defined]
        raise SuiteConfigError("suite_config_unreadable") from exc


def _required_string(raw: dict[str, Any], name: str) -> str:
    value = raw.get(name)
    if not isinstance(value, str) or not value.strip():
        raise SuiteConfigError(f"suite_{name}_invalid")
    return value.strip()


def _required_bool(raw: dict[str, Any], name: str) -> bool:
    value = raw.get(name)
    if not isinstance(value, bool):
        raise SuiteConfigError(f"suite_{name}_invalid")
    return value


def _parse_tracks(raw: Any) -> tuple[TrackConfig, ...]:
    if not isinstance(raw, list) or not raw:
        raise SuiteConfigError("suite_tracks_invalid")
    tracks: list[TrackConfig] = []
    for item in raw:
        if not isinstance(item, dict):
            raise SuiteConfigError("suite_track_not_object")
        track_id = _required_string(item, "id")
        if item.get("enabled") is not True:
            raise SuiteConfigError(f"suite_track_disabled:{track_id}")
        dataset = item.get("dataset")
        mode = item.get("mode")
        required_metrics = item.get("required_metrics", [])
        if dataset is not None and (not isinstance(dataset, str) or not dataset.strip()):
            raise SuiteConfigError(f"suite_track_dataset_invalid:{track_id}")
        if mode is not None and (not isinstance(mode, str) or not mode.strip()):
            raise SuiteConfigError(f"suite_track_mode_invalid:{track_id}")
        if not isinstance(required_metrics, list) or not all(
            isinstance(metric, str) and metric.strip() for metric in required_metrics
        ):
            raise SuiteConfigError(f"suite_track_metrics_invalid:{track_id}")
        if len(required_metrics) != len(set(required_metrics)):
            raise SuiteConfigError(f"suite_track_metrics_duplicate:{track_id}")
        tracks.append(
            TrackConfig(
                track_id=track_id,
                dataset=dataset.strip() if isinstance(dataset, str) else None,
                mode=mode.strip() if isinstance(mode, str) else None,
                required_metrics=tuple(required_metrics),
            )
        )
    track_ids = {track.track_id for track in tracks}
    if track_ids != REQUIRED_TRACK_IDS or len(track_ids) != len(tracks):
        raise SuiteConfigError("suite_tracks_must_cover_all_required_tracks")
    return tuple(tracks)


def _parse_gates(raw: Any) -> dict[str, bool]:
    if not isinstance(raw, dict) or not raw:
        raise SuiteConfigError("suite_gates_invalid")
    if not all(isinstance(value, bool) for value in raw.values()):
        raise SuiteConfigError("suite_gates_boolean_invalid")
    return dict(raw)


def _load_flat_v1(raw: dict[str, Any]) -> SuiteConfig:
    """Support the first flat config contract during active-eval migration."""

    expected_keys = {
        "schema_version",
        "suite",
        "dataset_manifest",
        "enabled_tracks",
        "requires_live_dependencies",
        "release_locked",
        "allow_synthetic_metrics",
        "output_dir",
    }
    if set(raw) != expected_keys:
        raise SuiteConfigError("suite_config_keys_invalid")
    suite = raw["suite"]
    if suite not in {"smoke", "nightly", "release", "judge_demo"}:
        raise SuiteConfigError("suite_kind_invalid")
    tracks = raw["enabled_tracks"]
    if (
        not isinstance(tracks, list)
        or not tracks
        or not all(isinstance(track, str) for track in tracks)
    ):
        raise SuiteConfigError("suite_tracks_invalid")
    if set(tracks) != REQUIRED_TRACK_IDS or len(tracks) != len(set(tracks)):
        raise SuiteConfigError("suite_tracks_must_cover_all_required_tracks")
    booleans = (
        "requires_live_dependencies",
        "release_locked",
        "allow_synthetic_metrics",
    )
    if any(not isinstance(raw[name], bool) for name in booleans):
        raise SuiteConfigError("suite_config_boolean_invalid")
    dataset_manifest = _required_string(raw, "dataset_manifest")
    output_dir = _required_string(raw, "output_dir")
    config = SuiteConfig(
        schema_version=raw["schema_version"],
        suite=suite,  # type: ignore[arg-type]
        display_name=f"CLARA-Eval VN {suite}",
        execution_mode="locked-live" if raw["release_locked"] else "offline-or-live",
        strict_gate=suite in {"smoke", "nightly", "release"},
        requires_live_dependencies=raw["requires_live_dependencies"],
        output_dir=output_dir,
        pii_policy="manifest-governed",
        required_artifacts=_default_required_artifacts(suite),
        tracks=tuple(
            TrackConfig(
                track_id=track,
                dataset=None,
                mode="fixture" if suite in {"smoke", "judge_demo"} else "live-or-not-measured",
                required_metrics=DEFAULT_REQUIRED_METRICS[track],
            )
            for track in tracks
        ),
        gates={"fail_on_unmeasured_required_metric": raw["release_locked"]},
        dataset_manifest=dataset_manifest,
        allow_synthetic_metrics=raw["allow_synthetic_metrics"],
    )
    if config.suite == "smoke" and config.requires_live_dependencies:
        raise SuiteConfigError("smoke_must_not_require_live_dependencies")
    if config.suite == "release" and not config.release_locked:
        raise SuiteConfigError("release_must_be_locked")
    if config.allow_synthetic_metrics:
        raise SuiteConfigError("synthetic_metrics_are_never_allowed")
    return config


def load_suite_config(path: Path) -> SuiteConfig:
    raw = _read_config(path)
    if not isinstance(raw, dict):
        raise SuiteConfigError("suite_config_not_object")
    if raw.get("schema_version") == "clara-eval-vn.suite-config.v1":
        return _load_flat_v1(raw)
    if raw.get("schema_version") != "clara-eval-vn-suite/v1":
        raise SuiteConfigError("suite_config_schema_unsupported")
    suite_raw = raw.get("suite")
    if not isinstance(suite_raw, dict):
        raise SuiteConfigError("suite_metadata_invalid")
    suite_id = _required_string(suite_raw, "id")
    if suite_id not in {"smoke", "nightly", "release", "judge_demo"}:
        raise SuiteConfigError("suite_kind_invalid")
    required_artifacts = suite_raw.get("required_artifacts")
    if (
        not isinstance(required_artifacts, list)
        or not required_artifacts
        or not all(isinstance(item, str) and item.strip() for item in required_artifacts)
    ):
        raise SuiteConfigError("suite_required_artifacts_invalid")
    config = SuiteConfig(
        schema_version=raw["schema_version"],
        suite=suite_id,  # type: ignore[arg-type]
        display_name=_required_string(suite_raw, "display_name"),
        execution_mode=_required_string(suite_raw, "execution_mode"),
        strict_gate=_required_bool(suite_raw, "strict_gate"),
        requires_live_dependencies=_required_bool(suite_raw, "allow_live_dependencies"),
        output_dir=_required_string(suite_raw, "output_root"),
        pii_policy=_required_string(suite_raw, "pii_policy"),
        required_artifacts=tuple(required_artifacts),
        tracks=_parse_tracks(raw.get("tracks")),
        gates=_parse_gates(raw.get("gates")),
    )
    if config.suite == "smoke" and config.requires_live_dependencies:
        raise SuiteConfigError("smoke_must_not_require_live_dependencies")
    if config.suite == "release":
        if not config.release_locked:
            raise SuiteConfigError("release_must_be_locked")
        if not config.strict_gate or not config.gates.get("fail_on_unmeasured_required_metric"):
            raise SuiteConfigError("release_must_fail_on_unmeasured_metrics")
    if config.allow_synthetic_metrics:
        raise SuiteConfigError("synthetic_metrics_are_never_allowed")
    return config
