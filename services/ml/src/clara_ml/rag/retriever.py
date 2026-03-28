from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, List, Sequence
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from clara_ml.config import settings
from clara_ml.rag.embedder import BgeM3EmbedderStub


@dataclass
class Document:
    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


class InMemoryRetriever:
    _PUBMED_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    _PUBMED_ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    _EUROPEPMC_SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

    def __init__(self, documents: List[Document]) -> None:
        self.documents = [
            self._normalized_document(doc, default_source="internal") for doc in documents
        ]
        self.embedder = BgeM3EmbedderStub()

    @staticmethod
    def _normalized_document(doc: Document, *, default_source: str) -> Document:
        metadata = dict(doc.metadata or {})
        metadata.setdefault("source", str(default_source).strip().lower() or "internal")
        metadata.setdefault("url", "")
        metadata.setdefault("score", 0.0)
        metadata.setdefault("weight", 1.0)
        return Document(id=doc.id, text=doc.text, metadata=metadata)

    @staticmethod
    def _dedupe_documents(documents: Sequence[Document]) -> List[Document]:
        deduped: list[Document] = []
        seen: set[str] = set()
        for doc in documents:
            if doc.id in seen:
                continue
            deduped.append(doc)
            seen.add(doc.id)
        return deduped

    @staticmethod
    def _parse_source_policies(rag_sources: object) -> dict[str, dict[str, float | bool]]:
        if not isinstance(rag_sources, list):
            return {}
        policies: dict[str, dict[str, float | bool]] = {}
        for item in rag_sources:
            if not isinstance(item, dict):
                continue
            source_id = (
                str(item.get("id") or item.get("source") or item.get("name") or "").strip().lower()
            )
            if not source_id:
                continue
            enabled = bool(item.get("enabled", True))
            raw_weight = item.get("weight", 1.0)
            try:
                weight = float(raw_weight)
            except (TypeError, ValueError):
                weight = 1.0
            weight = max(0.0, min(1.0, weight))
            policies[source_id] = {"enabled": enabled, "weight": weight}
        return policies

    def _score_documents(
        self,
        query: str,
        documents: Sequence[Document],
        top_k: int,
        *,
        source_policies: dict[str, dict[str, float | bool]] | None = None,
    ) -> List[Document]:
        if top_k <= 0:
            return []
        qvec = self.embedder.embed(query)
        scored: list[tuple[float, Document]] = []
        source_policies = source_policies or {}
        for doc in documents:
            dvec = self.embedder.embed(doc.text)
            base_score = sum(a * b for a, b in zip(qvec, dvec))
            normalized = self._normalized_document(doc, default_source="internal")
            source_key = str(normalized.metadata.get("source") or "").strip().lower()
            policy = source_policies.get(source_key, {"enabled": True, "weight": 1.0})
            if not bool(policy.get("enabled", True)):
                continue
            weight = float(policy.get("weight", 1.0))
            weight = max(0.0, min(1.0, weight))
            score = base_score * max(weight, 0.05)
            normalized.metadata["weight"] = weight
            normalized.metadata["score"] = float(score)
            scored.append((score, normalized))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored[:top_k]]

    @staticmethod
    def _build_uploaded_documents(uploaded_documents: object) -> List[Document]:
        if not isinstance(uploaded_documents, list):
            return []
        docs: list[Document] = []
        for idx, item in enumerate(uploaded_documents, start=1):
            if isinstance(item, str):
                text = item.strip()
                if not text:
                    continue
                docs.append(
                    Document(
                        id=f"uploaded-{idx}",
                        text=text,
                        metadata={"source": "uploaded", "url": "", "score": 0.0},
                    )
                )
                continue
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or item.get("content") or "").strip()
            if not text:
                continue
            doc_id = str(item.get("id") or f"uploaded-{idx}")
            docs.append(
                Document(
                    id=doc_id,
                    text=text,
                    metadata={
                        "source": str(item.get("source") or "uploaded"),
                        "url": str(item.get("url") or ""),
                        "score": 0.0,
                    },
                )
            )
        return docs

    @staticmethod
    def _build_rag_source_documents(rag_sources: object) -> List[Document]:
        if not isinstance(rag_sources, list):
            return []
        docs: list[Document] = []
        for idx, source_cfg in enumerate(rag_sources, start=1):
            if not isinstance(source_cfg, dict):
                continue
            if not bool(source_cfg.get("enabled", True)):
                continue
            source_id = str(source_cfg.get("id") or "").strip().lower()
            source_name = str(
                source_cfg.get("source")
                or source_cfg.get("type")
                or source_id
                or source_cfg.get("name")
                or f"rag-source-{idx}"
            )
            source_url = str(source_cfg.get("url") or "")
            inline_text = str(source_cfg.get("text") or source_cfg.get("content") or "").strip()
            if inline_text:
                docs.append(
                    Document(
                        id=str(source_cfg.get("id") or f"{source_name}-{idx}"),
                        text=inline_text,
                        metadata={
                            "source": (source_id or source_name).lower(),
                            "url": source_url,
                            "score": 0.0,
                            "weight": float(source_cfg.get("weight", 1.0) or 1.0),
                        },
                    )
                )

            nested_docs = source_cfg.get("documents")
            if not isinstance(nested_docs, list):
                continue
            for doc_idx, nested in enumerate(nested_docs, start=1):
                if isinstance(nested, str):
                    nested_text = nested.strip()
                    if not nested_text:
                        continue
                    docs.append(
                        Document(
                            id=f"{source_name}-{idx}-{doc_idx}",
                            text=nested_text,
                            metadata={
                                "source": (source_id or source_name).lower(),
                                "url": source_url,
                                "score": 0.0,
                                "weight": float(source_cfg.get("weight", 1.0) or 1.0),
                            },
                        )
                    )
                    continue
                if not isinstance(nested, dict):
                    continue
                nested_text = str(nested.get("text") or nested.get("content") or "").strip()
                if not nested_text:
                    continue
                docs.append(
                    Document(
                        id=str(nested.get("id") or f"{source_name}-{idx}-{doc_idx}"),
                        text=nested_text,
                        metadata={
                            "source": str(nested.get("source") or source_id or source_name).lower(),
                            "url": str(nested.get("url") or source_url),
                            "score": 0.0,
                            "weight": float(source_cfg.get("weight", 1.0) or 1.0),
                        },
                    )
                )
        return docs

    @staticmethod
    def _fetch_json(url: str, timeout_seconds: float) -> dict[str, Any] | list[Any] | None:
        req = Request(url, headers={"User-Agent": "CLARA-ML/0.1"})
        with urlopen(req, timeout=max(timeout_seconds, 0.1)) as response:
            payload = response.read().decode("utf-8", errors="ignore")
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return None

    def _retrieve_pubmed(self, query: str, *, top_k: int, timeout_seconds: float) -> List[Document]:
        if top_k <= 0:
            return []
        search_url = f"{self._PUBMED_ESEARCH_URL}?" + urlencode(
            {
                "db": "pubmed",
                "retmode": "json",
                "retmax": str(top_k),
                "sort": "relevance",
                "term": query,
            }
        )
        search_payload = self._fetch_json(search_url, timeout_seconds)
        if not isinstance(search_payload, dict):
            return []
        id_list = search_payload.get("esearchresult", {}).get("idlist", [])
        if not isinstance(id_list, list) or not id_list:
            return []

        summary_url = f"{self._PUBMED_ESUMMARY_URL}?" + urlencode(
            {
                "db": "pubmed",
                "retmode": "json",
                "id": ",".join(str(pmid) for pmid in id_list),
            }
        )
        summary_payload = self._fetch_json(summary_url, timeout_seconds)
        if not isinstance(summary_payload, dict):
            return []
        records = summary_payload.get("result", {})
        if not isinstance(records, dict):
            return []

        docs: list[Document] = []
        for pmid in id_list:
            record = records.get(str(pmid), {})
            if not isinstance(record, dict):
                continue
            title = str(record.get("title") or "").strip()
            if not title:
                continue
            journal = str(record.get("fulljournalname") or record.get("source") or "").strip()
            pub_date = str(record.get("pubdate") or "").strip()
            text = ". ".join(part for part in [title, journal, pub_date] if part)
            docs.append(
                Document(
                    id=f"pubmed-{pmid}",
                    text=text,
                    metadata={
                        "source": "pubmed",
                        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                        "score": 0.0,
                    },
                )
            )
        return docs

    def _retrieve_europe_pmc(
        self, query: str, *, top_k: int, timeout_seconds: float
    ) -> List[Document]:
        if top_k <= 0:
            return []
        search_url = f"{self._EUROPEPMC_SEARCH_URL}?" + urlencode(
            {
                "query": query,
                "format": "json",
                "pageSize": str(top_k),
                "resultType": "core",
            }
        )
        payload = self._fetch_json(search_url, timeout_seconds)
        if not isinstance(payload, dict):
            return []
        result_list = payload.get("resultList", {}).get("result", [])
        if not isinstance(result_list, list):
            return []

        docs: list[Document] = []
        for item in result_list:
            if not isinstance(item, dict):
                continue
            source = str(item.get("source") or "europepmc").strip().lower()
            source_id = str(item.get("id") or "").strip()
            title = str(item.get("title") or "").strip()
            if not source_id or not title:
                continue
            journal = str(item.get("journalTitle") or "").strip()
            pub_year = str(item.get("pubYear") or "").strip()
            text = ". ".join(part for part in [title, journal, pub_year] if part)
            if source == "med":
                url = f"https://pubmed.ncbi.nlm.nih.gov/{source_id}/"
            else:
                url = f"https://europepmc.org/article/{source.upper()}/{source_id}"
            docs.append(
                Document(
                    id=f"europepmc-{source}-{source_id}",
                    text=text,
                    metadata={"source": "europepmc", "url": url, "score": 0.0},
                )
            )
        return docs

    def retrieve_external_scientific(
        self,
        query: str,
        top_k: int = 3,
        *,
        timeout_seconds: float = 1.2,
        rag_sources: object = None,
    ) -> List[Document]:
        source_policies = self._parse_source_policies(rag_sources)
        docs: list[Document] = []
        try:
            docs.extend(self._retrieve_pubmed(query, top_k=top_k, timeout_seconds=timeout_seconds))
        except Exception:
            pass
        try:
            docs.extend(
                self._retrieve_europe_pmc(query, top_k=top_k, timeout_seconds=timeout_seconds)
            )
        except Exception:
            pass
        deduped = self._dedupe_documents(docs)
        return self._score_documents(query, deduped, top_k=top_k, source_policies=source_policies)

    def retrieve_internal(
        self,
        query: str,
        top_k: int = 3,
        *,
        file_retrieval_enabled: bool = True,
        rag_sources: object = None,
        uploaded_documents: object = None,
    ) -> List[Document]:
        if top_k <= 0:
            return []
        source_policies = self._parse_source_policies(rag_sources)
        candidates = list(self.documents)
        if file_retrieval_enabled:
            candidates.extend(self._build_uploaded_documents(uploaded_documents))
            candidates.extend(self._build_rag_source_documents(rag_sources))
        return self._score_documents(
            query,
            self._dedupe_documents(candidates),
            top_k=top_k,
            source_policies=source_policies,
        )

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        *,
        scientific_retrieval_enabled: bool = False,
        web_retrieval_enabled: bool = False,
        file_retrieval_enabled: bool = True,
        rag_sources: object = None,
        uploaded_documents: object = None,
    ) -> List[Document]:
        if top_k <= 0:
            return []

        staged_docs = self.retrieve_internal(
            query,
            top_k=max(top_k, 1),
            file_retrieval_enabled=file_retrieval_enabled,
            rag_sources=rag_sources,
            uploaded_documents=uploaded_documents,
        )

        if scientific_retrieval_enabled:
            staged_docs.extend(
                self.retrieve_external_scientific(
                    query,
                    top_k=max(
                        top_k,
                        min(settings.pubmed_esearch_max_results, settings.europe_pmc_max_results),
                    ),
                    timeout_seconds=settings.pubmed_connector_timeout_seconds,
                    rag_sources=rag_sources,
                )
            )

        if web_retrieval_enabled:
            # Placeholder for future non-scientific web retrieval.
            staged_docs.extend([])

        return self._score_documents(
            query,
            self._dedupe_documents(staged_docs),
            top_k=top_k,
            source_policies=self._parse_source_policies(rag_sources),
        )
