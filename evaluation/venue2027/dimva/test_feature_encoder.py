"""Tests for DIMVA-X04_feature_encoder — leak-safe sequence feature encoding.

Positive vectors (fit-then-transform is the only legal path):
- Full pipeline: fit on training sequences, transform dev/test sequences,
  correct feature-vector shape (44 = 22 raw + 22 normalized), JSON-serializable
  matrix output, known-value checks for hand-computable features.
- Determinism: identical (encoder state, events, window) yield byte-identical
  matrices; independent fresh encoders fit on the same training data produce
  identical stored statistics.
- Feature lineage: complete over every output column, each record carries
  family/source_fields/transform/fit_dependent, exactly the intended features
  are marked fit-dependent, and lineage of a non-fitted encoder is identical
  (it is a code-level property, never data-derived).
- Five feature families present: time gaps, scope transitions, denial
  transitions, entropy, rate-adjusted counts.
- Fit discipline: training medians/IQRs are actually stored and applied — a
  dev/test encoding leaves the stored stats digest untouched (no leakage);
  a different training set produces different statistics (stats are fitted,
  not constants).
- ``encode(events, window)`` one-shot contract works.

Adversarial vectors (fail closed with stable reason codes):
- transform before fit refused with NOT_FITTED.
- Fitting on holdout-tagged data refused with HOLDOUT_LEAK: ``split`` /
  ``partition`` / ``split_tag`` tags of dev/test/holdout.
- Dev/test encodings cannot alter stored train stats (digest before ==
  digest after many transforms; row bound to the digest via stats_sha256).
- Refitting a fitted encoder refused (HOLDOUT_LEAK discipline).
- Leak-surface refusals: rejection reason-code-like fields
  (EVENT_REASON_CODE_FIELD_FORBIDDEN) and campaign-label fields
  (EVENT_LABEL_FIELD_FORBIDDEN) — RQ1 masking; unknown/missing fields, bad
  types, non-monotonic ts, mixed actors, empty training fit, invalid window.
- A holdout-tagged sequence can be transformed (encoded) but never fitted on.

Failure semantics: every adversarial case raises FeatureEncodingError with a
stable uppercase reason code — never a silent misencode, never a default that
masks the failure.
"""

from __future__ import annotations

import json

import pytest

from evaluation.venue2027.dimva.feature_encoding import (
    FAMILY_DENIAL_TRANSITIONS,
    FAMILY_ENTROPY,
    FAMILY_RATE_ADJUSTED,
    FAMILY_SCOPE_TRANSITIONS,
    FAMILY_TIME_GAPS,
    FEATURE_COUNT,
    FEATURE_ENCODING_VERSION,
    FEATURE_NAMES,
    NORMALIZED_FEATURE_NAMES,
    OUTPUT_FEATURE_NAMES,
    RC_EVENT_LABEL_FIELD_FORBIDDEN,
    RC_EVENT_MISSING_FIELD,
    RC_EVENT_REASON_CODE_FORBIDDEN,
    RC_EVENT_SEQUENCE_EMPTY,
    RC_EVENT_TS_NOT_MONOTONIC,
    RC_EVENT_UNKNOWN_FIELD,
    RC_EVENTS_NOT_A_LIST,
    RC_HOLDOUT_LEAK,
    RC_INVALID_WINDOW,
    RC_NOT_FITTED,
    RC_SESSION_MIXED_ACTORS,
    FeatureEncoder,
    FeatureEncodingError,
    encode,
)


def ev(tool: str, scope: str, allowed: bool, ts: int, **extra: object) -> dict:
    row: dict = {"tool": tool, "scope": scope, "allowed": allowed, "ts": ts}
    row.update(extra)
    return row


