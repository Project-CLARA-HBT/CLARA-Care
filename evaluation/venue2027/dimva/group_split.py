"""DIMVA venue2027 strict independent cross-domain holdout splitter (task DIMVA-X08_splitter, phase P02).

Purpose
-------
Deterministic group-aware train/dev/test partitioner for the DIMVA 2027
"GovernanceTrace" study (``research/venue2027/VENUES/dimva/RESEARCH_BLUEPRINT.md``,
RQ2). The independent unit of inference is one *campaign group* (a multi-stage
agent-probing campaign / benign session), never an individual event, per
``research/venue2027/GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md`` section 3
(repeated calls within one history are clustered, not independent).

``split(groups, seed)`` assigns whole campaign groups to ``train`` / ``dev`` /
``test`` so that **no identity bridge leaks across splits**: any two groups
sharing an attacker family, a tenant, a tooling template (canonical form) or a
source lineage are merged into one leakage component and land in the same
split. This is the cross-family/cross-tenant holdout discipline: an
unseen-family or unseen-tenant test split cannot be bridged by shared
infrastructure, shared tooling or shared provenance. Bridges that force a
merge are *flagged* in the returned :class:`LeakageAudit` (exact overlap
report of kind, attribute and involved group ids) — they are handled by
merging, never silently dropped. A pure event-level split attempt (several
records claiming one campaign identity via a duplicate ``group_id`` or a
shared ``campaign_id``) is *refused* outright with
``EVENT_LEVEL_SPLIT_REFUSED``: events of one campaign are one unit and must
never be spread across partitions.

Determinism: the same ``(groups, seed)`` always yields byte-identical
partitions (sorted inputs, deterministic union-find, single seeded shuffle of
components). No clock, no environment reads, no hidden randomness, no network,
no live provider, no real PHI/PII — synthetic research surface only.

Allowed input
-------------
An iterable of JSON-serializable mappings, one per campaign group, with the
exact fields:

- ``group_id`` (str, required): stable identifier of the independent unit.
- ``attacker_family`` (str, required): scenario/attacker family label (e.g.
  ``low_and_slow``; ``benign_session`` is a pseudo-family).
- ``tenant`` (str, required): synthetic tenant label.
- ``tooling_templates`` (list/tuple of non-empty str, required; may be empty):
  tooling template ids used by the campaign. Trivial paraphrases (case and
  separator variants) are canonicalized before bridging.
- ``source_lineage`` (str, required): synthetic provenance/lineage label.
- ``campaign_id`` (str, optional): parent campaign identity; defaults to
  ``group_id``. Two different ``group_id`` values sharing one ``campaign_id``
  signal event-level fragmentation and are refused.

Unknown fields fail closed (no reason-code or attacker-label side channels).
``ratios`` optionally overrides the default 0.6/0.2/0.2 split proportions.

Failure semantics
-----------------
Every refusal is a :class:`GroupingError` carrying a stable uppercase
``reason_code``: ``EMPTY_GROUPS``, ``MISSING_GROUP_FIELD``,
``UNKNOWN_GROUP_FIELD``, ``INVALID_GROUP_FIELD``, ``INVALID_SEED``,
``INVALID_SPLIT_RATIOS``, ``EVENT_LEVEL_SPLIT_REFUSED``,
``DEGENERATE_COMPONENT_COUNT`` (identity bridges collapse all groups into
fewer components than splits), ``INCOMPLETE_ASSIGNMENT``,
``UNKNOWN_ASSIGNMENT_KEY``, ``INVALID_SPLIT_LABEL`` and
``BRIDGE_OVERLAP_DETECTED`` (post-hoc leak detector catch — never silently
return a leaky partition). The returned audit carries ``clean=True`` only when
the post-hoc bridge-overlap report is empty.

Version
-------
``GROUP_SPLIT_VERSION = "1.0.0"`` (additive-only within 1.x).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import random
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any

GROUP_SPLIT_VERSION = "1.0.0"

SPLITS: tuple[str, ...] = ("train", "dev", "test")

#: Unit of inference: one campaign group (never an event), per
#: GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md section 3.
UNIT_OF_INFERENCE = "campaign_group"

ALLOWED_GROUP_FIELDS: frozenset[str] = frozenset(
    {
        "group_id",
        "attacker_family",
        "tenant",
        "tooling_templates",
        "source_lineage",
        "campaign_id",
    }
)

REQUIRED_GROUP_FIELDS: tuple[str, ...] = (
    "group_id",
    "attacker_family",
    "tenant",
    "tooling_templates",
    "source_lineage",
)

RC_EMPTY_GROUPS = "EMPTY_GROUPS"
RC_MISSING_GROUP_FIELD = "MISSING_GROUP_FIELD"
RC_UNKNOWN_GROUP_FIELD = "UNKNOWN_GROUP_FIELD"
RC_INVALID_GROUP_FIELD = "INVALID_GROUP_FIELD"
RC_INVALID_SEED = "INVALID_SEED"
RC_INVALID_SPLIT_RATIOS = "INVALID_SPLIT_RATIOS"
RC_EVENT_LEVEL_SPLIT_REFUSED = "EVENT_LEVEL_SPLIT_REFUSED"
RC_DEGENERATE_COMPONENT_COUNT = "DEGENERATE_COMPONENT_COUNT"
RC_INCOMPLETE_ASSIGNMENT = "INCOMPLETE_ASSIGNMENT"
RC_UNKNOWN_ASSIGNMENT_KEY = "UNKNOWN_ASSIGNMENT_KEY"
RC_INVALID_SPLIT_LABEL = "INVALID_SPLIT_LABEL"
RC_BRIDGE_OVERLAP_DETECTED = "BRIDGE_OVERLAP_DETECTED"

BK_ATTACKER_FAMILY = "attacker_family"
BK_TENANT = "tenant"
BK_TOOLING_TEMPLATE = "tooling_template"
BK_TOOLING_TEMPLATE_PARAPHRASE = "tooling_template_paraphrase"
BK_SOURCE_LINEAGE = "source_lineage"


class GroupingError(ValueError):
    """Fail-closed refusal with a stable ``reason_code``."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


