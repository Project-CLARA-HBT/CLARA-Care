"""ACNS-X04_claim_extractor — deterministic attestation-claim extraction (SoK instrument).

Purpose
-------
Task ACNS-X04_claim_extractor (Phase P04, venue acns) delivers the *extraction
instrument* of the SoK "Evidence Boundaries of Attestation in Tool-Using AI
Systems" (``research/venue2027/VENUES/acns/RESEARCH_BLUEPRINT.md``, RQ1). Per
the signed novelty contract this study is a **SoK**: what this module
contributes is a deterministic, rule-based (NO LLM, no network, no clock, no
randomness) extractor that reads one paper record (title/abstract-like text)
and emits the structured attestation/provenance CLAIMS it contains, each
mapped to an evidence-boundary category of the pre-registered taxonomy
(selection protocol §8.2: ``BND_VALID`` / ``BND_OVERREAD`` / ``BND_UNDERREAD``
/ ``BND_INDETERMINATE``) and annotated with the gap-register codes (threat
model §6, G1-G9) where the claimed implication exceeds its evidence. The
instrument exists so corpus coding (RQ1), the witness gallery (ACNS-X07) and
the inter-rater statistics (RQ3) start from a reproducible mechanical
first-pass extraction that human coders (TC5) then adjudicate; it never
certifies labels by itself.

Core contract
-------------
- :func:`extract_claims` — ``extract_claims(record) -> list[Claim]``: parse the
  record text into sentences and emit one :class:`Claim` per detected
  attestation claim, carrying ``claim_kind`` (existence | boundary |
  performance, protocol §6 C7), ``subject``, ``evidence_boundary`` (taxonomy
  category or ``None`` when the sentence asserts a guarantee with no evidence
  boundary at all), ``asserted_guarantee`` (strongest lattice level the
  wording asserts, threat model §1.2, or ``None``), ``scope`` (universal |
  existential | unscoped quantifier of the claim) plus traceability fields:
  the text pointer (character span and claim id), the disclosed evidence
  class (six-class lattice), gap codes, ambiguity flag and confidence.
- :func:`assert_no_unsupported_claim` — ``assert_no_unsupported_claim(claims)
  -> None``: the fail-closed gate. It raises :class:`UnsupportedClaimError`
  with the stable reason code ``UNSUPPORTED_CLAIM_NO_EVIDENCE_BOUNDARY`` when
  any claim asserts a guarantee (a lattice level) while its
  ``evidence_boundary`` is ``None`` — the G9 shape "published claim ⇒ claim
  supported by the paper's evidence" with no disclosed evidence to apply the
  extraction manual to. Malformed input fails closed too, never silently.

Extraction rules (deterministic, ordered per sentence)
------------------------------------------------------
1. Skip captions (``Figure 3:``-style leads) and ablation sentences — not
   claim sentences for C1 coding.
2. Negated proof relations (``is not evidence that ...``, ``does not prove``,
   ``provides no guarantee``) become *boundary* claims (protocol §6 C7; a
   negative boundary claim can be ``BND_VALID``) with no asserted guarantee —
   a naive extractor would read them as positive claims.
3. Relevance gate: the sentence must be attestation-domain-relevant AND name
   evidence, assert a lattice level, or use guarantee wording; otherwise it
   is not a claim sentence and is skipped (skips are reported via the
   returned claim count, never via exceptions).
4. Performance sentences (percentages, success rates) are coded as
   ``performance`` claims with no asserted guarantee — context only, never
   corpus-anchored endpoints (protocol §6 C7).
5. A sentence with guarantee wording and asserted level but **no disclosed
   evidence class** yields a claim with ``evidence_boundary=None``
   (unsupported; gap G9) — retained at low confidence so that
   :func:`assert_no_unsupported_claim` can refuse it.
6. Hedged wording (``may``, ``designed to``, ...) under-determines the
   asserted level: the claim is retained as ``BND_INDETERMINATE`` with the
   ambiguity flag set — never coerced to a definite verdict (rater manual §5
   IND rules).
7. Otherwise the taxonomy comparison runs: the strongest level the wording
   asserts (C3) is compared against the class ceiling of the disclosed
   evidence (C4/D5): above the ceiling → ``BND_OVERREAD`` with the specific
   gap code (G1 transport-ack-as-processing, G2 receipt-as-execution, G3
   execution-as-consumption, residual G7); equal → ``BND_VALID``; below →
   ``BND_UNDERREAD``.

Allowed input
-------------
``record``: a JSON-serializable mapping with ``title`` and/or ``abstract``
(and optional ``text``, ``record_id``/``id``), or a plain string treated as
the record text. All input is synthetic (``synthetic-acns-2027``-style
fixtures or inline literals): no PHI/PII, no network, no clock, no database,
no live provider, no LLM.

Failure semantics (stable reason codes)
---------------------------------------
:class:`ClaimExtractorError` carries one stable uppercase ``reason_code``:
- ``MALFORMED_RECORD`` — ``record`` is neither a mapping nor a string.
- ``EMPTY_TEXT`` — the record yields no non-whitespace text; a record that
  cannot be coded fails closed instead of silently returning no claims.
:class:`UnsupportedClaimError` carries:
- ``MALFORMED_CLAIM_LIST`` — :func:`assert_no_unsupported_claim` received a
  non-list.
- ``MALFORMED_CLAIM`` — a list element is not a :class:`Claim`.
- ``UNSUPPORTED_CLAIM_NO_EVIDENCE_BOUNDARY`` — a claim asserts a guarantee
  with no evidence boundary (the fail-closed refusal).
Marketing-only records are refused *by policy, not by error*: the selection
protocol excludes vendor marketing from the corpus
(``EXCL_NOT_PEER_REVIEWED``), so a marketing-only record yields **no
confident claim** (empty list), which is distinguishable from a malformed
record.

Version
-------
``CLAIM_EXTRACTOR_VERSION = "1.0.0"``, contract
``clara.venue2027.acns.claim-extractor.v1``. All output types are
JSON-serializable via :meth:`Claim.to_dict`.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Mapping
from typing import Any, Final

CLAIM_EXTRACTOR_VERSION: Final[str] = "1.0.0"
CONTRACT_ID: Final[str] = "clara.venue2027.acns.claim-extractor.v1"
EXTRACTOR_ID: Final[str] = "acns-claim-extractor"

#: Evidence-to-claim lattice (threat model §1.2; rater manual §1.1). L1.5
#: (transport acknowledgment) is a distinct evidence class, not an upgrade of
#: L1; ranks are spaced so L1.5 sits between L1 and L2.
LATTICE_LEVELS: Final[tuple[str, ...]] = (
    "L0-ASSUMED",
    "L1-ASSEMBLED",
    "L1.5-TRANSPORT_ACK",
    "L2-ACKNOWLEDGED",
    "L3-EXECUTED",
    "L4-COMMITTED",
)
LEVEL_RANK: Final[dict[str, int]] = {level: rank for rank, level in enumerate(LATTICE_LEVELS)}

#: Evidence-boundary taxonomy categories (selection protocol §8.2). ``None``
#: is not a category: it marks a claim for which no evidence boundary exists
#: at all (unsupported; the fail-closed target of the assert gate).
BND_VALID: Final[str] = "BND_VALID"
BND_OVERREAD: Final[str] = "BND_OVERREAD"
BND_UNDERREAD: Final[str] = "BND_UNDERREAD"
BND_INDETERMINATE: Final[str] = "BND_INDETERMINATE"
TAXONOMY_BOUNDARY_CODES: Final[tuple[str, ...]] = (
    BND_VALID,
    BND_OVERREAD,
    BND_UNDERREAD,
    BND_INDETERMINATE,
)

#: Six evidence classes of the lattice (blueprint contribution) with the
#: class-to-level ceiling of the demonstrated-evidence derivation (rater
#: manual §2 C4 / decision tree D5).
EVIDENCE_CLASS_CEILING: Final[Mapping[str, str]] = {
    "assembly": "L0-ASSUMED",
    "egress": "L1-ASSEMBLED",
    "transport_acknowledgment": "L1.5-TRANSPORT_ACK",
    "provider_attested_receipt": "L2-ACKNOWLEDGED",
    "execution_trace": "L3-EXECUTED",
    "semantic_consumption": "L4-COMMITTED",
}
#: Deterministic primary-evidence priority: strongest class first (rater
#: manual §2 C2: code the class of the strongest evidence actually presented).
_EVIDENCE_PRIORITY: Final[tuple[str, ...]] = (
    "semantic_consumption",
    "execution_trace",
    "provider_attested_receipt",
    "transport_acknowledgment",
    "egress",
    "assembly",
)
_EVIDENCE_MARKERS: Final[Mapping[str, tuple[str, ...]]] = {
    "semantic_consumption": (
        r"persisting service",
        r"side effect (?:was|is|has been) recorded",
        r"consumption log",
        r"committed side effect",
    ),
    "execution_trace": (
        r"\btee\b",
        r"tee-attested",
        r"trusted execution environment",
        r"attested execution",
        r"execution trace",
        r"attested tool invocation",
    ),
    "provider_attested_receipt": (
        r"provider receipt",
        r"provider-signed",
        r"provider sign",
        r"signed receipt",
        r"receipts?",
        r"signed acknowledgment",
        r"\backnowledgments?\b",
        r"\bdigest\b",
    ),
    "transport_acknowledgment": (
        r"transport acknowledgment",
        r"transport-level acknowledgment",
        r"transport-level acknowledgement",
        r"\btcp\b",
        r"\btls ack",
        r"connection acknowledged",
    ),
    "egress": (
        r"left the agent",
        r"\bdispatch",
        r"\begress\b",
        r"transmitted the bytes",
        r"sent the request",
    ),
    "assembly": (r"composed payload", r"assembled the request", r"\bwe assume\b"),
}

#: Strongest lattice level the claim wording asserts (rater manual §2 C3 /
#: decision tree D4), scanned strongest-first with an included-wording test
#: ("end-to-end", "provably" imply execution-scope wording per anchor C3-A1).
_LEVEL_MARKERS: Final[Mapping[str, tuple[str, ...]]] = {
    "L4-COMMITTED": (r"\bconsumed\b", r"\bcommitted\b", r"\bpersisted\b"),
    "L3-EXECUTED": (
        r"\bexecuted\b",
        r"\bexecutes\b",
        r"tool execution",
        r"attested execution",
        r"end-to-end",
        r"\bprovably\b",
        r"ran the tool",
    ),
    "L2-ACKNOWLEDGED": (
        r"receipt",
        r"\breceived\b",
        r"\breceives\b",
        r"acknowledg",
        r"\bdigest\b",
        r"\bprocessed\b",
        r"\bconfirm",
        r"\bsigned\b",
    ),
    "L1.5-TRANSPORT_ACK": (
        r"transport acknowledgment",
        r"\btcp\b",
        r"connection acknowledged",
        r"bytes (?:were|was) sent",
    ),
    "L1-ASSEMBLED": (r"\bdispatch", r"\bsent\b", r"\begress\b", r"left the agent", r"\btransmit"),
    "L0-ASSUMED": (r"\bwe assume\b", r"\bassumed\b", r"composed payload"),
}

#: Subject canonicalization per evidence class (stable vocabulary).
_SUBJECT_BY_EVIDENCE: Final[Mapping[str, str]] = {
    "semantic_consumption": "committed side effect",
    "execution_trace": "attested tool execution",
    "provider_attested_receipt": "provider receipt",
    "transport_acknowledgment": "transport acknowledgment",
    "egress": "dispatched request",
    "assembly": "assembled request",
}

_GAP_BY_OVERREAD: Final[Mapping[str, str]] = {
    "transport_acknowledgment": "G1_TRANSPORT_ACK_AS_PROCESSING",
    "provider_attested_receipt": "G2_RECEIPT_AS_EXECUTION",
    "execution_trace": "G3_EXECUTION_AS_CONSUMPTION",
}
GAP_RESIDUAL_UPGRADE: Final[str] = "G7_LEVEL_IMPLICIT_UPGRADE"
GAP_NO_DISCLOSED_EVIDENCE: Final[str] = "G9_CLAIM_WITHOUT_DISCLOSED_EVIDENCE"

_RE_CAPTION: Final[re.Pattern[str]] = re.compile(
    r"^(?:figure|fig\.?|table|listing|algorithm)\s*\d+", re.IGNORECASE
)
_RE_ABLATION: Final[re.Pattern[str]] = re.compile(r"\bablation\b", re.IGNORECASE)
_RE_NEGATED_PROOF: Final[re.Pattern[str]] = re.compile(
    r"(?:does not|do not|did not)\s+(?:prove|demonstrate|establish)"
    r"|(?:is|are)\s+not\s+(?:a\s+)?(?:proof|evidence|guarantee)"
    r"|(?:provides?|offers?)\s+no\s+guarantee"
    r"|\bcannot\s+(?:prove|establish)"
    r"|not\s+sufficient\s+(?:evidence|proof)",
    re.IGNORECASE,
)
_RE_GUARANTEE: Final[re.Pattern[str]] = re.compile(
    r"\bguarantees?\b|\bensures?\b|\bcertifies?\b|\bprovably\b|\bproves?\b", re.IGNORECASE
)
_RE_HEDGE: Final[re.Pattern[str]] = re.compile(
    r"\bmay\b|\bmight\b|\bcould\b|\bpotentially\b|\bdesigned to\b|\baims to\b", re.IGNORECASE
)
_RE_PERFORMANCE: Final[re.Pattern[str]] = re.compile(
    r"\d+(?:\.\d+)?\s*%|\bsuccess rate\b|\boutperforms\b|\baccuracy\b|\blatency\b"
    r"|\bthroughput\b|\bauc\b|\bf1 score\b",
    re.IGNORECASE,
)
_RE_DOMAIN: Final[re.Pattern[str]] = re.compile(
    r"attest|receipt|acknowledg|provenance|audit|trace|\btool\b|\bagent\b|provider"
    r"|\btee\b|egress|dispatch|transparency|invocation",
    re.IGNORECASE,
)
_RE_SCOPE_UNIVERSAL: Final[re.Pattern[str]] = re.compile(
    r"\bevery\b|\ball\b|\beach\b|\balways\b|\bnever\b", re.IGNORECASE
)
_RE_SCOPE_EXISTENTIAL: Final[re.Pattern[str]] = re.compile(
    r"\bsome\b|\bcertain\b|\boccasionally\b", re.IGNORECASE
)
_RE_MARKETING: Final[re.Pattern[str]] = re.compile(
    r"revolutionary|seamless(?:ly)?|cutting-edge|best-in-class|world-class"
    r"|game-changing|next-generation|unparalleled|sign up|contact us"
    r"|request a demo|trust platform",
    re.IGNORECASE,
)
_RE_TOOL: Final[re.Pattern[str]] = re.compile(r"\btool\b", re.IGNORECASE)
_RE_ATTEST: Final[re.Pattern[str]] = re.compile(r"attest", re.IGNORECASE)

SENTENCE_RE: Final[re.Pattern[str]] = re.compile(r"[^.!?\n]+(?:[.!?]+|$)")

MIN_MARKETING_MARKERS: Final[int] = 2

SCOPE_UNIVERSAL: Final[str] = "universal"
SCOPE_EXISTENTIAL: Final[str] = "existential"
SCOPE_UNSCOPED: Final[str] = "unscoped"

CLAIM_KIND_EXISTENCE: Final[str] = "existence"
CLAIM_KIND_BOUNDARY: Final[str] = "boundary"
CLAIM_KIND_PERFORMANCE: Final[str] = "performance"

CONFIDENCE_HIGH: Final[str] = "high"
CONFIDENCE_LOW: Final[str] = "low"


class ClaimExtractorError(Exception):
    """Extraction failure carrying a stable uppercase ``reason_code``."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


