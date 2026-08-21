"""Transcript grounding / claim-traceability verifier (task 4.2, Requirement 12).

`GroundingVerifier` runs **after** note generation and only when
``RAG_SCRIBE_GROUNDING_ENABLED`` is true. It enumerates the clinically significant
statements in a generated note and, for each one, verifies it against the
transcript spans (the shared :class:`~clara_ml.scribe.provenance.SpanRegistry`
from task 4.1) treated as evidence rows — **reusing** the CLARA Research / FIDES
claim-verification approach (``factcheck.nli_verifier.verify_claims`` for the NLI
entailment decision and ``factcheck.fides_lite.run_fides_lite`` for the corroborating
fact-check verdict / CRITICAL-block discipline). No new verification engine is built.

Invariants (Requirement 12):
- A statement is ``grounded`` *iff* at least one transcript span entails it under the
  claim-verification pass (NLI ``support_status == "supported"``); otherwise
  ``ungrounded`` (Req 12.2/12.3).
- An ungrounded **critical safety** statement (medication, dose, allergy, vital, or
  diagnosis) is NEVER asserted as fact — it is surfaced only as an
  ``unverified_candidate`` requiring clinician confirmation (Req 12.4/12.5).
- The produced :class:`GroundingReport` is **additive metadata** (written to
  ``grounding_json``); this pass never alters, drops, or reorders the note's section
  text or the transcript (Req 12.6).
- The per-note ``grounded_claim_rate`` is recorded for non-PII analytics (Req 12.8).

When the flag is off the verifier is inert: :meth:`GroundingVerifier.verify` returns
an empty, disabled :class:`GroundingReport` and performs no verification. Importing
this module opens no socket and builds no client.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from clara_ml.config import settings
from clara_ml.factcheck.fides_lite import run_fides_lite
from clara_ml.factcheck.nli_verifier import verify_claims
from clara_ml.scribe.provenance import Provenance, SpanRegistry, TranscriptSpan

__all__ = [
    "GroundedStatement",
    "GroundingReport",
    "GroundingVerifier",
]


# Statuses on a GroundedStatement.
STATUS_GROUNDED = "grounded"
STATUS_UNVERIFIED = "unverified"
STATUS_BOILERPLATE = "boilerplate"


class _HasSections(Protocol):
    @property
    def sections(self) -> Mapping[str, str]: ...


# --- clinical-significance + critical-safety lexicons ----------------------

# Common note/section labels that are scaffolding, not factual assertions.
_BOILERPLATE_LABELS = {
    "subjective",
    "objective",
    "assessment",
    "plan",
    "hpi",
    "ros",
    "history",
    "examination",
    "exam",
    "vitals",
    "medications",
    "allergies",
    "problems",
    "soap",
    "chief complaint",
    "review of systems",
    # Vietnamese section labels (bệnh án).
    "chủ quan",
    "khách quan",
    "đánh giá",
    "kế hoạch",
    "tiền sử",
    "khám",
}

# Dose / medication signals.
_DOSE_PATTERN = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:mg|mcg|µg|ug|ml|mL|g|gram|grams|iu|units?|mEq|puffs?|"
    r"viên|vien|gói|goi|ống|ong|giọt|giot)\b",
    re.IGNORECASE,
)
_MED_TERMS = {
    "medication",
    "medications",
    "med",
    "meds",
    "drug",
    "dose",
    "dosage",
    "prescribe",
    "prescribed",
    "prescription",
    "tablet",
    "capsule",
    "injection",
    "infusion",
    # Vietnamese.
    "thuốc",
    "liều",
    "lieu",
    "kê",
    "uống",
    "uong",
    "tiêm",
    "tiem",
}
_ALLERGY_TERMS = {
    "allergy",
    "allergic",
    "allergies",
    "anaphylaxis",
    "hypersensitivity",
    "dị",
    "ứng",
    "dịứng",
}
_VITAL_TERMS = {
    "bp",
    "mmhg",
    "hr",
    "bpm",
    "spo2",
    "temperature",
    "temp",
    "pulse",
    "respiratory",
    "rr",
    "saturation",
    "weight",
    "heart",
    # Vietnamese.
    "mạch",
    "mach",
    "huyết",
    "huyet",
    "nhiệt",
    "nhiet",
    "áp",
}
_VITAL_PATTERNS = [
    re.compile(r"\b\d{2,3}\s*/\s*\d{2,3}\b"),  # blood pressure 120/80
    re.compile(r"\b\d{2,3}\s*(?:bpm|mmhg)\b", re.IGNORECASE),
    re.compile(r"\b(?:spo2|o2\s*sat)\b", re.IGNORECASE),
    re.compile(r"\b\d{2,3}(?:[.,]\d)?\s*°?\s*[cf]\b", re.IGNORECASE),  # temp
]
_DIAGNOSIS_TERMS = {
    "diagnosis",
    "diagnosed",
    "diagnose",
    "dx",
    "impression",
    "icd",
    # Vietnamese.
    "chẩn",
    "chan",
    "đoán",
    "doan",
}


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[0-9a-zA-ZÀ-ỹ]{2,}", str(text or "").lower())}


def _has_alnum(text: str) -> bool:
    return bool(re.search(r"[0-9a-zA-ZÀ-ỹ]", str(text or "")))


def _normalize(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def enumerate_statements(section_text: str) -> list[str]:
    """Split section text into discrete candidate statements (order-preserving).

    Splits on sentence/clause boundaries (line breaks, bullets, ``;`` and
    sentence terminators) and keeps any chunk that carries at least one
    alphanumeric token. Pure: it only reads the text.
    """

    chunks = re.split(r"[.!?\n\r;•]+", str(section_text or ""))
    statements: list[str] = []
    for chunk in chunks:
        stmt = _normalize(chunk)
        # Trim leading bullet/list markers that survive the split.
        stmt = re.sub(r"^[\-\*\u2022\.\s]+", "", stmt).strip()
        if stmt and _has_alnum(stmt):
            statements.append(stmt)
    return statements


def is_boilerplate(statement: str) -> bool:
    """True when a statement is scaffolding/heading rather than a factual claim."""

    norm = _normalize(statement)
    if not norm:
        return True
    label = norm.rstrip(":").strip().lower()
    if label in _BOILERPLATE_LABELS:
        return True
    tokens = _tokenize(norm)
    # A short label-like line with no numbers/clinical signal is a heading.
    if norm.endswith(":") and len(tokens) <= 3 and not any(c.isdigit() for c in norm):
        return True
    return False


def is_critical_safety(statement: str) -> bool:
    """Classify a statement as a critical-safety claim (med/dose/allergy/vital/dx)."""

    if _DOSE_PATTERN.search(statement):
        return True
    if any(p.search(statement) for p in _VITAL_PATTERNS):
        return True
    tokens = _tokenize(statement)
    for lexicon in (_MED_TERMS, _ALLERGY_TERMS, _VITAL_TERMS, _DIAGNOSIS_TERMS):
        if tokens & lexicon:
            return True
    return False


@dataclass(frozen=True, slots=True)
class GroundedStatement:
    """A single note statement with its grounding verdict + provenance."""

    statement: str
    section: str
    significant: bool
    critical_safety: bool
    grounded: bool
    supporting: Provenance
    status: str
    asserted: bool
    fact_check: str = "n/a"

    def as_dict(self) -> dict[str, Any]:
        return {
            "statement": self.statement,
            "section": self.section,
            "significant": self.significant,
            "critical_safety": self.critical_safety,
            "grounded": self.grounded,
            "supporting_span_ids": list(self.supporting.span_ids),
            "method": self.supporting.method,
            "status": self.status,
            "asserted": self.asserted,
            "fact_check": self.fact_check,
        }


@dataclass(frozen=True, slots=True)
class GroundingReport:
    """Additive grounding metadata for a note version (written to ``grounding_json``)."""

    enabled: bool
    statements: list[GroundedStatement] = field(default_factory=list)
    grounded_claim_rate: float = 0.0
    unverified_candidates: list[str] = field(default_factory=list)
    total_significant: int = 0
    grounded_significant: int = 0

    @classmethod
    def disabled(cls) -> GroundingReport:
        """An inert report for the flag-off / no-op path."""

        return cls(enabled=False)

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": "scribe-grounding-v1",
            "enabled": self.enabled,
            "statements": [s.as_dict() for s in self.statements],
            "grounded_claim_rate": round(float(self.grounded_claim_rate), 4),
            "unverified_candidates": list(self.unverified_candidates),
            "total_significant": self.total_significant,
            "grounded_significant": self.grounded_significant,
        }


class GroundingVerifier:
    """Verify a generated note's statements against transcript spans (Req 12).

    The verifier is gated by ``RAG_SCRIBE_GROUNDING_ENABLED`` (default off). When
    disabled it is a no-op. It never mutates the note or the transcript: it only
    reads the note's section text and the registry's spans and emits an additive
    :class:`GroundingReport`.
    """

    def __init__(self, *, enabled: bool | None = None) -> None:
        self._enabled = (
            bool(settings.rag_scribe_grounding_enabled) if enabled is None else bool(enabled)
        )

    @property
    def enabled(self) -> bool:
        return self._enabled

    def verify(
        self,
        note: _HasSections | Mapping[str, str],
        registry: SpanRegistry,
    ) -> GroundingReport:
        """Produce a :class:`GroundingReport` for ``note`` against ``registry`` spans.

        ``note`` may be a generated ``Note`` (anything with a ``sections`` mapping)
        or a plain ``{section_key: text}`` mapping. Returns an inert disabled report
        when the grounding flag is off.
        """

        if not self._enabled:
            return GroundingReport.disabled()

        sections = self._sections_of(note)
        spans = [s for s in registry.spans() if s.text.strip()]
        evidence_rows = [{"ref": s.span_id, "text": s.text} for s in spans]

        statements: list[GroundedStatement] = []
        unverified_candidates: list[str] = []
        total_significant = 0
        grounded_significant = 0

        for section_key, raw_text in sections.items():
            for raw in enumerate_statements(raw_text):
                evaluated = self._evaluate_statement(
                    statement=raw,
                    section=section_key,
                    spans=spans,
                    evidence_rows=evidence_rows,
                )
                statements.append(evaluated)
                if not evaluated.significant:
                    continue
                total_significant += 1
                if evaluated.grounded:
                    grounded_significant += 1
                elif evaluated.critical_safety:
                    unverified_candidates.append(evaluated.statement)

        rate = grounded_significant / total_significant if total_significant else 0.0
        return GroundingReport(
            enabled=True,
            statements=statements,
            grounded_claim_rate=rate,
            unverified_candidates=unverified_candidates,
            total_significant=total_significant,
            grounded_significant=grounded_significant,
        )

    # --- internals ---------------------------------------------------------

    @staticmethod
    def _sections_of(note: _HasSections | Mapping[str, str]) -> Mapping[str, str]:
        sections = getattr(note, "sections", note)
        if not isinstance(sections, Mapping):
            return {}
        return sections

    def _evaluate_statement(
        self,
        *,
        statement: str,
        section: str,
        spans: list[TranscriptSpan],
        evidence_rows: list[dict[str, str]],
    ) -> GroundedStatement:
        if is_boilerplate(statement):
            return GroundedStatement(
                statement=statement,
                section=section,
                significant=False,
                critical_safety=False,
                grounded=False,
                supporting=Provenance(),
                status=STATUS_BOILERPLATE,
                asserted=True,
            )

        critical = is_critical_safety(statement)
        supporting_ids = self._entailing_spans(statement, spans)
        grounded = bool(supporting_ids)
        fact_check = self._fact_check_verdict(statement, evidence_rows)

        if grounded:
            status = STATUS_GROUNDED
            asserted = True
        else:
            status = STATUS_UNVERIFIED
            # Req 12.5: an ungrounded critical-safety statement is NEVER asserted;
            # it is surfaced only as an unverified candidate. Non-critical ungrounded
            # statements stay flagged `unverified` for clinician review (Req 12.4).
            asserted = not critical

        return GroundedStatement(
            statement=statement,
            section=section,
            significant=True,
            critical_safety=critical,
            grounded=grounded,
            supporting=Provenance(span_ids=supporting_ids, method="nli"),
            status=status,
            asserted=asserted,
            fact_check=fact_check,
        )

    @staticmethod
    def _entailing_spans(statement: str, spans: list[TranscriptSpan]) -> list[str]:
        """Span ids that entail ``statement`` under the NLI claim-verification pass.

        Reuses ``factcheck.nli_verifier.verify_claims`` per span so the grounded
        decision is exactly "at least one transcript span entails it" (Req 12.3).
        """

        supporting: list[str] = []
        for span in spans:
            text = span.text.strip()
            if not text:
                continue
            verdicts = verify_claims(
                claims=[statement],
                evidence_rows=[{"ref": span.span_id, "text": text}],
            )
            if verdicts and verdicts[0].support_status == "supported":
                supporting.append(span.span_id)
        return supporting

    @staticmethod
    def _fact_check_verdict(statement: str, evidence_rows: list[dict[str, str]]) -> str:
        """Corroborating FIDES fact-check verdict (reuses ``run_fides_lite``).

        The grounded/ungrounded decision is authoritative from the NLI entailment
        pass; this verdict ("pass" | "warn" | "fail" | "n/a") is additive
        traceability metadata applying the FIDES CRITICAL-block discipline.
        """

        try:
            result = run_fides_lite(
                answer=statement,
                retrieved_context=[
                    {"id": row["ref"], "text": row["text"]} for row in evidence_rows
                ],
            )
            return result.verdict
        except Exception:  # noqa: BLE001 - additive pass never blocks
            return "n/a"