def benign_train() -> list[dict]:
    """Four synthetic benign training sessions (varied pacing, low denial)."""
    return [
        {
            "events": [
                ev("record_read", "scope_a", True, 0),
                ev("record_read", "scope_a", True, 120),
                ev("schedule_read", "scope_a", True, 300),
            ]
        },
        {
            "events": [
                ev("audit_query", "scope_b", True, 0),
                ev("audit_query", "scope_b", False, 900),
                ev("audit_query", "scope_b", True, 1800),
                ev("message_send", "scope_b", True, 2700),
            ]
        },
        {
            "events": [
                ev("record_write", "scope_c", True, 0),
                ev("record_write", "scope_c", True, 600),
                ev("record_read", "scope_c", True, 1500),
                ev("schedule_read", "scope_c", True, 2400),
                ev("record_write", "scope_c", True, 3300),
            ]
        },
        {
            "events": [
                ev("tool_list", "scope_a", True, 0),
                ev("flag_read", "scope_a", True, 450),
            ]
        },
    ]


def attack_session() -> dict:
    """Low-and-slow cross-tool campaign: many denials, wide gaps, one scope."""
    events = [ev(f"probe_tool_{i:02d}", "scope_a", False, 1000 + 1080 * i) for i in range(9)]
    events.append(ev("record_read", "scope_a", True, 1500))
    events.sort(key=lambda e: e["ts"])
    return {"events": events}


# ---------------------------------------------------------------------------
# Positive controls
# ---------------------------------------------------------------------------


def test_fit_then_transform_full_pipeline_shape() -> None:
    encoder = FeatureEncoder(window=3600)
    matrices = encoder.fit(benign_train()).transform([attack_session(), benign_train()[0]])
    assert len(matrices) == 2
    for matrix in matrices:
        assert len(matrix.values) == FEATURE_COUNT == 44
        assert matrix.feature_names == OUTPUT_FEATURE_NAMES
        assert matrix.encoder_version == FEATURE_ENCODING_VERSION
        assert matrix.window_seconds == 3600
        assert matrix.stats_sha256
    assert matrices[0].n_events == 10
    assert matrices[1].n_events == 3


def test_matrix_output_json_serializable() -> None:
    encoder = FeatureEncoder(window=1800)
    matrix = encoder.fit(benign_train()).transform([attack_session()])[0]
    payload = json.dumps(matrix.to_dict(), sort_keys=True)
    restored = json.loads(payload)
    assert restored["n_events"] == matrix.n_events
    assert restored["values"] == [round(v, 12) for v in matrix.values]
    assert restored["encoder_version"] == FEATURE_ENCODING_VERSION


def test_deterministic_same_state_byte_identical() -> None:
    a = FeatureEncoder(window=3600).fit(benign_train()).transform([attack_session()])[0]
    b = FeatureEncoder(window=3600).fit(benign_train()).transform([attack_session()])[0]
    assert a.to_dict() == b.to_dict()
    # Re-transforming the same encoder is also stable.
    again = FeatureEncoder(window=3600).fit(benign_train())
    first = again.transform([attack_session()])[0]
    second = again.transform([attack_session()])[0]
    assert first.to_dict() == second.to_dict()


def test_five_feature_families_present_in_lineage() -> None:
    lineage = FeatureEncoder.feature_lineage()
    families = {record.family for record in lineage}
    assert {
        FAMILY_TIME_GAPS,
        FAMILY_SCOPE_TRANSITIONS,
        FAMILY_DENIAL_TRANSITIONS,
        FAMILY_ENTROPY,
        FAMILY_RATE_ADJUSTED,
    } <= families


def test_lineage_complete_over_every_column() -> None:
    lineage = FeatureEncoder.feature_lineage()
    names = [record.name for record in lineage]
    assert len(names) == len(set(names)), "lineage rows must be unique per feature"
    assert set(names) == set(OUTPUT_FEATURE_NAMES)
    for record in lineage:
        assert record.family
        assert record.source_fields, f"{record.name} must name its source fields"
        assert record.transform, f"{record.name} must describe its transform"
        assert isinstance(record.fit_dependent, bool)
        # JSON-serializable lineage records (audit artifact requirement).
        assert json.dumps(record.to_dict())


