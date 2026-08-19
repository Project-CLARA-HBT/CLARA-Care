from research.careguard_vn.mapping_candidates import (
    TerminologyIndex,
    generate_candidates,
    normalize_record,
    normalize_text,
    parse_strength,
    record_digest,
)

ROWS = [
    {
        "source_record_id": "DAV-0001",
        "source_record_hash": "a" * 64,
        "product_name": "Warfarin STADA 5mg",
        "registration_number": "VD-12345-20",
        "active_ingredient_text": "warfarin sodium",
        "strength": "5 mg",
        "dosage_form": "tablet",
        "manufacturer": "STADA",
        "registrant": "STADA Vietnam",
        "release_label": "DAV-export-2026-09-01",
    },
    {
        "source_record_id": "DAV-0002",
        "source_record_hash": "b" * 64,
        "product_name": "Warfarin (Coumadin) 2mg",
        "registration_number": "",
        "active_ingredient_text": "warfarin",
        "strength": "2 mg",
        "dosage_form": "tablet",
        "manufacturer": "",
        "registrant": "",
        "release_label": "DAV-export-2026-09-01",
    },
]


def test_normalize_text_deterministic():
    assert normalize_text("  Warfarin\nSTADA  ") == normalize_text("Warfarin STADA")
    assert normalize_text("Warfarin-STADA 5mg") == "warfarin stada 5mg"


def test_parse_strength():
    assert parse_strength("5 mg") == ("5", "mg")
    assert parse_strength("500mg") == ("500", "mg")
    assert parse_strength("none") is None


def test_normalize_record_required_fields():
    record = normalize_record(ROWS[0])
    assert record.strength_parsed == ("5", "mg")
    assert record.product_name_norm == "warfarin stada 5mg"
    assert len(record_digest(record)) == 64


def test_missing_required_field_rejected():
    try:
        normalize_record({**ROWS[0], "product_name": ""})
    except ValueError as exc:
        assert "product_name" in str(exc)
    else:
        raise AssertionError("missing required field should be rejected")


def test_terminology_index_ingredient_and_fuzzy():
    index = TerminologyIndex(
        [
            {"rxcui": "11289", "name": "warfarin sodium", "synonym": "warfarin", "tty": "IN"},
            {"rxcui": "200349", "name": "warfarin 5 MG Oral Tablet", "synonym": "", "tty": "SCD"},
        ]
    )
    record = normalize_record(ROWS[0])
    outcome = generate_candidates(record, index)
    assert outcome.status == "CANDIDATES"
    assert any(candidate.method == "ingredient_level" for candidate in outcome.candidates)
    assert any(candidate.rxcui == "11289" for candidate in outcome.candidates)
    ingredient = next(
        candidate for candidate in outcome.candidates if candidate.rxcui == "11289"
    )
    assert ingredient.score == 0.85
    assert outcome.candidates[0].score >= ingredient.score


def test_no_terminology_runs_without_dav():
    record = normalize_record(ROWS[1])
    outcome = generate_candidates(record, None)
    assert outcome.status == "NO_TERMINOLOGY"
    assert outcome.candidates == []
