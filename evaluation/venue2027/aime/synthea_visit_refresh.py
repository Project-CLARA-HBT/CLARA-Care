"""Evaluate one-step chart refresh on a pinned public synthetic CSV release.

Only aggregated counts leave the runner. All arms start each step from the
previous reference view. The streaming comparator maintains counts per code,
so ending one of two overlapping orders cannot remove the other.
"""

import csv
import hashlib
import io
import json
import sys
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from . import selective_refresh as sr
from .selective_refresh import plan_transition

ARCHIVE_SHA256 = "ce211a05f27022ff1038000243a9291825ceb0107394e399b14c967948c030c3"
ARCHIVE_PREFIX = {
    ARCHIVE_SHA256: "",
    "870b68a127f3570ca964e89e49dd3433cf3e7a27cc4079d2bff5f094be0a43c2": "csv/",
}
FIELDS = ("medications", "allergies")
ARMS = ("single_section", "snapshot_checked", "full_scan", "interval_sweep")
METRICS = ("attempted", "delivered", "stale", "review", "partial", "full", "rebuilt_dependencies")


def day(stamp):
    if len(stamp) != 10:
        if not stamp.endswith("Z"):
            raise ValueError("expected_utc_timestamp")
        return datetime.fromisoformat(stamp).date()
    return date.fromisoformat(stamp)


@dataclass
class History:
    visits: set = field(default_factory=set)
    intervals: list = field(default_factory=list)
    invalid_intervals: int = 0


def read(archive, prefix=""):
    histories = defaultdict(History)
    counts = Counter()
    for table in ("encounters", *FIELDS):
        with archive.open(prefix + table + ".csv") as raw:
            for row in csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig")):
                counts[table] += 1
                history = histories[row["PATIENT"]]
                start = day(row["START"])
                if table == "encounters":
                    history.visits.add(start)
                    continue
                stop = day(row["STOP"]) if row["STOP"] else None
                if not row["CODE"] or (stop is not None and stop < start):
                    counts["invalid_" + table] += 1
                    history.invalid_intervals += 1
                    continue
                system = row["SYSTEM"] if table == "allergies" else "RxNorm"
                history.intervals.append((table, system + "|" + row["CODE"], start, stop))
    return histories, counts


def reference(intervals, at):
    values = {section: set() for section in FIELDS}
    for section, code, start, stop in intervals:
        if start <= at and (stop is None or at < stop):
            values[section].add(code)
    return {k: sorted(v) for k, v in values.items()}


def evaluate(history):
    counters = {arm: Counter(dict.fromkeys(METRICS, 0)) for arm in ARMS}
    transitions = Counter()
    events = defaultdict(list)
    for section, code, start, stop in history.intervals:
        events[start].append((section, code, 1))
        if stop is not None:
            events[stop].append((section, code, -1))
    days = iter(sorted(events))
    event_day = next(days, None)
    active = {section: Counter() for section in FIELDS}
    previous = None
    for at in sorted(history.visits):
        starts = set()
        while event_day is not None and event_day <= at:
            for section, code, delta in events[event_day]:
                active[section][code] += delta
                if delta == 1:
                    starts.add(section)
            event_day = next(days, None)
        view = reference(history.intervals, at)
        state = dict(view, notes=at.isoformat(), consent={"granted_purposes": ["chart_review"]})
        swept = {
            k: sorted(code for code, n in counts.items() if n > 0) for k, counts in active.items()
        }
        if any(n < 0 for counts in active.values() for n in counts.values()):
            raise ValueError("negative_interval_multiplicity")
        if previous is None:
            if swept != view:
                raise ValueError("initial_view_mismatch")
            previous = state
            continue
        changed = [k for k in FIELDS if previous[k] != view[k]]
        hint = next((k for k in FIELDS if k in starts), "notes")
        transitions["total"] += 1
        if changed:
            transitions["structured_change"] += 1
            if hint == "notes":
                transitions["change_without_new_start"] += 1
        plans = {
            "single_section": sr.refresh(state, hint),
            "snapshot_checked": plan_transition(previous, state, hint),
        }
        for arm, counts in counters.items():
            counts["attempted"] += 1
            if arm == "interval_sweep":
                observed = swept
            elif arm == "full_scan":
                observed = view
                counts["full"] += 1
                counts["rebuilt_dependencies"] += len(sr.ALL_DEPENDENCIES)
            else:
                plan = plans[arm]
                if plan.mode == sr.MODE_CLINICIAN_REVIEW:
                    counts["review"] += 1
                    continue
                counts["full" if plan.mode == sr.MODE_FULL else "partial"] += 1
                counts["rebuilt_dependencies"] += len(plan.recompute_dependencies)
                observed = {
                    k: previous[k] if dep in plan.carried_over_dependencies else view[k]
                    for k, dep in zip(
                        FIELDS, ("evidence_medication_list", "evidence_allergy_list"), strict=True
                    )
                }
            counts["delivered"] += 1
            counts["stale"] += int(observed != view)
        previous = state
    return counters, transitions


def replay(path):
    with path.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
        if digest not in ARCHIVE_PREFIX:
            raise ValueError("unexpected_synthetic_archive")
    with zipfile.ZipFile(path) as archive:
        histories, source_rows = read(archive, ARCHIVE_PREFIX[digest])
    results = {arm: Counter() for arm in ARMS}
    transitions = Counter()
    subjects = Counter()
    for history in histories.values():
        subjects["source_subjects"] += 1
        if not history.visits:
            subjects["without_encounters"] += 1
            continue
        subjects["with_encounters"] += 1
        if len(history.visits) > 1:
            subjects["with_paired_dates"] += 1
        if history.invalid_intervals:
            subjects["unscored_invalid_history"] += 1
            transitions["unscored_invalid_history"] += max(0, len(history.visits) - 1)
            continue
        counters, totals = evaluate(history)
        transitions.update(totals)
        for arm, c in counters.items():
            if c["review"] + c["delivered"] != c["attempted"] or c["attempted"] != totals["total"]:
                raise ValueError("incomplete_transition_accounting")
            results[arm].update(c)
            results[arm]["subjects_with_stale_view"] += int(c["stale"] > 0)
    # The sweep is not a six-dependency planner. Its two projection-maintenance
    # operations have no comparable rebuild count.
    for key in ("full", "partial", "rebuilt_dependencies"):
        results["interval_sweep"].pop(key)
    return dict(
        source_commit="e468b9163e04c34ad389ffa9160a3bacab22e892",
        archive_sha256=digest,
        source_rows=source_rows,
        subjects=subjects,
        transition_counts=transitions,
        results=results,
    )


if __name__ == "__main__":
    print(json.dumps(replay(Path(sys.argv[1])), indent=2, sort_keys=True))
