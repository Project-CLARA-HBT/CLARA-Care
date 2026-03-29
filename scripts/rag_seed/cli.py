from __future__ import annotations

import argparse
from pathlib import Path

from .acquisition import acquire_seed_pdfs, to_acquisition_report, to_seed_documents
from .io_utils import load_catalog_csv, write_json, write_manifest_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Acquire VN medical PDFs and build seed JSON for CLARA RAG."
    )
    parser.add_argument(
        "--catalog",
        default="docs/research/data/vn-medical-pdf-sources-phase1-part1-2026-03-29.csv",
        help="Path to VN source catalog CSV.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/rag_seed/downloads",
        help="Directory to store downloaded PDFs.",
    )
    parser.add_argument(
        "--manifest-jsonl",
        default="data/rag_seed/manifests/vn_medical_manifest.jsonl",
        help="Output manifest jsonl path.",
    )
    parser.add_argument(
        "--report-json",
        default="data/rag_seed/manifests/vn_medical_report.json",
        help="Output report json path.",
    )
    parser.add_argument(
        "--seed-json",
        default="services/ml/src/clara_ml/nlp/seed_data/vn_medical_seed.json",
        help="Output seed JSON path consumed by ML RAG runtime.",
    )
    parser.add_argument("--max-sources", type=int, default=0, help="0 = all sources.")
    parser.add_argument("--max-docs-per-source", type=int, default=2)
    parser.add_argument("--max-candidate-urls-per-source", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=float, default=14.0)
    parser.add_argument("--sleep-seconds", type=float, default=0.5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    entries = load_catalog_csv(Path(args.catalog))
    acquired = acquire_seed_pdfs(
        entries,
        output_dir=Path(args.output_dir),
        max_sources=max(args.max_sources, 0),
        max_docs_per_source=max(args.max_docs_per_source, 1),
        max_candidate_urls_per_source=max(args.max_candidate_urls_per_source, 1),
        timeout_seconds=max(args.timeout_seconds, 0.5),
        sleep_seconds=max(args.sleep_seconds, 0.0),
    )

    write_manifest_jsonl(Path(args.manifest_jsonl), acquired)
    write_json(Path(args.report_json), to_acquisition_report(acquired))
    write_json(
        Path(args.seed_json), to_seed_documents(acquired, catalog_entries=entries)
    )

    print(f"Catalog sources: {len(entries)}")
    print(f"Downloaded docs: {len(acquired)}")
    print(f"Manifest: {args.manifest_jsonl}")
    print(f"Report: {args.report_json}")
    print(f"Seed JSON: {args.seed_json}")


if __name__ == "__main__":
    main()
