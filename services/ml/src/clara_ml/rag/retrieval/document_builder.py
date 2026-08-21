from __future__ import annotations

from typing import Any

from .domain import Document
from .text_utils import normalize_tags, normalize_trust_tier, safe_weight


class DocumentBuilder:
    @staticmethod
    def normalized_document(doc: Document, *, default_source: str) -> Document:
        metadata = dict(doc.metadata or {})
        metadata.setdefault("source", str(default_source).strip().lower() or "internal")
        metadata.setdefault("url", "")
        metadata.setdefault("score", 0.0)
        metadata["weight"] = safe_weight(metadata.get("weight", 1.0), default=1.0)
        metadata["tags"] = normalize_tags(metadata.get("tags"))
        metadata.setdefault("trust_tier", "tier_3")
        metadata.setdefault("file_type", "")
        return Document(id=doc.id, text=doc.text, metadata=metadata)

    @staticmethod
    def parse_source_policies(rag_sources: object) -> dict[str, dict[str, float | bool]]:
        if not isinstance(rag_sources, list):
            return {}

        policies: dict[str, dict[str, float | bool]] = {}
        for item in rag_sources:
            if not isinstance(item, dict):
                continue

            keys = [
                str(item.get("id") or "").strip().lower(),
                str(item.get("source") or "").strip().lower(),
                str(item.get("name") or "").strip().lower(),
                str(item.get("type") or "").strip().lower(),
            ]
            keys = [key for key in keys if key]
            if not keys:
                continue

            enabled = bool(item.get("enabled", True))
            weight = safe_weight(item.get("weight", 1.0), default=1.0)
            for key in keys:
                policies[key] = {"enabled": enabled, "weight": weight}

        return policies

    @staticmethod
    def build_uploaded_documents(uploaded_documents: object) -> list[Document]:
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
                        "weight": safe_weight(item.get("weight", 1.0), default=1.0),
                        "tags": normalize_tags(item.get("tags")),
                        "trust_tier": normalize_trust_tier(item.get("trust_tier")),
                    },
                )
            )

        return docs

    @staticmethod
    def _extract_pdf_metadata(source_cfg: dict[str, Any]) -> dict[str, Any]:
        raw_pdf = source_cfg.get("pdf")
        if isinstance(raw_pdf, dict):
            return raw_pdf
        raw_pdf_meta = source_cfg.get("pdf_metadata")
        if isinstance(raw_pdf_meta, dict):
            return raw_pdf_meta
        return {}

    @classmethod
    def _build_registry_entry_documents(
        cls,
        source_cfg: dict[str, Any],
        *,
        source_idx: int,
    ) -> list[Document]:
        registry_blocks: list[Any] = []
        for key in ("vn_registry", "registry", "entries", "source_registry"):
            value = source_cfg.get(key)
            if isinstance(value, list):
                registry_blocks.extend(value)

        if not registry_blocks:
            return []

        default_source = str(
            source_cfg.get("id") or source_cfg.get("source") or source_cfg.get("name") or "vn_source_registry"
        ).strip().lower() or "vn_source_registry"
        default_weight = safe_weight(source_cfg.get("weight", 1.0), default=1.0)
        default_tier = normalize_trust_tier(source_cfg.get("trust_tier") or source_cfg.get("tier"))
        default_tags = normalize_tags(source_cfg.get("tags"))

        docs: list[Document] = []
        for entry_idx, entry in enumerate(registry_blocks, start=1):
            if not isinstance(entry, dict):
                continue
            if not bool(entry.get("enabled", True)):
                continue

            title = str(entry.get("title") or entry.get("name") or "").strip()
            summary = str(entry.get("summary") or entry.get("description") or "").strip()
            text = str(entry.get("text") or entry.get("content") or "").strip()
            entry_source = str(entry.get("source") or default_source).strip().lower() or default_source

            entry_pdf_raw = entry.get("pdf")
            entry_pdf: dict[str, Any] = entry_pdf_raw if isinstance(entry_pdf_raw, dict) else {}
            url = str(entry.get("url") or entry_pdf.get("url") or "").strip()
            tags = normalize_tags(default_tags + normalize_tags(entry.get("tags") or entry_pdf.get("tags")))
            tier = normalize_trust_tier(entry.get("trust_tier") or entry.get("tier") or default_tier)
            weight = safe_weight(entry.get("weight", default_weight), default=default_weight)
            file_type = "pdf" if (".pdf" in url.lower() or entry_pdf) else str(entry.get("file_type") or "")

            body = ". ".join(part for part in [title, summary, text, " ".join(tags)] if part).strip()
            if not body:
                continue

            doc_id = str(entry.get("id") or f"{entry_source}-registry-{source_idx}-{entry_idx}")
            docs.append(
                Document(
                    id=doc_id,
                    text=body,
                    metadata={
                        "source": entry_source,
                        "url": url,
                        "score": 0.0,
                        "weight": weight,
                        "tags": tags,
                        "title": title,
                        "trust_tier": tier,
                        "file_type": file_type,
                        "registry_type": "vn-medical",
                    },
                )
            )

        return docs

    @classmethod
    def build_rag_source_documents(cls, rag_sources: object) -> list[Document]:
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
            source_weight = safe_weight(source_cfg.get("weight", 1.0), default=1.0)
            source_tags = normalize_tags(source_cfg.get("tags"))
            source_tier = normalize_trust_tier(source_cfg.get("trust_tier") or source_cfg.get("tier"))

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
                            "weight": source_weight,
                            "tags": source_tags,
                            "trust_tier": source_tier,
                        },
                    )
                )

            pdf_meta = cls._extract_pdf_metadata(source_cfg)
            pdf_title = str(pdf_meta.get("title") or source_cfg.get("title") or "").strip()
            pdf_url = str(pdf_meta.get("url") or source_url or "").strip()
            pdf_tags = normalize_tags(source_tags + normalize_tags(pdf_meta.get("tags")))
            if pdf_title:
                docs.append(
                    Document(
                        id=str(source_cfg.get("id") or f"{source_name}-{idx}-pdf"),
                        text=". ".join(part for part in [pdf_title, " ".join(pdf_tags)] if part),
                        metadata={
                            "source": (source_id or source_name or "vn_pdf").lower(),
                            "url": pdf_url,
                            "score": 0.0,
                            "weight": source_weight,
                            "tags": pdf_tags,
                            "title": pdf_title,
                            "trust_tier": source_tier,
                            "file_type": "pdf",
                            "registry_type": "vn-medical",
                        },
                    )
                )

            docs.extend(cls._build_registry_entry_documents(source_cfg, source_idx=idx))

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
                                "weight": source_weight,
                                "tags": source_tags,
                                "trust_tier": source_tier,
                            },
                        )
                    )
                    continue

                if not isinstance(nested, dict):
                    continue

                nested_text = str(nested.get("text") or nested.get("content") or "").strip()
                if not nested_text:
                    continue

                nested_url = str(nested.get("url") or source_url)
                nested_tags = normalize_tags(source_tags + normalize_tags(nested.get("tags")))
                nested_tier = normalize_trust_tier(nested.get("trust_tier") or nested.get("tier") or source_tier)
                docs.append(
                    Document(
                        id=str(nested.get("id") or f"{source_name}-{idx}-{doc_idx}"),
                        text=nested_text,
                        metadata={
                            "source": str(nested.get("source") or source_id or source_name).lower(),
                            "url": nested_url,
                            "score": 0.0,
                            "weight": safe_weight(nested.get("weight", source_weight), default=source_weight),
                            "tags": nested_tags,
                            "trust_tier": nested_tier,
                            "file_type": str(nested.get("file_type") or "").lower(),
                        },
                    )
                )

        return docs
