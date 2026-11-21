import json
import subprocess
import sys

import pytest

from evaluation.venue2027.popets.sgd_replay import score
from evaluation.venue2027.popets.sgd_workload import extract, histories


@pytest.mark.parametrize(("arm", "hits", "builds"), [("B1", 1, 3), ("B2", 0, 4), ("B4", 2, 2)])
def test_barrier_and_rebuild(tmp_path, arm, hits, builds):
    # At midpoint slot zero is withdrawn. Slot one survives and repeats twice.
    shape = [[[[0, 0], [1, 1]], [[0, 0], [1, 1]], [[0, 2], [1, 1]]]]
    path = tmp_path / "shape.json"
    path.write_text(json.dumps(shape))
    ops = tmp_path / "operations"
    proc = subprocess.run(
        [sys.executable, "-m", "evaluation.venue2027.popets.sgd_sender", arm, str(path), str(ops)],
        check=True,
        capture_output=True,
    )
    record = dict(
        data=proc.stdout.decode(),
        cancel=proc.stderr.decode(),
        operations=json.loads(ops.read_bytes()),
        process_wall_ns=0,
    )
    schedule = histories(shape)
    measured = score(schedule, record)
    assert measured["hits"] == hits
    assert measured["builds"] == builds
    assert measured["authorized_coverage"] == 1
    assert measured["all_forbidden_bytes"] == 0
    assert measured["cancelled"] == 2
    # Replace an authorized delivery after withdrawal with the old revoked marker.
    allowed, revoked = schedule[0].sources[1].value, schedule[0].sources[0].value
    record["data"] = record["data"].replace(f"d0.3\t{allowed}", f"d0.3\t{revoked}")
    measured = score(schedule, record)
    assert measured["post_revocation_forbidden_bytes"] == 32
    assert measured["authorized_coverage"] == 0.75


def test_pin_precedes_parse(tmp_path):
    path = tmp_path / "other"
    path.write_bytes(b"invalid json")
    with pytest.raises(ValueError, match="pinned SGD training shard"):
        extract(path)
