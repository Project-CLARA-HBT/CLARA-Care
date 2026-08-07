from datetime import date

from clara_api.api.v1.endpoints.research import _age_band


def test_age_band_keeps_life_stage_without_exact_birth_date() -> None:
    assert _age_band(date(1990, 1, 1)) == "18_39"
    assert _age_band(date(1940, 1, 1)) == "65_plus"


def test_age_band_rejects_invalid_or_future_values() -> None:
    assert _age_band(None) == ""
    assert _age_band("1990-01-01") == ""
    assert _age_band(date(2099, 1, 1)) == ""
