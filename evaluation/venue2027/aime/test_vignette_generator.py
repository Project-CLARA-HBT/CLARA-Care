"""Tests for AIME-X02_case_generator (Phase P02) — stratified synthetic vignettes.

Positive controls (deterministic, synthetic only, no provider call):
- ``generate(seed, source_family, n)`` is byte-reproducible for a fixed
  generator version: same call twice -> identical IDs, labels and content
  hash; different seed -> different hash.
- Family balance: the five AIME update families
  (``stable_history``, ``consent_change``, ``medication_withdrawal``,
  ``allergy_update``, ``reconciliation``) are near-uniformly represented
  and every family is present for balanced requests.
- Independent case-archetype split: each archetype (base case identity)
  is assigned to exactly one split, so no vignette pair built from the same
  archetype ever appears in two splits (split disjointness by archetype).
- Deterministic manifest: canonical JSON with a SHA256 content hash that
  covers unit ids, families, archetypes, splits and label provenance; the
  manifest's own hash is stable across runs.
- Every vignette carries a family-definition-derived label whose
  ``label_provenance`` names only ``SYNTHETIC_FAMILY_DEFINITION`` (never a
  model answer), plus synthetic_only/source_authority markers.

Adversarial controls:
- Duplicate template across splits is detected: regenerating a vignette
  already assigned to one split and placing it in another is refused by
  ``assert_no_archetype_split_leak`` / ``detect_archetype_leakage`` with a
  stable reason code.
- Diagnosis-invented-as-settled-fact content is refused: a vignette or
  template asserting a settled diagnosis invented outside the family
  definition is rejected fail-closed with ``SETTLED_DIAGNOSIS_REFUSED``
  (uncertainty stays first-class).
- Model-derived label provenance is refused: ``assert_no_model_derived_labels``
  fails with ``MODEL_DERIVED_LABEL_REFUSED`` when any label provenance names a
  model answer (proposed output, model answer, LLM label) — the guard is also
  exercised against the real generated batch.
"""

from __future__ import annotations

import pytest

from evaluation.venue2027.aime import vignette_generator as vg
from evaluation.venue2027.aime.vignette_generator import (
    AIME_UPDATE_FAMILIES,
    SPLITS,
    Vignette,
    assert_no_archetype_split_leak,
    assert_no_model_derived_labels,
    build_manifest,
    detect_archetype_leakage,
    generate,
)

SOURCE_FAMILY = "counterfactual_clinical_workflow_safety"
SEED = 2027


# ------------------------------------------------------------- positive tests


def test_generate_deterministic() -> None:
    a = generate(seed=SEED, source_family=SOURCE_FAMILY, n=20)
    b = generate(seed=SEED, source_family=SOURCE_FAMILY, n=20)
    assert [v.unit_id for v in a] == [v.unit_id for v in b]
    assert [v.archetype for v in a] == [v.archetype for v in b]
    assert [v.split for v in a] == [v.split for v in b]
    assert [v.label for v in a] == [v.label for v in b]
    assert [v.to_dict() for v in a] == [v.to_dict() for v in b]
    assert build_manifest(a).content_sha256 == build_manifest(b).content_sha256


def test_different_seed_yields_different_batch() -> None:
    a = generate(seed=SEED, source_family=SOURCE_FAMILY, n=20)
    b = generate(seed=SEED + 1, source_family=SOURCE_FAMILY, n=20)
    assert build_manifest(a).content_sha256 != build_manifest(b).content_sha256


def test_balances_five_update_families() -> None:
    n = 50
    batch = generate(seed=SEED, source_family=SOURCE_FAMILY, n=n)
    counts = {family: 0 for family in AIME_UPDATE_FAMILIES}
    for vignette in batch:
        assert vignette.family in counts
        counts[vignette.family] += 1
    assert all(count > 0 for count in counts.values())
    # Near-uniform: each family gets floor/ceil of n/5; share within kernel tolerance.
    expected = n / len(AIME_UPDATE_FAMILIES)
    for count in counts.values():
        assert abs(count - expected) <= 1.0 + 1e-9


