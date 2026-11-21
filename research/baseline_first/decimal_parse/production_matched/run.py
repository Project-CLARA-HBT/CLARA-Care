"""Alternate fresh, single-CPU DuckDB workers on pinned development days."""
import csv
import datetime
import os
import subprocess
import sys
from pathlib import Path

if sys.argv[1] == "worker":
    import duckdb
    import numpy as np
    from fractions import Fraction
    import time

    assert duckdb.__version__ == "1.4.3"
    db = duckdb.connect(config={"threads": 1})
    names = [f"m{i}" for i in range(7)]
    schema = {"date": "VARCHAR", "time": "VARCHAR", **dict.fromkeys(names, "DOUBLE")}
    sql = f"""SELECT {','.join(names)} FROM read_csv(?, columns={schema},
              auto_detect=false, delim=';', header=false, nullstr=['?', ''])"""
    data = Path(sys.argv[2]).read_bytes()
    fd = os.memfd_create("day.csv")
    assert os.write(fd, data) == len(data)
    for _ in range(2):
        start = time.perf_counter_ns()
        columns = db.execute(sql, [f"/proc/self/fd/{fd}"]).fetchnumpy()
        elapsed = time.perf_counter_ns() - start
    rows = [line.split(b";")[2:] for line in data.splitlines()]
    for index, name in enumerate(names):
        values = [r[index] for r in rows]
        missing = np.array([v in (b"?", b"") for v in values])
        col = columns[name]
        assert np.array_equal(np.ma.getmaskarray(col), missing)
        expected = np.array([float(Fraction(v.decode())) for v in values if v not in (b"?", b"")])
        assert np.array_equal(np.asarray(col)[~missing].view("u8"), expected.view("u8"))
    print(elapsed)
else:
    days, objects, wheel = map(Path, sys.argv[1:])
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    writer = csv.writer(sys.stdout)
    writer.writerow(["day", "round", "first", "base_ns", "fast_ns"])
    for offset in range(14):
        day = datetime.date(2006, 12, 16) + datetime.timedelta(days=offset)
        for repeat in range(4):
            order = ("base", "fast") if (offset + repeat) % 2 == 0 else ("fast", "base")
            times = {}
            for mode in order:
                preload = f"{objects.resolve()}/{mode}.so:{wheel.resolve()}"
                times[mode] = int(subprocess.check_output(
                    [sys.executable, __file__, "worker", days / f"{day}.csv"],
                    env={**os.environ, "LD_PRELOAD": preload, "PYTHONPATH": str(wheel.resolve().parent)},
                ))
            writer.writerow([day, repeat, order[0], times["base"], times["fast"]])
            sys.stdout.flush()
