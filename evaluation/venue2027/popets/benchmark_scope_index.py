"""Development microbenchmark comparing the candidate with its pinned pre-index revision.

Run as a module from the repository root. Only source and synthetic labels enter
the benchmark. Timed sections exclude result hashing. Every operation's result
is checked against the previous revision before a paired timing is reported.
"""

import hashlib
import json
import platform
import random
import statistics
import subprocess
import sys
import tempfile
from importlib import util
from pathlib import Path
from time import perf_counter_ns

from evaluation.venue2027.popets import candidate

BASE = "2c026ade"
MODULE = "evaluation/venue2027/popets/candidate.py"


def trial(module, size, seed):
    cache = module.RevocationCompleteCache()
    order = list(range(size))
    random.Random(seed).shuffle(order)
    start = perf_counter_ns()
    for i in order:
        cache.put(f"p{i}", "payload", [(str(i), "care", 1)])
        cache.put(f"d{i}", "derived", [(str(i), "analysis", 1)], [f"p{i}"])
    built = perf_counter_ns()
    receipts = [cache.revoke(str(i), "care", 1) for i in order[:32]]
    revoked = perf_counter_ns()
    reads = [cache.get(f"d{i}", "analysis", 1).to_dict() for i in order]
    digest = hashlib.sha256(json.dumps([receipts, reads], sort_keys=True).encode()).hexdigest()
    return {"build_ms": (built - start) / 1e6, "revoke_ms": (revoked - built) / 1e6}, digest


def benchmark(old):
    results = []
    for size in (128, 1024):
        ratios = []
        trials = []
        for seed in range(6):
            timings = {}
            digests = []
            arms = [("old", old), ("indexed", candidate)]
            for name, module in reversed(arms) if seed % 2 else arms:
                timings[name], digest = trial(module, size, seed)
                digests.append(digest)
            if len(set(digests)) != 1:
                raise RuntimeError("observable_outputs_differ")
            ratios.append(timings["old"]["revoke_ms"] / timings["indexed"]["revoke_ms"])
            trials.append({"seed": seed, "times": timings, "receipt_read_digest": digests[0]})
        results.append(
            {
                "subjects": size,
                "median_paired_revoke_speedup": statistics.median(ratios),
                "trials": trials,
            }
        )
    return results


def main():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "original.py"
        path.write_bytes(subprocess.check_output(["git", "show", f"{BASE}:{MODULE}"]))
        spec = util.spec_from_file_location("original_popets_candidate", path)
        if spec is None or spec.loader is None:
            raise RuntimeError("baseline_module_unavailable")
        old = util.module_from_spec(spec)
        sys.modules[spec.name] = old
        spec.loader.exec_module(old)
        print(
            json.dumps(
                {
                    "scope": "development_in_process_microbenchmark",
                    "baseline_commit": subprocess.check_output(
                        ["git", "rev-parse", BASE], text=True
                    ).strip(),
                    "indexed_module_sha256": hashlib.sha256(
                        Path(candidate.__file__).read_bytes()
                    ).hexdigest(),
                    "python": platform.python_version(),
                    "machine": platform.machine(),
                    "revocations_per_trial": 32,
                    "results": benchmark(old),
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