def test_balanced_family_override_explicit() -> None:
    batch = generate(seed=SEED, source_family=SOURCE_FAMILY, n=10, balanced=True)
    counts = {family: 0 for family in AIME_UPDATE_FAMILIES}
    for vignette in batch:
        counts[vignette.family] += 1
    assert set(counts.values()) == {2}


def test_archetype_split_disjoint() -> None:
    batch = generate(seed=SEED, source_family=SOURCE_FAMILY, n=60)
    by_archetype: dict[str, set[str]] = {}
    for vignette in batch:
        by_archetype.setdefault(vignette.archetype, set()).add(vignette.split)
    assert by_archetype, "no archetypes generated"
    for archetype, splits in by_archetype.items():
        assert len(splits) == 1, f"archetype {archetype} crosses splits: {splits}"
    # All three splits are represented for a reasonable n.
    used = {v.split for v in batch}
    assert used == set(SPLITS)


def test_split_views_partition_batch() -> None:
    batch = generate(seed=SEED, source_family=SOURCE_FAMILY, n=30)
    views = [batch.split(name) for name in SPLITS]
    total = sum(len(view) for view in views)
    assert total == len(batch)
    for view in views:
        assert len({v.archetype for v in view}) == len(view)


def test_manifest_is_deterministic_and_hashed() -> None:
    batch = generate(seed=SEED, source_family=SOURCE_FAMILY, n=25)
    m1 = build_manifest(batch)
    m2 = build_manifest(generate(seed=SEED, source_family=SOURCE_FAMILY, n=25))
    assert m1.content_sha256 == m2.content_sha256
    assert m1.manifest["generator_version"] == vg.VIGNETTE_GENERATOR_VERSION
    assert m1.manifest["split_leak_clean"] is True
    payload = m1.to_json()
    assert vg.CONTENT_SHA256_RE.fullmatch(m1.content_sha256)
    assert m1.content_sha256 in payload


def test_label_provenance_is_family_definition_only() -> None:
    batch = generate(seed=SEED, source_family=SOURCE_FAMILY, n=25)
    for vignette in batch:
        assert vignette.label_provenance["derived_from"] == "SYNTHETIC_FAMILY_DEFINITION"
        assert vignette.label_provenance["family_definition_version"] == (
            vg.FAMILY_DEFINITION_VERSION
        )
        assert vignette.label in vg.ALLOWED_LABELS
        assert vignette.synthetic_only is True
        assert vignette.source_authority == "SYNTHETIC_RESEARCH_ONLY"


def test_unit_ids_unique() -> None:
    batch = generate(seed=SEED, source_family=SOURCE_FAMILY, n=40)
    ids = [v.unit_id for v in batch]
    assert len(ids) == len(set(ids))


def test_vignette_payload_schema_shaped() -> None:
    batch = generate(seed=SEED, source_family=SOURCE_FAMILY, n=10)
    for vignette in batch:
        payload = vignette.payload
        assert payload["schema_version"] == vg.VIGNETTE_SCHEMA_VERSION
        assert payload["synthetic_only"] is True
        assert payload["source_authority"] == "SYNTHETIC_RESEARCH_ONLY"
        assert payload["family"] == vignette.family
        assert payload["archetype"] == vignette.archetype
        assert payload["label"] == vignette.label
        assert payload["label_provenance"] == vignette.label_provenance
        timeline = payload["timeline"]
        assert timeline[0]["event_kind"] == "INITIAL_STATE"
        orders = [event["order"] for event in timeline]
        times = [event["logical_time"] for event in timeline]
        assert orders == sorted(orders) and times == sorted(times)


def test_guard_accepts_clean_generated_batch() -> None:
    batch = generate(seed=SEED, source_family=SOURCE_FAMILY, n=30)
    assert_no_model_derived_labels(batch)
    assert detect_archetype_leakage(batch) == ()


# ---------------------------------------------------------- adversarial tests


