import hashlib
import os
import re
import struct
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

root = Path(__file__).resolve().parent
binary, days, co2 = map(Path, sys.argv[1:])
os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
cases = []
for line in (root.parent / "production_matched/days.sha256").read_text().splitlines():
    digest, name = line.split()
    cases.append(("uci", days / name, digest))
cases.append(("co2", co2, "16695fa2786e53414e5a6b54767a3fdf5de99cfbc68617f69d1362d92776a92f"))
numeric = re.compile(rb"-?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")

def verify(dataset, path, prefix):
    rows = path.read_bytes().splitlines()
    if dataset == "co2":
        assert rows.pop(0) == b"date,co2"
    delim, skip = (b",", 1) if dataset == "co2" else (b";", 2)
    cols = list(zip(*(row.split(delim)[skip:] for row in rows), strict=True))
    assert len(cols) == (1 if dataset == "co2" else 7)
    expected = bytearray()
    for col in cols:
        for field in col:
            if field in (b"", b"?"):
                expected.extend(struct.pack("=Q", 0x7ff8000000000001))
            elif numeric.fullmatch(field):
                value = float(Fraction(field.decode()))
                if value == 0 and field.startswith(b"-"):
                    value = -0.0
                expected.extend(struct.pack("=d", value))
            else:
                expected.extend(struct.pack("=Q", 0x7ff8000000000002))
        expected.extend(field in (b"", b"?") for field in col)
    subprocess.run([binary, "check", dataset, path, prefix], check=True)
    for arm in ["adaptive", "current", "static", "general"] + (["record"] if dataset == "co2" else []):
        assert Path(str(prefix) + arm).read_bytes() == expected, (arm, path)

with tempfile.TemporaryDirectory() as tmp:
    prefix = Path(tmp) / "out"
    verify("uci", root.parent / "fused/matched/edge.csv", prefix)
    fixture = Path(tmp) / "edge.csv"
    fixture.write_bytes(b"date,co2\nd,?\nd,1.x\nd,123.4\r\nd,5.678\nd,-0.0\nd,12.3junk\nd,9.1\n")
    verify("co2", fixture, prefix)
    for dataset, path, digest in cases:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
        verify(dataset, path, prefix)
    print("batch,round,position,arm,ns_per_8")
    for dataset, path, _ in cases:
        lines = subprocess.check_output([binary, "time", dataset, path, prefix], text=True)
        for line in lines.splitlines():
            print(f"{path.stem},{line}")