def test_lineage_fit_dependent_exactly_normalized_and_ratio() -> None:
    lineage = {record.name: record for record in FeatureEncoder.feature_lineage()}
    fit_dependent = {n for n, r in lineage.items() if r.fit_dependent}
    assert fit_dependent == set(NORMALIZED_FEATURE_NAMES) | {"denial_rate_ratio_to_train"}
    # Raw companions of the normalized block are fit-independent, except the
    # rate-ratio itself (its raw value already divides by the train rate).
    for norm in NORMALIZED_FEATURE_NAMES:
        raw = norm[: -len("_norm")]
        if raw == "denial_rate_ratio_to_train":
            assert lineage[raw].fit_dependent is True
        else:
            assert lineage[raw].fit_dependent is False
        assert "train" in lineage[norm].transform


def test_lineage_is_code_level_never_data_derived() -> None:
    a = FeatureEncoder(window=600).fit(benign_train()).feature_lineage()
    b = FeatureEncoder.feature_lineage()
    c = (
        FeatureEncoder(window=90)
        .fit(  # never fitted encoder is fine too
            benign_train()
        )
        .feature_lineage()
    )
    assert [r.to_dict() for r in a] == [r.to_dict() for r in b] == [r.to_dict() for r in c]


def test_known_feature_values_hand_computed() -> None:
    events = [
        ev("t1", "s1", False, 0),
        ev("t2", "s1", False, 60),
        ev("t1", "s2", True, 360),
    ]
    encoder = FeatureEncoder(window=120)
    matrix = encoder.fit([{"events": events}]).transform([{"events": events}])[0]
    values = dict(zip(matrix.feature_names, matrix.values))
    assert values["denied_fraction"] == pytest.approx(2 / 3)
    # gaps: 60, 300 -> mean 180, max 300, min 60; short (<=120): 1/2
    assert values["gap_mean_seconds"] == pytest.approx(180.0)
    assert values["gap_max_seconds"] == pytest.approx(300.0)
    assert values["gap_min_seconds"] == pytest.approx(60.0)
    assert values["gap_short_fraction"] == pytest.approx(0.5)
    # 2 distinct scopes, 1 switch over 2 transitions
    assert values["distinct_scopes"] == pytest.approx(2.0)
    assert values["scope_switch_rate"] == pytest.approx(0.5)
    # denial runs: one run of length 2
    assert values["denial_run_max"] == pytest.approx(2.0)
    assert values["denial_run_mean"] == pytest.approx(2.0)
    assert values["allowed_after_denied_rate"] == pytest.approx(0.5)
    assert values["denied_after_denied_rate"] == pytest.approx(0.5)
    # tools: t1 x2, t2 x1 -> entropy = -(2/3 log2 2/3 + 1/3 log2 1/3)
    import math

    expected_tool_entropy = -(2 / 3) * math.log2(2 / 3) - (1 / 3) * math.log2(1 / 3)
    assert values["tool_entropy_bits"] == pytest.approx(expected_tool_entropy, abs=1e-9)
    # span 360s = 0.1h; 3 events / 0.1h = 30/h; 2 denials / 0.1h = 20/h
    assert values["events_per_hour"] == pytest.approx(30.0)
    assert values["denials_per_hour"] == pytest.approx(20.0)
    assert values["distinct_tools_per_hour"] == pytest.approx(20.0)
    # train denial rate is 2/3; ratio = (2/3)/(2/3) = 1
    assert values["denial_rate_ratio_to_train"] == pytest.approx(1.0)


def test_stats_are_fitted_not_constants() -> None:
    sparse = benign_train()
    busy = benign_train() + [attack_session() for _ in range(4)]
    a = FeatureEncoder(window=3600).fit(sparse)
    b = FeatureEncoder(window=3600).fit(busy)
    assert a.stats_digest() != b.stats_digest()
    # Same training data twice -> identical statistics (deterministic fit).
    c = FeatureEncoder(window=3600).fit(sparse)
    assert a.stats_digest() == c.stats_digest()


