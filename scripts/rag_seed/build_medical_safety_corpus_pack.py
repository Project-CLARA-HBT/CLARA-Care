from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .acquisition import acquire_seed_pdfs, to_acquisition_report, to_seed_documents
from .build_authoritative_pubmed_seed import build_seed_documents
from .io_utils import write_json
from .models import SourceCatalogEntry

DEFAULT_SOURCE_CSV = "docs/research/data/medical-safety-corpus-sources-2026-03-31.csv"
DEFAULT_QUERY_CSV = "docs/research/data/medical-safety-pubmed-queries-2026-03-31.csv"
DEFAULT_OUT_MANIFEST = "data/rag_seed/manifests/medical_safety_corpus_manifest.json"
DEFAULT_OUT_REGISTRY_SEED = "data/rag_seed/manifests/medical_safety_registry_seed.json"
DEFAULT_OUT_VN_CATALOG = "data/rag_seed/manifests/medical_safety_vn_pdf_catalog.csv"
DEFAULT_OUT_COMBINED_SEED = "data/rag_seed/manifests/medical_safety_combined_seed.json"
DEFAULT_OUT_VN_ACQUISITION_REPORT = (
    "data/rag_seed/manifests/medical_safety_vn_acquisition_report.json"
)
DEFAULT_EXISTING_SEEDS = [
    "services/ml/src/clara_ml/nlp/seed_data/vn_medical_seed.json",
    "services/ml/src/clara_ml/nlp/seed_data/pubmed_authoritative_seed.json",
]

VN_PDF_INGEST_STRATEGIES = {"pdf_direct", "pdf_discovery", "page_pdf_links"}


@dataclass(frozen=True)
class CorpusSource:
    source_id: str
    region: str
    language: str
    owner: str
    category: str
    source_type: str
    entry_url: str
    discovery_url: str
    license: str
    access_mode: str
    ingest_strategy: str
    trust_tier: str
    confidence: str
    priority: int
    refresh_cadence: str
    seed_action: str
    scope: str
    notes: str


