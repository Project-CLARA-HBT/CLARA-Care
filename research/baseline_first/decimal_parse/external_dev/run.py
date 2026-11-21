import hashlib
import os
import struct
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

binary, csv = map(Path, sys.argv[1:])
raw = csv.read_bytes()
assert hashlib.sha256(raw).hexdigest() == "16695fa2786e53414e5a6b54767a3fdf5de99cfbc68617f69d1362d92776a92f"
header, *rows = raw.splitlines()
assert header == b"date,co2"
values = bytearray()
mask = bytearray()
for row in rows:
    date, field = row.split(b",")
    assert len(date) == 8 and date.isdigit()
    values.extend(struct.pack("=d", float(Fraction(field.decode()))) if field else
                  struct.pack("=Q", 0x7ff8000000000001))
    mask.append(not field)
os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
with tempfile.TemporaryDirectory() as tmp:
    prefix = Path(tmp) / "out"
    subprocess.run([binary, "check", csv, prefix], check=True)
    for i in range(4):
        assert Path(f"{prefix}{i}").read_bytes() == values + mask
    subprocess.run([binary, "time", csv, prefix], check=True)