def canonical_template(raw: str) -> str:
    """Canonical tooling-template form: casefolded, separator-collapsed.

    Trivial paraphrases (``"Probe-Tool.01"`` vs ``"probe_tool_01"``) collapse
    to the same key and are bridged as near-duplicates; deeper paraphrase is
    declared out of scope for exact deterministic matching.
    """

    collapsed = re.sub(r"[^0-9a-z]+", "_", raw.strip().lower()).strip("_")
    return collapsed or raw.strip().lower()


@dataclasses.dataclass(frozen=True)
class SplitRatios:
    """Proportions of leakage components assigned to each split."""

    train: float = 0.6
    dev: float = 0.2
    test: float = 0.2

    def validate(self) -> None:
        values = {"train": self.train, "dev": self.dev, "test": self.test}
        for name, value in values.items():
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise GroupingError(
                    RC_INVALID_SPLIT_RATIOS, f"{name} ratio must be a number, got {value!r}"
                )
            if not 0.0 <= float(value) <= 1.0:
                raise GroupingError(
                    RC_INVALID_SPLIT_RATIOS, f"{name} ratio must be within [0, 1], got {value!r}"
                )
        total = sum(float(v) for v in values.values())
        if abs(total - 1.0) > 1e-9:
            raise GroupingError(RC_INVALID_SPLIT_RATIOS, f"ratios sum to {total!r}, expected 1.0")


@dataclasses.dataclass(frozen=True)
class LeakageFinding:
    """One identity bridge found *before* splitting (handled by merging)."""

    kind: str
    attribute: str
    group_ids: tuple[str, ...]
    raw_values: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "attribute": self.attribute,
            "group_ids": list(self.group_ids),
            "raw_values": list(self.raw_values),
        }


@dataclasses.dataclass(frozen=True)
class BridgeOverlap:
    """One identity bridge spanning multiple splits (a leak; must be empty)."""

    kind: str
    attribute: str
    splits: tuple[str, ...]
    group_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "attribute": self.attribute,
            "splits": list(self.splits),
            "group_ids": list(self.group_ids),
        }


@dataclasses.dataclass(frozen=True)
class LeakageAudit:
    """Leakage audit: pre-split bridge findings plus post-split overlap report."""

    findings: tuple[LeakageFinding, ...]
    bridge_overlap_report: tuple[BridgeOverlap, ...]
    group_count: int
    component_count: int
    unit_of_inference: str = UNIT_OF_INFERENCE

    @property
    def clean(self) -> bool:
        return not self.bridge_overlap_report

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_of_inference": self.unit_of_inference,
            "group_count": self.group_count,
            "component_count": self.component_count,
            "findings": [f.to_dict() for f in self.findings],
            "bridge_overlap_report": [o.to_dict() for o in self.bridge_overlap_report],
            "clean": self.clean,
        }


