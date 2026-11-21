"""Extract command DAG and timestamps from the two pinned CMake Ninja builds."""

import argparse
import hashlib
import json
import re
from functools import cache
from pathlib import Path


def capture(path):
    log = (path / ".ninja_log").read_bytes()
    rows = {}
    for line in log.decode().splitlines()[1:]:
        start, end, _, output, _ = line.split("\t")
        if output in rows:
            raise ValueError("expected a single clean build")
        rows[output] = (int(start), int(end))
    build = (path / "build.ninja").read_bytes()
    edges = {}
    for line in build.decode().splitlines():
        if line.startswith("build "):
            outputs, rule, inputs = re.fullmatch(r"build (.+?): (\S+)(.*)", line).groups()
            outputs = outputs.split()
            inputs = [item for item in inputs.split() if item not in ("|", "||")]
            for output in outputs:
                edges[output] = (outputs, rule, inputs)
    jobs = {}

    @cache
    def visit(output):
        if output not in edges:
            return set()
        outputs, rule, inputs = edges[output]
        parents = set().union(*(visit(name) for name in inputs))
        if rule == "phony":
            return parents
        name = outputs[0]
        stamps = {rows[key] for key in outputs}
        if len(stamps) != 1:
            raise ValueError("multi-output command inconsistency")
        start, finish = stamps.pop()
        if start >= finish:
            raise ValueError("duration below clock resolution")
        jobs[name] = dict(parents=sorted(parents), start=start, finish=finish, outputs=outputs)
        return {name}

    visit("all")
    if {k for v in jobs.values() for k in v["outputs"]} != rows.keys():
        raise ValueError("command coverage mismatch")
    for v in jobs.values():
        if any(jobs[k]["finish"] > v["start"] for k in v["parents"]):
            raise ValueError("observed precedence violation")
    return dict(
        tasks=jobs,
        log_sha256=hashlib.sha256(log).hexdigest(),
        manifest_sha256=hashlib.sha256(build).hexdigest(),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build_dir", type=Path)
    args = parser.parse_args()
    print(json.dumps(capture(args.build_dir), indent=2, sort_keys=True))
