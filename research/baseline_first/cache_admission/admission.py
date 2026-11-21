"""Run the fixed online admission probe and its matched ablation."""
import json
import sys
import zlib
from collections import Counter, OrderedDict
from pathlib import Path

import libcachesim as sim

from replay import load_prefix


def probe(requests, names, capacity):
    history = OrderedDict()
    groups = [0.5] * 256
    mean_reuse = 0.5
    misses = Counter()
    namespace = sim.Sieve(capacity, hashpower=16)
    recent_only = sim.Sieve(capacity, hashpower=16)
    arms = {cls.__name__: cls(capacity, hashpower=16) for cls in (sim.LFU, sim.WTinyLFU)}
    req = sim.Request(obj_size=1)
    for index, key in requests:
        req.obj_id = key
        recent = key in history
        bucket = names[key]
        hits = {name: arm.get(req) for name, arm in arms.items()}
        for name, cache, admit in (
            ("recent_only", recent_only, recent),
            ("namespace", namespace, recent or groups[bucket] > mean_reuse),
        ):
            if admit:
                hits[name] = cache.get(req)
            else:
                hits[name] = cache.find(req, update_cache=True) is not None
        if index >= 20_000:
            misses.update(name for name, hit in hits.items() if not hit)
        groups[bucket] += (recent - groups[bucket]) / 256
        mean_reuse += (recent - mean_reuse) / 256
        history[key] = None
        history.move_to_end(key)
        if len(history) > 4 * capacity:
            history.popitem(last=False)
    return dict(misses)


def main():
    output = {}
    for cluster in ("cluster17", "cluster52"):
        names = {}
        requests, _ = load_prefix(Path(sys.argv[1]) / f"{cluster}.zst", names)
        buckets = {key: zlib.crc32(name) % 256 for key, name in names.items()}
        output[cluster] = {
            cap: probe(requests, buckets, cap) for cap in (256, 1024, 4096)
        }
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