@dataclasses.dataclass(frozen=True)
class Partitions:
    """Deterministic train/dev/test partitions plus the leakage audit.

    ``train``/``dev``/``test`` hold the original group mappings sorted by
    ``group_id``; ``assignment`` maps every group id to its split label.
    Treat the mapping field as immutable.
    """

    train: tuple[Mapping[str, Any], ...]
    dev: tuple[Mapping[str, Any], ...]
    test: tuple[Mapping[str, Any], ...]
    assignment: dict[str, str]
    audit: LeakageAudit
    seed: int
    ratios: SplitRatios
    partition_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": GROUP_SPLIT_VERSION,
            "seed": self.seed,
            "ratios": {
                "train": self.ratios.train,
                "dev": self.ratios.dev,
                "test": self.ratios.test,
            },
            "train": [g["group_id"] for g in self.train],
            "dev": [g["group_id"] for g in self.dev],
            "test": [g["group_id"] for g in self.test],
            "assignment": dict(self.assignment),
            "partition_sha256": self.partition_sha256,
            "audit": self.audit.to_dict(),
        }


@dataclasses.dataclass(frozen=True)
class _Record:
    group_id: str
    attacker_family: str
    tenant: str
    templates: tuple[str, ...]
    source_lineage: str
    campaign_id: str
    payload: Mapping[str, Any]