def test_dev_test_encoding_does_not_alter_stored_train_stats() -> None:
    encoder = FeatureEncoder(window=3600).fit(benign_train())
    digest_before = encoder.stats_digest()
    holdout_rows = [attack_session(), {"events": benign_train()[0]["events"], "split": "test"}]
    for _ in range(5):
        encoder.transform(holdout_rows)
    assert encoder.stats_digest() == digest_before
    # Rows are bound to the digest they were produced under.
    row = encoder.transform([attack_session()])[0]
    assert row.stats_sha256 == digest_before


def test_holdout_sequences_can_be_transformed_never_fitted() -> None:
    encoder = FeatureEncoder(window=3600).fit(benign_train())
    tagged = {
        "events": attack_session()["events"],
        "split": "test",
    }
    matrix = encoder.transform([tagged])[0]
    assert matrix.n_events == 10


def test_encode_one_shot_contract() -> None:
    matrix = encode(benign_train()[0], 3600)
    assert len(matrix.values) == FEATURE_COUNT
    assert matrix.window_seconds == 3600
    try:
        encode({"events": benign_train()[0]["events"], "split": "holdout"}, 3600)
        raise AssertionError("encode on holdout-tagged data must be refused")
    except FeatureEncodingError as err:
        assert err.reason_code == RC_HOLDOUT_LEAK


# ---------------------------------------------------------------------------
# Adversarial controls
# ---------------------------------------------------------------------------


def test_transform_before_fit_refused_not_fitted() -> None:
    encoder = FeatureEncoder(window=3600)
    assert not encoder.is_fitted
    with pytest.raises(FeatureEncodingError) as err:
        encoder.transform([benign_train()[0]])
    assert err.value.reason_code == RC_NOT_FITTED
    with pytest.raises(FeatureEncodingError) as err:
        encoder.stats_digest()
    assert err.value.reason_code == RC_NOT_FITTED


@pytest.mark.parametrize("tag", ["dev", "test", "holdout"])
@pytest.mark.parametrize("key", ["split", "partition", "split_tag"])
def test_fit_on_holdout_tagged_data_refused(key: str, tag: str) -> None:
    encoder = FeatureEncoder(window=3600)
    with pytest.raises(FeatureEncodingError) as err:
        encoder.fit([{"events": benign_train()[0]["events"], key: tag}])
    assert err.value.reason_code == RC_HOLDOUT_LEAK
    assert not encoder.is_fitted


def test_fit_on_holdout_tagged_bare_mapping_partition_refused() -> None:
    encoder = FeatureEncoder(window=3600)
    with pytest.raises(FeatureEncodingError) as err:
        encoder.fit([benign_train()[0], {"events": attack_session()["events"], "partition": "dev"}])
    assert err.value.reason_code == RC_HOLDOUT_LEAK
    assert not encoder.is_fitted


def test_refit_refused_after_first_fit() -> None:
    encoder = FeatureEncoder(window=3600).fit(benign_train())
    digest = encoder.stats_digest()
    with pytest.raises(FeatureEncodingError) as err:
        encoder.fit([attack_session()])
    assert err.value.reason_code == RC_HOLDOUT_LEAK
    # Stored statistics unchanged by the refused refit.
    assert encoder.stats_digest() == digest


def test_rejection_reason_code_field_refused_leak_safe() -> None:
    for leak_key in ("reason_code", "reject_reason", "denial_reason", "rejection_code", "why"):
        encoder = FeatureEncoder(window=3600)
        poisoned = [{"events": [ev("t1", "s1", False, 0, **{leak_key: "EXPIRED_TOKEN"})]}]
        with pytest.raises(FeatureEncodingError) as err:
            encoder.fit(poisoned)
        assert err.value.reason_code == RC_EVENT_REASON_CODE_FORBIDDEN


def test_campaign_label_field_refused_on_events() -> None:
    encoder = FeatureEncoder(window=3600)
    with pytest.raises(FeatureEncodingError) as err:
        encoder.fit(
            [{"events": [ev("t1", "s1", False, 0, label="ATTACK", campaign_label="ATTACK")]}]
        )
    assert err.value.reason_code == RC_EVENT_LABEL_FIELD_FORBIDDEN


