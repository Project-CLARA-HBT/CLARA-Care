"""Development dispatch schedule v1. Build only the registered synthetic development indices.

Each visit provides two source attributes with separate purpose grants. Each post-window
request selects one visit/attribute. Known ancestry is required for this scoped comparison.
"""

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

DEV_CASES = (
    Path(__file__).resolve().parents[3]
    / "research/venue2027/proof/artifacts/popets_pilot_cases.jsonl"
)
DEV_CASES_SHA256 = "e0e955a3ea8031fc544fc5162d05d69124f72055e4fe84d292597394fe92a73e"


@dataclass(frozen=True)
class Source:
    visit: int
    purpose: str
    value: str
    retired: int | None


@dataclass(frozen=True)
class Request:
    id: str
    source: int
    purpose: str
    time: int
    path: str


@dataclass(frozen=True)
class History:
    subject: str
    family: str
    tenant: str
    sources: tuple[Source, ...]
    requests: tuple[Request, ...]


def schedule() -> tuple[list[History], list[str]]:
    histories = []
    excluded = []
    raw = DEV_CASES.read_bytes()
    if sha256(raw).hexdigest() != DEV_CASES_SHA256:
        raise ValueError("DEV_INPUT_DRIFT")
    for line in raw.splitlines():
        record = json.loads(line)
        uid, family, p = record["case_id"], record["family"], record["payload"]
        if record["split"] != "dev" or p["synthetic_only"] is not True:
            raise ValueError("INVALID_DEVELOPMENT_INPUT")
        if family == "transitive_gap":
            excluded.append(uid)
            continue
        tenant = f"tenant-{int(uid.rsplit('-', 1)[1]) % 3}"
        sources: list[Source] = []
        requests = []
        for visit in range(p["subject_history_length"]):
            first = len(sources)
            for purpose in (p["purpose"], "independent-purpose"):
                token = sha256(f"{tenant}/{uid}/{visit}/{purpose}".encode()).hexdigest()[:32]
                retired = None
                if purpose == p["purpose"] and family == "revoked_then_dispatch":
                    retired = p["revocation_at"]
                sources.append(Source(visit, purpose, token, retired))
            prefix = f"{uid}.{visit}."
            requests.append(Request(prefix + "warm", first, p["purpose"], visit, "prompt"))
            asked = p["requested_purpose"] if family == "cross_purpose" else p["purpose"]
            for offset, path in enumerate(("summary", "retry", "fallback", "retained")):
                idx = first + int(path == "retained")
                use = sources[idx].purpose if path == "retained" else asked
                at = p["dispatch_at"] + 4 * visit + offset
                requests.append(Request(prefix + path, idx, use, at, path))
        histories.append(
            History(
                uid, family, tenant, tuple(sources), tuple(sorted(requests, key=lambda r: r.time))
            )
        )
    return histories, excluded
