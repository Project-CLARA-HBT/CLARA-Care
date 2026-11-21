"""Inventory recurrence oracles and compare authoritative compiled Beirut rules."""

import argparse
import hashlib
import io
import json
import re
import subprocess
import tarfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import urlopen
from zoneinfo import ZoneInfo

LIB = "https://raw.githubusercontent.com/libical/libical/bb88226d94ab6d173c5e06fd1e548ad38e8414a6/"
ICAL = "https://raw.githubusercontent.com/ical4j/ical4j/4dac4d913706b41fa633449e8a95f7d3a0b410a2/"
SOURCES = {
    "gold": LIB + "src/test/icalrecur_test.txt",
    "events": LIB + "test-data/recur.txt",
    "overlap": ICAL + "src/test/groovy/net/fortuna/ical4j/model/RecurDstOverlapSpec.groovy",
    "rfc5545": "https://www.rfc-editor.org/rfc/rfc5545.txt",
    **{
        v: f"https://data.iana.org/time-zones/releases/tzdata{v}.tar.gz" for v in ("2023b", "2023c")
    },
}


def pull(cache):
    cache.mkdir(parents=True, exist_ok=True)
    for name, url in SOURCES.items():
        target = cache / name
        if not target.exists():
            with urlopen(url, timeout=30) as response:
                target.write_bytes(response.read())
    return {name: (cache / name).read_bytes() for name in SOURCES}


def zone(blob, target):
    target.mkdir()
    with tarfile.open(fileobj=io.BytesIO(blob)) as tar:
        (target / "asia").write_bytes(tar.extractfile("asia").read())
    subprocess.run(["zic", "-d", str(target), str(target / "asia")], check=True)
    with (target / "Asia/Beirut").open("rb") as f:
        return ZoneInfo.from_file(f)


def offset_ranges(old, new):
    cursor = datetime(2023, 1, 1, tzinfo=UTC)
    end = cursor.replace(year=2024)
    intervals = []
    while cursor < end:
        pair = [int(cursor.astimezone(z).utcoffset().total_seconds() // 60) for z in (old, new)]
        if pair[0] != pair[1]:
            if (
                not intervals
                or intervals[-1]["end_utc"] != cursor.isoformat()
                or intervals[-1]["offset_min"] != pair
            ):
                intervals.append({"start_utc": cursor.isoformat(), "offset_min": pair, "hours": 0})
            intervals[-1]["end_utc"] = (cursor + timedelta(hours=1)).isoformat()
            intervals[-1]["hours"] += 1
        cursor += timedelta(hours=1)
    return intervals


def inventory(raw):
    gold, events, overlap, standard = (
        raw[k].decode() for k in ("gold", "events", "overlap", "rfc5545")
    )
    events = re.sub(r"\r?\n[ \t]", "", events)
    section = standard.split("\n3.8.5.3.  Recurrence Rule\n")[1].split("\n3.8.6.")[0]
    def tzids(s):
        return sorted(set(re.findall(r"TZID=([\w/+_-]+)", s)))
    return {
        "libical_gold": {
            "rules": len(re.findall("^RRULE:", gold, re.M)),
            "instance_lists": len(re.findall("^INSTANCES:", gold, re.M)),
            "tzids": tzids(gold),
        },
        "libical_events": {
            "vevents": events.count("BEGIN:VEVENT"),
            "count_labels": events.count("X-EXPECT-NUMEVENTS:"),
            "tzids": tzids(events),
        },
        "ical4j_overlap": {"zones": sorted(set(re.findall(r"ZoneId\.of\('([^']+)'\)", overlap)))},
        "rfc5545_section": {"tzids": tzids(section)},
        "2023b_or_c_named_in_fixtures": any(
            re.search(r"2023[bc]", t) for t in (gold, events, overlap, section)
        ),
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("cache", type=Path)
    data = pull(p.parse_args().cache)
    with TemporaryDirectory() as scratch:
        old, new = [zone(data[v], Path(scratch) / v) for v in ("2023b", "2023c")]
        print(
            json.dumps(
                dict(
                    sources={
                        k: {"url": url, "sha256": hashlib.sha256(data[k]).hexdigest()}
                        for k, url in SOURCES.items()
                    },
                    beirut=offset_ranges(old, new),
                    fixtures=inventory(data),
                ),
                indent=2,
            )
        )
