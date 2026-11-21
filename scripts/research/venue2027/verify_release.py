"""Offline release integrity gate for shared harness v1 descriptive counts.

Run from the repository root with
`python3 -m scripts.research.venue2027.verify_release MANIFEST TRUSTED_SHA256`.
Take the digest from an independent publication or signed task report. A new
digest generated from the package being audited cannot authenticate its origin.
The directory containing the manifest is the root for all input paths.

The release manifest supplies checksum-pinned freeze, plan, raw RunBundle
JSONL, analysis JSON, figure SVG and claim ledger CSV files. The freeze must
cover the campaign plan, including its arm/case identities, seed, source SHA,
analysis identifier and complete claim list. Missing or unverifiable evidence
returns a failed GateReport and an empty verified claim count.

The built-in harness-counts.v1 analysis counts one row per arm and case.
Attempted excludes recorded unavailable arms. Completed includes both admit
and reject. Error includes timeout, execution error and invalid result.
Indeterminate and unavailable outcomes remain visible. Every scheduled pair
requires an explicit row. This version supports exact operational counts.
A new endpoint needs a reviewed replay implementation before it can pass.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from evaluation.venue2027._shared.harness import (
    COUNTABLE_OUTCOMES,
    HARNESS_VERSION,
    OUTCOME_BUCKETS,
    Campaign,
    HarnessError,
    _pair_digest,
)
from scripts.research.venue2027.freeze_protocol import (
    FREEZE_PROTOCOL_SCHEMA_VERSION,
    FreezeEntry,
    FreezeManifest,
    verify_freeze,
)

ROLES = ("freeze", "plan", "raw", "analysis", "figure", "ledger")
BUCKETS = tuple(bucket.lower() for bucket in OUTCOME_BUCKETS)
CLAIM_FIELDS = ("claim_id", "arm_id", "metric")
SHA256 = re.compile(r"[a-f0-9]{64}")


@dataclass(frozen=True)
class GateReport:
    ok: bool
    reason_code: str
    denominators: dict[str, dict[str, int]] = field(default_factory=dict)
    claims_verified: int = 0


class GateFailure(ValueError):
    """Stable reason code and any recoverable descriptive denominators."""

    def __init__(self, code: str, counts: dict[str, dict[str, int]] | None = None):
        super().__init__(code)
        self.counts = counts or {}


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise GateFailure(reason)


def encoded(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _object(pairs: list[tuple[str, Any]]) -> dict:
    obj = dict(pairs)
    require(len(obj) == len(pairs), "INVALID_JSON")
    return obj


def _constant(_name: str) -> None:
    raise GateFailure("INVALID_JSON")


def decode(data: bytes) -> Any:
    return json.loads(data.decode("utf-8"), object_pairs_hook=_object, parse_constant=_constant)


def confined(root: Path, name: str) -> Path:
    require(isinstance(name, str) and bool(name), "PATH_INVALID")
    rel = Path(name)
    require(not rel.is_absolute() and ".." not in rel.parts and str(rel) == name, "PATH_INVALID")
    resolved = (root / rel).resolve()
    require(resolved.is_relative_to(root) and resolved.is_file(), "PATH_INVALID")
    return resolved


def _frozen_at(frozen: dict, root: Path, plan: str, campaign: Campaign) -> float:
    entries = tuple(FreezeEntry(**entry) for entry in frozen["entries"])
    paths = [entry.path for entry in entries]
    require(plan in paths and len(set(paths)) == len(paths), "FREEZE_DRIFT")
    require(
        frozen["schema_version"] == FREEZE_PROTOCOL_SCHEMA_VERSION
        and frozen["ok"] is True
        and frozen["reason_code"] == "OK"
        and frozen["study_id"] == campaign.campaign_id
        and frozen["stage"] in {"development", "pre-holdout"},
        "FREEZE_DRIFT",
    )
    manifest = FreezeManifest(**{**frozen, "entries": entries})
    stamps = []
    for entry in entries:
        target = confined(root, entry.path)
        require(target.stat().st_size == entry.size_bytes, "FREEZE_DRIFT")
        stamp = datetime.fromisoformat(entry.timestamp_utc)
        require(stamp.tzinfo is not None, "FREEZE_CHRONOLOGY")
        stamps.append(stamp.timestamp())
    require(verify_freeze(manifest, root).ok, "FREEZE_DRIFT")
    # V1 cannot replay a changed protocol without an explicit amended plan.
    require(frozen["amendments"] == [], "AMENDMENT_REPLAY_UNSUPPORTED")
    return max(stamps)


def _denominators(
    rows: list[dict], campaign: Campaign, frozen_at: float
) -> dict[str, dict[str, int]]:
    require(bool(rows) and isinstance(rows[-1], dict), "RAW_INVALID")
    trailer = rows.pop()
    requested = set(campaign.planned_pairs)
    seen: set[tuple[str, str]] = set()
    counts: dict[str, Counter] = {arm: Counter() for arm in campaign.arm_ids}
    binding = dict(
        campaign_id=campaign.campaign_id,
        source_commit=campaign.source_commit,
        harness_version=HARNESS_VERSION,
        seed=campaign.seed,
    )
    operation_ids: set[str] = set()
    for record in rows:
        require(
            isinstance(record, dict) and record.get("record_kind") == "pair_result", "PAIR_INVALID"
        )
        require(
            all(encoded(record.get(k)) == encoded(v) for k, v in binding.items()), "PAIR_INVALID"
        )
        arm, case = record["arm_id"], record["case_id"]
        require((arm, case) in requested and (arm, case) not in seen, "PAIR_INVALID")
        require(record["pair_digest"] == _pair_digest(record), "PAIR_INVALID")
        require(record["logical_op_id"] == f"{campaign.campaign_id}:{arm}::{case}", "PAIR_INVALID")
        require(record["logical_op_id"] not in operation_ids, "PAIR_INVALID")
        operation_ids.add(record["logical_op_id"])
        require(isinstance(record.get("oracle"), dict) and bool(record["oracle"]), "PAIR_INVALID")
        require(
            isinstance(record.get("python_version"), str)
            and record["python_version"] == trailer.get("python_version"),
            "PAIR_INVALID",
        )
        duration = record.get("duration_seconds")
        require(
            type(duration) in (int, float) and math.isfinite(duration) and duration >= 0,
            "PAIR_INVALID",
        )
        stamp = record["recorded_at"]
        require(
            type(stamp) in (int, float) and math.isfinite(stamp) and stamp >= frozen_at,
            "FREEZE_CHRONOLOGY",
        )
        outcome = record["outcome"]["observed_outcome"]
        success = record["outcome"]["counted_as_success"]
        require(
            outcome in OUTCOME_BUCKETS
            and type(success) is bool
            and (not success or outcome in COUNTABLE_OUTCOMES),
            "PAIR_INVALID",
        )
        seen.add((arm, case))
        counts[arm][outcome.lower()] += 1
    result = {}
    for arm, buckets in counts.items():
        planned = len(campaign.case_ids)
        recorded = buckets.total()
        result[arm] = dict(
            planned=planned,
            recorded=recorded,
            attempted=recorded - buckets["not_run_external"],
            completed=buckets["admit"] + buckets["reject"],
            error=buckets["execution_error"] + buckets["invalid_result"] + buckets["timeout"],
            missing=planned - recorded,
            **{key: buckets[key] for key in BUCKETS},
        )
    if requested != seen:
        raise GateFailure("DENOMINATOR_MISMATCH", result)
    total = sum(counts.values(), Counter())
    expected = dict(
        **binding,
        record_kind="run_manifest",
        complete=True,
        denominator_total=len(seen),
        arm_ids=list(campaign.arm_ids),
        case_ids=list(campaign.case_ids),
        planned_pairs=len(requested),
        attempted_pairs=len(seen),
        missing_pairs=0,
        denominator={key: total[key] for key in BUCKETS},
    )
    require(
        all(encoded(trailer.get(k)) == encoded(v) for k, v in expected.items()),
        "DENOMINATOR_MISMATCH",
    )
    # execute() appends these three operational fields after hashing its trailer.
    hashed = {
        k: v
        for k, v in trailer.items()
        if k not in {"manifest_digest", "resumed_pairs", "executed_pairs", "journal_path"}
    }
    require(
        trailer["manifest_digest"] == hashlib.sha256(encoded(hashed)).hexdigest(), "TRAILER_INVALID"
    )
    operations = [trailer[k] for k in ("resumed_pairs", "executed_pairs")]
    require(
        all(type(n) is int and n >= 0 for n in operations) and sum(operations) == len(seen),
        "TRAILER_INVALID",
    )

    return result


def render_figure(counts: dict[str, dict[str, int]]) -> bytes:
    """Render per-arm outcome bars as deterministic SVG from raw-derived counts."""
    width = 640
    rows = [(arm, bucket, counts[arm][bucket]) for arm in sorted(counts) for bucket in BUCKETS]
    maximum = max(1, max(n for _, _, n in rows))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{34 + 20 * len(rows)}">',
        "<title>Recorded outcomes by arm</title>",
        '<text x="4" y="16">Recorded outcomes by arm</text>',
    ]
    for index, (arm, bucket, n) in enumerate(rows):
        y = 36 + index * 20
        parts.extend(
            [
                f'<text x="4" y="{y}">{escape(arm)} / {bucket}</text>',
                f'<rect x="310" y="{y - 12}" width="{260 * n / maximum:.2f}" height="12" fill="#30689a"/>',
                f'<text x="580" y="{y}">{n}</text>',
            ]
        )
    return ("\n".join([*parts, "</svg>"]) + "\n").encode()


def _ledger(content: bytes, claims: list[dict], counts: dict[str, dict[str, int]]) -> int:
    require(isinstance(claims, list) and bool(claims), "LEDGER_MISMATCH")
    expected = {}
    for claim in claims:
        require(isinstance(claim, dict) and set(claim) == set(CLAIM_FIELDS), "LEDGER_MISMATCH")
        claim_id, arm, metric = (claim[k] for k in CLAIM_FIELDS)
        require(
            isinstance(claim_id, str)
            and bool(claim_id.strip())
            and claim_id not in expected
            and arm in counts
            and metric in counts[arm],
            "LEDGER_MISMATCH",
        )
        expected[claim_id] = {**claim, "value": str(counts[arm][metric])}
    reader = csv.DictReader(io.StringIO(content.decode(), newline=""), strict=True)
    require(reader.fieldnames == [*CLAIM_FIELDS, "value"], "LEDGER_MISMATCH")
    remaining = dict(expected)
    for row in reader:
        require(row == remaining.pop(row.get("claim_id"), None), "LEDGER_MISMATCH")
    require(not remaining, "LEDGER_MISMATCH")
    return len(expected)


def verify(manifest: Path | str, expected_sha256: str) -> GateReport:
    """Replay a digest-pinned local release. On any failure certify zero claims."""
    try:
        path = Path(manifest)
        root = path.parent.resolve()
        raw_manifest = path.read_bytes()
        require(
            SHA256.fullmatch(expected_sha256) is not None
            and hashlib.sha256(raw_manifest).hexdigest() == expected_sha256,
            "MANIFEST_DIGEST_MISMATCH",
        )
        release = decode(raw_manifest)
        require(
            isinstance(release, dict)
            and set(release) == {*ROLES, "schema_version", "sha256"}
            and release["schema_version"] == "harness-release.v1",
            "MANIFEST_INVALID",
        )
        files = {}
        paths = [release[role] for role in ROLES]
        require(
            len(set(paths)) == len(paths) and set(paths) == set(release["sha256"]),
            "MANIFEST_INVALID",
        )
        for role, name in zip(ROLES, paths, strict=True):
            files[role] = confined(root, name).read_bytes()
            require(
                hashlib.sha256(files[role]).hexdigest() == release["sha256"][name],
                "CHECKSUM_MISMATCH",
            )

        plan = decode(files["plan"])
        require(
            isinstance(plan, dict) and set(plan) == {"analysis_id", "campaign", "claims"},
            "PLAN_INVALID",
        )
        require(
            isinstance(plan["campaign"], dict)
            and all(
                isinstance(plan["campaign"].get(key), list)
                for key in ("arm_ids", "case_ids", "seeds")
            ),
            "PLAN_INVALID",
        )
        campaign = Campaign(**plan["campaign"])
        campaign.validate()
        require(
            all(isinstance(x, str) and x.strip() for x in (*campaign.arm_ids, *campaign.case_ids))
            and type(campaign.seed) is int,
            "PLAN_INVALID",
        )
        require(plan["analysis_id"] == "harness-counts.v1", "ANALYSIS_UNSUPPORTED")
        frozen_at = _frozen_at(decode(files["freeze"]), root, release["plan"], campaign)
        counts = _denominators(
            [decode(line) for line in files["raw"].splitlines()], campaign, frozen_at
        )
        require(encoded(decode(files["analysis"])) == encoded(counts), "ANALYSIS_MISMATCH")
        require(files["figure"] == render_figure(counts), "FIGURE_MISMATCH")
        verified = _ledger(files["ledger"], plan["claims"], counts)
        return GateReport(True, "OK", counts, verified)
    except GateFailure as exc:
        return GateReport(False, str(exc), exc.counts)
    except HarnessError as exc:
        return GateReport(False, exc.reason_code)
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OverflowError,
        RuntimeError,
        csv.Error,
    ):
        return GateReport(False, "MALFORMED_RELEASE")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("manifest", type=Path)
    parser.add_argument("expected_sha256", help="SHA-256 from a trusted release reference")
    args = parser.parse_args()
    report = verify(args.manifest, args.expected_sha256)
    print(json.dumps(asdict(report), sort_keys=True))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
