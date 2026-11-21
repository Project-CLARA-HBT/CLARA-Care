"""Extract complete measurement rows for the first fourteen source dates."""
import argparse
import zipfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("archive", type=Path)
parser.add_argument("dest", type=Path)
args = parser.parse_args()
args.dest.mkdir(exist_ok=True, parents=True)
with zipfile.ZipFile(args.archive) as archive, archive.open("household_power_consumption.txt") as source:
    header = next(source).rstrip(b"\r\n").split(b";")
    assert len(header) == 9 and header[:2] == [b"Date", b"Time"]
    days = {}
    for line in source:
        date = line.split(b";", 1)[0]
        if date not in days:
            if len(days) == 14:
                break
            days[date] = []
        days[date].append(line)
    assert len(days) == 14
    for date, rows in days.items():
        day, month, year = date.decode("ascii").split("/")
        (args.dest / f"{year}-{int(month):02}-{int(day):02}.csv").write_bytes(b"".join(rows))
