from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import logging
import random
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import perf_counter, sleep
from typing import Any
import unicodedata
import urllib.error
import urllib.request
from uuid import uuid4

from clara_ml.config import settings
from clara_ml.factcheck import FactCheckResult, run_fides_lite
from clara_ml.factcheck.nli_verifier import classify_claim
from clara_ml.llm.deepseek_client import DeepSeekClient
from clara_ml.rag.pipeline import RagPipelineP1
from clara_ml.rag.retrieval.source_router import (
    SourceRouterDecision,
    decide_source_route,
    to_metadata_payload as source_route_metadata_payload,
)
from clara_ml.rag.retrieval.text_utils import analyze_query_profile, query_terms
from clara_ml.routing import P1RoleIntentRouter

logger = logging.getLogger(__name__)

router = P1RoleIntentRouter()


@dataclass(frozen=True)
class PlanStep:
    step: str
    objective: str
    output: str


@dataclass(frozen=True)
class Citation:
    source_id: str
    source: str
    title: str
    url: str
    relevance: str
    # Additive, flag-gated provenance fields (R6.2 recency/trust ranking, R11.2
    # claim-to-study traceability). They default to None and are stripped from the
    # emitted payload when unset so the legacy citation shape is preserved (R20.2).
    study_id: str | None = None  # PMID|DOI|RXCUI
    source_type: str | None = None
    trust_tier: int | None = None
    published_at: str | None = None  # publication / effective date


@dataclass(frozen=True)
class PicoFrame:
    """Structured EBM question framing (Population, Intervention, Comparison, Outcome).

    Every element is derived from the submitted query; the orchestrator never
    fabricates an element value. When any element cannot be determined the
    extractor raises :class:`PicoIncompleteError` naming the missing element (R7.2).
    """

    population: str
    intervention: str
    comparison: str
    outcome: str

    def as_payload(self) -> dict[str, str]:
        return {
            "population": self.population,
            "intervention": self.intervention,
            "comparison": self.comparison,
            "outcome": self.outcome,
        }


class PicoIncompleteError(ValueError):
    """Raised when a PICO element cannot be determined from a clinical query (R7.2)."""

    def __init__(self, element: str) -> None:
        self.element = element
        super().__init__(f"PICO element could not be determined: {element}")


@dataclass(frozen=True)
class CitationRef:
    """A Citation_Registry entry carrying per-citation study provenance (R11.2, R11.4).

    Every ``CitationRef`` is built from a *retrieved* source, so a citation that does
    not correspond to a retrieved source is never emitted (R11.5). ``study_id`` is a
    PMID/DOI/RXCUI (or the backing source id when no scholarly identifier is present),
    ``trust_tier`` is the ``{1..4}`` authority band, and ``published_at`` is the
    publication/effective date (``None`` when unknown).
    """

    citation_id: str
    study_id: str
    source_type: str
    trust_tier: int
    published_at: str | None

    def as_payload(self) -> dict[str, Any]:
        return {
            "citation_id": self.citation_id,
            "study_id": self.study_id,
            "source_type": self.source_type,
            "trust_tier": self.trust_tier,
            "published_at": self.published_at,
        }


@dataclass(frozen=True)
class TracedClaim:
    """A synthesized claim linked to its specific supporting citation id(s) (R11.1).

    ``citation_ids`` is always non-empty and every id resolves into the Citation
    Registry: a claim with no supporting retrieved source is suppressed before a
    ``TracedClaim`` is ever built, so a fabricated citation can never be attached
    (R11.5, R11.6). ``certainty`` carries the GRADE label when R8 is enabled.
    """

    claim: str
    citation_ids: list[str]
    verdict: str
    certainty: str | None = None

    def as_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "claim": self.claim,
            "citation_ids": list(self.citation_ids),
            "verdict": self.verdict,
        }
        if self.certainty is not None:
            payload["certainty"] = self.certainty
        return payload


# Per-citation provenance fields that are additive and only emitted when populated.
_OPTIONAL_CITATION_KEYS: tuple[str, ...] = (
    "study_id",
    "source_type",
    "trust_tier",
    "published_at",
)


def _citation_as_payload(citation: Citation) -> dict[str, Any]:
    """Serialize a :class:`Citation`, omitting unset additive provenance fields.

    The legacy citation payload only ever exposed ``source_id``/``source``/``title``/
    ``url``/``relevance``. The new provenance fields (``study_id``, ``source_type``,
    ``trust_tier``, ``published_at``) default to ``None``; when they are unset they are
    stripped here so a flags-off run emits the byte-for-byte legacy citation shape
    (R6.2, R11.2, R20.2).
    """

    payload = asdict(citation)
    for key in _OPTIONAL_CITATION_KEYS:
        if payload.get(key) is None:
            payload.pop(key, None)
    return payload


def _build_tier2_optional_payload(
    *,
    pico_frame: PicoFrame | None = None,
    citation_registry: list[dict[str, Any]] | None = None,
    traced_claims: list[dict[str, Any]] | None = None,
    grade: list[dict[str, Any]] | None = None,
    consensus: list[dict[str, Any]] | None = None,
    conflicting_evidence: list[dict[str, Any]] | None = None,
    subquestions: list[str] | None = None,
    gap_fill_passes: int | None = None,
    output_profile: str | None = None,
    disclaimer_present: bool | None = None,
) -> dict[str, Any]:
    """Assemble the additive, flag-gated Tier2 result fields.

    Each key is included **only** when its corresponding stage produced a value
    (i.e. when its feature flag was on). When an artifact is absent the key is
    omitted entirely, so a run with every new flag disabled emits the legacy result
    shape unchanged (R20.2). Downstream tasks populate these arguments as their
    stages land; this builder is the single carrier for all of them.

    Fields carried (design "Tier2 result payload (additive fields)"):
      * ``pico`` (R7.3)            * ``consensus`` (R9.1)
      * ``citation_registry`` (R11.4)   * ``conflicting_evidence`` (R9.4)
      * ``traced_claims`` (R11.1)       * ``subquestions`` (R4.4)
      * ``grade`` (R8.1)                * ``gap_fill_passes`` (R5.4)
      * ``output_profile`` (R14)        * ``disclaimer_present`` (R14.5/R14.6)
    """

    optional: dict[str, Any] = {}
    if pico_frame is not None:
        optional["pico"] = pico_frame.as_payload()
    if citation_registry is not None:
        optional["citation_registry"] = citation_registry
    if traced_claims is not None:
        optional["traced_claims"] = traced_claims
    if grade is not None:
        optional["grade"] = grade
    if consensus is not None:
        optional["consensus"] = consensus
    if conflicting_evidence is not None:
        optional["conflicting_evidence"] = conflicting_evidence
    if subquestions is not None:
        optional["subquestions"] = subquestions
    if gap_fill_passes is not None:
        optional["gap_fill_passes"] = gap_fill_passes
    if output_profile is not None:
        optional["output_profile"] = output_profile
    if disclaimer_present is not None:
        optional["disclaimer_present"] = disclaimer_present
    return optional


# R14 Role-Adaptive Output: each user role maps to exactly one output profile so a
# single run can never blend profiles (`normal` -> plain language, `researcher` ->
# evidence pack, `doctor` -> IMRaD clinical brief). Unmapped/unknown roles (e.g.
# `admin`) fall back to the safest plain-language profile so exactly one profile is
# always selected (R14.1-R14.3, Property 27).
_ROLE_OUTPUT_PROFILE_MAP: dict[str, str] = {
    "normal": "normal",
    "researcher": "researcher",
    "doctor": "doctor",
}
_DEFAULT_OUTPUT_PROFILE = "normal"

# R14.5/R20.5 decision-support disclaimer asset. Every role's output retains a
# disclaimer stating outputs are decision support only (not treatment orders) and
# that CLARA-Care is not a medical device or EMR. Keyed by the resolved answer
# language (Vietnamese default unless ``ui_language == "en"``, R14.4).
_DECISION_SUPPORT_DISCLAIMER_BY_LANGUAGE: dict[str, str] = {
    "vi": (
        "> **Tuyên bố hỗ trợ quyết định:** Nội dung này chỉ nhằm hỗ trợ quyết định, "
        "không phải là chỉ định điều trị. CLARA-Care không phải là thiết bị y tế hay "
        "hệ thống bệnh án điện tử (EMR)."
    ),
    "en": (
        "> **Decision-support notice:** This output is decision support only and is "
        "not a treatment order. CLARA-Care is not a medical device or EMR."
    ),
}


def _resolve_output_profile(role: str | None) -> str:
    """Select exactly one role output profile (R14.1-R14.3, Property 27).

    Mapping is total: every role resolves to exactly one of ``{normal, researcher,
    doctor}`` and unmapped roles fall back to the plain-language ``normal`` profile,
    so the selected profile can never blend content from other profiles.
    """

    normalized = str(role or "").strip().lower()
    return _ROLE_OUTPUT_PROFILE_MAP.get(normalized, _DEFAULT_OUTPUT_PROFILE)


def _load_decision_support_disclaimer(answer_language: str) -> str | None:
    """Return the decision-support disclaimer text for the answer language.

    Returns ``None`` when the disclaimer asset is unavailable so the caller can
    deliver output without it and record the omission (R14.6). The language is
    resolved to ``en`` only when ``answer_language`` is ``en``; otherwise the
    Vietnamese disclaimer is used (R14.4).
    """

    language = "en" if str(answer_language or "").strip().lower() == "en" else "vi"
    try:
        return _DECISION_SUPPORT_DISCLAIMER_BY_LANGUAGE[language]
    except (KeyError, TypeError):  # pragma: no cover - asset unavailable path
        return None


def _apply_role_adaptive_output(
    answer_markdown: str,
    *,
    role: str | None,
    answer_language: str,
) -> tuple[str, str, bool]:
    """Apply the R14 role-adaptive output profile and disclaimer handling.

    Selects exactly one output profile for ``role`` and ensures the decision-support
    disclaimer is present in the delivered output for every profile whenever its
    asset is available (R14.5). When the asset is unavailable the output is delivered
    unchanged and the omission is recorded via ``disclaimer_present=False`` (R14.6).

    Returns ``(answer_markdown, output_profile, disclaimer_present)``.
    """

    output_profile = _resolve_output_profile(role)
    disclaimer = _load_decision_support_disclaimer(answer_language)
    disclaimer_present = disclaimer is not None
    if disclaimer and disclaimer not in answer_markdown:
        answer_markdown = f"{answer_markdown.rstrip()}\n\n{disclaimer}\n"
    return answer_markdown, output_profile, disclaimer_present


_REQUIRED_MARKDOWN_HEADINGS = (
    "## Kết luận nhanh",
    "## Phân tích chi tiết",
    "## Khuyến nghị an toàn",
)

_REQUIRED_DEEP_MARKDOWN_HEADINGS = (
    "## Kết luận nhanh",
    "## Kế hoạch nghiên cứu",
    "## Tóm tắt điều hành",
    "## Bối cảnh lâm sàng áp dụng",
    "## Phân tích chi tiết",
    "## Bảng tổng hợp bằng chứng",
    "## Khuyến nghị ứng dụng thực hành",
    "## Giới hạn, sai số và rủi ro pháp lý",
)

_REQUIRED_DEEP_BETA_MARKDOWN_HEADINGS = (
    "## Kết luận nhanh",
    "## Kế hoạch nghiên cứu",
    "## Tóm tắt điều hành",
    "## Câu hỏi nghiên cứu (PICO)",
    "## Phương pháp truy xuất & tiêu chí chọn lọc",
    "## Hồ sơ bằng chứng & chất lượng nguồn",
    "## Tổng hợp phát hiện chính",
    "## Chuỗi lập luận bằng chứng",
    "## Phản biện bằng chứng đối nghịch",
    "## Ứng dụng lâm sàng theo nhóm bệnh nhân",
    "## Ma trận quyết định an toàn",
    "## Kế hoạch theo dõi sau tư vấn",
    "## Giới hạn, sai số và rủi ro pháp lý",
)
_REQUIRED_DEEP_DEDUP_HEADINGS: tuple[str, ...] = tuple(
    dict.fromkeys((*_REQUIRED_DEEP_MARKDOWN_HEADINGS, *_REQUIRED_DEEP_BETA_MARKDOWN_HEADINGS))
)

_DEFAULT_DEEP_PASS_CAP = 20
_DEEP_BETA_PASS_CAP = 36
_DEFAULT_EVIDENCE_HANDOFF_PROFILE: dict[str, int] = {
    "citation_context_rows": 10,
    "citation_trace_rows": 10,
    "uploaded_document_rows": 8,
    "reasoning_pass_summaries": 12,
    "reasoning_evidence_rows": 20,
    "verification_pass_summaries": 18,
    "verification_evidence_rows": 28,
    "verification_reasoning_nodes": 20,
    "verification_reasoning_chain_per_node": 2,
    "report_citations": 18,
    "report_pass_summaries": 14,
    "report_reasoning_chain_cards": 18,
}
_DEEP_BETA_EVIDENCE_HANDOFF_PROFILE: dict[str, int] = {
    **_DEFAULT_EVIDENCE_HANDOFF_PROFILE,
    "citation_context_rows": 24,
    "citation_trace_rows": 24,
    "uploaded_document_rows": 10,
    "reasoning_pass_summaries": 24,
    "reasoning_evidence_rows": 40,
    "verification_pass_summaries": 28,
    "verification_evidence_rows": 48,
    "verification_reasoning_nodes": 24,
    "verification_reasoning_chain_per_node": 3,
    "report_citations": 30,
    "report_pass_summaries": 24,
    "report_reasoning_chain_cards": 28,
}
_DEEP_BETA_REASONING_STAGE_ORDER = (
    "deep_beta_scope",
    "deep_beta_hypothesis_map",
    "deep_beta_retrieval_budget",
    "deep_beta_multi_pass_retrieval",
    "deep_beta_evidence_audit",
    "deep_beta_claim_graph",
    "deep_beta_counter_evidence_scan",
    "deep_beta_guideline_alignment",
    "deep_beta_risk_stratification",
    "deep_beta_gap_fill",
    "deep_beta_evidence_verification",
    "deep_beta_chain_synthesis",
    "deep_beta_report_synthesis",
    "deep_beta_quality_gate",
    "deep_beta_chain_verification",
)
_DEEP_BETA_PARALLEL_REASONING_NODES: tuple[tuple[str, str], ...] = (
    (
        "deep_beta_evidence_audit",
        "Audit evidence coverage quality, identify weak sources and unresolved questions.",
    ),
    (
        "deep_beta_claim_graph",
        "Build claim/conflict graph across passes and flag contradiction hypotheses.",
    ),
    (
        "deep_beta_counter_evidence_scan",
        "Find strongest counter-evidence, adverse subgroup exceptions, and unresolved caveats.",
    ),
    (
        "deep_beta_guideline_alignment",
        "Check alignment/misalignment between retrieved evidence and guideline-level recommendations.",
    ),
    (
        "deep_beta_risk_stratification",
        "Stratify risk signals by age/comorbidity/polypharmacy and highlight red-flag trajectories.",
    ),
    (
        "deep_beta_gap_fill",
        "Propose high-yield gap-fill retrieval actions to improve coverage.",
    ),
)
#: Internal pipeline / planner / telemetry identifiers that must NEVER appear in
#: the user-facing answer body (Requirement 3.3 / Property P9). Combines the
#: deep_beta reasoning-stage identifiers with the legacy plan-step / router /
#: node labels used elsewhere in the pipeline. A defense-in-depth inline scrub
#: (``_strip_internal_pipeline_tags``) removes any of these that leak past the
#: structured section removal, including bracketed (``[scope_question]``) and
#: execution-log arrow-chain forms.
_INTERNAL_PIPELINE_TAGS: frozenset[str] = frozenset(
    {
        *_DEEP_BETA_REASONING_STAGE_ORDER,
        *(name for name, _ in _DEEP_BETA_PARALLEL_REASONING_NODES),
        "deep_beta_router",
        "deep_beta_gate",
        "deep_beta_planner",
        "deep_beta_loop",
        "beta_hypothesis_graph",
        "deep_beta_hypothesis",
        "scope_question",
        "retrieval_budgeting",
        "reasoning_chain_audit",
        "iterative_gap_fill",
        "collect_evidence",
        "query_decomposition",
        "query_plan",
        "keyword_filter",
        "deep_research",
        "retrieval_orchestrator",
    }
)
#: Alternation of the known internal tags (longest-first so e.g.
#: ``deep_beta_scope`` wins over a hypothetical ``deep_beta`` prefix) plus a
#: catch-all for any ``deep_beta_<suffix>`` snake_case identifier, which is
#: always an internal stage label and never user-facing prose.
_INTERNAL_PIPELINE_TAG_ALTERNATION = "|".join(
    re.escape(tag) for tag in sorted(_INTERNAL_PIPELINE_TAGS, key=len, reverse=True)
)
_INTERNAL_PIPELINE_TAG_TOKEN_RE = re.compile(
    rf"(?<![0-9A-Za-z_])(?:{_INTERNAL_PIPELINE_TAG_ALTERNATION}|deep_beta_[a-z][a-z0-9_]*)(?![0-9A-Za-z_])",
    flags=re.IGNORECASE,
)
#: A bracketed planner tag, e.g. ``[scope_question]`` / ``[deep_beta_scope]``.
_INTERNAL_PIPELINE_TAG_BRACKETED_RE = re.compile(
    rf"\[\s*(?:{_INTERNAL_PIPELINE_TAG_ALTERNATION}|deep_beta_[a-z][a-z0-9_]*)\s*\]",
    flags=re.IGNORECASE,
)


def _strip_internal_pipeline_tags(text: str) -> str:
    """Remove internal pipeline / planner / telemetry labels from answer text.

    Defense-in-depth for Requirement 3.3 / Property P9: structured telemetry
    sections are removed by heading elsewhere, but this scrub also catches
    internal tags that leak *inline* (mid-paragraph, in a stray bullet, or as an
    execution-log arrow chain) so they never reach the reader. Operates purely
    on user-facing text and leaves substantive clinical prose untouched.
    """

    if not text or not text.strip():
        return text

    # 1) Drop bracketed planner tags entirely (e.g. "[scope_question]").
    scrubbed = _INTERNAL_PIPELINE_TAG_BRACKETED_RE.sub("", text)

    cleaned_lines: list[str] = []
    for line in scrubbed.split("\n"):
        # 2) Drop execution-log arrow-chain / label-only lines, e.g.
        #    "deep_beta_scope -> retrieval_budgeting -> deep_beta_evidence_audit"
        #    or a bullet that is nothing but internal labels and separators.
        stripped_markers = re.sub(r"^[\s>*\-•]+", "", line)
        residual = _INTERNAL_PIPELINE_TAG_TOKEN_RE.sub("", stripped_markers)
        residual = re.sub(r"[\s>→\-|/,:;.]+", "", residual)
        if stripped_markers.strip() and not residual:
            # The line carried internal tags and nothing else of substance.
            continue
        # 3) Strip residual inline tags from otherwise-substantive lines.
        line = _INTERNAL_PIPELINE_TAG_TOKEN_RE.sub("", line)
        cleaned_lines.append(line)

    result = "\n".join(cleaned_lines)
    # Tidy up artifacts left by inline removal (double spaces, empty arrows).
    result = re.sub(r"[ \t]{2,}", " ", result)
    result = re.sub(r"[ \t]+([,.;:])", r"\1", result)
    return result


_ALLOWED_RETRIEVAL_ROUTES = {
    "internal-heavy",
    "scientific-heavy",
    "web-assisted",
    "file-grounded",
}
_ENGLISH_SOURCE_KEYS = {
    "pubmed",
    "europepmc",
    "openalex",
    "semantic_scholar",
    "clinicaltrials",
    "openfda",
    "dailymed",
    "rxnorm",
}
_VIETNAMESE_SOURCE_KEYS = {
    "vn_moh",
    "vn_kcb",
    "vn_canhgiacduoc",
    "vn_vbpl_byt",
    "vn_dav",
    "davidrug",
}
_EN_GENERIC_KEYWORD_HINTS = {
    "interaction",
    "guideline",
    "guidelines",
    "evidence",
    "review",
    "trial",
    "safety",
    "contraindication",
    "risk",
    "monitoring",
    "recommendation",
}
_VI_GENERIC_KEYWORD_HINTS = {
    "tuong",
    "tac",
    "thuoc",
    "benh",
    "nguoi",
    "cao",
    "tuoi",
    "huong",
    "dan",
    "nguy",
    "co",
    "xuat",
    "huyet",
    "dieu",
    "tri",
    "theo",
    "doi",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalized_identifier(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    compact = re.sub(r"\s+", "-", text)
    return compact[:160]


def _resolve_trace_identifiers(payload: dict[str, Any]) -> tuple[str, str]:
    metadata_obj = payload.get("metadata")
    metadata = metadata_obj if isinstance(metadata_obj, dict) else {}
    trace_obj = payload.get("trace")
    trace = trace_obj if isinstance(trace_obj, dict) else {}

    trace_id = (
        _normalized_identifier(payload.get("trace_id"))
        or _normalized_identifier(metadata.get("trace_id"))
        or _normalized_identifier(trace.get("trace_id"))
    )
    run_id = (
        _normalized_identifier(payload.get("run_id"))
        or _normalized_identifier(metadata.get("run_id"))
        or _normalized_identifier(trace.get("run_id"))
        or _normalized_identifier(payload.get("request_id"))
        or _normalized_identifier(metadata.get("request_id"))
    )

    if trace_id and run_id:
        return trace_id, run_id
    if run_id and not trace_id:
        return f"tier2-trace-{run_id}", run_id
    if trace_id and not run_id:
        return trace_id, f"tier2-run-{trace_id}"

    seed = uuid4().hex
    return f"tier2-trace-{seed}", f"tier2-run-{seed}"


def _resolve_evidence_handoff_profile(research_mode: str | None = None) -> dict[str, int]:
    mode = str(research_mode or "fast").strip().lower()
    if mode == "deep_beta":
        return _DEEP_BETA_EVIDENCE_HANDOFF_PROFILE
    return _DEFAULT_EVIDENCE_HANDOFF_PROFILE


def _parse_event_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _normalize_topic(payload: dict[str, Any]) -> str:
    query = str(payload.get("query") or payload.get("message") or "").strip()
    if query:
        return query
    return "general medication safety in primary care"


def _normalize_research_mode(payload: dict[str, Any]) -> str:
    raw_mode = (
        str(
            payload.get("research_mode")
            or payload.get("mode")
            or payload.get("reasoning_mode")
            or "fast"
        )
        .strip()
        .lower()
    )
    if raw_mode in {"deep_beta", "deep-beta", "deepbeta", "beta"}:
        return "deep_beta"
    if raw_mode in {"deep", "deep_research", "long"}:
        return "deep"
    return "fast"


def _normalize_retrieval_stack_mode(payload: dict[str, Any]) -> str:
    metadata_obj = payload.get("metadata")
    metadata = metadata_obj if isinstance(metadata_obj, dict) else {}
    raw_mode = (
        str(
            payload.get("retrieval_stack_mode")
            or payload.get("stack_mode")
            or metadata.get("retrieval_stack_mode")
            or metadata.get("stack_mode")
            or "auto"
        )
        .strip()
        .lower()
    )
    if raw_mode in {"full", "full_stack", "full-stack"}:
        return "full"
    return "auto"


def _normalize_answer_language(payload: dict[str, Any]) -> str:
    metadata_obj = payload.get("metadata")
    metadata = metadata_obj if isinstance(metadata_obj, dict) else {}
    raw_value = (
        str(
            payload.get("ui_language")
            or payload.get("answer_language")
            or metadata.get("ui_language")
            or metadata.get("answer_language")
            or ""
        )
        .strip()
        .lower()
    )
    if raw_value in {"en", "english"}:
        return "en"
    return "vi"


def _normalize_personal_mode(payload: dict[str, Any]) -> bool:
    value = payload.get("personal_mode")
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _extract_personal_context(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("personal_context")
    return value if isinstance(value, dict) else {}


def _compact_personal_text(value: Any, *, limit: int = 120) -> str:
    text = " ".join(str(value or "").split()).strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def _build_personal_context_suffix(
    personal_context: dict[str, Any],
    *,
    answer_language: str,
) -> str:
    profile = personal_context.get("profile") if isinstance(personal_context.get("profile"), dict) else {}
    allergies = personal_context.get("allergies") if isinstance(personal_context.get("allergies"), list) else []
    conditions = personal_context.get("conditions") if isinstance(personal_context.get("conditions"), list) else []
    medications = personal_context.get("medications") if isinstance(personal_context.get("medications"), list) else []
    cabinet = (
        personal_context.get("medicine_cabinet")
        if isinstance(personal_context.get("medicine_cabinet"), dict)
        else {}
    )
    cabinet_items = cabinet.get("items") if isinstance(cabinet.get("items"), list) else []

    allergy_names = [
        _compact_personal_text(item.get("name"), limit=100)
        for item in allergies[:12]
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]
    condition_names = [
        _compact_personal_text(item.get("name"), limit=100)
        for item in conditions[:12]
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]
    medication_rows = []
    for raw in medications[:18]:
        if not isinstance(raw, dict):
            continue
        med_name = _compact_personal_text(raw.get("name"), limit=100)
        if not med_name:
            continue
        med_dose = _compact_personal_text(raw.get("dose"), limit=64)
        med_frequency = _compact_personal_text(raw.get("frequency"), limit=64)
        parts = [med_name]
        if med_dose:
            parts.append(med_dose)
        if med_frequency:
            parts.append(med_frequency)
        medication_rows.append(" - ".join(parts))

    cabinet_rows = []
    for raw in cabinet_items[:18]:
        if not isinstance(raw, dict):
            continue
        med_name = _compact_personal_text(raw.get("name"), limit=100)
        if not med_name:
            continue
        med_dose = _compact_personal_text(raw.get("dose"), limit=64)
        if med_dose:
            cabinet_rows.append(f"{med_name} ({med_dose})")
        else:
            cabinet_rows.append(med_name)

    profile_lines: list[str] = []
    if profile:
        full_name = _compact_personal_text(profile.get("full_name"), limit=80)
        date_of_birth = _compact_personal_text(profile.get("date_of_birth"), limit=20)
        gender = _compact_personal_text(profile.get("gender"), limit=32)
        blood_type = _compact_personal_text(profile.get("blood_type"), limit=16)
        if full_name:
            profile_lines.append(full_name)
        if date_of_birth:
            profile_lines.append(f"DOB: {date_of_birth}")
        if gender:
            profile_lines.append(f"Gender: {gender}")
        if blood_type:
            profile_lines.append(f"Blood: {blood_type}")

    if answer_language == "en":
        lines = [
            "### Personal Context (PHR + Medicine Cabinet)",
            "Use this context to personalize recommendations, contraindications, and monitoring.",
        ]
        if profile_lines:
            lines.append(f"- Profile: {', '.join(profile_lines)}")
        if allergy_names:
            lines.append(f"- Allergies: {', '.join(allergy_names)}")
        if condition_names:
            lines.append(f"- Conditions: {', '.join(condition_names)}")
        if medication_rows:
            lines.append(f"- Medications in PHR: {'; '.join(medication_rows)}")
        if cabinet_rows:
            lines.append(f"- Medicines from cabinet: {'; '.join(cabinet_rows)}")
    else:
        lines = [
            "### Bối Cảnh Cá Nhân (PHR + Tủ Thuốc)",
            "Dùng ngữ cảnh này để cá thể hóa khuyến nghị, chống chỉ định và kế hoạch theo dõi.",
        ]
        if profile_lines:
            lines.append(f"- Hồ sơ: {', '.join(profile_lines)}")
        if allergy_names:
            lines.append(f"- Dị ứng: {', '.join(allergy_names)}")
        if condition_names:
            lines.append(f"- Bệnh nền: {', '.join(condition_names)}")
        if medication_rows:
            lines.append(f"- Thuốc trong PHR: {'; '.join(medication_rows)}")
        if cabinet_rows:
            lines.append(f"- Thuốc trong tủ thuốc: {'; '.join(cabinet_rows)}")

    return "\n".join(lines).strip()


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
    return default


def _coerce_optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
    return None


def _ascii_fold(text: str) -> str:
    normalized = unicodedata.normalize("NFD", str(text or ""))
    without_marks = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return without_marks.lower()


def _detect_language_hint(text: str) -> tuple[bool, bool, str]:
    lowered = str(text or "").lower()
    has_vietnamese_marks = bool(
        re.search(
            r"[àáạảãâầấậẩẫăằắặẳẵđèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹ]",
            lowered,
        )
    )
    has_english_markers = bool(
        re.search(
            r"\b(interaction|guideline|evidence|review|trial|safety|contraindication|bleeding)\b",
            lowered,
        )
    )
    if has_vietnamese_marks and has_english_markers:
        return has_vietnamese_marks, has_english_markers, "mixed"
    if has_vietnamese_marks:
        return has_vietnamese_marks, has_english_markers, "vi"
    return has_vietnamese_marks, has_english_markers, "en"


def _is_comparison_query(text: str) -> bool:
    folded = _ascii_fold(text)
    markers = (
        "so sanh",
        "so sánh",
        "khac nhau",
        "khác nhau",
        "uu nhuoc",
        "ưu nhược",
        "pros and cons",
        "advantages and disadvantages",
        "compare",
        "comparison",
        "versus",
        " vs ",
    )
    return any(marker in folded for marker in markers)


def _is_nutrition_diet_query(text: str) -> bool:
    folded = _ascii_fold(text)
    markers = (
        "che do an",
        "chế độ ăn",
        "dinh duong",
        "dinh dưỡng",
        "nutrition",
        "diet",
        "dash",
        "dia trung hai",
        "địa trung hải",
        "mediterranean",
        "an uong",
        "ăn uống",
    )
    return any(marker in folded for marker in markers)


# --- PICO-structured question framing (R7) -------------------------------------------------
# Marker vocabularies are folded to ASCII (accent-insensitive, lowercase) so they match
# both Vietnamese (with/without diacritics) and English clinical phrasing. Element values
# returned by the extractor are always drawn from the query content (never fabricated).

_PICO_CLINICAL_MARKERS: tuple[str, ...] = (
    "dieu tri",
    "phac do",
    "lieu",
    "lieu luong",
    "thuoc",
    "benh nhan",
    "benh",
    "lam sang",
    "chan doan",
    "tien luong",
    "phong ngua",
    "phau thuat",
    "tiem chung",
    "vaccine",
    "vac xin",
    "hieu qua",
    "tac dung",
    "nguy co",
    "bien chung",
    "treatment",
    "therapy",
    "therapies",
    "drug",
    "medication",
    "dose",
    "dosage",
    "regimen",
    "clinical",
    "patient",
    "patients",
    "disease",
    "diagnosis",
    "prognosis",
    "prevention",
    "surgery",
    "efficacy",
    "symptom",
)

_PICO_POPULATION_MARKERS: tuple[str, ...] = (
    "benh nhan",
    "nguoi benh",
    "nguoi cao tuoi",
    "nguoi gia",
    "nguoi lon",
    "tre em",
    "tre nho",
    "tre so sinh",
    "phu nu mang thai",
    "phu nu co thai",
    "thai phu",
    "phu nu",
    "nam gioi",
    "patient",
    "patients",
    "adult",
    "adults",
    "child",
    "children",
    "infant",
    "neonate",
    "elderly",
    "women",
    "men",
    "pregnant",
    "population",
)

_PICO_INTERVENTION_MARKERS: tuple[str, ...] = (
    "dieu tri",
    "phac do",
    "su dung",
    "dung",
    "uong",
    "lieu",
    "thuoc",
    "tiem",
    "phau thuat",
    "can thiep",
    "vaccine",
    "vac xin",
    "treatment",
    "therapy",
    "drug",
    "medication",
    "dose",
    "regimen",
    "intervention",
    "administer",
    "surgery",
    "procedure",
)

_PICO_COMPARISON_MARKERS: tuple[str, ...] = (
    "so voi",
    "so sanh",
    "thay vi",
    "doi chung",
    "khac nhau",
    "versus",
    " vs ",
    " vs.",
    "compared",
    "comparison",
    "compare",
    "placebo",
    "control",
    "alternative",
    "standard of care",
)

_PICO_OUTCOME_MARKERS: tuple[str, ...] = (
    "hieu qua",
    "ket qua",
    "ket cuc",
    "ty le",
    "nguy co",
    "giam",
    "tang",
    "cai thien",
    "tac dung phu",
    "bien co",
    "bien chung",
    "tu vong",
    "song con",
    "an toan",
    "xuat huyet",
    "chay mau",
    "kiem soat",
    "outcome",
    "outcomes",
    "risk",
    "mortality",
    "morbidity",
    "survival",
    "efficacy",
    "effect",
    "effectiveness",
    "reduction",
    "safety",
    "adverse",
    "response",
    "remission",
    "control",
)

_PICO_AGE_PATTERN = re.compile(r"\b\d{1,3}\s*(?:tuoi|tuổi|year|years|yo|yrs)\b", re.IGNORECASE)


def _is_clinical_query(text: str) -> bool:
    """Heuristically decide whether a query is a clinical question eligible for PICO (R7.1)."""

    folded = _ascii_fold(text)
    if not folded.strip():
        return False
    if any(marker in folded for marker in _PICO_CLINICAL_MARKERS):
        return True
    if _PICO_AGE_PATTERN.search(text):
        return True
    # Recognized medications also signal a clinical question.
    profile = analyze_query_profile(str(text or ""))
    return bool(profile.get("primary_drug"))


def _pico_detect_markers(folded: str, markers: tuple[str, ...]) -> list[str]:
    found: list[str] = []
    for marker in markers:
        if marker in folded and marker.strip() not in found:
            found.append(marker.strip())
    return found


def _extract_pico_frame(text: str) -> PicoFrame:
    """Extract a PICO structure from a clinical query.

    Returns a complete :class:`PicoFrame` whose element values are derived from the
    query, or raises :class:`PicoIncompleteError` naming the first undetermined element.
    No element value is ever fabricated (R7.2).
    """

    folded = _ascii_fold(text)
    profile = analyze_query_profile(str(text or ""))
    primary_drug = str(profile.get("primary_drug") or "").strip()
    co_drugs = [str(item).strip() for item in (profile.get("co_drugs") or []) if str(item).strip()]

    # Population.
    population_markers = _pico_detect_markers(folded, _PICO_POPULATION_MARKERS)
    age_match = _PICO_AGE_PATTERN.search(text)
    if age_match:
        population_markers.append(" ".join(age_match.group(0).split()).lower())
    population = ", ".join(dict.fromkeys(population_markers)).strip()
    if not population:
        raise PicoIncompleteError("population")

    # Intervention.
    intervention_parts: list[str] = []
    if primary_drug:
        intervention_parts.append(primary_drug)
    intervention_parts.extend(_pico_detect_markers(folded, _PICO_INTERVENTION_MARKERS))
    intervention = ", ".join(dict.fromkeys(intervention_parts)).strip()
    if not intervention:
        raise PicoIncompleteError("intervention")

    # Comparison.
    comparison_parts: list[str] = list(_pico_detect_markers(folded, _PICO_COMPARISON_MARKERS))
    # An explicit second drug acts as a comparator/co-intervention.
    comparison_parts.extend(co_drugs)
    comparison = ", ".join(dict.fromkeys(comparison_parts)).strip()
    if not comparison:
        raise PicoIncompleteError("comparison")

    # Outcome.
    outcome = ", ".join(
        dict.fromkeys(_pico_detect_markers(folded, _PICO_OUTCOME_MARKERS))
    ).strip()
    if not outcome:
        raise PicoIncompleteError("outcome")

    return PicoFrame(
        population=population,
        intervention=intervention,
        comparison=comparison,
        outcome=outcome,
    )


def _maybe_build_pico_frame(query: str) -> PicoFrame | None:
    """Run PICO framing when enabled for a clinical query; otherwise return None (R7.4).

    Propagates :class:`PicoIncompleteError` so an undetermined element rejects the
    request before any retrieval/synthesis work (R7.2).
    """

    if not settings.research_pico_enabled:
        return None
    if not _is_clinical_query(query):
        return None
    return _extract_pico_frame(query)


# --- GRADE-style evidence-certainty + recommendation-strength labeling (R8) -----------------
# When ``RESEARCH_GRADE_ENABLED`` is on, each key claim surfaced by the verification matrix is
# assigned a GRADE evidence-certainty label ∈ {high, moderate, low, very_low}, derived from the
# Evidence Hierarchy (``source_type``) and ``trust_tier`` of its supporting sources (R8.1, R8.2).
# Recommendation items additionally carry a recommendation strength ∈ {strong, conditional}
# (R8.3). When the flag is off the orchestrator produces no labels (R8.5) and the legacy payload
# shape is preserved (R20.2). The certainty mapping is monotonic in evidence strength: a stronger
# Evidence-Hierarchy rank or higher trust_tier never yields a lower certainty (design Property 13).

# Certainty labels ordered weakest → strongest; the order is authoritative for monotonicity.
_GRADE_CERTAINTY_ORDER: tuple[str, ...] = ("very_low", "low", "moderate", "high")
_GRADE_STRENGTH_STRONG = "strong"
_GRADE_STRENGTH_CONDITIONAL = "conditional"

# Evidence-Hierarchy ranks (1 = strongest … 5 = weakest) keyed by ASCII-folded source-type
# markers. Mirrors the design "Trust tier / evidence hierarchy mapping" table: systematic review /
# meta-analysis / guideline (1) > RCT (2) > cohort / observational (3) > case study/series (4) >
# expert opinion / unranked web (5).
_EVIDENCE_HIERARCHY_RANK_MARKERS: tuple[tuple[tuple[str, ...], int], ...] = (
    (("systematic", "meta_analysis", "meta analysis", "guideline"), 1),
    (("rct", "randomi", "controlled_trial", "clinical_trial", "trial"), 2),
    (("cohort", "observational", "case_control", "registry", "longitudinal"), 3),
    (("case_study", "case_series", "case_report", "case study", "case series"), 4),
)
_EVIDENCE_HIERARCHY_RANK_DEFAULT = 5  # expert opinion / unranked web

# trust_tier (1 best … 4 worst) → strength contribution; unknown tier contributes 0.
_GRADE_TRUST_TIER_SCORE: dict[int, int] = {1: 3, 2: 2, 3: 1, 4: 0}


def _evidence_hierarchy_rank(source_type: str | None) -> int:
    """Map a source-type label to its Evidence-Hierarchy rank (1 strongest … 5 weakest)."""

    folded = _ascii_fold(source_type or "").replace("-", "_")
    if not folded.strip():
        return _EVIDENCE_HIERARCHY_RANK_DEFAULT
    for markers, rank in _EVIDENCE_HIERARCHY_RANK_MARKERS:
        if any(marker.replace("-", "_") in folded for marker in markers):
            return rank
    return _EVIDENCE_HIERARCHY_RANK_DEFAULT


def _grade_certainty_label(trust_tier: int | None, hierarchy_rank: int) -> str:
    """Derive a GRADE certainty label from trust_tier + Evidence-Hierarchy rank (R8.2).

    The strength score rises as evidence gets stronger (lower ``trust_tier`` band, lower
    ``hierarchy_rank``). Because the score is non-decreasing in evidence strength and the
    label thresholds are monotonic, a stronger source never yields a lower certainty
    (design Property 13).
    """

    tier_score = _GRADE_TRUST_TIER_SCORE.get(trust_tier, 0)
    bounded_rank = max(1, min(5, int(hierarchy_rank)))
    hierarchy_score = 5 - bounded_rank  # rank 1 → 4 … rank 5 → 0
    combined = tier_score + hierarchy_score  # range 0..7
    if combined >= 6:
        return "high"
    if combined >= 4:
        return "moderate"
    if combined >= 2:
        return "low"
    return "very_low"


def _is_recommendation_claim(claim: str, claim_type: Any = None) -> bool:
    """Heuristically detect whether a key claim is a recommendation item (R8.3).

    Detection is accent-aware for Vietnamese (``nên``/``khuyến nghị``/``khuyến cáo``) and
    keyword-based for English (``should``/``recommend``/``advise``) so a recommendation is
    recognized in either output language without fabricating intent.
    """

    if str(claim_type or "").strip().lower() == "recommendation":
        return True
    lowered = str(claim or "").lower()
    if any(marker in lowered for marker in ("nên", "khuyến nghị", "khuyến cáo")):
        return True
    folded = _ascii_fold(claim or "")
    return any(marker in folded for marker in ("should", "recommend", "advis"))


def _grade_supporting_profile(
    evidence_ref: str | None,
    retrieved_context: list[dict[str, Any]],
) -> tuple[int | None, int | None, bool]:
    """Resolve the strongest supporting source for a claim from its ``evidence_ref``.

    Returns ``(best_trust_tier, best_hierarchy_rank, matched)`` where the "best" values are the
    strongest (lowest) seen across the matched supporting rows. ``matched`` is ``False`` when the
    reference cannot be resolved to any retrieved source.
    """

    ref = _ascii_fold(evidence_ref or "").strip()
    if not ref:
        return None, None, False
    best_tier: int | None = None
    best_rank: int | None = None
    matched = False
    for row in retrieved_context:
        if not isinstance(row, dict):
            continue
        identity = _ascii_fold(
            " ".join(str(row.get(key) or "") for key in ("id", "source", "title", "url"))
        ).strip()
        if not identity:
            continue
        row_id = _ascii_fold(str(row.get("id") or "")).strip()
        if ref in identity or (row_id and row_id in ref):
            matched = True
            tier = _row_trust_tier(row)
            if tier is not None:
                best_tier = tier if best_tier is None else min(best_tier, tier)
            rank = _evidence_hierarchy_rank(_row_source_type(row))
            best_rank = rank if best_rank is None else min(best_rank, rank)
    return best_tier, best_rank, matched


def _grade_corpus_profile(
    retrieved_context: list[dict[str, Any]],
) -> tuple[int | None, int, bool]:
    """Strongest supporting source across the whole retrieved corpus (grounded fallback).

    Returns ``(best_trust_tier, best_hierarchy_rank, has_rows)``. Used when a supported claim's
    ``evidence_ref`` cannot be resolved to a specific row but the claim is still grounded in the
    retrieved evidence.
    """

    best_tier: int | None = None
    best_rank: int | None = None
    has_rows = False
    for row in retrieved_context:
        if not isinstance(row, dict):
            continue
        has_rows = True
        tier = _row_trust_tier(row)
        if tier is not None:
            best_tier = tier if best_tier is None else min(best_tier, tier)
        rank = _evidence_hierarchy_rank(_row_source_type(row))
        best_rank = rank if best_rank is None else min(best_rank, rank)
    return best_tier, (best_rank if best_rank is not None else _EVIDENCE_HIERARCHY_RANK_DEFAULT), has_rows


def _assign_grade_labels(
    verification_rows: list[dict[str, Any]],
    retrieved_context: list[dict[str, Any]],
    *,
    enabled: bool,
) -> list[dict[str, Any]] | None:
    """Assign GRADE certainty + recommendation-strength labels to key claims (R8.1–R8.3, R8.5).

    Returns ``None`` when GRADE labeling is disabled so the optional ``grade`` payload field is
    omitted entirely and the legacy result shape is preserved (R8.5, R20.2). When enabled, each
    key claim (verification-matrix row) gets a certainty label derived from the strongest
    supporting source's Evidence-Hierarchy rank + trust_tier; claims with no resolvable supporting
    source are labeled ``very_low``. Recommendation items additionally carry a recommendation
    strength of ``strong`` (when certainty is high/moderate) or ``conditional`` otherwise (R8.3).
    """

    if not enabled:
        return None

    context = [row for row in (retrieved_context or []) if isinstance(row, dict)]
    corpus_tier, corpus_rank, corpus_has_rows = _grade_corpus_profile(context)

    labels: list[dict[str, Any]] = []
    for row in verification_rows or []:
        if not isinstance(row, dict):
            continue
        claim = _first_nonempty_text(row.get("claim"))
        if not claim:
            continue

        status = str(row.get("support_status") or "").strip().lower()
        evidence_ref = _first_nonempty_text(row.get("evidence_ref")) or None
        best_tier, best_rank, matched = _grade_supporting_profile(evidence_ref, context)

        if matched:
            has_support = True
        elif status in {"supported", "contradicted"} and corpus_has_rows:
            # Claim is grounded in the retrieved corpus but the per-claim reference did not
            # resolve to a single row; fall back to the corpus's strongest source.
            best_tier, best_rank, has_support = corpus_tier, corpus_rank, True
        else:
            best_tier, best_rank, has_support = None, _EVIDENCE_HIERARCHY_RANK_DEFAULT, False

        if has_support:
            certainty = _grade_certainty_label(
                best_tier,
                best_rank if best_rank is not None else _EVIDENCE_HIERARCHY_RANK_DEFAULT,
            )
        else:
            certainty = "very_low"

        entry: dict[str, Any] = {"claim": claim, "certainty": certainty}
        if _is_recommendation_claim(claim, row.get("claim_type")):
            entry["recommendation_strength"] = (
                _GRADE_STRENGTH_STRONG
                if certainty in {"high", "moderate"}
                else _GRADE_STRENGTH_CONDITIONAL
            )
        labels.append(entry)

    return labels


# --- Evidence-agreement (Consensus) view + conflicting-evidence section (R9) ------------------
# When ``RESEARCH_CONSENSUS_ENABLED`` is on, the orchestrator computes, for each key claim, the
# number of retrieved sources that support, contrast, or are neutral toward the claim (R9.1),
# deriving each source-claim classification from the per-source NLI verdict (R9.2) by reusing the
# deterministic ``classify_claim`` core that backs ``verify_claims``. When a claim is both
# supported and contrasted by sources, a structured ``conflicting_evidence`` entry lists the
# contrasting source ids (R9.4). When the flag is off both helpers return ``None`` so the optional
# ``consensus``/``conflicting_evidence`` payload fields are omitted and the legacy result shape is
# preserved (R20.2).


def _consensus_evidence_rows(retrieved_context: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Build ``{"ref", "text"}`` source rows for per-source NLI classification.

    Mirrors ``fides_lite._build_evidence_rows`` so the source-claim verdicts used for consensus
    counts are derived from the exact same evidence set as the verification matrix. Sources with
    no usable text are excluded (they cannot be NLI-evaluated).
    """

    rows: list[dict[str, str]] = []
    for index, item in enumerate(retrieved_context or [], start=1):
        if not isinstance(item, dict):
            continue
        text = " ".join(str(item.get("text", "")).split()).strip()
        if not text:
            continue
        ref = str(item.get("id") or f"evidence-{index}").strip() or f"evidence-{index}"
        rows.append({"ref": ref, "text": text})
    return rows


def _compute_consensus_view(
    *,
    verification_rows: list[dict[str, Any]],
    retrieved_context: list[dict[str, Any]],
    enabled: bool,
) -> tuple[list[dict[str, Any]] | None, list[dict[str, Any]] | None]:
    """Compute per-claim support/contrast/neutral counts + the conflicting-evidence section (R9).

    Returns ``(consensus, conflicting_evidence)``. Both are ``None`` when consensus is disabled so
    the optional payload fields are omitted entirely (R20.2). When enabled, ``consensus`` carries
    one entry per key claim with ``support``/``contrast``/``neutral`` counts that partition the set
    of evaluated sources exactly (design Property 15): each evaluated source contributes to exactly
    one bucket, so ``support + contrast + neutral`` equals the number of evaluated sources.
    ``conflicting_evidence`` lists the contrasting source ids for every claim that has at least one
    supporting and one contrasting source (R9.4); it is an empty list when no claim conflicts.
    """

    if not enabled:
        return None, None

    evidence_rows = _consensus_evidence_rows(retrieved_context)

    consensus: list[dict[str, Any]] = []
    conflicting_evidence: list[dict[str, Any]] = []
    for row in verification_rows or []:
        if not isinstance(row, dict):
            continue
        claim = _first_nonempty_text(row.get("claim"))
        if not claim:
            continue

        support = 0
        contrast = 0
        neutral = 0
        contrasting_ids: list[str] = []
        for source in evidence_rows:
            # Derive the source-claim verdict from the per-source NLI classification (R9.2).
            verdict = classify_claim(claim, evidence_rows=[source])
            status = str(verdict.support_status or "").strip().lower()
            if status == "supported":
                support += 1
            elif status == "contradicted":
                contrast += 1
                contrasting_ids.append(source["ref"])
            else:
                neutral += 1

        consensus.append(
            {
                "claim": claim,
                "support": support,
                "contrast": contrast,
                "neutral": neutral,
            }
        )
        # Conflicting-evidence section present iff the claim has both supporting and contrasting
        # sources; it lists exactly the contrasting sources (R9.4).
        if support >= 1 and contrast >= 1:
            conflicting_evidence.append(
                {
                    "claim": claim,
                    "contrasting_citation_ids": contrasting_ids,
                }
            )

    return consensus, conflicting_evidence


# --- Claim-to-study traceability + Citation Registry + provenance (R11) ----------------------
# When ``RESEARCH_CLAIM_TRACE_ENABLED`` is on, the orchestrator links each supported key claim to
# the specific citation id(s) that support it (R11.1), attaches per-citation provenance
# (``study_id`` PMID/DOI/RXCUI, ``source_type``, ``trust_tier``, publication/effective date —
# R11.2), and builds a Citation_Registry appendix listing every surfaced citation (R11.4). A
# citation is only ever built from a retrieved source, so no fabricated citation can be emitted
# (R11.5); a claim with no resolvable supporting citation is suppressed and never gets a
# fabricated citation (R11.6). When the flag is off both artifacts are ``None`` so the optional
# ``citation_registry``/``traced_claims`` payload fields are omitted and the legacy result shape
# is preserved (R20.2).

# Lowest-authority band assigned to a surfaced citation whose backing source carries no explicit
# ``trust_tier``; keeps the registry's ``trust_tier`` field always present (R11.2) without
# inflating an unknown source's authority.
_DEFAULT_CITATION_TRUST_TIER = 4

# Ordered scholarly-identifier metadata keys → emitted ``study_id`` prefix (R11.2).
_STUDY_ID_METADATA_KEYS: tuple[tuple[str, str | None], ...] = (
    ("pmid", "PMID"),
    ("doi", "DOI"),
    ("rxcui", "RXCUI"),
    ("study_id", None),
)
_DOI_URL_PATTERN = re.compile(r"10\.\d{4,9}/\S+")


def _normalize_claim_verdict(status: Any) -> str:
    """Map a verification ``support_status`` to a claim verdict ∈ {supported, unsupported, contradicted}."""

    text = str(status or "").strip().lower()
    if text == "supported":
        return "supported"
    if text == "contradicted":
        return "contradicted"
    return "unsupported"


def _derive_citation_study_id(citation: Citation, row: dict[str, Any] | None) -> str:
    """Resolve a citation's ``study_id`` (PMID/DOI/RXCUI) from its backing source (R11.2).

    Prefers an explicit identifier already on the citation, then scholarly identifiers on the
    backing retrieved row, then a DOI embedded in the citation URL. Falls back to the retrieved
    source's own id so the field is always present while never pointing at a non-retrieved
    source (R11.5).
    """

    if citation.study_id:
        return citation.study_id
    if isinstance(row, dict):
        for key, prefix in _STUDY_ID_METADATA_KEYS:
            text = str(_row_metadata_value(row, key) or "").strip()
            if not text:
                continue
            if prefix and not text.upper().startswith(prefix.upper()):
                return f"{prefix}:{text}"
            return text
    doi_match = _DOI_URL_PATTERN.search(str(citation.url or ""))
    if doi_match:
        return f"DOI:{doi_match.group(0)}"
    return citation.source_id


def _match_citation_ids_for_claim(
    evidence_ref: str | None,
    citations: list[Citation],
) -> list[str]:
    """Resolve the citation id(s) that back a claim's ``evidence_ref`` (R11.1).

    Mirrors the fuzzy identity match used by GRADE supporting-source resolution: a citation
    matches when its folded identity (id/source/title/url) contains the reference, or when its
    folded id is contained in the reference. Returns the matched citation ids in citation order
    (deduplicated); empty when nothing resolves.
    """

    ref = _ascii_fold(evidence_ref or "").strip()
    if not ref:
        return []
    matched: list[str] = []
    seen: set[str] = set()
    for citation in citations or []:
        source_id = citation.source_id
        if not source_id or source_id in seen:
            continue
        identity = _ascii_fold(
            " ".join(
                str(value or "")
                for value in (citation.source_id, citation.source, citation.title, citation.url)
            )
        ).strip()
        if not identity:
            continue
        folded_id = _ascii_fold(source_id).strip()
        if ref in identity or (folded_id and folded_id in ref):
            seen.add(source_id)
            matched.append(source_id)
    return matched


def _build_claim_trace(
    *,
    verification_rows: list[dict[str, Any]],
    citations: list[Citation],
    retrieved_context: list[dict[str, Any]],
    grade_labels: list[dict[str, Any]] | None,
    enabled: bool,
) -> tuple[list[dict[str, Any]] | None, list[dict[str, Any]] | None]:
    """Build traced claims + the Citation Registry appendix (R11).

    Returns ``(traced_claims, citation_registry)``. Both are ``None`` when claim tracing is
    disabled so the optional payload fields are omitted and the legacy shape is preserved (R20.2).
    When enabled, the registry carries one :class:`CitationRef` per surfaced citation (every
    citation referenced in the report — R11.4) with complete provenance (R11.2), and
    ``traced_claims`` carries one :class:`TracedClaim` per *supported* key claim whose evidence
    resolves to at least one registry citation (R11.1). Claims with no resolvable supporting
    citation are suppressed (R11.6) and every emitted citation id corresponds to a retrieved
    source (R11.5).
    """

    if not enabled:
        return None, None

    # Index backing retrieved-source rows by id so each citation can inherit its provenance even
    # when the recency/trust ranking flag (R6) is off and the Citation object carries no metadata.
    context_by_id: dict[str, dict[str, Any]] = {}
    for row in retrieved_context or []:
        if not isinstance(row, dict):
            continue
        row_id = _ascii_fold(str(row.get("id") or "")).strip()
        if row_id and row_id not in context_by_id:
            context_by_id[row_id] = row

    registry: list[dict[str, Any]] = []
    valid_ids: set[str] = set()
    for citation in citations or []:
        citation_id = citation.source_id
        if not citation_id or citation_id in valid_ids:
            continue
        valid_ids.add(citation_id)
        row = context_by_id.get(_ascii_fold(citation_id).strip())
        source_type = (
            (_row_source_type(row) if row else None) or citation.source_type or "unknown"
        )
        trust_tier = (_row_trust_tier(row) if row else None)
        if trust_tier is None:
            trust_tier = citation.trust_tier
        if trust_tier is None:
            trust_tier = _DEFAULT_CITATION_TRUST_TIER
        published_at = (_row_effective_date(row) if row else None) or citation.published_at
        registry.append(
            CitationRef(
                citation_id=citation_id,
                study_id=_derive_citation_study_id(citation, row),
                source_type=source_type,
                trust_tier=trust_tier,
                published_at=published_at,
            ).as_payload()
        )

    certainty_by_claim: dict[str, str] = {}
    for entry in grade_labels or []:
        if not isinstance(entry, dict):
            continue
        claim_text = _first_nonempty_text(entry.get("claim"))
        certainty = _first_nonempty_text(entry.get("certainty"))
        if claim_text and certainty:
            certainty_by_claim[claim_text] = certainty

    traced_claims: list[dict[str, Any]] = []
    for row in verification_rows or []:
        if not isinstance(row, dict):
            continue
        claim = _first_nonempty_text(row.get("claim"))
        if not claim:
            continue
        # R11.1/R11.6: only a supported claim that resolves to ≥1 registry citation survives.
        if _normalize_claim_verdict(row.get("support_status")) != "supported":
            continue
        evidence_ref = _first_nonempty_text(row.get("evidence_ref")) or None
        citation_ids = [
            citation_id
            for citation_id in _match_citation_ids_for_claim(evidence_ref, citations)
            if citation_id in valid_ids
        ]
        if not citation_ids:
            continue
        traced_claims.append(
            TracedClaim(
                claim=claim,
                citation_ids=citation_ids,
                verdict="supported",
                certainty=certainty_by_claim.get(claim),
            ).as_payload()
        )

    return traced_claims, registry


def _normalize_source_mode_key(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def _resolve_target_language_for_query_bucket(
    *,
    bucket: str,
    source_mode: str | None,
    language_hint: str,
) -> str:
    normalized_source_mode = _normalize_source_mode_key(source_mode)
    if bucket == "scientific":
        return "en"
    if normalized_source_mode in _VIETNAMESE_SOURCE_KEYS:
        return "vi"
    if normalized_source_mode in _ENGLISH_SOURCE_KEYS:
        return "en"
    if language_hint in {"vi", "en"}:
        return language_hint
    return "mixed"


def _filter_keywords_by_language(
    keywords: list[str],
    *,
    target_language: str,
) -> tuple[list[str], bool]:
    normalized = _dedupe_query_list([str(item) for item in keywords], limit=12)
    if not normalized:
        return [], False
    if target_language not in {"vi", "en"}:
        return normalized, False

    filtered: list[str] = []
    for token in normalized:
        folded = _ascii_fold(token)
        if not folded:
            continue
        if target_language == "vi" and folded in _EN_GENERIC_KEYWORD_HINTS:
            continue
        if target_language == "en" and folded in _VI_GENERIC_KEYWORD_HINTS:
            continue
        filtered.append(token)
    if filtered:
        return filtered, False
    return normalized, True


def _apply_keyword_filter_to_query_plan(
    *,
    topic: str,
    query_plan: dict[str, Any],
    planner_keywords: list[str],
    source_mode: str | None,
) -> dict[str, Any]:
    safe_plan = dict(query_plan or {})
    source_queries_raw = safe_plan.get("source_queries")
    source_queries = (
        dict(source_queries_raw)
        if isinstance(source_queries_raw, dict)
        else {"internal": [], "scientific": [], "web": []}
    )

    fallback_seed = _dedupe_query_list(
        [
            *[str(item) for item in planner_keywords if str(item).strip()],
            *query_terms(str(topic or "")),
        ],
        limit=12,
    )
    if not fallback_seed:
        fallback_seed = ["medical safety"]

    language_hint = str(safe_plan.get("language_hint") or "").strip().lower()
    if language_hint not in {"vi", "en", "mixed"}:
        _, _, language_hint = _detect_language_hint(topic)

    keywords_by_source: dict[str, list[str]] = {}
    target_language_by_source: dict[str, str] = {}
    source_query_updates: dict[str, list[str]] = {}
    fallback_buckets: list[str] = []

    for bucket in ("internal", "scientific", "web"):
        target_language = _resolve_target_language_for_query_bucket(
            bucket=bucket,
            source_mode=source_mode,
            language_hint=language_hint,
        )
        target_language_by_source[bucket] = target_language
        filtered_keywords, fallback_used = _filter_keywords_by_language(
            fallback_seed,
            target_language=target_language,
        )
        if fallback_used:
            fallback_buckets.append(bucket)
        keywords_by_source[bucket] = filtered_keywords

        existing_queries = _dedupe_query_list(
            [str(item) for item in source_queries.get(bucket, []) if str(item).strip()],
            limit=8,
        )
        injected_query = " ".join(filtered_keywords[:6]).strip()
        if injected_query and all(
            _ascii_fold(injected_query) != _ascii_fold(existing) for existing in existing_queries
        ):
            existing_queries = _dedupe_query_list([injected_query, *existing_queries], limit=8)
        if not existing_queries:
            fallback_query = (
                str(safe_plan.get("canonical_query") or "").strip()
                or str(safe_plan.get("original_query") or "").strip()
                or str(topic).strip()
            )
            existing_queries = [fallback_query]
        source_query_updates[bucket] = existing_queries

    merged_keywords = _dedupe_query_list(
        [
            *(keywords_by_source.get("internal") or []),
            *(keywords_by_source.get("scientific") or []),
            *(keywords_by_source.get("web") or []),
        ],
        limit=12,
    ) or fallback_seed

    safe_plan["source_queries"] = source_query_updates
    safe_plan["query_terms"] = merged_keywords[:10]
    safe_plan["keyword_filter"] = {
        "source_mode": source_mode or "default",
        "language_hint": language_hint,
        "target_language_by_source": target_language_by_source,
        "keywords_by_source": keywords_by_source,
        "fallback_buckets": fallback_buckets,
    }
    return {
        "query_plan": safe_plan,
        "keywords": merged_keywords[:10],
        "keywords_by_source": keywords_by_source,
        "target_language_by_source": target_language_by_source,
        "fallback_buckets": fallback_buckets,
        "language_hint": language_hint,
    }


def _normalize_retrieval_route(value: Any) -> str:
    route = str(value or "").strip().lower()
    if route in _ALLOWED_RETRIEVAL_ROUTES:
        return route
    return "internal-heavy"


def _normalize_router_confidence(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = 0.0
    return round(max(0.0, min(numeric, 1.0)), 4)


def _dedupe_query_list(queries: list[str], *, limit: int = 12) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in queries:
        normalized = " ".join(str(item or "").split()).strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
        if len(deduped) >= max(int(limit), 1):
            break
    return deduped


def _is_ddi_critical_topic(topic: str) -> bool:
    lowered = str(topic or "").lower()
    folded = _ascii_fold(topic)
    critical_markers = {
        "critical",
        "major",
        "severe",
        "life-threatening",
        "black box",
        "contraindication",
        "bleeding risk",
        "hemorrhage",
        "nghiem trong",
        "nguy hiem",
        "chong chi dinh",
        "xuat huyet",
    }
    return any(marker in lowered or marker in folded for marker in critical_markers)


def _build_provider_query_overrides(
    *,
    topic: str,
    original_query: str,
    canonical_query: str,
    language_hint: str,
    keywords: list[str],
    is_ddi_query: bool,
    is_nutrition_query: bool,
    is_comparison_query: bool,
) -> dict[str, dict[str, str]]:
    cleaned_original = " ".join(str(original_query or "").split()).strip()
    cleaned_canonical = " ".join(str(canonical_query or "").split()).strip()
    keyword_phrase = " ".join(
        item.strip() for item in keywords if isinstance(item, str) and item.strip()
    )
    folded_original = _ascii_fold(cleaned_original)
    vi_focus = cleaned_original or folded_original or cleaned_canonical
    en_focus = cleaned_canonical or folded_original or cleaned_original
    if not en_focus:
        en_focus = keyword_phrase
    if not vi_focus:
        vi_focus = keyword_phrase

    scientific_query = en_focus
    if keyword_phrase:
        scientific_query = " ".join([en_focus, keyword_phrase]).strip()
    if is_nutrition_query:
        scientific_query = " ".join(
            [
                scientific_query,
                "DASH Mediterranean diet blood pressure cardiovascular outcomes adherence cost practicality",
            ]
        ).strip()
    if is_comparison_query:
        scientific_query = " ".join(
            [
                scientific_query,
                "comparative effectiveness benefits harms implementation constraints subgroup response",
            ]
        ).strip()
    scientific_query = scientific_query[:360]

    web_query = vi_focus if language_hint in {"vi", "mixed"} else en_focus
    if is_nutrition_query:
        web_query = " ".join(
            [
                web_query,
                "so sánh DASH và Địa Trung Hải lợi ích nguy cơ tuân thủ chi phí áp dụng thực tế",
            ]
        ).strip()
    web_query = web_query[:320]

    regulatory_query = vi_focus if language_hint in {"vi", "mixed"} else cleaned_original or web_query
    regulatory_query = regulatory_query[:320]

    scientific_providers: dict[str, str] = {
        "pubmed": scientific_query,
        "europepmc": scientific_query,
        "semantic_scholar": scientific_query,
        "openalex": scientific_query,
        "crossref": scientific_query,
        "clinicaltrials": scientific_query,
    }
    if is_ddi_query:
        scientific_providers.update(
            {
                "openfda": scientific_query,
                "dailymed": scientific_query,
                "rxnorm": scientific_query,
            }
        )

    output: dict[str, dict[str, str]] = {
        "scientific": scientific_providers,
        "web": {
            "searxng": web_query,
        },
    }
    # Chỉ bật luồng regulatory khi truy vấn liên quan thuốc/an toàn dược.
    if is_ddi_query and not is_nutrition_query:
        output["regulatory"] = {
            "davidrug": regulatory_query,
            "vn_moh": regulatory_query,
            "vn_kcb": regulatory_query,
            "vn_canhgiacduoc": regulatory_query,
            "vn_vbpl_byt": regulatory_query,
            "vn_dav": regulatory_query,
        }
    return output


def _sanitize_provider_query_overrides(
    value: Any,
    *,
    fallback: dict[str, dict[str, str]],
) -> dict[str, dict[str, str]]:
    if not isinstance(value, dict):
        return fallback

    normalized: dict[str, dict[str, str]] = {}
    for category_raw, provider_map in value.items():
        category = str(category_raw or "").strip().lower()
        if category not in {"scientific", "web", "regulatory"}:
            continue
        if not isinstance(provider_map, dict):
            continue
        row: dict[str, str] = {}
        for provider_raw, query_raw in provider_map.items():
            provider = str(provider_raw or "").strip().lower()
            query_text = " ".join(str(query_raw or "").split()).strip()
            if not provider or not query_text:
                continue
            row[provider] = query_text[:360]
        if row:
            normalized[category] = row

    merged: dict[str, dict[str, str]] = {}
    for category in ("scientific", "web", "regulatory"):
        fallback_row = fallback.get(category, {})
        merged_row = dict(fallback_row)
        if category in normalized:
            merged_row.update(normalized[category])
        if merged_row:
            merged[category] = merged_row
    return merged or fallback


def _build_source_aware_query_plan(
    *,
    topic: str,
    research_mode: str,
    keywords: list[str],
    source_route: SourceRouterDecision | None = None,
) -> dict[str, Any]:
    original_query = " ".join(str(topic or "").split()).strip()
    folded_query = _ascii_fold(original_query)
    profile = analyze_query_profile(original_query)
    is_comparison_query = _is_comparison_query(original_query)
    is_nutrition_query = _is_nutrition_diet_query(original_query)
    is_ddi_query = bool(profile.get("is_ddi_query"))
    keyword_terms = [
        item.strip().lower()
        for item in keywords
        if isinstance(item, str) and item.strip()
    ]
    if not keyword_terms:
        keyword_terms = query_terms(original_query)

    _, _, language_hint = _detect_language_hint(original_query)

    primary_drug = str(profile.get("primary_drug") or "").strip().lower()
    co_drugs_raw = profile.get("co_drugs")
    co_drugs = (
        [str(item).strip().lower() for item in co_drugs_raw if str(item).strip()]
        if isinstance(co_drugs_raw, list)
        else []
    )
    co_drug_phrase = ", ".join(co_drugs[:4]) if co_drugs else "common analgesics"
    canonical_query = original_query
    if is_ddi_query:
        canonical_query = (
            f"{primary_drug or 'index drug'} interaction with {co_drug_phrase} "
            "bleeding risk contraindication guidance"
        ).strip()
    elif is_nutrition_query and is_comparison_query:
        canonical_query = (
            "DASH diet versus Mediterranean diet comparative effectiveness "
            "blood pressure cardiovascular outcomes adherence cost practicality"
        )
    elif language_hint == "vi":
        canonical_query = " ".join(keyword_terms[:8]).strip() or folded_query or original_query

    internal_queries = _dedupe_query_list(
        [
            original_query,
            canonical_query,
            folded_query if folded_query != original_query.lower() else "",
            " ".join(keyword_terms[:8]),
        ],
        limit=8,
    )
    scientific_queries = _dedupe_query_list(
        [
            canonical_query,
            " ".join(keyword_terms[:8]),
            (
                f"{primary_drug or 'index drug'} drug-drug interaction with {co_drug_phrase} "
                "clinical evidence"
                if profile.get("is_ddi_query")
                else ""
            ),
            original_query,
        ],
        limit=8,
    )
    web_queries = _dedupe_query_list(
        [
            original_query,
            canonical_query,
            f"{canonical_query} guideline",
            f"{canonical_query} safety warning",
        ],
        limit=8,
    )

    deep_queries = _dedupe_query_list(
        [
            canonical_query,
            f"{canonical_query} guideline recommendations and safety thresholds",
            f"{canonical_query} systematic review meta-analysis outcomes",
            f"{canonical_query} adverse events contraindications interaction risks",
            f"{canonical_query} contradictory findings and subgroup caveats",
            f"{canonical_query} clinical translation and monitoring checklist",
            (
                "DASH diet core principles food groups sodium limits and blood pressure effect"
                if is_nutrition_query
                else ""
            ),
            (
                "Mediterranean diet core principles olive oil unsaturated fats and cardiovascular outcomes"
                if is_nutrition_query
                else ""
            ),
            (
                "DASH versus Mediterranean adherence burden cost accessibility in Vietnam"
                if is_nutrition_query and is_comparison_query
                else ""
            ),
            (
                "DASH versus Mediterranean subgroup response in hypertension diabetes CKD elderly patients"
                if is_nutrition_query and is_comparison_query
                else ""
            ),
        ],
        limit=18,
    )
    deep_beta_queries = _dedupe_query_list(
        [
            *deep_queries,
            f"{canonical_query} dose-adjusted subgroup evidence chronic kidney disease liver impairment",
            f"{canonical_query} pharmacovigilance post-marketing safety signal trend",
            f"{canonical_query} disagreement analysis by trial design and endpoint definitions",
            f"{canonical_query} guideline divergence and implementation constraints primary care",
            f"{canonical_query} monitoring algorithm threshold escalation and stop criteria",
            f"{canonical_query} unresolved evidence gaps and pragmatic fallback protocol",
            (
                "network meta analysis DASH and Mediterranean hard endpoints MI stroke mortality"
                if is_nutrition_query and is_comparison_query
                else ""
            ),
            (
                "real-world implementation barriers DASH Mediterranean in low-middle income settings"
                if is_nutrition_query and is_comparison_query
                else ""
            ),
        ],
        limit=24,
    )
    fast_queries = _dedupe_query_list([canonical_query, original_query, " ".join(keyword_terms[:6])], limit=4)
    provider_queries = _build_provider_query_overrides(
        topic=original_query,
        original_query=original_query,
        canonical_query=canonical_query,
        language_hint=language_hint,
        keywords=keyword_terms[:10],
        is_ddi_query=is_ddi_query,
        is_nutrition_query=is_nutrition_query,
        is_comparison_query=is_comparison_query,
    )

    route_payload = source_route_metadata_payload(source_route)
    return {
        "original_query": original_query,
        "canonical_query": canonical_query,
        "language_hint": language_hint,
        "is_ddi_query": is_ddi_query,
        "is_ddi_critical_query": is_ddi_query and _is_ddi_critical_topic(original_query),
        "is_comparison_query": is_comparison_query,
        "is_nutrition_query": is_nutrition_query,
        "source_queries": {
            "internal": internal_queries,
            "scientific": scientific_queries,
            "web": web_queries,
        },
        "decomposition": {
            "fast_pass_queries": fast_queries,
            "deep_pass_queries": deep_queries,
            "deep_beta_pass_queries": deep_beta_queries,
        },
        "provider_queries": provider_queries,
        "research_mode": research_mode,
        "query_terms": keyword_terms[:10],
        "retrieval_route": route_payload.get("retrieval_route"),
        "router_confidence": route_payload.get("router_confidence"),
        "router_reason_codes": route_payload.get("router_reason_codes", []),
    }


def _strip_markdown_fence(value: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def _extract_first_json_object(value: str) -> str:
    text = str(value or "").strip()
    start = text.find("{")
    if start < 0:
        return ""
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        ch = text[index]
        if in_string:
            if escaped:
                escaped = False
                continue
            if ch == "\\":
                escaped = True
                continue
            if ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            depth += 1
            continue
        if ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return ""


def _parse_planner_json_payload(raw_content: str) -> Any:
    cleaned = _strip_markdown_fence(raw_content)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        extracted = _extract_first_json_object(cleaned)
        if not extracted:
            raise
        return json.loads(extracted)


def _safe_planner_error_code(exc: Exception) -> str:
    normalized = f"{exc.__class__.__name__}:{exc}".lower()
    if "timeout" in normalized:
        return "timeout"
    if "json" in normalized:
        return "invalid_json"
    if "schema" in normalized or "required" in normalized or "missing" in normalized:
        return "invalid_schema"
    if "deepseek_request_failed" in normalized:
        return "provider_request_failed"
    return "runtime_error"


def _sanitize_required_query_entries(
    value: Any,
    *,
    field_name: str,
    limit: int,
) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"Missing required list field: {field_name}")
    cleaned = _dedupe_query_list([str(item) for item in value], limit=limit)
    if not cleaned:
        raise ValueError(f"Required list field has no usable values: {field_name}")
    return cleaned


def _sanitize_llm_query_plan_payload(
    payload: Any,
    *,
    base_query_plan: dict[str, Any],
    research_mode: str,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Planner output must be a JSON object")

    required_keys = {"canonical_query", "language_hint", "keywords", "source_queries", "decomposition"}
    if not required_keys.issubset(set(payload.keys())):
        raise ValueError("Planner output missing required keys")

    original_query = str(base_query_plan.get("original_query") or "").strip()
    canonical_query = " ".join(str(payload.get("canonical_query") or "").split()).strip()
    if not canonical_query:
        raise ValueError("Planner output missing canonical_query")
    # Preserve the user's complete question as the immutable semantic anchor.
    # The LLM may expand/translate it, but its generated plan cannot erase trial
    # names, drugs, population details, or qualifiers supplied by the user.
    canonical_query = f"{original_query} {canonical_query}".strip()
    canonical_query = canonical_query[:320]

    language_hint_raw = str(payload.get("language_hint") or "").strip().lower()
    language_hint = language_hint_raw if language_hint_raw in {"vi", "en", "mixed"} else "mixed"

    keywords_raw = payload.get("keywords")
    if not isinstance(keywords_raw, list):
        raise ValueError("Planner output keywords must be list")
    keywords = _dedupe_query_list([str(item) for item in keywords_raw], limit=12)
    keywords = _dedupe_query_list(
        [*query_terms(original_query), *keywords],
        limit=12,
    )
    if not keywords:
        keywords = _dedupe_query_list(query_terms(canonical_query), limit=12)
    if not keywords:
        raise ValueError("Planner output keywords must not be empty")

    source_queries_raw = payload.get("source_queries")
    if not isinstance(source_queries_raw, dict):
        raise ValueError("Planner output source_queries must be object")
    internal_queries = _sanitize_required_query_entries(
        source_queries_raw.get("internal"),
        field_name="source_queries.internal",
        limit=8,
    )
    scientific_queries = _sanitize_required_query_entries(
        source_queries_raw.get("scientific"),
        field_name="source_queries.scientific",
        limit=8,
    )
    web_queries = _sanitize_required_query_entries(
        source_queries_raw.get("web"),
        field_name="source_queries.web",
        limit=8,
    )

    decomposition_raw = payload.get("decomposition")
    if not isinstance(decomposition_raw, dict):
        raise ValueError("Planner output decomposition must be object")
    deep_pass_queries = _sanitize_required_query_entries(
        decomposition_raw.get("deep_pass_queries"),
        field_name="decomposition.deep_pass_queries",
        limit=12,
    )
    deep_beta_limit = _DEEP_BETA_PASS_CAP
    deep_beta_pass_queries = _sanitize_required_query_entries(
        decomposition_raw.get("deep_beta_pass_queries"),
        field_name="decomposition.deep_beta_pass_queries",
        limit=deep_beta_limit,
    )
    # The original multilingual question is an immutable retrieval anchor. LLM
    # planning may expand or translate it, but must not erase trial names, drug
    # classes, or other user-supplied entities.
    internal_queries = _dedupe_query_list([original_query, *internal_queries], limit=8)
    scientific_queries = _dedupe_query_list(
        [original_query, canonical_query, *scientific_queries],
        limit=8,
    )
    web_queries = _dedupe_query_list([original_query, canonical_query, *web_queries], limit=8)
    deep_pass_queries = _dedupe_query_list(
        [original_query, canonical_query, *deep_pass_queries],
        limit=12,
    )
    deep_beta_pass_queries = _dedupe_query_list(
        [original_query, canonical_query, *deep_beta_pass_queries],
        limit=deep_beta_limit,
    )
    fast_pass_queries = _dedupe_query_list(
        [canonical_query, base_query_plan.get("original_query"), " ".join(keywords[:6])],
        limit=4,
    )
    fallback_provider_queries = _build_provider_query_overrides(
        topic=str(base_query_plan.get("original_query") or canonical_query),
        original_query=str(base_query_plan.get("original_query") or canonical_query),
        canonical_query=canonical_query,
        language_hint=language_hint,
        keywords=keywords[:10],
        is_ddi_query=bool(base_query_plan.get("is_ddi_query")),
        is_nutrition_query=bool(base_query_plan.get("is_nutrition_query")),
        is_comparison_query=bool(base_query_plan.get("is_comparison_query")),
    )
    provider_queries = _sanitize_provider_query_overrides(
        payload.get("provider_queries"),
        fallback=fallback_provider_queries,
    )

    return {
        "original_query": original_query or canonical_query,
        "canonical_query": canonical_query,
        "language_hint": language_hint,
        "is_ddi_query": bool(base_query_plan.get("is_ddi_query")),
        "is_ddi_critical_query": bool(base_query_plan.get("is_ddi_critical_query")),
        "is_comparison_query": bool(base_query_plan.get("is_comparison_query")),
        "is_nutrition_query": bool(base_query_plan.get("is_nutrition_query")),
        "source_queries": {
            "internal": internal_queries,
            "scientific": scientific_queries,
            "web": web_queries,
        },
        "decomposition": {
            "fast_pass_queries": fast_pass_queries,
            "deep_pass_queries": deep_pass_queries,
            "deep_beta_pass_queries": deep_beta_pass_queries,
        },
        "provider_queries": provider_queries,
        "research_mode": research_mode,
        "query_terms": keywords[:10],
    }


def _resolve_runtime_llm_config(
    llm_runtime: dict[str, Any] | None,
) -> tuple[str, str, str, str]:
    runtime = llm_runtime if isinstance(llm_runtime, dict) else {}
    if settings.llm_deepseek_only:
        api_key = str(settings.deepseek_api_key or "").strip() or str(runtime.get("api_key") or "").strip()
        base_url = str(settings.deepseek_base_url or "").strip() or str(runtime.get("base_url") or "").strip()
        model = str(settings.deepseek_model or "").strip() or str(runtime.get("model") or "").strip()
        return "deepseek", api_key, base_url, model
    raw_provider = str(runtime.get("provider") or "").strip().lower()
    if raw_provider:
        provider = raw_provider
    else:
        provider = (
            "hitechcloud_gpt53_codex_high"
            if str(settings.primary_llm_api_key or "").strip()
            else "deepseek"
        )
    if provider == "hitechcloud_gpt53_codex_high":
        api_key = (
            str(runtime.get("api_key") or "").strip()
            or str(settings.primary_llm_api_key or "").strip()
        )
        base_url = (
            str(runtime.get("base_url") or "").strip()
            or str(settings.primary_llm_base_url or "").strip()
            or "https://platform.hitechcloud.one/v1"
        )
        model = (
            str(runtime.get("model") or "").strip()
            or str(settings.primary_llm_model or "").strip()
            or "gpt-5.3-codex-high"
        )
        if not api_key:
            deepseek_api_key = (
                str(settings.deepseek_api_key or "").strip()
                or str(runtime.get("api_key") or "").strip()
            )
            deepseek_base_url = (
                str(settings.deepseek_base_url or "").strip()
                or str(runtime.get("base_url") or "").strip()
            )
            deepseek_model = (
                str(settings.deepseek_model or "").strip()
                or str(runtime.get("model") or "").strip()
            )
            if deepseek_api_key and deepseek_base_url and deepseek_model:
                return "deepseek", deepseek_api_key, deepseek_base_url, deepseek_model
        return provider, api_key, base_url, model

    api_key = str(runtime.get("api_key") or "").strip() or str(settings.deepseek_api_key or "").strip()
    base_url = str(runtime.get("base_url") or "").strip() or str(settings.deepseek_base_url or "").strip()
    model = str(runtime.get("model") or "").strip() or str(settings.deepseek_model or "").strip()
    return "deepseek", api_key, base_url, model


def _has_request_runtime_override(llm_runtime: dict[str, Any] | None) -> bool:
    runtime = llm_runtime if isinstance(llm_runtime, dict) else {}
    return bool(
        str(runtime.get("api_key") or "").strip()
        and str(runtime.get("base_url") or "").strip()
        and str(runtime.get("model") or "").strip()
    )


def _resolve_runtime_retry_policy(
    llm_runtime: dict[str, Any] | None,
) -> tuple[int, float]:
    if _has_request_runtime_override(llm_runtime):
        return 0, min(max(float(settings.deepseek_retry_backoff_seconds), 0.0), 0.25)
    return (
        max(0, int(settings.deepseek_retries_per_base)),
        max(0.0, float(settings.deepseek_retry_backoff_seconds)),
    )


def _pause_between_pipeline_parts(multiplier: float = 1.0) -> None:
    base_pause = max(0.0, float(settings.research_inter_step_pause_seconds))
    if base_pause <= 0:
        return
    jitter = max(0.0, float(settings.research_inter_step_jitter_seconds))
    effective_multiplier = max(0.2, float(multiplier))
    wait_seconds = base_pause * effective_multiplier
    if jitter > 0:
        wait_seconds += random.uniform(0.0, jitter)
    sleep(wait_seconds)


def _build_query_planner_client(
    *, llm_runtime: dict[str, Any] | None = None
) -> DeepSeekClient | None:
    _, api_key, base_url, model = _resolve_runtime_llm_config(llm_runtime)
    if not api_key or not base_url or not model:
        return None
    timeout_seconds = max(2.0, min(float(settings.deepseek_timeout_seconds), 20.0))
    if _has_request_runtime_override(llm_runtime):
        timeout_seconds = min(timeout_seconds, 10.0)
    retries_per_base, retry_backoff_seconds = _resolve_runtime_retry_policy(llm_runtime)
    return DeepSeekClient(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_seconds=timeout_seconds,
        retries_per_base=retries_per_base,
        retry_backoff_seconds=retry_backoff_seconds,
        max_concurrency=settings.llm_global_max_concurrency,
        min_interval_seconds=settings.llm_global_min_interval_seconds,
        request_jitter_seconds=settings.llm_global_jitter_seconds,
    )


def _build_reasoning_client(
    *,
    timeout_seconds: float | None = None,
    llm_runtime: dict[str, Any] | None = None,
) -> DeepSeekClient | None:
    _, api_key, base_url, model = _resolve_runtime_llm_config(llm_runtime)
    if not api_key or not base_url or not model:
        return None
    resolved_timeout = float(timeout_seconds or settings.deep_beta_reasoning_llm_timeout_seconds)
    resolved_timeout = max(2.0, min(resolved_timeout, 120.0))
    if _has_request_runtime_override(llm_runtime):
        resolved_timeout = min(resolved_timeout, 18.0)
    retries_per_base, retry_backoff_seconds = _resolve_runtime_retry_policy(llm_runtime)
    return DeepSeekClient(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_seconds=resolved_timeout,
        retries_per_base=retries_per_base,
        retry_backoff_seconds=retry_backoff_seconds,
        max_concurrency=settings.llm_global_max_concurrency,
        min_interval_seconds=settings.llm_global_min_interval_seconds,
        request_jitter_seconds=settings.llm_global_jitter_seconds,
    )


def _parse_json_from_llm(raw_text: str) -> dict[str, Any]:
    cleaned = _strip_markdown_fence(str(raw_text or "").strip())
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("llm_json_not_object")
    return parsed


def _run_deep_beta_llm_reasoning_node(
    *,
    node_name: str,
    objective: str,
    topic: str,
    query_plan: dict[str, Any],
    retrieval_budget: dict[str, Any],
    deep_pass_summaries: list[dict[str, Any]],
    evidence_rows: list[dict[str, Any]],
    llm_runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    handoff_profile = _resolve_evidence_handoff_profile("deep_beta")
    if not settings.deep_beta_reasoning_llm_enabled:
        return {
            "node": node_name,
            "status": "skipped",
            "reason": "deep_beta_reasoning_llm_disabled",
            "confidence": 0.0,
            "insights": [],
            "actions": [],
            "watchouts": [],
            "reasoning_chain": [],
        }
    _, api_key, _base_url, _model = _resolve_runtime_llm_config(llm_runtime)
    if not api_key:
        return {
            "node": node_name,
            "status": "degraded",
            "reason": "api_key_missing",
            "confidence": 0.0,
            "insights": [],
            "actions": [],
            "watchouts": [],
            "reasoning_chain": [],
        }

    compact_passes = [
        {
            "pass_index": item.get("pass_index"),
            "subquery": item.get("subquery"),
            "retrieved_count": item.get("retrieved_count"),
            "duration_ms": item.get("duration_ms"),
            "source_errors": item.get("source_errors", {}),
        }
        for item in deep_pass_summaries[: handoff_profile["reasoning_pass_summaries"]]
        if isinstance(item, dict)
    ]
    compact_evidence = [
        {
            "id": item.get("id"),
            "source": item.get("source"),
            "title": item.get("title"),
            "score": item.get("score"),
            "text": _compact_snippet(item.get("text", ""), max_len=220),
        }
        for item in evidence_rows[: handoff_profile["reasoning_evidence_rows"]]
        if isinstance(item, dict)
    ]

    system_prompt = (
        "You are a clinical research reasoning worker node in a multi-agent RAG pipeline. "
        "Return STRICT JSON only. No markdown. No extra keys."
    )
    prompt = (
        "Analyze this node objective and produce structured reasoning output.\n"
        "Output EXACT JSON:\n"
        "{\n"
        '  "confidence": 0.0,\n'
        '  "insights": ["short insight"],\n'
        '  "actions": ["next action"],\n'
        '  "watchouts": ["risk/caveat"],\n'
        '  "reasoning_chain": [\n'
        "    {\n"
        '      "claim": "short claim",\n'
        '      "evidence": "which evidence supports/weakens the claim",\n'
        '      "inference": "clinical interpretation from evidence",\n'
        '      "clinical_action": "practical action/escalation",\n'
        '      "confidence": 0.0\n'
        "    }\n"
        "  ],\n"
        '  "follow_up_queries": ["targeted retrieval query"],\n'
        '  "evidence_checks": ["specific evidence check"]\n'
        "}\n"
        "Constraints:\n"
        "- confidence must be between 0 and 1\n"
        "- each array size <= 6\n"
        "- reasoning_chain item count <= 4, each field must be concise and concrete\n"
        "- every reasoning_chain item must mention a concrete evidence signal (source title/id/snippet)\n"
        "- focus on evidence quality, contradiction risk, and retrieval gaps\n\n"
        f"node_name={node_name}\n"
        f"objective={objective}\n"
        f"topic={topic}\n"
        f"query_plan={json.dumps(query_plan, ensure_ascii=False)}\n"
        f"retrieval_budget={json.dumps(retrieval_budget, ensure_ascii=False)}\n"
        f"deep_pass_summaries={json.dumps(compact_passes, ensure_ascii=False)}\n"
        f"evidence_rows={json.dumps(compact_evidence, ensure_ascii=False)}\n"
    )

    try:
        client = _build_reasoning_client(llm_runtime=llm_runtime)
        if client is None:
            return {
                "node": node_name,
                "status": "degraded",
                "reason": "runtime_llm_unconfigured",
                "confidence": 0.0,
                "insights": [],
                "actions": [],
                "watchouts": [],
                "reasoning_chain": [],
                "follow_up_queries": [],
                "evidence_checks": [],
            }
        response = client.generate(prompt=prompt, system_prompt=system_prompt)
        parsed = _parse_json_from_llm(response.content)
        confidence = _normalize_router_confidence(parsed.get("confidence"))

        def _clean_list(key: str) -> list[str]:
            raw = parsed.get(key)
            if not isinstance(raw, list):
                return []
            cleaned: list[str] = []
            for item in raw[:6]:
                text = " ".join(str(item or "").split()).strip()
                if text:
                    cleaned.append(text)
            return cleaned

        def _clean_reasoning_chain(value: Any) -> list[dict[str, Any]]:
            if not isinstance(value, list):
                return []
            cleaned: list[dict[str, Any]] = []
            for item in value[:4]:
                if not isinstance(item, dict):
                    continue
                claim = " ".join(str(item.get("claim") or "").split()).strip()
                evidence = " ".join(str(item.get("evidence") or "").split()).strip()
                inference = " ".join(str(item.get("inference") or "").split()).strip()
                clinical_action = " ".join(str(item.get("clinical_action") or "").split()).strip()
                if not any((claim, evidence, inference, clinical_action)):
                    continue
                cleaned.append(
                    {
                        "claim": _compact_snippet(claim, max_len=220),
                        "evidence": _compact_snippet(evidence, max_len=260),
                        "inference": _compact_snippet(inference, max_len=240),
                        "clinical_action": _compact_snippet(clinical_action, max_len=180),
                        "confidence": _normalize_router_confidence(item.get("confidence")),
                    }
                )
            return cleaned

        return {
            "node": node_name,
            "status": "completed",
            "reason": "ok",
            "model_used": response.model,
            "confidence": confidence,
            "insights": _clean_list("insights"),
            "actions": _clean_list("actions"),
            "watchouts": _clean_list("watchouts"),
            "reasoning_chain": _clean_reasoning_chain(parsed.get("reasoning_chain")),
            "follow_up_queries": _clean_list("follow_up_queries"),
            "evidence_checks": _clean_list("evidence_checks"),
        }
    except Exception as exc:  # pragma: no cover - provider/network defensive path
        return {
            "node": node_name,
            "status": "degraded",
            "reason": f"{exc.__class__.__name__}",
            "confidence": 0.0,
            "insights": [],
            "actions": [],
            "watchouts": [],
            "reasoning_chain": [],
            "follow_up_queries": [],
            "evidence_checks": [],
        }


def _run_deep_beta_parallel_reasoning_nodes(
    *,
    topic: str,
    query_plan: dict[str, Any],
    retrieval_budget: dict[str, Any],
    deep_pass_summaries: list[dict[str, Any]],
    evidence_rows: list[dict[str, Any]],
    llm_runtime: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    nodes = list(_DEEP_BETA_PARALLEL_REASONING_NODES)
    max_nodes = max(1, min(int(settings.deep_beta_reasoning_llm_nodes), len(nodes)))
    selected_nodes = nodes[:max_nodes]
    if not selected_nodes:
        return []

    reasoning_rounds = max(1, int(settings.deep_beta_reasoning_rounds))
    max_workers = max(1, min(int(settings.deep_beta_reasoning_parallel_workers), len(selected_nodes)))
    outputs: list[dict[str, Any]] = []
    for round_index in range(1, reasoning_rounds + 1):
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="deep-beta-llm") as executor:
            futures = {
                executor.submit(
                    _run_deep_beta_llm_reasoning_node,
                    node_name=node_name,
                    objective=(
                        f"{objective} "
                        f"(round {round_index}/{reasoning_rounds}; prioritize unresolved gaps from earlier rounds)"
                        if reasoning_rounds > 1
                        else objective
                    ),
                    topic=topic,
                    query_plan=query_plan,
                    retrieval_budget=retrieval_budget,
                    deep_pass_summaries=deep_pass_summaries,
                    evidence_rows=evidence_rows,
                    llm_runtime=llm_runtime,
                ): node_name
                for node_name, objective in selected_nodes
            }
            for future in as_completed(futures):
                node_name = futures[future]
                try:
                    result = future.result()
                except Exception as exc:  # pragma: no cover - defensive
                    result = {
                        "node": node_name,
                        "status": "degraded",
                        "reason": f"{exc.__class__.__name__}",
                        "confidence": 0.0,
                        "insights": [],
                        "actions": [],
                        "watchouts": [],
                        "reasoning_chain": [],
                        "follow_up_queries": [],
                        "evidence_checks": [],
                    }
                result["round"] = round_index
                result["rounds_total"] = reasoning_rounds
                outputs.append(result)
        if round_index < reasoning_rounds:
            _pause_between_pipeline_parts(multiplier=0.8)
    outputs.sort(
        key=lambda item: (
            str(item.get("node")),
            _safe_int(item.get("round"), 0),
        )
    )
    return outputs


def _collect_reasoning_follow_up_queries(
    reasoning_nodes: list[dict[str, Any]],
    *,
    limit: int,
) -> list[str]:
    if limit <= 0:
        return []
    collected: list[str] = []
    for node in reasoning_nodes:
        if not isinstance(node, dict):
            continue
        for key in ("follow_up_queries", "evidence_checks", "actions", "watchouts"):
            raw = node.get(key)
            if not isinstance(raw, list):
                continue
            for item in raw:
                text = " ".join(str(item or "").split()).strip()
                if not text:
                    continue
                collected.append(text)
        chain_rows = node.get("reasoning_chain")
        if isinstance(chain_rows, list):
            for item in chain_rows:
                if not isinstance(item, dict):
                    continue
                for key in ("claim", "evidence", "inference", "clinical_action"):
                    text = " ".join(str(item.get(key) or "").split()).strip()
                    if text:
                        collected.append(text)
    return _dedupe_query_list(collected, limit=limit)


def _run_deep_beta_evidence_verification_node(
    *,
    topic: str,
    deep_pass_summaries: list[dict[str, Any]],
    evidence_rows: list[dict[str, Any]],
    reasoning_nodes: list[dict[str, Any]],
    llm_runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    handoff_profile = _resolve_evidence_handoff_profile("deep_beta")
    if not settings.deep_beta_evidence_verification_enabled:
        return {
            "status": "skipped",
            "verification_confidence": 0.0,
            "supported_claims": [],
            "unsupported_claims": [],
            "contradicted_claims": [],
            "evidence_gaps": [],
            "high_risk_flags": [],
            "model_used": "disabled",
        }
    _, api_key, _base_url, _model = _resolve_runtime_llm_config(llm_runtime)
    if not api_key:
        return {
            "status": "degraded",
            "verification_confidence": 0.0,
            "supported_claims": [],
            "unsupported_claims": [],
            "contradicted_claims": [],
            "evidence_gaps": ["DeepSeek API key missing."],
            "high_risk_flags": [],
            "model_used": "unconfigured",
        }

    compact_passes = [
        {
            "pass_index": item.get("pass_index"),
            "subquery": item.get("subquery"),
            "retrieved_count": item.get("retrieved_count"),
            "source_errors": item.get("source_errors", {}),
        }
        for item in deep_pass_summaries[: handoff_profile["verification_pass_summaries"]]
        if isinstance(item, dict)
    ]
    compact_evidence = [
        {
            "id": item.get("id"),
            "source": item.get("source"),
            "title": item.get("title"),
            "score": item.get("score"),
            "snippet": _compact_snippet(item.get("text"), max_len=180),
        }
        for item in evidence_rows[: handoff_profile["verification_evidence_rows"]]
        if isinstance(item, dict)
    ]
    compact_nodes = [
        {
            "node": item.get("node"),
            "status": item.get("status"),
            "confidence": item.get("confidence"),
            "insights": item.get("insights", [])[:3] if isinstance(item.get("insights"), list) else [],
            "watchouts": item.get("watchouts", [])[:3] if isinstance(item.get("watchouts"), list) else [],
            "reasoning_chain": (
                item.get("reasoning_chain", [])[
                    : handoff_profile["verification_reasoning_chain_per_node"]
                ]
                if isinstance(item.get("reasoning_chain"), list)
                else []
            ),
        }
        for item in reasoning_nodes[: handoff_profile["verification_reasoning_nodes"]]
        if isinstance(item, dict)
    ]
    prompt = (
        "Verify evidence support at claim level for this deep research run.\n"
        "Output STRICT JSON only with exact schema:\n"
        "{\n"
        '  "verification_confidence": 0.0,\n'
        '  "supported_claims": ["..."],\n'
        '  "unsupported_claims": ["..."],\n'
        '  "contradicted_claims": ["..."],\n'
        '  "evidence_gaps": ["..."],\n'
        '  "high_risk_flags": ["..."]\n'
        "}\n"
        "Rules:\n"
        "- keep each list <= 8 items\n"
        "- do not prescribe diagnosis/dose\n"
        "- high_risk_flags should prioritize clinical safety issues\n"
        "- if evidence is weak, explicitly add to evidence_gaps\n\n"
        f"topic={topic}\n"
        f"deep_pass_summaries={json.dumps(compact_passes, ensure_ascii=False)}\n"
        f"evidence_rows={json.dumps(compact_evidence, ensure_ascii=False)}\n"
        f"reasoning_nodes={json.dumps(compact_nodes, ensure_ascii=False)}\n"
    )
    try:
        client = _build_reasoning_client(
            timeout_seconds=max(float(settings.deep_beta_evidence_verification_timeout_seconds), 2.0),
            llm_runtime=llm_runtime,
        )
        if client is None:
            raise RuntimeError("runtime_llm_unconfigured")
        response = client.generate(
            prompt=prompt,
            system_prompt=(
                "You are CLARA deep evidence verifier. "
                "Be conservative and safety-first. Output strict JSON only."
            ),
        )
        parsed = _parse_json_from_llm(response.content)

        def _clean(value: Any) -> list[str]:
            if not isinstance(value, list):
                return []
            cleaned: list[str] = []
            for item in value[:8]:
                text = " ".join(str(item or "").split()).strip()
                if text:
                    cleaned.append(text)
            return cleaned

        return {
            "status": "completed",
            "verification_confidence": _normalize_router_confidence(
                parsed.get("verification_confidence")
            ),
            "supported_claims": _clean(parsed.get("supported_claims")),
            "unsupported_claims": _clean(parsed.get("unsupported_claims")),
            "contradicted_claims": _clean(parsed.get("contradicted_claims")),
            "evidence_gaps": _clean(parsed.get("evidence_gaps")),
            "high_risk_flags": _clean(parsed.get("high_risk_flags")),
            "model_used": response.model,
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "status": "degraded",
            "verification_confidence": 0.0,
            "supported_claims": [],
            "unsupported_claims": [],
            "contradicted_claims": [],
            "evidence_gaps": [f"evidence_verification_error:{exc.__class__.__name__}"],
            "high_risk_flags": [],
            "model_used": "error",
        }


def _run_deep_beta_quality_gate(
    *,
    topic: str,
    answer_markdown: str,
    citations: list[Citation],
    verification_matrix_payload: dict[str, Any],
    reasoning_nodes: list[dict[str, Any]],
    evidence_verification: dict[str, Any] | None = None,
    llm_runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not settings.deep_beta_quality_gate_enabled:
        return {
            "status": "skipped",
            "quality_score": 0.0,
            "groundedness_score": 0.0,
            "completeness_score": 0.0,
            "revision_required": False,
            "findings": [],
            "follow_up_actions": [],
        }
    _, api_key, _base_url, _model = _resolve_runtime_llm_config(llm_runtime)
    if not api_key:
        return {
            "status": "degraded",
            "quality_score": 0.0,
            "groundedness_score": 0.0,
            "completeness_score": 0.0,
            "revision_required": False,
            "findings": ["DeepSeek API key missing for quality gate."],
            "follow_up_actions": [],
        }

    compact_citations = [
        {
            "source_id": item.source_id,
            "source": item.source,
            "title": item.title,
            "url": item.url,
        }
        for item in citations[:14]
    ]
    prompt = (
        "Evaluate this medical deep-research markdown answer quality.\n"
        "Return STRICT JSON only.\n"
        "Schema:\n"
        "{\n"
        '  "quality_score": 0.0,\n'
        '  "groundedness_score": 0.0,\n'
        '  "completeness_score": 0.0,\n'
        '  "revision_required": false,\n'
        '  "findings": ["..."],\n'
        '  "follow_up_actions": ["..."]\n'
        "}\n"
        "Rules:\n"
        "- scores in [0,1]\n"
        "- findings/follow_up_actions max 6 each\n"
        "- penalize unsupported clinical claims, missing safety caveats, weak attribution\n\n"
        f"topic={topic}\n"
        f"answer_markdown={answer_markdown}\n"
        f"citations={json.dumps(compact_citations, ensure_ascii=False)}\n"
        f"verification_matrix={json.dumps(verification_matrix_payload, ensure_ascii=False)}\n"
        f"evidence_verification={json.dumps(evidence_verification or {}, ensure_ascii=False)}\n"
        f"reasoning_nodes={json.dumps(reasoning_nodes[:12], ensure_ascii=False)}\n"
    )
    try:
        client = _build_reasoning_client(
            timeout_seconds=max(float(settings.deep_beta_quality_gate_timeout_seconds), 2.0),
            llm_runtime=llm_runtime,
        )
        if client is None:
            raise RuntimeError("runtime_llm_unconfigured")
        response = client.generate(
            prompt=prompt,
            system_prompt=(
                "You are CLARA quality gate evaluator for medical RAG reports. "
                "Be strict and safety-first. Output strict JSON only."
            ),
        )
        parsed = _parse_json_from_llm(response.content)
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "status": "degraded",
            "quality_score": 0.0,
            "groundedness_score": 0.0,
            "completeness_score": 0.0,
            "revision_required": False,
            "findings": [f"quality_gate_error:{exc.__class__.__name__}"],
            "follow_up_actions": [],
        }

    def _clamp(value: Any) -> float:
        return _normalize_router_confidence(value)

    def _clean_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        cleaned: list[str] = []
        for item in value[:6]:
            text = " ".join(str(item or "").split()).strip()
            if text:
                cleaned.append(text)
        return cleaned

    return {
        "status": "completed",
        "quality_score": _clamp(parsed.get("quality_score")),
        "groundedness_score": _clamp(parsed.get("groundedness_score")),
        "completeness_score": _clamp(parsed.get("completeness_score")),
        "revision_required": bool(parsed.get("revision_required", False)),
        "findings": _clean_list(parsed.get("findings")),
        "follow_up_actions": _clean_list(parsed.get("follow_up_actions")),
    }


def _normalize_mermaid_block_body(body: str) -> str:
    normalized = str(body or "")
    normalized = re.sub(r"<\s*br\s*/?\s*>", "\n", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"</?[a-z][^>\n]*>", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"&nbsp;", " ", normalized, flags=re.IGNORECASE)
    # Normalize inline citations like " ... [1]" or " ... [pubmed-123]".
    normalized = re.sub(
        r"(?<=\s)\[((?:\d{1,3})|(?:[A-Za-z][A-Za-z0-9_.:-]{2,}))\](?=(?:\s|$|[.,;:\]]))",
        r"(\1)",
        normalized,
    )
    return "\n".join(line.rstrip() for line in normalized.splitlines()).strip()


def _strip_html_from_mermaid_blocks(markdown_text: str) -> str:
    text = str(markdown_text or "")
    pattern = re.compile(r"```mermaid\s*(.*?)```", flags=re.DOTALL | re.IGNORECASE)

    def _normalize(block: re.Match[str]) -> str:
        body = _normalize_mermaid_block_body(block.group(1))
        return f"```mermaid\n{body}\n```"

    return pattern.sub(_normalize, text)


def _canonical_h2_key(heading: str) -> str:
    text = str(heading or "")
    if text.startswith("## "):
        text = text[3:]
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).strip().lower()
    return text


_SECTION_TITLES_BY_LANGUAGE: dict[str, dict[str, str]] = {
    "vi": {
        "quick_conclusion": "Kết luận nhanh",
        "key_points": "Điểm chính",
        "detailed_analysis": "Phân tích chi tiết",
        "practical_application": "Ứng dụng thực tế",
        "safety_guidance": "Khuyến nghị an toàn",
        "safety_notes": "Lưu ý an toàn",
        "monitoring_red_flags": "Theo dõi & cảnh báo đỏ",
        "research_plan": "Kế hoạch nghiên cứu",
        "executive_summary": "Tóm tắt điều hành",
        "clinical_context": "Bối cảnh lâm sàng áp dụng",
        "practice_recommendations": "Khuyến nghị ứng dụng thực hành",
        "evidence_table": "Bảng tổng hợp bằng chứng",
        "limitations_legal": "Giới hạn, sai số và rủi ro pháp lý",
    },
    "en": {
        "quick_conclusion": "Quick conclusion",
        "key_points": "Key points",
        "detailed_analysis": "Detailed analysis",
        "practical_application": "Practical application",
        "safety_guidance": "Safety recommendations",
        "safety_notes": "Important caveats",
        "monitoring_red_flags": "Monitoring & red flags",
        "research_plan": "Research plan",
        "executive_summary": "Executive summary",
        "clinical_context": "Clinical context",
        "practice_recommendations": "Practical recommendations",
        "evidence_table": "Evidence summary table",
        "limitations_legal": "Limitations, error bands, and legal risk",
    },
}

_DEEP_BETA_DOSSIER_HEADINGS_BY_LANGUAGE: dict[str, tuple[str, ...]] = {
    "vi": _REQUIRED_DEEP_BETA_MARKDOWN_HEADINGS,
    "en": (
        "## Quick conclusion",
        "## Executive summary",
        "## Research question (PICO)",
        "## Retrieval method & selection criteria",
        "## Evidence profile & source quality",
        "## Main findings synthesis",
        "## Evidence reasoning chain",
        "## Counter-evidence and contradictions",
        "## Clinical application by patient subgroup",
        "## Safety decision matrix",
        "## Follow-up plan after counseling",
        "## Limitations, error bands, and legal risk",
    ),
}


def _resolve_section_title(section_id: str, answer_language: str) -> str:
    language = "en" if str(answer_language or "").strip().lower() == "en" else "vi"
    return _SECTION_TITLES_BY_LANGUAGE.get(language, _SECTION_TITLES_BY_LANGUAGE["vi"]).get(
        section_id,
        section_id,
    )


def _resolve_deep_beta_dossier_headings(answer_language: str) -> list[str]:
    language = "en" if str(answer_language or "").strip().lower() == "en" else "vi"
    return list(
        _DEEP_BETA_DOSSIER_HEADINGS_BY_LANGUAGE.get(
            language,
            _DEEP_BETA_DOSSIER_HEADINGS_BY_LANGUAGE["vi"],
        )
    )


_USER_FACING_HEADING_ALIASES = {
    _canonical_h2_key("Quick conclusion"): "quick_conclusion",
    _canonical_h2_key("Quick take"): "quick_conclusion",
    _canonical_h2_key("Bottom line"): "quick_conclusion",
    _canonical_h2_key("Key takeaways"): "quick_conclusion",
    _canonical_h2_key("Kết luận nhanh"): "quick_conclusion",
    _canonical_h2_key("Key points"): "key_points",
    _canonical_h2_key("Main points"): "key_points",
    _canonical_h2_key("Main analysis"): "key_points",
    _canonical_h2_key("Điểm chính"): "key_points",
    _canonical_h2_key("Detailed analysis"): "detailed_analysis",
    _canonical_h2_key("Analysis"): "detailed_analysis",
    _canonical_h2_key("Clinical analysis"): "detailed_analysis",
    _canonical_h2_key("Discussion"): "detailed_analysis",
    _canonical_h2_key("Assessment"): "detailed_analysis",
    _canonical_h2_key("Phân tích chi tiết"): "detailed_analysis",
    _canonical_h2_key("Practical application"): "practical_application",
    _canonical_h2_key("Practical implications"): "practical_application",
    _canonical_h2_key("Next steps"): "practical_application",
    _canonical_h2_key("Ứng dụng thực tế"): "practical_application",
    _canonical_h2_key("Safety recommendations"): "safety_guidance",
    _canonical_h2_key("Safety guidance"): "safety_guidance",
    _canonical_h2_key("Safety considerations"): "safety_guidance",
    _canonical_h2_key("Safety notes"): "safety_guidance",
    _canonical_h2_key("Khuyến nghị an toàn"): "safety_guidance",
    _canonical_h2_key("Important caveats"): "safety_notes",
    _canonical_h2_key("Caveats"): "safety_notes",
    _canonical_h2_key("Lưu ý an toàn"): "safety_notes",
    _canonical_h2_key("Monitoring and red flags"): "monitoring_red_flags",
    _canonical_h2_key("Monitoring & red flags"): "monitoring_red_flags",
    _canonical_h2_key("Follow-up and red flags"): "monitoring_red_flags",
    _canonical_h2_key("Follow up and red flags"): "monitoring_red_flags",
    _canonical_h2_key("Theo dõi & cảnh báo đỏ"): "monitoring_red_flags",
    _canonical_h2_key("Research plan"): "research_plan",
    _canonical_h2_key("Search plan"): "research_plan",
    _canonical_h2_key("Investigation plan"): "research_plan",
    _canonical_h2_key("Kế hoạch nghiên cứu"): "research_plan",
    _canonical_h2_key("Executive summary"): "executive_summary",
    _canonical_h2_key("Executive overview"): "executive_summary",
    _canonical_h2_key("Tóm tắt điều hành"): "executive_summary",
    _canonical_h2_key("Clinical context"): "clinical_context",
    _canonical_h2_key("Clinical applicability"): "clinical_context",
    _canonical_h2_key("Bối cảnh lâm sàng áp dụng"): "clinical_context",
    _canonical_h2_key("Practical recommendations"): "practice_recommendations",
    _canonical_h2_key("Practice implications"): "practice_recommendations",
    _canonical_h2_key("Khuyến nghị ứng dụng thực hành"): "practice_recommendations",
    _canonical_h2_key("Evidence summary table"): "evidence_table",
    _canonical_h2_key("Evidence table"): "evidence_table",
    _canonical_h2_key("Bảng tổng hợp bằng chứng"): "evidence_table",
    _canonical_h2_key("Research question (PICO)"): "research_plan",
    _canonical_h2_key("Câu hỏi nghiên cứu (PICO)"): "research_plan",
    _canonical_h2_key("Retrieval method & selection criteria"): "research_plan",
    _canonical_h2_key("Phương pháp truy xuất & tiêu chí chọn lọc"): "research_plan",
    _canonical_h2_key("Evidence profile & source quality"): "evidence_table",
    _canonical_h2_key("Hồ sơ bằng chứng & chất lượng nguồn"): "evidence_table",
    _canonical_h2_key("Main findings synthesis"): "key_points",
    _canonical_h2_key("Tổng hợp phát hiện chính"): "key_points",
    _canonical_h2_key("Evidence reasoning chain"): "detailed_analysis",
    _canonical_h2_key("Chuỗi lập luận bằng chứng"): "detailed_analysis",
    _canonical_h2_key("Counter-evidence and contradictions"): "safety_notes",
    _canonical_h2_key("Phản biện bằng chứng đối nghịch"): "safety_notes",
    _canonical_h2_key("Clinical application by patient subgroup"): "clinical_context",
    _canonical_h2_key("Ứng dụng lâm sàng theo nhóm bệnh nhân"): "clinical_context",
    _canonical_h2_key("Safety decision matrix"): "safety_guidance",
    _canonical_h2_key("Ma trận quyết định an toàn"): "safety_guidance",
    _canonical_h2_key("Follow-up plan after counseling"): "monitoring_red_flags",
    _canonical_h2_key("Kế hoạch theo dõi sau tư vấn"): "monitoring_red_flags",
    _canonical_h2_key("Limitations legal and safety notes"): "limitations_legal",
    _canonical_h2_key("Limitations and legal notes"): "limitations_legal",
    _canonical_h2_key("Giới hạn, sai số và rủi ro pháp lý"): "limitations_legal",
}

_USER_FACING_NOISE_LINE_KEYS = {
    _canonical_h2_key("Markdown"),
    _canonical_h2_key("Copy"),
    _canonical_h2_key("Clinical analysis report"),
    _canonical_h2_key("Bao cao phan tich lam sang"),
}


def _normalize_user_facing_answer_markdown(
    markdown_text: str,
    *,
    answer_language: str = "vi",
) -> str:
    text = str(markdown_text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return text

    output_lines: list[str] = []
    previous_blank = False
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            if output_lines and not previous_blank:
                output_lines.append("")
            previous_blank = True
            continue

        previous_blank = False
        plain_key = _canonical_h2_key(stripped)
        if plain_key in _USER_FACING_NOISE_LINE_KEYS:
            continue

        if stripped.startswith("#"):
            prefix_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
            if prefix_match:
                hashes, heading_text = prefix_match.groups()
                alias = _USER_FACING_HEADING_ALIASES.get(_canonical_h2_key(heading_text))
                if alias:
                    line = f"{hashes} {_resolve_section_title(alias, answer_language)}"
                    stripped = line.strip()

        normalized_bullet = re.sub(r"^[•●▪◦‣]\s*", "- ", stripped)
        normalized_numbered = re.sub(r"^(\d+)\)\s+", r"\1. ", normalized_bullet)
        if normalized_numbered != stripped:
            line = normalized_numbered

        output_lines.append(line)

    normalized = "\n".join(output_lines)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _resolve_required_deep_heading_key(heading: str) -> str:
    key = _canonical_h2_key(heading)
    if not key:
        return ""
    for required in _REQUIRED_DEEP_DEDUP_HEADINGS:
        required_key = _canonical_h2_key(required)
        if key == required_key or key.startswith(f"{required_key} "):
            return required_key
    return key


def _dedupe_duplicate_h2_headings(markdown_text: str) -> str:
    lines = [line.rstrip() for line in str(markdown_text or "").splitlines()]
    prelude: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            if current_heading is None:
                if current_lines:
                    prelude.extend(current_lines)
            else:
                sections.append((current_heading, current_lines))
            current_heading = stripped
            current_lines = [line]
            continue
        current_lines.append(line)
    if current_heading is None:
        if current_lines:
            prelude.extend(current_lines)
    else:
        sections.append((current_heading, current_lines))

    required_heading_by_key = {
        _canonical_h2_key(item): item for item in _REQUIRED_DEEP_DEDUP_HEADINGS
    }
    singleton_keys = set(required_heading_by_key.keys())
    output: list[str] = [line for line in prelude if line.strip()]
    block_plan: list[tuple[str, str | list[str]]] = []
    singleton_best_blocks: dict[str, list[str]] = {}
    previous_key: str | None = None

    for heading, block_lines in sections:
        key = _resolve_required_deep_heading_key(heading)
        if not key:
            continue
        if key in singleton_keys:
            current_best = singleton_best_blocks.get(key)
            current_len = sum(len(item.strip()) for item in block_lines[1:] if item.strip())
            if current_best is None:
                singleton_best_blocks[key] = block_lines
                block_plan.append(("singleton", key))
            else:
                previous_len = sum(len(item.strip()) for item in current_best[1:] if item.strip())
                if current_len > previous_len:
                    singleton_best_blocks[key] = block_lines
            previous_key = key
            continue
        if key == previous_key:
            continue
        block_plan.append(("block", block_lines))
        previous_key = key

    emitted_singleton: set[str] = set()
    for block_type, payload in block_plan:
        if block_type == "singleton":
            singleton_key = str(payload)
            if singleton_key in emitted_singleton:
                continue
            block_lines = singleton_best_blocks.get(singleton_key)
            if block_lines:
                canonical_heading = required_heading_by_key.get(singleton_key)
                normalized_block = list(block_lines)
                if canonical_heading:
                    normalized_block[0] = canonical_heading
                output.extend(normalized_block)
                emitted_singleton.add(singleton_key)
            continue
        if isinstance(payload, list):
            output.extend(payload)
    return "\n".join(output).strip() + "\n"


def _sanitize_deep_beta_markdown_output(markdown_text: str) -> str:
    return _dedupe_duplicate_h2_headings(_strip_html_from_mermaid_blocks(markdown_text))


#: A markdown table layout/separator row carries no prose — only pipes, dashes,
#: colons, and whitespace (e.g. ``| --- | :--: |``). Such rows are dropped before
#: counting so table scaffolding never inflates the word count, while table
#: *content* rows (their cell text) are kept.
_MARKDOWN_TABLE_LAYOUT_RE = re.compile(r"^[\s|:\-]+$")


def _markdown_word_count(text: str) -> int:
    """Return the markdown-aware prose word count for ``text``.

    This is the SINGLE word counter used across budget resolution, the
    expansion/convergence loop, and min-word enforcement (design Property P7),
    so the meaning of a "word" is identical everywhere and a target expressed in
    words is compared against an equivalently measured body. Markdown scaffolding
    is stripped first so structural punctuation never inflates the count:

    * fenced code blocks are removed entirely (code is not prose),
    * table layout/separator rows are dropped (content rows are kept),
    * link/image syntax is reduced to its visible label,
    * heading / list / emphasis / blockquote / pipe / rule markers are stripped.

    Only tokens carrying at least one word character are counted, so leftover
    punctuation (``---``, stray ``|`` …) is never mistaken for a word.
    """

    source = str(text or "")
    if not source.strip():
        return 0

    # 1. Drop fenced code blocks entirely.
    cleaned = re.sub(r"```[\s\S]*?```", " ", source)

    # 2. Drop table layout/separator rows while keeping table content rows.
    kept_lines = [
        line
        for line in cleaned.splitlines()
        if not (
            line.strip().startswith("|") and _MARKDOWN_TABLE_LAYOUT_RE.match(line.strip())
        )
    ]
    cleaned = "\n".join(kept_lines)

    # 3. Reduce markdown links/images to their visible label only.
    cleaned = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", cleaned)

    # 4. Strip structural / inline markdown markers, keeping surrounding text.
    cleaned = re.sub(r"[#>*_`~|]+", " ", cleaned)

    # 5. Count only tokens that contain at least one word character.
    return sum(1 for token in cleaned.split() if re.search(r"\w", token))


def _deep_beta_missing_required_headings(content: str, answer_language: str) -> list[str]:
    """Return the deep_beta dossier headings (R18.1) absent from ``content``.

    Uses the language-resolved ``_REQUIRED_DEEP_BETA_MARKDOWN_HEADINGS`` contract so a
    deficient draft can be completed by a generation pass before any programmatic
    fallback/padding is applied (design section 18, Requirement 18.1/18.3).
    """

    required = _resolve_deep_beta_dossier_headings(answer_language)
    return [heading for heading in required if not _has_markdown_heading(content, heading)]


def _build_reasoning_chain_cards(
    reasoning_nodes: list[dict[str, Any]],
    *,
    limit: int = 18,
) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for node in reasoning_nodes:
        if not isinstance(node, dict):
            continue
        node_name = _first_nonempty_text(node.get("node"), "deep_beta_node")
        node_confidence = _normalize_router_confidence(node.get("confidence"))
        chain_rows = node.get("reasoning_chain")
        if isinstance(chain_rows, list):
            for row in chain_rows:
                if not isinstance(row, dict):
                    continue
                claim = _compact_snippet(_first_nonempty_text(row.get("claim")), max_len=220)
                evidence = _compact_snippet(_first_nonempty_text(row.get("evidence")), max_len=260)
                inference = _compact_snippet(_first_nonempty_text(row.get("inference")), max_len=240)
                action = _compact_snippet(
                    _first_nonempty_text(row.get("clinical_action"), row.get("action")),
                    max_len=180,
                )
                if not any((claim, evidence, inference, action)):
                    continue
                cards.append(
                    {
                        "node": node_name,
                        "confidence": _normalize_router_confidence(
                            row.get("confidence", node_confidence)
                        ),
                        "claim": claim,
                        "evidence": evidence,
                        "inference": inference,
                        "clinical_action": action,
                    }
                )
                if len(cards) >= limit:
                    return cards
        if len(cards) >= limit:
            return cards

    if cards:
        return cards

    # Fallback synthesis when the node returns only flat insight/action lists.
    for node in reasoning_nodes:
        if not isinstance(node, dict):
            continue
        node_name = _first_nonempty_text(node.get("node"), "deep_beta_node")
        insights = node.get("insights") if isinstance(node.get("insights"), list) else []
        actions = node.get("actions") if isinstance(node.get("actions"), list) else []
        watchouts = node.get("watchouts") if isinstance(node.get("watchouts"), list) else []
        top_claim = _compact_snippet(insights[0], max_len=220) if insights else ""
        top_action = _compact_snippet(actions[0], max_len=180) if actions else ""
        top_watchout = _compact_snippet(watchouts[0], max_len=240) if watchouts else ""
        if not any((top_claim, top_action, top_watchout)):
            continue
        cards.append(
            {
                "node": node_name,
                "confidence": _normalize_router_confidence(node.get("confidence")),
                "claim": top_claim,
                "evidence": top_watchout,
                "inference": top_claim,
                "clinical_action": top_action,
            }
        )
        if len(cards) >= limit:
            break
    return cards


#: Ordered scope labels (narrowest → broadest) and their ``scope_factor`` in
#: [0.4, 1.0]. The ordering encodes Property P2 (scope monotonicity): a broader
#: scope label always carries a ``scope_factor`` greater-than-or-equal to a
#: narrower one, all else equal.
_SCOPE_FACTORS: dict[str, float] = {
    "narrow": 0.4,
    "standard": 0.62,
    "broad": 0.85,
    "comparative_multi": 1.0,
}


def _classify_query_scope(
    topic: str,
    *,
    citation_count: int = 0,
    deep_pass_count: int = 0,
    reasoning_node_count: int = 0,
) -> tuple[str, float]:
    """Classify a ``deep_beta`` query's scope and emit a ``scope_factor``.

    Returns a ``(scope_label, scope_factor)`` ScopeSignal where
    ``scope_label ∈ {narrow, standard, broad, comparative_multi}`` and
    ``scope_factor ∈ [0.4, 1.0]`` (Requirement 1.1).

    Pure and PII-free: it derives the signal only from accent-folded query
    tokens (via the existing :func:`_is_comparison_query`,
    :func:`_is_nutrition_diet_query`, :func:`_is_ddi_critical_topic` detectors
    plus multi-part / length intent cues) and the supplied non-identifying
    evidence-density counts. No query text is stored, logged, or returned.

    Broader, comparative, or multi-part questions justify a longer report and
    map to a higher ``scope_factor``; narrow definitional questions scale down.
    The label→factor mapping is monotonic in scope rank (design Property P2).
    """

    text = str(topic or "").strip()
    folded = _ascii_fold(text)
    word_count = len([token for token in folded.split() if token])

    is_comparison = _is_comparison_query(text)

    # Multi-part cues: clinical-domain breadth, conjunctions / enumerations,
    # multiple explicit questions, or a long, information-dense prompt.
    multipart_markers = (
        " va ",
        " and ",
        ";",
        " cung nhu ",
        " lan luot ",
        " dong thoi ",
    )
    multipart_hits = sum(1 for marker in multipart_markers if marker in folded)
    question_marks = text.count("?")
    is_multipart = multipart_hits >= 2 or question_marks >= 2 or word_count >= 32

    # Breadth-signalling domains (nutrition/diet and critical DDI topics) widen
    # scope even when phrased compactly.
    is_breadth_topic = _is_nutrition_diet_query(text) or _is_ddi_critical_topic(text)

    density = (
        max(0, int(citation_count))
        + max(0, int(deep_pass_count))
        + max(0, int(reasoning_node_count))
    )

    if is_comparison and (is_multipart or density >= 30):
        label = "comparative_multi"
    elif is_comparison or is_multipart or is_breadth_topic or density >= 40:
        label = "broad"
    elif word_count <= 8 and density < 12:
        label = "narrow"
    else:
        label = "standard"

    return label, _SCOPE_FACTORS[label]


def _resolve_deep_beta_word_budget() -> tuple[int, int, int]:
    # Respect runtime tuning while keeping a sensible long-form envelope.
    hard_min = 1200
    hard_max = 15000
    configured_min = int(settings.deep_beta_report_min_words)
    min_words = min(max(configured_min, hard_min), hard_max - 1200)

    # Keep page-based target, but avoid exploding target size when min_words is
    # intentionally tuned down for latency-sensitive environments.
    page_target = min(max(int(settings.deep_beta_report_target_pages), 3), 80)
    words_per_page = min(max(int(settings.deep_beta_report_words_per_page), 220), 900)
    configured_target = page_target * words_per_page
    baseline_target = min_words + max(450, int(min_words * 0.25))
    target_ceiling = min(hard_max - 900, max(min_words + 700, int(min_words * 2.0)))
    target_words = min(max(configured_target, baseline_target), target_ceiling)

    max_words = min(max(target_words + 1400, min_words + 900), hard_max)
    target_words = min(max(target_words, min_words), max_words)
    return min_words, target_words, max_words


def _resolve_deep_word_budget() -> tuple[int, int, int]:
    # Deep mode should read like a dense briefing, not a dossier.
    min_words = 900
    target_words = 1600
    max_words = 2800
    return min_words, target_words, max_words


def _smoothstep(value: float, lo: float, hi: float) -> float:
    """Monotonic Hermite ``smoothstep`` clamped to ``[0.0, 1.0]``.

    Returns ``0.0`` at/below ``lo``, ``1.0`` at/above ``hi``, and a smooth,
    monotonically non-decreasing ramp in between. Used to turn an unbounded
    evidence-density count into a bounded ``density_factor`` so the scope-aware
    budget grows smoothly with evidence (design Property P3, density
    monotonicity).
    """

    if hi <= lo:
        return 1.0 if value >= hi else 0.0
    if value <= lo:
        return 0.0
    if value >= hi:
        return 1.0
    t = (value - lo) / (hi - lo)
    return t * t * (3.0 - 2.0 * t)


def _resolve_scope_aware_word_budget(
    *,
    scope_factor: float,
    scope_label: str,
    citation_count: int = 0,
    deep_pass_count: int = 0,
    reasoning_node_count: int = 0,
) -> tuple[int, int, int]:
    """Scope-aware ``deep_beta`` word budget (synthesis v2 band math).

    Blends the query-scope signal (``scope_factor`` / ``scope_label`` from
    :func:`_classify_query_scope`) with evidence density (citations + retrieval
    passes + reasoning nodes) to produce a ``(min, target, max)`` envelope that
    scales smoothly from a no-pad floor for narrow/sparse queries up into the
    8,000-15,000 word band for broad, evidence-rich ones.

    Guarantees the design Correctness Properties:

    - **P1** invariant: ``min_words <= target <= max_words <= 15000``.
    - **P2** scope monotonicity: ``target`` non-decreasing in ``scope_factor``.
    - **P3** density monotonicity: ``target`` non-decreasing in evidence density.
    - **P4** broad band: a broad/comparative high-density query reaches ``>= 8000``.
    - **P5** no-pad floor: a narrow + sparse query lands below ``floor``.

    Pure and PII-free: it consumes only the scope signal and non-identifying
    evidence counts.
    """

    hard_max_ceiling = 15000

    # Documented floor: the configured ``deep_beta`` minimum, clamped to the
    # validated band so a misconfiguration cannot push it out of range.
    floor = min(max(int(settings.deep_beta_report_min_words), 4000), 12000)
    # Ceiling: the configured cap, never below ``floor + 2000`` nor above the
    # hard 15k ceiling (design section B + Requirement 1.4 / 6.5).
    hard_max = min(
        max(int(settings.deep_beta_report_max_words_cap), floor + 2000),
        hard_max_ceiling,
    )

    # Broad / comparative-multi questions anchor at the full floor; narrower
    # scopes relax the floor to ~0.7x so a narrow query can land below ``floor``
    # without padding (design Property P5, Requirement 1.3).
    if str(scope_label).strip().lower() in {"broad", "comparative_multi"}:
        min_words = floor
    else:
        min_words = round(floor * 0.7)
    min_words = min(min_words, hard_max)

    density = (
        max(0, int(citation_count))
        + max(0, int(deep_pass_count))
        + max(0, int(reasoning_node_count))
    )
    density_factor = _smoothstep(float(density), 10.0, 60.0)

    # Map ``scope_factor`` in [0.4, 1.0] onto a [0, 1] drive so a narrow query
    # (0.4) contributes no upward push while a comparative-multi query (1.0)
    # drives the target to the ceiling.
    scope_drive = max(0.0, min(1.0, (float(scope_factor) - 0.4) / 0.6))
    drive = max(scope_drive, density_factor * 0.9)

    target_words = round(min_words + drive * (hard_max - min_words))
    max_words = hard_max

    # Re-assert the invariant defensively (clamp rather than raise so a relaxed
    # bound can never surface a violation to callers — design error handling).
    target_words = min(max(target_words, min_words), max_words)
    max_words = min(max_words, hard_max_ceiling)
    min_words = min(min_words, target_words)
    return min_words, target_words, max_words


def _resolve_report_word_budget(research_mode: str) -> tuple[int, int, int]:
    mode = str(research_mode or "fast").strip().lower()
    if mode == "deep_beta":
        return _resolve_deep_beta_word_budget()
    return _resolve_deep_word_budget()


def _deep_beta_clean_body_active() -> bool:
    """Whether the clean-body Pro path is active for deep_beta synthesis.

    Clean-body is the default (natural, reader-first, single-language answer with
    no telemetry padding in the body). It DEFERS to an explicit ``synthesis_v2``
    opt-in: when synthesis_v2 is enabled the legacy scope-aware dossier path wins,
    so existing v2 behavior/tests are byte-for-byte preserved. Only when
    ``deep_beta_clean_body_enabled`` is true AND ``synthesis_v2_enabled`` is false
    do the clean-body branches take effect.
    """

    return bool(
        settings.deep_beta_clean_body_enabled and not settings.synthesis_v2_enabled
    )


def _resolve_adaptive_report_word_budget(
    *,
    research_mode: str,
    citation_count: int,
    deep_pass_count: int,
    reasoning_node_count: int,
    topic: str = "",
) -> tuple[int, int, int]:
    mode = str(research_mode or "fast").strip().lower()

    # Clean-body Pro (default): guide deep_beta to a natural long-form length
    # instead of the 8,000-15,000 word dossier target, so the answer explains
    # thoroughly without padding. The technical matrices/sources move to the
    # hidden telemetry panel, so the prose body itself stays readable.
    if mode == "deep_beta" and _deep_beta_clean_body_active():
        clean_min = int(settings.deep_beta_clean_body_min_words)
        clean_target = max(
            clean_min, int(settings.deep_beta_clean_body_target_words)
        )
        clean_max = max(
            clean_target, int(settings.deep_beta_clean_body_max_words)
        )
        return clean_min, clean_target, clean_max

    # Synthesis v2 (flag-gated): scope-aware band math for deep_beta only.
    # When the flag is off we fall through to the exact pre-feature behavior so
    # the budget is byte-identical to baseline (design Property P8).
    if mode == "deep_beta" and settings.synthesis_v2_enabled:
        scope_label, scope_factor = _classify_query_scope(
            topic,
            citation_count=citation_count,
            deep_pass_count=deep_pass_count,
            reasoning_node_count=reasoning_node_count,
        )
        min_words, target_words, max_words = _resolve_scope_aware_word_budget(
            scope_factor=scope_factor,
            scope_label=scope_label,
            citation_count=citation_count,
            deep_pass_count=deep_pass_count,
            reasoning_node_count=reasoning_node_count,
        )
        # Expose the resolved (min, target, max) envelope and the scope label in
        # trace/telemetry for observability (Requirement 1.6). PII-free by
        # construction: only the non-identifying scope category, the numeric
        # word-budget triple, and aggregate evidence counts are emitted — never
        # the query text or any user content.
        logger.info(
            "synthesis_v2 deep_beta budget resolved: "
            "scope=%s min_words=%d target_words=%d max_words=%d "
            "citations=%d passes=%d reasoning_nodes=%d",
            scope_label,
            min_words,
            target_words,
            max_words,
            max(0, int(citation_count)),
            max(0, int(deep_pass_count)),
            max(0, int(reasoning_node_count)),
        )
        return min_words, target_words, max_words

    min_words, target_words, max_words = _resolve_report_word_budget(mode)
    if mode != "deep_beta":
        return min_words, target_words, max_words

    evidence_density = max(0, int(citation_count)) + max(0, int(deep_pass_count)) + max(
        0, int(reasoning_node_count)
    )

    # Never downscale Deep Beta into short answers.
    adaptive_min = min_words
    adaptive_max = max_words
    adaptive_target = target_words
    if evidence_density >= 50:
        adaptive_target = min(adaptive_max, max(target_words + 1800, int(target_words * 1.18)))
    elif evidence_density >= 35:
        adaptive_target = min(adaptive_max, max(target_words + 900, int(target_words * 1.1)))
    adaptive_target = min(max(adaptive_target, adaptive_min), adaptive_max)
    return adaptive_min, adaptive_target, adaptive_max


def _resolve_query_type_directives(
    scope_label: str,
    topic: str,
) -> list[str]:
    """Query-type-aware section directives appended on the synthesis-v2 path.

    Pure and PII-free: derives extra framing directives from the scope label
    (from :func:`_classify_query_scope`) plus accent-folded intent cues, never
    storing or logging the query text. The returned directives are *appended*
    after the legacy dossier requirements so the executive-answer-first,
    decision-boundary, and safety sections always remain (Requirement 3.6, 5).

    The directives vary the report's analytic framing by query type
    (comparison vs single-intervention vs diagnostic-workup vs narrow) so the
    prose no longer reads as one fixed template (Requirement 3.1).
    """

    label = str(scope_label or "standard").strip().lower()
    folded = _ascii_fold(topic)

    # Diagnostic-workup intent cues (differential / red-flag framing).
    diagnostic_markers = (
        "chan doan",
        "chan doan phan biet",
        "trieu chung",
        "dau hieu",
        "tiep can",
        "workup",
        "differential",
        "diagnos",
        "symptom",
    )
    is_diagnostic = any(marker in folded for marker in diagnostic_markers)

    directives: list[str] = []

    if label == "comparative_multi":
        directives.append(
            "- frame as an options-comparison: contrast each option head-to-head on "
            "efficacy, safety, adherence, feasibility, and cost/access in a comparison table"
        )
        directives.append(
            "- close each comparison with a net decision recommendation and the conditions that flip it"
        )
    elif label == "broad":
        directives.append(
            "- expand the dossier with type-specific sub-sections so each analytic "
            "dimension (mechanism, evidence, subgroups, monitoring) gets dedicated depth"
        )

    if is_diagnostic:
        directives.append(
            "- include a differential-diagnosis framing with explicit red-flags and "
            "escalation criteria before management discussion"
        )

    if label == "narrow":
        directives.append(
            "- keep the brief compact: cover only the directly relevant sections without padding, "
            "while preserving the executive answer, decision boundary, and safety notes"
        )

    if not directives:
        # Standard scope still gets a de-templating nudge so the v2 path is
        # never byte-identical to the fixed legacy contract.
        directives.append(
            "- vary section emphasis to fit the specific question rather than emitting a fixed template"
        )

    return directives


def _resolve_report_section_contract(
    research_mode: str,
    *,
    answer_language: str = "vi",
    topic: str = "",
) -> tuple[list[str], list[str]]:
    mode = str(research_mode or "fast").strip().lower()
    quick_conclusion = f"## {_resolve_section_title('quick_conclusion', answer_language)}"
    key_points = f"## {_resolve_section_title('key_points', answer_language)}"
    practical_application = f"## {_resolve_section_title('practical_application', answer_language)}"
    important_caveats = f"## {_resolve_section_title('safety_notes', answer_language)}"
    detailed_analysis = f"## {_resolve_section_title('detailed_analysis', answer_language)}"
    # Clean-body Pro (default): a lean, reader-first explanatory contract instead
    # of the rigid 12-heading dossier. The answer explains thoroughly in natural
    # prose; matrices/sources/reasoning logs are NOT part of the body (they move
    # to the hidden telemetry panel from the response envelope). This is what
    # removes the "cố làm dài", the mixed VN/EN table headers, and the technical
    # confusion-matrix/source dump from the answer.
    if mode == "deep_beta" and _deep_beta_clean_body_active():
        language_label = "English" if answer_language == "en" else "Vietnamese"
        sections = [
            quick_conclusion,
            detailed_analysis,
            practical_application,
            important_caveats,
        ]
        requirements = [
            "- open with a direct, decision-oriented answer in 3-5 sentences before any background",
            "- explain the reasoning in clear, natural prose a clinician can read quickly; go deep on the WHY, not on process logs",
            "- expand only where it genuinely helps the decision; never pad to reach a length target",
            f"- write EVERY heading, sentence, bullet, and table entirely in {language_label}; the only non-{language_label} tokens allowed are drug names, study names, or source titles",
            "- do NOT include reasoning-node matrices, multi-pass retrieval logs, claim-status/confusion matrices, or source-profile tables in the answer body; those belong to the separate telemetry view",
            "- use a comparative table ONLY when it makes a clinical trade-off clearer, with fully translated column headers",
            "- cover contradictory evidence, subgroup caveats, and uncertainty in prose, plainly",
            "- do not prescribe a personal dosage and do not diagnose",
        ]
        return sections, requirements
    if mode == "deep_beta":
        sections = _resolve_deep_beta_dossier_headings(answer_language)
        requirements = [
            "- write as a structured clinical dossier / evidence brief with explicit section-by-section traceability",
            "- open with the answer and decision boundary before background context",
            "- keep claim-evidence mapping explicit, including contradictory or counter evidence and how it changes confidence",
            "- include at least one comparative evidence table and one risk-monitoring table when clinically relevant",
            "- when the query compares options, cover adherence, efficacy, safety, feasibility, and cost/access",
            "- include subgroup caveats, uncertainty, and what new evidence could shift the recommendation",
            "- do not expose internal pipeline tags, execution steps, or debug telemetry in the answer body",
        ]
        # Synthesis v2 (flag-gated): choose the plan by query scope/type and
        # append query-type directives. When the flag is off we return the
        # legacy fixed dossier byte-for-byte so flags-off behavior is identical
        # to baseline (design Property P8 / Requirement 6.2).
        if settings.synthesis_v2_enabled:
            scope_label, _scope_factor = _classify_query_scope(topic)
            requirements = requirements + _resolve_query_type_directives(scope_label, topic)
        return sections, requirements

    sections = [
        quick_conclusion,
        key_points,
        practical_application,
        important_caveats,
    ]
    requirements = [
        "- answer directly in the opening 3-5 sentences before expanding",
        "- keep narrative clinician-friendly, implementation-oriented, and free of template filler",
        "- preserve practical trade-off analysis, uncertainty notes, and follow-up checkpoints",
    ]
    return sections, requirements


#: Anti-repetition directives appended to the synthesis-v2 ``deep_beta`` style
#: profile so the model varies phrasing/structure instead of emitting one
#: template (Requirement 3.2). Pure constants — no PII, no query text.
_ANTI_REPETITION_DIRECTIVES: list[str] = [
    "Vary the opening words of adjacent paragraphs; never begin two consecutive paragraphs with the same word or phrase.",
    "Alternate sentence structure (declarative, comparative, conditional, list-led) so prose does not read as a filled template.",
    "Rotate connective and transition phrasing instead of reusing the same linkers across sections.",
    "Avoid reusing the same stock framing sentence to introduce each section.",
]


def _resolve_style_variation(scope_label: str, topic: str) -> dict[str, Any]:
    """Per-query-type style-variation hints for the synthesis-v2 path.

    Pure and PII-free: derives a stylistic-variation block from the scope label
    (from :func:`_classify_query_scope`) plus accent-folded intent cues, never
    storing or logging the query text. The block nudges the model to vary the
    report's *structure and phrasing by query type* (comparison vs
    single-intervention vs diagnostic-workup vs narrow) so adjacent reports do
    not share an identical skeleton or repeated openings (Requirement 3.2,
    complementing the section-plan variation of Requirement 3.1).
    """

    label = str(scope_label or "standard").strip().lower()
    folded = _ascii_fold(topic)

    diagnostic_markers = (
        "chan doan",
        "trieu chung",
        "dau hieu",
        "tiep can",
        "workup",
        "differential",
        "diagnos",
        "symptom",
    )
    is_diagnostic = any(marker in folded for marker in diagnostic_markers)

    if label == "comparative_multi":
        framing = "options_contrast"
        opening_strategy = (
            "Open each option's analysis from a different angle (efficacy, then safety, then "
            "adherence) rather than repeating one fixed lead-in per option."
        )
    elif label == "broad":
        framing = "thematic_dossier"
        opening_strategy = (
            "Lead successive analytic dimensions (mechanism, evidence, subgroups, monitoring) "
            "with distinct sentence patterns so the dossier does not read as a repeated shell."
        )
    elif label == "narrow":
        framing = "compact_brief"
        opening_strategy = (
            "Keep the brief tight and front-loaded; vary the few openings you use and avoid "
            "padding sections to fill space."
        )
    else:
        framing = "adaptive_clinical"
        opening_strategy = (
            "Shape section emphasis around the specific question and vary paragraph openings "
            "rather than emitting a fixed template."
        )

    if is_diagnostic:
        framing = "differential_workup"
        opening_strategy = (
            "Frame around differential reasoning and red-flags first; vary how each differential "
            "and escalation criterion is introduced."
        )

    return {
        "framing": framing,
        "opening_strategy": opening_strategy,
        "anti_repetition": list(_ANTI_REPETITION_DIRECTIVES),
    }


def _resolve_report_style_profile(
    research_mode: str,
    *,
    topic: str = "",
) -> dict[str, Any]:
    mode = str(research_mode or "fast").strip().lower()
    if mode == "deep_beta":
        profile: dict[str, Any] = {
            "tone": "clinical_dossier_evidence_brief",
            "narrative_density": "very_high",
            "target_reader": "clinician, researcher, or medical operator who needs a traceable long-form synthesis",
            "must_do": [
                "Lead with the answer and decision boundary, then show the evidence chain explicitly.",
                "Keep claim-evidence linkage explicit and include contradiction handling in a dedicated section.",
                "Translate uncertainty into concrete decision boundaries, subgroup caveats, and monitoring steps.",
                "Use structured clinical headings that make evidence provenance and applicability auditable.",
            ],
            "avoid": [
                "Do not expose internal system nodes, debug steps, or planner tags.",
                "Do not repeat identical sentence openings across adjacent paragraphs.",
                "Do not collapse the report into short Perplexity-style summary-only prose.",
            ],
        }
        # Synthesis v2 (flag-gated): add per-query-type style variation and
        # explicit anti-repetition directives so the prose de-templates
        # (Requirement 3.2). When the flag is off we return the legacy profile
        # byte-for-byte so flags-off behavior is identical to baseline
        # (design Property P8 / Requirement 6.2).
        if settings.synthesis_v2_enabled:
            scope_label, _scope_factor = _classify_query_scope(topic)
            profile["style_variation"] = _resolve_style_variation(scope_label, topic)
        return profile
    return {
        "tone": "clinical_briefing_reader_first",
        "narrative_density": "high",
        "target_reader": "clinician or health operator scanning for the answer first",
        "must_do": [
            "Prioritize practical interpretation and what changes in decision-making.",
            "Keep prose natural, concise, and non-robotic while preserving rigor.",
            "Translate evidence into actionable follow-up checkpoints.",
        ],
        "avoid": [
            "Do not over-expose internal pipeline/debug mechanics in main body.",
            "Do not stack legal boilerplate repeatedly in every section.",
            "Do not duplicate the same conclusion in multiple headings.",
        ],
    }


def _safe_generate_with_token_budget(
    client: Any,
    *,
    prompt: str,
    system_prompt: str,
    max_tokens: int,
) -> Any:
    try:
        return client.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
        )
    except TypeError:
        return client.generate(prompt=prompt, system_prompt=system_prompt)


def _ensure_deep_beta_report_artifacts(
    *,
    markdown_text: str,
    deep_pass_summaries: list[dict[str, Any]],
    reasoning_nodes: list[dict[str, Any]] | None = None,
    evidence_verification: dict[str, Any] | None = None,
    verification_summary: dict[str, Any] | None = None,
    research_mode: str = "deep_beta",
) -> str:
    mode = str(research_mode or "deep_beta").strip().lower()
    output = _sanitize_deep_beta_markdown_output(markdown_text)
    # Clean-body Pro (default): keep the answer body pure explanatory prose and
    # never inject reasoning-chain / evidence-summary / multi-pass matrix tables
    # (which also carried English headers, causing the mixed VN/EN output). That
    # technical material stays in the response envelope for the hidden telemetry
    # panel on web + mobile. Return the sanitized prose as-is.
    if mode == "deep_beta" and _deep_beta_clean_body_active():
        return output
    appendix_sections: list[str] = []
    reasoning_cards = _build_reasoning_chain_cards(
        reasoning_nodes if isinstance(reasoning_nodes, list) else [],
        limit=16,
    )

    require_reasoning_chain = mode == "deep_beta"
    if require_reasoning_chain and not _has_markdown_heading(output, "## Chuỗi lập luận bằng chứng"):
        if reasoning_cards:
            rows = [
                "| Node | Claim | Evidence | Inference | Clinical action | Confidence |",
                "| --- | --- | --- | --- | --- | ---: |",
            ]
            for card in reasoning_cards[:10]:
                rows.append(
                    f"| {_escape_markdown_cell(card.get('node') or '-')} | "
                    f"{_escape_markdown_cell(card.get('claim') or '-')} | "
                    f"{_escape_markdown_cell(card.get('evidence') or '-')} | "
                    f"{_escape_markdown_cell(card.get('inference') or '-')} | "
                    f"{_escape_markdown_cell(card.get('clinical_action') or '-')} | "
                    f"{_normalize_router_confidence(card.get('confidence')):.2f} |"
                )
            appendix_sections.append("## Chuỗi lập luận bằng chứng\n" + "\n".join(rows))
        else:
            appendix_sections.append(
                "## Chuỗi lập luận bằng chứng\n"
                "- Bằng chứng hiện tại chưa đủ để dựng chain chi tiết cho mọi claim.\n"
                "- Ưu tiên bổ sung truy xuất mục tiêu vào các điểm còn thiếu hỗ trợ trước khi ra quyết định.\n"
            )

    if not _has_markdown_heading(output, "## Bảng tổng hợp bằng chứng"):
        verification = evidence_verification if isinstance(evidence_verification, dict) else {}
        summary = verification_summary if isinstance(verification_summary, dict) else {}
        supported_count = len(verification.get("supported_claims", [])) if isinstance(
            verification.get("supported_claims"), list
        ) else _safe_int(summary.get("supported_claims"), 0)
        unsupported_count = len(verification.get("unsupported_claims", [])) if isinstance(
            verification.get("unsupported_claims"), list
        ) else _safe_int(summary.get("unsupported_claims"), 0)
        contradicted_count = len(verification.get("contradicted_claims", [])) if isinstance(
            verification.get("contradicted_claims"), list
        ) else _safe_int(summary.get("contradicted_claims"), 0)
        support_ratio = _safe_float(summary.get("support_ratio"), 0.0)
        appendix_sections.append(
            "## Bảng tổng hợp bằng chứng\n"
            "| Chỉ số | Giá trị |\n"
            "| --- | ---: |\n"
            f"| Supported claims | {supported_count} |\n"
            f"| Unsupported claims | {unsupported_count} |\n"
            f"| Contradicted claims | {contradicted_count} |\n"
            f"| Support ratio | {round(max(0.0, min(support_ratio, 1.0)), 3)} |\n"
        )

    if "| --- |" not in output:
        rows = [
            "| Pass | Subquery | Retrieved | Duration (ms) |",
            "| --- | --- | ---: | ---: |",
        ]
        for item in deep_pass_summaries[:10]:
            if not isinstance(item, dict):
                continue
            rows.append(
                f"| {_safe_int(item.get('pass_index'), 0)} | "
                f"{_escape_markdown_cell(item.get('subquery') or '-')} | "
                f"{_safe_int(item.get('retrieved_count'), 0)} | "
                f"{round(_safe_float(item.get('duration_ms'), 0.0), 2)} |"
            )
        if mode == "deep_beta":
            appendix_sections.append("### Bảng bổ sung Deep Beta\n" + "\n".join(rows))
        else:
            appendix_sections.append("### Bảng triển khai truy xuất\n" + "\n".join(rows[:8]))

    if appendix_sections:
        output = f"{output.rstrip()}\n\n" + "\n\n".join(appendix_sections).rstrip() + "\n"
    return output


#: Legacy expansion focus line used by the flags-off / non-``deep_beta``
#: convergence loop. Kept verbatim so the flags-off continuation prompt is
#: byte-for-byte identical to the pre-feature behavior (design Property P8 /
#: Requirement 6.2).
_LEGACY_EXPANSION_FOCUS = (
    "Add deeper analysis with practical clinical caveats, subgroup handling, "
    "uncertainty, and scientific interpretation."
)

#: Ordered expansion directives for the synthesis-v2 ``deep_beta`` convergence
#: loop (Requirement 2.2 / Property P6). When an expansion round returns empty
#: or duplicate content, the loop rotates to the next directive — each targeting
#: a different analytic dimension — before giving up, rather than breaking on the
#: first empty/duplicate round. The loop stops only when the target length is
#: met, the round budget is exhausted, a full rotation produces nothing new, or
#: the wall-clock timeout is hit. Pure constants: no PII, no query text.
_EXPANSION_DIRECTIVES: tuple[str, ...] = (
    "Add deeper subgroup and special-population analysis (age, comorbidity, "
    "renal/hepatic function, pregnancy, polypharmacy) with practical clinical "
    "caveats, uncertainty, and scientific interpretation.",
    "Add a comparative analysis contrasting the main options across efficacy, "
    "safety, adherence, feasibility, and cost/access, using a Markdown comparison "
    "table where it clarifies the trade-offs.",
    "Add a monitoring and safety matrix covering baseline checks, follow-up "
    "cadence, adverse-effect surveillance, and red-flag escalation thresholds, "
    "using a Markdown table where useful.",
    "Add an uncertainty and evidence-gap section that states what evidence is "
    "missing or contradictory, how it changes confidence, and which questions "
    "remain open for clinician judgement.",
)


def _synthesize_deep_beta_long_report(
    *,
    topic: str,
    answer_markdown: str,
    citations: list[Citation],
    verification_matrix_payload: dict[str, Any],
    reasoning_nodes: list[dict[str, Any]],
    deep_pass_summaries: list[dict[str, Any]],
    evidence_verification: dict[str, Any] | None = None,
    llm_runtime: dict[str, Any] | None = None,
    research_mode: str = "deep_beta",
    answer_language: str = "vi",
) -> str:
    if not settings.deep_beta_report_llm_enabled:
        return answer_markdown
    _, api_key, _base_url, _model = _resolve_runtime_llm_config(llm_runtime)
    if not api_key:
        return answer_markdown

    mode = str(research_mode or "deep_beta").strip().lower()
    handoff_profile = _resolve_evidence_handoff_profile(mode)
    compact_citations = [
        {
            "source_id": item.source_id,
            "source": item.source,
            "title": item.title,
            "url": item.url,
            "relevance": item.relevance,
        }
        for item in citations[: handoff_profile["report_citations"]]
    ]
    verification_summary = (
        verification_matrix_payload.get("summary")
        if isinstance(verification_matrix_payload.get("summary"), dict)
        else {}
    )
    contradiction_summary = (
        verification_matrix_payload.get("contradiction_summary")
        if isinstance(verification_matrix_payload.get("contradiction_summary"), dict)
        else {}
    )
    compact_passes = [
        {
            "pass_index": item.get("pass_index"),
            "subquery": item.get("subquery"),
            "retrieved_count": item.get("retrieved_count"),
            "duration_ms": item.get("duration_ms"),
        }
        for item in deep_pass_summaries[: handoff_profile["report_pass_summaries"]]
        if isinstance(item, dict)
    ]
    reasoning_chain_cards = _build_reasoning_chain_cards(
        reasoning_nodes,
        limit=handoff_profile["report_reasoning_chain_cards"],
    )

    min_words, target_words, max_words = _resolve_adaptive_report_word_budget(
        research_mode=mode,
        citation_count=len(compact_citations),
        deep_pass_count=len(compact_passes),
        reasoning_node_count=len(reasoning_chain_cards),
        topic=topic,
    )
    section_contract, section_requirements = _resolve_report_section_contract(
        mode,
        answer_language=answer_language,
        topic=topic,
    )
    style_profile = _resolve_report_style_profile(mode, topic=topic)
    section_contract_text = "\n".join(section_contract)
    section_requirements_text = "\n".join(section_requirements)
    report_timeout_seconds = max(
        float(settings.deep_beta_report_timeout_seconds),
        float(settings.deep_beta_reasoning_llm_timeout_seconds),
        30.0,
    )
    report_max_tokens = (
        max(int(settings.deep_beta_report_max_tokens), 4096)
        if mode == "deep_beta"
        else max(min(int(settings.deep_beta_report_max_tokens), 8192), 2048)
    )
    language_label = "English" if answer_language == "en" else "Vietnamese"
    # Clean-body Pro (default): deep_beta uses the SAME natural, reader-first
    # style directives as deep mode instead of the dossier/evidence-brief
    # directives. This is what turns off the rigid "cố làm dài" dossier voice
    # and keeps the answer explanatory rather than telemetry-like. The technical
    # matrices/sources move to the hidden telemetry panel (response envelope).
    use_dossier_style = mode == "deep_beta" and not _deep_beta_clean_body_active()
    style_target_line = (
        "- write as a structured clinical dossier / evidence brief: evidence-dense, contradiction-aware, and clinically actionable"
        if use_dossier_style
        else "- write like a high-signal Perplexity-style medical research answer: direct, analytic, reader-first, and not dossier-like"
    )
    chain_requirement_line = (
        "- keep claim-to-evidence linkage explicit with contradiction audit and confidence boundaries; avoid internal debug chain labels"
        if use_dossier_style
        else "- keep claim-to-evidence linkage explicit in short paragraphs or short bullets without rigid chain templates"
    )
    opening_requirement_line = (
        "- answer with an executive conclusion and explicit decision boundary before background context"
        if use_dossier_style
        else "- answer the user directly in the opening before background context"
    )
    opening_length_line = (
        "- keep the opening to 3-6 strong sentences, then expand by dossier section where it changes decisions"
        if use_dossier_style
        else "- keep the opening to 2-4 strong sentences, then expand only where it helps the decision"
    )
    transition_requirement_line = (
        "- use structured dossier transitions and evidence labels; avoid vague narrative jumps"
        if use_dossier_style
        else "- use natural transitions between sections; avoid checklist-like prose or compliance boilerplate"
    )
    skimmable_requirement_line = (
        "- keep each section scannable with concise paragraphs/tables; bullets should usually stay within 3-6 items"
        if use_dossier_style
        else "- keep each section skimmable: paragraphs should stay short and bullets should usually stay within 3-5 items"
    )
    evidence_label_requirement_line = (
        "- include evidence-brief labels such as research question, retrieval criteria, evidence profile, contradiction audit, and safety matrix when supported by evidence"
        if use_dossier_style
        else "- avoid meta labels such as core question, evidence coverage, working synthesis, or retrieval process unless they change the clinical interpretation"
    )
    # Synthesis v2 (flag-gated, deep_beta only): an explicit anti-repetition
    # directive so adjacent paragraphs do not share identical sentence openings
    # and the report does not read as a filled template (Requirement 3.2). Empty
    # on the flags-off / non-deep_beta path so the legacy prompt is byte-for-byte
    # preserved (design Property P8 / Requirement 6.2).
    anti_repetition_requirement_line = (
        "- vary the opening words of adjacent paragraphs and rotate transition phrasing; "
        "never begin two consecutive paragraphs with the same word or phrase\n"
        if mode == "deep_beta" and settings.synthesis_v2_enabled
        else ""
    )
    prompt = (
        f"Rewrite the baseline answer into a polished long-form medical research answer in {language_label}.\n"
        "Output valid GitHub-Flavored Markdown only, no HTML.\n"
        "Must include these sections in this exact order:\n"
        f"{section_contract_text}\n"
        "Requirements:\n"
        f"- total length must be between {min_words} and {max_words} words; target around {target_words} words\n"
        f"{style_target_line}\n"
        f"- keep every heading, label, bullet, and sentence in {language_label}; do not mix Vietnamese and English except for drug names, study names, or source titles\n"
        f"{opening_requirement_line}\n"
        f"{opening_length_line}\n"
        "- avoid robotic wording and avoid repeating the same sentence pattern across sections\n"
        f"{anti_repetition_requirement_line}"
        f"{transition_requirement_line}\n"
        f"{skimmable_requirement_line}\n"
        f"{evidence_label_requirement_line}\n"
        "- each major section must contain concrete analysis and actionable interpretation\n"
        f"{chain_requirement_line}\n"
        f"{section_requirements_text}\n"
        "- do not add a dedicated references/citations section in the answer body\n"
        "- keep citations concise and only when needed to support critical claims\n"
        "- do not prescribe dosage, do not diagnose\n\n"
        f"style_profile={json.dumps(style_profile, ensure_ascii=False)}\n"
        f"topic={topic}\n"
        f"baseline_answer={answer_markdown}\n"
        f"citations={json.dumps(compact_citations, ensure_ascii=False)}\n"
        f"verification_summary={json.dumps(verification_summary, ensure_ascii=False)}\n"
        f"contradiction_summary={json.dumps(contradiction_summary, ensure_ascii=False)}\n"
        f"evidence_verification={json.dumps(evidence_verification or {}, ensure_ascii=False)}\n"
        f"reasoning_nodes={json.dumps(reasoning_nodes, ensure_ascii=False)}\n"
        f"reasoning_chain_cards={json.dumps(reasoning_chain_cards, ensure_ascii=False)}\n"
        f"deep_pass_summaries={json.dumps(compact_passes, ensure_ascii=False)}\n"
    )
    system_prompt = (
        "You are CLARA medical research synthesizer. "
        f"Write natural, evidence-grounded, safety-first {language_label} with a direct answer first. "
        "Prioritize coherent clinical reasoning over template-heavy filler or dossier language. "
        "The answer should read like a strong Perplexity synthesis for clinicians: fast to scan, but still rigorous."
    )
    if use_dossier_style:
        system_prompt = (
            "You are CLARA deep beta clinical dossier synthesizer. "
            f"Produce a structured {language_label} evidence brief in valid GFM markdown only. "
            "Keep section-level traceability from claim to evidence, include contradiction audit, and state decision boundaries explicitly. "
            "Use dossier-style clinical headings when they improve auditability. "
            "Do not prescribe dosage or diagnose."
        )
    try:
        client = _build_reasoning_client(
            timeout_seconds=report_timeout_seconds,
            llm_runtime=llm_runtime,
        )
        if client is None:
            return answer_markdown
        # Wall-clock start for the synthesis-v2 convergence/enrichment bound
        # (Requirement 2.4): total synthesis time is capped at
        # ``report_timeout_seconds`` and the best-so-far report is kept on
        # timeout rather than discarded.
        synthesis_start = perf_counter()
        response = client.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=report_max_tokens,
        )
        content = _sanitize_deep_beta_markdown_output(str(response.content or "").strip())
        if not content:
            return answer_markdown

        def _build_continuation_prompt(focus_line: str, missing_words: int) -> str:
            """Build an append-only continuation prompt for a given directive.

            Used by both the legacy loop (with ``_LEGACY_EXPANSION_FOCUS``) and the
            synthesis-v2 loop (rotating ``_EXPANSION_DIRECTIVES``). With the legacy
            focus line the produced string is byte-for-byte identical to the
            pre-feature continuation prompt, preserving flags-off equivalence
            (design Property P8). ``content`` is read at call time so each round
            embeds the latest accumulated report.
            """

            return (
                f"Expand the following {language_label} medical report by APPENDING new content only.\n"
                "Do NOT rewrite previous sections.\n"
                "Do NOT duplicate any existing H2 section title.\n"
                "Do NOT add internal pipeline labels like [scope_question], deep_beta_scope, retrieval_budgeting, or execution logs.\n"
                f"{focus_line}\n"
                f"Need at least ~{missing_words} additional words.\n"
                "Append supplementary sections using H3/H4 headings and additional tables where useful.\n"
                "Return Markdown only.\n\n"
                f"topic={topic}\n"
                f"existing_report={content}\n"
                f"reasoning_nodes={json.dumps(reasoning_nodes, ensure_ascii=False)}\n"
                f"reasoning_chain_cards={json.dumps(reasoning_chain_cards, ensure_ascii=False)}\n"
                f"deep_pass_summaries={json.dumps(compact_passes, ensure_ascii=False)}\n"
                f"evidence_verification={json.dumps(evidence_verification or {}, ensure_ascii=False)}\n"
                f"verification_summary={json.dumps(verification_summary, ensure_ascii=False)}\n"
            )

        configured_rounds = max(1, int(settings.deep_beta_report_expansion_rounds))
        expansion_rounds = (
            configured_rounds
            if mode == "deep_beta"
            else max(min(configured_rounds, 2), 1)
        )
        if mode == "deep_beta":
            if target_words >= 12000:
                expansion_rounds = max(expansion_rounds, 3)
            elif target_words >= 8000:
                expansion_rounds = max(expansion_rounds, 2)
        if mode == "deep_beta" and settings.synthesis_v2_enabled:
            # Synthesis-v2 robust convergence loop (Requirement 2.1, 2.2, 2.4 /
            # Property P6). Differences from the legacy loop below:
            #   * On an empty/duplicate continuation, rotate to the NEXT expansion
            #     directive (a different analytic dimension) instead of breaking
            #     immediately; only stop once a full rotation through every
            #     directive yields nothing new.
            #   * A wall-clock check bounds total synthesis time against
            #     ``report_timeout_seconds`` and keeps the best-so-far (append-only)
            #     report rather than discarding accumulated work on timeout.
            # ``_markdown_word_count`` is the single counter used for budgeting,
            # expansion, and enforcement (Property P7).
            directive_index = 0
            consecutive_empty = 0
            for _round_idx in range(expansion_rounds):
                if perf_counter() - synthesis_start >= report_timeout_seconds:
                    break
                current_words = _markdown_word_count(content)
                if current_words >= target_words:
                    break

                missing_words = max(target_words - current_words, 0)
                focus_line = _EXPANSION_DIRECTIVES[
                    directive_index % len(_EXPANSION_DIRECTIVES)
                ]
                directive_index += 1
                continuation_prompt = _build_continuation_prompt(focus_line, missing_words)
                continuation_response = client.generate(
                    prompt=continuation_prompt,
                    system_prompt=system_prompt,
                    max_tokens=report_max_tokens,
                )
                continuation = _sanitize_deep_beta_markdown_output(
                    str(continuation_response.content or "").strip()
                )
                if not continuation or continuation in content:
                    # Empty/duplicate pass: try a different directive before
                    # giving up (Requirement 2.2). Stop only after a full
                    # rotation through every directive produced no new content.
                    consecutive_empty += 1
                    if consecutive_empty >= len(_EXPANSION_DIRECTIVES):
                        break
                    continue
                consecutive_empty = 0
                content = f"{content.rstrip()}\n\n{continuation.strip()}"
        else:
            for _round_idx in range(expansion_rounds):
                current_words = _markdown_word_count(content)
                if current_words >= target_words:
                    break

                missing_words = max(target_words - current_words, 0)
                continuation_prompt = _build_continuation_prompt(
                    _LEGACY_EXPANSION_FOCUS, missing_words
                )
                continuation_response = client.generate(
                    prompt=continuation_prompt,
                    system_prompt=system_prompt,
                    max_tokens=report_max_tokens,
                )
                continuation = _sanitize_deep_beta_markdown_output(
                    str(continuation_response.content or "").strip()
                )
                if not continuation or continuation in content:
                    break
                content = f"{content.rstrip()}\n\n{continuation.strip()}"

        # R18.1/R18.3: enforce the deep_beta section + minimum-word contract *by
        # generation* before any programmatic fallback/padding runs below. When the
        # draft is missing required dossier headings or is still short of the resolved
        # minimum word count, run an additional bounded generation pass that asks the
        # model to append the deficient sections (by their exact H2 titles) and enough
        # substantive content to reach the minimum. The existing markdown naturalness
        # sanitizers (R18.4) are preserved by routing every pass through
        # ``_sanitize_deep_beta_markdown_output``. Gated behind ``synthesis_v2_enabled``
        # so the flags-off path stays byte-for-byte the pre-feature legacy behavior
        # (design Property P8 / Requirement 20.2 flags-off equivalence).
        if (
            mode == "deep_beta"
            and settings.synthesis_v2_enabled
            and not _deep_beta_clean_body_active()
        ):
            for _ in range(2):
                if perf_counter() - synthesis_start >= report_timeout_seconds:
                    # Wall-clock bound: keep the best-so-far report rather than
                    # spending more time on enrichment (Requirement 2.4).
                    break
                missing_headings = _deep_beta_missing_required_headings(content, answer_language)
                word_deficit = max(min_words - _markdown_word_count(content), 0)
                if not missing_headings and word_deficit <= 0:
                    break
                missing_section_lines = "\n".join(missing_headings)
                section_fill_prompt = (
                    f"Complete the following {language_label} medical research report so it "
                    "satisfies its section and length contract.\n"
                    "Output valid GitHub-Flavored Markdown only, no HTML.\n"
                    "APPEND new content only; do NOT rewrite or duplicate existing sections.\n"
                    "Add each of these required H2 sections, using the exact heading text, "
                    "with concrete, evidence-grounded, clinically actionable analysis:\n"
                    f"{missing_section_lines or '(all required sections already present)'}\n"
                    f"After adding the required sections, ensure the full report reaches at least "
                    f"{min_words} words by deepening analysis (about {word_deficit} more words still needed).\n"
                    f"- keep every heading, label, bullet, and sentence in {language_label}\n"
                    "- do not expose internal pipeline tags, execution logs, or debug telemetry\n"
                    "- do not prescribe dosage, do not diagnose\n\n"
                    f"topic={topic}\n"
                    f"existing_report={content}\n"
                    f"citations={json.dumps(compact_citations, ensure_ascii=False)}\n"
                    f"evidence_verification={json.dumps(evidence_verification or {}, ensure_ascii=False)}\n"
                    f"verification_summary={json.dumps(verification_summary, ensure_ascii=False)}\n"
                    f"reasoning_chain_cards={json.dumps(reasoning_chain_cards, ensure_ascii=False)}\n"
                )
                section_fill_response = client.generate(
                    prompt=section_fill_prompt,
                    system_prompt=system_prompt,
                    max_tokens=report_max_tokens,
                )
                section_fill = _sanitize_deep_beta_markdown_output(
                    str(section_fill_response.content or "").strip()
                )
                if not section_fill or section_fill in content:
                    break
                content = f"{content.rstrip()}\n\n{section_fill.strip()}"

        # Clean-body Pro (default): never pad the answer body with telemetry
        # (multi-pass logs, reasoning-node/claim matrices, source-profile tables).
        # That material stays in the response envelope for the hidden telemetry
        # panel, so the prose body remains a natural, single-language explanation.
        if (
            not _deep_beta_clean_body_active()
            and _markdown_word_count(content) < target_words
        ):
            pass_rows = [
                "| Pass | Subquery | Retrieved | Duration (ms) |",
                "| --- | --- | ---: | ---: |",
            ]
            for item in compact_passes[:16]:
                pass_rows.append(
                    f"| {item.get('pass_index') or '-'} | "
                    f"{_escape_markdown_cell(item.get('subquery') or '-')} | "
                    f"{_safe_int(item.get('retrieved_count'), 0)} | "
                    f"{round(_safe_float(item.get('duration_ms'), 0.0), 2)} |"
                )

            node_rows = [
                "| Reasoning Node | Status | Confidence | Key Insight | Actions |",
                "| --- | --- | ---: | --- | --- |",
            ]
            for node in reasoning_nodes[:16]:
                insights = node.get("insights")
                actions = node.get("actions")
                top_insight = (
                    _compact_snippet(insights[0], max_len=150)
                    if isinstance(insights, list) and insights
                    else "-"
                )
                top_action = (
                    _compact_snippet(actions[0], max_len=120)
                    if isinstance(actions, list) and actions
                    else "-"
                )
                node_rows.append(
                    f"| {_escape_markdown_cell(node.get('node') or '-')} | "
                    f"{_escape_markdown_cell(node.get('status') or '-')} | "
                    f"{_normalize_router_confidence(node.get('confidence')):.2f} | "
                    f"{_escape_markdown_cell(top_insight)} | "
                    f"{_escape_markdown_cell(top_action)} |"
                )

            chain_rows = [
                "| Node | Claim | Evidence | Inference | Clinical action | Confidence |",
                "| --- | --- | --- | --- | --- | ---: |",
            ]
            for item in reasoning_chain_cards[:16]:
                chain_rows.append(
                    f"| {_escape_markdown_cell(item.get('node') or '-')} | "
                    f"{_escape_markdown_cell(item.get('claim') or '-')} | "
                    f"{_escape_markdown_cell(item.get('evidence') or '-')} | "
                    f"{_escape_markdown_cell(item.get('inference') or '-')} | "
                    f"{_escape_markdown_cell(item.get('clinical_action') or '-')} | "
                    f"{_normalize_router_confidence(item.get('confidence')):.2f} |"
                )

            citation_rows = [
                "| Source ID | Nguồn | Relevance | Ghi chú áp dụng |",
                "| --- | --- | ---: | --- |",
            ]
            for citation in compact_citations[:24]:
                source_id = _escape_markdown_cell(citation.get("source_id") or "-")
                source_label = _escape_markdown_cell(citation.get("source") or "-")
                relevance = _safe_float(citation.get("relevance"), 0.0)
                title_text = _compact_snippet(citation.get("title") or "-", max_len=180)
                citation_rows.append(
                    f"| {source_id} | {source_label} | {relevance:.2f} | "
                    f"{_escape_markdown_cell(title_text)} |"
                )

            supported_claims = []
            contradicted_claims = []
            unsupported_claims = []
            if isinstance(evidence_verification, dict):
                if isinstance(evidence_verification.get("supported_claims"), list):
                    supported_claims = evidence_verification.get("supported_claims") or []
                if isinstance(evidence_verification.get("contradicted_claims"), list):
                    contradicted_claims = evidence_verification.get("contradicted_claims") or []
                if isinstance(evidence_verification.get("unsupported_claims"), list):
                    unsupported_claims = evidence_verification.get("unsupported_claims") or []

            claim_rows = [
                "| Nhóm claim | Số lượng | Gợi ý hành động |",
                "| --- | ---: | --- |",
                f"| Supported | {len(supported_claims)} | Có thể dùng cho tư vấn tham khảo có điều kiện |",
                f"| Contradicted | {len(contradicted_claims)} | Cần cảnh báo đỏ, đối chiếu bác sĩ ngay |",
                f"| Unsupported | {len(unsupported_claims)} | Không chuyển thành khuyến nghị lâm sàng |",
            ]

            uncertainty_blocks = [
                "- Khi bằng chứng mâu thuẫn giữa các nguồn, ưu tiên guideline/consensus cập nhật hơn nghiên cứu đơn lẻ.",
                "- Mọi kết luận chỉ mang tính hỗ trợ quyết định, không thay thế chỉ định khám, kê đơn hay chẩn đoán.",
                "- Với bệnh nền phức tạp (tim mạch, suy thận, thai kỳ, đa trị liệu), cần hội chẩn bác sĩ trước mọi thay đổi thuốc.",
                "- Nếu xuất hiện dấu hiệu nặng (xuất huyết, khó thở, đau ngực, lú lẫn), ưu tiên cấp cứu thay vì tự điều chỉnh điều trị.",
            ]

            appendix_title = (
                "## Phụ lục mở rộng Deep Beta (chuyên sâu)" if mode == "deep_beta" else "## Phụ lục mở rộng Deep"
            )
            appendix_blocks = [f"\n\n{appendix_title}\n"]
            if mode == "deep_beta":
                appendix_blocks.extend(
                    [
                        "### Nhật ký multi-pass retrieval\n",
                        "\n".join(pass_rows),
                        "\n\n### Ma trận reasoning nodes\n",
                        "\n".join(node_rows),
                        "\n\n### Chuỗi lập luận claim-level\n",
                        "\n".join(chain_rows),
                        "\n\n### Hồ sơ nguồn mở rộng\n",
                        "\n".join(citation_rows),
                    ]
                )
                appendix_blocks.extend(
                    [
                        "\n\n### Ma trận trạng thái claim-level\n",
                        "\n".join(claim_rows),
                    ]
                )
            else:
                # Deep mode appendix should stay implementation-facing, not telemetry-heavy.
                implementation_rows = [
                    "| Nhóm bệnh nhân | Điểm cần chú ý | Hành động theo dõi |",
                    "| --- | --- | --- |",
                    "| Tăng huyết áp đơn thuần | Ưu tiên mục tiêu huyết áp và khả năng tuân thủ | Đo HA tại nhà 1-2 tuần, hiệu chỉnh chế độ ăn theo đáp ứng |",
                    "| Đái tháo đường / rối loạn lipid | Cân bằng kiểm soát đường huyết và nguy cơ tim mạch dài hạn | Theo dõi HbA1c/lipid định kỳ, đánh giá tuân thủ thực đơn thực tế |",
                    "| Người cao tuổi / đa bệnh nền | Nguy cơ thiếu dinh dưỡng, tương tác đa trị liệu, giảm tuân thủ | Theo dõi cân nặng, chức năng thận, cảnh báo dấu hiệu suy giảm chức năng |",
                ]
                appendix_blocks.extend(
                    [
                        "### Bảng triển khai theo phân tầng lâm sàng\n",
                        "\n".join(implementation_rows),
                        "\n\n### Checklist theo dõi 2-4 tuần đầu\n"
                        "- Xác định mục tiêu ưu tiên (HA, lipid, cân nặng, đường huyết).\n"
                        "- Ghi nhật ký khẩu phần và mức độ tuân thủ thực tế.\n"
                        "- Đánh giá sớm tác động bất lợi hoặc dấu hiệu báo động.\n"
                        "- Điều chỉnh can thiệp dựa trên dữ liệu theo dõi, không theo cảm tính.\n",
                    ]
                )
            appendix_blocks.extend(
                [
                    "\n\n### Uncertainty & Safety Escalation Notes\n",
                    "\n".join(uncertainty_blocks),
                ]
            )
            appendix_blocks.extend(
                [
                    "\n\n### Ghi chú phương pháp\n",
                    "- Báo cáo này được mở rộng tự động để tăng độ bao phủ bằng chứng và chiều sâu diễn giải lâm sàng.\n"
                    "- Các nội dung chưa đủ bằng chứng được giữ trạng thái cảnh báo và không chuyển thành khuyến nghị điều trị.\n"
                    "- Trường hợp cần quyết định điều trị, đầu ra này phải được xác nhận bởi chuyên gia y tế có thẩm quyền.\n",
                ]
            )
            fallback_appendix = "".join(appendix_blocks)
            content = f"{content.rstrip()}{fallback_appendix}"

        return _ensure_deep_beta_report_artifacts(
            markdown_text=content,
            deep_pass_summaries=deep_pass_summaries,
            reasoning_nodes=reasoning_nodes,
            evidence_verification=evidence_verification,
            verification_summary=verification_summary,
            research_mode=mode,
        )
    except Exception:
        return _ensure_deep_beta_report_artifacts(
            markdown_text=answer_markdown,
            deep_pass_summaries=deep_pass_summaries,
            reasoning_nodes=reasoning_nodes,
            evidence_verification=evidence_verification,
            verification_summary=verification_summary,
            research_mode=mode,
        )


def _refine_query_plan_with_llm(
    *,
    topic: str,
    research_mode: str,
    route_role: str,
    route_intent: str,
    base_query_plan: dict[str, Any],
    keywords: list[str],
    llm_runtime: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    _, api_key, _base_url, _model = _resolve_runtime_llm_config(llm_runtime)
    if not api_key:
        return base_query_plan, {
            "attempted": False,
            "status": "degraded",
            "reason": "api_key_missing",
            "model_used": "unconfigured",
        }

    system_prompt = (
        "You are a clinical evidence query planner. Return STRICT JSON only. "
        "No markdown, no explanations, no extra keys."
    )
    prompt = (
        "Refine this retrieval query plan for high-recall clinical research.\n"
        "Output EXACT JSON schema:\n"
        "{\n"
        '  "canonical_query": "string",\n'
        '  "language_hint": "vi|en|mixed",\n'
        '  "keywords": ["..."],\n'
        '  "source_queries": {\n'
        '    "internal": ["..."],\n'
        '    "scientific": ["..."],\n'
        '    "web": ["..."]\n'
        "  },\n"
        '  "provider_queries": {\n'
        '    "scientific": {"pubmed": "...", "europepmc": "...", "openfda": "..."},\n'
        '    "web": {"searxng": "..."}\n'
        "  },\n"
        '  "decomposition": {\n'
        '    "deep_pass_queries": ["..."],\n'
        '    "deep_beta_pass_queries": ["..."]\n'
        "  }\n"
        "}\n"
        "Constraints:\n"
        "- keywords length <= 12\n"
        "- keep clinical safety terms when query is medication-related\n"
        "- return at least one query per source and decomposition list\n"
        "- provider_queries is optional; if provided, map each provider to concise query\n"
        "- return valid JSON only\n\n"
        f"topic={topic}\n"
        f"research_mode={research_mode}\n"
        f"route_role={route_role}\n"
        f"route_intent={route_intent}\n"
        f"base_keywords={keywords[:12]}\n"
        f"base_plan={json.dumps(base_query_plan, ensure_ascii=False)}\n"
    )
    compact_recovery_prompt = (
        "Return STRICT JSON only for retrieval planning.\n"
        "Required keys: canonical_query, language_hint, keywords, source_queries, decomposition.\n"
        "Do not add explanations.\n"
        "Ensure source_queries contains internal/scientific/web with at least one query each.\n"
        "Ensure decomposition contains deep_pass_queries/deep_beta_pass_queries with at least one query each.\n"
        f"topic={topic}\n"
        f"research_mode={research_mode}\n"
        f"route_role={route_role}\n"
        f"route_intent={route_intent}\n"
        f"keywords_hint={keywords[:8]}\n"
        f"canonical_hint={base_query_plan.get('canonical_query')}\n"
    )

    try:
        try:
            client = _build_query_planner_client(llm_runtime=llm_runtime)
        except TypeError:
            # Backward-compatible path for monkeypatched helpers that still expose no kwargs.
            client = _build_query_planner_client()
        if client is None:
            raise RuntimeError("runtime_llm_unconfigured")
        first_error: Exception | None = None
        for attempt_index, planner_prompt in enumerate((prompt, compact_recovery_prompt), start=1):
            try:
                llm_response = client.generate(prompt=planner_prompt, system_prompt=system_prompt)
                parsed_payload = _parse_planner_json_payload(llm_response.content)
                sanitized = _sanitize_llm_query_plan_payload(
                    parsed_payload,
                    base_query_plan=base_query_plan,
                    research_mode=research_mode,
                )
                return sanitized, {
                    "attempted": True,
                    "status": "completed",
                    "reason": "ok" if attempt_index == 1 else "ok_recovered_compact_prompt",
                    "model_used": llm_response.model,
                }
            except Exception as exc:  # pragma: no cover - defensive planner retry
                if first_error is None:
                    first_error = exc
                continue
        if first_error is None:
            raise RuntimeError("planner_unknown_failure")
        raise first_error
    except Exception as exc:  # pragma: no cover - network/provider defensive path
        return base_query_plan, {
            "attempted": True,
            "status": "recovered",
            "reason": f"heuristic_recovery:{_safe_planner_error_code(exc)}",
            "error": f"{exc.__class__.__name__}: {exc}",
            "model_used": "planner-heuristic-v1",
        }


def _build_plan_steps(
    topic: str,
    source_mode: str | None,
    *,
    research_mode: str,
) -> list[PlanStep]:
    source_line = " from uploaded files" if source_mode == "uploaded_files" else ""
    base_steps = [
        PlanStep(
            step="scope_question",
            objective=f"Narrow the exact Tier-2 research question for '{topic}'.",
            output="Framed question and inclusion boundaries.",
        ),
        PlanStep(
            step="collect_evidence",
            objective=f"Prioritize high-signal clinical summaries and guidelines{source_line}.",
            output="Evidence shortlist with source quality notes.",
        ),
        PlanStep(
            step="synthesize_findings",
            objective="Merge findings into agreement/disagreement points.",
            output="Structured synthesis with confidence caveats.",
        ),
        PlanStep(
            step="clinical_translation",
            objective="Translate evidence into practical decision guidance.",
            output="Actionable recommendations with safety notes.",
        ),
    ]
    if research_mode == "deep_beta":
        return [
            base_steps[0],
            PlanStep(
                step="decompose_research",
                objective=(
                    "Break the research topic into sub-queries, hypothesis/counter-hypothesis "
                    "pairs and evidence conflict checkpoints."
                ),
                output="Prioritized sub-query graph and expected directional signals.",
            ),
            PlanStep(
                step="retrieval_budgeting",
                objective=(
                    "Allocate explicit retrieval budget by source type, pass index and "
                    "quality threshold."
                ),
                output="Pass-level retrieval budgets and source coverage targets.",
            ),
            PlanStep(
                step="breadth_scan",
                objective=(
                    "Run a broad evidence sweep across guidelines, trials, reviews, "
                    "drug labels and safety bulletins."
                ),
                output="Breadth-first evidence pool with source quality metadata.",
            ),
            base_steps[1],
            PlanStep(
                step="iterative_gap_fill",
                objective=(
                    "Run iterative passes to fill unresolved evidence gaps and "
                    "edge-case caveats."
                ),
                output="Gap-closure notes and augmented pass summaries.",
            ),
            PlanStep(
                step="counter_evidence_scan",
                objective=(
                    "Search explicitly for contradictory findings, subgroup caveats "
                    "and negative outcomes."
                ),
                output="Contradiction candidates and uncertainty notes.",
            ),
            PlanStep(
                step="cross_source_verification",
                objective=(
                    "Cross-check consistency across internal docs, scientific connectors, "
                    "web and source trust hierarchy."
                ),
                output="Agreement/disagreement matrix by source and pass.",
            ),
            PlanStep(
                step="reasoning_chain_audit",
                objective=(
                    "Audit the reasoning chain for unsupported links before synthesis."
                ),
                output="Reasoning-chain status with mitigation notes.",
            ),
            base_steps[2],
            base_steps[3],
        ]

    if research_mode != "deep":
        return base_steps

    return [
        base_steps[0],
        PlanStep(
            step="decompose_research",
            objective=(
                "Break the research topic into sub-queries, evidence hypotheses, "
                "and counter-hypotheses."
            ),
            output="Prioritized sub-query list with expected evidence direction.",
        ),
        PlanStep(
            step="breadth_scan",
            objective=(
                "Run broad retrieval across guideline, trial, review and safety sources "
                "to maximize evidence recall."
            ),
            output="Breadth-first evidence pool with source quality metadata.",
        ),
        base_steps[1],
        PlanStep(
            step="counter_evidence_scan",
            objective=(
                "Search explicitly for contradictory findings, subgroup caveats "
                "and negative outcomes."
            ),
            output="Contradiction candidates and uncertainty notes.",
        ),
        PlanStep(
            step="cross_source_verification",
            objective=(
                "Cross-check consistency across internal docs, " "scientific connectors and web."
            ),
            output="Agreement/disagreement matrix by source.",
        ),
        base_steps[2],
        base_steps[3],
    ]


def _build_planner_hints(
    *,
    topic: str,
    source_mode: str | None,
    route_role: str,
    route_intent: str,
    uploaded_documents: list[dict[str, Any]],
    rag_sources: object,
    research_mode: str,
    retrieval_stack_mode: str = "auto",
) -> dict[str, Any]:
    normalized_topic = topic.lower()
    _, _, language_hint = _detect_language_hint(topic)
    query_profile = analyze_query_profile(topic)
    is_ddi_query = bool(query_profile.get("is_ddi_query"))
    is_ddi_critical_query = is_ddi_query and _is_ddi_critical_topic(topic)
    is_comparison_query = _is_comparison_query(topic)
    is_nutrition_query = _is_nutrition_diet_query(topic)
    has_uploaded = bool(uploaded_documents)
    has_knowledge_sources = isinstance(rag_sources, list) and len(rag_sources) > 0
    evidence_query = any(
        token in normalized_topic
        for token in {
            "evidence",
            "guideline",
            "meta-analysis",
            "rct",
            "systematic",
            "interaction",
            "drug-drug",
            "ddi",
            "contraindication",
            "polypharmacy",
            "tuong tac",
            "tương tác",
            "da thuoc",
            "đa thuốc",
            "thuoc",
            "thuốc",
        }
    )
    evidence_query = bool(evidence_query or is_ddi_query)

    reason_codes: list[str] = ["tier2_standard_flow"]
    if research_mode == "deep":
        reason_codes.append("tier2_deep_mode")
    if research_mode == "deep_beta":
        reason_codes.append("tier2_deep_beta_mode")
    extracted_keywords = query_terms(topic)
    if has_uploaded:
        reason_codes.append("uploaded_documents_present")
    if has_knowledge_sources:
        reason_codes.append("knowledge_sources_present")
    if evidence_query:
        reason_codes.append("evidence_heavy_query")
    if is_ddi_query:
        reason_codes.append("ddi_query_detected")
    if is_ddi_critical_query:
        reason_codes.append("ddi_critical_query")
    if is_comparison_query:
        reason_codes.append("comparison_query_detected")
    if is_nutrition_query:
        reason_codes.append("nutrition_query_detected")
    requested_stack_mode = (
        "full" if str(retrieval_stack_mode).strip().lower() == "full" else "auto"
    )
    stack_mode = requested_stack_mode
    if research_mode == "fast" and requested_stack_mode == "full":
        stack_mode = "auto"
        reason_codes.append("stack_mode_full_downgraded_for_fast_mode")
    reason_codes.append(f"retrieval_stack_mode_{stack_mode}")

    internal_top_k = 4 if has_uploaded else 3
    if has_knowledge_sources:
        internal_top_k += 1
    if is_ddi_query:
        internal_top_k += 1
    if is_ddi_critical_query:
        internal_top_k += 1
    if is_comparison_query:
        internal_top_k += 1
    hybrid_top_k = max(internal_top_k + 1, 5 if evidence_query else 4)
    if is_ddi_critical_query:
        hybrid_top_k += 1
    if is_comparison_query:
        hybrid_top_k += 1

    deep_mode = research_mode == "deep"
    deep_beta_mode = research_mode == "deep_beta"
    deep_like_mode = deep_mode or deep_beta_mode
    force_multi_source = bool(deep_like_mode or is_nutrition_query)
    if deep_mode:
        internal_top_k = min(18, internal_top_k + 4)
        hybrid_top_k = min(18, hybrid_top_k + 6)
        target_pass_count = (
            20
            if is_comparison_query or is_nutrition_query
            else 18
            if is_ddi_query
            else 16
            if evidence_query
            else 14
        )
    elif deep_beta_mode:
        internal_top_k = min(18, internal_top_k + 6)
        hybrid_top_k = min(18, hybrid_top_k + 8)
        target_pass_count = (
            30
            if is_comparison_query or is_nutrition_query
            else 28
            if is_ddi_query
            else 24
            if evidence_query
            else 20
        )
    else:
        # Fast mode ưu tiên SLA: giới hạn fan-out retrieval để tránh timeout upstream.
        internal_top_k = min(4, max(2, internal_top_k))
        hybrid_top_k = min(5, max(3, hybrid_top_k))
        target_pass_count = 1
    # Web crawl chỉ bật mặc định ở deep/deep_beta để giảm latency dao động ở fast mode.
    web_enabled = bool(deep_like_mode or is_nutrition_query)
    if not deep_like_mode and (evidence_query or is_ddi_query):
        reason_codes.append("fast_mode_latency_guard")

    scientific_enabled = bool(deep_like_mode or is_nutrition_query)
    if not scientific_enabled and evidence_query:
        reason_codes.append("fast_scientific_disabled_for_sla")

    graphrag_enabled_override: bool | None = None
    if stack_mode == "full":
        scientific_enabled = True
        web_enabled = True
        reason_codes.append("stack_mode_full_force_scientific")
        reason_codes.append("stack_mode_full_force_web")

    pass_cap = _DEEP_BETA_PASS_CAP if deep_beta_mode else _DEFAULT_DEEP_PASS_CAP
    retrieval_budget = {
        "mode": research_mode,
        "retrieval_stack_mode": stack_mode,
        "target_pass_count": max(1, min(pass_cap, target_pass_count)),
        "pass_cap": pass_cap,
        "internal_top_k": max(1, min(18, internal_top_k)),
        "hybrid_top_k": max(1, min(18, hybrid_top_k)),
        "estimated_max_documents": max(1, min(18, hybrid_top_k))
        * max(1, min(pass_cap, target_pass_count)),
        "scientific_retrieval_enabled": scientific_enabled,
        "web_retrieval_enabled": web_enabled,
        "file_retrieval_enabled": True,
    }

    return {
        "internal_top_k": max(1, min(18, internal_top_k)),
        "hybrid_top_k": max(1, min(18, hybrid_top_k)),
        "query_focus": route_intent or "evidence_review",
        "reason_codes": reason_codes,
        "keywords": extracted_keywords,
        "is_ddi_query": is_ddi_query,
        "is_ddi_critical_query": is_ddi_critical_query,
        "is_comparison_query": is_comparison_query,
        "is_nutrition_query": is_nutrition_query,
        "language_hint": language_hint,
        "role": route_role,
        "source_mode": source_mode or "default",
        "low_context_threshold": 0.12 if has_uploaded else 0.15,
        "scientific_retrieval_enabled": scientific_enabled,
        "web_retrieval_enabled": web_enabled,
        "file_retrieval_enabled": True,
        "retrieval_stack_mode": stack_mode,
        "graphrag_enabled_override": graphrag_enabled_override,
        "research_mode": research_mode,
        "deep_pass_count": max(1, min(pass_cap, target_pass_count)),
        "force_multi_source": force_multi_source,
        "reasoning_style": (
            (
                "agentic_deep_research_beta_v1"
                if deep_beta_mode
                else "agentic_deep_research_v2"
                if deep_mode
                else "targeted_fast_research_v1"
            )
        ),
        "ddi_critical_query": is_ddi_critical_query,
        "retrieval_budget": retrieval_budget,
    }


def _flow_event(
    *,
    stage: str,
    status: str,
    source_count: int,
    note: str,
    component: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "stage": stage,
        "timestamp": _now_iso(),
        "status": status,
        "source_count": max(int(source_count), 0),
        "note": note,
        "detail": note,
        "component": component,
        "payload": payload or {},
    }


def _first_nonempty_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _safe_url(value: Any) -> str:
    text = str(value or "").strip()
    if text.startswith("https://") or text.startswith("http://"):
        return text
    return ""


def _compact_snippet(text: Any, *, max_len: int = 120) -> str:
    snippet = " ".join(str(text or "").split()).strip()
    if not snippet:
        return ""
    if len(snippet) <= max_len:
        return snippet
    return f"{snippet[: max_len - 3]}..."


def _compact_context_rows(
    rows: list[dict[str, Any]],
    *,
    max_items: int = 10,
    max_text_len: int = 260,
) -> list[dict[str, Any]]:
    compacted: list[dict[str, Any]] = []
    for row in rows[:max_items]:
        if not isinstance(row, dict):
            continue
        compacted.append(
            {
                "id": row.get("id"),
                "source": row.get("source"),
                "title": _context_title(row, fallback="Retrieved evidence"),
                "url": row.get("url"),
                "score": row.get("score"),
                "snippet": _compact_snippet(row.get("text"), max_len=max_text_len),
            }
        )
    return compacted


def _shrink_payload(value: Any, *, max_list: int = 12, max_str: int = 300) -> Any:
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = str(key).strip().lower()
            if normalized_key in {"text", "content", "raw", "html"}:
                output[key] = _compact_snippet(item, max_len=max_str)
            else:
                output[key] = _shrink_payload(item, max_list=max_list, max_str=max_str)
        return output
    if isinstance(value, list):
        return [
            _shrink_payload(item, max_list=max_list, max_str=max_str)
            for item in value[:max_list]
        ]
    if isinstance(value, str):
        return _compact_snippet(value, max_len=max_str)
    return value


def _compact_context_debug(value: Any) -> dict[str, Any]:
    context = value if isinstance(value, dict) else {}
    compact = _shrink_payload(context, max_list=12, max_str=300)
    if not isinstance(compact, dict):
        return {}
    retrieval_trace = compact.get("retrieval_trace")
    if isinstance(retrieval_trace, dict):
        top_context = retrieval_trace.get("top_context")
        if isinstance(top_context, list):
            retrieval_trace["top_context"] = _compact_context_rows(
                [item for item in top_context if isinstance(item, dict)],
                max_items=8,
                max_text_len=200,
            )
    return compact


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _build_evidence_review_summary(
    *,
    effective_context: list[dict[str, Any]],
    deep_pass_summaries: list[dict[str, Any]],
    evidence_verification: dict[str, Any],
) -> dict[str, Any]:
    source_counts: dict[str, int] = {}
    score_values: list[float] = []
    for row in effective_context:
        if not isinstance(row, dict):
            continue
        source_key = str(row.get("source") or "unknown").strip().lower() or "unknown"
        source_counts[source_key] = source_counts.get(source_key, 0) + 1
        score = _safe_float(row.get("score"), -1.0)
        if score >= 0:
            score_values.append(max(0.0, min(1.0, score)))

    total_evidence_rows = len(effective_context)
    unique_source_count = len(source_counts)
    average_relevance_score = (
        round(sum(score_values) / len(score_values), 4)
        if score_values
        else 0.0
    )

    contradicted_claims_raw = evidence_verification.get("contradicted_claims")
    contradicted_claims = (
        [str(item).strip() for item in contradicted_claims_raw if str(item).strip()]
        if isinstance(contradicted_claims_raw, list)
        else []
    )
    evidence_gaps_raw = evidence_verification.get("evidence_gaps")
    evidence_gaps = (
        [str(item).strip() for item in evidence_gaps_raw if str(item).strip()]
        if isinstance(evidence_gaps_raw, list)
        else []
    )

    source_error_count = 0
    for summary in deep_pass_summaries:
        if not isinstance(summary, dict):
            continue
        source_errors = summary.get("source_errors")
        if not isinstance(source_errors, dict):
            continue
        source_error_count += sum(
            1 for value in source_errors.values() if str(value or "").strip()
        )

    missing_evidence_signals: list[str] = []
    if total_evidence_rows < 3:
        missing_evidence_signals.append("low_evidence_row_count")
    if unique_source_count < 2:
        missing_evidence_signals.append("low_source_diversity")
    if source_error_count > 0:
        missing_evidence_signals.append("source_connector_errors")
    if evidence_gaps:
        missing_evidence_signals.extend(evidence_gaps[:6])
    missing_evidence_signals = _dedupe_query_list(missing_evidence_signals, limit=8)

    if total_evidence_rows >= 8 and unique_source_count >= 3 and not contradicted_claims:
        evidence_strength = "strong"
    elif total_evidence_rows >= 4 and unique_source_count >= 2:
        evidence_strength = "moderate"
    else:
        evidence_strength = "limited"

    status = "completed" if evidence_strength in {"strong", "moderate"} else "warning"
    note = (
        "Evidence review completed with broad source coverage."
        if status == "completed"
        else "Evidence review found limited/fragile support and requires caution."
    )
    return {
        "status": status,
        "note": note,
        "evidence_strength": evidence_strength,
        "total_evidence_rows": total_evidence_rows,
        "unique_source_count": unique_source_count,
        "average_relevance_score": average_relevance_score,
        "contradiction_count": len(contradicted_claims),
        "contradicted_claims": contradicted_claims[:5],
        "missing_evidence_signals": missing_evidence_signals,
        "source_error_count": source_error_count,
        "source_counts": source_counts,
        "pass_count": len(deep_pass_summaries),
    }


def _compact_verification_matrix_rows(
    rows: Any,
    *,
    max_items: int = 20,
    max_snippet_len: int = 180,
) -> list[dict[str, Any]]:
    compact_rows: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        return compact_rows

    for row in rows[:max_items]:
        if not isinstance(row, dict):
            continue
        raw_status = str(row.get("support_status") or "insufficient").strip().lower()
        support_status = "insufficient" if raw_status == "unsupported" else raw_status
        compact_rows.append(
            {
                "claim": _first_nonempty_text(row.get("claim")),
                "claim_type": _first_nonempty_text(row.get("claim_type")) or "general",
                "support_status": support_status or "insufficient",
                "overlap_score": round(
                    max(0.0, min(1.0, _safe_float(row.get("overlap_score")))),
                    4,
                ),
                "confidence": round(
                    max(0.0, min(1.0, _safe_float(row.get("confidence")))),
                    4,
                ),
                "evidence_ref": _first_nonempty_text(row.get("evidence_ref")) or None,
                "evidence_snippet": _compact_snippet(
                    row.get("evidence_snippet") or row.get("evidence"),
                    max_len=max_snippet_len,
                ),
                "rationale": _compact_snippet(row.get("rationale"), max_len=max_snippet_len),
            }
        )
    return compact_rows


def _summarize_verification_matrix(
    rows: list[dict[str, Any]],
    *,
    total_claims: int,
    supported_claims: int,
) -> dict[str, Any]:
    supported_count = 0
    insufficient_count = 0
    contradicted_count = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        status = str(row.get("support_status") or "").strip().lower()
        if status == "supported":
            supported_count += 1
        elif status == "contradicted":
            contradicted_count += 1
        else:
            insufficient_count += 1

    inferred_total = max(_safe_int(total_claims, 0), len(rows))
    inferred_supported = _safe_int(supported_claims, 0)
    if inferred_supported <= 0 and supported_count > 0:
        inferred_supported = supported_count
    inferred_supported = max(0, min(inferred_supported, inferred_total))
    support_ratio = inferred_supported / max(inferred_total, 1) if inferred_total > 0 else 0.0
    return {
        "version": "claim-v2-nli",
        "total_claims": inferred_total,
        "supported_claims": inferred_supported,
        "insufficient_claims": insufficient_count,
        "unsupported_claims": insufficient_count,
        "contradicted_claims": contradicted_count,
        "support_ratio": round(float(support_ratio), 4),
    }


def _build_contradiction_summary(
    verification_matrix_rows: list[dict[str, Any]],
    raw_summary: Any,
    *,
    fallback_note: str,
) -> dict[str, Any]:
    contradicted_rows = [
        row
        for row in verification_matrix_rows
        if str(row.get("support_status") or "").strip().lower() == "contradicted"
    ]
    default_note = (
        "Phát hiện claim mâu thuẫn với evidence retrieval."
        if contradicted_rows
        else "Không phát hiện claim mâu thuẫn."
    )
    defaults = {
        "version": "claim-v2-nli",
        "has_contradiction": bool(contradicted_rows),
        "contradiction_count": len(contradicted_rows),
        "claims": [str(item.get("claim") or "") for item in contradicted_rows[:5]],
        "details": [
            {
                "claim": item.get("claim", ""),
                "claim_type": item.get("claim_type", "general"),
                "evidence_ref": item.get("evidence_ref"),
                "evidence_snippet": item.get("evidence_snippet", ""),
                "overlap_score": item.get("overlap_score", 0.0),
                "confidence": item.get("confidence", 0.0),
                "rationale": item.get("rationale", ""),
            }
            for item in contradicted_rows[:5]
        ],
        "note": fallback_note or default_note,
    }
    if not isinstance(raw_summary, dict):
        return defaults

    claims = raw_summary.get("claims")
    details = raw_summary.get("details")
    contradiction_count = max(
        0,
        _safe_int(raw_summary.get("contradiction_count"), defaults["contradiction_count"]),
    )
    return {
        "version": str(raw_summary.get("version") or defaults["version"]),
        "has_contradiction": bool(
            raw_summary.get("has_contradiction", defaults["has_contradiction"])
        ),
        "contradiction_count": contradiction_count,
        "claims": (
            [str(item) for item in claims[:5]]
            if isinstance(claims, list)
            else defaults["claims"]
        ),
        "details": details if isinstance(details, list) else defaults["details"],
        "note": str(raw_summary.get("note") or defaults["note"]),
    }


_SAFETY_CRITICAL_CLAIM_TYPES = {"dosage", "contraindication"}
_SAFETY_CRITICAL_RISK_STATUSES = {"insufficient", "unsupported", "contradicted"}


def _evaluate_safety_critical_override(
    *,
    rows: list[dict[str, Any]],
    nli_enabled: bool,
) -> dict[str, Any]:
    if not nli_enabled:
        return {"applied": False, "reason": "nli_disabled"}

    critical_rows: list[dict[str, Any]] = []
    contradicted_rows: list[dict[str, Any]] = []
    insufficient_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        claim_type = str(row.get("claim_type") or "").strip().lower()
        support_status = str(row.get("support_status") or "").strip().lower()
        if claim_type not in _SAFETY_CRITICAL_CLAIM_TYPES:
            continue
        if support_status not in _SAFETY_CRITICAL_RISK_STATUSES:
            continue
        critical_rows.append(row)
        if support_status == "contradicted":
            contradicted_rows.append(row)
        else:
            insufficient_rows.append(row)

    if not critical_rows:
        return {"applied": False, "reason": "no_safety_critical_risk"}

    top_claims = [str(item.get("claim") or "") for item in critical_rows[:5]]
    base_payload = {
        "applied": True,
        "affected_claim_count": len(critical_rows),
        "claims": top_claims,
    }
    if contradicted_rows:
        return {
            **base_payload,
            "policy_action": "block",
            "verification_state": "warning",
            "severity_override": "high",
            "reason": "safety_critical_contradicted",
            "note": "Safety override: claim safety-critical bị contradicted, policy chuyển block.",
            "status": "blocked",
        }
    return {
        **base_payload,
        "policy_action": "warn",
        "verification_state": "warning",
        "severity_override": "high",
        "reason": "safety_critical_insufficient",
        "note": "Safety override: claim safety-critical ở trạng thái insufficient, policy chuyển warn.",
        "status": "warning",
    }


def _context_title(item: dict[str, Any], fallback: str) -> str:
    explicit = _first_nonempty_text(
        item.get("title"),
        item.get("name"),
        item.get("document_title"),
        item.get("filename"),
    )
    if explicit:
        return explicit

    text = _compact_snippet(item.get("text"), max_len=84)
    if text:
        return text

    return fallback


# --- R6: Recency / trust-tier composite ranking ------------------------------------------
# Reuses the trust_tier primitive already carried on retrieved rows (and read by the FIDES
# trust/recency tightening in ``rag/pipeline.py``). The comparator orders surfaced sources by a
# composite key ``(trust_tier asc, recency desc, base_score desc)`` so the highest-authority,
# most-recent, best-scoring evidence sorts first (R6.1, R6.3). Ranking and the surfaced
# provenance fields are gated on ``RESEARCH_RECENCY_TRUST_RANKING_ENABLED``; when the flag is off
# the rows are returned untouched and no provenance is attached, preserving the byte-for-byte
# legacy ordering and citation shape (R20.2).

# Sentinels keep rows whose signal is unknown deterministically *after* rows that carry the
# signal, without perturbing the relative order among themselves.
_UNKNOWN_TRUST_TIER_RANK = 99
_UNKNOWN_RECENCY_RANK = 1  # sorts after any "-year" key, which is always negative


def _row_metadata_value(row: Any, key: str) -> Any:
    """Read ``key`` from a context row, top-level or nested under ``metadata``."""

    if not isinstance(row, dict):
        return None
    if row.get(key) is not None:
        return row.get(key)
    nested = row.get("metadata")
    if isinstance(nested, dict):
        return nested.get(key)
    return None


def _row_trust_tier(row: Any) -> int | None:
    """Parse a row's ``trust_tier`` into the ``{1,2,3,4}`` authority band (else ``None``)."""

    try:
        tier = int(_row_metadata_value(row, "trust_tier"))
    except (TypeError, ValueError):
        return None
    return tier if 1 <= tier <= 4 else None


def _row_effective_date(row: Any) -> str | None:
    """Best-effort publication / effective date string for a row (``None`` when absent)."""

    for key in ("published_at", "effective_date", "date"):
        value = _row_metadata_value(row, key)
        if value:
            return str(value)
    return None


def _row_recency_year(row: Any) -> int | None:
    """Extract a 4-digit year from a row's date metadata (``None`` when undeterminable)."""

    raw = _row_effective_date(row)
    if not raw:
        return None
    match = re.search(r"(\d{4})", raw)
    if not match:
        return None
    year = int(match.group(1))
    return year if 1000 <= year <= 9999 else None


def _row_source_type(row: Any) -> str | None:
    """Source-type label for a row (``None`` when absent)."""

    value = _row_metadata_value(row, "source_type")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _composite_source_rank_key(row: dict[str, Any]) -> tuple[int, float, float]:
    """Composite ranking key ``(trust_tier asc, recency desc, base_score desc)``.

    Lower tuples sort first, so a higher-authority source (lower ``trust_tier``) leads; among
    equal tiers the more recent source leads; among equal tier + recency the higher base score
    leads (R6.1, R6.3). Rows missing a signal fall back to a sentinel so they sort after rows
    that carry it. The key is a total order, so :func:`sorted` is deterministic and the ranking
    is monotonic in each factor.
    """

    tier = _row_trust_tier(row)
    tier_key = tier if tier is not None else _UNKNOWN_TRUST_TIER_RANK
    year = _row_recency_year(row)
    recency_key = float(-year) if year is not None else float(_UNKNOWN_RECENCY_RANK)
    score_key = -_safe_float(row.get("score"))
    return (tier_key, recency_key, score_key)


def _rank_sources_by_recency_trust(
    rows: list[dict[str, Any]], *, enabled: bool
) -> list[dict[str, Any]]:
    """Order retrieved sources by the composite recency/trust-tier key (R6.1).

    Gated on ``RESEARCH_RECENCY_TRUST_RANKING_ENABLED``; when disabled the input is returned
    unchanged so legacy ordering is byte-for-byte preserved (R20.2). Python's sort is stable, so
    rows tying on the composite key keep their original relative order — the ranking stays
    deterministic.
    """

    if not enabled:
        return rows
    valid_rows = [row for row in rows if isinstance(row, dict)]
    return sorted(valid_rows, key=_composite_source_rank_key)


def _build_citations(
    topic: str,
    retrieved_context: list[dict[str, Any]],
    uploaded_documents: list[dict[str, Any]],
    *,
    research_mode: str | None = None,
    rank_enabled: bool = False,
) -> list[Citation]:
    handoff_profile = _resolve_evidence_handoff_profile(research_mode)
    citations: list[Citation] = []
    seen_source_ids: set[str] = set()

    # R6.1: order surfaced sources by the composite recency/trust-tier key before slicing the
    # citation window. A no-op when ``rank_enabled`` is False (legacy ordering preserved).
    ranked_context = _rank_sources_by_recency_trust(retrieved_context, enabled=rank_enabled)

    for idx, item in enumerate(
        ranked_context[: handoff_profile["citation_context_rows"]],
        start=1,
    ):
        if not isinstance(item, dict):
            continue

        source_name = _first_nonempty_text(item.get("source"), "retrieved")
        source_id = _first_nonempty_text(item.get("id"), f"{source_name}-{idx}")
        source_key = source_id.lower()
        if source_key in seen_source_ids:
            continue
        seen_source_ids.add(source_key)

        title = _context_title(item, fallback=f"Retrieved evidence {idx}")
        url = _safe_url(item.get("url"))
        relevance = f"Retrieved context matched query '{topic}' from source '{source_name}'."
        score = item.get("score")
        if isinstance(score, (int, float)):
            relevance = f"{relevance} Score={float(score):.4f}."

        # R6.2: surface trust_tier and publication/effective date per source, but only when the
        # ranking flag is on so a flags-off run keeps the legacy citation shape (R20.2). Unset
        # fields are stripped by ``_citation_as_payload``.
        citations.append(
            Citation(
                source_id=source_id,
                source=source_name,
                title=title,
                url=url,
                relevance=relevance,
                trust_tier=_row_trust_tier(item) if rank_enabled else None,
                source_type=_row_source_type(item) if rank_enabled else None,
                published_at=_row_effective_date(item) if rank_enabled else None,
            )
        )

    for idx, doc in enumerate(
        uploaded_documents[: handoff_profile["uploaded_document_rows"]],
        start=1,
    ):
        if not isinstance(doc, dict):
            continue

        source_name = _first_nonempty_text(doc.get("source"), "uploaded")
        file_id = _first_nonempty_text(doc.get("file_id"), doc.get("id"), f"file-{idx}")
        source_id = f"{source_name}-{file_id}"
        source_key = source_id.lower()
        if source_key in seen_source_ids:
            continue
        seen_source_ids.add(source_key)

        title = _first_nonempty_text(
            doc.get("filename"),
            doc.get("name"),
            doc.get("title"),
            f"Uploaded document {idx}",
        )
        url = _safe_url(doc.get("url"))
        preview = _compact_snippet(doc.get("preview") or doc.get("text"), max_len=120)
        relevance = f"Uploaded document context from source '{source_name}'."
        if preview:
            relevance = f"{relevance} Preview: {preview}"

        citations.append(
            Citation(
                source_id=source_id,
                source=source_name,
                title=title,
                url=url,
                relevance=relevance,
            )
        )

    return citations


def _build_planner_trace(
    *,
    topic: str,
    source_mode: str | None,
    route_role: str,
    route_intent: str,
    route_confidence: float,
    route_emergency: bool,
    planner_hints: dict[str, Any],
    plan_steps: list[PlanStep],
) -> dict[str, Any]:
    return {
        "stage": "planner-v1",
        "timestamp": _now_iso(),
        "topic": topic,
        "source_mode": source_mode,
        "routing": {
            "role": route_role,
            "intent": route_intent,
            "confidence": route_confidence,
            "emergency": route_emergency,
        },
        "planner_hints": planner_hints,
        "plan_steps": [asdict(step) for step in plan_steps],
    }


def _build_retrieval_trace(
    *,
    rag_result: Any,
    planner_hints: dict[str, Any],
) -> dict[str, Any]:
    context_debug = rag_result.context_debug if isinstance(rag_result.context_debug, dict) else {}
    retrieval_debug = (
        context_debug.get("retrieval_trace")
        if isinstance(context_debug.get("retrieval_trace"), dict)
        else {}
    )
    source_errors = retrieval_debug.get("source_errors")
    if not isinstance(source_errors, dict):
        source_errors = {}
    query_plan = retrieval_debug.get("query_plan")
    if not isinstance(query_plan, dict):
        query_plan = {}
    generation_trace = (
        rag_result.trace.get("generation")
        if isinstance(getattr(rag_result, "trace", None), dict)
        and isinstance(rag_result.trace.get("generation"), dict)
        else {}
    )
    fallback_reason_raw = generation_trace.get("fallback_reason")
    fallback_reason = str(fallback_reason_raw).strip() if fallback_reason_raw is not None else ""
    compact_top_context = _compact_context_rows(
        rag_result.retrieved_context if isinstance(rag_result.retrieved_context, list) else [],
        max_items=8,
        max_text_len=220,
    )
    return {
        "stage": "retrieval-v2",
        "timestamp": _now_iso(),
        "planner_hints": planner_hints,
        "relevance": context_debug.get("relevance"),
        "low_context_threshold": context_debug.get("low_context_threshold"),
        "external_attempted": context_debug.get("external_attempted"),
        "source_counts": context_debug.get("source_counts"),
        "used_stages": context_debug.get("used_stages"),
        "retrieved_ids": list(rag_result.retrieved_ids),
        "retrieved_count": len(rag_result.retrieved_ids),
        "retriever_debug": _shrink_payload(retrieval_debug, max_list=12, max_str=300),
        "search_plan": retrieval_debug.get("search_plan")
        if isinstance(retrieval_debug.get("search_plan"), dict)
        else {},
        "source_attempts": retrieval_debug.get("source_attempts")
        if isinstance(retrieval_debug.get("source_attempts"), list)
        else [],
        "source_errors": source_errors,
        "fallback_reason": fallback_reason or None,
        "query_plan": query_plan,
        "stack_mode_requested": str(retrieval_debug.get("stack_mode_requested") or "auto"),
        "stack_mode_effective": str(retrieval_debug.get("stack_mode_effective") or "auto"),
        "stack_mode_reason_codes": (
            [str(item).strip() for item in retrieval_debug.get("stack_mode_reason_codes", []) if str(item).strip()]
            if isinstance(retrieval_debug.get("stack_mode_reason_codes"), list)
            else []
        ),
        "stack_coverage": retrieval_debug.get("stack_coverage")
        if isinstance(retrieval_debug.get("stack_coverage"), dict)
        else {},
        "index_summary": retrieval_debug.get("index_summary")
        if isinstance(retrieval_debug.get("index_summary"), dict)
        else {},
        "crawl_summary": retrieval_debug.get("crawl_summary")
        if isinstance(retrieval_debug.get("crawl_summary"), dict)
        else {},
        "top_context": compact_top_context,
    }


def _build_verifier_trace(
    *,
    factcheck_result: Any,
    policy_action: str,
    verification_state: str,
    verification_matrix: dict[str, Any] | None = None,
) -> dict[str, Any]:
    trace = {
        "stage": "verifier-v1",
        "timestamp": _now_iso(),
        "verifier": factcheck_result.stage,
        "state": verification_state,
        "policy_action": policy_action,
        "verdict": factcheck_result.verdict,
        "severity": factcheck_result.severity,
        "confidence": factcheck_result.confidence,
        "supported_claims": factcheck_result.supported_claims,
        "total_claims": factcheck_result.total_claims,
        "unsupported_claims": factcheck_result.unsupported_claims,
        "evidence_count": factcheck_result.evidence_count,
        "note": factcheck_result.note,
    }
    if isinstance(verification_matrix, dict):
        trace["verification_matrix"] = verification_matrix
    return trace


def _normalize_retrieval_events(
    events: list[dict[str, Any]],
    *,
    default_component: str = "retrieval",
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    first_timestamp: datetime | None = None

    for item in events:
        if not isinstance(item, dict):
            continue
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        source_count_raw = item.get("source_count", 0)
        try:
            source_count = int(source_count_raw)
        except (TypeError, ValueError):
            source_count = 0
        parsed_timestamp = _parse_event_timestamp(item.get("timestamp"))
        if parsed_timestamp and first_timestamp is None:
            first_timestamp = parsed_timestamp
        elapsed_ms = (
            round((parsed_timestamp - first_timestamp).total_seconds() * 1000.0, 3)
            if parsed_timestamp and first_timestamp
            else None
        )
        sequence = len(normalized) + 1
        payload.setdefault("source_count", max(source_count, 0))
        payload.setdefault("event_sequence", sequence)
        if elapsed_ms is not None:
            payload.setdefault("elapsed_ms", elapsed_ms)
        normalized.append(
            {
                **item,
                "component": str(item.get("component") or default_component),
                "detail": str(item.get("detail") or item.get("note") or ""),
                "payload": payload,
                "event_sequence": sequence,
                **({"elapsed_ms": elapsed_ms} if elapsed_ms is not None else {}),
            }
        )
    return normalized


def _build_stage_span_summaries(
    flow_events: list[dict[str, Any]],
    *,
    stage_entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not stage_entries:
        return []

    events_by_stage: dict[str, list[dict[str, Any]]] = {}
    retrieval_like_events: list[dict[str, Any]] = []
    for event in flow_events:
        if not isinstance(event, dict):
            continue
        stage = str(event.get("stage") or "").strip()
        if not stage:
            continue
        events_by_stage.setdefault(stage, []).append(event)
        stage_lower = stage.lower()
        component = str(event.get("component") or "").strip().lower()
        if (
            component in {"retrieval", "deep_retrieval", "deep_beta_retrieval"}
            or "retrieval" in stage_lower
            or "search" in stage_lower
            or "index" in stage_lower
        ):
            retrieval_like_events.append(event)

    status_start_markers = {"started", "start", "running", "in_progress"}
    stage_aliases: dict[str, list[str]] = {
        "plan": ["planner"],
        "hybrid_retrieval": [],
    }

    spans: list[dict[str, Any]] = []
    for stage_entry in stage_entries:
        if not isinstance(stage_entry, dict):
            continue
        stage_name = str(stage_entry.get("name") or "").strip()
        if not stage_name:
            continue

        stage_events: list[dict[str, Any]] = []
        if stage_name == "hybrid_retrieval":
            stage_events = retrieval_like_events
        else:
            candidates = stage_aliases.get(stage_name, [stage_name])
            for candidate in candidates:
                stage_events.extend(events_by_stage.get(candidate, []))

        start_at: str | None = None
        end_at: str | None = None
        duration_ms: float | None = None
        event_count = len(stage_events)
        final_status = str(stage_entry.get("status") or "unknown")
        source_count = 0
        first_event_sequence: int | None = None
        last_event_sequence: int | None = None

        if stage_events:
            start_event = next(
                (
                    item
                    for item in stage_events
                    if str(item.get("status") or "").strip().lower() in status_start_markers
                ),
                stage_events[0],
            )
            end_event = next(
                (
                    item
                    for item in reversed(stage_events)
                    if str(item.get("status") or "").strip().lower() not in status_start_markers
                ),
                stage_events[-1],
            )
            start_at_raw = str(start_event.get("timestamp") or "").strip()
            end_at_raw = str(end_event.get("timestamp") or "").strip()
            start_at = start_at_raw or None
            end_at = end_at_raw or None
            start_ts = _parse_event_timestamp(start_at)
            end_ts = _parse_event_timestamp(end_at)
            if start_ts and end_ts:
                duration_ms = round(max((end_ts - start_ts).total_seconds() * 1000.0, 0.0), 3)
            final_status = str(end_event.get("status") or final_status)
            source_count = max(_safe_int(end_event.get("source_count"), 0), 0)
            first_event_sequence = _safe_int(start_event.get("event_sequence"), 0) or None
            last_event_sequence = _safe_int(end_event.get("event_sequence"), 0) or None

        spans.append(
            {
                "stage": stage_name,
                "status": final_status,
                "start_at": start_at,
                "end_at": end_at,
                "duration_ms": duration_ms,
                "event_count": event_count,
                "source_count": source_count,
                "first_event_sequence": first_event_sequence,
                "last_event_sequence": last_event_sequence,
            }
        )
    return spans


def _build_otel_trace_metadata(
    *,
    trace_id: str,
    run_id: str,
    stage_spans: list[dict[str, Any]],
    flow_events: list[dict[str, Any]],
) -> dict[str, Any]:
    span_rows: list[dict[str, Any]] = []
    for row in stage_spans:
        if not isinstance(row, dict):
            continue
        name = str(row.get("stage") or "").strip()
        if not name:
            continue
        span_rows.append(
            {
                "name": name,
                "status": str(row.get("status") or "unknown"),
                "start_at": row.get("start_at"),
                "end_at": row.get("end_at"),
                "duration_ms": row.get("duration_ms"),
                "event_count": row.get("event_count"),
                "source_count": row.get("source_count"),
            }
        )

    return {
        "trace_id": trace_id,
        "run_id": run_id,
        "service_name": "clara-ml",
        "component": "research_tier2",
        "span_count": len(span_rows),
        "event_count": len(flow_events),
        "spans": span_rows,
    }


def _emit_otel_trace_best_effort(
    *,
    otel_trace_metadata: dict[str, Any],
    flow_events: list[dict[str, Any]],
) -> dict[str, Any]:
    endpoint = str(settings.otel_export_endpoint or "").strip()
    enabled = bool(settings.otel_export_enabled) and bool(endpoint)
    status: dict[str, Any] = {
        "enabled": enabled,
        "sent": False,
    }
    if not enabled:
        return status

    payload = {
        "service_name": "clara-ml",
        "component": "research_tier2",
        "trace": otel_trace_metadata,
        "event_count": len(flow_events),
        "exported_at": _now_iso(),
    }
    request = urllib.request.Request(
        url=endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(  # noqa: S310
            request,
            timeout=float(settings.otel_export_timeout_seconds),
        ) as response:
            status["sent"] = True
            status["http_status"] = int(response.getcode())
            return status
    except urllib.error.HTTPError as exc:
        status["http_status"] = int(exc.code)
        status["error"] = "export_failed"
        return status
    except Exception as exc:  # noqa: BLE001
        logger.warning("OTel export failed: %s", type(exc).__name__)
        status["error"] = "export_failed"
        return status


def _build_deep_subqueries(
    topic: str,
    keywords: list[str],
    pass_count: int,
    *,
    seed_queries: list[str] | None = None,
) -> list[str]:
    cleaned_keywords = [item.strip() for item in keywords if isinstance(item, str) and item.strip()]
    keyword_hint = " ".join(cleaned_keywords[:4]).strip()
    query_profile = analyze_query_profile(topic)
    comparison_query = _is_comparison_query(topic)
    nutrition_query = _is_nutrition_diet_query(topic)
    base = [
        *(seed_queries or []),
        topic,
        f"{topic} guideline recommendations and first-line safety considerations",
        f"{topic} systematic review and meta-analysis clinical outcomes",
        f"{topic} adverse events contraindications interaction risks",
        f"{topic} subgroup analysis older adults CKD liver disease polypharmacy",
        f"{topic} contradictory findings limitations and uncertainty analysis",
        f"{topic} clinical decision criteria patient-centered recommendation framework",
    ]
    if query_profile.get("is_ddi_query"):
        primary = str(query_profile.get("primary_drug") or "index drug").strip()
        co_drugs = query_profile.get("co_drugs", [])
        co_block = (
            ", ".join(str(item) for item in co_drugs[:4])
            if isinstance(co_drugs, list) and co_drugs
            else "common analgesics"
        )
        base.extend(
            [
                f"{primary} interaction with {co_block} bleeding risk INR safety",
                f"{primary} contraindication mechanism management with {co_block}",
                f"{primary} painkiller interaction systematic review meta-analysis",
            ]
        )
    if comparison_query:
        base.extend(
            [
                f"{topic} adherence burden and long-term sustainability comparison",
                f"{topic} comparative effectiveness across key clinical endpoints",
                f"{topic} implementation feasibility cost and accessibility analysis",
                f"{topic} decision trade-offs and subgroup-sensitive recommendations",
            ]
        )
    if nutrition_query and comparison_query:
        base.extend(
            [
                f"{topic} sodium control versus healthy fat optimization clinical implications",
                f"{topic} blood pressure lipid glycemic endpoint comparison",
                f"{topic} Vietnam dietary habit adaptation feasibility DASH Mediterranean",
            ]
        )
    if keyword_hint:
        base.extend(
            [
                f"{topic} evidence profile for {keyword_hint}",
                f"{topic} mechanism and pharmacology context for {keyword_hint}",
            ]
        )

    deduped: list[str] = []
    seen: set[str] = set()
    for item in base:
        key = item.lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= pass_count:
            break
    return deduped


# --- Agentic query decomposition (R4) ------------------------------------------------------
# A bounded, deterministic decomposition of a compound research question into an ordered set
# of sub-questions. It runs only when ``RESEARCH_QUERY_DECOMPOSITION_ENABLED`` is on and the
# research mode is deep/deep_beta; retrieval then runs once per returned sub-question (R4.2).
# Decomposition is intentionally deterministic (no network/LLM dependency) so it stays cheap,
# reproducible, and easy to test, while still broadening retrieval coverage facet-by-facet.

# Conjunction/separator markers used to split a compound question into clause sub-questions.
# Vietnamese forms are matched directly (with diacritics) alongside English equivalents.
_QUERY_CLAUSE_SPLIT_RE = re.compile(
    r"(?:\bcùng với\b|\bkết hợp với\b|\bkết hợp\b|\bso với\b|\bvà\b"
    r"|\band\b|\bversus\b|\bvs\.?\b|[;])",
    re.IGNORECASE,
)

# Facet expansions broaden coverage across the evidence dimensions a researcher expects.
_QUERY_DECOMPOSITION_FACETS_VI: tuple[str, ...] = (
    "{topic}: hiệu quả và bằng chứng lâm sàng",
    "{topic}: an toàn, chống chỉ định và tương tác",
    "{topic}: khuyến nghị hướng dẫn và áp dụng thực hành",
)
_QUERY_DECOMPOSITION_FACETS_EN: tuple[str, ...] = (
    "{topic}: efficacy and clinical evidence",
    "{topic}: safety, contraindications and interactions",
    "{topic}: guideline recommendations and practical application",
)


def _split_query_clauses(topic: str) -> list[str]:
    """Split a compound research question into clause-level sub-questions.

    Returns the discovered clauses only when the query actually decomposes into two or
    more substantial parts; otherwise returns an empty list so the caller can fall back to
    facet-based expansion. Each clause must carry at least three words to avoid fragments.
    """

    parts = _QUERY_CLAUSE_SPLIT_RE.split(str(topic or ""))
    clauses: list[str] = []
    for part in parts:
        clause = " ".join(str(part).split()).strip(" ,.-")
        if len(clause.split()) >= 3:
            clauses.append(clause)
    return clauses if len(clauses) >= 2 else []


def _decompose_into_subquestions(
    topic: str,
    *,
    keywords: list[str],
    seed_queries: list[str],
    max_subqueries: int,
) -> list[str]:
    """Build an ordered, de-duplicated set of sub-questions for ``topic`` (R4.1).

    Ordering: the original query first, then any plan-provided seed queries, clause-level
    splits of compound questions, evidence-facet expansions, and finally a keyword-targeted
    sub-question. The list is capped at ``max_subqueries``.
    """

    ordered: list[str] = []
    seen: set[str] = set()

    def _add(candidate: Any) -> None:
        text = " ".join(str(candidate or "").split()).strip()
        if not text:
            return
        key = text.lower()
        if key in seen:
            return
        seen.add(key)
        ordered.append(text)

    # 1. The original query is always the first sub-question.
    _add(topic)
    # 2. Explicit plan-provided seed queries (e.g. query_plan.decomposition).
    for seed in seed_queries:
        _add(seed)
    # 3. Clause-level decomposition of compound questions.
    for clause in _split_query_clauses(topic):
        _add(clause)
    # 4. Evidence-facet expansions to broaden retrieval coverage.
    _, _, language_hint = _detect_language_hint(topic)
    facets = (
        _QUERY_DECOMPOSITION_FACETS_EN
        if language_hint == "en"
        else _QUERY_DECOMPOSITION_FACETS_VI
    )
    for facet in facets:
        _add(facet.format(topic=topic))
    # 5. Keyword-targeted sub-question.
    cleaned_keywords = [item.strip() for item in keywords if isinstance(item, str) and item.strip()]
    if cleaned_keywords:
        _add(f"{topic} — {', '.join(cleaned_keywords[:4])}")

    cap = max(1, int(max_subqueries))
    return ordered[:cap]


def decompose_query(
    topic: str,
    *,
    enabled: bool,
    mode: str,
    keywords: list[str] | None = None,
    seed_queries: list[str] | None = None,
    max_subqueries: int = 6,
) -> list[str]:
    """Decompose a research query into an ordered set of sub-questions (R4).

    Returns the original query as a single-element plan ``[topic]`` when decomposition is
    disabled or the mode is not ``deep``/``deep_beta`` (R4.3, legacy single-query behavior),
    and also falls back to ``[topic]`` when decomposition yields nothing (R4.5). When enabled
    for deep/deep_beta the result is an ordered, de-duplicated list of sub-questions; the
    orchestrator runs retrieval exactly once per returned sub-question (R4.2).
    """

    clean_topic = str(topic or "").strip()
    if not clean_topic:
        return []
    if not enabled or mode not in {"deep", "deep_beta"}:
        return [clean_topic]
    subquestions = _decompose_into_subquestions(
        clean_topic,
        keywords=keywords or [],
        seed_queries=seed_queries or [],
        max_subqueries=max_subqueries,
    )
    return subquestions or [clean_topic]


def _gap_fill_should_run(
    retrieved_count: int,
    *,
    enabled: bool,
    min_results: int,
    max_passes: int,
    passes_used: int,
) -> bool:
    """Decide whether one more bounded gap-fill retrieval pass may run (R5).

    Returns ``True`` only when iterative gap-fill is enabled, the sub-question has
    insufficient supporting evidence (fewer than ``min_results`` docs, R5.1), and the
    cumulative gap-fill pass budget has not been exhausted (R5.2, R5.3). The caller
    increments ``passes_used`` after each executed pass, so the cumulative count can
    never exceed ``max_passes`` and the loop is guaranteed to terminate.
    """

    if not enabled:
        return False
    if max_passes <= 0:
        return False
    if retrieved_count >= max(1, min_results):
        return False
    return passes_used < max_passes


def _deep_research_methodology(*, topic: str, subqueries: list[str]) -> dict[str, Any]:
    return {
        "id": "agentic-deep-research-v2",
        "inspired_patterns": [
            "query_decomposition",
            "breadth_first_retrieval",
            "iterative_multi_pass_search",
            "counter_evidence_scan",
            "cross_source_consensus",
            "citation_first_synthesis",
        ],
        "query": topic,
        "subquery_count": len(subqueries),
        "subqueries": subqueries,
        "stages": [
            {
                "name": "scope_and_hypothesis",
                "goal": "Chuẩn hóa câu hỏi, tách giả thuyết chính/phản biện.",
            },
            {
                "name": "evidence_collection",
                "goal": "Thu thập bằng chứng đa nguồn theo nhiều pass.",
            },
            {
                "name": "contradiction_audit",
                "goal": "Tìm bất đồng, ngoại lệ theo nhóm bệnh nền.",
            },
            {
                "name": "consensus_and_translation",
                "goal": "Tổng hợp điểm đồng thuận và khuyến nghị an toàn có điều kiện.",
            },
        ],
    }


def _deep_beta_research_methodology(
    *,
    topic: str,
    subqueries: list[str],
    retrieval_budget: dict[str, Any],
) -> dict[str, Any]:
    base = _deep_research_methodology(topic=topic, subqueries=subqueries)
    return {
        **base,
        "id": "agentic-deep-research-beta-v2",
        "query": topic,
        "retrieval_budget": retrieval_budget,
        "inspired_patterns": [
            *base.get("inspired_patterns", []),
            "retrieval_budgeting",
            "iterative_gap_fill",
            "reasoning_chain_audit",
            "parallel_reasoning_workers",
            "evidence_quality_auditor",
            "longform_report_synthesis",
        ],
        "stages": [
            {
                "name": "beta_scope_lock",
                "goal": "Khoá phạm vi lâm sàng, giả định và tiêu chí loại trừ ngay từ đầu.",
            },
            {
                "name": "beta_hypothesis_map",
                "goal": "Tạo bản đồ giả thuyết/chống giả thuyết kèm bằng chứng kỳ vọng.",
            },
            {
                "name": "beta_budgeted_retrieval",
                "goal": "Phân bổ ngân sách retrieval theo pass/source và chạy multi-pass.",
            },
            {
                "name": "beta_reasoning_chain",
                "goal": "Liên kết bằng chứng-pass thành chuỗi lập luận có kiểm lỗi.",
            },
            {
                "name": "beta_chain_verification",
                "goal": "Đánh dấu mắt xích yếu, mâu thuẫn và mức tự tin cuối.",
            },
            {
                "name": "beta_parallel_reasoning",
                "goal": "Chạy nhiều node reasoning LLM song song để kiểm evidence/gap/mâu thuẫn.",
            },
            {
                "name": "beta_evidence_verification",
                "goal": "Hợp nhất evidence-check theo claim và gắn cờ mắt xích chưa đủ bằng chứng.",
            },
            {
                "name": "beta_longform_report",
                "goal": "Tổng hợp báo cáo dài dạng markdown, ưu tiên phân tích rõ ràng và bảng bằng chứng.",
            },
        ],
    }


def _build_deep_beta_reasoning_steps(*, topic: str, subqueries: list[str]) -> list[dict[str, Any]]:
    objectives = {
        "deep_beta_scope": "Lock scope, safety boundaries and exclusions for the beta chain.",
        "deep_beta_hypothesis_map": "Map main/counter hypotheses with expected supporting evidence.",
        "deep_beta_retrieval_budget": "Allocate retrieval budgets and quality thresholds across passes.",
        "deep_beta_multi_pass_retrieval": "Run iterative retrieval passes and close evidence gaps.",
        "deep_beta_evidence_audit": "LLM node: audit evidence coverage, quality, and unresolved dimensions.",
        "deep_beta_claim_graph": "LLM node: derive claim/conflict graph and contradiction hypotheses.",
        "deep_beta_counter_evidence_scan": "LLM node: seek strongest counter-evidence and boundary conditions.",
        "deep_beta_guideline_alignment": "LLM node: compare findings against guideline-level recommendations.",
        "deep_beta_risk_stratification": "LLM node: stratify risk by subgroup and red-flag conditions.",
        "deep_beta_gap_fill": "Run targeted retrieval passes to fill evidence gaps from LLM audit.",
        "deep_beta_evidence_verification": "LLM node: verify claim support/contradiction coverage before synthesis.",
        "deep_beta_chain_synthesis": "Generate long-form synthesis chain from pass-level evidence.",
        "deep_beta_chain_verification": "Validate chain consistency, contradictions, and uncertainty.",
        "deep_beta_report_synthesis": "LLM node: synthesize long-form final report with explicit evidence contract.",
        "deep_beta_quality_gate": "LLM node: final quality gate for groundedness/completeness before response.",
    }
    steps: list[dict[str, Any]] = []
    for index, stage in enumerate(_DEEP_BETA_REASONING_STAGE_ORDER):
        steps.append(
            {
                "stage": stage,
                "status": "pending",
                "objective": objectives.get(stage, stage),
                "subquery": subqueries[index] if index < len(subqueries) else topic,
            }
        )
    return steps

def _resolve_deep_pass_count(
    payload: dict[str, Any],
    default_count: int,
    *,
    cap: int = _DEFAULT_DEEP_PASS_CAP,
) -> int:
    metadata_obj = payload.get("metadata")
    metadata = metadata_obj if isinstance(metadata_obj, dict) else {}
    candidates = [
        payload.get("deep_pass_count"),
        payload.get("deep_passes"),
        payload.get("pass_count"),
        metadata.get("deep_pass_count"),
        metadata.get("deep_passes"),
        metadata.get("pass_count"),
    ]

    for raw in candidates:
        try:
            parsed = int(raw)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        return max(1, min(max(cap, 1), parsed))
    return max(1, min(max(cap, 1), int(default_count)))


def _merge_retrieved_context(
    primary: list[dict[str, Any]],
    extras: list[list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _append_rows(rows: list[dict[str, Any]]) -> None:
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_id = str(row.get("id") or "")
            row_source = str(row.get("source") or "")
            row_title = str(row.get("title") or row.get("filename") or "")[:80]
            key = f"{row_id}|{row_source}|{row_title}"
            if key in seen:
                continue
            seen.add(key)
            merged.append(row)

    _append_rows(primary)
    for rows in extras:
        _append_rows(rows)
    return merged


def _is_drug_interaction_query(topic: str) -> bool:
    return bool(analyze_query_profile(topic).get("is_ddi_query"))


def _filter_context_for_topic(topic: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not _is_drug_interaction_query(topic):
        return rows

    profile = analyze_query_profile(topic)
    primary = str(profile.get("primary_drug") or "").strip().lower()
    primary_aliases = {
        str(item).strip().lower()
        for item in profile.get("primary_aliases", [])
        if str(item).strip()
    }
    if primary:
        primary_aliases.add(primary)
    co_drugs = {
        str(item).strip().lower()
        for item in profile.get("co_drugs", [])
        if str(item).strip()
    }
    co_drug_aliases = set(co_drugs)
    co_drug_aliases_raw = profile.get("co_drug_aliases")
    if isinstance(co_drug_aliases_raw, dict):
        for aliases in co_drug_aliases_raw.values():
            if not isinstance(aliases, list):
                continue
            for item in aliases:
                alias = str(item).strip().lower()
                if alias:
                    co_drug_aliases.add(alias)
    interaction_terms = {
        "interaction",
        "ddi",
        "drug-drug",
        "coadministration",
        "contraindication",
        "bleeding",
        "inr",
        "hypoglycemia",
        "lactic",
        "acidosis",
        "renal",
        "clearance",
        "contrast",
    }
    noise_markers = {
        "diet",
        "ketogenic",
        "pcos",
        "heart failure",
        "sodium",
        "mediterranean",
        "dash",
        "exercise",
        "obesity",
        "nutrition",
    }
    filtered: list[dict[str, Any]] = []

    for row in rows:
        if not isinstance(row, dict):
            continue
        haystack = " ".join(
            [
                str(row.get("title") or ""),
                str(row.get("text") or ""),
                str(row.get("source") or ""),
                str(row.get("id") or ""),
            ]
        ).lower()
        tokens = {token for token in re.findall(r"[0-9a-zA-ZÀ-ỹ]{2,}", haystack) if token}
        if primary_aliases and not primary_aliases.intersection(tokens):
            continue

        source_name = str(row.get("source") or "").strip().lower()
        has_primary = bool(primary_aliases.intersection(tokens))
        has_codrug = bool(co_drug_aliases.intersection(tokens))
        has_interaction = bool(interaction_terms.intersection(tokens))
        trusted_label_source = source_name in {"openfda", "dailymed", "rxnorm", "rxnav"}
        scientific_source = source_name in {"pubmed", "europepmc", "semantic_scholar", "openalex"}
        has_noise_topic = any(marker in haystack for marker in noise_markers)

        # Keep strong DDI rows (primary + co-drug or interaction).
        if has_primary and (has_codrug or has_interaction):
            filtered.append(row)
            continue

        # Drop noisy lifestyle rows for DDI tasks unless they carry interaction signals.
        if scientific_source and has_primary and has_noise_topic and not has_codrug and not has_interaction:
            continue

        # Keep authoritative drug-label rows mentioning primary drug,
        # so we do not zero out evidence when query is specific but corpus is sparse.
        if has_primary and trusted_label_source:
            filtered.append(row)

    return filtered


def _infer_fallback_used(rag_result: Any) -> bool:
    trace = rag_result.trace if isinstance(getattr(rag_result, "trace", None), dict) else {}
    generation = trace.get("generation") if isinstance(trace.get("generation"), dict) else {}
    generation_mode = str(generation.get("mode") or "").strip().lower()
    if generation_mode in {"llm", "retrieval_only"}:
        return False
    if generation_mode == "local_synthesis":
        return True

    model_used = str(getattr(rag_result, "model_used", "") or "").strip().lower()
    if model_used.startswith("local-synth"):
        return True
    return "fallback" in model_used


def _trace_rows_for_citation(
    retrieval_trace: dict[str, Any],
    *,
    research_mode: str | None = None,
) -> list[dict[str, Any]]:
    handoff_profile = _resolve_evidence_handoff_profile(research_mode)
    retriever_debug = (
        retrieval_trace.get("retriever_debug")
        if isinstance(retrieval_trace.get("retriever_debug"), dict)
        else {}
    )
    top_documents = retriever_debug.get("top_documents")
    if not isinstance(top_documents, list):
        return []

    rows: list[dict[str, Any]] = []
    for item in top_documents[: handoff_profile["citation_trace_rows"]]:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source") or "retrieved")
        doc_id = str(item.get("id") or "")
        url = _safe_url(item.get("url"))
        score = item.get("score")
        rows.append(
            {
                "id": doc_id or f"{source}-{len(rows) + 1}",
                "source": source,
                "title": doc_id or f"{source} evidence",
                "text": "",
                "url": url,
                "score": score,
            }
        )
    return rows


def _has_markdown_heading(content: str, heading: str) -> bool:
    pattern = re.compile(rf"^\s*{re.escape(heading)}\s*$", flags=re.IGNORECASE | re.MULTILINE)
    return bool(pattern.search(content))


def _citation_markdown_lines(citations: list[Citation]) -> list[str]:
    if not citations:
        return ["- [1] Chưa có nguồn tham chiếu cụ thể trong phản hồi hiện tại."]

    rows: list[str] = []
    for index, citation in enumerate(citations[:12], start=1):
        title = _first_nonempty_text(citation.title, citation.source, citation.source_id, f"Nguồn {index}")
        url = _safe_url(citation.url)
        if url:
            rows.append(f"- [{index}] {title} ({url})")
        else:
            rows.append(f"- [{index}] {title}")
    return rows


def _escape_markdown_cell(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()


def _evidence_table_markdown(
    citations: list[Citation],
    *,
    max_rows: int = 8,
) -> str:
    headers = "| Nguồn | Tiêu đề | Mức liên quan | URL |"
    separator = "| --- | --- | --- | --- |"
    rows: list[str] = [headers, separator]
    if not citations:
        rows.append("| system_fallback | Chưa có nguồn | Cần truy xuất thêm bằng chứng. | - |")
        return "\n".join(rows)

    for citation in citations[:max_rows]:
        url = _safe_url(citation.url) or "-"
        rows.append(
            "| "
            f"{_escape_markdown_cell(citation.source)} | "
            f"{_escape_markdown_cell(citation.title)} | "
            f"{_escape_markdown_cell(_compact_snippet(citation.relevance, max_len=96))} | "
            f"{_escape_markdown_cell(url)} |"
        )
    return "\n".join(rows)


def _extract_answer_digest_points(answer: str, *, limit: int = 3) -> list[str]:
    cleaned = " ".join(str(answer or "").split()).strip()
    if not cleaned:
        return []
    chunks = re.split(r"(?<=[.!?])\s+", cleaned)
    points: list[str] = []
    for chunk in chunks:
        point = chunk.strip(" -")
        if not point:
            continue
        points.append(_compact_snippet(point, max_len=160))
        if len(points) >= max(1, limit):
            break
    return points


def _build_chart_specs(
    *,
    citations: list[Citation],
    verification_matrix_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    source_counts: dict[str, int] = {}
    for citation in citations:
        source_name = _first_nonempty_text(citation.source, "unknown")
        source_counts[source_name] = source_counts.get(source_name, 0) + 1
    if not source_counts:
        source_counts["system_fallback"] = 1

    source_values = [{"source": key, "count": value} for key, value in source_counts.items()]
    chart_specs: list[dict[str, Any]] = [
        {
            "id": "source_distribution",
            "type": "chart-spec",
            "engine": "vega-lite",
            "title": "Phân bổ nguồn bằng chứng",
            "config": {
                "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                "description": "Distribution of evidence citations by source.",
                "data": {"values": source_values},
                "mark": {"type": "bar", "cornerRadiusTopLeft": 4, "cornerRadiusTopRight": 4},
                "encoding": {
                    "x": {"field": "source", "type": "nominal", "sort": "-y", "title": "Nguồn"},
                    "y": {"field": "count", "type": "quantitative", "title": "Số bằng chứng"},
                    "tooltip": [
                        {"field": "source", "type": "nominal"},
                        {"field": "count", "type": "quantitative"},
                    ],
                },
            },
        }
    ]

    summary = (
        verification_matrix_payload.get("summary")
        if isinstance(verification_matrix_payload.get("summary"), dict)
        else {}
    )
    support_values = [
        {
            "status": "supported",
            "count": _safe_int(summary.get("supported_claims"), 0),
        },
        {
            "status": "unsupported",
            "count": _safe_int(summary.get("unsupported_claims"), 0),
        },
        {
            "status": "contradicted",
            "count": _safe_int(summary.get("contradicted_claims"), 0),
        },
    ]
    chart_specs.append(
        {
            "id": "claim_support_matrix",
            "type": "chart-spec",
            "engine": "vega-lite",
            "title": "Ma trận mức độ hậu thuẫn claim",
            "config": {
                "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                "description": "Claim support profile from verification matrix.",
                "data": {"values": support_values},
                "mark": "arc",
                "encoding": {
                    "theta": {"field": "count", "type": "quantitative"},
                    "color": {"field": "status", "type": "nominal"},
                    "tooltip": [
                        {"field": "status", "type": "nominal"},
                        {"field": "count", "type": "quantitative"},
                    ],
                },
            },
        }
    )
    return chart_specs


def _build_visual_assets(citations: list[Citation]) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    for index, citation in enumerate(citations[:12], start=1):
        url = _safe_url(citation.url)
        if not url:
            continue
        assets.append(
            {
                "asset_id": f"citation-asset-{index}",
                "type": "reference_url",
                "source_id": citation.source_id,
                "source": citation.source,
                "title": citation.title,
                "url": url,
                "label": f"Nguồn {index}",
            }
        )
    return assets


def _build_reasoning_digest(
    *,
    topic: str,
    research_mode: str,
    planner_hints: dict[str, Any],
    answer_markdown: str,
    citations: list[Citation],
    verification_matrix_payload: dict[str, Any],
    flow_events: list[dict[str, Any]],
    deep_pass_count: int,
    parallel_reasoning_nodes: list[dict[str, Any]] | None = None,
    evidence_verification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = (
        verification_matrix_payload.get("summary")
        if isinstance(verification_matrix_payload.get("summary"), dict)
        else {}
    )
    contradiction_summary = (
        verification_matrix_payload.get("contradiction_summary")
        if isinstance(verification_matrix_payload.get("contradiction_summary"), dict)
        else {}
    )
    sources = [citation.source for citation in citations if citation.source]
    top_sources: list[str] = []
    for source in sources:
        if source in top_sources:
            continue
        top_sources.append(source)
        if len(top_sources) >= 4:
            break

    llm_status = "disabled"
    reason_codes = (
        planner_hints.get("reason_codes") if isinstance(planner_hints.get("reason_codes"), list) else []
    )
    if "llm_query_planner_enabled" in reason_codes:
        llm_status = "enabled"
    elif "llm_query_planner_fallback" in reason_codes:
        llm_status = "fallback"

    node_rows = parallel_reasoning_nodes if isinstance(parallel_reasoning_nodes, list) else []
    reasoning_chain_count = sum(
        len(item.get("reasoning_chain", []))
        for item in node_rows
        if isinstance(item, dict) and isinstance(item.get("reasoning_chain"), list)
    )
    completed_nodes = sum(
        1
        for item in node_rows
        if isinstance(item, dict) and str(item.get("status") or "").strip().lower() == "completed"
    )
    evidence_verification_payload = (
        evidence_verification if isinstance(evidence_verification, dict) else {}
    )

    return {
        "topic": topic,
        "research_mode": research_mode,
        "llm_query_planner_status": llm_status,
        "highlights": _extract_answer_digest_points(answer_markdown, limit=3),
        "evidence": {
            "citation_count": len(citations),
            "top_sources": top_sources,
            "deep_pass_count": max(1, int(deep_pass_count)),
            "parallel_reasoning_nodes": len(node_rows),
            "parallel_reasoning_nodes_completed": completed_nodes,
            "reasoning_chain_items": reasoning_chain_count,
            "evidence_verification_confidence": _safe_float(
                evidence_verification_payload.get("verification_confidence"),
                0.0,
            ),
            "evidence_verification_gaps": (
                len(evidence_verification_payload.get("evidence_gaps", []))
                if isinstance(evidence_verification_payload.get("evidence_gaps"), list)
                else 0
            ),
        },
        "verification": {
            "support_ratio": _safe_float(summary.get("support_ratio"), 0.0),
            "supported_claims": _safe_int(summary.get("supported_claims"), 0),
            "total_claims": _safe_int(summary.get("total_claims"), 0),
            "contradiction_count": _safe_int(contradiction_summary.get("contradiction_count"), 0),
        },
        "event_count": len(flow_events),
    }


def _build_research_plan_markdown(
    topic: str,
    plan_steps: list[PlanStep],
    *,
    answer_language: str = "vi",
) -> str:
    answer_language = "en" if str(answer_language or "").strip().lower() == "en" else "vi"
    topic_text = _compact_snippet(topic, max_len=240)

    def _clean_plan_line(value: str) -> str:
        text = str(value or "").strip()
        text = re.sub(r"^\s*\[[^\]]+\]\s*", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    if _is_nutrition_diet_query(topic) and _is_comparison_query(topic):
        if answer_language == "en":
            return (
                "1. Define the core principles, signature food groups, and health goals of the DASH diet.\n"
                "2. Define the core principles, signature food groups, and health goals of the Mediterranean diet.\n"
                "3. Summarize DASH advantages: blood pressure control, structured meal design, and guideline-aligned standardization.\n"
                "4. Summarize DASH limitations: adherence burden, stricter sodium or portion tracking, and long-term drop-off risk.\n"
                "5. Summarize Mediterranean diet advantages: long-term cardiovascular benefit, flexibility, healthy-fat quality, and behavioral sustainability.\n"
                "6. Summarize Mediterranean diet limitations: looser quantification, excess calorie risk, ingredient cost, and access barriers.\n"
                "7. Compare both options directly across four axes:\n"
                "   - (a) Real-world adherence in daily life.\n"
                "   - (b) Prevention and supportive-treatment effects for cardiovascular and metabolic disease.\n"
                "   - (c) Nutritional emphasis: sodium control versus optimization of healthy fats.\n"
                "   - (d) Implementation feasibility given cost, food culture, and ingredient availability."
            )
        return (
            "1. Xác định nguyên tắc cốt lõi, nhóm thực phẩm chủ đạo và mục tiêu sức khỏe của chế độ ăn DASH.\n"
            "2. Xác định nguyên tắc cốt lõi, nhóm thực phẩm chủ đạo và mục tiêu sức khỏe của chế độ ăn Địa Trung Hải.\n"
            "3. Tổng hợp ưu điểm DASH: hiệu quả kiểm soát huyết áp, tính cấu trúc khẩu phần, khả năng chuẩn hóa theo guideline.\n"
            "4. Tổng hợp hạn chế DASH: gánh nặng tuân thủ, mức độ khắt khe khi theo dõi natri/khẩu phần, rủi ro bỏ cuộc dài hạn.\n"
            "5. Tổng hợp ưu điểm Địa Trung Hải: lợi ích tim mạch dài hạn, tính linh hoạt, chất lượng chất béo và tính bền vững hành vi.\n"
            "6. Tổng hợp hạn chế Địa Trung Hải: định lượng kém chặt, nguy cơ tăng năng lượng nạp, chi phí nguyên liệu và khả năng tiếp cận.\n"
            "7. So sánh trực tiếp theo bốn trục:\n"
            "   - (a) Tính dễ tuân thủ trong đời sống hằng ngày.\n"
            "   - (b) Hiệu quả phòng ngừa và hỗ trợ điều trị bệnh lý tim mạch/chuyển hóa.\n"
            "   - (c) Khác biệt trọng tâm dinh dưỡng: kiểm soát natri so với tối ưu hóa chất béo lành mạnh.\n"
            "   - (d) Tính khả thi triển khai theo bối cảnh chi phí, văn hóa ăn uống và nguồn thực phẩm."
        )
    rows: list[str] = []
    for index, step in enumerate(plan_steps, start=1):
        objective = _compact_snippet(_clean_plan_line(step.objective), max_len=220)
        output = _compact_snippet(_clean_plan_line(step.output), max_len=180)
        if answer_language == "en":
            rows.append(f"{index}. {objective} Expected output: {output}.")
        else:
            rows.append(f"{index}. {objective} Kết quả kỳ vọng: {output}.")
        if len(rows) >= 8:
            break
    if not rows:
        rows = (
            [
                f"1. Define the central question: {topic_text}.",
                "2. Retrieve across multiple sources with priority on guidelines, systematic reviews, and clinical trials.",
                "3. Compare supporting versus conflicting evidence and turn it into practical recommendations.",
            ]
            if answer_language == "en"
            else [
                f"1. Xác định câu hỏi trung tâm: {topic_text}.",
                "2. Truy xuất đa nguồn ưu tiên guideline, tổng quan hệ thống và thử nghiệm lâm sàng.",
                "3. So sánh bằng chứng thuận chiều/ngược chiều và tổng hợp khuyến nghị ứng dụng.",
            ]
        )
    return "\n".join(rows)


def _inject_research_plan_section(
    markdown_text: str,
    *,
    plan_markdown: str,
    answer_language: str = "vi",
) -> str:
    text = str(markdown_text or "").strip()
    research_plan_heading = f"## {_resolve_section_title('research_plan', answer_language)}"
    quick_conclusion_heading = _resolve_section_title("quick_conclusion", answer_language)
    if not text:
        return f"{research_plan_heading}\n{plan_markdown}\n"
    if _has_markdown_heading(text, research_plan_heading):
        return text
    insertion = f"\n\n{research_plan_heading}\n{plan_markdown}\n\n"
    pattern = re.compile(
        rf"(##\s*{re.escape(quick_conclusion_heading)}[\s\S]*?)(\n##\s)",
        flags=re.IGNORECASE,
    )
    if pattern.search(text):
        return pattern.sub(lambda m: f"{m.group(1)}{insertion}{m.group(2)}", text, count=1).strip()
    return f"{research_plan_heading}\n{plan_markdown}\n\n{text}".strip()


def _sentence_split_for_overlap(text: str) -> list[str]:
    """Split prose into trimmed sentences for overlap detection (pure helper)."""

    parts = re.split(r"(?<=[.!?。])\s+|\n+", str(text or ""))
    return [p.strip() for p in parts if p.strip()]


def _strip_leading_overlap(body: str, already_shown: str) -> str:
    """Drop sentences from the start of ``body`` that were already shown.

    The deep/deep_beta fallback layout excerpts the quick conclusion and the key
    points from the SAME source text, so the key-points block tended to repeat
    the conclusion's opening sentences verbatim. This removes that leading
    overlap (case/space-insensitive) so key points add new detail instead of
    echoing the conclusion. Pure and language-agnostic.
    """

    shown = {
        re.sub(r"\s+", " ", s).strip().lower()
        for s in _sentence_split_for_overlap(already_shown)
    }
    if not shown:
        return body.strip()
    kept: list[str] = []
    dropping = True
    for sentence in _sentence_split_for_overlap(body):
        key = re.sub(r"\s+", " ", sentence).strip().lower()
        if dropping and key in shown:
            continue
        dropping = False
        kept.append(sentence)
    return " ".join(kept).strip()


def _ensure_markdown_structure(
    topic: str,
    answer: str,
    citations: list[Citation],
    *,
    research_mode: str,
    plan_steps: list[PlanStep] | None = None,
    answer_language: str = "vi",
) -> str:
    answer_language = "en" if str(answer_language or "").strip().lower() == "en" else "vi"

    def _cleanup_markdown_noise(text: str) -> str:
        lines = str(text or "").splitlines()
        cleaned_lines: list[str] = []
        prev_key = ""
        # Track substantial prose lines already emitted anywhere in the answer so
        # a paragraph echoed across sections (the deep_beta "repeat to fill"
        # artifact) is dropped, not just adjacent duplicates. Short lines,
        # headings, table rows, and list markers are exempt so legitimately
        # repeated bullets/labels are preserved.
        seen_prose: set[str] = set()
        for raw in lines:
            line = raw.rstrip()
            normalized = re.sub(r"\s+", " ", line).strip().lower()
            if not normalized and cleaned_lines and cleaned_lines[-1] == "":
                continue
            if normalized and normalized == prev_key:
                continue
            if normalized.startswith("- phạm vi nghiên cứu: ##") or normalized.startswith("phạm vi nghiên cứu: ##"):
                line = f"- Phạm vi nghiên cứu: {_compact_snippet(topic, max_len=150)} và bằng chứng truy xuất đa nguồn."
                normalized = re.sub(r"\s+", " ", line).strip().lower()
            # Global de-duplication of substantial prose paragraphs: a long,
            # non-heading, non-table, non-bullet line that exactly repeats an
            # earlier one is an echo artifact and is skipped.
            is_structural = (
                line.lstrip().startswith("#")
                or line.lstrip().startswith("|")
                or line.lstrip().startswith("-")
                or line.lstrip().startswith("*")
                or line.lstrip().startswith(">")
                or line.lstrip().startswith("```")
            )
            if not is_structural and len(normalized) >= 60:
                if normalized in seen_prose:
                    continue
                seen_prose.add(normalized)
            cleaned_lines.append(line)
            prev_key = normalized
        return "\n".join(cleaned_lines).strip()

    def _compact_plain_summary(text: str, *, max_len: int) -> str:
        cleaned_lines: list[str] = []
        for raw_line in str(text or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#"):
                continue
            if line.startswith("|"):
                continue
            if line.startswith("```"):
                continue
            line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
            line = re.sub(r"`([^`]+)`", r"\1", line)
            line = re.sub(r"\[[^\]]+\]\((https?:\/\/[^\)]+)\)", "", line)
            line = re.sub(r"\s+", " ", line).strip(" -•\t")
            if line:
                cleaned_lines.append(line)
            if len(" ".join(cleaned_lines)) >= max_len:
                break
        if not cleaned_lines:
            return _compact_snippet(text, max_len=max_len)
        return _compact_snippet(" ".join(cleaned_lines), max_len=max_len)

    def _estimate_medical_risk_band(
        text: str,
        *,
        answer_language: str = "vi",
    ) -> tuple[str, str, str]:
        language = "en" if str(answer_language or "").strip().lower() == "en" else "vi"
        normalized = _ascii_fold(text)
        high_terms = (
            "warfarin",
            "xuất huyết",
            "bleeding",
            "shock",
            "sốc",
            "phản vệ",
            "anaphylaxis",
            "khó thở",
            "đau ngực",
            "ngất",
        )
        moderate_terms = (
            "ddi",
            "tương tác thuốc",
            "ibuprofen",
            "aspirin",
            "kháng viêm",
            "nsaid",
            "suy thận",
            "suy gan",
            "đái tháo đường",
            "tim mạch",
        )
        if any(term in normalized for term in high_terms):
            if language == "en":
                return ("High", "Red", "Prompt action and in-person medical evaluation are warranted.")
            return ("Cao", "Đỏ", "Cần xử trí sớm và đánh giá y tế trực tiếp.")
        if any(term in normalized for term in moderate_terms):
            if language == "en":
                return ("Moderate", "Orange", "Close monitoring and clinician or pharmacist confirmation are warranted.")
            return ("Trung bình", "Cam", "Cần theo dõi sát và xác minh với bác sĩ/dược sĩ.")
        if language == "en":
            return ("Low", "Yellow", "Routine follow-up is reasonable while continuing to verify primary sources.")
        return ("Thấp", "Vàng", "Theo dõi định kỳ, tiếp tục kiểm chứng nguồn chính thống.")

    def _build_decision_matrix_markdown(*, risk_level: str, risk_signal: str) -> str:
        return (
            "| Mục đánh giá | Mức hiện tại | Hành động khuyến nghị |\n"
            "| --- | --- | --- |\n"
            f"| Mức rủi ro tổng quát | {risk_level} ({risk_signal}) | Không tự điều chỉnh thuốc, xác minh với bác sĩ/dược sĩ. |\n"
            "| Độ tin cậy bằng chứng | Trung bình - Cao (tùy nguồn) | Ưu tiên guideline, nhãn thuốc chính thức, và dữ liệu DDI có trích dẫn. |\n"
            "| Quyết định tại nhà | Có điều kiện | Chỉ tiếp tục dùng thuốc khi không có dấu hiệu cảnh báo đỏ. |\n"
            "| Cần chuyển tuyến ngay | Khi có red flag | Đau ngực, khó thở, ngất, xuất huyết, lú lẫn, phản vệ. |\n"
        )

    cleaned = str(answer or "").strip()
    if not cleaned:
        cleaned = (
            "No in-depth answer content was generated yet."
            if answer_language == "en"
            else "Chưa có nội dung trả lời chuyên sâu."
        )

    quick_conclusion_heading = f"## {_resolve_section_title('quick_conclusion', answer_language)}"
    key_points_heading = f"## {_resolve_section_title('key_points', answer_language)}"
    practical_heading = f"## {_resolve_section_title('practical_application', answer_language)}"
    caveat_heading = f"## {_resolve_section_title('safety_notes', answer_language)}"

    required_headings = (
        (quick_conclusion_heading, key_points_heading, practical_heading, caveat_heading)
        if research_mode == "deep_beta"
        else (
            (quick_conclusion_heading, key_points_heading)
            if research_mode == "deep"
            else (quick_conclusion_heading, key_points_heading, practical_heading, caveat_heading)
        )
    )
    plan_markdown = _build_research_plan_markdown(
        topic,
        plan_steps or [],
        answer_language=answer_language,
    )
    if all(_has_markdown_heading(cleaned, heading) for heading in required_headings):
        # The execution plan remains available in structured metadata for
        # transparency/debugging. Do not inject internal planner boilerplate into
        # an already complete reader-facing report.
        return _cleanup_markdown_noise(cleaned)

    analysis_block = cleaned
    if "\n" not in analysis_block:
        analysis_block = f"- {analysis_block}"

    risk_level, risk_signal, risk_note = _estimate_medical_risk_band(
        f"{topic} {cleaned}",
        answer_language=answer_language,
    )
    if research_mode in {"deep", "deep_beta"}:
        key_points_heading = f"## {_resolve_section_title('key_points', answer_language)}"
        practical_heading = f"## {_resolve_section_title('practical_application', answer_language)}"
        caveat_heading = f"## {_resolve_section_title('safety_notes', answer_language)}"
        # Plan steps are authored in English internally. Surface them only in the
        # English answer; the Vietnamese branch uses clean Vietnamese guidance so
        # the internal English plan text never leaks into a Vietnamese answer
        # (the mixed VN/EN artifact).
        plan_summary = _compact_plain_summary(plan_markdown, max_len=220)
        # The quick-conclusion section is a sentence excerpt taken from the START
        # of ``cleaned``. If key points also excerpt from the start, the opening
        # sentences echo across both sections. Build the conclusion first, then
        # drop that leading text so key points continue from where the
        # conclusion left off (adds detail instead of repeating it).
        conclusion_excerpt = _curate_sentence_excerpt(
            cleaned,
            max_len=560 if research_mode == "deep_beta" else 420,
            max_sentences=5 if research_mode == "deep_beta" else 4,
        )
        # Only strip the conclusion overlap when enough distinct content remains
        # afterwards; otherwise an over-eager strip on a thin base answer empties
        # the key-points section entirely (worse than mild overlap). The global
        # line-level de-dup in ``_cleanup_markdown_noise`` still removes any exact
        # repeated paragraph that survives.
        analysis_remainder = _strip_leading_overlap(analysis_block, conclusion_excerpt)
        if len(analysis_remainder.strip()) < 120:
            analysis_remainder = analysis_block
        main_excerpt = _curate_markdown_excerpt(
            analysis_remainder,
            max_len=2200 if research_mode == "deep_beta" else 1600,
            max_lines=12 if research_mode == "deep_beta" else 9,
        )
        deep_comparison_table = ""
        if _is_comparison_query(topic):
            if answer_language == "en":
                deep_comparison_table = (
                    "\n\n| Criteria | Option A | Option B | Clinical note |\n"
                    "| --- | --- | --- | --- |\n"
                    "| Primary goal | Tighter control of the immediate target | Broader long-term cardiometabolic benefit | Match to the main treatment objective |\n"
                    "| Ease of adherence | More structured, often easier to standardize | More flexible, often easier to sustain | Re-check after 2-4 weeks in real life |\n"
                    "| Safety / burden | May require closer monitoring or stricter discipline | Can be easier to live with, but less tightly defined | Balance safety with feasibility |\n"
                )
            else:
                deep_comparison_table = (
                    "\n\n| Tiêu chí | Phương án A | Phương án B | Ghi chú lâm sàng |\n"
                    "| --- | --- | --- | --- |\n"
                    "| Mục tiêu chính | Kiểm soát chặt chỉ số đích trước mắt | Lợi ích tim mạch - chuyển hóa dài hạn | Chọn theo mục tiêu điều trị ưu tiên |\n"
                    "| Khả năng tuân thủ | Cấu trúc rõ hơn, dễ chuẩn hóa hơn | Linh hoạt hơn, dễ duy trì dài hạn hơn | Đánh giá lại sau 2-4 tuần áp dụng thực tế |\n"
                    "| Gánh nặng an toàn | Có thể cần theo dõi sát hoặc kỷ luật hơn | Dễ sống chung hơn nhưng ít chặt chẽ hơn | Cân bằng an toàn với tính khả thi |\n"
                )

        reader_facing_main = _normalize_reader_facing_block(
            # Key points must NOT re-summarize the conclusion: the quick-conclusion
            # section already carries the executive summary of ``cleaned``. Feeding
            # ``executive_summary`` in here again is what produced the paragraph
            # echoed across ``Kết luận nhanh`` and ``Điểm chính``. Use the curated
            # analysis excerpt only so key points add detail rather than repeat.
            main_excerpt,
            max_items=6 if research_mode == "deep_beta" else 5,
            max_len=1900 if research_mode == "deep_beta" else 1300,
            prefer_paragraphs=True,
        )

        if answer_language == "en":
            practical_block = (
                "- Most useful when the patient context matches the scenario above and the decision is between reasonable options rather than a single mandatory path.\n"
                "- Before acting, confirm comorbidities, current medicines, baseline risk, and whether any red-flag symptoms are already present.\n"
                f"- Best next step: {plan_summary or 'confirm the main clinical question, compare the core options, and verify the highest-impact risk trade-offs before acting.'}"
            )
            caveat_block = (
                f"- Confidence boundary: {risk_level} ({risk_signal}). {risk_note}\n"
                f"- Evidence quality still varies across settings and populations despite {len(citations)} cited source(s).\n"
                "- Escalate urgently for chest pain, shortness of breath, syncope, bleeding, rapidly worsening symptoms, or anaphylaxis."
            )
        else:
            practical_block = (
                "- Phù hợp nhất khi bối cảnh người bệnh gần với tình huống đang phân tích và quyết định nằm ở chỗ chọn giữa vài hướng hợp lý, không phải một đáp án cứng duy nhất.\n"
                "- Trước khi áp dụng, cần đối chiếu lại bệnh nền, thuốc đang dùng, mức nguy cơ nền và xem đã có dấu hiệu cảnh báo đỏ hay chưa.\n"
                "- Bước tiếp theo nên làm: chốt lại câu hỏi lâm sàng chính, so sánh các lựa chọn cốt lõi và xác minh các đánh đổi có ảnh hưởng lớn nhất trước khi hành động."
            )
            caveat_block = (
                f"- Ranh giới độ chắc chắn: {risk_level} ({risk_signal}). {risk_note}\n"
                f"- Dù đã có {len(citations)} nguồn trích dẫn, chất lượng và mức độ áp dụng trực tiếp vẫn có thể khác nhau theo quần thể và bối cảnh.\n"
                "- Cần đi cấp cứu ngay nếu có đau ngực, khó thở, ngất, xuất huyết, triệu chứng nặng lên nhanh hoặc phản vệ."
            )

        key_points_block = f"{reader_facing_main}{deep_comparison_table}"

        return _cleanup_markdown_noise(
            f"{quick_conclusion_heading}\n"
            f"{conclusion_excerpt}\n\n"
            f"{key_points_heading}\n"
            f"{key_points_block}\n\n"
            f"{practical_heading}\n"
            f"{practical_block}\n\n"
            f"{caveat_heading}\n"
            f"{caveat_block}"
        )

    fast_summary = _compact_plain_summary(cleaned, max_len=420)
    fast_analysis = _curate_markdown_excerpt(
        cleaned,
        max_len=1450,
        max_lines=8,
    )
    fast_practical = (
        "- Match the answer to the clinical question, treatment goal, comorbidity profile, and concurrent medicines.\n"
        "- Use the next step to confirm the highest-impact trade-off, then document what needs monitoring."
        if answer_language == "en"
        else "- Gắn kết luận với câu hỏi lâm sàng, mục tiêu điều trị, bệnh nền và các thuốc đang dùng.\n"
        "- Ở bước tiếp theo, hãy xác minh điểm đánh đổi quan trọng nhất rồi ghi rõ cần theo dõi gì."
    )
    fast_caveats = (
        "- Cross-check with primary sources before changing care decisions.\n"
        "- Seek urgent care now for chest pain, shortness of breath, syncope, bleeding, or anaphylaxis."
        if answer_language == "en"
        else "- Ưu tiên đối chiếu nguồn chính thống trước khi thay đổi quyết định chăm sóc.\n"
        "- Cần đi khám/cấp cứu ngay nếu có đau ngực, khó thở, ngất, xuất huyết hoặc phản vệ."
    )
    comparison_table = ""
    if _is_comparison_query(topic):
        comparison_table = (
            "\n\n| Criteria | Option A | Option B | Note |\n"
            "| --- | --- | --- | --- |\n"
            "| Primary goal | Tighter short-term target control | Broader long-term cardiometabolic benefit | Choose by treatment priority |\n"
            "| Real-world adherence | More structured and standardized | More flexible and often easier to sustain | Re-check after 2-4 weeks |\n"
            "| Safety / burden | May need closer discipline or monitoring | Usually easier to live with but less tightly defined | Balance safety with feasibility |\n"
            if answer_language == "en"
            else "\n\n| Tiêu chí | Phương án A | Phương án B | Ghi chú |\n"
            "| --- | --- | --- | --- |\n"
            "| Mục tiêu chính | Kiểm soát chặt mục tiêu ngắn hạn | Lợi ích tim mạch - chuyển hóa dài hạn | Chọn theo ưu tiên điều trị |\n"
            "| Khả năng tuân thủ thực tế | Cấu trúc rõ và dễ chuẩn hóa hơn | Linh hoạt hơn, thường dễ duy trì hơn | Đánh giá lại sau 2-4 tuần |\n"
            "| Gánh nặng an toàn | Có thể cần theo dõi hoặc kỷ luật chặt hơn | Dễ sống chung hơn nhưng ít chặt chẽ hơn | Cân bằng an toàn với tính khả thi |\n"
        )

    return _cleanup_markdown_noise(
        f"{quick_conclusion_heading}\n"
        f"{fast_summary or cleaned}\n\n"
        f"{key_points_heading}\n"
        f"{fast_analysis or analysis_block}{comparison_table}\n\n"
        f"{practical_heading}\n"
        f"{fast_practical}\n\n"
        f"{caveat_heading}\n"
        f"{fast_caveats}"
    )


def _remove_h2_sections(markdown_text: str, *, section_heading_keys: set[str]) -> str:
    text = str(markdown_text or "")
    if not text.strip() or not section_heading_keys:
        return text

    lines = text.splitlines()
    output_lines: list[str] = []
    skipping = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            heading_key = _canonical_h2_key(stripped[3:])
            skipping = heading_key in section_heading_keys
            if skipping:
                continue
        if not skipping:
            output_lines.append(line)

    normalized = "\n".join(output_lines)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _remove_fenced_blocks(markdown_text: str, *, languages: set[str]) -> str:
    if not languages:
        return str(markdown_text or "")
    pattern = re.compile(r"```([a-zA-Z0-9_-]+)?\s*\n.*?```", flags=re.DOTALL)

    def _replace(match: re.Match[str]) -> str:
        language = str(match.group(1) or "").strip().lower()
        if language in languages:
            return ""
        return match.group(0)

    stripped = pattern.sub(_replace, str(markdown_text or ""))
    stripped = re.sub(r"\n{3,}", "\n\n", stripped)
    return stripped.strip()


_FAST_ALLOWED_H2_KEYS = {
    _canonical_h2_key("Kết luận nhanh"),
    _canonical_h2_key("Điểm chính"),
    _canonical_h2_key("Ứng dụng thực tế"),
    _canonical_h2_key("Lưu ý an toàn"),
    _canonical_h2_key("Phân tích chi tiết"),
    _canonical_h2_key("Khuyến nghị an toàn"),
    _canonical_h2_key("Theo dõi & cảnh báo đỏ"),
    _canonical_h2_key("Quick conclusion"),
    _canonical_h2_key("Key points"),
    _canonical_h2_key("Practical application"),
    _canonical_h2_key("Important caveats"),
    _canonical_h2_key("Detailed analysis"),
    _canonical_h2_key("Safety recommendations"),
    _canonical_h2_key("Monitoring & red flags"),
}

_FAST_DROP_H2_KEYWORDS = (
    "tom tat dieu hanh",
    "ke hoach nghien cuu",
    "cau hoi nghien cuu pico",
    "phuong phap truy xuat",
    "ho so bang chung",
    "tong hop phat hien",
    "chuoi lap luan bang chung",
    "phan bien bang chung",
    "ung dung lam sang",
    "ma tran quyet dinh an toan",
    "ke hoach theo doi sau tu van",
    "gioi han sai so va rui ro phap ly",
    "bang tong hop bang chung",
    "nguon tham chieu",
)


def _remove_unapproved_fast_h2_sections(markdown_text: str) -> str:
    text = str(markdown_text or "")
    if not text.strip():
        return text
    lines = text.splitlines()
    output_lines: list[str] = []
    keep_current = True
    saw_first_h2 = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            saw_first_h2 = True
            key = _canonical_h2_key(stripped[3:])
            is_drop_keyword = any(keyword in key for keyword in _FAST_DROP_H2_KEYWORDS)
            keep_current = (key in _FAST_ALLOWED_H2_KEYS) and not is_drop_keyword
            if keep_current:
                output_lines.append(line)
            continue
        if not saw_first_h2:
            # Drop preamble noise in fast mode to keep body concise.
            continue
        if keep_current:
            output_lines.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(output_lines)).strip()


def _remove_h3_sections_by_heading_keys(markdown_text: str, *, heading_keys: set[str]) -> str:
    text = str(markdown_text or "")
    if not text.strip() or not heading_keys:
        return text

    lines = text.splitlines()
    output_lines: list[str] = []
    skipping = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("### "):
            heading_key = _canonical_h2_key(stripped[4:])
            skipping = heading_key in heading_keys
            if skipping:
                continue
        elif stripped.startswith("## ") or stripped.startswith("# "):
            skipping = False

        if not skipping:
            output_lines.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(output_lines)).strip()


def _extract_h2_body(markdown_text: str, heading_key: str) -> str:
    lines = str(markdown_text or "").splitlines()
    target_body: list[str] = []
    collecting = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            key = _canonical_h2_key(stripped[3:])
            if collecting:
                break
            collecting = key == heading_key
            continue
        if collecting:
            target_body.append(line)
    body = "\n".join(target_body).strip()
    return body


def _to_plain_text(markdown_text: str) -> str:
    text = str(markdown_text or "")
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"^#+\s+.*$", " ", text, flags=re.MULTILINE)
    text = re.sub(r"^\|.*$", " ", text, flags=re.MULTILINE)
    text = re.sub(r"\[[^\]]+\]\((https?:\/\/[^\)]+)\)", " ", text)
    text = re.sub(r"[*_`>#-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_h2_body_any(markdown_text: str, headings: list[str]) -> str:
    for heading in headings:
        body = _extract_h2_body(markdown_text, _canonical_h2_key(heading))
        if body:
            return body
    return ""


def _curate_sentence_excerpt(markdown_text: str, *, max_len: int, max_sentences: int = 3) -> str:
    plain = _to_plain_text(markdown_text)
    if not plain:
        return ""
    sentences = re.split(r"(?<=[\.\!\?])\s+", plain)
    curated: list[str] = []
    current_len = 0
    for sentence in sentences:
        normalized = sentence.strip()
        if not normalized:
            continue
        if current_len and current_len + len(normalized) + 1 > max_len:
            break
        curated.append(normalized)
        current_len += len(normalized) + 1
        if len(curated) >= max_sentences or current_len >= max_len:
            break
    if curated:
        return " ".join(curated).strip()
    return _compact_snippet(plain, max_len=max_len)


def _extract_markdown_h2_section_ids(markdown_text: str) -> list[str]:
    section_ids: list[str] = []
    seen: set[str] = set()
    for raw_line in str(markdown_text or "").splitlines():
        line = raw_line.strip()
        if not line.startswith("## "):
            continue
        section_id = _USER_FACING_HEADING_ALIASES.get(_canonical_h2_key(line[3:]))
        if not section_id or section_id in seen:
            continue
        seen.add(section_id)
        section_ids.append(section_id)
    return section_ids


def _approved_user_facing_section_ids(research_mode: str) -> set[str]:
    mode = str(research_mode or "fast").strip().lower()
    base_sections = {
        "quick_conclusion",
        "key_points",
        "practical_application",
        "safety_notes",
        "monitoring_red_flags",
    }
    if mode == "fast":
        return base_sections
    # Deep/Deep Beta can expose richer sections for long-form analysis.
    return {
        *base_sections,
        "detailed_analysis",
        "safety_guidance",
        "research_plan",
        "executive_summary",
        "clinical_context",
        "practice_recommendations",
        "limitations_legal",
    }


def _find_unapproved_h2_sections(markdown_text: str, *, research_mode: str) -> list[str]:
    approved = _approved_user_facing_section_ids(research_mode)
    unexpected: list[str] = []
    for raw_line in str(markdown_text or "").splitlines():
        line = raw_line.strip()
        if not line.startswith("## "):
            continue
        heading_key = _canonical_h2_key(line[3:])
        section_id = _USER_FACING_HEADING_ALIASES.get(heading_key)
        if section_id and section_id in approved:
            continue
        unexpected.append(section_id or heading_key or line[3:].strip())
    return unexpected


def _drop_unapproved_h2_sections(markdown_text: str, *, research_mode: str) -> str:
    text = str(markdown_text or "").strip()
    if not text:
        return text

    approved = _approved_user_facing_section_ids(research_mode)
    output_lines: list[str] = []
    keeping_block = True
    seen_h2 = False

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith("## "):
            seen_h2 = True
            heading_key = _canonical_h2_key(stripped[3:])
            section_id = _USER_FACING_HEADING_ALIASES.get(heading_key)
            keeping_block = bool(section_id and section_id in approved)
            if not keeping_block:
                continue
        if keeping_block or not seen_h2:
            output_lines.append(line)

    normalized = "\n".join(output_lines)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _has_reader_friendly_layout(markdown_text: str, *, research_mode: str) -> bool:
    section_ids = set(_extract_markdown_h2_section_ids(markdown_text))
    mode = str(research_mode).strip().lower()
    if mode == "fast":
        if _find_unapproved_h2_sections(markdown_text, research_mode=research_mode):
            return False
        return (
            "quick_conclusion" in section_ids
            and "key_points" in section_ids
            and "practical_application" in section_ids
            and "safety_notes" in section_ids
        )
    # Deep modes tolerate extra sections as long as core structure exists.
    return (
        "quick_conclusion" in section_ids
        and "key_points" in section_ids
        and bool({"safety_notes", "safety_guidance", "monitoring_red_flags"} & section_ids)
    )


def _has_preservable_long_form_layout(markdown_text: str, *, research_mode: str) -> bool:
    mode = str(research_mode or "fast").strip().lower()
    if mode not in {"deep", "deep_beta"}:
        return False

    section_ids = set(_extract_markdown_h2_section_ids(markdown_text))
    if len(section_ids) >= 5:
        return True

    long_form_sections = {
        "research_plan",
        "executive_summary",
        "detailed_analysis",
        "clinical_context",
        "practice_recommendations",
        "limitations_legal",
    }
    return len(section_ids) >= 4 and len(section_ids & long_form_sections) >= 2


_ENGLISH_BODY_MARKERS = (
    " the ",
    " and ",
    " with ",
    " patient ",
    " treatment ",
    " clinical ",
    " evidence ",
    " safety ",
    " monitor ",
)
_VIETNAMESE_BODY_MARKERS = (
    " benh ",
    " thuoc ",
    " can ",
    " khong ",
    " nguoi ",
    " dieu tri ",
    " theo doi ",
    " canh bao ",
    " khuyen nghi ",
)


def _looks_language_misaligned(markdown_text: str, *, answer_language: str) -> bool:
    plain = f" {_ascii_fold(_to_plain_text(markdown_text))} "
    if not plain.strip():
        return False
    english_hits = sum(1 for marker in _ENGLISH_BODY_MARKERS if marker in plain)
    vietnamese_hits = sum(1 for marker in _VIETNAMESE_BODY_MARKERS if marker in plain)
    if answer_language == "en":
        return vietnamese_hits >= 3 and english_hits <= 2
    return english_hits >= 4 and vietnamese_hits <= 2


def _stabilize_fast_answer_layout(markdown_text: str, *, answer_language: str = "vi") -> str:
    text = str(markdown_text or "").strip()
    if not text:
        text = (
            "The analysis was compacted temporarily to keep the answer stable."
            if answer_language == "en"
            else "Nội dung phân tích tạm thời rút gọn để giữ an toàn hiển thị."
        )

    conclusion_heading = _resolve_section_title("quick_conclusion", answer_language)
    key_points_heading = _resolve_section_title("key_points", answer_language)
    practical_heading = _resolve_section_title("practical_application", answer_language)
    caveat_heading = _resolve_section_title("safety_notes", answer_language)
    followup_heading = _resolve_section_title("monitoring_red_flags", answer_language)

    conclusion = _extract_h2_body_any(text, [conclusion_heading, "Kết luận nhanh", "Quick conclusion"])
    analysis = _extract_h2_body_any(
        text,
        [key_points_heading, "Điểm chính", "Key points", "Phân tích chi tiết", "Detailed analysis"],
    )
    practical = _extract_h2_body_any(
        text,
        [practical_heading, "Ứng dụng thực tế", "Practical application", "Khuyến nghị an toàn", "Safety recommendations"],
    )
    safety = _extract_h2_body_any(
        text,
        [caveat_heading, "Lưu ý an toàn", "Important caveats"],
    )
    followup = _extract_h2_body_any(
        text,
        [
            followup_heading,
            "Theo dõi & cảnh báo đỏ",
            "Monitoring & red flags",
        ],
    )

    plain = _to_plain_text(text)
    if _looks_language_misaligned(conclusion, answer_language=answer_language):
        conclusion = ""
    if _looks_language_misaligned(analysis, answer_language=answer_language):
        analysis = ""
    if _looks_language_misaligned(practical, answer_language=answer_language):
        practical = ""
    if _looks_language_misaligned(safety, answer_language=answer_language):
        safety = ""
    if _looks_language_misaligned(followup, answer_language=answer_language):
        followup = ""
    if not conclusion:
        conclusion = (
            (
                "The safest reading from the current evidence is to stay cautious, confirm the core clinical context, and avoid overcommitting beyond what the retrieved evidence can support."
                if answer_language == "en"
                else "Tín hiệu an toàn nhất từ phần trả lời hiện tại là giữ kết luận ở mức thận trọng, xác minh lại bối cảnh lâm sàng chính và tránh diễn giải vượt quá bằng chứng đang có."
            )
            if _looks_language_misaligned(plain, answer_language=answer_language)
            else _curate_sentence_excerpt(
                plain,
                max_len=520,
                max_sentences=4,
            )
        )
    if not analysis:
        analysis = (
            (
                "The answer should be interpreted around treatment goal, comorbidities, active medications, and the main trade-off between expected benefit and safety burden."
                if answer_language == "en"
                else "Cần đọc kết luận theo mục tiêu điều trị, bệnh nền, các thuốc đang dùng và điểm đánh đổi chính giữa lợi ích kỳ vọng với gánh nặng an toàn."
            )
            if _looks_language_misaligned(plain, answer_language=answer_language)
            else _compact_snippet(
                plain,
                max_len=1750,
            )
        )
    if not practical:
        practical = (
            "- Apply the answer against the patient's treatment goal, comorbidities, and current medications.\n"
            "- Re-check the recommendation with a clinician or pharmacist before any concrete treatment change."
            if answer_language == "en"
            else "- Ghép kết luận với mục tiêu điều trị, bệnh nền và các thuốc đang dùng của người bệnh.\n"
            "- Khi cần thay đổi điều trị cụ thể, nên xác minh lại với bác sĩ hoặc dược sĩ."
        )
    if not safety:
        safety = ""
    if not followup:
        followup = (
            "- Do not self-prescribe or change dosing without qualified clinical advice.\n"
            "- Monitor symptoms over the next 24-48 hours and seek urgent care for chest pain, shortness of breath, syncope, bleeding, or anaphylaxis."
            if answer_language == "en"
            else "- Không tự ý kê đơn hoặc điều chỉnh liều khi chưa có tư vấn chuyên môn.\n"
            "- Theo dõi triệu chứng trong 24-48 giờ và cần cấp cứu ngay nếu có đau ngực, khó thở, ngất, xuất huyết hoặc phản vệ."
        )
    analysis = _normalize_reader_facing_block(
        analysis,
        max_items=6,
        max_len=1400,
        prefer_paragraphs=True,
    )
    practical = _ensure_scannable_markdown_block(
        practical,
        max_items=3,
        max_len=620,
    )
    followup = _ensure_scannable_markdown_block(
        followup,
        max_items=3,
        max_len=460,
    )
    safety = _ensure_scannable_markdown_block(
        "\n".join(part for part in [safety, followup] if part.strip()),
        max_items=4,
        max_len=560,
    )

    stabilized = (
        f"## {conclusion_heading}\n"
        f"{conclusion}\n\n"
        f"## {key_points_heading}\n"
        f"{analysis}\n\n"
        f"## {practical_heading}\n"
        f"{practical}\n\n"
        f"## {caveat_heading}\n"
        f"{safety}"
    )
    return re.sub(r"\n{3,}", "\n\n", stabilized).strip()


def _curate_markdown_excerpt(
    markdown_text: str,
    *,
    max_len: int,
    max_lines: int,
) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    current_len = 0
    for raw_line in str(markdown_text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#") or line.startswith("|") or line.startswith("```"):
            continue
        line = re.sub(r"\[(.*?)\]\((https?:\/\/[^\)]+)\)", r"\1", line)
        line = re.sub(r"`([^`]+)`", r"\1", line)
        line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
        line = re.sub(r"\s+", " ", line).strip()
        lowered = _ascii_fold(line)
        if not line:
            continue
        if any(
            token in lowered
            for token in (
                "duoi day la ngu canh da truy xuat",
                "he thong chuyen sang che do tong hop an toan",
                "fallback local",
                "query:",
                "telemetry",
                "verified protocol engine",
                "logic flow",
                "source intel",
                "claim verdict confidence",
                "pass subquery retrieved",
            )
        ):
            continue
        if re.match(r"^\d+[\)\.]\s*", line):
            line = re.sub(r"^(\d+)[\)\.]\s*", r"\1. ", line)
        elif re.match(r"^[\-*•]\s*", line):
            line = re.sub(r"^[\-*•]\s*", "- ", line)
        normalized = _ascii_fold(line)
        if normalized in seen:
            continue
        seen.add(normalized)
        remaining = max_len - current_len
        if remaining <= 0:
            break
        if len(line) > remaining:
            if not lines:
                lines.append(_compact_snippet(line, max_len=max(remaining, 80)))
            break
        lines.append(line)
        current_len += len(line) + 1
        if len(lines) >= max_lines or current_len >= max_len:
            break

    if not lines:
        return _compact_snippet(_to_plain_text(markdown_text), max_len=max_len)
    return "\n".join(lines).strip()


def _looks_like_scannable_block(markdown_text: str) -> bool:
    for raw_line in str(markdown_text or "").splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped.startswith("|"):
            return True
        if re.match(r"^(?:[-*•]|\d+\.)\s+", stripped):
            return True
    return False


def _sentence_bulletize(markdown_text: str, *, max_items: int, max_len: int) -> str:
    plain = _to_plain_text(markdown_text)
    if not plain:
        return ""
    sentences = re.split(r"(?<=[\.\!\?])\s+", plain)
    bullets: list[str] = []
    current_len = 0
    for sentence in sentences:
        normalized = sentence.strip(" -\t")
        if not normalized:
            continue
        bullet = f"- {normalized}"
        if current_len and current_len + len(bullet) + 1 > max_len:
            break
        bullets.append(bullet)
        current_len += len(bullet) + 1
        if len(bullets) >= max_items or current_len >= max_len:
            break
    return "\n".join(bullets).strip()


def _ensure_scannable_markdown_block(
    markdown_text: str,
    *,
    max_items: int,
    max_len: int,
) -> str:
    text = str(markdown_text or "").strip()
    if not text:
        return ""
    if _looks_like_scannable_block(text):
        return text
    bulletized = _sentence_bulletize(text, max_items=max_items, max_len=max_len)
    return bulletized or text


def _normalize_reader_facing_block(
    markdown_text: str,
    *,
    max_items: int,
    max_len: int,
    prefer_paragraphs: bool = False,
) -> str:
    text = str(markdown_text or "").strip()
    if not text:
        return ""
    if _looks_like_scannable_block(text):
        return text
    if prefer_paragraphs:
        return _curate_markdown_excerpt(
            text,
            max_len=max_len,
            max_lines=max(4, max_items + 2),
        )
    return _ensure_scannable_markdown_block(
        text,
        max_items=max_items,
        max_len=max_len,
    )


def _stabilize_long_answer_layout(
    markdown_text: str,
    *,
    research_mode: str,
    answer_language: str = "vi",
) -> str:
    text = str(markdown_text or "").strip()
    if not text:
        text = (
            "The research answer was compacted to keep the display stable."
            if answer_language == "en"
            else "Nội dung nghiên cứu đã được rút gọn để giữ hiển thị ổn định."
        )

    is_deep_beta = str(research_mode).strip().lower() == "deep_beta"
    conclusion_heading = _resolve_section_title("quick_conclusion", answer_language)
    key_points_heading = _resolve_section_title("key_points", answer_language)
    practical_heading = _resolve_section_title("practical_application", answer_language)
    caveat_heading = _resolve_section_title("safety_notes", answer_language)

    conclusion = _extract_h2_body_any(text, [conclusion_heading, "Kết luận nhanh", "Quick conclusion"])

    main_sections = "\n\n".join(
        filter(
            None,
            [
                _extract_h2_body_any(text, [key_points_heading, "Điểm chính", "Key points"]),
                _extract_h2_body(text, _canonical_h2_key("Phân tích chính")),
                _extract_h2_body_any(text, ["Phân tích chi tiết", "Detailed analysis"]),
                _extract_h2_body(text, _canonical_h2_key("Tổng hợp phát hiện chính")),
                _extract_h2_body_any(text, ["Tóm tắt điều hành", "Executive summary"]),
            ],
        )
    )
    practical_sections = "\n\n".join(
        filter(
            None,
            [
                _extract_h2_body_any(text, [practical_heading, "Ứng dụng thực tế", "Practical application"]),
                _extract_h2_body(text, _canonical_h2_key("Khuyến nghị ứng dụng thực hành")),
                _extract_h2_body(text, _canonical_h2_key("Ứng dụng lâm sàng theo nhóm bệnh nhân")),
                _extract_h2_body(text, _canonical_h2_key("Bối cảnh lâm sàng áp dụng")),
            ],
        )
    )
    caveat_sections = "\n\n".join(
        filter(
            None,
            [
                _extract_h2_body_any(text, [caveat_heading, "Lưu ý an toàn", "Important caveats"]),
                _extract_h2_body_any(text, ["Khuyến nghị an toàn", "Safety recommendations"]),
                _extract_h2_body_any(text, ["Theo dõi & cảnh báo đỏ", "Monitoring & red flags"]),
                _extract_h2_body(text, _canonical_h2_key("Kế hoạch theo dõi sau tư vấn")),
                _extract_h2_body(text, _canonical_h2_key("Giới hạn, sai số và rủi ro pháp lý")),
                _extract_h2_body(text, _canonical_h2_key("Phản biện bằng chứng đối nghịch")),
            ],
        )
    )

    plain = _to_plain_text(text)
    if _looks_language_misaligned(conclusion, answer_language=answer_language):
        conclusion = ""
    if _looks_language_misaligned(main_sections, answer_language=answer_language):
        main_sections = ""
    if _looks_language_misaligned(practical_sections, answer_language=answer_language):
        practical_sections = ""
    if _looks_language_misaligned(caveat_sections, answer_language=answer_language):
        caveat_sections = ""
    conclusion_block = _curate_sentence_excerpt(
        conclusion
        or (
            (
                "The evidence supports a cautious, context-dependent conclusion rather than a universal recommendation."
                if answer_language == "en"
                else "Bằng chứng hiện tại ủng hộ một kết luận thận trọng, phụ thuộc bối cảnh hơn là một khuyến nghị áp dụng cho mọi tình huống."
            )
            if _looks_language_misaligned(plain, answer_language=answer_language)
            else plain
        ),
        max_len=620 if is_deep_beta else 520,
        max_sentences=5 if is_deep_beta else 4,
    )
    main_block = _curate_markdown_excerpt(
        main_sections
        or (
            (
                "The main usable signal is to compare likely benefit, safety burden, implementation feasibility, and patient context before acting on a specific option."
                if answer_language == "en"
                else "Tín hiệu hữu ích nhất lúc này là phải so sánh lợi ích kỳ vọng, gánh nặng an toàn, tính khả thi triển khai và bối cảnh người bệnh trước khi chốt một lựa chọn cụ thể."
            )
            if _looks_language_misaligned(plain, answer_language=answer_language)
            else plain
        ),
        max_len=2800 if is_deep_beta else 1900,
        max_lines=16 if is_deep_beta else 11,
    )
    practical_block = _curate_markdown_excerpt(
        practical_sections,
        max_len=1600 if is_deep_beta else 1150,
        max_lines=10 if is_deep_beta else 7,
    )
    caveat_block = _curate_markdown_excerpt(
        caveat_sections,
        max_len=1200 if is_deep_beta else 880,
        max_lines=8 if is_deep_beta else 6,
    )

    if not practical_block:
        practical_block = (
            "- Apply the conclusion against the patient context, comorbidities, polypharmacy burden, and treatment goals.\n"
            "- For any concrete treatment change, re-check the decision with the treating clinician or pharmacist."
            if answer_language == "en"
            else "- Ưu tiên áp dụng kết luận theo bối cảnh bệnh nền, đa thuốc và mục tiêu điều trị cụ thể.\n"
            "- Khi cần thay đổi điều trị hoặc diễn giải kết quả cho một ca cụ thể, nên đối chiếu lại với bác sĩ/dược sĩ."
        )
    if not caveat_block:
        caveat_block = (
            "- Treat this as decision support, not a substitute for direct clinical evaluation.\n"
            "- Seek urgent care now for chest pain, shortness of breath, syncope, bleeding, or anaphylaxis."
            if answer_language == "en"
            else "- Xem đây là tổng hợp hỗ trợ quyết định, không thay thế đánh giá lâm sàng trực tiếp.\n"
            "- Cần đi khám/cấp cứu ngay nếu có đau ngực, khó thở, ngất, xuất huyết hoặc phản vệ."
        )
    main_block = _normalize_reader_facing_block(
        main_block,
        max_items=6 if is_deep_beta else 5,
        max_len=1800 if is_deep_beta else 1200,
        prefer_paragraphs=True,
    )
    practical_block = _ensure_scannable_markdown_block(
        practical_block,
        max_items=4 if is_deep_beta else 3,
        max_len=900 if is_deep_beta else 680,
    )
    caveat_block = _ensure_scannable_markdown_block(
        caveat_block,
        max_items=4 if is_deep_beta else 3,
        max_len=720 if is_deep_beta else 560,
    )

    stabilized = (
        f"## {conclusion_heading}\n"
        f"{conclusion_block}\n\n"
        f"## {key_points_heading}\n"
        f"{main_block}\n\n"
        f"## {practical_heading}\n"
        f"{practical_block}\n\n"
        f"## {caveat_heading}\n"
        f"{caveat_block}"
    )
    return re.sub(r"\n{3,}", "\n\n", stabilized).strip()


def _stabilize_deep_beta_fallback_dossier_layout(
    markdown_text: str,
    *,
    answer_language: str = "vi",
) -> str:
    language = "en" if str(answer_language or "").strip().lower() == "en" else "vi"
    text = str(markdown_text or "").strip()
    if not text:
        text = (
            "Fallback synthesis is active; treat this as a conservative evidence brief."
            if language == "en"
            else "Fallback synthesis đang hoạt động; xem đây là bản evidence brief thận trọng."
        )

    quick_heading = _resolve_section_title("quick_conclusion", language)
    key_points_heading = _resolve_section_title("key_points", language)
    practical_heading = _resolve_section_title("practical_application", language)
    caveat_heading = _resolve_section_title("safety_notes", language)
    monitoring_heading = _resolve_section_title("monitoring_red_flags", language)
    detailed_heading = _resolve_section_title("detailed_analysis", language)
    plan_heading = _resolve_section_title("research_plan", language)
    executive_heading = _resolve_section_title("executive_summary", language)

    quick_conclusion = _extract_h2_body_any(text, [quick_heading, "Kết luận nhanh", "Quick conclusion"])
    research_plan = _extract_h2_body_any(text, [plan_heading, "Kế hoạch nghiên cứu", "Research plan"])
    executive_summary = _extract_h2_body_any(
        text,
        [executive_heading, "Tóm tắt điều hành", "Executive summary", key_points_heading, "Điểm chính", "Key points"],
    )
    pico_question = _extract_h2_body_any(text, ["Câu hỏi nghiên cứu (PICO)", "Research question (PICO)"])
    retrieval_method = _extract_h2_body_any(
        text,
        ["Phương pháp truy xuất & tiêu chí chọn lọc", "Retrieval method & selection criteria"],
    )
    evidence_profile = _extract_h2_body_any(
        text,
        [
            "Hồ sơ bằng chứng & chất lượng nguồn",
            "Evidence profile & source quality",
            "Bảng tổng hợp bằng chứng",
            "Evidence summary table",
        ],
    )
    main_findings = _extract_h2_body_any(
        text,
        [
            "Tổng hợp phát hiện chính",
            "Main findings synthesis",
            key_points_heading,
            "Điểm chính",
            "Key points",
            executive_heading,
            "Tóm tắt điều hành",
            "Executive summary",
        ],
    )
    reasoning_chain = _extract_h2_body_any(
        text,
        [detailed_heading, "Phân tích chi tiết", "Detailed analysis", "Chuỗi lập luận bằng chứng", "Evidence reasoning chain"],
    )
    counter_evidence = _extract_h2_body_any(
        text,
        [
            "Phản biện bằng chứng đối nghịch",
            "Counter-evidence and contradictions",
            caveat_heading,
            "Lưu ý an toàn",
            "Important caveats",
        ],
    )
    clinical_application = _extract_h2_body_any(
        text,
        [
            "Ứng dụng lâm sàng theo nhóm bệnh nhân",
            "Clinical application by patient subgroup",
            "Bối cảnh lâm sàng áp dụng",
            "Clinical context",
            practical_heading,
            "Ứng dụng thực tế",
            "Practical application",
        ],
    )
    safety_matrix = _extract_h2_body_any(text, ["Ma trận quyết định an toàn", "Safety decision matrix"])
    follow_up_plan = _extract_h2_body_any(
        text,
        [
            "Kế hoạch theo dõi sau tư vấn",
            "Follow-up plan after counseling",
            monitoring_heading,
            "Theo dõi & cảnh báo đỏ",
            "Monitoring & red flags",
        ],
    )
    limitations = _extract_h2_body_any(
        text,
        ["Giới hạn, sai số và rủi ro pháp lý", "Limitations, error bands, and legal risk"],
    )

    summary_excerpt = _curate_sentence_excerpt(text, max_len=680, max_sentences=5)
    detail_excerpt = _curate_markdown_excerpt(text, max_len=1800, max_lines=12)

    if language == "en":
        quick_default = (
            "Current output is in local fallback mode; keep conclusions conservative and verify any treatment changes with primary sources."
        )
        plan_default = (
            "- Lock the question scope and patient safety boundaries before acting.\n"
            "- Prioritize guideline-level sources, systematic reviews, and high-quality clinical studies.\n"
            "- Reconcile supportive and contradictory evidence before final recommendations."
        )
        pico_default = (
            "- Population: patients matching the presented scenario and risk profile.\n"
            "- Intervention/Comparator: evaluate the relevant options and key trade-offs.\n"
            "- Outcomes: prioritize safety, efficacy, and practical feasibility."
        )
        retrieval_default = (
            "- Use multi-source retrieval with quality-first ranking.\n"
            "- Down-rank weak or non-clinical sources when stronger evidence exists.\n"
            "- Keep only evidence rows that can be traced back to explicit source references."
        )
        evidence_default = (
            "- Evidence quality is mixed in fallback mode; treat certainty as provisional.\n"
            "- Prioritize claims that are supported by multiple independent sources."
        )
        counter_default = (
            "- Contradictory evidence remains possible and should be reviewed before commitment.\n"
            "- Any recommendation should include uncertainty boundaries and conditions that would change the decision."
        )
        clinical_default = (
            "- Apply conclusions only after matching comorbidities, active medications, and treatment goals.\n"
            "- Escalate to clinician review for high-risk subgroups or unstable symptoms."
        )
        safety_matrix_default = (
            "| Decision axis | Current signal | Safe action |\n"
            "| --- | --- | --- |\n"
            "| Overall risk | Moderate/uncertain | Do not self-adjust treatment; confirm with clinician/pharmacist. |\n"
            "| Evidence confidence | Mixed | Prefer primary guidance and source-verified drug labels. |\n"
            "| Immediate escalation | Red-flag dependent | Seek urgent care for chest pain, dyspnea, syncope, bleeding, or anaphylaxis. |"
        )
        followup_default = (
            "- Document symptom trajectory and medication context after counseling.\n"
            "- Reassess red flags in the next 24-48 hours and escalate promptly if symptoms worsen."
        )
        limitations_default = (
            "- This report is decision support, not a replacement for direct clinical evaluation.\n"
            "- Residual uncertainty remains because fallback synthesis may miss newly emerged evidence."
        )
    else:
        quick_default = (
            "Đầu ra hiện ở chế độ fallback local; cần giữ kết luận thận trọng và xác minh lại trước khi đổi điều trị."
        )
        plan_default = (
            "- Khóa phạm vi câu hỏi và ranh giới an toàn trước khi áp dụng.\n"
            "- Ưu tiên guideline, tổng quan hệ thống và nghiên cứu lâm sàng chất lượng cao.\n"
            "- Đối chiếu bằng chứng thuận chiều và đối nghịch trước khi chốt khuyến nghị."
        )
        pico_default = (
            "- Population: nhóm người bệnh phù hợp bối cảnh và mức nguy cơ đang xem xét.\n"
            "- Intervention/Comparator: các lựa chọn điều trị hoặc hành động cần so sánh.\n"
            "- Outcomes: ưu tiên an toàn, hiệu quả và tính khả thi triển khai."
        )
        retrieval_default = (
            "- Truy xuất đa nguồn theo thứ tự ưu tiên chất lượng bằng chứng.\n"
            "- Giảm trọng số nguồn yếu hoặc không phù hợp lâm sàng khi đã có nguồn mạnh hơn.\n"
            "- Chỉ giữ các claim có thể truy vết về nguồn tham chiếu rõ ràng."
        )
        evidence_default = (
            "- Chất lượng bằng chứng trong fallback còn không đồng đều; xem mức chắc chắn là tạm thời.\n"
            "- Ưu tiên nhận định được hậu thuẫn bởi nhiều nguồn độc lập."
        )
        counter_default = (
            "- Vẫn có khả năng tồn tại bằng chứng đối nghịch cần rà soát trước khi quyết định.\n"
            "- Mọi khuyến nghị cần nêu rõ ranh giới bất định và điều kiện đảo chiều quyết định."
        )
        clinical_default = (
            "- Áp dụng theo nhóm bệnh nhân, bệnh nền, đa thuốc và mục tiêu điều trị cụ thể.\n"
            "- Nhóm nguy cơ cao hoặc triệu chứng không ổn định cần ưu tiên trao đổi bác sĩ sớm."
        )
        safety_matrix_default = (
            "| Mục đánh giá | Tín hiệu hiện tại | Hành động an toàn |\n"
            "| --- | --- | --- |\n"
            "| Mức rủi ro tổng quát | Trung bình/bất định | Không tự ý đổi thuốc hoặc liều; xác minh với bác sĩ/dược sĩ. |\n"
            "| Độ tin cậy bằng chứng | Không đồng nhất | Ưu tiên guideline và nhãn thuốc có truy xuất nguồn. |\n"
            "| Chuyển tuyến khẩn | Phụ thuộc red flag | Cần cấp cứu ngay nếu đau ngực, khó thở, ngất, xuất huyết hoặc phản vệ. |"
        )
        followup_default = (
            "- Ghi nhận diễn tiến triệu chứng và bối cảnh dùng thuốc sau tư vấn.\n"
            "- Tái đánh giá dấu hiệu cảnh báo đỏ trong 24-48 giờ và chuyển tuyến ngay khi nặng lên."
        )
        limitations_default = (
            "- Báo cáo này chỉ hỗ trợ quyết định, không thay thế đánh giá lâm sàng trực tiếp.\n"
            "- Fallback synthesis có thể bỏ sót bằng chứng mới nên vẫn còn sai số tồn dư."
        )

    quick_block = quick_conclusion or summary_excerpt or quick_default
    plan_block = _ensure_scannable_markdown_block(research_plan or plan_default, max_items=4, max_len=620)
    executive_block = _normalize_reader_facing_block(
        executive_summary or main_findings or detail_excerpt or summary_excerpt,
        max_items=6,
        max_len=1800,
        prefer_paragraphs=True,
    )
    pico_block = _ensure_scannable_markdown_block(pico_question or pico_default, max_items=4, max_len=620)
    retrieval_block = _ensure_scannable_markdown_block(
        retrieval_method or retrieval_default,
        max_items=4,
        max_len=680,
    )
    evidence_block = _ensure_scannable_markdown_block(
        evidence_profile or evidence_default,
        max_items=5,
        max_len=900,
    )
    main_findings_block = _normalize_reader_facing_block(
        main_findings or executive_summary or detail_excerpt,
        max_items=6,
        max_len=1800,
        prefer_paragraphs=True,
    )
    reasoning_block = _normalize_reader_facing_block(
        reasoning_chain or detail_excerpt,
        max_items=6,
        max_len=1800,
        prefer_paragraphs=True,
    )
    counter_block = _ensure_scannable_markdown_block(
        counter_evidence or counter_default,
        max_items=4,
        max_len=900,
    )
    clinical_block = _ensure_scannable_markdown_block(
        clinical_application or clinical_default,
        max_items=4,
        max_len=900,
    )
    matrix_block = safety_matrix.strip() if safety_matrix.strip() else safety_matrix_default
    followup_block = _ensure_scannable_markdown_block(
        follow_up_plan or followup_default,
        max_items=4,
        max_len=900,
    )
    limitations_block = _ensure_scannable_markdown_block(
        limitations or counter_evidence or limitations_default,
        max_items=4,
        max_len=900,
    )

    section_body_by_key = {
        _canonical_h2_key("Kết luận nhanh"): quick_block,
        _canonical_h2_key("Quick conclusion"): quick_block,
        _canonical_h2_key("Kế hoạch nghiên cứu"): plan_block,
        _canonical_h2_key("Research plan"): plan_block,
        _canonical_h2_key("Tóm tắt điều hành"): executive_block,
        _canonical_h2_key("Executive summary"): executive_block,
        _canonical_h2_key("Câu hỏi nghiên cứu (PICO)"): pico_block,
        _canonical_h2_key("Research question (PICO)"): pico_block,
        _canonical_h2_key("Phương pháp truy xuất & tiêu chí chọn lọc"): retrieval_block,
        _canonical_h2_key("Retrieval method & selection criteria"): retrieval_block,
        _canonical_h2_key("Hồ sơ bằng chứng & chất lượng nguồn"): evidence_block,
        _canonical_h2_key("Evidence profile & source quality"): evidence_block,
        _canonical_h2_key("Tổng hợp phát hiện chính"): main_findings_block,
        _canonical_h2_key("Main findings synthesis"): main_findings_block,
        _canonical_h2_key("Chuỗi lập luận bằng chứng"): reasoning_block,
        _canonical_h2_key("Evidence reasoning chain"): reasoning_block,
        _canonical_h2_key("Phản biện bằng chứng đối nghịch"): counter_block,
        _canonical_h2_key("Counter-evidence and contradictions"): counter_block,
        _canonical_h2_key("Ứng dụng lâm sàng theo nhóm bệnh nhân"): clinical_block,
        _canonical_h2_key("Clinical application by patient subgroup"): clinical_block,
        _canonical_h2_key("Ma trận quyết định an toàn"): matrix_block,
        _canonical_h2_key("Safety decision matrix"): matrix_block,
        _canonical_h2_key("Kế hoạch theo dõi sau tư vấn"): followup_block,
        _canonical_h2_key("Follow-up plan after counseling"): followup_block,
        _canonical_h2_key("Giới hạn, sai số và rủi ro pháp lý"): limitations_block,
        _canonical_h2_key("Limitations, error bands, and legal risk"): limitations_block,
    }

    sections: list[str] = []
    for heading in _resolve_deep_beta_dossier_headings(language):
        heading_key = _canonical_h2_key(heading)
        section_body = section_body_by_key.get(heading_key) or summary_excerpt or detail_excerpt
        sections.append(f"{heading}\n{section_body}".rstrip())

    return re.sub(r"\n{3,}", "\n\n", "\n\n".join(sections)).strip()


def _sanitize_user_facing_answer_markdown(
    answer_markdown: str,
    *,
    research_mode: str = "fast",
    answer_language: str = "vi",
    fallback_used: bool = False,
) -> str:
    mode = str(research_mode).strip().lower()
    is_deep_beta = mode == "deep_beta"
    sanitized = _normalize_user_facing_answer_markdown(
        answer_markdown,
        answer_language=answer_language,
    )
    if not sanitized.strip():
        return sanitized

    # Strip noisy fallback sentence from body; fallback state remains in metadata/telemetry.
    sanitized = re.sub(
        r"hệ thống tạm thời dùng fallback local để đảm bảo không gián đoạn trả lời\.?",
        "",
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"hệ thống chuyển sang chế độ tổng hợp an toàn để duy trì phản hồi ổn định\.?",
        "",
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"(?:^|\n)\s*(?:query|câu hỏi)\s*:\s*.+?(?=\n|$)",
        "\n",
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"(?:^|\n)\s*-*\s*(?:dưới đây là ngữ cảnh đã truy xuất và rút gọn ở chế độ cục bộ|below is the locally retrieved and condensed context)\s*:?",
        "\n",
        sanitized,
        flags=re.IGNORECASE,
    )

    if not is_deep_beta:
        # Fast/deep keep citations in side panels to reduce answer-body verbosity.
        sanitized = _remove_h2_sections(
            sanitized,
            section_heading_keys={
                _canonical_h2_key("Nguồn tham chiếu"),
                _canonical_h2_key("Danh mục nguồn dùng để hiệu chỉnh nhận định"),
                _canonical_h2_key("Nguồn tham chiếu bổ sung"),
            },
        )
        sanitized = re.sub(
            r"(?:^|\n)\s*###\s*Nguồn tham chiếu[^\n]*[\s\S]*?(?=\n##\s|\n#\s|$)",
            "\n",
            sanitized,
            flags=re.IGNORECASE,
        )

    if mode == "fast":
        # Fast mode should stay compact and natural; deep template sections are moved to telemetry.
        sanitized = _remove_h2_sections(
            sanitized,
            section_heading_keys={
                _canonical_h2_key("Tóm tắt điều hành"),
                _canonical_h2_key("Kế hoạch nghiên cứu"),
                _canonical_h2_key("Câu hỏi nghiên cứu (PICO)"),
                _canonical_h2_key("Phương pháp truy xuất & tiêu chí chọn lọc"),
                _canonical_h2_key("Hồ sơ bằng chứng & chất lượng nguồn"),
                _canonical_h2_key("Tổng hợp phát hiện chính"),
                _canonical_h2_key("Chuỗi lập luận bằng chứng"),
                _canonical_h2_key("Phản biện bằng chứng đối nghịch"),
                _canonical_h2_key("Ứng dụng lâm sàng theo nhóm bệnh nhân"),
                _canonical_h2_key("Ma trận quyết định an toàn"),
                _canonical_h2_key("Kế hoạch theo dõi sau tư vấn"),
                _canonical_h2_key("Giới hạn, sai số và rủi ro pháp lý"),
                _canonical_h2_key("Bảng tổng hợp bằng chứng"),
            },
        )
        sanitized = _remove_unapproved_fast_h2_sections(sanitized)
        sanitized = re.sub(
            r"(?:^|\n)\s*security\s*\n+\s*ma trận quyết định an toàn[\s\S]*?(?=\n##\s|\n#\s|$)",
            "\n",
            sanitized,
            flags=re.IGNORECASE,
        )
        sanitized = re.sub(
            r"(?:^|\n)\s*ai\s*verified[\s\S]*?(?=\n##\s|\n#\s|$)",
            "\n",
            sanitized,
            flags=re.IGNORECASE,
        )
        sanitized = re.sub(
            r"(?:^|\n)\s*\|?\s*claim\s*\|?\s*verdict\s*\|?\s*confidence[^\n]*\n(?:\s*\|?.*?\n){1,30}",
            "\n",
            sanitized,
            flags=re.IGNORECASE,
        )

    if mode == "deep":
        # Deep keeps analysis sections but removes heavy evidence table from body.
        sanitized = _remove_h2_sections(
            sanitized,
            section_heading_keys={
                _canonical_h2_key("Bảng tổng hợp bằng chứng"),
                _canonical_h2_key("Evidence summary table"),
                _canonical_h2_key("Evidence table"),
            },
        )
    if mode in {"deep", "deep_beta"}:
        # Remove telemetry-heavy H3 blocks in deep modes; keep user-facing report sections.
        sanitized = _remove_h3_sections_by_heading_keys(
            sanitized,
            heading_keys={
                _canonical_h2_key("Nhật ký multi-pass retrieval"),
                _canonical_h2_key("Ma trận reasoning nodes"),
                _canonical_h2_key("Ma trận trạng thái claim-level"),
                _canonical_h2_key("Hồ sơ nguồn mở rộng"),
                _canonical_h2_key("Nguồn tham chiếu bổ sung"),
                _canonical_h2_key("Bảng bổ sung Deep Beta"),
                _canonical_h2_key("Bảng triển khai truy xuất"),
            },
        )

    # Mermaid/chart spec is moved out of main answer area to reduce visual clutter.
    sanitized = _remove_fenced_blocks(
        sanitized,
        languages={"mermaid", "chart-spec", "vega-lite", "echarts-option"},
    )
    if mode == "fast":
        if not _has_reader_friendly_layout(sanitized, research_mode=mode):
            sanitized = _stabilize_fast_answer_layout(sanitized, answer_language=answer_language)
    elif mode in {"deep", "deep_beta"}:
        should_stabilize_long = not _has_reader_friendly_layout(sanitized, research_mode=mode)
        if should_stabilize_long and _has_preservable_long_form_layout(
            sanitized,
            research_mode=mode,
        ):
            should_stabilize_long = False
        if mode == "deep_beta":
            # Preserve long deep-research body when it is already substantial.
            deep_beta_guardrail = max(2500, int(max(int(settings.deep_beta_report_min_words), 7000) * 0.5))
            if _markdown_word_count(sanitized) >= deep_beta_guardrail:
                should_stabilize_long = False
        sanitized = (
            _stabilize_long_answer_layout(
                sanitized,
                research_mode=mode,
                answer_language=answer_language,
            )
            if should_stabilize_long
            else sanitized
        )
    if mode == "fast":
        sanitized = _drop_unapproved_h2_sections(sanitized, research_mode=mode)
    elif mode in {"deep", "deep_beta"}:
        # Remove only the overly verbose execution appendix; keep deep sections intact.
        sanitized = _remove_h2_sections(
            sanitized,
            section_heading_keys={
                _canonical_h2_key("Triển khai đầy đủ kế hoạch"),
                _canonical_h2_key("Full execution plan"),
            },
        )
    if (
        mode == "deep_beta"
        and fallback_used
        and not _deep_beta_clean_body_active()
    ):
        # On the clean-body path we intentionally keep the natural, reader-first
        # layout even on fallback rather than re-imposing the rigid dossier.
        sanitized = _stabilize_deep_beta_fallback_dossier_layout(
            sanitized,
            answer_language=answer_language,
        )
    if mode in {"deep", "deep_beta"}:
        # Deep modes keep analytic prose, but any leaked FIDES-style claim/verdict/
        # confidence debug table is internal telemetry and must not reach the body.
        sanitized = re.sub(
            r"(?:^|\n)\s*\|?\s*claim\s*\|?\s*verdict\s*\|?\s*confidence[^\n]*\n(?:\s*\|?.*?\n){1,30}",
            "\n",
            sanitized,
            flags=re.IGNORECASE,
        )
    # Final defense-in-depth pass: strip any internal pipeline / planner /
    # telemetry tags that leaked inline past the structured section removal
    # (Requirement 3.3 / Property P9).
    sanitized = _strip_internal_pipeline_tags(sanitized)
    sanitized = re.sub(r"\n{3,}", "\n\n", sanitized).strip()
    return sanitized


def _build_deep_beta_reasoning_client(
    *,
    timeout_cap_seconds: float = 25.0,
    llm_runtime: dict[str, Any] | None = None,
) -> DeepSeekClient | None:
    _, api_key, base_url, model = _resolve_runtime_llm_config(llm_runtime)
    if not api_key or not base_url or not model:
        return None
    timeout_seconds = max(2.0, min(float(settings.deepseek_timeout_seconds), timeout_cap_seconds))
    return DeepSeekClient(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_seconds=timeout_seconds,
        retries_per_base=max(0, int(settings.deepseek_retries_per_base)),
        retry_backoff_seconds=max(0.0, float(settings.deepseek_retry_backoff_seconds)),
        max_concurrency=settings.llm_global_max_concurrency,
        min_interval_seconds=settings.llm_global_min_interval_seconds,
        request_jitter_seconds=settings.llm_global_jitter_seconds,
    )


def _extract_reasoning_context_rows(
    rows: list[dict[str, Any]],
    *,
    max_items: int = 18,
    max_text_len: int = 260,
) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        compact.append(
            {
                "id": _first_nonempty_text(item.get("id"), item.get("source"), f"ctx-{len(compact)+1}"),
                "source": _first_nonempty_text(item.get("source"), "unknown"),
                "title": _compact_snippet(_first_nonempty_text(item.get("title")), max_len=96),
                "text": _compact_snippet(item.get("text"), max_len=max_text_len),
                "url": _safe_url(item.get("url")) or "",
                "score": _safe_float(item.get("score"), 0.0),
            }
        )
        if len(compact) >= max_items:
            break
    return compact


def _strip_json_fence(raw: str) -> str:
    text = str(raw or "").strip()
    text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def _deep_beta_json_call(
    *,
    client: DeepSeekClient,
    system_prompt: str,
    prompt: str,
    fallback: dict[str, Any],
) -> dict[str, Any]:
    try:
        response = client.generate(prompt=prompt, system_prompt=system_prompt)
    except Exception:
        return fallback

    try:
        parsed = json.loads(_strip_json_fence(response.content))
    except Exception:
        return fallback
    return parsed if isinstance(parsed, dict) else fallback


def _deep_beta_markdown_call(
    *,
    client: DeepSeekClient,
    system_prompt: str,
    prompt: str,
) -> str:
    try:
        response = client.generate(prompt=prompt, system_prompt=system_prompt)
    except Exception:
        return ""
    return str(response.content or "").strip()


def _coerce_reasoning_queries(value: Any, *, limit: int = 6) -> list[str]:
    if not isinstance(value, list):
        return []
    return _dedupe_query_list([str(item) for item in value], limit=limit)


def _request_targeted_enrichment_section(
    *,
    client: DeepSeekClient,
    system_prompt: str,
    report_markdown: str,
    topic: str,
    citations: list[Citation],
    answer_language: str,
    min_chars: int,
) -> str:
    """Request ONE targeted, evidence-grounded section to grow a short report.

    Synthesis-v2 enrichment (Requirement 2.3 / design section E, Property P5):
    instead of immediately padding a sub-minimum ``deep_beta`` report with the
    static auto-appendix log table, ask the model for a single substantive
    section that fills the largest missing analytic dimension, grounded only in
    the citations/evidence already retrieved (no fabricated sources). Returns
    sanitized Markdown, or ``""`` when the model returns nothing usable so the
    caller can fall back to the legacy appendix. Pure w.r.t. the report (does
    not mutate inputs) and PII-free in telemetry (it traces nothing).
    """

    language_label = "English" if answer_language == "en" else "Vietnamese"
    compact_citations = [
        {
            "source_id": item.source_id,
            "source": item.source,
            "title": item.title,
            "url": item.url,
            "relevance": item.relevance,
        }
        for item in citations[:24]
    ]
    missing_words = max(int(min_chars) // 6, 200)
    enrichment_prompt = (
        f"The following {language_label} medical research report is shorter than "
        "its required minimum length. Add ONE substantive, evidence-grounded "
        "section that deepens the single most valuable missing analytic "
        "dimension for this topic (for example: comparative effectiveness, "
        "safety/monitoring, subgroup considerations, or evidence gaps and "
        "uncertainty).\n"
        "Output valid GitHub-Flavored Markdown only, no HTML.\n"
        "APPEND new content only as one new H2 section; do NOT rewrite, repeat, "
        "or duplicate any existing section.\n"
        "Ground every major claim in the supplied citations and state evidence "
        "limitations explicitly; do NOT fabricate citations or sources to reach "
        "a length target.\n"
        f"Aim for roughly {missing_words} additional words of dense analysis.\n"
        f"- keep every heading, label, bullet, and sentence in {language_label}\n"
        "- do not expose internal pipeline tags, execution logs, or debug telemetry\n"
        "- do not prescribe dosage, do not provide a definitive diagnosis\n\n"
        f"topic={topic}\n"
        f"existing_report={report_markdown}\n"
        f"citations={json.dumps(compact_citations, ensure_ascii=False)}\n"
    )
    raw = _deep_beta_markdown_call(
        client=client,
        system_prompt=system_prompt,
        prompt=enrichment_prompt,
    )
    enriched = _sanitize_deep_beta_markdown_output(str(raw or "").strip())
    if not enriched or enriched in report_markdown:
        return ""
    return enriched


def _ensure_min_deep_beta_report(
    *,
    report_markdown: str,
    topic: str,
    citations: list[Citation],
    deep_pass_summaries: list[dict[str, Any]],
    min_chars: int,
    client: DeepSeekClient | None = None,
    system_prompt: str | None = None,
    answer_language: str = "vi",
) -> str:
    cleaned = str(report_markdown or "").strip()
    threshold = max(400, int(min_chars))
    if len(cleaned) >= threshold:
        return cleaned

    # Synthesis-v2 (Requirement 2.3 / Property P5): before resorting to the
    # static appendix padding below, request ONE targeted, evidence-grounded
    # section from the LLM using the available citations/evidence. Gated behind
    # ``synthesis_v2_enabled`` AND a usable client so the flags-off / no-client
    # path stays byte-for-byte identical to the legacy appendix fallback
    # (design Property P8 / Requirement 6.2).
    if settings.synthesis_v2_enabled and client is not None:
        enriched = _request_targeted_enrichment_section(
            client=client,
            system_prompt=system_prompt or "",
            report_markdown=cleaned,
            topic=topic,
            citations=citations,
            answer_language=answer_language,
            min_chars=threshold,
        )
        if enriched:
            candidate = f"{cleaned}\n\n{enriched}".strip()
            if len(candidate) >= threshold:
                return candidate
            # Keep the substantive enrichment, then let the appendix below act
            # only as a final top-up rather than the sole padding source.
            cleaned = candidate

    citations_md = "\n".join(_citation_markdown_lines(citations))
    pass_rows = deep_pass_summaries[:10]
    pass_table_rows = [
        "| Pass | Subquery | Retrieved | Duration (ms) |",
        "| --- | --- | --- | --- |",
    ]
    if pass_rows:
        for item in pass_rows:
            pass_table_rows.append(
                "| "
                f"{_escape_markdown_cell(item.get('pass_index'))} | "
                f"{_escape_markdown_cell(_compact_snippet(item.get('subquery'), max_len=120))} | "
                f"{_escape_markdown_cell(item.get('retrieved_count'))} | "
                f"{_escape_markdown_cell(item.get('duration_ms'))} |"
            )
    else:
        pass_table_rows.append("| 1 | baseline | 0 | 0 |")
    pass_table = "\n".join(pass_table_rows)

    extension = (
        "## Phụ lục Deep Beta (Auto-Expanded)\n"
        f"- Chủ đề: {_compact_snippet(topic, max_len=220)}\n"
        f"- Tổng số pass retrieval: {max(1, len(deep_pass_summaries))}\n"
        f"- Tổng số nguồn trích dẫn: {len(citations)}\n\n"
        "### Nhật ký pass retrieval\n"
        f"{pass_table}\n\n"
        "### Hướng dẫn diễn giải an toàn\n"
        "- Luôn đọc kết quả như thông tin hỗ trợ, không thay thế chỉ định điều trị cá thể hóa.\n"
        "- Ưu tiên xác minh lại điểm mâu thuẫn evidence trước khi ra quyết định.\n"
        "- Khi có bệnh nền/đa thuốc/triệu chứng nặng, cần trao đổi bác sĩ ngay.\n\n"
        "### Nguồn tham chiếu bổ sung\n"
        f"{citations_md}"
    )
    combined = f"{cleaned}\n\n{extension}".strip()
    return combined


def run_research_tier2(payload: dict[str, Any]) -> dict:
    topic = _normalize_topic(payload)
    research_mode = _normalize_research_mode(payload)
    # PICO-structured question framing (R7). Runs on the clean query before any
    # personalization suffix, retrieval, or synthesis so that an undetermined element
    # rejects the request (PicoIncompleteError) instead of fabricating a value (R7.2).
    # Returns None when the flag is off or the query is not clinical (R7.4).
    pico_frame = _maybe_build_pico_frame(topic)
    retrieval_stack_mode = _normalize_retrieval_stack_mode(payload)
    answer_language = _normalize_answer_language(payload)
    personal_mode = _normalize_personal_mode(payload)
    # clara-research R15.1: personalization (PHR + medicine cabinet) is incorporated into the
    # synthesis only for deep / deep_beta runs. Fast mode never personalizes (R15.2 invariant),
    # so even if a payload carries personal_context in fast mode it is ignored here (defense in
    # depth). Consent gating is enforced API-side: personal_context is only present in the
    # payload when the user has granted consent, so no consent ⇒ no personal_context ⇒ no
    # personalization (R15.3).
    personalization_allowed = personal_mode and research_mode in {"deep", "deep_beta"}
    personal_context = _extract_personal_context(payload) if personalization_allowed else {}
    personal_context_suffix = (
        _build_personal_context_suffix(personal_context, answer_language=answer_language)
        if personalization_allowed and personal_context
        else ""
    )
    if personal_context_suffix:
        topic = f"{topic}\n\n{personal_context_suffix}".strip()
    trace_id, run_id = _resolve_trace_identifiers(payload)
    source_mode = str(payload.get("source_mode") or "").strip().lower() or None
    role_hint = str(payload.get("role") or "").strip().lower() or None
    uploaded_documents_raw = payload.get("uploaded_documents")
    uploaded_documents: list[dict[str, Any]] = (
        uploaded_documents_raw if isinstance(uploaded_documents_raw, list) else []
    )
    rag_sources = payload.get("rag_sources")
    rag_flow_payload = payload.get("rag_flow")
    rag_flow = rag_flow_payload if isinstance(rag_flow_payload, dict) else {}
    top_level_llm_runtime = payload.get("llm_runtime")
    top_level_llm_runtime_dict = (
        top_level_llm_runtime if isinstance(top_level_llm_runtime, dict) else {}
    )
    requested_llm_runtime = {
        "provider": top_level_llm_runtime_dict.get("provider") or rag_flow.get("llm_provider"),
        "api_key": top_level_llm_runtime_dict.get("api_key") or rag_flow.get("llm_api_key"),
        "base_url": top_level_llm_runtime_dict.get("base_url") or rag_flow.get("llm_base_url"),
        "model": top_level_llm_runtime_dict.get("model") or rag_flow.get("llm_model"),
    }
    llm_provider, resolved_llm_api_key, llm_base_url, llm_model = _resolve_runtime_llm_config(
        requested_llm_runtime
    )
    llm_runtime = {
        "provider": llm_provider,
        "api_key": resolved_llm_api_key,
        "base_url": llm_base_url,
        "model": llm_model,
    }
    legacy_verification_enabled = _coerce_bool(
        rag_flow.get("verification_enabled"),
        bool(settings.rule_verification_enabled),
    )
    rule_verification_enabled = (
        _coerce_bool(rag_flow.get("rule_verification_enabled"), legacy_verification_enabled)
        if "rule_verification_enabled" in rag_flow
        else legacy_verification_enabled
    )
    nli_model_enabled = _coerce_bool(rag_flow.get("nli_model_enabled"), True)
    rag_nli_enabled_override = _coerce_optional_bool(rag_flow.get("rag_nli_enabled"))
    rag_nli_enabled_runtime = (
        bool(settings.rag_nli_enabled)
        if rag_nli_enabled_override is None
        else bool(rag_nli_enabled_override)
    )
    rag_nli_enabled_runtime = bool(nli_model_enabled and rag_nli_enabled_runtime)
    rag_reranker_enabled_override = _coerce_optional_bool(rag_flow.get("rag_reranker_enabled"))
    rag_graphrag_enabled_override = _coerce_optional_bool(rag_flow.get("rag_graphrag_enabled"))
    if research_mode == "deep_beta":
        if rag_reranker_enabled_override is None:
            rag_reranker_enabled_override = True
        if rag_graphrag_enabled_override is None:
            rag_graphrag_enabled_override = True
    effective_rag_reranker_enabled = (
        bool(settings.rag_reranker_enabled)
        if rag_reranker_enabled_override is None
        else bool(rag_reranker_enabled_override)
    )
    effective_rag_graphrag_enabled = (
        bool(settings.rag_graphrag_enabled)
        if rag_graphrag_enabled_override is None
        else bool(rag_graphrag_enabled_override)
    )
    route = router.route(topic, role_hint=role_hint)

    plan_steps = _build_plan_steps(topic, source_mode, research_mode=research_mode)
    planner_hints = _build_planner_hints(
        topic=topic,
        source_mode=source_mode,
        route_role=route.role,
        route_intent=route.intent,
        uploaded_documents=uploaded_documents,
        rag_sources=rag_sources,
        research_mode=research_mode,
        retrieval_stack_mode=retrieval_stack_mode,
    )
    planner_hints["personal_mode"] = personal_mode
    if personal_context_suffix:
        planner_hints["personal_context_summary"] = personal_context_suffix[:2000]
    planner_hints["answer_language"] = answer_language
    source_route = decide_source_route(
        query=topic,
        research_mode=research_mode,
        has_uploaded_documents=bool(uploaded_documents),
        is_ddi_query=bool(planner_hints.get("is_ddi_query")),
        is_ddi_critical_query=bool(planner_hints.get("is_ddi_critical_query")),
        language_hint=str(planner_hints.get("language_hint") or "en"),
        web_policy_allowed=bool(planner_hints.get("web_retrieval_enabled")),
    )

    force_multi_source = bool(planner_hints.get("force_multi_source"))
    planner_hints["scientific_retrieval_enabled"] = bool(
        planner_hints.get("scientific_retrieval_enabled")
    ) and (bool(source_route.enable_scientific) or force_multi_source)
    planner_hints["web_retrieval_enabled"] = bool(planner_hints.get("web_retrieval_enabled")) and (
        bool(source_route.enable_web) or force_multi_source
    )
    reason_codes = planner_hints.get("reason_codes")
    if not isinstance(reason_codes, list):
        reason_codes = []
    reason_codes.extend(f"source_route:{code}" for code in source_route.reason_codes if code)
    reason_codes.append(f"retrieval_route_{source_route.retrieval_route}")
    planner_hints["reason_codes"] = list(dict.fromkeys([str(item) for item in reason_codes if str(item)]))
    planner_hints["retrieval_route"] = _normalize_retrieval_route(source_route.retrieval_route)
    planner_hints["router_confidence"] = _normalize_router_confidence(source_route.confidence)
    planner_hints["router_reason_codes"] = list(source_route.reason_codes)

    base_query_plan = _build_source_aware_query_plan(
        topic=topic,
        research_mode=research_mode,
        keywords=planner_hints.get("keywords", []),
        source_route=source_route,
    )
    planner_hints["query_plan"] = base_query_plan
    run_started_at = perf_counter()
    pipeline_node_steps: list[dict[str, Any]] = []
    keyword_filter_report: dict[str, Any] = {}
    keyword_filter_status = "skipped"
    evidence_review_summary: dict[str, Any] = {}
    evidence_review_status = "skipped"

    def _event(
        *,
        stage: str,
        status: str,
        source_count: int,
        note: str,
        component: str,
        payload: dict[str, Any] | None = None,
        started_at: float | None = None,
    ) -> dict[str, Any]:
        now = perf_counter()
        event_payload = dict(payload or {})
        event_payload.setdefault("trace_id", trace_id)
        event_payload.setdefault("run_id", run_id)
        event_payload.setdefault("elapsed_ms", round((now - run_started_at) * 1000.0, 3))
        if started_at is not None:
            event_payload.setdefault("duration_ms", round((now - started_at) * 1000.0, 3))
        return _flow_event(
            stage=stage,
            status=status,
            source_count=source_count,
            note=note,
            component=component,
            payload=event_payload,
        )

    flow_events: list[dict[str, Any]] = [
        _event(
            stage="planner",
            status="started",
            source_count=0,
            note="Planner started Tier-2 orchestration.",
            component="planner",
            payload={
                "source_mode": source_mode or "default",
                "route_role": route.role,
                "route_intent": route.intent,
                "research_mode": research_mode,
                "retrieval_route": planner_hints.get("retrieval_route", "internal-heavy"),
                "router_confidence": planner_hints.get("router_confidence", 0.0),
                "flow_flags": {
                    "verification_enabled": legacy_verification_enabled,
                    "rule_verification_enabled": rule_verification_enabled,
                    "nli_model_enabled": nli_model_enabled,
                    "rag_nli_enabled": rag_nli_enabled_runtime,
                    "rag_reranker_enabled": effective_rag_reranker_enabled,
                    "rag_graphrag_enabled": effective_rag_graphrag_enabled,
                },
            },
        ),
    ]

    llm_plan, llm_plan_status = _refine_query_plan_with_llm(
        topic=topic,
        research_mode=research_mode,
        route_role=route.role,
        route_intent=route.intent,
        base_query_plan=base_query_plan,
        keywords=planner_hints.get("keywords", []),
        llm_runtime=llm_runtime,
    )
    llm_attempted = bool(llm_plan_status.get("attempted"))
    llm_status = str(llm_plan_status.get("status") or "degraded")
    llm_reason = str(llm_plan_status.get("reason") or "unknown")

    if llm_attempted:
        flow_events.append(
            _event(
                stage="llm_query_planner",
                status="started",
                source_count=0,
                note="LLM query planner refinement started.",
                component="planner",
                payload={
                    "base_canonical_query": base_query_plan.get("canonical_query"),
                    "model": llm_model or settings.deepseek_model,
                    "provider": llm_provider,
                    "base_url": llm_base_url,
                },
            )
        )

    if llm_status == "completed":
        planner_hints["query_plan"] = llm_plan
        planner_hints["reason_codes"] = [
            *planner_hints.get("reason_codes", []),
            "llm_query_planner_enabled",
        ]
        flow_events.append(
            _event(
                stage="llm_query_planner",
                status="completed",
                source_count=0,
                note="LLM query planner refinement completed.",
                component="planner",
                payload={
                    "model_used": llm_plan_status.get("model_used"),
                    "reason": llm_reason,
                    "canonical_query": llm_plan.get("canonical_query"),
                },
            )
        )
    else:
        # A "recovered" result is the deterministic base plan, not an LLM
        # success. Keep telemetry honest so operators can distinguish semantic
        # planning from outage recovery.
        planner_hints["query_plan"] = llm_plan if llm_status == "recovered" else base_query_plan
        if llm_attempted:
            planner_hints["reason_codes"] = [
                *planner_hints.get("reason_codes", []),
                "llm_query_planner_fallback",
            ]
        flow_events.append(
            _event(
                stage="llm_query_planner",
                status="degraded",
                source_count=0,
                note=(
                    "LLM query planner degraded; fallback to base query plan."
                    if llm_attempted
                    else "LLM query planner skipped due to missing API key."
                ),
                component="planner",
                payload={
                    "reason": llm_reason,
                    "attempted": llm_attempted,
                    "error": llm_plan_status.get("error"),
                    "canonical_query": planner_hints["query_plan"].get("canonical_query"),
                },
            )
        )

    if isinstance(planner_hints.get("query_plan"), dict):
        planner_hints["query_plan"]["retrieval_route"] = _normalize_retrieval_route(
            planner_hints.get("retrieval_route")
        )
        planner_hints["query_plan"]["router_confidence"] = _normalize_router_confidence(
            planner_hints.get("router_confidence")
        )

    keyword_filter_started = perf_counter()
    flow_events.append(
        _event(
            stage="keyword_filter",
            status="started",
            source_count=0,
            note="Keyword filter node started (source-language alignment).",
            component="planner",
            payload={
                "source_mode": source_mode or "default",
                "language_hint": planner_hints.get("language_hint"),
                "keywords_before": planner_hints.get("keywords", []),
            },
        )
    )
    keyword_filter_report = _apply_keyword_filter_to_query_plan(
        topic=topic,
        query_plan=(
            planner_hints.get("query_plan")
            if isinstance(planner_hints.get("query_plan"), dict)
            else {}
        ),
        planner_keywords=(
            planner_hints.get("keywords")
            if isinstance(planner_hints.get("keywords"), list)
            else []
        ),
        source_mode=source_mode,
    )
    planner_hints["query_plan"] = keyword_filter_report.get("query_plan", planner_hints.get("query_plan"))
    planner_hints["keywords"] = keyword_filter_report.get("keywords", planner_hints.get("keywords", []))
    planner_hints["keywords_by_source"] = keyword_filter_report.get("keywords_by_source", {})
    planner_hints["target_language_by_source"] = keyword_filter_report.get(
        "target_language_by_source", {}
    )
    keyword_filter_status = (
        "warning"
        if keyword_filter_report.get("fallback_buckets")
        else "completed"
    )
    pipeline_node_steps.append(
        {
            "stage": "keyword_filter",
            "status": keyword_filter_status,
            "note": (
                "Keyword filter completed with source-language buckets."
                if keyword_filter_status == "completed"
                else "Keyword filter used fallback keywords for some source buckets."
            ),
            "payload": keyword_filter_report,
        }
    )
    flow_events.append(
        _event(
            stage="keyword_filter",
            status=keyword_filter_status,
            source_count=0,
            note=(
                "Keyword filter completed."
                if keyword_filter_status == "completed"
                else "Keyword filter completed with fallback buckets."
            ),
            component="planner",
            payload=keyword_filter_report,
            started_at=keyword_filter_started,
        )
    )

    planner_trace = _build_planner_trace(
        topic=topic,
        source_mode=source_mode,
        route_role=route.role,
        route_intent=route.intent,
        route_confidence=route.confidence,
        route_emergency=route.emergency,
        planner_hints=planner_hints,
        plan_steps=plan_steps,
    )
    planner_trace["trace_id"] = trace_id
    planner_trace["run_id"] = run_id
    flow_events.append(
        _event(
            stage="planner",
            status="completed",
            source_count=0,
            note="Planner produced retrieval and verification strategy.",
            component="planner",
            payload=planner_hints,
        )
    )

    pipeline = RagPipelineP1()
    # Only service-level policy should force strict upstream generation.
    # Request-level runtime overrides are best-effort and must still degrade
    # gracefully to telemetry-rich fallback when the external gateway is down.
    strict_deepseek_required = bool(settings.deepseek_required)
    deepseek_fallback_enabled = not strict_deepseek_required
    deep_beta_cap = max(6, min(int(settings.deep_beta_pass_cap), 64))
    pass_count_cap = deep_beta_cap if research_mode == "deep_beta" else _DEFAULT_DEEP_PASS_CAP
    deep_pass_count = _resolve_deep_pass_count(
        payload,
        int(planner_hints.get("deep_pass_count", 1)),
        cap=pass_count_cap,
    )
    planner_hints["deep_pass_count"] = deep_pass_count
    if isinstance(planner_trace.get("planner_hints"), dict):
        planner_trace["planner_hints"]["deep_pass_count"] = deep_pass_count
    deep_subqueries: list[str] = [topic]
    # R5.4: cumulative count of bounded gap-fill retrieval passes executed across all
    # sub-questions. Stays 0 when ``RESEARCH_GAP_FILL_ENABLED`` is off (legacy behavior).
    deep_gap_fill_passes: int = 0
    deep_research_profiles: list[dict[str, Any]] = []
    deep_research_method: dict[str, Any] = {}
    deep_pass_summaries: list[dict[str, Any]] = []
    deep_pass_contexts: list[list[dict[str, Any]]] = []
    deep_pass_flow_events: list[dict[str, Any]] = []
    deep_beta_reasoning_steps: list[dict[str, Any]] = []
    deep_beta_retrieval_budgets: dict[str, Any] = {}
    deep_beta_chain_status: dict[str, Any] = {}
    deep_beta_parallel_reasoning_nodes: list[dict[str, Any]] = []
    deep_beta_gap_fill_queries: list[str] = []
    deep_beta_evidence_verification: dict[str, Any] = {}
    deep_beta_quality_gate: dict[str, Any] = {}

    def _update_beta_reasoning_step(
        *,
        stage: str,
        status: str,
        note: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        if not deep_beta_reasoning_steps:
            return
        for item in deep_beta_reasoning_steps:
            if str(item.get("stage")) != stage:
                continue
            item["status"] = status
            item["note"] = note
            if isinstance(payload, dict) and payload:
                item["payload"] = payload
            break

    def _refresh_beta_chain_status(*, current_stage: str | None = None, status: str | None = None) -> None:
        if not deep_beta_reasoning_steps:
            return
        total_steps = len(deep_beta_reasoning_steps)
        completed_steps = sum(
            1
            for item in deep_beta_reasoning_steps
            if str(item.get("status") or "").strip().lower() == "completed"
        )
        warning_steps = sum(
            1
            for item in deep_beta_reasoning_steps
            if str(item.get("status") or "").strip().lower() in {"warning", "degraded", "failed"}
        )
        skipped_steps = sum(
            1
            for item in deep_beta_reasoning_steps
            if str(item.get("status") or "").strip().lower() in {"skipped"}
        )
        terminal_steps = completed_steps + warning_steps + skipped_steps
        if not current_stage:
            current_stage = ""
            for item in deep_beta_reasoning_steps:
                state = str(item.get("status") or "").strip().lower()
                if state in {"pending", "started", "running"}:
                    current_stage = str(item.get("stage") or "")
                    break
            if not current_stage and deep_beta_reasoning_steps:
                current_stage = str(deep_beta_reasoning_steps[-1].get("stage") or "")
        if not status:
            if terminal_steps >= total_steps and warning_steps == 0:
                status = "completed"
            elif terminal_steps >= total_steps and warning_steps > 0:
                status = "warning"
            else:
                status = "running"
        deep_beta_chain_status.update(
            {
                "completed_steps": completed_steps,
                "total_steps": total_steps,
                "terminal_steps": terminal_steps,
                "current_stage": current_stage,
                "status": status,
                "warning_steps": warning_steps,
                "skipped_steps": skipped_steps,
            }
        )

    def _apply_query_decomposition(
        legacy_subqueries: list[str],
        *,
        seed_queries: list[str],
    ) -> list[str]:
        """Override the legacy subquery plan with agentic decomposition when enabled (R4).

        When ``RESEARCH_QUERY_DECOMPOSITION_ENABLED`` is off (or the mode is not deep/
        deep_beta) the legacy multi-pass subqueries are returned unchanged so flags-off
        behavior is byte-for-byte preserved (R4.3, R20.2). When on, the query is decomposed
        into an ordered set of sub-questions; retrieval then runs once per sub-question
        (R4.2) and the set is recorded in telemetry via ``search_plan.subqueries`` (R4.4).
        Recording the decomposition flow event is best-effort: a failure is logged and the
        run continues (R4.6).
        """

        if not settings.research_query_decomposition_enabled:
            return legacy_subqueries
        decomposed = decompose_query(
            topic,
            enabled=True,
            mode=research_mode,
            keywords=planner_hints.get("keywords", []),
            seed_queries=seed_queries,
            max_subqueries=max(1, deep_pass_count),
        )
        # R4.5: empty decomposition falls back to the original query.
        resolved = decomposed or [topic]
        try:
            flow_events.append(
                _event(
                    stage="query_decomposition",
                    status="completed",
                    source_count=0,
                    note=f"Query decomposed into {len(resolved)} sub-question(s).",
                    component="planner",
                    payload={
                        "subqueries": resolved,
                        "subquery_count": len(resolved),
                        "research_mode": research_mode,
                    },
                )
            )
        except Exception:  # pragma: no cover - telemetry must never abort the run (R4.6)
            logger.warning("query_decomposition telemetry write failed", exc_info=True)
        return resolved

    if research_mode == "deep":
        query_plan = (
            planner_hints.get("query_plan")
            if isinstance(planner_hints.get("query_plan"), dict)
            else {}
        )
        decomposition = (
            query_plan.get("decomposition") if isinstance(query_plan.get("decomposition"), dict) else {}
        )
        deep_seed_queries = (
            decomposition.get("deep_pass_queries")
            if isinstance(decomposition.get("deep_pass_queries"), list)
            else []
        )
        subqueries = _build_deep_subqueries(
            str(query_plan.get("canonical_query") or topic),
            planner_hints.get("keywords", []),
            deep_pass_count,
            seed_queries=[str(item) for item in deep_seed_queries if str(item).strip()],
        )
        subqueries = _apply_query_decomposition(
            subqueries,
            seed_queries=[str(item) for item in deep_seed_queries if str(item).strip()],
        )
        deep_subqueries = subqueries
        deep_research_method = _deep_research_methodology(topic=topic, subqueries=subqueries)
        deep_research_profiles = [
            {
                "profile": "hypothesis_decomposition",
                "goal": "Tách giả thuyết chính và giả thuyết phản biện.",
                "subquery": subqueries[0] if len(subqueries) > 0 else topic,
            },
            {
                "profile": "breadth_first_evidence_scan",
                "goal": "Mở rộng recall từ guideline/review/trial/safety notes.",
                "subquery": subqueries[1] if len(subqueries) > 1 else topic,
            },
            {
                "profile": "counter_evidence_search",
                "goal": "Tìm bằng chứng trái chiều và điều kiện ngoại lệ.",
                "subquery": subqueries[2] if len(subqueries) > 2 else topic,
            },
            {
                "profile": "cross_source_consistency",
                "goal": "Đối chiếu mức nhất quán giữa nhiều nguồn.",
                "subquery": subqueries[3] if len(subqueries) > 3 else topic,
            },
            {
                "profile": "clinical_synthesis",
                "goal": "Tổng hợp thành khuyến nghị có điều kiện áp dụng.",
                "subquery": subqueries[4] if len(subqueries) > 4 else topic,
            },
        ]
        flow_events.append(
            _event(
                stage="deep_research",
                status="started",
                source_count=0,
                note=f"Deep research mode started with {len(subqueries)} retrieval pass(es).",
                component="planner",
                payload={
                    "pass_count": len(subqueries),
                    "subqueries": subqueries,
                    "keywords": planner_hints.get("keywords", []),
                    "profiles": deep_research_profiles,
                    "methodology": deep_research_method,
                },
            )
        )

        for pass_index, subquery in enumerate(subqueries, start=1):
            pass_started = perf_counter()
            deep_pass_flow_events.append(
                _event(
                    stage="deep_retrieval_pass",
                    status="started",
                    source_count=0,
                    note=f"Deep retrieval pass {pass_index} started.",
                    component="retrieval",
                    payload={"pass_index": pass_index, "subquery": subquery},
                )
            )
            _pause_between_pipeline_parts(multiplier=1.0)
            pass_result = pipeline.run(
                subquery,
                low_context_threshold=float(planner_hints["low_context_threshold"]),
                deepseek_fallback_enabled=deepseek_fallback_enabled,
                scientific_retrieval_enabled=bool(planner_hints["scientific_retrieval_enabled"]),
                web_retrieval_enabled=bool(planner_hints["web_retrieval_enabled"]),
                file_retrieval_enabled=bool(planner_hints["file_retrieval_enabled"]),
                rag_sources=rag_sources,
                uploaded_documents=uploaded_documents,
                planner_hints={
                    **planner_hints,
                    "query_focus": f"deep_pass_{pass_index}",
                    "reason_codes": [
                        *planner_hints.get("reason_codes", []),
                        f"deep_pass_{pass_index}",
                    ],
                },
                generation_enabled=False,
                strict_deepseek_required=strict_deepseek_required,
                rag_reranker_enabled=rag_reranker_enabled_override,
                rag_graphrag_enabled=rag_graphrag_enabled_override,
                llm_runtime=llm_runtime,
            )
            pass_trace = (
                pass_result.trace.get("retrieval")
                if isinstance(pass_result.trace.get("retrieval"), dict)
                else {}
            )
            pass_source_attempts = (
                pass_trace.get("source_attempts")
                if isinstance(pass_trace.get("source_attempts"), list)
                else []
            )
            pass_index_summary = (
                pass_trace.get("index_summary")
                if isinstance(pass_trace.get("index_summary"), dict)
                else {}
            )
            pass_crawl_summary = (
                pass_trace.get("crawl_summary")
                if isinstance(pass_trace.get("crawl_summary"), dict)
                else {}
            )
            retriever_debug = (
                pass_trace.get("hybrid")
                if isinstance(pass_trace.get("hybrid"), dict)
                else pass_trace.get("internal")
                if isinstance(pass_trace.get("internal"), dict)
                else {}
            )
            deep_pass_contexts.append(pass_result.retrieved_context)
            deep_pass_summaries.append(
                {
                    "pass_index": pass_index,
                    "subquery": subquery,
                    "retrieved_count": len(pass_result.retrieved_ids),
                    "doc_ids": list(pass_result.retrieved_ids[:8]),
                    "relevance": pass_result.context_debug.get("relevance")
                    if isinstance(pass_result.context_debug, dict)
                    else None,
                    "duration_ms": round((perf_counter() - pass_started) * 1000.0, 3),
                    "source_errors": retriever_debug.get("source_errors", {})
                    if isinstance(retriever_debug, dict)
                    else {},
                    "source_attempts": pass_source_attempts,
                    "index_summary": pass_index_summary,
                    "crawl_summary": pass_crawl_summary,
                }
            )
            source_errors = (
                deep_pass_summaries[-1].get("source_errors")
                if isinstance(deep_pass_summaries[-1].get("source_errors"), dict)
                else {}
            )
            duration_ms = round((perf_counter() - pass_started) * 1000.0, 3)
            deep_pass_flow_events.extend(
                _normalize_retrieval_events(
                    pass_result.flow_events, default_component="deep_retrieval"
                )
            )
            deep_pass_flow_events.append(
                _event(
                    stage="deep_retrieval_pass",
                    status="completed",
                    source_count=len(pass_result.retrieved_ids),
                    note=f"Deep retrieval pass {pass_index} completed.",
                    component="retrieval",
                    payload={
                        "pass_index": pass_index,
                        "subquery": subquery,
                        "docs_found": list(pass_result.retrieved_ids[:8]),
                        "retrieved_count": len(pass_result.retrieved_ids),
                        "duration_ms": duration_ms,
                        "source_errors": source_errors,
                    },
                    started_at=pass_started,
                )
            )

            # --- R5: bounded iterative gap-fill retrieval -------------------------
            # When a sub-question is below ``rag_min_results`` supporting docs, run
            # additional retrieval pass(es) for that sub-question, bounded by
            # ``RESEARCH_GAP_FILL_MAX_PASSES`` across the whole run (R5.1, R5.2). The
            # loop stops at the bound and synthesis proceeds (R5.3); the executed count
            # is carried into the result/telemetry (R5.4). Disabled flag => no-op.
            gap_fill_min_results = max(1, int(settings.rag_min_results))
            gap_fill_max_passes = max(0, int(settings.research_gap_fill_max_passes))
            combined_retrieved_ids = list(pass_result.retrieved_ids)
            while _gap_fill_should_run(
                len(combined_retrieved_ids),
                enabled=settings.research_gap_fill_enabled,
                min_results=gap_fill_min_results,
                max_passes=gap_fill_max_passes,
                passes_used=deep_gap_fill_passes,
            ):
                deep_gap_fill_passes += 1
                gap_fill_pass_no = deep_gap_fill_passes
                gap_fill_started = perf_counter()
                deep_pass_flow_events.append(
                    _event(
                        stage="deep_gap_fill_pass",
                        status="started",
                        source_count=0,
                        note=(
                            f"Gap-fill retrieval pass {gap_fill_pass_no} started for "
                            f"sub-question {pass_index} (evidence below minimum)."
                        ),
                        component="retrieval",
                        payload={
                            "pass_index": pass_index,
                            "gap_fill_pass": gap_fill_pass_no,
                            "subquery": subquery,
                            "evidence_count": len(combined_retrieved_ids),
                            "min_results": gap_fill_min_results,
                            "max_passes": gap_fill_max_passes,
                        },
                    )
                )
                _pause_between_pipeline_parts(multiplier=1.0)
                gap_fill_result = pipeline.run(
                    subquery,
                    low_context_threshold=float(planner_hints["low_context_threshold"]),
                    deepseek_fallback_enabled=deepseek_fallback_enabled,
                    scientific_retrieval_enabled=bool(planner_hints["scientific_retrieval_enabled"]),
                    web_retrieval_enabled=bool(planner_hints["web_retrieval_enabled"]),
                    file_retrieval_enabled=bool(planner_hints["file_retrieval_enabled"]),
                    rag_sources=rag_sources,
                    uploaded_documents=uploaded_documents,
                    planner_hints={
                        **planner_hints,
                        "query_focus": f"deep_gap_fill_{pass_index}_{gap_fill_pass_no}",
                        "reason_codes": [
                            *planner_hints.get("reason_codes", []),
                            f"deep_gap_fill_{pass_index}_{gap_fill_pass_no}",
                        ],
                    },
                    generation_enabled=False,
                    strict_deepseek_required=strict_deepseek_required,
                    rag_reranker_enabled=rag_reranker_enabled_override,
                    rag_graphrag_enabled=rag_graphrag_enabled_override,
                    llm_runtime=llm_runtime,
                )
                if gap_fill_result.retrieved_context:
                    deep_pass_contexts.append(gap_fill_result.retrieved_context)
                for doc_id in gap_fill_result.retrieved_ids:
                    if doc_id not in combined_retrieved_ids:
                        combined_retrieved_ids.append(doc_id)
                deep_pass_flow_events.extend(
                    _normalize_retrieval_events(
                        gap_fill_result.flow_events, default_component="deep_gap_fill"
                    )
                )
                deep_pass_summaries.append(
                    {
                        "pass_index": pass_index,
                        "gap_fill_pass": gap_fill_pass_no,
                        "subquery": subquery,
                        "retrieved_count": len(gap_fill_result.retrieved_ids),
                        "doc_ids": list(gap_fill_result.retrieved_ids[:8]),
                        "combined_count": len(combined_retrieved_ids),
                        "duration_ms": round((perf_counter() - gap_fill_started) * 1000.0, 3),
                        "kind": "gap_fill",
                    }
                )
                deep_pass_flow_events.append(
                    _event(
                        stage="deep_gap_fill_pass",
                        status="completed",
                        source_count=len(gap_fill_result.retrieved_ids),
                        note=(
                            f"Gap-fill retrieval pass {gap_fill_pass_no} completed for "
                            f"sub-question {pass_index}."
                        ),
                        component="retrieval",
                        payload={
                            "pass_index": pass_index,
                            "gap_fill_pass": gap_fill_pass_no,
                            "subquery": subquery,
                            "retrieved_count": len(gap_fill_result.retrieved_ids),
                            "combined_count": len(combined_retrieved_ids),
                            "duration_ms": round((perf_counter() - gap_fill_started) * 1000.0, 3),
                        },
                        started_at=gap_fill_started,
                    )
                )

        flow_events.extend(deep_pass_flow_events)
        flow_events.append(
            _event(
                stage="deep_research",
                status="completed",
                source_count=sum(item["retrieved_count"] for item in deep_pass_summaries),
                note="Deep retrieval passes completed; moving to final synthesis.",
                component="planner",
                payload={
                    "pass_count": len(deep_pass_summaries),
                    "gap_fill_passes": deep_gap_fill_passes,
                    "keywords": planner_hints.get("keywords", []),
                    "profiles": deep_research_profiles,
                    "methodology": deep_research_method,
                },
            )
        )
    elif research_mode == "deep_beta":
        query_plan = (
            planner_hints.get("query_plan")
            if isinstance(planner_hints.get("query_plan"), dict)
            else {}
        )
        decomposition = (
            query_plan.get("decomposition") if isinstance(query_plan.get("decomposition"), dict) else {}
        )
        deep_seed_queries = (
            decomposition.get("deep_beta_pass_queries")
            if isinstance(decomposition.get("deep_beta_pass_queries"), list)
            else decomposition.get("deep_pass_queries")
            if isinstance(decomposition.get("deep_pass_queries"), list)
            else []
        )
        subqueries = _build_deep_subqueries(
            str(query_plan.get("canonical_query") or topic),
            planner_hints.get("keywords", []),
            deep_pass_count,
            seed_queries=[str(item) for item in deep_seed_queries if str(item).strip()],
        )
        subqueries = _apply_query_decomposition(
            subqueries,
            seed_queries=[str(item) for item in deep_seed_queries if str(item).strip()],
        )
        deep_subqueries = subqueries
        budget_pass_cap = _safe_int(
            (
                planner_hints.get("retrieval_budget", {}).get("pass_cap")
                if isinstance(planner_hints.get("retrieval_budget"), dict)
                else None
            ),
            _DEEP_BETA_PASS_CAP,
        )
        deep_beta_retrieval_budgets = {
            **(
                planner_hints.get("retrieval_budget")
                if isinstance(planner_hints.get("retrieval_budget"), dict)
                else {}
            ),
            "mode": "deep_beta",
            "pass_cap": max(1, budget_pass_cap),
            "target_pass_count": len(subqueries),
            "allocated_pass_count": len(subqueries),
            "per_pass_doc_target": max(4, min(12, _safe_int(planner_hints.get("hybrid_top_k"), 8))),
            "max_total_docs": max(4, min(12, _safe_int(planner_hints.get("hybrid_top_k"), 8)))
            * max(len(subqueries), 1),
        }
        deep_research_method = _deep_beta_research_methodology(
            topic=topic,
            subqueries=subqueries,
            retrieval_budget=deep_beta_retrieval_budgets,
        )
        deep_research_profiles = [
            {
                "profile": "beta_scope_lock",
                "goal": "Khoá phạm vi và điều kiện loại trừ ngay từ đầu.",
                "subquery": subqueries[0] if len(subqueries) > 0 else topic,
            },
            {
                "profile": "beta_hypothesis_map",
                "goal": "Lập bản đồ giả thuyết/chống giả thuyết theo hướng bằng chứng.",
                "subquery": subqueries[1] if len(subqueries) > 1 else topic,
            },
            {
                "profile": "beta_budgeted_recall",
                "goal": "Mở rộng retrieval theo ngân sách pass/source.",
                "subquery": subqueries[2] if len(subqueries) > 2 else topic,
            },
            {
                "profile": "beta_gap_fill",
                "goal": "Lấp khoảng trống bằng chứng sau mỗi pass.",
                "subquery": subqueries[3] if len(subqueries) > 3 else topic,
            },
            {
                "profile": "beta_counter_evidence",
                "goal": "Tập trung tìm bằng chứng trái chiều và ngoại lệ.",
                "subquery": subqueries[4] if len(subqueries) > 4 else topic,
            },
            {
                "profile": "beta_chain_synthesis",
                "goal": "Xây chuỗi lập luận từ bằng chứng đa pass.",
                "subquery": subqueries[5] if len(subqueries) > 5 else topic,
            },
            {
                "profile": "beta_chain_validation",
                "goal": "Đánh dấu mắt xích yếu và mức độ chắc chắn.",
                "subquery": subqueries[6] if len(subqueries) > 6 else topic,
            },
        ]
        deep_beta_reasoning_steps = _build_deep_beta_reasoning_steps(topic=topic, subqueries=subqueries)
        deep_beta_chain_status = {
            "mode": "deep_beta",
            "status": "running",
            "completed_steps": 0,
            "total_steps": len(deep_beta_reasoning_steps),
            "current_stage": "deep_beta_scope",
        }
        _refresh_beta_chain_status(current_stage="deep_beta_scope", status="running")

        flow_events.append(
            _event(
                stage="deep_beta_scope",
                status="started",
                source_count=0,
                note="Deep beta stage started: scope lock.",
                component="planner",
                payload={
                    "reasoning_steps": deep_beta_reasoning_steps,
                    "profiles": deep_research_profiles,
                    "methodology": deep_research_method,
                },
            )
        )
        _update_beta_reasoning_step(
            stage="deep_beta_scope",
            status="completed",
            note="Scope lock completed.",
            payload={"topic": topic},
        )
        _refresh_beta_chain_status(current_stage="deep_beta_hypothesis_map", status="running")
        flow_events.append(
            _event(
                stage="deep_beta_scope",
                status="completed",
                source_count=0,
                note="Deep beta scope locked.",
                component="planner",
                payload={
                    "reasoning_steps": deep_beta_reasoning_steps,
                    "chain_status": deep_beta_chain_status,
                },
            )
        )

        flow_events.append(
            _event(
                stage="deep_beta_hypothesis_map",
                status="started",
                source_count=0,
                note="Deep beta stage started: hypothesis map.",
                component="planner",
                payload={
                    "profiles": deep_research_profiles,
                    "reasoning_steps": deep_beta_reasoning_steps,
                },
            )
        )
        _update_beta_reasoning_step(
            stage="deep_beta_hypothesis_map",
            status="completed",
            note="Hypothesis map completed.",
            payload={"profiles": deep_research_profiles},
        )
        _refresh_beta_chain_status(current_stage="deep_beta_retrieval_budget", status="running")
        flow_events.append(
            _event(
                stage="deep_beta_hypothesis_map",
                status="completed",
                source_count=0,
                note="Deep beta hypothesis map completed.",
                component="planner",
                payload={
                    "reasoning_steps": deep_beta_reasoning_steps,
                    "profiles": deep_research_profiles,
                    "chain_status": deep_beta_chain_status,
                },
            )
        )

        flow_events.append(
            _event(
                stage="deep_beta_retrieval_budget",
                status="started",
                source_count=0,
                note="Deep beta stage started: retrieval budgeting.",
                component="planner",
                payload={"retrieval_budgets": deep_beta_retrieval_budgets},
            )
        )
        _update_beta_reasoning_step(
            stage="deep_beta_retrieval_budget",
            status="completed",
            note="Retrieval budget allocated.",
            payload=deep_beta_retrieval_budgets,
        )
        _refresh_beta_chain_status(current_stage="deep_beta_multi_pass_retrieval", status="running")
        flow_events.append(
            _event(
                stage="deep_beta_retrieval_budget",
                status="completed",
                source_count=0,
                note="Deep beta retrieval budget allocated.",
                component="planner",
                payload={
                    "retrieval_budgets": deep_beta_retrieval_budgets,
                    "reasoning_steps": deep_beta_reasoning_steps,
                    "chain_status": deep_beta_chain_status,
                },
            )
        )
        flow_events.append(
            _event(
                stage="deep_beta_multi_pass_retrieval",
                status="started",
                source_count=0,
                note=f"Deep beta multi-pass retrieval started ({len(subqueries)} pass(es)).",
                component="retrieval",
                payload={
                    "pass_count": len(subqueries),
                    "subqueries": subqueries,
                    "retrieval_budgets": deep_beta_retrieval_budgets,
                    "reasoning_steps": deep_beta_reasoning_steps,
                },
            )
        )

        for pass_index, subquery in enumerate(subqueries, start=1):
            pass_started = perf_counter()
            deep_pass_flow_events.append(
                _event(
                    stage="deep_beta_retrieval_pass",
                    status="started",
                    source_count=0,
                    note=f"Deep beta retrieval pass {pass_index} started.",
                    component="retrieval",
                    payload={
                        "pass_index": pass_index,
                        "subquery": subquery,
                        "retrieval_budgets": deep_beta_retrieval_budgets,
                    },
                )
            )
            _pause_between_pipeline_parts(multiplier=1.0)
            pass_result = pipeline.run(
                subquery,
                low_context_threshold=float(planner_hints["low_context_threshold"]),
                deepseek_fallback_enabled=deepseek_fallback_enabled,
                scientific_retrieval_enabled=bool(planner_hints["scientific_retrieval_enabled"]),
                web_retrieval_enabled=bool(planner_hints["web_retrieval_enabled"]),
                file_retrieval_enabled=bool(planner_hints["file_retrieval_enabled"]),
                rag_sources=rag_sources,
                uploaded_documents=uploaded_documents,
                planner_hints={
                    **planner_hints,
                    "query_focus": f"deep_beta_pass_{pass_index}",
                    "reason_codes": [
                        *planner_hints.get("reason_codes", []),
                        f"deep_beta_pass_{pass_index}",
                    ],
                    "retrieval_budget": deep_beta_retrieval_budgets,
                },
                generation_enabled=False,
                strict_deepseek_required=strict_deepseek_required,
                rag_reranker_enabled=rag_reranker_enabled_override,
                rag_graphrag_enabled=rag_graphrag_enabled_override,
                llm_runtime=llm_runtime,
            )
            pass_trace = (
                pass_result.trace.get("retrieval")
                if isinstance(pass_result.trace.get("retrieval"), dict)
                else {}
            )
            pass_source_attempts = (
                pass_trace.get("source_attempts")
                if isinstance(pass_trace.get("source_attempts"), list)
                else []
            )
            pass_index_summary = (
                pass_trace.get("index_summary")
                if isinstance(pass_trace.get("index_summary"), dict)
                else {}
            )
            pass_crawl_summary = (
                pass_trace.get("crawl_summary")
                if isinstance(pass_trace.get("crawl_summary"), dict)
                else {}
            )
            retriever_debug = (
                pass_trace.get("hybrid")
                if isinstance(pass_trace.get("hybrid"), dict)
                else pass_trace.get("internal")
                if isinstance(pass_trace.get("internal"), dict)
                else {}
            )
            deep_pass_contexts.append(pass_result.retrieved_context)
            deep_pass_summaries.append(
                {
                    "pass_index": pass_index,
                    "subquery": subquery,
                    "retrieved_count": len(pass_result.retrieved_ids),
                    "doc_ids": list(pass_result.retrieved_ids[:8]),
                    "relevance": pass_result.context_debug.get("relevance")
                    if isinstance(pass_result.context_debug, dict)
                    else None,
                    "duration_ms": round((perf_counter() - pass_started) * 1000.0, 3),
                    "source_errors": retriever_debug.get("source_errors", {})
                    if isinstance(retriever_debug, dict)
                    else {},
                    "source_attempts": pass_source_attempts,
                    "index_summary": pass_index_summary,
                    "crawl_summary": pass_crawl_summary,
                    "reasoning_focus": f"deep_beta_pass_{pass_index}",
                    "budget_target_docs": deep_beta_retrieval_budgets.get("per_pass_doc_target"),
                }
            )
            source_errors = (
                deep_pass_summaries[-1].get("source_errors")
                if isinstance(deep_pass_summaries[-1].get("source_errors"), dict)
                else {}
            )
            duration_ms = round((perf_counter() - pass_started) * 1000.0, 3)
            deep_pass_flow_events.extend(
                _normalize_retrieval_events(
                    pass_result.flow_events, default_component="deep_beta_retrieval"
                )
            )
            deep_pass_flow_events.append(
                _event(
                    stage="deep_beta_retrieval_pass",
                    status="completed",
                    source_count=len(pass_result.retrieved_ids),
                    note=f"Deep beta retrieval pass {pass_index} completed.",
                    component="retrieval",
                    payload={
                        "pass_index": pass_index,
                        "subquery": subquery,
                        "docs_found": list(pass_result.retrieved_ids[:8]),
                        "retrieved_count": len(pass_result.retrieved_ids),
                        "duration_ms": duration_ms,
                        "source_errors": source_errors,
                        "pass_summary": deep_pass_summaries[-1],
                    },
                    started_at=pass_started,
                )
            )

        _update_beta_reasoning_step(
            stage="deep_beta_multi_pass_retrieval",
            status="completed",
            note="All deep beta retrieval passes completed.",
            payload={
                "pass_count": len(deep_pass_summaries),
                "pass_summaries": deep_pass_summaries,
            },
        )
        _refresh_beta_chain_status(current_stage="deep_beta_evidence_audit", status="running")
        flow_events.extend(deep_pass_flow_events)
        flow_events.append(
            _event(
                stage="deep_beta_multi_pass_retrieval",
                status="completed",
                source_count=sum(item["retrieved_count"] for item in deep_pass_summaries),
                note="Deep beta multi-pass retrieval completed.",
                component="retrieval",
                payload={
                    "pass_count": len(deep_pass_summaries),
                    "pass_summaries": deep_pass_summaries,
                    "retrieval_budgets": deep_beta_retrieval_budgets,
                    "reasoning_steps": deep_beta_reasoning_steps,
                    "chain_status": deep_beta_chain_status,
                },
            )
        )

        parallel_started = perf_counter()
        flow_events.append(
            _event(
                stage="deep_beta_parallel_reasoning",
                status="started",
                source_count=len(deep_pass_summaries),
                note="Running parallel Deep Beta LLM reasoning nodes for evidence audit.",
                component="verifier",
                payload={
                    "nodes_target": min(
                        int(settings.deep_beta_reasoning_llm_nodes),
                        6,
                    ),
                    "parallel_workers": int(settings.deep_beta_reasoning_parallel_workers),
                    "reasoning_rounds": int(settings.deep_beta_reasoning_rounds),
                },
            )
        )
        selected_parallel_nodes = list(
            _DEEP_BETA_PARALLEL_REASONING_NODES[
                : max(1, min(int(settings.deep_beta_reasoning_llm_nodes), len(_DEEP_BETA_PARALLEL_REASONING_NODES)))
            ]
        )
        for node_name, node_objective in selected_parallel_nodes:
            flow_events.append(
                _event(
                    stage=node_name,
                    status="started",
                    source_count=len(deep_pass_summaries),
                    note="Reasoning node started.",
                    component="verifier",
                    payload={
                        "node": node_name,
                        "objective": node_objective,
                        "reasoning_rounds": int(settings.deep_beta_reasoning_rounds),
                    },
                )
            )
        deep_beta_parallel_reasoning_nodes = _run_deep_beta_parallel_reasoning_nodes(
            topic=topic,
            query_plan=query_plan if isinstance(query_plan, dict) else {},
            retrieval_budget=deep_beta_retrieval_budgets,
            deep_pass_summaries=deep_pass_summaries,
            evidence_rows=_merge_retrieved_context([], deep_pass_contexts),
            llm_runtime=llm_runtime,
        )
        completed_parallel_nodes = 0
        for node_result in deep_beta_parallel_reasoning_nodes:
            node_name = str(node_result.get("node") or "deep_beta_parallel_node")
            node_status = str(node_result.get("status") or "degraded").strip().lower()
            mapped_status = "completed" if node_status == "completed" else "warning"
            if mapped_status == "completed":
                completed_parallel_nodes += 1
            node_note = (
                "Reasoning node completed."
                if mapped_status == "completed"
                else f"Reasoning node degraded ({node_result.get('reason') or 'unknown'})."
            )
            _update_beta_reasoning_step(
                stage=node_name,
                status=mapped_status,
                note=node_note,
                payload=node_result,
            )
            flow_events.append(
                _event(
                    stage=node_name,
                    status=mapped_status,
                    source_count=len(deep_pass_summaries),
                    note=node_note,
                    component="verifier",
                    payload=node_result,
                )
            )
        _refresh_beta_chain_status(current_stage="deep_beta_gap_fill", status="running")
        flow_events.append(
            _event(
                stage="deep_beta_parallel_reasoning",
                status="completed" if completed_parallel_nodes else "warning",
                source_count=len(deep_beta_parallel_reasoning_nodes),
                note="Parallel Deep Beta reasoning nodes finished.",
                component="verifier",
                payload={
                    "completed_nodes": completed_parallel_nodes,
                    "total_nodes": len(deep_beta_parallel_reasoning_nodes),
                    "nodes": deep_beta_parallel_reasoning_nodes,
                },
                started_at=parallel_started,
            )
        )

        deep_beta_gap_fill_queries = _collect_reasoning_follow_up_queries(
            deep_beta_parallel_reasoning_nodes,
            limit=max(int(settings.deep_beta_gap_fill_max_queries), 1),
        )
        gap_fill_pass_cap = max(0, int(settings.deep_beta_gap_fill_max_passes))
        if deep_beta_gap_fill_queries and gap_fill_pass_cap > 0:
            gap_fill_started = perf_counter()
            _update_beta_reasoning_step(
                stage="deep_beta_gap_fill",
                status="started",
                note="Targeted gap-fill retrieval started.",
                payload={
                    "queries": deep_beta_gap_fill_queries[:gap_fill_pass_cap],
                    "pass_cap": gap_fill_pass_cap,
                },
            )
            flow_events.append(
                _event(
                    stage="deep_beta_gap_fill",
                    status="started",
                    source_count=0,
                    note="Deep beta targeted gap-fill retrieval started.",
                    component="retrieval",
                    payload={
                        "query_count": len(deep_beta_gap_fill_queries),
                        "pass_cap": gap_fill_pass_cap,
                        "queries": deep_beta_gap_fill_queries[:gap_fill_pass_cap],
                    },
                )
            )
            executed_gap_fill_passes = 0
            for query_index, gap_query in enumerate(deep_beta_gap_fill_queries[:gap_fill_pass_cap], start=1):
                pass_started = perf_counter()
                flow_events.append(
                    _event(
                        stage="deep_beta_gap_fill_pass",
                        status="started",
                        source_count=0,
                        note=f"Deep beta gap-fill pass {query_index} started.",
                        component="retrieval",
                        payload={"pass_index": query_index, "subquery": gap_query},
                    )
                )
                _pause_between_pipeline_parts(multiplier=0.9)
                pass_result = pipeline.run(
                    gap_query,
                    low_context_threshold=float(planner_hints["low_context_threshold"]),
                    deepseek_fallback_enabled=deepseek_fallback_enabled,
                    scientific_retrieval_enabled=bool(planner_hints["scientific_retrieval_enabled"]),
                    web_retrieval_enabled=bool(planner_hints["web_retrieval_enabled"]),
                    file_retrieval_enabled=bool(planner_hints["file_retrieval_enabled"]),
                    rag_sources=rag_sources,
                    uploaded_documents=uploaded_documents,
                    planner_hints={
                        **planner_hints,
                        "query_focus": f"deep_beta_gap_fill_{query_index}",
                        "reason_codes": [
                            *planner_hints.get("reason_codes", []),
                            f"deep_beta_gap_fill_{query_index}",
                        ],
                    },
                    generation_enabled=False,
                    strict_deepseek_required=strict_deepseek_required,
                    rag_reranker_enabled=rag_reranker_enabled_override,
                    rag_graphrag_enabled=rag_graphrag_enabled_override,
                    llm_runtime=llm_runtime,
                )
                deep_pass_contexts.append(pass_result.retrieved_context)
                deep_pass_summaries.append(
                    {
                        "pass_index": len(deep_pass_summaries) + 1,
                        "subquery": gap_query,
                        "retrieved_count": len(pass_result.retrieved_ids),
                        "doc_ids": list(pass_result.retrieved_ids[:8]),
                        "relevance": pass_result.context_debug.get("relevance")
                        if isinstance(pass_result.context_debug, dict)
                        else None,
                        "duration_ms": round((perf_counter() - pass_started) * 1000.0, 3),
                        "source_errors": {},
                        "source_attempts": [],
                        "index_summary": {},
                        "crawl_summary": {},
                        "reasoning_focus": f"deep_beta_gap_fill_{query_index}",
                        "budget_target_docs": deep_beta_retrieval_budgets.get("per_pass_doc_target"),
                    }
                )
                flow_events.extend(
                    _normalize_retrieval_events(
                        pass_result.flow_events, default_component="deep_beta_retrieval"
                    )
                )
                flow_events.append(
                    _event(
                        stage="deep_beta_gap_fill_pass",
                        status="completed",
                        source_count=len(pass_result.retrieved_ids),
                        note=f"Deep beta gap-fill pass {query_index} completed.",
                        component="retrieval",
                        payload={
                            "pass_index": query_index,
                            "subquery": gap_query,
                            "retrieved_count": len(pass_result.retrieved_ids),
                        },
                        started_at=pass_started,
                    )
                )
                executed_gap_fill_passes += 1
            _update_beta_reasoning_step(
                stage="deep_beta_gap_fill",
                status="completed" if executed_gap_fill_passes else "warning",
                note=(
                    "Targeted gap-fill retrieval completed."
                    if executed_gap_fill_passes
                    else "No effective docs retrieved from gap-fill queries."
                ),
                payload={
                    "executed_passes": executed_gap_fill_passes,
                    "queries": deep_beta_gap_fill_queries[:gap_fill_pass_cap],
                },
            )
            flow_events.append(
                _event(
                    stage="deep_beta_gap_fill",
                    status="completed" if executed_gap_fill_passes else "warning",
                    source_count=executed_gap_fill_passes,
                    note=(
                        "Deep beta targeted gap-fill retrieval completed."
                        if executed_gap_fill_passes
                        else "Deep beta gap-fill did not add strong evidence."
                    ),
                    component="retrieval",
                    payload={
                        "executed_passes": executed_gap_fill_passes,
                        "queries": deep_beta_gap_fill_queries[:gap_fill_pass_cap],
                    },
                    started_at=gap_fill_started,
                )
            )
        else:
            _update_beta_reasoning_step(
                stage="deep_beta_gap_fill",
                status="skipped",
                note="Gap-fill retrieval skipped (no follow-up queries or pass cap=0).",
                payload={
                    "query_count": len(deep_beta_gap_fill_queries),
                    "pass_cap": gap_fill_pass_cap,
                },
            )
            flow_events.append(
                _event(
                    stage="deep_beta_gap_fill",
                    status="skipped",
                    source_count=0,
                    note="Gap-fill retrieval skipped.",
                    component="retrieval",
                    payload={
                        "query_count": len(deep_beta_gap_fill_queries),
                        "pass_cap": gap_fill_pass_cap,
                    },
                )
            )

        _refresh_beta_chain_status(current_stage="deep_beta_evidence_verification", status="running")
        evidence_verify_started = perf_counter()
        flow_events.append(
            _event(
                stage="deep_beta_evidence_verification",
                status="started",
                source_count=len(deep_pass_summaries),
                note="Deep beta evidence verification node started.",
                component="verifier",
                payload={
                    "reasoning_node_count": len(deep_beta_parallel_reasoning_nodes),
                    "pass_count": len(deep_pass_summaries),
                },
            )
        )
        deep_beta_evidence_verification = _run_deep_beta_evidence_verification_node(
            topic=topic,
            deep_pass_summaries=deep_pass_summaries,
            evidence_rows=_merge_retrieved_context([], deep_pass_contexts),
            reasoning_nodes=deep_beta_parallel_reasoning_nodes,
            llm_runtime=llm_runtime,
        )
        evidence_verification_status = str(
            deep_beta_evidence_verification.get("status") or "degraded"
        ).strip().lower()
        mapped_evidence_status = (
            "completed" if evidence_verification_status == "completed" else "warning"
        )
        _update_beta_reasoning_step(
            stage="deep_beta_evidence_verification",
            status=mapped_evidence_status,
            note=(
                "Evidence verification completed."
                if mapped_evidence_status == "completed"
                else "Evidence verification degraded."
            ),
            payload=deep_beta_evidence_verification,
        )
        flow_events.append(
            _event(
                stage="deep_beta_evidence_verification",
                status=mapped_evidence_status,
                source_count=len(deep_pass_summaries),
                note=(
                    "Deep beta evidence verification completed."
                    if mapped_evidence_status == "completed"
                    else "Deep beta evidence verification degraded."
                ),
                component="verifier",
                payload=deep_beta_evidence_verification,
                started_at=evidence_verify_started,
            )
        )

        _refresh_beta_chain_status(current_stage="deep_beta_chain_synthesis", status="running")
        flow_events.append(
            _event(
                stage="deep_beta_chain_synthesis",
                status="started",
                source_count=len(deep_pass_summaries),
                note="Deep beta chain synthesis started.",
                component="planner",
                payload={
                    "pass_summaries": deep_pass_summaries,
                    "reasoning_steps": deep_beta_reasoning_steps,
                },
            )
        )
        _update_beta_reasoning_step(
            stage="deep_beta_chain_synthesis",
            status="completed",
            note="Deep beta chain synthesis prepared for final answer generation.",
            payload={"pass_summaries": deep_pass_summaries},
        )
        _refresh_beta_chain_status(current_stage="deep_beta_chain_verification", status="running")
        flow_events.append(
            _event(
                stage="deep_beta_chain_synthesis",
                status="completed",
                source_count=len(deep_pass_summaries),
                note="Deep beta chain synthesis completed.",
                component="planner",
                payload={
                    "reasoning_steps": deep_beta_reasoning_steps,
                    "chain_status": deep_beta_chain_status,
                },
            )
        )

    rag_result = pipeline.run(
        topic,
        low_context_threshold=float(planner_hints["low_context_threshold"]),
        deepseek_fallback_enabled=deepseek_fallback_enabled,
        scientific_retrieval_enabled=bool(planner_hints["scientific_retrieval_enabled"]),
        web_retrieval_enabled=bool(planner_hints["web_retrieval_enabled"]),
        file_retrieval_enabled=bool(planner_hints["file_retrieval_enabled"]),
        rag_sources=rag_sources,
        uploaded_documents=uploaded_documents,
        planner_hints=planner_hints,
        generation_enabled=True,
        strict_deepseek_required=strict_deepseek_required,
        rag_reranker_enabled=rag_reranker_enabled_override,
        rag_graphrag_enabled=rag_graphrag_enabled_override,
        llm_runtime=llm_runtime,
    )
    if strict_deepseek_required and (
        rag_result.model_used.startswith("local-synth")
        or "fallback" in rag_result.model_used.lower()
    ):
        raise RuntimeError("tier2_deepseek_required_violation")
    retrieval_trace = _build_retrieval_trace(rag_result=rag_result, planner_hints=planner_hints)
    retrieval_trace["trace_id"] = trace_id
    retrieval_trace["run_id"] = run_id
    if research_mode in {"deep", "deep_beta"}:
        retrieval_trace["deep_pass_summaries"] = deep_pass_summaries
        retrieval_trace["deep_pass_count"] = len(deep_pass_summaries)
    if research_mode == "deep_beta":
        retrieval_trace["reasoning_steps"] = deep_beta_reasoning_steps
        retrieval_trace["retrieval_budgets"] = deep_beta_retrieval_budgets
        retrieval_trace["chain_status"] = deep_beta_chain_status
    flow_events.extend(_normalize_retrieval_events(rag_result.flow_events))

    merged_context = _merge_retrieved_context(rag_result.retrieved_context, deep_pass_contexts)
    filtered_context = _filter_context_for_topic(topic, merged_context)
    if filtered_context:
        effective_context = filtered_context
    elif _is_drug_interaction_query(topic):
        # For DDI queries, prefer filtered rows; if filter is too strict and returns empty,
        # gracefully fall back to merged retrieval evidence instead of an empty context.
        effective_context = merged_context[:10]
    else:
        effective_context = merged_context

    evidence_review_started = perf_counter()
    flow_events.append(
        _event(
            stage="evidence_review",
            status="started",
            source_count=len(effective_context),
            note="Evidence review node started.",
            component="verifier",
            payload={
                "deep_pass_count": len(deep_pass_summaries),
                "context_rows": len(effective_context),
            },
        )
    )
    evidence_review_summary = _build_evidence_review_summary(
        effective_context=effective_context,
        deep_pass_summaries=deep_pass_summaries,
        evidence_verification=deep_beta_evidence_verification,
    )
    evidence_review_status = str(evidence_review_summary.get("status") or "warning")
    pipeline_node_steps.append(
        {
            "stage": "evidence_review",
            "status": evidence_review_status,
            "note": str(evidence_review_summary.get("note") or "Evidence review completed."),
            "payload": evidence_review_summary,
        }
    )
    flow_events.append(
        _event(
            stage="evidence_review",
            status=evidence_review_status,
            source_count=len(effective_context),
            note=str(evidence_review_summary.get("note") or "Evidence review completed."),
            component="verifier",
            payload=evidence_review_summary,
            started_at=evidence_review_started,
        )
    )

    citation_handoff = _resolve_evidence_handoff_profile(research_mode)
    # R6.1: composite recency/trust-tier ranking is gated on its flag; default-off preserves the
    # legacy citation ordering and shape (R20.2).
    recency_trust_ranking_enabled = settings.research_recency_trust_ranking_enabled
    citation_context = effective_context
    if research_mode == "deep_beta" and len(citation_context) < citation_handoff["citation_context_rows"]:
        citation_context = _merge_retrieved_context(citation_context, [merged_context])

    citations = _build_citations(
        topic,
        citation_context,
        uploaded_documents,
        research_mode=research_mode,
        rank_enabled=recency_trust_ranking_enabled,
    )
    if not citations and merged_context:
        citations = _build_citations(
            topic,
            merged_context[: citation_handoff["citation_context_rows"]],
            uploaded_documents,
            research_mode=research_mode,
            rank_enabled=recency_trust_ranking_enabled,
        )
    if not citations:
        trace_rows = _trace_rows_for_citation(retrieval_trace, research_mode=research_mode)
        if trace_rows:
            citations = _build_citations(
                topic,
                trace_rows,
                uploaded_documents,
                research_mode=research_mode,
                rank_enabled=recency_trust_ranking_enabled,
            )
    fallback_used = _infer_fallback_used(rag_result)
    generation_trace = (
        rag_result.trace.get("generation")
        if isinstance(getattr(rag_result, "trace", None), dict)
        and isinstance(rag_result.trace.get("generation"), dict)
        else {}
    )
    fallback_reason_raw = generation_trace.get("fallback_reason")
    fallback_reason = str(fallback_reason_raw).strip() if fallback_reason_raw is not None else ""
    if fallback_used and not fallback_reason:
        fallback_reason = "llm_unavailable_or_failed"
    if not citations:
        citations = [
            Citation(
                source_id="fallback-safe-1",
                source="system_fallback",
                title="Safety fallback notice",
                url="",
                relevance="Fallback an toàn khi nguồn truy xuất chưa đủ ổn định.",
            )
        ]

    synthesis_started = perf_counter()
    flow_events.append(
        _event(
            stage="answer_synthesis",
            status="started",
            source_count=len(effective_context),
            note="Preparing final markdown answer from retrieved evidence.",
            component="postprocess",
            payload={
                "retrieved_count": len(rag_result.retrieved_ids),
                "citation_count": len(citations),
                "model_used": rag_result.model_used,
            },
        )
    )
    answer_markdown = _ensure_markdown_structure(
        topic,
        rag_result.answer,
        citations,
        research_mode=research_mode,
        plan_steps=plan_steps,
        answer_language=answer_language,
    )
    if research_mode in {"deep", "deep_beta"}:
        report_stage = "deep_beta_report_synthesis" if research_mode == "deep_beta" else "deep_report_synthesis"
        report_mode_label = "Deep Beta" if research_mode == "deep_beta" else "Deep"
        report_started = perf_counter()
        flow_events.append(
            _event(
                stage=report_stage,
                status="started",
                source_count=len(citations),
                note=f"{report_mode_label} long-form report synthesis started.",
                component="postprocess",
                payload={
                    "citation_count": len(citations),
                    "reasoning_node_count": len(deep_beta_parallel_reasoning_nodes),
                    "deep_pass_count": len(deep_pass_summaries),
                },
            )
        )
        rewritten_report = _synthesize_deep_beta_long_report(
            topic=topic,
            answer_markdown=answer_markdown,
            citations=citations,
            verification_matrix_payload={},
            reasoning_nodes=deep_beta_parallel_reasoning_nodes,
            deep_pass_summaries=deep_pass_summaries,
            evidence_verification=deep_beta_evidence_verification,
            llm_runtime=llm_runtime,
            research_mode=research_mode,
            answer_language=answer_language,
        )
        report_changed = bool(
            str(rewritten_report or "").strip()
            and str(rewritten_report).strip() != str(answer_markdown).strip()
        )
        if report_changed:
            answer_markdown = _ensure_markdown_structure(
                topic,
                rewritten_report,
                citations,
                research_mode=research_mode,
                plan_steps=plan_steps,
                answer_language=answer_language,
            )
            if research_mode == "deep_beta":
                _update_beta_reasoning_step(
                    stage="deep_beta_report_synthesis",
                    status="completed",
                    note="Deep beta report synthesis completed with LLM long-form output.",
                    payload={"answer_chars": len(answer_markdown)},
                )
                _refresh_beta_chain_status(current_stage="deep_beta_chain_verification", status="running")
        else:
            if research_mode == "deep_beta":
                _update_beta_reasoning_step(
                    stage="deep_beta_report_synthesis",
                    status="warning",
                    note="Deep beta report synthesis fell back to baseline answer.",
                    payload={"answer_chars": len(answer_markdown)},
                )
                _refresh_beta_chain_status(current_stage="deep_beta_chain_verification", status="warning")
        flow_events.append(
            _event(
                stage=report_stage,
                status="completed" if report_changed else "warning",
                source_count=len(citations),
                note=(
                    f"{report_mode_label} long-form report synthesized."
                    if report_changed
                    else f"{report_mode_label} report synthesis degraded; baseline report retained."
                ),
                component="postprocess",
                payload={
                    "report_changed": report_changed,
                    "answer_chars": len(answer_markdown),
                    "target_min_words": int(settings.deep_beta_report_min_words),
                },
                started_at=report_started,
            )
        )
    if research_mode in {"deep", "deep_beta"}:
        answer_markdown = _sanitize_deep_beta_markdown_output(answer_markdown)
        answer_markdown = _ensure_deep_beta_report_artifacts(
            markdown_text=answer_markdown,
            deep_pass_summaries=deep_pass_summaries,
            reasoning_nodes=deep_beta_parallel_reasoning_nodes,
            evidence_verification=deep_beta_evidence_verification,
            verification_summary={},
            research_mode=research_mode,
        )
    answer_markdown = _sanitize_user_facing_answer_markdown(
        answer_markdown,
        research_mode=research_mode,
        answer_language=answer_language,
        fallback_used=fallback_used,
    )
    if not answer_markdown.strip():
        answer_markdown = (
            "## Quick conclusion\n"
            "Retrieval and synthesis completed, but the answer body was compacted automatically for stable display.\n\n"
            "## Detailed analysis\n"
            "Use the evidence and citation panels to inspect the underlying sources more closely.\n\n"
            "## Safety recommendations\n"
            "- Do not change treatment without qualified clinical advice.\n"
            "- Seek direct medical attention promptly if severe symptoms develop."
            if answer_language == "en"
            else "## Kết luận nhanh\n"
            "Đã hoàn tất truy xuất và tổng hợp, nhưng nội dung cần hiển thị đã được rút gọn tự động.\n\n"
            "## Phân tích chi tiết\n"
            "Vui lòng xem bảng Evidence/Citation ở panel bên phải để kiểm tra nguồn và đối chiếu thêm.\n\n"
            "## Khuyến nghị an toàn\n"
            "- Không tự ý thay đổi điều trị nếu chưa có tư vấn chuyên môn.\n"
            "- Khi có dấu hiệu nặng, ưu tiên liên hệ cơ sở y tế ngay."
        )
    # R14 Role-Adaptive Output (gated). Select exactly one output profile by role and
    # retain the decision-support disclaimer in every profile; when the disclaimer
    # asset is unavailable the output is delivered without it and the omission is
    # recorded (disclaimer_present=False, R14.5/R14.6). Both values are carried through
    # the additive Tier2 payload builder. When the flag is off both stay None so the
    # legacy payload shape is preserved (R20.2).
    output_profile: str | None = None
    disclaimer_present: bool | None = None
    if settings.research_role_adaptive_output_enabled:
        answer_markdown, output_profile, disclaimer_present = _apply_role_adaptive_output(
            answer_markdown,
            role=route.role,
            answer_language=answer_language,
        )
    answer_status = "warning" if fallback_used else "completed"
    flow_events.append(
        _event(
            stage="answer_synthesis",
            status=answer_status,
            source_count=len(citations),
            note="Final markdown answer assembled.",
            component="postprocess",
            payload={
                "citation_count": len(citations),
                "fallback_used": fallback_used,
                "answer_chars": len(answer_markdown),
            },
            started_at=synthesis_started,
        )
    )
    if rule_verification_enabled:
        try:
            factcheck_result = run_fides_lite(
                answer=answer_markdown,
                retrieved_context=effective_context,
                nli_enabled=rag_nli_enabled_runtime,
            )
        except TypeError as type_exc:
            if "unexpected keyword argument" not in str(type_exc):
                raise
            factcheck_result = run_fides_lite(
                answer=answer_markdown,
                retrieved_context=effective_context,
            )
        policy_action = "allow" if factcheck_result.verdict == "pass" else "warn"
        verification_state = "verified" if policy_action == "allow" else "warning"
    else:
        factcheck_result = FactCheckResult(
            enabled=False,
            stage="verification-skipped-v1",
            verdict="pass",
            confidence=1.0,
            supported_claims=0,
            total_claims=0,
            unsupported_claims=[],
            evidence_count=len(effective_context),
            severity="low",
            note="Rule verification disabled by flow flag.",
            verification_matrix=[],
            contradiction_summary={
                "version": "claim-v2-nli",
                "has_contradiction": False,
                "contradiction_count": 0,
                "claims": [],
                "details": [],
                "note": "Verification skipped.",
            },
            fide_report={},
        )
        policy_action = "allow"
        verification_state = "skipped"
    verification_matrix_rows = _compact_verification_matrix_rows(
        getattr(factcheck_result, "verification_matrix", []),
        max_items=20,
        max_snippet_len=180,
    )
    verification_matrix_summary = _summarize_verification_matrix(
        verification_matrix_rows,
        total_claims=factcheck_result.total_claims,
        supported_claims=factcheck_result.supported_claims,
    )
    contradiction_summary = _build_contradiction_summary(
        verification_matrix_rows,
        getattr(factcheck_result, "contradiction_summary", {}),
        fallback_note=factcheck_result.note if factcheck_result.verdict == "fail" else "",
    )
    verification_matrix_payload = {
        "version": str(verification_matrix_summary.get("version") or "claim-v2-nli"),
        "rows": verification_matrix_rows,
        "summary": verification_matrix_summary,
        "contradiction_summary": contradiction_summary,
    }
    # GRADE evidence-certainty + recommendation-strength labeling (R8). Derived from the
    # verification-matrix key claims and the strongest supporting source's Evidence-Hierarchy
    # rank + trust_tier. Returns None when the flag is off so the optional `grade` field is
    # omitted and the legacy payload shape is preserved (R8.5, R20.2).
    grade_labels = _assign_grade_labels(
        verification_matrix_rows,
        effective_context,
        enabled=settings.research_grade_enabled,
    )
    # Evidence-agreement (Consensus) view + conflicting-evidence section (R9). Per-claim
    # support/contrast/neutral counts are derived from the per-source NLI verdict (reusing
    # classify_claim). Both return None when the flag is off so the optional payload fields are
    # omitted and the legacy result shape is preserved (R9.1, R9.2, R9.4, R20.2).
    consensus_view, conflicting_evidence = _compute_consensus_view(
        verification_rows=verification_matrix_rows,
        retrieved_context=effective_context,
        enabled=settings.research_consensus_enabled,
    )
    # Claim-to-study traceability + Citation Registry (R11). Links each supported key claim to its
    # specific supporting citation id(s), attaches per-citation provenance (study_id/source_type/
    # trust_tier/date), and builds the registry appendix. Returns (None, None) when the flag is off
    # so the optional payload fields are omitted and the legacy result shape is preserved (R20.2).
    traced_claims, citation_registry = _build_claim_trace(
        verification_rows=verification_matrix_rows,
        citations=citations,
        retrieved_context=effective_context,
        grade_labels=grade_labels,
        enabled=settings.research_claim_trace_enabled,
    )
    if rule_verification_enabled:
        safety_override = _evaluate_safety_critical_override(
            rows=verification_matrix_rows,
            nli_enabled=rag_nli_enabled_runtime,
        )
    else:
        safety_override = {
            "applied": False,
            "status": "skipped",
            "reason": "rule_verification_disabled",
            "note": "Rule verification disabled by flow flag.",
            "policy_action": policy_action,
            "verification_state": verification_state,
            "claims": [],
            "affected_claim_count": 0,
        }
    if bool(safety_override.get("applied")):
        policy_action = str(safety_override.get("policy_action") or policy_action)
        verification_state = str(safety_override.get("verification_state") or verification_state)
        severity_override = str(safety_override.get("severity_override") or "").strip().lower()
        if severity_override:
            factcheck_result.severity = severity_override
        flow_events.append(
            _event(
                stage="safety_override",
                status=str(safety_override.get("status") or "warning"),
                source_count=_safe_int(safety_override.get("affected_claim_count"), 0),
                note=str(safety_override.get("note") or "Safety override applied."),
                component="policy",
                payload={
                    "reason": safety_override.get("reason"),
                    "policy_action": policy_action,
                    "verification_state": verification_state,
                    "claims": safety_override.get("claims", []),
                    "affected_claim_count": _safe_int(
                        safety_override.get("affected_claim_count"),
                        0,
                    ),
                },
            )
        )
    verification_matrix_payload["safety_override"] = safety_override
    if research_mode == "deep_beta":
        quality_gate_started = perf_counter()
        flow_events.append(
            _event(
                stage="deep_beta_quality_gate",
                status="started",
                source_count=len(citations),
                note="Deep beta quality gate started.",
                component="verifier",
                payload={
                    "reasoning_nodes": deep_beta_parallel_reasoning_nodes,
                    "citation_count": len(citations),
                    "evidence_verification_status": deep_beta_evidence_verification.get("status"),
                },
            )
        )
        deep_beta_quality_gate = _run_deep_beta_quality_gate(
            topic=topic,
            answer_markdown=answer_markdown,
            citations=citations,
            verification_matrix_payload=verification_matrix_payload,
            reasoning_nodes=deep_beta_parallel_reasoning_nodes,
            evidence_verification=deep_beta_evidence_verification,
            llm_runtime=llm_runtime,
        )
        gate_status = str(deep_beta_quality_gate.get("status") or "degraded").strip().lower()
        gate_quality_score = _safe_float(deep_beta_quality_gate.get("quality_score"), 0.0)
        if gate_status == "completed" and gate_quality_score >= 0.65:
            gate_event_status = "completed"
        elif gate_status == "completed":
            gate_event_status = "warning"
        elif gate_status == "skipped":
            gate_event_status = "skipped"
        else:
            gate_event_status = "degraded"
        _update_beta_reasoning_step(
            stage="deep_beta_quality_gate",
            status=gate_event_status,
            note=(
                "Deep beta quality gate completed."
                if gate_event_status == "completed"
                else "Deep beta quality gate requires manual review."
            ),
            payload=deep_beta_quality_gate,
        )
        _refresh_beta_chain_status(
            current_stage="deep_beta_chain_verification",
            status="warning" if gate_event_status in {"warning", "degraded"} else "running",
        )
        flow_events.append(
            _event(
                stage="deep_beta_quality_gate",
                status=gate_event_status,
                source_count=len(citations),
                note=(
                    "Deep beta quality gate completed."
                    if gate_event_status == "completed"
                    else "Deep beta quality gate flagged potential quality risks."
                ),
                component="verifier",
                payload=deep_beta_quality_gate,
                started_at=quality_gate_started,
            )
        )
    verifier_trace = _build_verifier_trace(
        factcheck_result=factcheck_result,
        policy_action=policy_action,
        verification_state=verification_state,
        verification_matrix=verification_matrix_payload,
    )
    verifier_trace["trace_id"] = trace_id
    verifier_trace["run_id"] = run_id
    verification_status = {
        "state": verification_state,
        "stage": factcheck_result.stage,
        "verdict": factcheck_result.verdict,
        "severity": factcheck_result.severity,
        "confidence": factcheck_result.confidence,
        "evidence_count": factcheck_result.evidence_count,
        "note": factcheck_result.note,
        "verification_matrix": {
            "summary": verification_matrix_summary,
            "contradiction_summary": contradiction_summary,
            "safety_override": safety_override,
        },
    }
    if research_mode == "deep_beta":
        flow_events.append(
            _event(
                stage="deep_beta_chain_verification",
                status="started",
                source_count=len(deep_pass_summaries),
                note="Deep beta chain verification started.",
                component="verifier",
                payload={
                    "reasoning_steps": deep_beta_reasoning_steps,
                    "chain_status": deep_beta_chain_status,
                    "pass_summaries": deep_pass_summaries,
                },
            )
        )
    if rule_verification_enabled:
        flow_events.append(
            _event(
                stage="verification",
                status="started",
                source_count=factcheck_result.evidence_count,
                note="Verifier started evidence consistency checks.",
                component="verifier",
                payload={"verifier": factcheck_result.stage},
            )
        )
        flow_events.append(
            _event(
                stage="verification",
                status=factcheck_result.verdict,
                source_count=factcheck_result.evidence_count,
                note=factcheck_result.note,
                component="verifier",
                payload={
                    "confidence": factcheck_result.confidence,
                    "severity": factcheck_result.severity,
                    "supported_claims": factcheck_result.supported_claims,
                    "total_claims": factcheck_result.total_claims,
                },
            )
        )
    else:
        flow_events.append(
            _event(
                stage="verification",
                status="skipped",
                source_count=0,
                note="Rule verification disabled by flow flag.",
                component="verifier",
                payload={"verifier": "disabled"},
            )
        )
    contradiction_stage_status = (
        "warning" if bool(contradiction_summary.get("has_contradiction")) else "completed"
    )
    flow_events.append(
        _event(
            stage="contradiction_miner",
            status=contradiction_stage_status,
            source_count=_safe_int(contradiction_summary.get("contradiction_count"), 0),
            note=str(contradiction_summary.get("note") or "Contradiction miner completed."),
            component="verifier",
            payload={
                "has_contradiction": bool(contradiction_summary.get("has_contradiction")),
                "contradiction_count": _safe_int(
                    contradiction_summary.get("contradiction_count"),
                    0,
                ),
                "claims": contradiction_summary.get("claims", []),
                "details": contradiction_summary.get("details", []),
                "summary": contradiction_summary,
            },
        )
    )
    flow_events.append(
        _event(
            stage="verification_matrix",
            status="completed",
            source_count=factcheck_result.evidence_count,
            note="Verification matrix generated from claim-level factcheck outputs.",
            component="verifier",
            payload={
                "supported_claims": factcheck_result.supported_claims,
                "unsupported_claims": len(factcheck_result.unsupported_claims),
                "total_claims": factcheck_result.total_claims,
                "severity": factcheck_result.severity,
                "confidence": factcheck_result.confidence,
                "summary": verification_matrix_summary,
                "rows": verification_matrix_rows,
                "contradiction_summary": contradiction_summary,
            },
        )
    )
    if research_mode == "deep_beta":
        chain_verification_status = (
            "warning"
            if contradiction_summary.get("has_contradiction") or factcheck_result.verdict != "pass"
            else "completed"
        )
        _update_beta_reasoning_step(
            stage="deep_beta_chain_verification",
            status=chain_verification_status,
            note="Deep beta chain verification completed.",
            payload={
                "verdict": factcheck_result.verdict,
                "support_ratio": verification_matrix_summary.get("support_ratio"),
                "contradiction_count": contradiction_summary.get("contradiction_count"),
            },
        )
        _refresh_beta_chain_status(
            current_stage="deep_beta_chain_verification",
            status=chain_verification_status,
        )
        deep_beta_chain_status["verification_status"] = chain_verification_status
        flow_events.append(
            _event(
                stage="deep_beta_chain_verification",
                status=chain_verification_status,
                source_count=factcheck_result.evidence_count,
                note="Deep beta chain verification completed.",
                component="verifier",
                payload={
                    "reasoning_steps": deep_beta_reasoning_steps,
                    "chain_status": deep_beta_chain_status,
                    "summary": verification_matrix_summary,
                    "contradiction_summary": contradiction_summary,
                },
            )
        )
    flow_events.append(
        _event(
            stage="citation_selection",
            status="completed",
            source_count=len(citations),
            note=f"Selected {len(citations)} citation(s) for final answer.",
            component="postprocess",
            payload={"citation_count": len(citations)},
        )
    )
    flow_events = _normalize_retrieval_events(flow_events, default_component="tier2_orchestrator")

    retrieval_status = (
        "warning"
        if any(str(event.get("status", "")).lower() in {"error", "failed"} for event in flow_events)
        else "completed"
    )
    effective_fallback_used = False if strict_deepseek_required else fallback_used
    answer_status = "warning" if effective_fallback_used else "completed"

    def _beta_stage_status(stage_name: str, default: str = "completed") -> str:
        if research_mode != "deep_beta" or not deep_beta_reasoning_steps:
            return default
        for item in deep_beta_reasoning_steps:
            if str(item.get("stage")) != stage_name:
                continue
            raw = str(item.get("status") or "").strip().lower()
            if raw in {"completed", "pass", "ok"}:
                return "completed"
            if raw in {"warning", "degraded", "failed", "error"}:
                return "warning"
            if raw in {"running", "started", "pending"}:
                return "running"
            return default
        return default

    metadata_stage_entries = [
        {"name": "plan", "status": "completed"},
        {"name": "keyword_filter", "status": keyword_filter_status},
        *(
            [{"name": "deep_research", "status": "completed"}]
            if research_mode == "deep"
            else [
                {"name": "deep_beta_scope", "status": _beta_stage_status("deep_beta_scope")},
                {"name": "deep_beta_hypothesis_map", "status": _beta_stage_status("deep_beta_hypothesis_map")},
                {"name": "deep_beta_retrieval_budget", "status": _beta_stage_status("deep_beta_retrieval_budget")},
                {
                    "name": "deep_beta_multi_pass_retrieval",
                    "status": _beta_stage_status("deep_beta_multi_pass_retrieval", retrieval_status),
                },
                {"name": "deep_beta_evidence_audit", "status": _beta_stage_status("deep_beta_evidence_audit")},
                {"name": "deep_beta_claim_graph", "status": _beta_stage_status("deep_beta_claim_graph")},
                {
                    "name": "deep_beta_counter_evidence_scan",
                    "status": _beta_stage_status("deep_beta_counter_evidence_scan"),
                },
                {
                    "name": "deep_beta_guideline_alignment",
                    "status": _beta_stage_status("deep_beta_guideline_alignment"),
                },
                {
                    "name": "deep_beta_risk_stratification",
                    "status": _beta_stage_status("deep_beta_risk_stratification"),
                },
                {"name": "deep_beta_gap_fill", "status": _beta_stage_status("deep_beta_gap_fill")},
                {
                    "name": "deep_beta_parallel_reasoning",
                    "status": (
                        "completed"
                        if deep_beta_parallel_reasoning_nodes
                        and all(
                            str(item.get("status") or "").strip().lower() == "completed"
                            for item in deep_beta_parallel_reasoning_nodes
                            if isinstance(item, dict)
                        )
                        else "warning"
                        if deep_beta_parallel_reasoning_nodes
                        else "skipped"
                    ),
                },
                {
                    "name": "deep_beta_evidence_verification",
                    "status": _beta_stage_status("deep_beta_evidence_verification"),
                },
                {"name": "deep_beta_chain_synthesis", "status": _beta_stage_status("deep_beta_chain_synthesis")},
                {"name": "deep_beta_report_synthesis", "status": _beta_stage_status("deep_beta_report_synthesis")},
                {"name": "deep_beta_quality_gate", "status": _beta_stage_status("deep_beta_quality_gate")},
                {
                    "name": "deep_beta_chain_verification",
                    "status": (
                        deep_beta_chain_status.get("verification_status", "completed")
                        if isinstance(deep_beta_chain_status, dict)
                        else "completed"
                    ),
                },
            ]
            if research_mode == "deep_beta"
            else []
        ),
        {"name": "hybrid_retrieval", "status": retrieval_status},
        {"name": "evidence_review", "status": evidence_review_status},
        {"name": "answer_synthesis", "status": answer_status},
        {"name": "verification", "status": verification_state},
        {"name": "contradiction_miner", "status": contradiction_stage_status},
        {"name": "verification_matrix", "status": "completed"},
        {"name": "citation_selection", "status": "completed"},
    ]
    stage_spans = (
        _build_stage_span_summaries(flow_events, stage_entries=metadata_stage_entries)
        if research_mode in {"deep", "deep_beta"}
        else []
    )
    stage_spans_by_stage: dict[str, dict[str, Any]] = {
        str(item.get("stage")): item for item in stage_spans if isinstance(item, dict)
    }
    metadata_stages = [
        {
            **stage_entry,
            "start_at": (
                stage_spans_by_stage.get(str(stage_entry.get("name")), {}).get("start_at")
                if stage_spans_by_stage
                else None
            ),
            "end_at": (
                stage_spans_by_stage.get(str(stage_entry.get("name")), {}).get("end_at")
                if stage_spans_by_stage
                else None
            ),
            "duration_ms": (
                stage_spans_by_stage.get(str(stage_entry.get("name")), {}).get("duration_ms")
                if stage_spans_by_stage
                else None
            ),
        }
        for stage_entry in metadata_stage_entries
    ]
    reasoning_steps_output = (
        [*deep_beta_reasoning_steps, *pipeline_node_steps]
        if research_mode == "deep_beta"
        else list(pipeline_node_steps)
    )
    otel_trace_metadata = _build_otel_trace_metadata(
        trace_id=trace_id,
        run_id=run_id,
        stage_spans=stage_spans,
        flow_events=flow_events,
    )
    otel_export_status = _emit_otel_trace_best_effort(
        otel_trace_metadata=otel_trace_metadata,
        flow_events=flow_events,
    )
    trace_bundle = {
        "trace_id": trace_id,
        "run_id": run_id,
        "planner": planner_trace,
        "retrieval": retrieval_trace,
        "verifier": verifier_trace,
        "stage_spans": stage_spans,
        "otel_trace_metadata": otel_trace_metadata,
        "otel_export": otel_export_status,
    }
    source_reasoning: list[dict[str, Any]] = []
    retriever_debug = (
        retrieval_trace.get("retriever_debug")
        if isinstance(retrieval_trace.get("retriever_debug"), dict)
        else {}
    )
    for score_key in ("score_trace", "final_score_trace"):
        rows = retriever_debug.get(score_key)
        if not isinstance(rows, list):
            continue
        for row in rows[:24]:
            if not isinstance(row, dict):
                continue
            if row.get("selected") is False:
                continue
            source_reasoning.append(
                {
                    "source": str(row.get("source") or "unknown"),
                    "score": row.get("final_score"),
                    "reasoning": (
                        f"base={row.get('base_score')} policy={row.get('policy_weight')} "
                        f"trust={row.get('trust_factor')} tag={row.get('tag_factor')}"
                    ),
                }
            )

    aggregated_errors: dict[str, Any] = {}
    if isinstance(retriever_debug.get("source_errors"), dict):
        aggregated_errors.update(retriever_debug.get("source_errors", {}))
    elif isinstance(retrieval_trace.get("source_errors"), dict):
        aggregated_errors.update(retrieval_trace.get("source_errors", {}))
    for summary in deep_pass_summaries:
        source_errors = summary.get("source_errors")
        if not isinstance(source_errors, dict):
            continue
        for source_name, err_value in source_errors.items():
            aggregated_errors[source_name] = err_value

    search_plan = (
        retrieval_trace.get("search_plan")
        if isinstance(retrieval_trace.get("search_plan"), dict)
        else {}
    )
    if not search_plan:
        search_plan = {
            "query": topic,
            "keywords": planner_hints.get("keywords", []),
            "top_k": planner_hints.get("hybrid_top_k"),
            "scientific_retrieval_enabled": planner_hints.get("scientific_retrieval_enabled"),
            "web_retrieval_enabled": planner_hints.get("web_retrieval_enabled"),
            "file_retrieval_enabled": planner_hints.get("file_retrieval_enabled"),
        }

    query_plan = (
        retrieval_trace.get("query_plan")
        if isinstance(retrieval_trace.get("query_plan"), dict)
        else {}
    )
    if not query_plan and isinstance(planner_hints.get("query_plan"), dict):
        query_plan = dict(planner_hints.get("query_plan", {}))
    if not query_plan:
        query_plan = {
            "original_query": topic,
            "canonical_query": topic,
            "source_queries": {"internal": [topic], "scientific": [topic], "web": [topic]},
            "decomposition": {
                "fast_pass_queries": [topic],
                "deep_pass_queries": [topic],
                "deep_beta_pass_queries": [topic],
            },
            "research_mode": research_mode,
        }

    source_attempts: list[dict[str, Any]] = []
    retrieval_source_attempts = retrieval_trace.get("source_attempts")
    if isinstance(retrieval_source_attempts, list):
        source_attempts.extend(item for item in retrieval_source_attempts if isinstance(item, dict))
    for summary in deep_pass_summaries:
        attempts = summary.get("source_attempts")
        if not isinstance(attempts, list):
            continue
        for item in attempts:
            if not isinstance(item, dict):
                continue
            source_attempts.append(
                {
                    **item,
                    "pass_index": summary.get("pass_index"),
                    "subquery": summary.get("subquery"),
                }
            )

    index_summary = (
        retrieval_trace.get("index_summary")
        if isinstance(retrieval_trace.get("index_summary"), dict)
        else {}
    )
    index_summary = {
        **index_summary,
        "retrieved_count": index_summary.get("retrieved_count", retrieval_trace.get("retrieved_count")),
        "source_counts": index_summary.get("source_counts", retrieval_trace.get("source_counts", {})),
        "before_dedupe_count": index_summary.get(
            "before_dedupe_count",
            index_summary.get("before_dedupe", retrieval_trace.get("retrieved_count")),
        ),
        "after_dedupe_count": index_summary.get(
            "after_dedupe_count",
            index_summary.get("after_dedupe", retrieval_trace.get("retrieved_count")),
        ),
        "before_dedupe": index_summary.get(
            "before_dedupe",
            index_summary.get("before_dedupe_count", retrieval_trace.get("retrieved_count")),
        ),
        "after_dedupe": index_summary.get(
            "after_dedupe",
            index_summary.get("after_dedupe_count", retrieval_trace.get("retrieved_count")),
        ),
        "selected_count": index_summary.get(
            "selected_count",
            retrieval_trace.get("retrieved_count"),
        ),
    }
    crawl_summary = (
        retrieval_trace.get("crawl_summary")
        if isinstance(retrieval_trace.get("crawl_summary"), dict)
        else {}
    )
    if not isinstance(crawl_summary.get("domains"), list):
        crawl_summary["domains"] = []

    stack_mode_requested = (
        "full"
        if str(planner_hints.get("retrieval_stack_mode") or "").strip().lower() == "full"
        else "auto"
    )
    stack_coverage_raw = (
        retrieval_trace.get("stack_coverage")
        if isinstance(retrieval_trace.get("stack_coverage"), dict)
        else {}
    )
    if not stack_coverage_raw:
        provider_keys: set[str] = set()
        for attempt in source_attempts:
            if not isinstance(attempt, dict):
                continue
            provider_key = _first_nonempty_text(attempt.get("provider"), attempt.get("source")).lower()
            if provider_key:
                provider_keys.add(provider_key)
        scientific_provider_keys = {
            "pubmed",
            "europepmc",
            "semantic_scholar",
            "openalex",
            "crossref",
            "clinicaltrials",
            "openfda",
            "dailymed",
            "rxnorm",
            "external_scientific",
        }
        web_provider_keys = {"searxng", "searxng-search", "searxng-crawl", "web_crawl"}
        stack_coverage_raw = {
            "vector_internal_used": "internal_corpus" in provider_keys,
            "graph_used": bool(retrieval_trace.get("graphrag_enabled")),
            "graph_expansion_count": _safe_int(retrieval_trace.get("graphrag_expansion_count"), 0),
            "scientific_used": bool(provider_keys.intersection(scientific_provider_keys)),
            "web_used": bool(provider_keys.intersection(web_provider_keys)),
        }
    stack_coverage = {
        "vector_internal_used": bool(stack_coverage_raw.get("vector_internal_used")),
        "graph_used": bool(stack_coverage_raw.get("graph_used")),
        "graph_expansion_count": _safe_int(
            stack_coverage_raw.get("graph_expansion_count"),
            _safe_int(retrieval_trace.get("graphrag_expansion_count"), 0),
        ),
        "scientific_used": bool(stack_coverage_raw.get("scientific_used")),
        "web_used": bool(stack_coverage_raw.get("web_used")),
    }
    missing_stack_components = [
        name
        for name, used in (
            ("vector_internal", stack_coverage["vector_internal_used"]),
            ("graph", stack_coverage["graph_used"]),
            ("scientific", stack_coverage["scientific_used"]),
            ("web", stack_coverage["web_used"]),
        )
        if not used
    ]

    stack_mode_effective_from_trace = str(retrieval_trace.get("stack_mode_effective") or "").strip().lower()
    if stack_mode_effective_from_trace not in {"auto", "full"}:
        stack_mode_effective_from_trace = ""
    computed_stack_mode_effective = (
        "full"
        if stack_mode_requested == "full" and not missing_stack_components
        else "auto"
    )
    # requested=full must degrade to auto if any stack is missing.
    if stack_mode_requested == "full":
        stack_mode_effective = computed_stack_mode_effective
    else:
        stack_mode_effective = stack_mode_effective_from_trace or computed_stack_mode_effective

    stack_mode_reason_codes = (
        [str(item).strip() for item in retrieval_trace.get("stack_mode_reason_codes", []) if str(item).strip()]
        if isinstance(retrieval_trace.get("stack_mode_reason_codes"), list)
        else []
    )
    stack_mode_reason_codes.append(f"stack_mode_requested_{stack_mode_requested}")
    if stack_mode_effective == "full":
        stack_mode_reason_codes.append("stack_mode_effective_full")
    elif stack_mode_requested == "full":
        stack_mode_reason_codes.append("stack_mode_effective_auto_missing_stack")
        stack_mode_reason_codes.extend(
            f"stack_mode_missing_{component}" for component in missing_stack_components
        )
    else:
        stack_mode_reason_codes.append("stack_mode_effective_auto")
    if (
        stack_mode_requested == "full"
        and stack_mode_effective_from_trace == "full"
        and stack_mode_effective == "auto"
    ):
        stack_mode_reason_codes.append("stack_mode_effective_adjusted_from_retrieval_trace")
    stack_mode_reason_codes = list(dict.fromkeys(stack_mode_reason_codes))

    retrieval_trace["stack_mode_effective"] = stack_mode_effective
    retrieval_trace["stack_mode_reason_codes"] = stack_mode_reason_codes
    retrieval_trace["stack_coverage"] = stack_coverage

    target_sources = ["internal"]
    if bool(planner_hints.get("scientific_retrieval_enabled")):
        target_sources.append("scientific")
    if bool(planner_hints.get("web_retrieval_enabled")):
        target_sources.append("web")
    if bool(planner_hints.get("file_retrieval_enabled")):
        target_sources.append("file")

    source_target_objective = {
        "target_sources": target_sources,
        "target_source_count": len(target_sources),
        "target_pass_count": deep_pass_count if research_mode in {"deep", "deep_beta"} else 1,
        "pass_cap": pass_count_cap,
        "target_document_budget": _safe_int(
            (
                planner_hints.get("retrieval_budget", {}).get("estimated_max_documents")
                if isinstance(planner_hints.get("retrieval_budget"), dict)
                else None
            ),
            max(len(target_sources), 1),
        ),
    }

    achieved_sources: list[str] = []
    for row in effective_context:
        if not isinstance(row, dict):
            continue
        source_name = _first_nonempty_text(row.get("source"))
        if source_name and source_name not in achieved_sources:
            achieved_sources.append(source_name)
    for attempt in source_attempts:
        if not isinstance(attempt, dict):
            continue
        source_name = _first_nonempty_text(attempt.get("provider"), attempt.get("source"))
        if source_name and source_name not in achieved_sources:
            achieved_sources.append(source_name)

    source_target_achieved = {
        "achieved_sources": achieved_sources,
        "achieved_source_count": len(achieved_sources),
        "achieved_document_count": len(effective_context),
        "achieved_pass_count": (
            len(deep_pass_summaries)
            if research_mode in {"deep", "deep_beta"} and deep_pass_summaries
            else 1
        ),
    }

    chart_specs = _build_chart_specs(
        citations=citations,
        verification_matrix_payload=verification_matrix_payload,
    )
    visual_assets = _build_visual_assets(citations)
    reasoning_digest = _build_reasoning_digest(
        topic=topic,
        research_mode=research_mode,
        planner_hints=planner_hints,
        answer_markdown=answer_markdown,
        citations=citations,
        verification_matrix_payload=verification_matrix_payload,
        flow_events=flow_events,
        deep_pass_count=len(deep_pass_summaries) if deep_pass_summaries else 1,
        parallel_reasoning_nodes=deep_beta_parallel_reasoning_nodes,
        evidence_verification=deep_beta_evidence_verification,
    )
    retrieval_route = _normalize_retrieval_route(
        query_plan.get("retrieval_route")
        or planner_hints.get("retrieval_route")
        or "internal-heavy"
    )
    router_confidence = _normalize_router_confidence(
        query_plan.get("router_confidence")
        if isinstance(query_plan.get("router_confidence"), (int, float))
        else planner_hints.get("router_confidence")
        if isinstance(planner_hints.get("router_confidence"), (int, float))
        else 0.0
    )
    degraded_path = bool(
        effective_fallback_used
        or any(
            str(event.get("status") or "").strip().lower() == "degraded"
            for event in flow_events
            if isinstance(event, dict)
        )
    )

    telemetry = {
        "trace_id": trace_id,
        "run_id": run_id,
        "flow_flags": {
            "verification_enabled": legacy_verification_enabled,
            "rule_verification_enabled": rule_verification_enabled,
            "nli_model_enabled": nli_model_enabled,
            "rag_nli_enabled": rag_nli_enabled_runtime,
            "rag_reranker_enabled": effective_rag_reranker_enabled,
            "rag_graphrag_enabled": effective_rag_graphrag_enabled,
        },
        "keywords": planner_hints.get("keywords", []),
        "query_plan": query_plan,
        "search_plan": {
            **search_plan,
            "subqueries": deep_subqueries,
            "research_mode": research_mode,
            "profiles": deep_research_profiles,
            "retrieval_budgets": deep_beta_retrieval_budgets
            if research_mode == "deep_beta"
            else planner_hints.get("retrieval_budget", {}),
        },
        "source_attempts": source_attempts,
        "source_errors": aggregated_errors,
        "fallback_reason": fallback_reason or None,
        "degraded_path": degraded_path,
        "retrieval_route": retrieval_route,
        "router_confidence": router_confidence,
        "index_summary": index_summary,
        "crawl_summary": crawl_summary,
        "stack_mode": {
            "requested": stack_mode_requested,
            "effective": stack_mode_effective,
            "reason_codes": stack_mode_reason_codes,
        },
        "stack_coverage": stack_coverage,
        "docs": _compact_context_rows(effective_context, max_items=10, max_text_len=240),
        "scores": {
            "relevance": rag_result.context_debug.get("relevance")
            if isinstance(rag_result.context_debug, dict)
            else None,
            "low_context_threshold": rag_result.context_debug.get("low_context_threshold")
            if isinstance(rag_result.context_debug, dict)
            else None,
            "pipeline_duration_ms": rag_result.context_debug.get("pipeline_duration_ms")
            if isinstance(rag_result.context_debug, dict)
            else None,
            "deep_pass_count": len(deep_pass_summaries),
        },
        "source_reasoning": source_reasoning,
        "errors": aggregated_errors,
        "deep_pass_summaries": deep_pass_summaries,
        "pass_summaries": deep_pass_summaries,
        "deep_research_profiles": deep_research_profiles,
        "deep_research_methodology": deep_research_method,
        "reasoning_steps": reasoning_steps_output,
        "parallel_reasoning_nodes": (
            deep_beta_parallel_reasoning_nodes if research_mode == "deep_beta" else []
        ),
        "evidence_verification": (
            deep_beta_evidence_verification if research_mode == "deep_beta" else {}
        ),
        "keyword_filter": keyword_filter_report,
        "evidence_review": evidence_review_summary,
        "retrieval_budgets": deep_beta_retrieval_budgets if research_mode == "deep_beta" else {},
        "chain_status": deep_beta_chain_status if research_mode == "deep_beta" else {},
        "source_target_objective": source_target_objective,
        "source_target_achieved": source_target_achieved,
        "chart_specs": chart_specs,
        "visual_assets": visual_assets,
        "reasoning_digest": reasoning_digest,
        "verification_matrix": verification_matrix_payload,
        "stage_spans": stage_spans,
        "otel_trace_metadata": otel_trace_metadata,
        "otel_export": otel_export_status,
    }
    citations_payload = [_citation_as_payload(item) for item in citations]
    compact_context_debug = _compact_context_debug(rag_result.context_debug)

    return {
        "metadata": {
            "trace_id": trace_id,
            "run_id": run_id,
            "response_style": "progressive",
            "pipeline": (
                "p2-research-tier2-deep-v1"
                if research_mode == "deep"
                else "p2-research-tier2-deep-beta-v1"
                if research_mode == "deep_beta"
                else "p2-research-tier2-hybrid-v2"
            ),
            "stages": metadata_stages,
            "flow_stages": metadata_stages,
            "stage_spans": stage_spans,
            "fallback_used": effective_fallback_used,
            "fallback_reason": fallback_reason or None,
            "source_mode": source_mode,
            "research_mode": research_mode,
            "deep_pass_count": len(deep_pass_summaries),
            "flow_flags": {
                "verification_enabled": legacy_verification_enabled,
                "rule_verification_enabled": rule_verification_enabled,
                "nli_model_enabled": nli_model_enabled,
                "rag_nli_enabled": rag_nli_enabled_runtime,
                "rag_reranker_enabled": effective_rag_reranker_enabled,
                "rag_graphrag_enabled": effective_rag_graphrag_enabled,
            },
            "source_attempts": source_attempts,
            "source_errors": aggregated_errors,
            "degraded_path": degraded_path,
            "retrieval_route": retrieval_route,
            "router_confidence": router_confidence,
            "query_plan": query_plan,
            "context_debug": compact_context_debug,
            "policy_action": policy_action,
            "verification_status": verification_status,
            "verification_matrix": verification_matrix_payload,
            "planner_trace": planner_trace,
            "retrieval_trace": retrieval_trace,
            "verifier_trace": verifier_trace,
            "trace": trace_bundle,
            "flow_events": flow_events,
            "telemetry": telemetry,
            "otel_trace_metadata": otel_trace_metadata,
            "otel_export": otel_export_status,
            "deep_research_methodology": deep_research_method,
            "reasoning_steps": reasoning_steps_output,
            "parallel_reasoning_nodes": (
                deep_beta_parallel_reasoning_nodes if research_mode == "deep_beta" else []
            ),
            "evidence_verification": (
                deep_beta_evidence_verification if research_mode == "deep_beta" else {}
            ),
            "keyword_filter": keyword_filter_report,
            "evidence_review": evidence_review_summary,
            "pass_summaries": deep_pass_summaries if research_mode == "deep_beta" else [],
            "retrieval_budgets": (
                deep_beta_retrieval_budgets
                if research_mode == "deep_beta"
                else planner_hints.get("retrieval_budget", {})
            ),
            "chain_status": deep_beta_chain_status if research_mode == "deep_beta" else {},
            "source_target_objective": source_target_objective,
            "source_target_achieved": source_target_achieved,
            "visual_assets": visual_assets,
            "chart_specs": chart_specs,
            "reasoning_digest": reasoning_digest,
            "routing": {
                "role": route.role,
                "intent": route.intent,
                "confidence": route.confidence,
                "emergency": route.emergency,
            },
            "answer_format": "markdown",
            "render_hints": {
                "markdown": True,
                "tables": True,
                "mermaid": False,
                "inline_references": False,
                "chart_spec_fences": [
                    "chart-spec",
                    "vega-lite",
                    "echarts-option",
                    "json",
                    "yaml",
                ],
            },
        },
        "context_debug": compact_context_debug,
        "trace_id": trace_id,
        "run_id": run_id,
        "flow_events": flow_events,
        "flow_stages": metadata_stages,
        "stages": metadata_stages,
        "planner_trace": planner_trace,
        "retrieval_trace": retrieval_trace,
        "verifier_trace": verifier_trace,
        "trace": trace_bundle,
        "telemetry": telemetry,
        "otel_trace_metadata": otel_trace_metadata,
        "otel_export": otel_export_status,
        "policy_action": policy_action,
        "verification_status": verification_status,
        "verification_matrix": verification_matrix_payload,
        "contradiction_summary": contradiction_summary,
        "fallback_used": effective_fallback_used,
        "fallback_reason": fallback_reason or None,
        "source_attempts": source_attempts,
        "source_errors": aggregated_errors,
        "degraded_path": degraded_path,
        "retrieval_route": retrieval_route,
        "router_confidence": router_confidence,
        "query_plan": query_plan,
        "research_mode": research_mode,
        "deep_pass_count": len(deep_pass_summaries),
        "reasoning_steps": reasoning_steps_output,
        "parallel_reasoning_nodes": (
            deep_beta_parallel_reasoning_nodes if research_mode == "deep_beta" else []
        ),
        "evidence_verification": (
            deep_beta_evidence_verification if research_mode == "deep_beta" else {}
        ),
        "keyword_filter": keyword_filter_report,
        "evidence_review": evidence_review_summary,
        "pass_summaries": deep_pass_summaries if research_mode == "deep_beta" else [],
        "retrieval_budgets": (
            deep_beta_retrieval_budgets
            if research_mode == "deep_beta"
            else planner_hints.get("retrieval_budget", {})
        ),
        "chain_status": deep_beta_chain_status if research_mode == "deep_beta" else {},
        "source_target_objective": source_target_objective,
        "source_target_achieved": source_target_achieved,
        "visual_assets": visual_assets,
        "chart_specs": chart_specs,
        "reasoning_digest": reasoning_digest,
        "plan_steps": [asdict(step) for step in plan_steps],
        "citations": citations_payload,
        # Backward-compat alias for clients still expecting `sources`.
        "sources": citations_payload,
        # Additive, flag-gated Tier2 result fields. Each key is present only when its
        # stage produced a value; otherwise it is omitted so the legacy payload shape
        # is preserved (R20.2). Downstream tasks pass their artifacts here as they land.
        **_build_tier2_optional_payload(
            pico_frame=pico_frame,
            grade=grade_labels,
            consensus=consensus_view,
            conflicting_evidence=(conflicting_evidence or None),
            citation_registry=citation_registry,
            traced_claims=traced_claims,
            gap_fill_passes=(
                deep_gap_fill_passes if settings.research_gap_fill_enabled else None
            ),
            output_profile=output_profile,
            disclaimer_present=disclaimer_present,
        ),
        "answer": answer_markdown,
        "answer_markdown": answer_markdown,
        "answer_format": "markdown",
        "render_hints": {
            "markdown": True,
            "tables": True,
            "mermaid": False,
            "inline_references": False,
            "chart_spec_fences": [
                "chart-spec",
                "vega-lite",
                "echarts-option",
                "json",
                "yaml",
            ],
        },
    }
