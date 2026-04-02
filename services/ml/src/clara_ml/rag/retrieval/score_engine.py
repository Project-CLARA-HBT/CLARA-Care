from __future__ import annotations

import re
from typing import Any, Sequence
import unicodedata

from clara_ml.config import settings
from clara_ml.rag.embedder import HttpEmbeddingClient

from .domain import Document, SOURCE_SCORE_BIAS
from .text_utils import (
    analyze_query_profile,
    normalize_tags,
    query_terms,
    safe_weight,
    tag_relevance_factor,
    trust_tier_factor,
)


class DocumentScorer:
    _RRF_K = 60
    _RRF_BLEND = 0.14
    _BIOMEDICAL_SIGNAL_TERMS = {
        "interaction",
        "ddi",
        "contraindication",
        "contraindications",
        "bleeding",
        "hemorrhage",
        "adverse",
        "toxicity",
        "safety",
        "warning",
        "boxed warning",
        "labeling",
        "pharmacokinetic",
        "pharmacodynamic",
        "metabolism",
        "cyp",
        "inr",
        "guideline",
        "clinical trial",
    }
    _BIOMEDICAL_SOURCE_PRIOR = {
        "openfda": 1.0,
        "dailymed": 1.0,
        "rxnorm": 0.9,
        "pubmed": 0.85,
        "europepmc": 0.82,
        "clinicaltrials": 0.8,
        "who": 0.78,
        "nih": 0.76,
        "internal": 0.55,
    }

    def __init__(self, embedder: HttpEmbeddingClient | None = None) -> None:
        self.embedder = embedder or HttpEmbeddingClient()

    @staticmethod
    def _is_ddi_critical_query(query: str, query_profile: dict[str, Any]) -> bool:
        if not bool(query_profile.get("is_ddi_query")):
            return False
        lowered = str(query or "").lower()
        normalized = unicodedata.normalize("NFD", lowered)
        folded = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        critical_markers = {
            "critical",
            "major",
            "severe",
            "life-threatening",
            "contraindication",
            "black box",
            "bleeding risk",
            "hemorrhage",
            "nghiem trong",
            "nguy hiem",
            "chong chi dinh",
            "xuat huyet",
        }
        return any(marker in lowered or marker in folded for marker in critical_markers)

    @staticmethod
    def _normalize_document(doc: Document, *, default_source: str = "internal") -> Document:
        metadata = dict(doc.metadata or {})
        metadata.setdefault("source", str(default_source).strip().lower() or "internal")
        metadata.setdefault("url", "")
        metadata.setdefault("score", 0.0)
        metadata["weight"] = safe_weight(metadata.get("weight", 1.0), default=1.0)
        metadata["tags"] = normalize_tags(metadata.get("tags"))
        metadata.setdefault("trust_tier", "tier_3")
        metadata.setdefault("file_type", "")
        return Document(id=doc.id, text=doc.text, metadata=metadata)

    def score_documents(
        self,
        query: str,
        documents: Sequence[Document],
        top_k: int,
        *,
        source_policies: dict[str, dict[str, float | bool]] | None = None,
        score_trace: list[dict[str, Any]] | None = None,
    ) -> list[Document]:
        if top_k <= 0:
            return []

        if score_trace is not None:
            score_trace.clear()

        normalized_docs = [self._normalize_document(doc) for doc in documents]
        if not normalized_docs:
            return []

        vectors = self.embedder.embed_batch([query] + [doc.text for doc in normalized_docs])
        if not vectors:
            return []

        query_vector = vectors[0]
        doc_vectors = vectors[1:]

        source_policies = source_policies or {}
        query_profile = analyze_query_profile(query)
        expanded_query = " ".join(query_terms(query))
        query_tokens = self._tokenize(expanded_query or query)
        scored: list[tuple[float, Document]] = []
        trace_rows: list[dict[str, Any]] = []
        candidate_rows: list[dict[str, Any]] = []
        is_ddi_query = bool(query_profile.get("is_ddi_query"))
        is_ddi_critical_query = self._is_ddi_critical_query(query, query_profile)
        primary_drug = str(query_profile.get("primary_drug") or "").strip().lower()
        primary_aliases = {
            str(item).strip().lower()
            for item in query_profile.get("primary_aliases", [])
            if str(item).strip()
        }
        if primary_drug:
            primary_aliases.add(primary_drug)
        co_drugs = {
            str(item).strip().lower()
            for item in query_profile.get("co_drugs", [])
            if str(item).strip()
        }
        co_drug_aliases = set(co_drugs)
        co_drug_aliases_raw = query_profile.get("co_drug_aliases")
        if isinstance(co_drug_aliases_raw, dict):
            for aliases in co_drug_aliases_raw.values():
                if not isinstance(aliases, list):
                    continue
                for item in aliases:
                    alias = str(item).strip().lower()
                    if alias:
                        co_drug_aliases.add(alias)
        interaction_tokens = {
            "interaction",
            "ddi",
            "bleeding",
            "contraindication",
            "adverse",
            "risk",
            "hemorrhage",
            "pharmacokinetic",
            "pharmacodynamic",
        }

        for doc, doc_vector in zip(normalized_docs, doc_vectors):
            base_score = sum(a * b for a, b in zip(query_vector, doc_vector))
            lexical_overlap = self._lexical_overlap(query_tokens, doc.text)
            metadata = doc.metadata or {}
            doc_haystack = " ".join(
                [
                    doc.text,
                    str(metadata.get("title") or ""),
                    str(metadata.get("url") or ""),
                    str(doc.id or ""),
                ]
            )
            doc_tokens = self._tokenize(doc_haystack)
            has_primary_drug = bool(primary_aliases) and bool(
                primary_aliases.intersection(doc_tokens)
            )
            has_codrug_signal = bool(co_drug_aliases.intersection(doc_tokens))
            has_interaction_signal = bool(doc_tokens.intersection(interaction_tokens))
            source_key = str(doc.metadata.get("source") or "").strip().lower()
            trusted_label_source = source_key in {"openfda", "dailymed", "rxnorm", "rxnav"}

            if is_ddi_query and not has_primary_drug:
                trace_rows.append(
                    {
                        "doc_id": doc.id,
                        "source": str(doc.metadata.get("source") or "unknown"),
                        "excluded": True,
                        "reason": "ddi_missing_primary_drug",
                        "lexical_overlap": lexical_overlap,
                    }
                )
                continue
            if (
                is_ddi_query
                and not has_codrug_signal
                and not has_interaction_signal
                and not trusted_label_source
            ):
                trace_rows.append(
                    {
                        "doc_id": doc.id,
                        "source": source_key or "unknown",
                        "excluded": True,
                        "reason": "ddi_missing_codrug_or_interaction",
                        "lexical_overlap": lexical_overlap,
                    }
                )
                continue
            if (
                is_ddi_query
                and lexical_overlap < 0.08
                and not has_codrug_signal
                and not has_interaction_signal
                and not trusted_label_source
            ):
                trace_rows.append(
                    {
                        "doc_id": doc.id,
                        "source": source_key or "unknown",
                        "excluded": True,
                        "reason": "ddi_low_lexical_overlap",
                        "lexical_overlap": lexical_overlap,
                    }
                )
                continue
            if is_ddi_critical_query and (not has_codrug_signal or not has_interaction_signal):
                trace_rows.append(
                    {
                        "doc_id": doc.id,
                        "source": source_key or "unknown",
                        "excluded": True,
                        "reason": "ddi_critical_requires_codrug_and_interaction",
                        "lexical_overlap": lexical_overlap,
                    }
                )
                continue
            if is_ddi_critical_query and lexical_overlap < 0.12:
                trace_rows.append(
                    {
                        "doc_id": doc.id,
                        "source": source_key or "unknown",
                        "excluded": True,
                        "reason": "ddi_critical_low_lexical_overlap",
                        "lexical_overlap": lexical_overlap,
                    }
                )
                continue
            policy = source_policies.get(source_key, {"enabled": True, "weight": 1.0})
            if not bool(policy.get("enabled", True)):
                trace_rows.append(
                    {
                        "doc_id": doc.id,
                        "source": source_key or "unknown",
                        "excluded": True,
                        "reason": "source_disabled_by_policy",
                    }
                )
                continue

            policy_weight = safe_weight(policy.get("weight", 1.0), default=1.0)
            doc_weight = safe_weight(doc.metadata.get("weight", 1.0), default=1.0)
            source_bias = max(0.5, min(1.6, float(SOURCE_SCORE_BIAS.get(source_key, 1.0))))
            trust_factor = trust_tier_factor(doc.metadata.get("trust_tier"))
            tag_factor = tag_relevance_factor(query, doc.metadata.get("tags"))
            file_type = str(doc.metadata.get("file_type") or "").strip().lower()
            pdf_factor = 1.05 if file_type == "pdf" else 1.0

            semantic_component = max(float(base_score), 0.0)
            blend_score = (0.65 * semantic_component) + (0.35 * lexical_overlap)

            score = (
                blend_score
                * max(policy_weight, 0.05)
                * max(doc_weight, 0.05)
                * source_bias
                * trust_factor
                * tag_factor
                * pdf_factor
            )
            ddi_boost = 1.0
            if is_ddi_query:
                if has_primary_drug and has_codrug_signal and has_interaction_signal:
                    ddi_boost = 1.3
                elif has_primary_drug and has_codrug_signal:
                    ddi_boost = 1.22
                elif has_primary_drug and has_interaction_signal:
                    ddi_boost = 1.16
                elif trusted_label_source and has_primary_drug:
                    ddi_boost = 1.1
            score *= ddi_boost
            candidate_rows.append(
                {
                    "doc": doc,
                    "source_key": source_key or "unknown",
                    "base_score": float(base_score),
                    "semantic_component": float(semantic_component),
                    "lexical_overlap": float(lexical_overlap),
                    "policy_weight": float(policy_weight),
                    "doc_weight": float(doc_weight),
                    "source_bias": float(source_bias),
                    "trust_factor": float(trust_factor),
                    "tag_factor": float(tag_factor),
                    "pdf_factor": float(pdf_factor),
                    "ddi_boost": float(ddi_boost),
                    "pre_rrf_score": float(score),
                    "ddi_query": is_ddi_query,
                    "ddi_critical_query": is_ddi_critical_query,
                    "has_primary_drug": has_primary_drug,
                    "has_codrug_signal": has_codrug_signal,
                    "has_interaction_signal": has_interaction_signal,
                    "trusted_label_source": trusted_label_source,
                }
            )

        semantic_rank: dict[str, int] = {}
        lexical_rank: dict[str, int] = {}
        for index, item in enumerate(
            sorted(
                candidate_rows,
                key=lambda row: (
                    float(row["semantic_component"]),
                    float(row["lexical_overlap"]),
                    float(row["pre_rrf_score"]),
                ),
                reverse=True,
            ),
            start=1,
        ):
            semantic_rank[str(item["doc"].id)] = index
        for index, item in enumerate(
            sorted(
                candidate_rows,
                key=lambda row: (
                    float(row["lexical_overlap"]),
                    float(row["semantic_component"]),
                    float(row["pre_rrf_score"]),
                ),
                reverse=True,
            ),
            start=1,
        ):
            lexical_rank[str(item["doc"].id)] = index

        scored_rows: list[dict[str, Any]] = []
        for item in candidate_rows:
            doc = item["doc"]
            doc_id = str(doc.id)
            semantic_pos = int(semantic_rank.get(doc_id, len(candidate_rows) + 1))
            lexical_pos = int(lexical_rank.get(doc_id, len(candidate_rows) + 1))
            rrf_score = (1.0 / float(self._RRF_K + semantic_pos)) + (
                1.0 / float(self._RRF_K + lexical_pos)
            )
            rrf_scaled = rrf_score * float(self._RRF_K)
            final_score = (float(item["pre_rrf_score"]) * (1.0 - self._RRF_BLEND)) + (
                rrf_scaled * self._RRF_BLEND
            )
            score_breakdown = {
                "base_score": float(item["base_score"]),
                "semantic_component": float(item["semantic_component"]),
                "lexical_overlap": float(item["lexical_overlap"]),
                "policy_weight": float(item["policy_weight"]),
                "doc_weight": float(item["doc_weight"]),
                "source_bias": float(item["source_bias"]),
                "trust_factor": float(item["trust_factor"]),
                "tag_factor": float(item["tag_factor"]),
                "pdf_factor": float(item["pdf_factor"]),
                "ddi_boost": float(item["ddi_boost"]),
                "pre_rrf_score": float(item["pre_rrf_score"]),
                "rrf_score": float(rrf_score),
                "rrf_scaled": float(rrf_scaled),
                "rrf_semantic_rank": semantic_pos,
                "rrf_lexical_rank": lexical_pos,
                "final_score": float(final_score),
                "biomedical_rerank_enabled": False,
                "biomedical_rerank_signal": 0.0,
                "biomedical_rerank_factor": 1.0,
                "ddi_query": bool(item["ddi_query"]),
                "ddi_critical_query": bool(item["ddi_critical_query"]),
                "has_primary_drug": bool(item["has_primary_drug"]),
                "has_codrug_signal": bool(item["has_codrug_signal"]),
                "has_interaction_signal": bool(item["has_interaction_signal"]),
                "trusted_label_source": bool(item["trusted_label_source"]),
            }
            scored_rows.append(
                {
                    "doc": doc,
                    "source": str(item["source_key"] or "unknown"),
                    "final_score": float(final_score),
                    "score_breakdown": score_breakdown,
                    "has_primary_drug": bool(item["has_primary_drug"]),
                    "has_codrug_signal": bool(item["has_codrug_signal"]),
                    "has_interaction_signal": bool(item["has_interaction_signal"]),
                    "trusted_label_source": bool(item["trusted_label_source"]),
                }
            )

        rerank_enabled = bool(settings.rag_biomedical_rerank_enabled)
        rerank_alpha = max(0.0, min(1.0, float(settings.rag_biomedical_rerank_alpha)))
        rerank_top_n = max(0, int(settings.rag_biomedical_rerank_top_n))
        if rerank_enabled and rerank_alpha > 0.0 and rerank_top_n > 0 and scored_rows:
            rerank_candidates = sorted(
                scored_rows,
                key=lambda row: float(row["final_score"]),
                reverse=True,
            )[:rerank_top_n]
            for row in rerank_candidates:
                doc = row["doc"]
                signal = self._biomedical_signal(
                    query_tokens=query_tokens,
                    doc=doc,
                    query_profile=query_profile,
                    has_primary_drug=bool(row["has_primary_drug"]),
                    has_codrug_signal=bool(row["has_codrug_signal"]),
                    has_interaction_signal=bool(row["has_interaction_signal"]),
                    trusted_label_source=bool(row["trusted_label_source"]),
                )
                rerank_factor = 1.0 + (rerank_alpha * signal)
                reranked_score = float(row["final_score"]) * rerank_factor
                row["final_score"] = reranked_score
                score_breakdown = row["score_breakdown"]
                score_breakdown["biomedical_rerank_enabled"] = True
                score_breakdown["biomedical_rerank_signal"] = float(signal)
                score_breakdown["biomedical_rerank_factor"] = float(rerank_factor)
                score_breakdown["final_score"] = float(reranked_score)

        for row in scored_rows:
            doc = row["doc"]
            score_breakdown = row["score_breakdown"]
            final_score = float(row["final_score"])
            doc.metadata["weight"] = float(score_breakdown["doc_weight"])
            doc.metadata["policy_weight"] = float(score_breakdown["policy_weight"])
            doc.metadata["source_bias"] = float(score_breakdown["source_bias"])
            doc.metadata["trust_factor"] = float(score_breakdown["trust_factor"])
            doc.metadata["tag_factor"] = float(score_breakdown["tag_factor"])
            doc.metadata["pdf_factor"] = float(score_breakdown["pdf_factor"])
            doc.metadata["ddi_boost"] = float(score_breakdown["ddi_boost"])
            doc.metadata["rrf_score"] = float(score_breakdown["rrf_score"])
            doc.metadata["rrf_scaled"] = float(score_breakdown["rrf_scaled"])
            doc.metadata["biomedical_rerank_enabled"] = bool(
                score_breakdown["biomedical_rerank_enabled"]
            )
            doc.metadata["biomedical_rerank_signal"] = float(
                score_breakdown["biomedical_rerank_signal"]
            )
            doc.metadata["biomedical_rerank_factor"] = float(
                score_breakdown["biomedical_rerank_factor"]
            )
            doc.metadata["score"] = float(final_score)
            doc.metadata["score_breakdown"] = score_breakdown
            trace_rows.append(
                {
                    "doc_id": doc.id,
                    "source": str(row["source"] or "unknown"),
                    "excluded": False,
                    **score_breakdown,
                }
            )
            scored.append((float(final_score), doc))

        scored.sort(key=lambda item: item[0], reverse=True)
        selected_docs = self._select_with_source_diversity(scored, top_k=top_k)

        if score_trace is not None:
            selected_ids = {doc.id for doc in selected_docs}
            for row in trace_rows:
                row["selected"] = row.get("doc_id") in selected_ids
            score_trace.extend(trace_rows)

        return selected_docs

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        lowered = text.lower()
        tokens = re.findall(r"[0-9a-zA-ZÀ-ỹ]{2,}", lowered)
        return {token for token in tokens if token}

    @staticmethod
    def _select_with_source_diversity(
        scored: list[tuple[float, Document]],
        *,
        top_k: int,
    ) -> list[Document]:
        if top_k <= 0:
            return []
        if not scored:
            return []

        # Keep score order but prevent one source from monopolizing all slots.
        max_per_source = max(2, (top_k + 1) // 2)
        selected: list[Document] = []
        deferred: list[Document] = []
        source_counts: dict[str, int] = {}

        for _, doc in scored:
            source = str((doc.metadata or {}).get("source") or "unknown").strip().lower()
            count = source_counts.get(source, 0)
            if count < max_per_source:
                selected.append(doc)
                source_counts[source] = count + 1
            else:
                deferred.append(doc)
            if len(selected) >= top_k:
                return selected[:top_k]

        if len(selected) < top_k:
            selected.extend(deferred[: max(0, top_k - len(selected))])
        return selected[:top_k]

    @classmethod
    def _lexical_overlap(cls, query_tokens: set[str], text: str) -> float:
        if not query_tokens:
            return 0.0
        doc_tokens = cls._tokenize(text)
        if not doc_tokens:
            return 0.0
        overlap = len(query_tokens.intersection(doc_tokens))
        return float(overlap) / float(max(len(query_tokens), 1))

    @classmethod
    def _biomedical_signal(
        cls,
        *,
        query_tokens: set[str],
        doc: Document,
        query_profile: dict[str, Any],
        has_primary_drug: bool,
        has_codrug_signal: bool,
        has_interaction_signal: bool,
        trusted_label_source: bool,
    ) -> float:
        metadata = doc.metadata or {}
        doc_haystack = " ".join(
            [
                str(doc.text or ""),
                str(metadata.get("title") or ""),
                str(metadata.get("url") or ""),
            ]
        ).strip()
        doc_tokens = cls._tokenize(doc_haystack)
        if not doc_tokens:
            return 0.0

        lexical_signal = float(len(query_tokens.intersection(doc_tokens))) / float(
            max(len(query_tokens), 1)
        )
        biomedical_hits = 0
        lowered_haystack = doc_haystack.lower()
        for marker in cls._BIOMEDICAL_SIGNAL_TERMS:
            if " " in marker:
                if marker in lowered_haystack:
                    biomedical_hits += 1
            elif marker in doc_tokens:
                biomedical_hits += 1
        biomedical_term_signal = min(1.0, float(biomedical_hits) / 6.0)

        source_key = str(metadata.get("source") or "").strip().lower()
        source_signal = float(cls._BIOMEDICAL_SOURCE_PRIOR.get(source_key, 0.5))

        ddi_signal = 0.0
        if bool(query_profile.get("is_ddi_query")):
            if has_primary_drug:
                ddi_signal += 0.35
            if has_codrug_signal:
                ddi_signal += 0.3
            if has_interaction_signal:
                ddi_signal += 0.25
            if trusted_label_source:
                ddi_signal += 0.1
        else:
            if trusted_label_source:
                ddi_signal += 0.15
            if has_interaction_signal:
                ddi_signal += 0.2

        combined = (
            (0.38 * lexical_signal)
            + (0.32 * biomedical_term_signal)
            + (0.2 * min(ddi_signal, 1.0))
            + (0.1 * min(source_signal, 1.0))
        )
        return max(0.0, min(1.0, combined))
