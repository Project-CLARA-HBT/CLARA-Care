from __future__ import annotations

from pathlib import Path
from typing import Any

from clara_ml.nlp.seed_loader import load_seed_json
from clara_ml.rag.retrieval.domain import Document

_DEFAULT_SEED_DIR = Path(__file__).resolve().parents[1] / "nlp" / "seed_data"


def base_documents() -> list[Document]:
    return [
        Document(
            id="byt-001",
            text="Bo Y Te guidance on safe medicine use in older adults.",
            metadata={"source": "byt", "url": "https://moh.gov.vn/", "score": 0.0},
        ),
        Document(
            id="duoc-thu-001",
            text="National drug handbook warning for NSAID interactions.",
            metadata={"source": "duoc-thu", "url": "https://dav.gov.vn/", "score": 0.0},
        ),
        Document(
            id="pubmed-001",
            text="PubMed: medication adherence improves with reminders.",
            metadata={
                "source": "seed-pubmed",
                "url": "https://pubmed.ncbi.nlm.nih.gov/",
                "score": 0.0,
            },
        ),
    ]


def load_seed_documents(seed_dir: Path | None = None) -> list[Document]:
    actual_seed_dir = seed_dir or _DEFAULT_SEED_DIR
    payload = load_seed_json(actual_seed_dir)
    docs: list[Document] = []

    for idx, item in enumerate(payload, start=1):
        parsed = _to_document(item, idx=idx)
        if parsed is None:
            continue
        docs.append(parsed)
    return docs


def _to_document(item: Any, *, idx: int) -> Document | None:
    if not isinstance(item, dict):
        return None
    doc_id = str(item.get("id") or f"seed-{idx}").strip()
    text = str(item.get("text") or item.get("content") or "").strip()
    metadata_raw = item.get("metadata")
    metadata = dict(metadata_raw) if isinstance(metadata_raw, dict) else {}

    if not text:
        source = str(item.get("source") or metadata.get("source") or "seed").strip()
        title = str(item.get("title") or metadata.get("title") or "").strip()
        drug = str(item.get("drug") or "").strip()
        note = str(item.get("note") or "").strip()
        text = ". ".join(part for part in [title, drug, note] if part).strip()
        if not text:
            text = f"Seed record from {source}"

    metadata.setdefault("source", str(item.get("source") or metadata.get("source") or "seed"))
    metadata.setdefault("url", str(item.get("url") or metadata.get("url") or ""))
    metadata.setdefault("score", 0.0)
    if "trust_tier" in item and "trust_tier" not in metadata:
        metadata["trust_tier"] = item["trust_tier"]
    if "tags" in item and "tags" not in metadata:
        metadata["tags"] = item["tags"]
    return Document(id=doc_id, text=text, metadata=metadata)