def test_duplicate_template_across_split_detected() -> None:
    batch = generate(seed=SEED, source_family=SOURCE_FAMILY, n=30)
    src = batch[0]
    # Same template content (archetype+family) re-emitted under another split.
    forged = Vignette(
        unit_id=src.unit_id + "-forged",
        family=src.family,
        archetype=src.archetype,
        split="test" if src.split != "test" else "train",
        label=src.label,
        label_provenance=src.label_provenance,
        payload=src.payload,
        template=src.template,
        synthetic_only=src.synthetic_only,
        source_authority=src.source_authority,
    )
    assert detect_archetype_leakage([*batch, forged]) == ("ARCHETYPE_SPLIT_LEAKAGE",)
    with pytest.raises(vg.VignetteGeneratorError) as exc:
        assert_no_archetype_split_leak([*batch, forged])
    assert exc.value.reason_code == "ARCHETYPE_SPLIT_LEAKAGE"


def test_leak_detector_clean_on_fresh_batches() -> None:
    for seed in (1, 2, 3):
        batch = generate(seed=seed, source_family=SOURCE_FAMILY, n=36)
        assert detect_archetype_leakage(batch) == ()
        assert_no_archetype_split_leak(batch)


def test_diagnosis_invented_as_settled_fact_refused() -> None:
    batch = generate(seed=SEED, source_family=SOURCE_FAMILY, n=5)
    innocent = batch[0]
    invented = dict(innocent.template)
    invented["settlement"] = "diagnosis: community-acquired pneumonia confirmed"
    forged = Vignette(
        unit_id=innocent.unit_id,
        family=innocent.family,
        archetype=innocent.archetype,
        split=innocent.split,
        label=innocent.label,
        label_provenance=innocent.label_provenance,
        payload=innocent.payload,
        template=invented,
        synthetic_only=innocent.synthetic_only,
        source_authority=innocent.source_authority,
    )
    with pytest.raises(vg.VignetteGeneratorError) as exc:
        assert_no_settled_diagnosis([forged])
    assert exc.value.reason_code == "SETTLED_DIAGNOSIS_REFUSED"


def assert_no_settled_diagnosis(batch: list[Vignette]) -> None:
    vg.assert_no_settled_diagnosis(batch)


def test_model_derived_label_provenance_refused() -> None:
    batch = generate(seed=SEED, source_family=SOURCE_FAMILY, n=5)
    src = batch[0]
    model_provenance = dict(src.label_provenance)
    model_provenance["derived_from"] = "PROPOSED_MODEL_ANSWER"
    forged = Vignette(
        unit_id=src.unit_id,
        family=src.family,
        archetype=src.archetype,
        split=src.split,
        label=src.label,
        label_provenance=model_provenance,
        payload=src.payload,
        template=src.template,
        synthetic_only=src.synthetic_only,
        source_authority=src.source_authority,
    )
    with pytest.raises(vg.VignetteGeneratorError) as exc:
        assert_no_model_derived_labels([*batch, forged])
    assert exc.value.reason_code == "MODEL_DERIVED_LABEL_REFUSED"


@pytest.mark.parametrize(
    "forbidden",
    [
        "PROPOSED_MODEL_ANSWER",
        "MODEL_ANSWER",
        "PROPOSED_OUTPUT",
        "LLM_OUTPUT",
        "DEEPSEEK_FLASH",
        "model_response",
    ],
)
def test_guard_rejects_each_model_provenance_marker(forbidden: str) -> None:
    batch = generate(seed=SEED, source_family=SOURCE_FAMILY, n=3)
    src = batch[0]
    provenance = dict(src.label_provenance)
    provenance["derived_from"] = forbidden
    forged = Vignette(
        unit_id=src.unit_id,
        family=src.family,
        archetype=src.archetype,
        split=src.split,
        label=src.label,
        label_provenance=provenance,
        payload=src.payload,
        template=src.template,
        synthetic_only=src.synthetic_only,
        source_authority=src.source_authority,
    )
    with pytest.raises(vg.VignetteGeneratorError) as exc:
        assert_no_model_derived_labels([forged])
    assert exc.value.reason_code == "MODEL_DERIVED_LABEL_REFUSED"


def test_invalid_inputs_fail_closed() -> None:
    with pytest.raises(vg.VignetteGeneratorError) as exc:
        generate(seed=SEED, source_family="unknown_family", n=10)
    assert exc.value.reason_code == "UNKNOWN_SOURCE_FAMILY"
    with pytest.raises(vg.VignetteGeneratorError) as exc:
        generate(seed=SEED, source_family=SOURCE_FAMILY, n=0)
    assert exc.value.reason_code == "INVALID_N"
