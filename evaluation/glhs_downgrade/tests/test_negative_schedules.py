"""Tests for E03 negative laundering schedule generation and schema validation."""

import json
from pathlib import Path

from evaluation.glhs_downgrade.negative_schedules import (
    DOMAINS,
    LaunderingSchedule,
    LaunderingTemplate,
    export_schedules_json,
    generate_all_schedules,
    generate_negative_schedules,
    generate_positive_controls,
    load_schedules_json,
)


def test_template_count_and_enumeration() -> None:
    """Verify exactly 10 distinct laundering templates exist."""
    templates = list(LaunderingTemplate)
    assert len(templates) == 10
    template_values = {t.value for t in templates}
    assert "template_1_model_downgrade_base_only" in template_values
    assert "template_2_human_review_drop_binding" in template_values
    assert "template_3_lineage_parent_substitution" in template_values
    assert "template_4_snapshot_substitution_review" in template_values
    assert "template_5_post_review_binding_mutation" in template_values
    assert "template_6_forged_non_consumed_thss" in template_values
    assert "template_7_cross_profile_snapshot_injection" in template_values
    assert "template_8_cross_actor_coordinate_substitution" in template_values
    assert "template_9_purpose_task_laundering" in template_values
    assert "template_10_direct_bypass_raw_mutation" in template_values


def test_negative_schedules_sample_size_and_stratification() -> None:
    """Verify negative schedule generator produces >= 160 schedules with >= 16 per template."""
    negatives = generate_negative_schedules(per_template_count=18)
    assert len(negatives) == 180
    assert len(negatives) >= 160

    template_counts: dict[str, int] = {}
    for s in negatives:
        assert s.is_negative is True
        assert s.expected_rejection is True
        assert s.template is not None
        assert s.domain in DOMAINS
        template_counts[s.template.value] = template_counts.get(s.template.value, 0) + 1

    assert len(template_counts) == 10
    for t_val, count in template_counts.items():
        assert count >= 16, f"Template {t_val} has count {count} < 16"


def test_positive_controls_sample_size() -> None:
    """Verify positive controls produce >= 32 valid review chains."""
    controls = generate_positive_controls(count=36)
    assert len(controls) == 36
    assert len(controls) >= 32
    for c in controls:
        assert c.is_negative is False
        assert c.expected_rejection is False
        assert c.domain in DOMAINS


def test_combined_suite_and_json_serialization(tmp_path: Path) -> None:
    """Verify JSON export and re-import preserves all schedule fields."""
    json_file = tmp_path / "negative_schedules.json"
    raw_data = export_schedules_json(json_file, negative_per_template=18, control_count=36)
    assert len(raw_data) == 216

    loaded = load_schedules_json(json_file)
    assert len(loaded) == 216

    first = loaded[0]
    assert isinstance(first, LaunderingSchedule)
    assert first.schedule_id == "E03-T01-01"
    assert first.template == LaunderingTemplate.TEMPLATE_1_MODEL_DOWNGRADE_BASE_ONLY
    assert first.is_negative is True
    assert first.domain in DOMAINS

    last = loaded[-1]
    assert isinstance(last, LaunderingSchedule)
    assert last.schedule_id == "E03-CTRL-36"
    assert last.is_negative is False
