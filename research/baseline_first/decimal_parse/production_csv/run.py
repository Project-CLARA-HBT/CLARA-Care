"""Run with DuckDB 1.4.3 and NumPy on the prepared development days."""
import csv
import datetime
import os
import statistics
import sys
import time
from fractions import Fraction
from pathlib import Path

import duckdb
import numpy as np

assert duckdb.__version__ == "1.4.3"
os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
db = duckdb.connect(config={"threads": 1})
names = [f"m{i}" for i in range(7)]
schema = {"date": "VARCHAR", "time": "VARCHAR", **dict.fromkeys(names, "DOUBLE")}
sql = f"""SELECT {','.join(names)} FROM read_csv(?, columns={schema},
          auto_detect=false, delim=';', header=false, nullstr=['?', ''])"""
out = csv.writer(sys.stdout)
out.writerow(["day", "rows", "nulls", "median_us", *[f"us_{i}" for i in range(10)]])
for offset in range(14):
    day = datetime.date(2006, 12, 16) + datetime.timedelta(days=offset)
    data = (Path(sys.argv[1]) / f"{day}.csv").read_bytes()
    fd = os.memfd_create("day.csv")
    os.write(fd, data)
    path = f"/proc/self/fd/{fd}"
    fields = [line.split(b";")[2:] for line in data.splitlines()]
    times = []
    for i in range(11):
        start = time.perf_counter_ns()
        columns = db.execute(sql, [path]).fetchnumpy()
        elapsed = (time.perf_counter_ns() - start) / 1000
        if i:
            times.append(elapsed)
    nulls = 0
    for index, name in enumerate(names):
        col = columns[name]
        missing = np.array([row[index] in (b"?", b"") for row in fields])
        assert col.dtype == np.float64
        assert np.array_equal(np.ma.getmaskarray(col), missing)
        expected = np.array([float(Fraction(row[index].decode())) for row in fields if row[index] not in (b"?", b"")])
        assert np.array_equal(np.asarray(col)[~missing].view("u8"), expected.view("u8"))
        nulls += int(missing.sum())
    out.writerow([day, len(fields), nulls, statistics.median(times), *times])
    os.close(fd)
