"""Regression vectors for interval endpoints and duplicate active records."""

from datetime import date

from .synthea_visit_refresh import History, evaluate, reference


def test_stop_day_open_interval_overlaps_and_simultaneous_expiry():
    dates = [date(2024, 1, d) for d in range(1, 5)]
    h = History(
        set(dates),
        [
            ("medications", "m", dates[0], dates[1]),
            ("medications", "m", dates[0], dates[2]),
            ("allergies", "a", dates[0], dates[2]),
            ("medications", "empty", dates[3], dates[3]),
        ],
    )
    assert reference(h.intervals, dates[1]) == {"medications": ["m"], "allergies": ["a"]}
    assert reference(h.intervals, dates[2]) == {"medications": [], "allergies": []}
    arms, transitions = evaluate(h)
    assert transitions["total"] == 3
    assert arms["single_section"]["stale"] == 1
    assert arms["snapshot_checked"]["review"] == 1
    assert arms["interval_sweep"]["stale"] == 0
