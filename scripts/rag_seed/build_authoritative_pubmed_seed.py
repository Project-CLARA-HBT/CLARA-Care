from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import OrderedDict
from pathlib import Path
from typing import Any

DEFAULT_QUERIES = [
    "DASH diet hypertension randomized trial",
    "Mediterranean diet cardiovascular disease meta-analysis",
    "DASH versus Mediterranean diet cardiovascular outcomes",
    "hypertension dietary pattern blood pressure adults",
    "heart failure sodium restriction diet evidence",
    "cardiovascular prevention nutrition guideline",
    "type 2 diabetes diet cardiovascular outcomes",
    "dyslipidemia dietary intervention guideline",
]

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def _http_get_json(url: str, params: dict[str, Any], timeout: float) -> dict[str, Any]:
    query = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{url}?{query}", headers={"User-Agent": "clara-rag-seed/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:  # nosec B310
        payload = response.read().decode("utf-8", errors="replace")
    return json.loads(payload)


def _http_get_text(url: str, params: dict[str, Any], timeout: float) -> str:
    query = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{url}?{query}", headers={"User-Agent": "clara-rag-seed/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:  # nosec B310
        return response.read().decode("utf-8", errors="replace")


def esearch(query: str, *, retmax: int, timeout: float) -> list[str]:
    payload = _http_get_json(
        f"{EUTILS_BASE}/esearch.fcgi",
        {
            "db": "pubmed",
            "term": query,
            "retmax": str(retmax),
            "retmode": "json",
            "sort": "relevance",
        },
        timeout=timeout,
    )
    id_list = payload.get("esearchresult", {}).get("idlist")
    if not isinstance(id_list, list):
        return []
    return [str(item) for item in id_list if str(item).strip()]


def efetch(ids: list[str], *, timeout: float) -> list[dict[str, str]]:
    if not ids:
        return []
    xml_payload = _http_get_text(
        f"{EUTILS_BASE}/efetch.fcgi",
        {
            "db": "pubmed",
            "id": ",".join(ids),
            "retmode": "xml",
        },
        timeout=timeout,
    )

    root = ET.fromstring(xml_payload)
    rows: list[dict[str, str]] = []
    for article in root.findall(".//PubmedArticle"):
        pmid = "".join(article.findtext(".//PMID") or "").strip()
        title = "".join(article.findtext(".//ArticleTitle") or "").strip()
        journal = "".join(article.findtext(".//Journal/Title") or "").strip()

        pub_year = ""
        year_node = article.find(".//PubDate/Year")
        medline_node = article.find(".//PubDate/MedlineDate")
        if year_node is not None and year_node.text:
            pub_year = year_node.text.strip()
        elif medline_node is not None and medline_node.text:
            pub_year = medline_node.text.strip()[:4]

        abstract_parts: list[str] = []
        for abstract_node in article.findall(".//Abstract/AbstractText"):
            label = abstract_node.attrib.get("Label", "").strip()
            text = "".join(abstract_node.itertext()).strip()
            if not text:
                continue
            if label:
                abstract_parts.append(f"{label}: {text}")
            else:
                abstract_parts.append(text)

        rows.append(
            {
                "pmid": pmid,
                "title": title,
                "journal": journal,
                "year": pub_year,
                "abstract": " ".join(abstract_parts).strip(),
            }
        )
    return rows


def build_seed_documents(
    *,
    queries: list[str],
    per_query: int,
    timeout_seconds: float,
    sleep_seconds: float,
) -> list[dict[str, Any]]:
    docs_by_id: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for query in queries:
        ids = esearch(query, retmax=per_query, timeout=timeout_seconds)
        articles = efetch(ids, timeout=timeout_seconds)

        for row in articles:
            pmid = row.get("pmid", "").strip()
            if not pmid:
                continue
            title = row.get("title", "").strip()
            abstract = row.get("abstract", "").strip()
            if not title:
                continue

            content = [title]
            if abstract:
                content.append(abstract[:2400])
            else:
                content.append("No abstract available from PubMed metadata.")

            journal = row.get("journal", "").strip()
            year = row.get("year", "").strip()
            citation_bits = [bit for bit in [journal, year] if bit]
            if citation_bits:
                content.append(f"Source: {' | '.join(citation_bits)}")

            doc = {
                "id": f"pubmed-{pmid}",
                "text": "\n".join(content).strip(),
                "metadata": {
                    "source": "pubmed",
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    "score": 0.0,
                    "weight": 1.25,
                    "tags": ["pubmed", "cardiometabolic", "nutrition", "evidence"],
                    "trust_tier": "tier_1",
                    "file_type": "abstract",
                    "query_seed": query,
                },
            }
            docs_by_id[doc["id"]] = doc

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    return list(docs_by_id.values())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build authoritative PubMed seed docs for CLARA RAG."
    )
    parser.add_argument(
        "--output",
        default="services/ml/src/clara_ml/nlp/seed_data/pubmed_authoritative_seed.json",
        help="Output JSON file.",
    )
    parser.add_argument(
        "--per-query",
        type=int,
        default=24,
        help="How many PMIDs to fetch per query.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=14.0,
        help="HTTP timeout for each EUtils request.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.25,
        help="Throttle between queries.",
    )
    parser.add_argument(
        "--query",
        action="append",
        dest="queries",
        default=[],
        help="Additional query (repeatable).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    queries = DEFAULT_QUERIES + [item.strip() for item in args.queries if item.strip()]

    docs = build_seed_documents(
        queries=queries,
        per_query=max(5, min(100, args.per_query)),
        timeout_seconds=max(3.0, args.timeout_seconds),
        sleep_seconds=max(0.0, args.sleep_seconds),
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Queries: {len(queries)}")
    print(f"Documents: {len(docs)}")
    print(f"Output: {output}")


if __name__ == "__main__":
    main()
