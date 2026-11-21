"""Offline bounded serial replay. Consumes observations only; no driver or DB import."""

import gzip
import json
import sys
from collections import Counter
from itertools import permutations, product
from statistics import median


def apply(state, event):
    key = event["account"]
    savings, checking = state[key]
    kind = event["kind"]
    status = event["status"]
    reads = event["reads"]
    if status == "aborted":
        return len(event["failures"]) == 3 and not reads
    if kind == "withdraw":
        if reads != [savings]:
            return False
        if savings < 20.2:
            return status == "insufficient"
        savings -= 20.2
    elif kind == "deposit":
        if reads:
            return False
        checking += 1.3
    elif kind == "check":
        if reads != [savings, checking]:
            return False
        checking -= 5 if savings + checking >= 5 else 4
    else:
        raise ValueError(kind)
    state[key] = savings, checking
    return status == "committed"


def serial_witness(before, wave):
    events = wave["events"]
    for order in permutations(range(len(events))):
        if any(
            events[j]["end"] <= events[i]["start"]
            for pos, i in enumerate(order)
            for j in order[pos + 1 :]
        ):
            continue
        state = {k: (s, c) for k, s, c in before}
        if all(apply(state, events[i]) for i in order):
            if [[k, *state[k]] for k in sorted(state)] == wave["after"]:
                return order
    return None


def score(raw):
    results = {}
    inputs = {}
    for row in raw["rows"]:
        arm, n, size, seed = (row[k] for k in ("arm", "workers", "accounts", "seed"))
        key = (size, n, seed, arm)
        assert key not in results
        if "population" in row:
            assert row["dormant"] == row["population"] - size and row["changed_dormant"] == 0
        before = row["initial"]
        assert before == [[k, 40.4, 0.0] for k in range(size)]
        counts = Counter()
        bad = []
        stream = []
        elapsed = 0
        assert len(row["waves"]) == 60
        for i, wave in enumerate(row["waves"]):
            assert len(wave["events"]) == 4
            assert wave["elapsed_ns"] > 0
            elapsed += wave["elapsed_ns"]
            for event in wave["events"]:
                kind, acct = event["kind"], event["account"]
                assert 0 <= acct < size and event["start"] < event["end"]
                assert set(event["failures"]) <= {"40001", "40P01"}
                assert len(event["failures"]) <= (3 if event["status"] == "aborted" else 2)
                counts.update(event["failures"])
                counts[event["status"]] += 1
                stream.append((kind, acct))
            if serial_witness(before, wave) is None:
                bad.append(i)
            before = wave["after"]
        assert Counter(k for k, _ in stream) == {"check": 120, "deposit": 84, "withdraw": 36}
        assert inputs.setdefault(key[:3], stream) == stream
        results[key] = dict(counts=counts, bad_waves=bad, rate=counts["committed"] * 1e9 / elapsed)
    assert results.keys() == set(product((4, 32), (1, 4), range(6), ("ssi", "scoped_rc")))
    return results


def report(results):
    for size, n in product((4, 32), (1, 4)):
        pairs = []
        for arm in ("ssi", "scoped_rc"):
            rows = [results[size, n, i, arm] for i in range(6)]
            counts = sum((row["counts"] for row in rows), Counter())
            rates = [row["rate"] for row in rows]
            pairs.append(rates)
            print(
                size,
                n,
                arm,
                dict(counts),
                "median commits/s",
                round(median(rates), 1),
                "unwitnessed",
                [(i, r["bad_waves"]) for i, r in enumerate(rows) if r["bad_waves"]],
            )
        ratios = [rc / ssi for rc, ssi in zip(pairs[1], pairs[0], strict=True)]
        print(
            "ratios",
            *[round(r, 3) for r in ratios],
            "median",
            round(median(ratios), 3),
            "losses",
            sum(r < 1 for r in ratios),
        )


if __name__ == "__main__":
    with gzip.open(sys.argv[1], "rt") as stream:
        report(score(json.load(stream)))