class UnsupportedClaimError(Exception):
    """Fail-closed refusal carrying a stable uppercase ``reason_code``."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


@dataclasses.dataclass(frozen=True)
class Claim:
    """One extracted attestation claim (JSON-serializable coding object).

    The five contract fields are ``claim_kind``, ``subject``,
    ``evidence_boundary``, ``asserted_guarantee`` and ``scope``; the remaining
    fields carry the traceability the task requires (text pointer, evidence
    type, confidence, ambiguity, gap codes).
    """

    claim_kind: str
    subject: str
    evidence_boundary: str | None
    asserted_guarantee: str | None
    scope: str
    record_id: str = ""
    claim_id: str = ""
    text_pointer: tuple[int, int] = (0, 0)
    quote: str = ""
    evidence_class: str | None = None
    gap_codes: tuple[str, ...] = ()
    ambiguous: bool = False
    confidence: str = CONFIDENCE_HIGH

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_kind": self.claim_kind,
            "subject": self.subject,
            "evidence_boundary": self.evidence_boundary,
            "asserted_guarantee": self.asserted_guarantee,
            "scope": self.scope,
            "record_id": self.record_id,
            "claim_id": self.claim_id,
            "text_pointer": list(self.text_pointer),
            "quote": self.quote,
            "evidence_class": self.evidence_class,
            "gap_codes": list(self.gap_codes),
            "ambiguous": self.ambiguous,
            "confidence": self.confidence,
            "extractor_id": EXTRACTOR_ID,
            "extractor_version": CLAIM_EXTRACTOR_VERSION,
            "contract_id": CONTRACT_ID,
        }


def _record_text(record: Mapping[str, Any] | str) -> tuple[str, str]:
    """Extract ``(record_id, text)`` from a record; fail closed when empty."""
    if isinstance(record, str):
        if not record.strip():
            raise ClaimExtractorError("EMPTY_TEXT", "record string has no codable text")
        return "record", record
    if not isinstance(record, Mapping):
        raise ClaimExtractorError(
            "MALFORMED_RECORD", f"record must be a mapping or string, got {type(record).__name__}"
        )
    record_id = str(record.get("record_id") or record.get("id") or "record")
    text = record.get("text")
    if not isinstance(text, str) or not text.strip():
        title = record.get("title") if isinstance(record.get("title"), str) else ""
        abstract = record.get("abstract") if isinstance(record.get("abstract"), str) else ""
        text = ". ".join(part for part in (title.strip(), abstract.strip()) if part)
    if not text.strip():
        raise ClaimExtractorError("EMPTY_TEXT", f"record {record_id!r} has no codable text")
    return record_id, text


def _sentences_with_spans(text: str) -> list[tuple[str, int, int]]:
    """Deterministic sentence segmentation with character spans."""
    out: list[tuple[str, int, int]] = []
    for match in SENTENCE_RE.finditer(text):
        raw = match.group(0)
        stripped = raw.strip()
        if stripped:
            offset = match.start() + raw.index(stripped[0]) if stripped[0] != raw[0] else 0
            out.append((stripped, match.start() + offset, match.start() + offset + len(stripped)))
    return out


def _match_evidence(sentence: str) -> str | None:
    for evidence_class in _EVIDENCE_PRIORITY:
        for marker in _EVIDENCE_MARKERS[evidence_class]:
            if re.search(marker, sentence, re.IGNORECASE):
                return evidence_class
    return None


def _match_level(sentence: str) -> str | None:
    asserted: str | None = None
    rank = -1
    for level, markers in _LEVEL_MARKERS.items():
        if LEVEL_RANK[level] <= rank:
            continue
        if any(re.search(marker, sentence, re.IGNORECASE) for marker in markers):
            asserted, rank = level, LEVEL_RANK[level]
    return asserted


def _match_scope(sentence: str) -> str:
    if _RE_SCOPE_UNIVERSAL.search(sentence):
        return SCOPE_UNIVERSAL
    if _RE_SCOPE_EXISTENTIAL.search(sentence):
        return SCOPE_EXISTENTIAL
    return SCOPE_UNSCOPED


def _subject_for(evidence_class: str | None, sentence: str) -> str:
    if evidence_class is not None:
        return _SUBJECT_BY_EVIDENCE[evidence_class]
    if _RE_TOOL.search(sentence):
        return "agent tool call"
    if _RE_ATTEST.search(sentence):
        return "remote attestation"
    return "attestation claim"


def _marketing_only(text: str) -> bool:
    """Vendor-marketing gate (protocol EXCL_NOT_PEER_REVIEWED channel).

    A record dominated by promotional markers that discloses no evidence
    artifact is marketing-only material: it is not corpus-codable, so no
    confident claim is extracted from it.
    """
    return len(_RE_MARKETING.findall(text)) >= MIN_MARKETING_MARKERS and (
        _match_evidence(text) is None
    )


def _claim_from_sentence(
    sentence: str,
    span: tuple[int, int],
    record_id: str,
    index: int,
    record_evidence: str | None = None,
) -> Claim | None:
    s_lower_strip = sentence
    if _RE_CAPTION.match(s_lower_strip) or _RE_ABLATION.search(s_lower_strip):
        return None
    if _RE_NEGATED_PROOF.search(s_lower_strip):
        evidence_class = _match_evidence(s_lower_strip)
        return Claim(
            claim_kind=CLAIM_KIND_BOUNDARY,
            subject=_subject_for(evidence_class, s_lower_strip),
            evidence_boundary=BND_VALID,
            asserted_guarantee=None,
            scope=_match_scope(s_lower_strip),
            record_id=record_id,
            claim_id=f"{record_id}:claim-{index:03d}",
            text_pointer=span,
            quote=sentence,
            evidence_class=evidence_class,
            gap_codes=(),
            ambiguous=False,
            confidence=CONFIDENCE_HIGH,
        )

    evidence_class = _match_evidence(s_lower_strip)
    asserted = _match_level(s_lower_strip)
    guarantee_wording = _RE_GUARANTEE.search(s_lower_strip) is not None
    if evidence_class is None and asserted is None and not guarantee_wording:
        return None
    if _RE_PERFORMANCE.search(s_lower_strip):
        return Claim(
            claim_kind=CLAIM_KIND_PERFORMANCE,
            subject=_subject_for(evidence_class, s_lower_strip),
            evidence_boundary=BND_INDETERMINATE,
            asserted_guarantee=None,
            scope=_match_scope(s_lower_strip),
            record_id=record_id,
            claim_id=f"{record_id}:claim-{index:03d}",
            text_pointer=span,
            quote=sentence,
            evidence_class=evidence_class,
            gap_codes=(),
            ambiguous=True,
            confidence=CONFIDENCE_LOW,
        )

    scope = _match_scope(s_lower_strip)
    subject = _subject_for(evidence_class, s_lower_strip)
    if evidence_class is None and record_evidence is not None and asserted is not None:
        # D3 record-level evidence inventory: the sentence names no evidence
        # class itself, but the record documents one; the demonstrated level
        # (C4) derives from the record's evidence, the claimed level (C3) from
        # the sentence wording alone (rater manual §2 C4 / D3+D5).
        ceiling = EVIDENCE_CLASS_CEILING[record_evidence]
        if LEVEL_RANK[asserted] > LEVEL_RANK[ceiling]:
            return Claim(
                claim_kind=CLAIM_KIND_EXISTENCE,
                subject=subject,
                evidence_boundary=None,
                asserted_guarantee=asserted,
                scope=scope,
                record_id=record_id,
                claim_id=f"{record_id}:claim-{index:03d}",
                text_pointer=span,
                quote=sentence,
                evidence_class=None,
                gap_codes=(GAP_NO_DISCLOSED_EVIDENCE,),
                ambiguous=True,
                confidence=CONFIDENCE_LOW,
            )
        return Claim(
            claim_kind=CLAIM_KIND_EXISTENCE,
            subject=_SUBJECT_BY_EVIDENCE[record_evidence],
            evidence_boundary=(
                BND_UNDERREAD if LEVEL_RANK[asserted] < LEVEL_RANK[ceiling] else BND_VALID
            ),
            asserted_guarantee=asserted,
            scope=scope,
            record_id=record_id,
            claim_id=f"{record_id}:claim-{index:03d}",
            text_pointer=span,
            quote=sentence,
            evidence_class=record_evidence,
            gap_codes=(),
            ambiguous=False,
            confidence=CONFIDENCE_HIGH,
        )
    if evidence_class is None:
        if guarantee_wording and asserted is not None:
            return Claim(
                claim_kind=CLAIM_KIND_EXISTENCE,
                subject=subject,
                evidence_boundary=None,
                asserted_guarantee=asserted,
                scope=scope,
                record_id=record_id,
                claim_id=f"{record_id}:claim-{index:03d}",
                text_pointer=span,
                quote=sentence,
                evidence_class=None,
                gap_codes=(GAP_NO_DISCLOSED_EVIDENCE,),
                ambiguous=True,
                confidence=CONFIDENCE_LOW,
            )
        return Claim(
            claim_kind=CLAIM_KIND_EXISTENCE,
            subject=subject,
            evidence_boundary=BND_INDETERMINATE,
            asserted_guarantee=asserted,
            scope=scope,
            record_id=record_id,
            claim_id=f"{record_id}:claim-{index:03d}",
            text_pointer=span,
            quote=sentence,
            evidence_class=None,
            gap_codes=(),
            ambiguous=True,
            confidence=CONFIDENCE_LOW,
        )

    if _RE_HEDGE.search(s_lower_strip):
        return Claim(
            claim_kind=CLAIM_KIND_EXISTENCE,
            subject=subject,
            evidence_boundary=BND_INDETERMINATE,
            asserted_guarantee=asserted,
            scope=scope,
            record_id=record_id,
            claim_id=f"{record_id}:claim-{index:03d}",
            text_pointer=span,
            quote=sentence,
            evidence_class=evidence_class,
            gap_codes=(),
            ambiguous=True,
            confidence=CONFIDENCE_LOW,
        )

    ceiling = EVIDENCE_CLASS_CEILING[evidence_class]
    effective_asserted = asserted if asserted is not None else ceiling
    rank_asserted = LEVEL_RANK[effective_asserted]
    rank_ceiling = LEVEL_RANK[ceiling]
    if rank_asserted > rank_ceiling:
        gap = _GAP_BY_OVERREAD.get(evidence_class, GAP_RESIDUAL_UPGRADE)
        boundary, gaps, ambiguous, confidence = BND_OVERREAD, (gap,), False, CONFIDENCE_HIGH
    elif rank_asserted < rank_ceiling:
        boundary, gaps, ambiguous, confidence = BND_UNDERREAD, (), False, CONFIDENCE_HIGH
    else:
        boundary, gaps, ambiguous, confidence = BND_VALID, (), False, CONFIDENCE_HIGH
    return Claim(
        claim_kind=CLAIM_KIND_EXISTENCE,
        subject=subject,
        evidence_boundary=boundary,
        asserted_guarantee=effective_asserted,
        scope=scope,
        record_id=record_id,
        claim_id=f"{record_id}:claim-{index:03d}",
        text_pointer=span,
        quote=sentence,
        evidence_class=evidence_class,
        gap_codes=gaps,
        ambiguous=ambiguous,
        confidence=confidence,
    )


def extract_claims(record: Mapping[str, Any] | str) -> list[Claim]:
    """Extract structured attestation claims from one paper record.

    Exact task contract ``extract_claims(record) -> list[Claim]`` (the task
    manifest's ``extract(paper)->list[Claim]`` signature with the orchestrator
    -directed name). Deterministic rules only: no LLM, no network, no clock,
    no randomness. A marketing-only record yields no confident claim (empty
    list, per the protocol's marketing exclusion); a record that cannot be
    coded at all fails closed with a stable reason code.
    """
    record_id, text = _record_text(record)
    if _marketing_only(text):
        return []
    record_evidence = _match_evidence(text)
    claims: list[Claim] = []
    for index, (sentence, start, end) in enumerate(_sentences_with_spans(text), start=1):
        claim = _claim_from_sentence(
            sentence, (start, end), record_id, index, record_evidence=record_evidence
        )
        if claim is not None:
            claims.append(claim)
    if claims:
        return claims
    # Sentence-level extraction found nothing codable (e.g. every marker is
    # record-level, never sentence-local): fall back to the whole-text record
    # as one coding object (rater manual D1 allows record-scoped inventory).
    record_span = (0, len(text))
    whole = _claim_from_sentence(
        text, record_span, record_id, 1, record_evidence=record_evidence
    )
    return [] if whole is None else [whole]


def assert_no_unsupported_claim(claims: list[Claim]) -> None:
    """Fail closed when a claim asserts a guarantee with no evidence boundary.

    A claim whose ``evidence_boundary`` is ``None`` while it asserts a lattice
    level is the G9 unsupported shape (a guarantee with no disclosed evidence
    to apply the extraction manual to); this gate refuses it with the stable
    reason code ``UNSUPPORTED_CLAIM_NO_EVIDENCE_BOUNDARY``. Malformed input is
    refused as well — it is never counted as a safe pass.
    """
    if not isinstance(claims, list | tuple):
        raise UnsupportedClaimError(
            "MALFORMED_CLAIM_LIST",
            f"claims must be a list of Claim, got {type(claims).__name__}",
        )
    for position, claim in enumerate(claims):
        if not isinstance(claim, Claim):
            raise UnsupportedClaimError(
                "MALFORMED_CLAIM",
                f"claims[{position}] is {type(claim).__name__}, expected Claim",
            )
        if claim.asserted_guarantee is not None and claim.evidence_boundary is None:
            raise UnsupportedClaimError(
                "UNSUPPORTED_CLAIM_NO_EVIDENCE_BOUNDARY",
                f"claim {claim.claim_id!r} ({claim.subject!r}) asserts guarantee "
                f"{claim.asserted_guarantee} with no evidence boundary; gaps="
                f"{','.join(claim.gap_codes) or 'none'}",
            )


__all__ = [
    "BND_INDETERMINATE",
    "BND_OVERREAD",
    "BND_UNDERREAD",
    "BND_VALID",
    "CONTRACT_ID",
    "CLAIM_EXTRACTOR_VERSION",
    "Claim",
    "ClaimExtractorError",
    "EXTRACTOR_ID",
    "LATTICE_LEVELS",
    "TAXONOMY_BOUNDARY_CODES",
    "UnsupportedClaimError",
    "assert_no_unsupported_claim",
    "extract_claims",
]
