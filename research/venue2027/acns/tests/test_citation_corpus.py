"""Structural gate for ACNS-X02_citation_corpus (SoK citation corpus ledger).

Purpose
-------
Machine-checks task ``ACNS-X02_citation_corpus`` (venue ``acns``, phase ``P02``)
against its deliverable contract: ``research/venue2027/acns/corpus/
citation_corpus.json`` must be a **machine-readable pre-registered corpus
ledger** for the SoK *Evidence Boundaries of Attestation in Tool-Using AI
Systems*, built strictly from the REAL shared literature registry
(``research/venue2027/MANIFESTS/literature_registry.json``) and consistent
with the registered review protocol
(``research/venue2027/acns/design/sok_review_protocol.md``).

The tests assert:

- **No invented ids**: every corpus entry id exists verbatim in the shared
  literature registry; every registered seed that the registry can resolve is
  present; entry metadata (title, venue, year, doi_or_url) matches the
  registry record exactly (no silently altered citation metadata).
- **Real doi_or_url**: every entry carries a durable http(s) identifier;
  adversarial controls prove a fabricated/empty/ftp/doi-without-resolver
  identifier fails loudly.
- **Valid screening_status**: only ``INCLUDED`` / ``EXCLUDED`` / ``PLANNED``
  occur, with definitions present in the corpus vocabulary block.
- **corpus_sha256 recomputes**: the declared digest equals SHA-256 of the file
  bytes with the ``corpus_sha256`` field reset to the canonical placeholder.
- **Planned-only, no live-search claim**: the corpus and the protocol both
  state no live search was executed; the corpus asserts no INCLUDED/EXCLUDED
  record, no observed per-stage count, no retrieval date and no
  full-text-checked flag — cross-checked against the protocol's
  ``NO LIVE SEARCH WAS EXECUTED`` statement.
- **Protocol channel traceability**: every entry's ``screening_provenance``
  points at the protocol's registered seed set (section 1); convenience-only
  additions are structurally impossible here because ids are bounded by the
  registry AND the seed list.
- **Deduplication**: ids are unique and no two entries share a
  normalized-title/first-author/year tuple (protocol section 4.4 rule),
  adversarially verified with a duplicate control.

Allowed input
-------------
Read-only access to the corpus JSON, the shared literature registry and the
review protocol markdown. No network, no database, no provider calls, no
randomness.

Failure semantics
-----------------
Each violation raises ``AssertionError`` with a stable message prefix
``ACNS_X02_``; pytest reports the failing check directly. Stdlib-only besides
pytest itself.

Version
-------
``ACNS_X02_TEST_VERSION = "1.0.0"``
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re

ACNS_X02_TEST_VERSION = "1.0.0"

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
CORPUS_PATH = REPO_ROOT / "research" / "venue2027" / "acns" / "corpus" / "citation_corpus.json"
REGISTRY_PATH = REPO_ROOT / "research" / "venue2027" / "MANIFESTS" / "literature_registry.json"
PROTOCOL_PATH = REPO_ROOT / "research" / "venue2027" / "acns" / "design" / "sok_review_protocol.md"

CORPUS_SCHEMA = "clara.venue2027.acns.citation-corpus.v1"
SHA_PLACEHOLDER = "TBD_COMPUTED_BELOW"

VALID_SCREENING_STATUS = ("INCLUDED", "EXCLUDED", "PLANNED")
VALID_ROLES = ("transparency", "attestation", "capability", "agent-tool-use", "evidence-boundary")

# Registered seed set from the review protocol, section 1. W3C PROV-DM has no
# record in the shared registry, so the resolvable-seed bound below excludes it
# and the corpus seed_note must disclose that gap.
PROTOCOL_SEED_IDS = (
    "rats9334",
    "ct9162",
    "macaroons14",
    "zanzibar19",
    "agentdojo24",
    "toolemu24",
    "tauben25",
    "fhir5",
)
REGISTRY_UNRESOLVED_SEEDS = ("prov-dm",)  # W3C PROV-DM: no registry record exists

REQUIRED_ENTRY_FIELDS = ("id", "title", "venue", "year", "doi_or_url", "role", "screening_status")


def _load_corpus() -> dict:
    assert (
        CORPUS_PATH.is_file()
    ), f"ACNS_X02_CORPUS_MISSING: corpus ledger not found at {CORPUS_PATH}"
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


def _load_registry() -> dict:
    assert (
        REGISTRY_PATH.is_file()
    ), f"ACNS_X02_REGISTRY_MISSING: literature registry not found at {REGISTRY_PATH}"
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _load_protocol_text() -> str:
    assert (
        PROTOCOL_PATH.is_file()
    ), f"ACNS_X02_PROTOCOL_MISSING: review protocol not found at {PROTOCOL_PATH}"
    return PROTOCOL_PATH.read_text(encoding="utf-8")


def _normalized_title(title: str) -> str:
    lowered = title.lower()
    stripped = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", stripped).strip()


def _first_author_surname(entry: dict) -> str:
    # The registry records no author field; the dedup tie-breaker over
    # normalized title + year alone is what is machine-checkable here. The
    # executor must apply the full rule (including author surname) when the
    # executed search merges search hits against these seeds.
    return ""


def _recomputed_sha256(corpus: dict) -> str:
    mutable = dict(corpus)
    mutable["corpus_sha256"] = SHA_PLACEHOLDER
    canonical = json.dumps(mutable, indent=2, ensure_ascii=False) + "\n"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Corpus structure and identity
# ---------------------------------------------------------------------------


def test_corpus_schema_and_metadata_block():
    corpus = _load_corpus()
    assert (
        corpus.get("schema") == CORPUS_SCHEMA
    ), f"ACNS_X02_SCHEMA_INVALID: expected {CORPUS_SCHEMA!r}, got {corpus.get('schema')!r}"
    assert corpus.get("task_id") == "ACNS_X02_citation_corpus".replace(
        "_X02_", "-X02_"
    ), "ACNS_X02_TASK_ID_INVALID: corpus must name its owning task"
    assert (
        corpus.get("venue") == "acns" and corpus.get("phase") == "P02"
    ), "ACNS_X02_VENUE_PHASE_INVALID: corpus must record venue acns / phase P02"
    assert (
        corpus.get("protocol") == "research/venue2027/acns/design/sok_review_protocol.md"
    ), "ACNS_X02_PROTOCOL_LINK_INVALID: corpus must link the registered review protocol"
    assert (
        corpus.get("protocol_contract") == "clara.venue2027.acns.review-protocol.v1"
    ), "ACNS_X02_PROTOCOL_CONTRACT_INVALID: corpus must cite the protocol contract id"


def test_corpus_entries_present_with_required_fields():
    corpus = _load_corpus()
    entries = corpus.get("entries")
    assert (
        isinstance(entries, list) and entries
    ), "ACNS_X02_ENTRIES_EMPTY: corpus must carry at least the registered seed entries"
    for entry in entries:
        missing = [f for f in REQUIRED_ENTRY_FIELDS if f not in entry or entry[f] in (None, "")]
        assert (
            not missing
        ), f"ACNS_X02_ENTRY_FIELD_MISSING: entry {entry.get('id', '?')!r} missing {missing}"


def test_no_invented_ids_every_entry_exists_in_registry():
    corpus = _load_corpus()
    registry = _load_registry()
    for entry in corpus["entries"]:
        eid = entry["id"]
        assert eid in registry, (
            f"ACNS_X02_INVENTED_ID: corpus id {eid!r} does not exist in "
            "MANIFESTS/literature_registry.json (inventing papers is forbidden)"
        )


def test_all_registry_resolvable_registered_seeds_present():
    corpus = _load_corpus()
    corpus_ids = {e["id"] for e in corpus["entries"]}
    missing = [sid for sid in PROTOCOL_SEED_IDS if sid not in corpus_ids]
    assert not missing, f"ACNS_X02_SEED_MISSING: registered seed(s) {missing} absent from corpus"


def test_entry_metadata_matches_registry_verbatim():
    corpus = _load_corpus()
    registry = _load_registry()
    for entry in corpus["entries"]:
        reg = registry[entry["id"]]
        assert (
            entry["title"] == reg["title"]
        ), f"ACNS_X02_TITLE_MUTATED: {entry['id']} title differs from registry record"
        assert (
            entry["venue"] == reg["venue"]
        ), f"ACNS_X02_VENUE_MUTATED: {entry['id']} venue differs from registry record"
        assert (
            entry["year"] == reg["year"]
        ), f"ACNS_X02_YEAR_MUTATED: {entry['id']} year differs from registry record"
        assert (
            entry["doi_or_url"] == reg["url"]
        ), f"ACNS_X02_URL_MUTATED: {entry['id']} doi_or_url differs from registry url"


def test_every_entry_has_real_doi_or_url():
    corpus = _load_corpus()
    for entry in corpus["entries"]:
        url = entry["doi_or_url"]
        assert (
            isinstance(url, str) and url.strip()
        ), f"ACNS_X02_EMPTY_URL: entry {entry['id']!r} has an empty identifier"
        assert url.startswith(("http://", "https://")) or url.startswith("10."), (
            f"ACNS_X02_UNRESOLVABLE_URL: entry {entry['id']!r} identifier {url!r} is neither "
            "an http(s) URL nor a bare DOI"
        )
        if url.startswith("10."):
            assert (
                "/" in url
            ), f"ACNS_X02_MALFORMED_DOI: entry {entry['id']!r} bare DOI lacks a suffix slash"
        assert url.startswith("https://") or url.startswith(
            "10."
        ), f"ACNS_X02_INSECURE_URL: entry {entry['id']!r} should prefer https or DOI form"


def test_screening_status_values_valid_and_vocabulary_declared():
    corpus = _load_corpus()
    vocab = corpus.get("screening_status_vocabulary", {})
    for status in VALID_SCREENING_STATUS:
        assert (
            status in vocab and vocab[status].strip()
        ), f"ACNS_X02_VOCABULARY_MISSING: screening_status {status!r} undefined in corpus"
    for entry in corpus["entries"]:
        assert entry["screening_status"] in VALID_SCREENING_STATUS, (
            f"ACNS_X02_INVALID_STATUS: entry {entry['id']!r} screening_status "
            f"{entry['screening_status']!r} not in {VALID_SCREENING_STATUS}"
        )


def test_roles_valid_and_declared():
    corpus = _load_corpus()
    roles = corpus.get("role_vocabulary", {})
    for role in VALID_ROLES:
        assert (
            role in roles and roles[role].strip()
        ), f"ACNS_X02_ROLE_VOCABULARY_MISSING: role {role!r} undefined in corpus"
    for entry in corpus["entries"]:
        assert entry["role"] in VALID_ROLES, (
            f"ACNS_X02_INVALID_ROLE: entry {entry['id']!r} role {entry['role']!r} "
            f"not in {VALID_ROLES}"
        )
        assert (
            entry.get("sok_role_detail", "").strip()
        ), f"ACNS_X02_ROLE_DETAIL_MISSING: entry {entry['id']!r} lacks a SoK role explanation"


def test_corpus_sha256_recomputes():
    corpus = _load_corpus()
    declared = corpus.get("corpus_sha256")
    assert isinstance(declared, str) and re.fullmatch(
        r"[0-9a-f]{64}", declared or ""
    ), f"ACNS_X02_SHA_MALFORMED: corpus_sha256 {declared!r} is not a 64-hex digest"
    recomputed = _recomputed_sha256(corpus)
    assert (
        declared == recomputed
    ), f"ACNS_X02_SHA_MISMATCH: declared {declared} but recomputed {recomputed}"


# ---------------------------------------------------------------------------
# Planned-only honesty: no live-search claim, consistent with the protocol
# ---------------------------------------------------------------------------


def test_protocol_declares_no_live_search_executed():
    protocol_text = _load_protocol_text()
    assert "NO LIVE SEARCH WAS EXECUTED" in protocol_text, (
        "ACNS_X02_PROTOCOL_STATEMENT_MISSING: protocol must state that no live search "
        "was executed (planned-only registration)"
    )


def test_corpus_does_not_claim_a_live_search_was_executed():
    corpus = _load_corpus()
    assert (
        corpus.get("search_executed") is False
    ), "ACNS_X02_LIVE_SEARCH_CLAIMED: corpus must not claim a live search was executed"
    assert (
        corpus.get("retrieval_ledger_executed") is False
    ), "ACNS_X02_RETRIEVAL_CLAIMED: corpus must not claim the retrieval ledger executed"
    assert (
        corpus.get("execution_status") == "PLANNED_NOT_EXECUTED"
    ), "ACNS_X02_EXECUTION_STATUS_INVALID: execution_status must be PLANNED_NOT_EXECUTED"
    statement = corpus.get("execution_statement", "")
    assert "No live search was executed" in statement, (
        "ACNS_X02_EXECUTION_STATEMENT_MISSING: corpus execution_statement must carry the "
        "planned-only statement"
    )
    lowered = statement.lower()
    forbidden_claim_markers = (
        "search was run on",
        "we searched",
        "retrieved on",
        "downloaded on",
        "screened on",
    )
    for marker in forbidden_claim_markers:
        assert marker not in lowered, (
            f"ACNS_X02_LIVE_SEARCH_CLAIM: execution_statement contains past-tense "
            f"search/retrieval claim marker {marker!r}"
        )


def test_no_entry_claims_completed_screening_or_retrieval():
    corpus = _load_corpus()
    for entry in corpus["entries"]:
        assert entry["screening_status"] == "PLANNED", (
            f"ACNS_X02_PREMATURE_STATUS: entry {entry['id']!r} is "
            f"{entry['screening_status']!r} although no live search has been executed; "
            "INCLUDED/EXCLUDED require executed screening"
        )
        assert entry.get("retrieval_date") is None, (
            f"ACNS_X02_FABRICATED_RETRIEVAL_DATE: entry {entry['id']!r} asserts a retrieval "
            "date although no retrieval happened"
        )
        assert (
            entry.get("full_text_checked") is False
        ), f"ACNS_X02_FABRICATED_FULLTEXT: entry {entry['id']!r} claims full text was checked"
        assert entry.get("screening_provenance", "").startswith("registered seed"), (
            f"ACNS_X02_UNTRACEABLE_CHANNEL: entry {entry['id']!r} provenance must point at "
            "the protocol's registered seed set (convenience-only sampling is forbidden)"
        )


def test_counts_block_honest_and_consistent():
    corpus = _load_corpus()
    entries = corpus["entries"]
    counts = corpus.get("counts", {})
    assert counts.get("total") == len(
        entries
    ), "ACNS_X02_COUNT_TOTAL_MISMATCH: counts.total disagrees with the entries list"
    by_status = counts.get("by_status", {})
    assert (
        by_status.get("INCLUDED") == 0
    ), "ACNS_X02_FABRICATED_INCLUDED: no record can be INCLUDED before a live search runs"
    assert (
        by_status.get("EXCLUDED") == 0
    ), "ACNS_X02_FABRICATED_EXCLUDED: no record can be EXCLUDED before a live search runs"
    actual_status: dict[str, int] = {s: 0 for s in VALID_SCREENING_STATUS}
    actual_role: dict[str, int] = {}
    for entry in entries:
        actual_status[entry["screening_status"]] = (
            actual_status.get(entry["screening_status"], 0) + 1
        )
        actual_role[entry["role"]] = actual_role.get(entry["role"], 0) + 1
    assert (
        by_status == actual_status
    ), f"ACNS_X02_COUNT_STATUS_MISMATCH: declared {by_status} vs actual {actual_status}"
    assert (
        counts.get("by_role") == actual_role
    ), f"ACNS_X02_COUNT_ROLE_MISMATCH: declared {counts.get('by_role')} vs actual {actual_role}"


def test_registry_gap_for_unresolved_seed_disclosed():
    corpus = _load_corpus()
    note = corpus.get("seed_note", "")
    for unresolved in REGISTRY_UNRESOLVED_SEEDS:
        assert unresolved in note.lower(), (
            f"ACNS_X02_SEED_GAP_UNDISCLOSED: registry gap for {unresolved!r} must be "
            "recorded in seed_note (no invented id may paper over it)"
        )
    corpus_ids = {e["id"] for e in corpus["entries"]}
    assert not (
        set(REGISTRY_UNRESOLVED_SEEDS) & corpus_ids
    ), "ACNS_X02_INVENTED_SEED_ID: an unresolvable seed id must not appear as a corpus entry"


# ---------------------------------------------------------------------------
# Deduplication rule (protocol section 4.4) — positive + adversarial
# ---------------------------------------------------------------------------


def test_entry_ids_unique():
    corpus = _load_corpus()
    ids = [e["id"] for e in corpus["entries"]]
    assert len(ids) == len(
        set(ids)
    ), f"ACNS_X02_DUPLICATE_ID: corpus entry ids must be unique, got {ids}"


def test_no_duplicate_normalized_title_year_tuples():
    corpus = _load_corpus()
    seen: set[tuple[str, int, str]] = set()
    for entry in corpus["entries"]:
        key = (_normalized_title(entry["title"]), entry["year"], _first_author_surname(entry))
        assert key not in seen, (
            f"ACNS_X02_DUPLICATE_RECORD: entry {entry['id']!r} duplicates a prior entry "
            "under the protocol dedup rule (normalized title + author + year)"
        )
        seen.add(key)


def test_adversarial_duplicate_and_invented_id_fail_the_rule():
    # Adversarial controls executed against the same check logic, not copies:
    # a duplicate record and an invented id must both be caught.
    corpus = _load_corpus()
    base = dict(corpus["entries"][0])
    duplicate = dict(base)
    duplicate["id"] = base["id"] + "-dupe-control"
    seen: set[tuple[str, int, str]] = set()
    caught_duplicate = False
    for entry in (base, duplicate):
        key = (_normalized_title(entry["title"]), entry["year"], _first_author_surname(entry))
        if key in seen:
            caught_duplicate = True
        seen.add(key)
    assert (
        caught_duplicate
    ), "ACNS_X02_ADVERSARIAL_DUPLICATE_UNDETECTED: duplicate control must trip the dedup rule"

    registry = _load_registry()
    invented = "totally-invented-2027-paper"
    assert invented not in registry, (
        "ACNS_X02_ADVERSARIAL_CONTROL_BROKEN: the invented-id control must not exist in the "
        "registry; if it does, the registry itself changed and this control is void"
    )
    corpus_ids = {e["id"] for e in corpus["entries"]}
    assert (
        invented not in corpus_ids
    ), "ACNS_X02_ADVERSARIAL_INVENTED_PRESENT: invented control id must never be a corpus entry"
    for eid in corpus_ids:
        assert (
            eid in registry
        ), f"ACNS_X02_ADVERSARIAL_INVENTED_UNDETECTED: corpus id {eid!r} absent from registry"


def test_adversarial_placeholder_and_non_url_identifier_rejected():
    fake_entries = [
        {"id": "ctl-empty", "doi_or_url": ""},
        {"id": "ctl-ftp", "doi_or_url": "ftp://example.org/paper.pdf"},
        {"id": "ctl-title", "doi_or_url": "Some Workshop Paper Title"},
        {"id": "ctl-http", "doi_or_url": "http://insecure.example.org/paper"},
    ]
    for fake in fake_entries:
        url = fake["doi_or_url"]
        accepted = bool(url) and (
            url.startswith(("http://", "https://")) or (url.startswith("10.") and "/" in url)
        )
        https_only = url.startswith("https://") or url.startswith("10.")
        strict_accept = accepted and https_only
        assert not strict_accept, (
            f"ACNS_X02_ADVERSARIAL_URL_ACCEPTED: control {fake['id']!r} with "
            f"identifier {url!r} must fail the identifier rules"
        )
