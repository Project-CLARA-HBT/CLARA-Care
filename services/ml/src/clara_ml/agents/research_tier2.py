from __future__ import annotations

from dataclasses import asdict, dataclass


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


def _normalize_topic(query: str) -> str:
    clean = query.strip()
    if clean:
        return clean
    return "general medication safety in primary care"


def _build_plan_steps(topic: str) -> list[PlanStep]:
    return [
        PlanStep(
            step="scope_question",
            objective=f"Narrow the exact Tier-2 research question for '{topic}'.",
            output="Framed question and inclusion boundaries.",
        ),
        PlanStep(
            step="collect_evidence",
            objective="Prioritize high-signal clinical summaries and guidelines.",
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


def _build_citations(topic: str) -> list[Citation]:
    lowered = topic.lower()
    if "nsaid" in lowered or "warfarin" in lowered or "ddi" in lowered:
        return [
            Citation(
                source_id="pubmed-ddi-001",
                title="Drug-drug interactions with anticoagulants and NSAIDs",
                url="https://pubmed.ncbi.nlm.nih.gov/",
                relevance="High relevance for bleeding-risk medication combinations.",
            ),
            Citation(
                source_id="guideline-anticoag-2024",
                title="Anticoagulation safety update",
                url="https://www.ahajournals.org/",
                relevance="Guideline framing for risk mitigation and monitoring.",
            ),
        ]
    return [
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


def _try_model_answer(topic: str, plan_steps: list[PlanStep], citations: list[Citation]) -> str | None:
    # Extension point: plug in LLM or external researcher stack in a later phase.
    _ = (topic, plan_steps, citations)
    return None


def _fallback_answer(topic: str, plan_steps: list[PlanStep], citations: list[Citation]) -> str:
    first = citations[0].source_id if citations else "no-source"
    return (
        f"Tier-2 synthesis for '{topic}': start with scoped evidence collection, then "
        f"compare study-level findings before clinical translation. Primary anchor: {first}. "
        "Use guideline alignment and patient-specific risk factors to finalize decisions."
    )


def run_research_tier2(query: str) -> dict:
    topic = _normalize_topic(query)
    plan_steps = _build_plan_steps(topic)
    citations = _build_citations(topic)

    answer = _try_model_answer(topic, plan_steps, citations)
    fallback_used = False
    if answer is None:
        answer = _fallback_answer(topic, plan_steps, citations)
        fallback_used = True

    return {
        "metadata": {
            "response_style": "progressive",
            "pipeline": "p2-research-tier2-skeleton-v1",
            "stages": [
                {"name": "plan", "status": "completed"},
                {"name": "citation_selection", "status": "completed"},
                {"name": "answer_synthesis", "status": "completed"},
            ],
            "fallback_used": fallback_used,
        },
        "plan_steps": [asdict(step) for step in plan_steps],
        "citations": [asdict(item) for item in citations],
        "answer": answer,
    }
