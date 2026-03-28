from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from clara_ml.rag.pipeline import RagPipelineP1


@dataclass(frozen=True)
class PlanStep:
    step: str
    objective: str
    output: str


@dataclass(frozen=True)
class Citation:
    source_id: str
    title: str
    url: str
    relevance: str


def _normalize_topic(payload: dict[str, Any]) -> str:
    query = str(payload.get("query") or payload.get("message") or "").strip()
    if query:
        return query
    return "general medication safety in primary care"


def _build_plan_steps(topic: str, source_mode: str | None) -> list[PlanStep]:
    source_line = " from uploaded files" if source_mode == "uploaded_files" else ""
    return [
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


def _url_from_doc_id(doc_id: str) -> str:
    lowered = doc_id.lower()
    if lowered.startswith("pubmed-"):
        suffix = lowered.split("pubmed-", 1)[1]
        if suffix.isdigit():
            return f"https://pubmed.ncbi.nlm.nih.gov/{suffix}/"
        return "https://pubmed.ncbi.nlm.nih.gov/"
    if lowered.startswith("europepmc-"):
        return "https://europepmc.org/"
    if lowered.startswith("uploaded-"):
        return ""
    return ""


def _build_citations(
    topic: str,
    retrieved_ids: list[str],
    uploaded_documents: list[dict[str, Any]],
) -> list[Citation]:
    citations: list[Citation] = []

    for doc_id in retrieved_ids[:8]:
        citations.append(
            Citation(
                source_id=doc_id,
                title=f"Evidence: {doc_id}",
                url=_url_from_doc_id(doc_id),
                relevance=f"Matched to query '{topic}' via hybrid retrieval.",
            )
        )

    for idx, doc in enumerate(uploaded_documents[:6], start=1):
        file_id = str(doc.get("file_id") or doc.get("id") or f"uploaded-{idx}")
        name = str(doc.get("filename") or doc.get("name") or file_id)
        preview = str(doc.get("preview") or "").strip()
        relevance = f"Uploaded document context ({name})"
        if preview:
            relevance = f"{relevance}: {preview[:120]}"
        citations.append(
            Citation(
                source_id=f"uploaded-{file_id}",
                title=name,
                url="",
                relevance=relevance,
            )
        )

    if not citations:
        citations = [
            Citation(
                source_id="who-msh-001",
                title="WHO medication safety resources",
                url="https://www.who.int/teams/integrated-health-services/patient-safety",
                relevance="Global baseline for medication safety principles.",
            ),
            Citation(
                source_id="pubmed-adherence-001",
                title="Medication adherence interventions review",
                url="https://pubmed.ncbi.nlm.nih.gov/",
                relevance="Evidence patterns for adherence and outcomes.",
            ),
        ]

    return citations


def run_research_tier2(payload: dict[str, Any]) -> dict:
    topic = _normalize_topic(payload)
    source_mode = str(payload.get("source_mode") or "").strip().lower() or None
    uploaded_documents_raw = payload.get("uploaded_documents")
    uploaded_documents: list[dict[str, Any]] = (
        uploaded_documents_raw if isinstance(uploaded_documents_raw, list) else []
    )
    rag_sources = payload.get("rag_sources")

    plan_steps = _build_plan_steps(topic, source_mode)

    pipeline = RagPipelineP1()
    rag_result = pipeline.run(
        topic,
        low_context_threshold=0.15,
        deepseek_fallback_enabled=True,
        scientific_retrieval_enabled=True,
        web_retrieval_enabled=False,
        file_retrieval_enabled=True,
        rag_sources=rag_sources,
        uploaded_documents=uploaded_documents,
    )

    citations = _build_citations(topic, rag_result.retrieved_ids, uploaded_documents)
    fallback_used = rag_result.model_used.startswith("local-synth") or "fallback" in rag_result.model_used.lower()

    return {
        "metadata": {
            "response_style": "progressive",
            "pipeline": "p2-research-tier2-hybrid-v2",
            "stages": [
                {"name": "plan", "status": "completed"},
                {"name": "hybrid_retrieval", "status": "completed"},
                {"name": "answer_synthesis", "status": "completed"},
                {"name": "citation_selection", "status": "completed"},
            ],
            "fallback_used": fallback_used,
            "source_mode": source_mode,
            "context_debug": rag_result.context_debug,
        },
        "plan_steps": [asdict(step) for step in plan_steps],
        "citations": [asdict(item) for item in citations],
        "answer": rag_result.answer,
    }
