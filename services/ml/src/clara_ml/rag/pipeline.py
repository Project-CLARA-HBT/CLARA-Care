from __future__ import annotations

from dataclasses import dataclass
import re
from typing import List, Protocol

from clara_ml.config import settings
from clara_ml.llm.deepseek_client import DeepSeekClient, DeepSeekResponse
from clara_ml.rag.retriever import Document, InMemoryRetriever


@dataclass
class RagResult:
    query: str
    retrieved_ids: List[str]
    answer: str
    model_used: str


class LlmGenerator(Protocol):
    @property
    def model(self) -> str: ...

    def generate(self, prompt: str, system_prompt: str | None = None) -> DeepSeekResponse: ...


class RagPipelineP1:
    """P1 pipeline: retrieve -> LLM answer (if available) -> deterministic fallback."""

    def __init__(
        self,
        retriever: InMemoryRetriever | None = None,
        llm_client: LlmGenerator | None = None,
        deepseek_api_key: str | None = None,
        deepseek_base_url: str | None = None,
        deepseek_model: str | None = None,
        deepseek_timeout_seconds: float | None = None,
    ) -> None:
        self.retriever = retriever or InMemoryRetriever(
            documents=[
                Document(id="byt-001", text="Bo Y Te guidance on safe medicine use in older adults."),
                Document(id="duoc-thu-001", text="National drug handbook warning for NSAID interactions."),
                Document(id="pubmed-001", text="PubMed: medication adherence improves with reminders."),
            ]
        )
        self._deepseek_api_key = (
            settings.deepseek_api_key if deepseek_api_key is None else deepseek_api_key
        )
        self._llm_client = llm_client
        if self._llm_client is None and self._deepseek_api_key:
            self._llm_client = DeepSeekClient(
                api_key=self._deepseek_api_key,
                base_url=deepseek_base_url or settings.deepseek_base_url,
                model=deepseek_model or settings.deepseek_model,
                timeout_seconds=(
                    settings.deepseek_timeout_seconds
                    if deepseek_timeout_seconds is None
                    else deepseek_timeout_seconds
                ),
            )

    @staticmethod
    def _local_synthesis(query: str, docs: List[Document]) -> str:
        sources = ", ".join(doc.id for doc in docs) if docs else "none"
        snippets = " | ".join(f"{doc.id}: {doc.text}" for doc in docs)
        return (
            f"Tra loi tam thoi (local): query='{query}'. "
            f"Sources=[{sources}]. Summary={snippets}"
        )

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-zA-Z0-9]{3,}", text.lower())
            if token
        }

    def _context_relevance(self, query: str, docs: List[Document]) -> float:
        query_tokens = self._tokenize(query)
        if not query_tokens or not docs:
            return 0.0
        best_score = 0.0
        for doc in docs:
            doc_tokens = self._tokenize(doc.text)
            if not doc_tokens:
                continue
            overlap = len(query_tokens.intersection(doc_tokens))
            score = overlap / max(len(query_tokens), 1)
            if score > best_score:
                best_score = score
        return best_score

    @staticmethod
    def _build_prompt(query: str, docs: List[Document]) -> str:
        context = "\n".join(f"- ({doc.id}) {doc.text}" for doc in docs)
        return (
            "Answer using only retrieved context.\n"
            "If context is insufficient, still provide a concise safe answer using general medical knowledge.\n"
            f"User query: {query}\n"
            f"Retrieved context:\n{context}"
        )

    @staticmethod
    def _build_no_rag_prompt(query: str) -> str:
        return (
            "User asks a health/medical question.\n"
            "Retrieved context is empty or irrelevant.\n"
            "Provide a useful, concise, safety-first answer in Vietnamese.\n"
            "Do not claim you cannot answer due to missing context.\n"
            "Include: practical next steps, warning signs to seek urgent care, and suggest consulting clinician when needed.\n"
            f"User query: {query}"
        )

    def run(
        self,
        query: str,
        *,
        low_context_threshold: float = 0.15,
        deepseek_fallback_enabled: bool = True,
    ) -> RagResult:
        docs = self.retriever.retrieve(query)
        ids = [d.id for d in docs]
        relevance_score = self._context_relevance(query, docs)
        threshold = max(0.0, min(1.0, low_context_threshold))
        has_relevant_context = relevance_score >= threshold
        if self._llm_client and self._deepseek_api_key:
            try:
                if not has_relevant_context and not deepseek_fallback_enabled:
                    return RagResult(
                        query=query,
                        retrieved_ids=[],
                        answer=self._local_synthesis(query, docs),
                        model_used="local-synth-v1-no-fallback",
                    )
                prompt = (
                    self._build_prompt(query, docs)
                    if has_relevant_context
                    else self._build_no_rag_prompt(query)
                )
                response = self._llm_client.generate(
                    prompt=prompt,
                    system_prompt=(
                        "You are CLARA clinical assistant. Be concise, safe, and cite source ids."
                    ),
                )
                return RagResult(
                    query=query,
                    retrieved_ids=ids if has_relevant_context else [],
                    answer=response.content,
                    model_used=(
                        f"{response.model or self._llm_client.model}-with-rag"
                        if has_relevant_context
                        else f"{response.model or self._llm_client.model}-fallback"
                    ),
                )
            except Exception:
                pass

        return RagResult(
            query=query,
            retrieved_ids=ids if has_relevant_context else [],
            answer=self._local_synthesis(query, docs),
            model_used="local-synth-v1",
        )


RagPipelineP0 = RagPipelineP1