def _require_str(value: Any, field: str, index: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GroupingError(
            RC_INVALID_GROUP_FIELD,
            f"group #{index}: field {field!r} must be a non-empty string, got {value!r}",
        )
    return value.strip()


def _materialize(groups: Iterable[Mapping[str, Any]]) -> tuple[_Record, ...]:
    """Validate and order group entries; refuse event-level fragmentation."""

    entries = list(groups)
    if not entries:
        raise GroupingError(RC_EMPTY_GROUPS, "groups must contain at least one campaign group")
    records: list[_Record] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            raise GroupingError(
                RC_INVALID_GROUP_FIELD,
                f"group #{index} must be a mapping, got {type(entry).__name__}",
            )
        unknown = sorted(str(k) for k in set(entry) - ALLOWED_GROUP_FIELDS)
        if unknown:
            raise GroupingError(
                RC_UNKNOWN_GROUP_FIELD,
                f"group #{index}: unknown field(s) {unknown}; allowed fields are "
                f"{sorted(ALLOWED_GROUP_FIELDS)}",
            )
        missing = sorted(f for f in REQUIRED_GROUP_FIELDS if f not in entry)
        if missing:
            raise GroupingError(
                RC_MISSING_GROUP_FIELD, f"group #{index}: missing required field(s) {missing}"
            )
        group_id = _require_str(entry["group_id"], "group_id", index)
        family = _require_str(entry["attacker_family"], "attacker_family", index)
        tenant = _require_str(entry["tenant"], "tenant", index)
        lineage = _require_str(entry["source_lineage"], "source_lineage", index)
        templates_raw = entry["tooling_templates"]
        if isinstance(templates_raw, str | bytes) or not isinstance(templates_raw, list | tuple):
            raise GroupingError(
                RC_INVALID_GROUP_FIELD,
                f"group #{index} ({group_id!r}): tooling_templates must be a list of strings",
            )
        templates = tuple(
            _require_str(t, f"tooling_templates[{i}]", index) for i, t in enumerate(templates_raw)
        )
        campaign_id = group_id
        if "campaign_id" in entry:
            campaign_id = _require_str(entry["campaign_id"], "campaign_id", index)
        records.append(
            _Record(
                group_id=group_id,
                attacker_family=family,
                tenant=tenant,
                templates=templates,
                source_lineage=lineage,
                campaign_id=campaign_id,
                payload=entry,
            )
        )
    records.sort(key=lambda r: r.group_id)

    duplicated = sorted(g for g, c in Counter(r.group_id for r in records).items() if c > 1)
    if duplicated:
        raise GroupingError(
            RC_EVENT_LEVEL_SPLIT_REFUSED,
            f"{len(records)} records claim group_id(s) {duplicated}; splitting is defined over "
            "campaign groups, not events — events of one campaign are a single unit of "
            "inference and must never be spread across splits",
        )
    by_campaign: dict[str, set[str]] = {}
    for record in records:
        by_campaign.setdefault(record.campaign_id, set()).add(record.group_id)
    fragmented = sorted(cid for cid, gids in by_campaign.items() if len(gids) > 1)
    if fragmented:
        raise GroupingError(
            RC_EVENT_LEVEL_SPLIT_REFUSED,
            f"campaign_id(s) {fragmented} span multiple group_id values; these records are "
            "event fragments of one campaign and must not be split",
        )
    return tuple(records)


def _bridge_buckets(
    records: tuple[_Record, ...],
) -> list[tuple[str, str, tuple[str, ...], tuple[str, ...]]]:
    """Bucket groups by every identity-bridge attribute class.

    Returns ``(kind, attribute, group_ids, raw_values)`` tuples; ``group_ids``
    is sorted (records are pre-sorted) and only buckets with >= 2 groups are
    actual bridges. Template buckets use :func:`canonical_template`.
    """

    buckets: list[tuple[str, str, tuple[str, ...], tuple[str, ...]]] = []
    for kind, field in (
        (BK_ATTACKER_FAMILY, "attacker_family"),
        (BK_TENANT, "tenant"),
        (BK_SOURCE_LINEAGE, "source_lineage"),
    ):
        grouped: dict[str, list[str]] = {}
        for record in records:
            grouped.setdefault(getattr(record, field), []).append(record.group_id)
        for value in sorted(grouped):
            buckets.append((kind, value, tuple(grouped[value]), (value,)))
    canon_members: dict[str, list[str]] = {}
    canon_raws: dict[str, set[str]] = {}
    for record in records:
        for template in record.templates:
            key = canonical_template(template)
            members = canon_members.setdefault(key, [])
            if record.group_id not in members:
                members.append(record.group_id)
            canon_raws.setdefault(key, set()).add(template)
    for value in sorted(canon_members):
        raws = tuple(sorted(canon_raws[value]))
        kind = BK_TOOLING_TEMPLATE_PARAPHRASE if len(raws) > 1 else BK_TOOLING_TEMPLATE
        buckets.append((kind, value, tuple(canon_members[value]), raws))
    return buckets


def _bridge_findings(records: tuple[_Record, ...]) -> tuple[LeakageFinding, ...]:
    findings = [
        LeakageFinding(kind=kind, attribute=attribute, group_ids=gids, raw_values=raws)
        for kind, attribute, gids, raws in _bridge_buckets(records)
        if len(gids) > 1
    ]
    findings.sort(key=lambda f: (f.kind, f.attribute, f.group_ids))
    return tuple(findings)


def _components(
    records: tuple[_Record, ...], findings: tuple[LeakageFinding, ...]
) -> list[tuple[str, ...]]:
    """Union-find leakage components (smallest root wins; deterministic)."""

    index_of = {record.group_id: i for i, record in enumerate(records)}
    parent = list(range(len(records)))

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for finding in findings:
        anchor = index_of[finding.group_ids[0]]
        for gid in finding.group_ids[1:]:
            root_a, root_b = find(anchor), find(index_of[gid])
            if root_a != root_b:
                low, high = min(root_a, root_b), max(root_a, root_b)
                parent[high] = low
    members: dict[int, list[int]] = {}
    for i in range(len(records)):
        members.setdefault(find(i), []).append(i)
    components = [
        tuple(sorted(records[i].group_id for i in indices)) for indices in members.values()
    ]
    return sorted(components)


def _allocate_counts(n_components: int, ratios: SplitRatios) -> tuple[int, int, int]:
    """Largest-remainder allocation with a no-empty-split repair pass."""

    exact = (ratios.train * n_components, ratios.dev * n_components, ratios.test * n_components)
    counts = [int(value) for value in exact]
    remaining = n_components - sum(counts)
    order = sorted(range(3), key=lambda i: (-(exact[i] - counts[i]), i))
    for i in range(remaining):
        counts[order[i]] += 1
    while 0 in counts:
        zero = counts.index(0)
        donor = max(range(3), key=lambda i: (counts[i], -i))
        counts[donor] -= 1
        counts[zero] += 1
    return counts[0], counts[1], counts[2]


def _validate_assignment(records: tuple[_Record, ...], assignment: Mapping[str, str]) -> None:
    if not isinstance(assignment, Mapping):
        raise GroupingError(
            RC_INVALID_GROUP_FIELD,
            f"assignment must be a mapping of group_id -> split label, got "
            f"{type(assignment).__name__}",
        )
    known = {record.group_id for record in records}
    unknown_keys = sorted(str(k) for k in set(assignment) - known)
    if unknown_keys:
        raise GroupingError(
            RC_UNKNOWN_ASSIGNMENT_KEY,
            f"assignment covers unknown group_id(s) {unknown_keys}",
        )
    missing = sorted(known - set(assignment))
    if missing:
        raise GroupingError(
            RC_INCOMPLETE_ASSIGNMENT, f"assignment is missing group_id(s) {missing}"
        )
    bad_labels = sorted({str(assignment[g]) for g in known} - set(SPLITS))
    if bad_labels:
        raise GroupingError(RC_INVALID_SPLIT_LABEL, f"split label(s) {bad_labels} not in {SPLITS}")


def _detect_overlaps(
    records: tuple[_Record, ...], assignment: Mapping[str, str]
) -> tuple[BridgeOverlap, ...]:
    """Post-hoc leak detector: exact report of bridges spanning > 1 split."""

    overlaps = [
        BridgeOverlap(
            kind=kind,
            attribute=attribute,
            splits=tuple(sorted({assignment[g] for g in gids})),
            group_ids=gids,
        )
        for kind, attribute, gids, _raws in _bridge_buckets(records)
        if len({assignment[g] for g in gids}) > 1
    ]
    overlaps.sort(key=lambda o: (o.kind, o.attribute, o.group_ids))
    return tuple(overlaps)


def detect_bridge_overlaps(
    groups: Iterable[Mapping[str, Any]], assignment: Mapping[str, str]
) -> tuple[BridgeOverlap, ...]:
    """Independent leak detector: exact overlap report (empty tuple == clean).

    Recomputes every identity bridge from the raw groups and reports any
    bridge whose members land in more than one split under ``assignment``.
    """

    records = _materialize(groups)
    _validate_assignment(records, assignment)
    return _detect_overlaps(records, assignment)


def split(
    groups: Iterable[Mapping[str, Any]],
    seed: int,
    *,
    ratios: SplitRatios | None = None,
) -> Partitions:
    """Partition campaign groups into leak-free train/dev/test partitions.

    Groups sharing an attacker family, tenant, canonical tooling template or
    source lineage are merged into one leakage component and assigned to the
    same split; components are shuffled with ``random.Random(seed)`` and
    allocated by largest remainder (every split stays non-empty when at least
    three bridge-free components exist). Raises :class:`GroupingError` with a
    stable ``reason_code`` on any malformed input, event-level fragmentation,
    degenerate bridge collapse or post-hoc overlap.
    """

    if isinstance(seed, bool) or not isinstance(seed, int):
        raise GroupingError(RC_INVALID_SEED, f"seed must be an int, got {type(seed).__name__}")
    active_ratios = ratios if ratios is not None else SplitRatios()
    active_ratios.validate()
    records = _materialize(groups)
    findings = _bridge_findings(records)
    components = _components(records, findings)
    if len(components) < len(SPLITS):
        raise GroupingError(
            RC_DEGENERATE_COMPONENT_COUNT,
            f"identity bridges collapse {len(records)} group(s) into {len(components)} "
            f"component(s); at least {len(SPLITS)} bridge-free components are required to "
            f"fill {SPLITS}",
        )
    shuffled = list(components)
    random.Random(seed).shuffle(shuffled)
    n_train, n_dev, n_test = _allocate_counts(len(components), active_ratios)
    chunks: dict[str, list[tuple[str, ...]]] = {
        "train": shuffled[:n_train],
        "dev": shuffled[n_train : n_train + n_dev],
        "test": shuffled[n_train + n_dev :],
    }
    assignment: dict[str, str] = {}
    for label in SPLITS:
        for component in chunks[label]:
            for group_id in component:
                assignment[group_id] = label
    assignment = dict(sorted(assignment.items()))

    overlaps = _detect_overlaps(records, assignment)
    if overlaps:
        raise GroupingError(
            RC_BRIDGE_OVERLAP_DETECTED,
            "post-hoc leak detector found identity bridges spanning splits: "
            + json.dumps([o.to_dict() for o in overlaps], sort_keys=True),
        )

    payload_by_gid = {record.group_id: record.payload for record in records}
    parts: dict[str, tuple[Mapping[str, Any], ...]] = {}
    for label in SPLITS:
        gids = sorted(gid for component in chunks[label] for gid in component)
        parts[label] = tuple(payload_by_gid[gid] for gid in gids)
    audit = LeakageAudit(
        findings=findings,
        bridge_overlap_report=(),
        group_count=len(records),
        component_count=len(components),
    )
    digest = hashlib.sha256(
        json.dumps(
            {"assignment": assignment, "schema_version": GROUP_SPLIT_VERSION, "seed": seed},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return Partitions(
        train=parts["train"],
        dev=parts["dev"],
        test=parts["test"],
        assignment=assignment,
        audit=audit,
        seed=seed,
        ratios=active_ratios,
        partition_sha256=digest,
    )
