from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, List, Protocol

from clara_ml.config import settings
from clara_ml.llm.deepseek_client import DeepSeekClient, DeepSeekResponse
from clara_ml.rag.retriever import Document, InMemoryRetriever


@dataclass
class RagResult:
    query: str
    retrieved_ids: List[str]
    answer: str
    model_used: str
    retrieved_context: List[dict[str, Any]] = field(default_factory=list)
    context_debug: dict[str, Any] = field(default_factory=dict)


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
                Document(
                    id="byt-001",
                    text="Bo Y Te guidance on safe medicine use in older adults.",
                    metadata={"source": "byt", "url": "", "score": 0.0},
                ),
                Document(
                    id="duoc-thu-001",
                    text="National drug handbook warning for NSAID interactions.",
                    metadata={"source": "duoc-thu", "url": "", "score": 0.0},
                ),
                Document(
                    id="pubmed-001",
                    text="PubMed: medication adherence improves with reminders.",
                    metadata={"source": "seed-pubmed", "url": "", "score": 0.0},
                ),
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
        return f"Tra loi tam thoi (local): query='{query}'. Sources=[{sources}]. Summary={snippets}"

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {token for token in re.findall(r"[0-9a-zA-ZÀ-ỹ]{2,}", text.lower()) if token}

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
    def _format_doc_context(doc: Document) -> str:
        metadata = doc.metadata or {}
        source = str(metadata.get("source") or "unknown")
        url = str(metadata.get("url") or "")
        score = metadata.get("score", 0.0)
        try:
            score_txt = f"{float(score):.4f}"
        except (TypeError, ValueError):
            score_txt = "0.0000"
        meta_bits = f"source={source}; score={score_txt}"
        if url:
            meta_bits = f"{meta_bits}; url={url}"
        return f"- ({doc.id}) [{meta_bits}] {doc.text}"

    @classmethod
    def _build_prompt(cls, query: str, docs: List[Document]) -> str:
        context = "\n".join(cls._format_doc_context(doc) for doc in docs)
        return (
            "Answer using only retrieved context.\n"
            "If context is insufficient, still provide a concise safe answer using general medical knowledge.\n"
            "Do not answer that there is no context; provide useful next steps safely.\n"
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
            "If the query is comparative (e.g., compares diets/treatments), provide a balanced comparison and practical decision criteria.\n"
            "Only include urgent warning signs when the query is about symptoms or acute risk.\n"
            "Suggest consulting a clinician when needed.\n"
            f"User query: {query}"
        )

    @staticmethod
    def _safe_helpful_answer(query: str, docs: List[Document]) -> str:
        if docs:
            source_ids = ", ".join(doc.id for doc in docs[:3])
            return (
                "Thong tin hien co cho thay can danh gia theo muc tieu dieu tri, benh nen va thuoc dang dung. "
                f"Nguon tham chieu gan nhat: {source_ids}. "
                "Ban nen theo doi trieu chung bat thuong, tranh tu y tang lieu, va trao doi bac si/duoc si de ca nhan hoa khuyen nghi."
            )
        return (
            "Voi cau hoi nay, ban co the ap dung nguyen tac an toan: dung thuoc dung lieu, theo doi trieu chung bat thuong, "
            "va uu tien tham van bac si neu co benh nen hoac dang dung nhieu thuoc."
        )

    @classmethod
    def _postprocess_answer(cls, answer: str, query: str, docs: List[Document]) -> str:
        cleaned = (answer or "").strip()
        if not cleaned:
            return cls._safe_helpful_answer(query, docs)
        blocked_phrases = {
            "khong co thong tin tu ngu canh",
            "không có thông tin từ ngữ cảnh",
            "khong du thong tin tu ngu canh",
            "insufficient context",
            "no context",
            "cannot answer due to missing context",
        }
        lowered = cleaned.lower()
        if any(phrase in lowered for phrase in blocked_phrases):
            return cls._safe_helpful_answer(query, docs)
        return cleaned

    @staticmethod
    def _source_counts(docs: List[Document]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for doc in docs:
            source = str((doc.metadata or {}).get("source") or "unknown")
            counts[source] = counts.get(source, 0) + 1
        return counts

    def _build_context_debug(
        self,
        *,
        relevance: float,
        threshold: float,
        used_stages: List[str],
        docs: List[Document],
        low_context_before_external: bool,
        external_attempted: bool,
    ) -> dict[str, Any]:
        return {
            "relevance": round(float(relevance), 4),
            "low_context_threshold": round(float(threshold), 4),
            "used_stages": used_stages,
            "source_counts": self._source_counts(docs),
            "low_context_before_external": low_context_before_external,
            "external_attempted": external_attempted,
        }

    @staticmethod
    def _serialize_context(docs: List[Document]) -> List[dict[str, Any]]:
        serialized: list[dict[str, Any]] = []
        for doc in docs:
            metadata = doc.metadata or {}
            serialized.append(
                {
                    "id": doc.id,
                    "text": doc.text,
                    "source": str(metadata.get("source") or "unknown"),
                    "url": str(metadata.get("url") or ""),
                    "score": metadata.get("score"),
                }
            )
        return serialized

    def run(
        self,
        query: str,
        *,
        low_context_threshold: float = 0.15,
        deepseek_fallback_enabled: bool = True,
        scientific_retrieval_enabled: bool = False,
        web_retrieval_enabled: bool = False,
        file_retrieval_enabled: bool = True,
        rag_sources: object = None,
        uploaded_documents: object = None,
    ) -> RagResult:
        threshold = max(0.0, min(1.0, low_context_threshold))
        used_stages: list[str] = ["internal_retrieval"]
        external_attempted = False

        docs = self.retriever.retrieve_internal(
            query,
            file_retrieval_enabled=file_retrieval_enabled,
            rag_sources=rag_sources,
            uploaded_documents=uploaded_documents,
        )
        relevance_score = self._context_relevance(query, docs)
        low_context_before_external = relevance_score < threshold

        if (
            low_context_before_external
            and scientific_retrieval_enabled
            and settings.rag_external_connectors_enabled
        ):
            external_attempted = True
            used_stages.append("external_scientific_retrieval")
            docs = self.retriever.retrieve(
                query,
                scientific_retrieval_enabled=True,
                web_retrieval_enabled=web_retrieval_enabled,
                file_retrieval_enabled=file_retrieval_enabled,
                rag_sources=rag_sources,
                uploaded_documents=uploaded_documents,
            )
            relevance_score = self._context_relevance(query, docs)

        has_relevant_context = relevance_score >= threshold
        ids = [d.id for d in docs]

        if self._llm_client and self._deepseek_api_key:
            try:
                if not has_relevant_context and not deepseek_fallback_enabled:
                    used_stages.append("local_synthesis_no_fallback")
                    answer = self._postprocess_answer(
                        self._local_synthesis(query, docs), query, docs
                    )
                    return RagResult(
                        query=query,
                        retrieved_ids=ids,
                        answer=answer,
                        model_used="local-synth-v1-no-fallback",
                        retrieved_context=self._serialize_context(docs),
                        context_debug=self._build_context_debug(
                            relevance=relevance_score,
                            threshold=threshold,
                            used_stages=used_stages,
                            docs=docs,
                            low_context_before_external=low_context_before_external,
                            external_attempted=external_attempted,
                        ),
                    )

                used_stages.append("llm_generation")
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
                    answer=self._postprocess_answer(response.content, query, docs),
                    model_used=response.model or self._llm_client.model,
                    retrieved_context=self._serialize_context(docs if has_relevant_context else []),
                    context_debug=self._build_context_debug(
                        relevance=relevance_score,
                        threshold=threshold,
                        used_stages=used_stages,
                        docs=docs,
                        low_context_before_external=low_context_before_external,
                        external_attempted=external_attempted,
                    ),
                )
            except Exception:
                used_stages.append("llm_error_fallback")

        used_stages.append("local_synthesis")
        return RagResult(
            query=query,
            retrieved_ids=ids,
            answer=self._postprocess_answer(self._local_synthesis(query, docs), query, docs),
            model_used="local-synth-v1",
            retrieved_context=self._serialize_context(docs),
            context_debug=self._build_context_debug(
                relevance=relevance_score,
                threshold=threshold,
                used_stages=used_stages,
                docs=docs,
                low_context_before_external=low_context_before_external,
                external_attempted=external_attempted,
            ),
        )


RagPipelineP0 = RagPipelineP1