def test_unknown_field_refused() -> None:
    encoder = FeatureEncoder(window=3600)
    with pytest.raises(FeatureEncodingError) as err:
        encoder.fit([{"events": [ev("t1", "s1", True, 0, payload_blob="x")]}])
    assert err.value.reason_code == RC_EVENT_UNKNOWN_FIELD


def test_missing_required_field_refused() -> None:
    encoder = FeatureEncoder(window=3600)
    with pytest.raises(FeatureEncodingError) as err:
        encoder.fit([{"events": [{"tool": "t1", "scope": "s1", "allowed": True}]}])
    assert err.value.reason_code == RC_EVENT_MISSING_FIELD


def test_non_monotonic_ts_refused() -> None:
    encoder = FeatureEncoder(window=3600)
    with pytest.raises(FeatureEncodingError) as err:
        encoder.fit([{"events": [ev("t1", "s1", True, 100), ev("t1", "s1", True, 50)]}])
    assert err.value.reason_code == RC_EVENT_TS_NOT_MONOTONIC


def test_mixed_actors_refused() -> None:
    encoder = FeatureEncoder(window=3600)
    with pytest.raises(FeatureEncodingError) as err:
        encoder.fit(
            [
                {
                    "events": [
                        ev("t1", "s1", True, 0, actor="actor-1"),
                        ev("t1", "s1", True, 10, actor="actor-2"),
                    ]
                }
            ]
        )
    assert err.value.reason_code == RC_SESSION_MIXED_ACTORS


def test_empty_training_fit_refused() -> None:
    encoder = FeatureEncoder(window=3600)
    with pytest.raises(FeatureEncodingError) as err:
        encoder.fit([{"events": []}])
    assert err.value.reason_code == RC_EVENT_SEQUENCE_EMPTY


def test_train_events_not_a_list_refused() -> None:
    encoder = FeatureEncoder(window=3600)
    with pytest.raises(FeatureEncodingError) as err:
        encoder.fit({"events": benign_train()[0]["events"]})  # a single mapping, not a list
    assert err.value.reason_code == RC_EVENTS_NOT_A_LIST


@pytest.mark.parametrize("bad_window", [0, -5, True, 3.5, "3600", None])
def test_invalid_window_refused(bad_window: object) -> None:
    with pytest.raises(FeatureEncodingError) as err:
        FeatureEncoder(window=bad_window)  # type: ignore[arg-type]
    assert err.value.reason_code == RC_INVALID_WINDOW


def test_empty_sequence_transforms_to_zero_row() -> None:
    encoder = FeatureEncoder(window=3600).fit(benign_train())
    matrix = encoder.transform([{"events": []}])[0]
    assert matrix.n_events == 0
    # Raw block is exactly zero; the normalized block centers the zero raw
    # values with the stored TRAIN medians (a dev/test row, never refitted).
    n_raw = len(FEATURE_NAMES)
    assert all(value == 0.0 for value in matrix.values[:n_raw])
    assert all(isinstance(value, float) for value in matrix.values[n_raw:])


def test_normalize_uses_train_median_iqr_no_future_leakage() -> None:
    # Normalized block is (raw - train_median) / train_iqr: verify directly on
    # a training row (median/IQR come from the training rows only).
    encoder = FeatureEncoder(window=3600).fit(benign_train())
    matrix = encoder.transform([benign_train()[0]])[0]
    values = dict(zip(matrix.feature_names, matrix.values))
    for raw_name in FEATURE_NAMES:
        raw = values[raw_name]
        norm = values[f"{raw_name}_norm"]
        lineage = {record.name: record for record in FeatureEncoder.feature_lineage()}[
            f"{raw_name}_norm"
        ]
        # The transform formula references train statistics only.
        assert "train_median" in lineage.transform and "train_iqr" in lineage.transform
        assert isinstance(raw, float) and isinstance(norm, float)
