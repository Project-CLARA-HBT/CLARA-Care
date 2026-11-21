"""Pin and de-identify a single SGD training shard for the PoPETs development replay."""

import json
from hashlib import sha256
from pathlib import Path

from evaluation.venue2027.popets.dispatch_fixture import History, Request, Source

UPSTREAM = "e852981ae34990f4358979625854259302feaa78"
TRAIN_SHA256 = "5ce28a6e656bc88c1da29c983d243d5a81eb37de92698da3864d1cf02894ca24"


def extract(path: Path) -> list:
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != TRAIN_SHA256:
        raise ValueError("Expected the pinned SGD training shard")
    result = []
    for dialogue in json.loads(raw):
        scopes: dict = {}
        versions: dict = {}
        turns = []
        for turn in dialogue["turns"]:
            if turn["speaker"] != "USER":
                continue
            fields = []
            for frame in turn["frames"]:
                for slot, values in sorted(frame["state"]["slot_values"].items()):
                    scope = scopes.setdefault((frame["service"], slot), len(scopes))
                    version = versions.setdefault((scope, tuple(values)), len(versions))
                    fields.append([scope, version])
            turns.append(fields)
        result.append(turns)
    return result


def histories(shape: list) -> list[History]:
    result = []
    for idx, turns in enumerate(shape):
        subject = f"d{idx}"
        midpoint = len(turns) // 2
        revoked = next((slot for turn in turns[:midpoint] for slot, _ in turn), None)
        sources: list[Source] = []
        requests = []
        for visit, fields in enumerate(turns):
            for slot, version in fields:
                purpose = f"s{slot}"
                if version == len(sources):
                    marker = sha256(f"{subject}/{version}".encode()).hexdigest()[:32]
                    retired = midpoint if slot == revoked else None
                    sources.append(Source(visit, purpose, marker, retired))
                if not 0 <= version < len(sources) or sources[version].purpose != purpose:
                    raise ValueError("Invalid version in workload")
                key = f"{subject}.{len(requests)}"
                requests.append(Request(key, version, purpose, visit, "state"))
        result.append(History(subject, "sgd-train", "local", tuple(sources), tuple(requests)))
    return result