@dataclass(frozen=True)
class QuerySpec:
    query_id: str
    query: str
    focus_area: str
    priority: int
    notes: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build practical medical safety corpus pack for CLARA RAG."
    )
    parser.add_argument("--source-csv", default=DEFAULT_SOURCE_CSV)
    parser.add_argument("--query-csv", default=DEFAULT_QUERY_CSV)
    parser.add_argument("--out-manifest", default=DEFAULT_OUT_MANIFEST)
    parser.add_argument("--out-registry-seed", default=DEFAULT_OUT_REGISTRY_SEED)
    parser.add_argument("--out-vn-catalog", default=DEFAULT_OUT_VN_CATALOG)
    parser.add_argument("--out-combined-seed", default=DEFAULT_OUT_COMBINED_SEED)
    parser.add_argument(
        "--out-vn-acquisition-report", default=DEFAULT_OUT_VN_ACQUISITION_REPORT
    )
    parser.add_argument(
        "--existing-seed",
        action="append",
        dest="existing_seeds",
        default=[],
        help="Existing seed JSON to merge into combined seed output.",
    )
    parser.add_argument(
        "--include-default-existing-seeds",
        action="store_true",
        help="Include vn_medical_seed.json and pubmed_authoritative_seed.json.",
    )
    parser.add_argument(
        "--build-combined-seed",
        action="store_true",
        help="Write combined seed JSON by merging registry docs with existing seeds.",
    )
    parser.add_argument(
        "--build-pubmed-live",
        action="store_true",
        help="Fetch live PubMed documents using the curated safety query set.",
    )
    parser.add_argument(
        "--build-vn-live",
        action="store_true",
        help="Attempt live VN PDF acquisition using the filtered VN catalog.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=12.0)
    parser.add_argument("--sleep-seconds", type=float, default=0.4)
    parser.add_argument("--pubmed-per-query", type=int, default=12)
    parser.add_argument("--max-vn-docs-per-source", type=int, default=2)
    parser.add_argument("--max-vn-candidate-urls-per-source", type=int, default=10)
    return parser.parse_args()


def load_sources(path: Path) -> list[CorpusSource]:
    if not path.exists():
        raise FileNotFoundError(f"Source CSV not found: {path}")

    rows: list[CorpusSource] = []
    with path.open("r", encoding="utf-8", newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        for raw in reader:
            source_id = str(raw.get("source_id") or "").strip()
            if not source_id:
                continue
            rows.append(
                CorpusSource(
                    source_id=source_id,
                    region=str(raw.get("region") or "").strip().lower(),
                    language=str(raw.get("language") or "").strip().lower(),
                    owner=str(raw.get("owner") or "").strip(),
                    category=str(raw.get("category") or "").strip(),
                    source_type=str(raw.get("source_type") or "").strip().lower(),
                    entry_url=str(raw.get("entry_url") or "").strip(),
                    discovery_url=str(raw.get("discovery_url") or "").strip(),
                    license=str(raw.get("license") or "").strip(),
                    access_mode=str(raw.get("access_mode") or "").strip().lower(),
                    ingest_strategy=str(raw.get("ingest_strategy") or "")
                    .strip()
                    .lower(),
                    trust_tier=str(raw.get("trust_tier") or "").strip().upper(),
                    confidence=str(raw.get("confidence") or "").strip().lower(),
                    priority=int(str(raw.get("priority") or "3").strip() or "3"),
                    refresh_cadence=str(raw.get("refresh_cadence") or "").strip(),
                    seed_action=str(raw.get("seed_action") or "").strip().lower(),
                    scope=str(raw.get("scope") or "").strip(),
                    notes=str(raw.get("notes") or "").strip(),
                )
            )
    return rows


def load_queries(path: Path) -> list[QuerySpec]:
    if not path.exists():
        raise FileNotFoundError(f"Query CSV not found: {path}")

    rows: list[QuerySpec] = []
    with path.open("r", encoding="utf-8", newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        for raw in reader:
            query_id = str(raw.get("query_id") or "").strip()
            query = str(raw.get("query") or "").strip()
            if not query_id or not query:
                continue
            rows.append(
                QuerySpec(
                    query_id=query_id,
                    query=query,
                    focus_area=str(raw.get("focus_area") or "").strip(),
                    priority=int(str(raw.get("priority") or "3").strip() or "3"),
                    notes=str(raw.get("notes") or "").strip(),
                )
            )
    return rows


def build_registry_seed_docs(sources: Iterable[CorpusSource]) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for source in sources:
        doc_id = f"registry-{source.source_id.lower().replace('_', '-')}"
        discovery = source.discovery_url or source.entry_url
        text = (
            f"Authoritative medical safety corpus source. "
            f"Source ID: {source.source_id}. Region: {source.region}. Language: {source.language}. "
            f"Owner: {source.owner}. Category: {source.category}. Source type: {source.source_type}. "
            f"Primary URL: {source.entry_url}. Discovery URL: {discovery}. "
            f"Access mode: {source.access_mode}. Ingest strategy: {source.ingest_strategy}. "
            f"Trust tier: {source.trust_tier}. Priority: {source.priority}. "
            f"Refresh cadence: {source.refresh_cadence}. "
            f"Scope: {source.scope}. Notes: {source.notes}"
        )
        docs.append(
            {
                "id": doc_id,
                "text": text,
                "metadata": {
                    "source": "medical_safety_registry",
                    "url": source.entry_url,
                    "score": 0.0,
                    "weight": trust_tier_weight(source.trust_tier),
                    "tags": [
                        "medical-safety",
                        source.region,
                        source.source_type,
                        source.source_id.lower(),
                    ],
                    "trust_tier": normalize_trust_tier(source.trust_tier),
                    "file_type": "registry",
                    "source_id": source.source_id,
                    "owner": source.owner,
                    "license": source.license,
                    "seed_action": source.seed_action,
                },
            }
        )
    return docs


def build_vn_catalog_rows(sources: Iterable[CorpusSource]) -> list[SourceCatalogEntry]:
    rows: list[SourceCatalogEntry] = []
    for source in sources:
        if source.region != "vn":
            continue
        if source.ingest_strategy not in VN_PDF_INGEST_STRATEGIES:
            continue
        direct_url = source.discovery_url or source.entry_url
        rows.append(
            SourceCatalogEntry(
                source_id=source.source_id,
                owner=source.owner,
                category=source.category,
                entry_url=source.entry_url,
                direct_url_example=direct_url,
                update_cadence_observed=source.refresh_cadence,
                usage_notes=source.notes,
                trust_tier=source.trust_tier,
                confidence=source.confidence,
            )
        )
    return rows


def write_vn_catalog_csv(path: Path, rows: Iterable[SourceCatalogEntry]) -> None:
    records = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(
            file_obj,
            fieldnames=[
                "source_id",
                "owner",
                "category",
                "entry_url",
                "direct_url_example",
                "update_cadence_observed",
                "usage_notes",
                "trust_tier",
                "confidence",
            ],
        )
        writer.writeheader()
        for row in records:
            writer.writerow(
                {
                    "source_id": row.source_id,
                    "owner": row.owner,
                    "category": row.category,
                    "entry_url": row.entry_url,
                    "direct_url_example": row.direct_url_example,
                    "update_cadence_observed": row.update_cadence_observed,
                    "usage_notes": row.usage_notes,
                    "trust_tier": row.trust_tier,
                    "confidence": row.confidence,
                }
            )


def load_seed_docs(paths: Iterable[Path]) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, list):
            docs.extend([item for item in payload if isinstance(item, dict)])
    return docs


def dedupe_docs(documents: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for doc in documents:
        doc_id = str(doc.get("id") or "").strip()
        metadata = doc.get("metadata")
        url = ""
        if isinstance(metadata, dict):
            url = str(metadata.get("url") or "").strip()
        key = doc_id or url or json.dumps(doc, sort_keys=True, ensure_ascii=False)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(doc)
    return deduped


def build_manifest(
    *,
    sources: list[CorpusSource],
    queries: list[QuerySpec],
    registry_seed_docs: list[dict[str, Any]],
    vn_catalog_rows: list[SourceCatalogEntry],
    existing_seed_paths: list[Path],
    live_pubmed_doc_count: int,
    live_vn_doc_count: int,
) -> dict[str, Any]:
    by_region = Counter(source.region for source in sources)
    by_type = Counter(source.source_type for source in sources)
    by_trust = Counter(source.trust_tier for source in sources)
    by_strategy = Counter(source.ingest_strategy for source in sources)
    by_action = Counter(source.seed_action for source in sources)
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    return {
        "pack_id": "medical-safety-corpus-pack-2026-03-31",
        "generated_at": generated_at,
        "goal": "Practical trustworthy corpus pack for medication safety, DDI, labeling, safety bulletins, and guideline-grounded research.",
        "constraints": [
            "Do not alter retrieval or ranking logic.",
            "Prefer official VN + international sources with stable provenance.",
            "Use metadata-only registry entries when full-text access is unstable or license-restricted.",
        ],
        "coverage": {
            "source_count": len(sources),
            "pubmed_query_count": len(queries),
            "vn_pdf_seed_source_count": len(vn_catalog_rows),
            "registry_seed_doc_count": len(registry_seed_docs),
            "live_pubmed_doc_count": live_pubmed_doc_count,
            "live_vn_doc_count": live_vn_doc_count,
            "existing_seed_inputs": [str(path) for path in existing_seed_paths if path.exists()],
        },
        "breakdown": {
            "by_region": dict(by_region),
            "by_source_type": dict(by_type),
            "by_trust_tier": dict(by_trust),
            "by_ingest_strategy": dict(by_strategy),
            "by_seed_action": dict(by_action),
        },
        "sources": [
            {
                "source_id": source.source_id,
                "region": source.region,
                "language": source.language,
                "owner": source.owner,
                "category": source.category,
                "source_type": source.source_type,
                "entry_url": source.entry_url,
                "discovery_url": source.discovery_url,
                "license": source.license,
                "access_mode": source.access_mode,
                "ingest_strategy": source.ingest_strategy,
                "trust_tier": source.trust_tier,
                "confidence": source.confidence,
                "priority": source.priority,
                "refresh_cadence": source.refresh_cadence,
                "seed_action": source.seed_action,
                "scope": source.scope,
                "notes": source.notes,
            }
            for source in sources
        ],
        "pubmed_queries": [
            {
                "query_id": query.query_id,
                "query": query.query,
                "focus_area": query.focus_area,
                "priority": query.priority,
                "notes": query.notes,
            }
            for query in queries
        ],
    }


def trust_tier_weight(trust_tier: str) -> float:
    normalized = trust_tier.strip().upper()
    if normalized == "A1":
        return 1.0
    if normalized == "A2":
        return 0.95
    if normalized == "B1":
        return 0.8
    if normalized == "C1":
        return 0.6
    return 0.75


def normalize_trust_tier(trust_tier: str) -> str:
    normalized = trust_tier.strip().upper()
    if normalized == "A1":
        return "tier_1"
    if normalized == "A2":
        return "tier_2"
    if normalized == "B1":
        return "tier_3"
    if normalized == "C1":
        return "tier_4"
    return "tier_3"


def main() -> None:
    args = parse_args()

    source_csv = Path(args.source_csv)
    query_csv = Path(args.query_csv)
    out_manifest = Path(args.out_manifest)
    out_registry_seed = Path(args.out_registry_seed)
    out_vn_catalog = Path(args.out_vn_catalog)
    out_combined_seed = Path(args.out_combined_seed)
    out_vn_acquisition_report = Path(args.out_vn_acquisition_report)

    sources = load_sources(source_csv)
    queries = load_queries(query_csv)
    registry_seed_docs = build_registry_seed_docs(sources)
    vn_catalog_rows = build_vn_catalog_rows(sources)

    write_json(out_registry_seed, registry_seed_docs)
    write_vn_catalog_csv(out_vn_catalog, vn_catalog_rows)

    existing_seed_paths = [Path(item) for item in args.existing_seeds]
    if args.include_default_existing_seeds:
        existing_seed_paths.extend(Path(item) for item in DEFAULT_EXISTING_SEEDS)
    deduped_seed_paths: list[Path] = []
    seen_paths: set[str] = set()
    for path in existing_seed_paths:
        key = str(path)
        if key in seen_paths:
            continue
        seen_paths.add(key)
        deduped_seed_paths.append(path)

    combined_docs: list[dict[str, Any]] = list(registry_seed_docs)
    live_pubmed_doc_count = 0
    live_vn_doc_count = 0

    if args.build_pubmed_live and queries:
        live_pubmed_docs = build_seed_documents(
            queries=[item.query for item in queries],
            per_query=max(5, min(100, args.pubmed_per_query)),
            timeout_seconds=max(3.0, args.timeout_seconds),
            sleep_seconds=max(0.0, args.sleep_seconds),
        )
        live_pubmed_doc_count = len(live_pubmed_docs)
        combined_docs.extend(live_pubmed_docs)

    if args.build_vn_live and vn_catalog_rows:
        acquired = acquire_seed_pdfs(
            vn_catalog_rows,
            output_dir=Path("data/rag_seed/downloads"),
            max_sources=0,
            max_docs_per_source=max(1, args.max_vn_docs_per_source),
            max_candidate_urls_per_source=max(1, args.max_vn_candidate_urls_per_source),
            timeout_seconds=max(3.0, args.timeout_seconds),
            sleep_seconds=max(0.0, args.sleep_seconds),
        )
        live_vn_doc_count = len(acquired)
        if acquired:
            write_json(out_vn_acquisition_report, to_acquisition_report(acquired))
            combined_docs.extend(to_seed_documents(acquired, catalog_entries=vn_catalog_rows))

    manifest = build_manifest(
        sources=sources,
        queries=queries,
        registry_seed_docs=registry_seed_docs,
        vn_catalog_rows=vn_catalog_rows,
        existing_seed_paths=deduped_seed_paths,
        live_pubmed_doc_count=live_pubmed_doc_count,
        live_vn_doc_count=live_vn_doc_count,
    )
    write_json(out_manifest, manifest)

    if args.build_combined_seed:
        combined_docs.extend(load_seed_docs(deduped_seed_paths))
        write_json(out_combined_seed, dedupe_docs(combined_docs))

    print(f"Sources: {len(sources)}")
    print(f"Queries: {len(queries)}")
    print(f"Registry seed docs: {len(registry_seed_docs)}")
    print(f"VN PDF seed sources: {len(vn_catalog_rows)}")
    print(f"Manifest: {out_manifest}")
    print(f"Registry seed: {out_registry_seed}")
    print(f"VN catalog: {out_vn_catalog}")
    if args.build_combined_seed:
        print(f"Combined seed: {out_combined_seed}")
    if args.build_vn_live:
        print(f"VN acquisition report: {out_vn_acquisition_report}")


if __name__ == "__main__":
    main()
