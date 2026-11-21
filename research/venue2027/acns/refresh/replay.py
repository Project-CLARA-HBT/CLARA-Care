"""Replay the projected experiment with the archived delta and oracle receipt."""

import argparse
from pathlib import Path

from compare import assess, digest, project, read, replay

HERE = Path(__file__).resolve().parent


def verify(old):
    expected = read(HERE / "results.json")
    new = replay(old, read(HERE / "projection_delta.json"))
    reference = {key: project(row) for key, row in new.items()}
    if digest(reference) != expected["oracle_sha256"]:
        raise ValueError("Replayed catalogue differs from archived Expat oracle")
    if assess(old, new, reference) != expected:
        raise ValueError("Refresh outcomes differ from archived results")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old", type=Path)
    args = parser.parse_args()
    verify(read(args.old))
    print("All six outcomes match the archived experiment.")
