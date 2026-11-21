import hashlib
import os
import struct
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

root = Path(__file__).resolve().parent
binary, days = map(Path, sys.argv[1:])
os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
print("day,round,position,arm,ns_per_16")
with tempfile.TemporaryDirectory() as tmp:
    prefix = Path(tmp) / "out"
    for entry in [None, *(root.parent / "production_matched/days.sha256").read_text().splitlines()]:
        path = root.parent / "fused/matched/edge.csv"
        if entry:
            digest, name = entry.split()
            path = days / name
            assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
        rows = [row.split(b";")[2:] for row in path.read_bytes().splitlines()]
        expected = bytearray()
        for col in zip(*rows, strict=True):
            for field in col:
                if field in (b"", b"?"):
                    word = 0x7ff8000000000001
                elif field in (b"1.a00", b"1x000", b"1.000junk", b"+3.1"):
                    word = 0x7ff8000000000002
                else:
                    number = float(Fraction(field.decode()))
                    if number == 0 and field.startswith(b"-"):
                        number = -0.0
                    word, = struct.unpack("=Q", struct.pack("=d", number))
                expected.extend(struct.pack("=Q", word))
            expected.extend(field in (b"", b"?") for field in col)
        result = subprocess.check_output([binary, path, prefix], text=True)
        for arm in (0, 1):
            assert Path(f"{prefix}{arm}").read_bytes() == expected, path
        if entry:
            for line in result.splitlines():
                print(f"{path.stem},{line}")
