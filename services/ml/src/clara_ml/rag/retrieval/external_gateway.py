from __future__ import annotations

import html
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeoutError
from threading import Lock
from time import monotonic, perf_counter, sleep
import random
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

from clara_ml.config import settings

from .domain import Document
from .text_utils import analyze_query_profile, first_text, query_terms


class ExternalSourceGateway:
    PUBMED_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    PUBMED_ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    EUROPEPMC_SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    OPENALEX_WORKS_URL = "https://api.openalex.org/works"
    CROSSREF_WORKS_URL = "https://api.crossref.org/works"
    CLINICALTRIALS_V2_URL = "https://clinicaltrials.gov/api/v2/studies"
    OPENFDA_LABEL_URL = "https://api.fda.gov/drug/label.json"
    DAILYMED_DRUGNAME_URL = "https://dailymed.nlm.nih.gov/dailymed/services/v1/drugname"
    RXNAV_APPROXIMATE_TERM_URL = "https://rxnav.nlm.nih.gov/REST/approximateTerm.json"
    SEMANTIC_SCHOLAR_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
    _HOST_RATE_LOCK = Lock()
    _HOST_LAST_REQUEST_TS: dict[str, float] = {}

    @classmethod
    def _throttle_before_request(cls, url: str) -> None:
        min_interval = max(0.0, float(settings.rag_external_min_interval_seconds))
        if min_interval <= 0:
            return
        jitter = max(0.0, float(settings.rag_external_jitter_seconds))
        host = cls._safe_host(url) or "global"
        with cls._HOST_RATE_LOCK:
            now = monotonic()
            last = float(cls._HOST_LAST_REQUEST_TS.get(host, 0.0))
            wait_seconds = min_interval - (now - last)
            if wait_seconds > 0:
                wait_seconds += random.uniform(0.0, jitter)
                sleep(wait_seconds)
                now = monotonic()
            cls._HOST_LAST_REQUEST_TS[host] = now

    @staticmethod
    def _fetch_json(
        url: str,
        timeout_seconds: float,
        *,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any] | list[Any] | None:
        ExternalSourceGateway._throttle_before_request(url)
        merged_headers = {"User-Agent": "CLARA-ML/0.1"}
        if headers:
            merged_headers.update(headers)
        request = Request(url, headers=merged_headers)
        with urlopen(request, timeout=max(timeout_seconds, 0.1)) as response:
            payload = response.read().decode("utf-8", errors="ignore")
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _fetch_text(
        url: str,
        timeout_seconds: float,
        *,
        headers: dict[str, str] | None = None,
    ) -> str:
        ExternalSourceGateway._throttle_before_request(url)
        merged_headers = {"User-Agent": "CLARA-ML/0.1"}
        if headers:
            merged_headers.update(headers)
        request = Request(url, headers=merged_headers)
        with urlopen(request, timeout=max(timeout_seconds, 0.1)) as response:
            return response.read().decode("utf-8", errors="ignore")

    @staticmethod
    def _allowed_domains() -> set[str]:
        raw = settings.searxng_crawl_allowed_domains
        return {item.strip().lower() for item in str(raw or "").split(",") if item and item.strip()}

    @staticmethod
    def _domain_is_allowed(url: str, allowed_domains: set[str]) -> bool:
        parsed = urlparse(url)
        host = (parsed.hostname or "").strip().lower()
        if not host:
            return False
        if not allowed_domains:
            # Secure-by-default: never allow open crawl when allowlist is empty.
            return False
        if host in allowed_domains:
            return True
        return any(host.endswith(f".{domain}") for domain in allowed_domains)

    @staticmethod
    def _sanitize_html_snippet(raw_html: str, *, max_chars: int) -> tuple[str, str]:
        title_match = re.search(
            r"<title[^>]*>(.*?)</title>", raw_html, flags=re.IGNORECASE | re.DOTALL
        )
        title = html.unescape(title_match.group(1)).strip() if title_match else ""
        if title:
            title = re.sub(r"\s+", " ", title)

        body = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw_html)
        body = re.sub(r"(?s)<[^>]+>", " ", body)
        body = html.unescape(re.sub(r"\s+", " ", body)).strip()
        max_len = max(256, int(max_chars))
        body = body[:max_len]
        return title, body

    @staticmethod
    def _safe_host(url: str) -> str:
        parsed = urlparse(url)
        return (parsed.hostname or "").strip().lower()

    @staticmethod
    def _medication_terms(query: str, profile: dict[str, Any]) -> list[str]:
        terms: list[str] = []
        primary = str(profile.get("primary_drug") or "").strip().lower()
        co_drugs = [str(item).strip().lower() for item in profile.get("co_drugs", []) if item]
        aliases: dict[str, tuple[str, ...]] = {
            "warfarin": ("warfarin", "coumadin"),
            "ibuprofen": ("ibuprofen",),
            "naproxen": ("naproxen",),
            "diclofenac": ("diclofenac",),
            "aspirin": ("aspirin",),
            "paracetamol": ("paracetamol", "acetaminophen"),
            "nsaid": ("nsaid",),
        }
        for drug in [primary, *co_drugs]:
            if not drug:
                continue
            for alias in aliases.get(drug, (drug,)):
                token = alias.strip().lower()
                if token and token not in terms:
                    terms.append(token)

        if terms:
            return terms[:8]

        fallback_terms = [item for item in query_terms(query) if " " not in item][:8]
        return fallback_terms

    @classmethod
    def _clinical_trials_query(cls, query: str, profile: dict[str, Any]) -> str:
        meds = cls._medication_terms(query, profile)
        if not meds:
            return query
        if bool(profile.get("is_ddi_query")) and len(meds) >= 2:
            return " AND ".join(meds[:3])
        return " ".join(meds[:3])

    @classmethod
    def _ddi_query_phrase(cls, profile: dict[str, Any]) -> str:
        primary = str(profile.get("primary_drug") or "").strip()
        if not primary:
            return ""
        co_drugs = [
            str(item).strip()
            for item in profile.get("co_drugs", [])
            if str(item).strip()
        ][:5]
        if not co_drugs:
            co_drugs = ["ibuprofen", "naproxen", "diclofenac", "aspirin", "paracetamol"]
        co_clause = " OR ".join(co_drugs)
        return f"{primary} ({co_clause}) drug interaction bleeding INR adverse event"

    @classmethod
    def _provider_query(cls, query: str, profile: dict[str, Any], *, provider: str) -> str:
        normalized_provider = provider.strip().lower()
        if normalized_provider == "pubmed":
            return cls._build_pubmed_query(query, profile)
        if normalized_provider == "europepmc":
            return cls._build_europe_pmc_query(query, profile)
        if normalized_provider == "clinicaltrials":
            return cls._clinical_trials_query(query, profile)
        if bool(profile.get("is_ddi_query")):
            ddi_phrase = cls._ddi_query_phrase(profile)
            if ddi_phrase:
                return ddi_phrase
        return query

    @staticmethod
    def _normalize_provider_query_overrides(
        value: dict[str, str] | None,
    ) -> dict[str, str]:
        if not isinstance(value, dict):
            return {}
        normalized: dict[str, str] = {}
        for provider_raw, query_raw in value.items():
            provider = str(provider_raw or "").strip().lower()
            query_text = " ".join(str(query_raw or "").split()).strip()
            if not provider or not query_text:
                continue
            normalized[provider] = query_text[:360]
        return normalized

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {token for token in re.findall(r"[0-9a-zA-ZÀ-ỹ]{2,}", text.lower()) if token}

    @classmethod
    def _is_ddi_evidence_document(cls, profile: dict[str, Any], document: Document) -> bool:
        primary = str(profile.get("primary_drug") or "").strip().lower()
        if not primary:
            return True
        co_drugs = {
            str(item).strip().lower()
            for item in profile.get("co_drugs", [])
            if str(item).strip()
        }
        interaction_terms = {
            "interaction",
            "ddi",
            "contraindication",
            "bleeding",
            "inr",
            "adverse",
            "warning",
            "risk",
            "toxicity",
            "hemorrhage",
        }
        trusted_label_sources = {"openfda", "dailymed", "rxnorm", "rxnav"}

        metadata = document.metadata if isinstance(document.metadata, dict) else {}
        source_name = str(metadata.get("source") or "").strip().lower()
        haystack = " ".join(
            [
                str(document.id or ""),
                str(document.text or ""),
                source_name,
                str(metadata.get("url") or ""),
            ]
        )
        tokens = cls._tokenize(haystack)
        if primary not in tokens:
            return False
        has_codrug = bool(co_drugs.intersection(tokens))
        has_interaction = bool(interaction_terms.intersection(tokens))
        if has_codrug or has_interaction:
            return True
        if source_name in trusted_label_sources:
            return True
        return False

    @classmethod
    def _filter_ddi_documents(
        cls, *, profile: dict[str, Any], documents: list[Document]
    ) -> list[Document]:
        if not bool(profile.get("is_ddi_query")):
            return documents
        return [doc for doc in documents if cls._is_ddi_evidence_document(profile, doc)]

    def retrieve_pubmed(self, query: str, *, top_k: int, timeout_seconds: float) -> list[Document]:
        if top_k <= 0:
            return []

        profile = analyze_query_profile(query)
        query_for_provider = (
            query if "[Title/Abstract]" in query else self._build_pubmed_query(query, profile)
        )
        search_url = f"{self.PUBMED_ESEARCH_URL}?" + urlencode(
            {
                "db": "pubmed",
                "retmode": "json",
                "retmax": str(top_k),
                "sort": "relevance",
                "term": query_for_provider,
            }
        )
        search_payload = self._fetch_json(search_url, timeout_seconds)
        if not isinstance(search_payload, dict):
            return []

        id_list = search_payload.get("esearchresult", {}).get("idlist", [])
        if not isinstance(id_list, list) or not id_list:
            return []

        summary_url = f"{self.PUBMED_ESUMMARY_URL}?" + urlencode(
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

    def retrieve_europe_pmc(
        self, query: str, *, top_k: int, timeout_seconds: float
    ) -> list[Document]:
        if top_k <= 0:
            return []

        profile = analyze_query_profile(query)
        query_for_provider = (
            query
            if "drug interaction" in query.lower() and "bleeding" in query.lower()
            else self._build_europe_pmc_query(query, profile)
        )
        search_url = f"{self.EUROPEPMC_SEARCH_URL}?" + urlencode(
            {
                "query": query_for_provider,
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
            url = (
                f"https://pubmed.ncbi.nlm.nih.gov/{source_id}/"
                if source == "med"
                else f"https://europepmc.org/article/{source.upper()}/{source_id}"
            )
            docs.append(
                Document(
                    id=f"europepmc-{source}-{source_id}",
                    text=text,
                    metadata={"source": "europepmc", "url": url, "score": 0.0},
                )
            )

        return docs

    def retrieve_openalex(
        self, query: str, *, top_k: int, timeout_seconds: float
    ) -> list[Document]:
        if top_k <= 0:
            return []

        profile = analyze_query_profile(query)
        query_for_provider = self._provider_query(query, profile, provider="openalex")
        search_url = f"{self.OPENALEX_WORKS_URL}?" + urlencode(
            {
                "search": query_for_provider,
                "per-page": str(top_k),
                "sort": "relevance_score:desc",
            }
        )
        payload = self._fetch_json(search_url, timeout_seconds)
        if not isinstance(payload, dict):
            return []

        results = payload.get("results", [])
        if not isinstance(results, list):
            return []

        docs: list[Document] = []
        for item in results:
            if not isinstance(item, dict):
                continue

            openalex_id = first_text(item.get("id"))
            title = first_text(item.get("display_name"), item.get("title"))
            if not openalex_id or not title:
                continue

            year = first_text(item.get("publication_year"))
            host = (
                item.get("primary_location", {})
                if isinstance(item.get("primary_location"), dict)
                else {}
            )
            url = first_text(host.get("landing_page_url"), host.get("pdf_url"), openalex_id)
            text = ". ".join(part for part in [title, year] if part)
            docs.append(
                Document(
                    id=f"openalex-{openalex_id.rsplit('/', 1)[-1]}",
                    text=text,
                    metadata={"source": "openalex", "url": url or openalex_id, "score": 0.0},
                )
            )

        return docs

    def retrieve_crossref(
        self, query: str, *, top_k: int, timeout_seconds: float
    ) -> list[Document]:
        if top_k <= 0:
            return []

        profile = analyze_query_profile(query)
        query_for_provider = self._provider_query(query, profile, provider="crossref")
        search_url = f"{self.CROSSREF_WORKS_URL}?" + urlencode(
            {"query.bibliographic": query_for_provider, "rows": str(top_k), "sort": "relevance"}
        )
        payload = self._fetch_json(search_url, timeout_seconds)
        if not isinstance(payload, dict):
            return []

        items = payload.get("message", {}).get("items", [])
        if not isinstance(items, list):
            return []

        docs: list[Document] = []
        for item in items:
            if not isinstance(item, dict):
                continue

            doi = first_text(item.get("DOI"))
            titles = item.get("title", [])
            title = first_text(titles[0] if isinstance(titles, list) and titles else "")
            if not doi or not title:
                continue

            container = item.get("container-title", [])
            journal = first_text(container[0] if isinstance(container, list) and container else "")
            url = first_text(item.get("URL"), f"https://doi.org/{doi}")
            text = ". ".join(part for part in [title, journal] if part)
            docs.append(
                Document(
                    id=f"crossref-{doi.lower()}",
                    text=text,
                    metadata={"source": "crossref", "url": url, "score": 0.0},
                )
            )

        return docs

    def retrieve_clinicaltrials(
        self, query: str, *, top_k: int, timeout_seconds: float
    ) -> list[Document]:
        if top_k <= 0:
            return []

        profile = analyze_query_profile(query)
        query_for_provider = self._clinical_trials_query(query, profile)
        search_url = f"{self.CLINICALTRIALS_V2_URL}?" + urlencode(
            {"query.term": query_for_provider, "pageSize": str(top_k), "format": "json"}
        )
        payload = self._fetch_json(search_url, timeout_seconds)
        if not isinstance(payload, dict):
            return []

        studies = payload.get("studies", [])
        if not isinstance(studies, list):
            return []

        docs: list[Document] = []
        for item in studies:
            if not isinstance(item, dict):
                continue

            protocol = item.get("protocolSection", {})
            if not isinstance(protocol, dict):
                continue

            identification = protocol.get("identificationModule", {})
            status_module = protocol.get("statusModule", {})
            if not isinstance(identification, dict):
                continue

            nct_id = first_text(identification.get("nctId"))
            title = first_text(identification.get("briefTitle"))
            if not nct_id or not title:
                continue

            status = (
                first_text(status_module.get("overallStatus"))
                if isinstance(status_module, dict)
                else ""
            )
            text = ". ".join(part for part in [title, status] if part)
            docs.append(
                Document(
                    id=f"clinicaltrials-{nct_id.lower()}",
                    text=text,
                    metadata={
                        "source": "clinicaltrials",
                        "url": f"https://clinicaltrials.gov/study/{nct_id}",
                        "score": 0.0,
                    },
                )
            )

        return docs

    def retrieve_openfda(self, query: str, *, top_k: int, timeout_seconds: float) -> list[Document]:
        if top_k <= 0:
            return []

        profile = analyze_query_profile(query)
        terms = self._medication_terms(query, profile)
        if not terms:
            return []

        clauses = [f'openfda.generic_name:"{term}"' for term in terms]
        clauses.extend(f'openfda.brand_name:"{term}"' for term in terms)
        search_expr = " OR ".join(clauses[:12])
        search_url = f"{self.OPENFDA_LABEL_URL}?" + urlencode(
            {"search": search_expr, "limit": str(top_k)}
        )
        try:
            payload = self._fetch_json(search_url, timeout_seconds)
        except HTTPError as exc:
            if exc.code in {400, 404}:
                return []
            raise
        if not isinstance(payload, dict):
            return []

        results = payload.get("results", [])
        if not isinstance(results, list):
            return []

        docs: list[Document] = []
        for idx, item in enumerate(results, start=1):
            if not isinstance(item, dict):
                continue

            openfda = item.get("openfda", {}) if isinstance(item.get("openfda"), dict) else {}
            generic_names = openfda.get("generic_name", [])
            brand_names = openfda.get("brand_name", [])
            generic = first_text(
                generic_names[0] if isinstance(generic_names, list) and generic_names else ""
            )
            brand = first_text(
                brand_names[0] if isinstance(brand_names, list) and brand_names else ""
            )
            if not generic and not brand:
                continue

            usage = item.get("indications_and_usage", [])
            purpose = item.get("purpose", [])
            usage_text = first_text(
                usage[0] if isinstance(usage, list) and usage else "",
                purpose[0] if isinstance(purpose, list) and purpose else "",
            )
            label = first_text(generic, brand, f"openfda-{idx}")
            text = ". ".join(part for part in [label, usage_text] if part)
            docs.append(
                Document(
                    id=f"openfda-{idx}-{label.lower().replace(' ', '-')}",
                    text=text,
                    metadata={
                        "source": "openfda",
                        "url": "https://open.fda.gov/apis/drug/label/",
                        "score": 0.0,
                    },
                )
            )

        return docs

    def retrieve_dailymed(
        self, query: str, *, top_k: int, timeout_seconds: float
    ) -> list[Document]:
        if top_k <= 0:
            return []

        profile = analyze_query_profile(query)
        term_candidates = self._medication_terms(query, profile)
        if not term_candidates:
            return []

        docs: list[Document] = []
        seen_ids: set[str] = set()
        for term in term_candidates[: max(top_k * 2, 4)]:
            search_url = f"{self.DAILYMED_DRUGNAME_URL}/{quote(term)}/spls.json"
            try:
                payload = self._fetch_json(search_url, timeout_seconds)
            except HTTPError as exc:
                if exc.code in {400, 404}:
                    continue
                raise
            if not isinstance(payload, dict):
                continue

            rows = payload.get("data")
            if not isinstance(rows, list):
                rows = payload.get("DATA", [])
            if not isinstance(rows, list):
                continue

            for item in rows:
                if not isinstance(item, list):
                    continue

                set_id = first_text(item[0] if len(item) > 0 else "")
                title = first_text(item[1] if len(item) > 1 else "")
                version = first_text(item[2] if len(item) > 2 else "")
                published = first_text(item[3] if len(item) > 3 else "")
                if not set_id and not title:
                    continue
                canonical_id = set_id or title.lower()
                if canonical_id in seen_ids:
                    continue
                seen_ids.add(canonical_id)

                label = first_text(title, f"DailyMed-{len(docs) + 1}")
                text = ". ".join(part for part in [label, version, published] if part)
                docs.append(
                    Document(
                        id=f"dailymed-{set_id or len(docs) + 1}",
                        text=text,
                        metadata={
                            "source": "dailymed",
                            "url": (
                                f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={set_id}"
                                if set_id
                                else "https://dailymed.nlm.nih.gov/"
                            ),
                            "score": 0.0,
                        },
                    )
                )
                if len(docs) >= top_k:
                    return docs

        return docs

    def retrieve_rxnorm(self, query: str, *, top_k: int, timeout_seconds: float) -> list[Document]:
        if top_k <= 0:
            return []

        profile = analyze_query_profile(query)
        term_candidates = self._medication_terms(query, profile)
        if not term_candidates:
            return []

        docs: list[Document] = []
        seen_ids: set[str] = set()
        max_entries = max(3, min(top_k, 10))
        for term in term_candidates[: max(top_k * 2, 4)]:
            payload = self._fetch_json(
                f"{self.RXNAV_APPROXIMATE_TERM_URL}?{urlencode({'term': term, 'maxEntries': str(max_entries)})}",
                timeout_seconds,
            )
            if not isinstance(payload, dict):
                continue

            group = payload.get("approximateGroup")
            group_obj = group if isinstance(group, dict) else {}
            candidates = group_obj.get("candidate")
            rows = candidates if isinstance(candidates, list) else []
            for index, item in enumerate(rows, start=1):
                if not isinstance(item, dict):
                    continue
                rxcui = first_text(item.get("rxcui"))
                name = first_text(item.get("name"))
                score = first_text(item.get("score"))
                rank = first_text(item.get("rank"))
                if not rxcui and not name:
                    continue
                canonical_id = (rxcui or name).strip().lower()
                if canonical_id in seen_ids:
                    continue
                seen_ids.add(canonical_id)

                title = first_text(name, f"RxNorm candidate {index}")
                text = ". ".join(
                    part
                    for part in [
                        title,
                        f"RxCUI {rxcui}" if rxcui else "",
                        f"score {score}" if score else "",
                        f"rank {rank}" if rank else "",
                    ]
                    if part
                )
                docs.append(
                    Document(
                        id=f"rxnorm-{rxcui or len(docs) + 1}",
                        text=text,
                        metadata={
                            "source": "rxnorm",
                            "url": (
                                f"https://mor.nlm.nih.gov/RxNav/search?searchBy=RXCUI&searchTerm={rxcui}"
                                if rxcui
                                else "https://lhncbc.nlm.nih.gov/RxNav/APIs/index.html"
                            ),
                            "score": 0.0,
                        },
                    )
                )
                if len(docs) >= top_k:
                    return docs

        return docs

    def retrieve_semantic_scholar(
        self,
        query: str,
        *,
        top_k: int,
        timeout_seconds: float,
    ) -> list[Document]:
        if top_k <= 0:
            return []

        profile = analyze_query_profile(query)
        query_for_provider = self._provider_query(query, profile, provider="semantic_scholar")
        search_url = f"{self.SEMANTIC_SCHOLAR_SEARCH_URL}?" + urlencode(
            {
                "query": query_for_provider,
                "limit": str(top_k),
                "fields": "title,year,url,externalIds,journal,venue",
            }
        )
        headers: dict[str, str] | None = None
        if settings.semantic_scholar_api_key:
            headers = {"x-api-key": settings.semantic_scholar_api_key}
        payload = self._fetch_json(search_url, timeout_seconds, headers=headers)
        if not isinstance(payload, dict):
            return []

        data = payload.get("data", [])
        if not isinstance(data, list):
            return []

        docs: list[Document] = []
        for idx, item in enumerate(data, start=1):
            if not isinstance(item, dict):
                continue
            paper_id = first_text(item.get("paperId"), str(idx))
            title = first_text(item.get("title"))
            if not title:
                continue

            year = first_text(item.get("year"))
            url = first_text(item.get("url"))
            venue = first_text(item.get("venue"))
            journal = item.get("journal") if isinstance(item.get("journal"), dict) else {}
            journal_name = first_text(journal.get("name")) if isinstance(journal, dict) else ""
            text = ". ".join(part for part in [title, venue, journal_name, year] if part)
            docs.append(
                Document(
                    id=f"semantic-scholar-{paper_id}",
                    text=text,
                    metadata={
                        "source": "semantic_scholar",
                        "url": url or f"https://www.semanticscholar.org/paper/{paper_id}",
                        "score": 0.0,
                    },
                )
            )

        return docs

    def _build_searxng_search_urls(self, query: str) -> list[str]:
        base_url = settings.searxng_base_url.strip().rstrip("/")
        if not base_url:
            return []
        query_params = {
            "q": query,
            "format": "json",
            "language": "all" if re.search(r"[À-ỹ]", query) and re.search(r"[A-Za-z]", query) else "vi" if re.search(r"[À-ỹ]", query) else "en",
            "categories": "science,general",
            "safesearch": 1,
        }
        encoded = urlencode(query_params)
        return [f"{base_url}/search?{encoded}", f"{base_url}/?{encoded}"]

    def retrieve_searxng(
        self,
        query: str,
        *,
        top_k: int,
        timeout_seconds: float,
    ) -> list[Document]:
        telemetry: dict[str, Any] = {}
        return self.retrieve_searxng_with_telemetry(
            query,
            top_k=top_k,
            timeout_seconds=timeout_seconds,
            telemetry=telemetry,
            crawl_enabled=settings.searxng_crawl_enabled,
            crawl_top_k=settings.searxng_crawl_top_k,
            crawl_timeout_seconds=settings.searxng_crawl_timeout_seconds,
        )

    def retrieve_searxng_with_telemetry(
        self,
        query: str,
        *,
        top_k: int,
        timeout_seconds: float,
        telemetry: dict[str, Any] | None,
        crawl_enabled: bool,
        crawl_top_k: int,
        crawl_timeout_seconds: float,
    ) -> list[Document]:
        started = perf_counter()
        docs: list[Document] = []
        source_attempts: list[dict[str, Any]] = []
        crawl_events: list[dict[str, Any]] = []
        crawled_domains: set[str] = set()

        if top_k <= 0:
            if telemetry is not None:
                telemetry.clear()
                telemetry.update(
                    {
                        "query": query,
                        "status": "skipped",
                        "reason": "invalid_top_k",
                        "source_attempts": [],
                        "crawl_summary": {
                            "enabled": bool(crawl_enabled),
                            "attempted": 0,
                            "success": 0,
                            "domains": [],
                            "events": [],
                        },
                    }
                )
            return []

        search_urls = self._build_searxng_search_urls(query)
        if not search_urls:
            if telemetry is not None:
                telemetry.clear()
                telemetry.update(
                    {
                        "query": query,
                        "status": "skipped",
                        "reason": "searxng_base_url_missing",
                        "source_attempts": [],
                        "crawl_summary": {
                            "enabled": bool(crawl_enabled),
                            "attempted": 0,
                            "success": 0,
                            "domains": [],
                            "events": [],
                        },
                    }
                )
            return []

        payload: dict[str, Any] | None = None
        selected_search_url = ""
        for search_url in search_urls:
            payload_candidate = self._fetch_json(
                search_url,
                timeout_seconds,
                headers={"Accept": "application/json"},
            )
            if isinstance(payload_candidate, dict) and isinstance(
                payload_candidate.get("results"), list
            ):
                payload = payload_candidate
                selected_search_url = search_url
                break

        if not isinstance(payload, dict):
            source_attempts.append(
                {
                    "source": "searxng-search",
                    "status": "error",
                    "documents": 0,
                    "error": "invalid_searxng_payload",
                    "duration_ms": round((perf_counter() - started) * 1000.0, 3),
                    "query": query,
                }
            )
            if telemetry is not None:
                telemetry.clear()
                telemetry.update(
                    {
                        "query": query,
                        "status": "error",
                        "search_url": selected_search_url,
                        "source_attempts": source_attempts,
                        "crawl_summary": {
                            "enabled": bool(crawl_enabled),
                            "attempted": 0,
                            "success": 0,
                            "domains": [],
                            "events": [],
                        },
                        "duration_ms": round((perf_counter() - started) * 1000.0, 3),
                    }
                )
            return []

        results = payload.get("results", [])
        if not isinstance(results, list):
            results = []

        ranked_urls: list[str] = []
        for idx, item in enumerate(results[:top_k], start=1):
            if not isinstance(item, dict):
                continue

            title = first_text(item.get("title"))
            url = first_text(item.get("url"))
            if not title or not url:
                continue

            content = first_text(item.get("content"))
            engine = first_text(item.get("engine"), "searxng")
            text = ". ".join(part for part in [title, content] if part)
            docs.append(
                Document(
                    id=f"searxng-{idx}-{engine}",
                    text=text,
                    metadata={"source": "searxng", "url": url, "score": 0.0},
                )
            )
            ranked_urls.append(url)

        source_attempts.append(
            {
                "source": "searxng-search",
                "status": "completed",
                "documents": len(docs),
                "error": None,
                "duration_ms": round((perf_counter() - started) * 1000.0, 3),
                "query": query,
                "search_url": selected_search_url,
            }
        )

        crawl_enabled_effective = bool(crawl_enabled and crawl_top_k > 0)
        crawl_attempted = 0
        crawl_success = 0
        allowed_domains = self._allowed_domains()
        crawl_started = perf_counter()

        if crawl_enabled_effective:
            for idx, url in enumerate(ranked_urls[: max(0, int(crawl_top_k))], start=1):
                host = self._safe_host(url)
                event_base = {
                    "url": url,
                    "host": host,
                    "index": idx,
                }
                if not self._domain_is_allowed(url, allowed_domains):
                    crawl_events.append({**event_base, "status": "blocked_domain"})
                    continue

                crawl_attempted += 1
                try:
                    html_text = self._fetch_text(
                        url,
                        timeout_seconds=crawl_timeout_seconds,
                        headers={"Accept": "text/html,application/xhtml+xml"},
                    )
                    page_title, page_snippet = self._sanitize_html_snippet(
                        html_text,
                        max_chars=1000,
                    )
                    if not page_title and not page_snippet:
                        crawl_events.append({**event_base, "status": "empty"})
                        continue

                    crawled_domains.add(host)
                    crawl_success += 1
                    crawl_events.append({**event_base, "status": "completed"})
                    docs.append(
                        Document(
                            id=f"searxng-crawl-{idx}-{host or 'unknown'}",
                            text=". ".join(part for part in [page_title, page_snippet] if part),
                            metadata={
                                "source": "searxng-crawl",
                                "url": url,
                                "score": 0.0,
                                "crawl": True,
                                "host": host,
                            },
                        )
                    )
                except Exception as exc:  # pragma: no cover - network variability
                    crawl_events.append(
                        {
                            **event_base,
                            "status": "error",
                            "error": exc.__class__.__name__,
                        }
                    )

        crawl_duration_ms = round((perf_counter() - crawl_started) * 1000.0, 3)
        source_attempts.append(
            {
                "source": "searxng-crawl",
                "status": "completed" if crawl_enabled_effective else "skipped",
                "documents": crawl_success,
                "error": None,
                "duration_ms": crawl_duration_ms,
                "query": query,
            }
        )

        if telemetry is not None:
            telemetry.clear()
            telemetry.update(
                {
                    "query": query,
                    "status": "completed",
                    "search_url": selected_search_url,
                    "results_count": len(results),
                    "documents": len(docs),
                    "source_attempts": source_attempts,
                    "crawl_summary": {
                        "enabled": crawl_enabled_effective,
                        "attempted": crawl_attempted,
                        "success": crawl_success,
                        "domains": sorted(crawled_domains),
                        "events": crawl_events,
                        "duration_ms": crawl_duration_ms,
                    },
                    "duration_ms": round((perf_counter() - started) * 1000.0, 3),
                }
            )

        return docs

    def retrieve_scientific(
        self,
        query: str,
        *,
        top_k: int,
        timeout_seconds: float,
        provider_query_overrides: dict[str, str] | None = None,
    ) -> list[Document]:
        return self.retrieve_scientific_with_telemetry(
            query,
            top_k=top_k,
            timeout_seconds=timeout_seconds,
            telemetry=None,
            provider_query_overrides=provider_query_overrides,
        )

    def retrieve_scientific_with_telemetry(
        self,
        query: str,
        *,
        top_k: int,
        timeout_seconds: float,
        telemetry: dict[str, Any] | None,
        allowed_providers: set[str] | None = None,
        provider_query_overrides: dict[str, str] | None = None,
    ) -> list[Document]:
        if top_k <= 0:
            if telemetry is not None:
                telemetry.clear()
                telemetry.update(
                    {
                        "query": query,
                        "requested_top_k": int(top_k),
                        "provider_events": [],
                        "total_documents": 0,
                        "timeout_seconds": float(timeout_seconds),
                    }
                )
            return []

        docs: list[Document] = []
        provider_events: list[dict[str, Any]] = []
        profile = analyze_query_profile(query)
        normalized_provider_query_overrides = self._normalize_provider_query_overrides(
            provider_query_overrides
        )
        is_ddi_query = bool(profile.get("is_ddi_query"))
        base_order = (
            [
                "openfda",
                "dailymed",
                "rxnorm",
                "pubmed",
                "europepmc",
                "clinicaltrials",
                "semantic_scholar",
            ]
            if is_ddi_query
            else [
                "pubmed",
                "europepmc",
                "semantic_scholar",
                "rxnorm",
                "openalex",
                "crossref",
                "clinicaltrials",
            ]
        )
        normalized_allowed = {item.strip().lower() for item in (allowed_providers or set()) if item}
        if normalized_allowed:
            provider_order = [item for item in base_order if item in normalized_allowed]
        else:
            provider_order = base_order

        provider_queries = {
            "pubmed": self._provider_query(query, profile, provider="pubmed"),
            "europepmc": self._provider_query(query, profile, provider="europepmc"),
            "semantic_scholar": self._provider_query(query, profile, provider="semantic_scholar"),
            "openalex": self._provider_query(query, profile, provider="openalex"),
            "crossref": self._provider_query(query, profile, provider="crossref"),
            "clinicaltrials": self._provider_query(query, profile, provider="clinicaltrials"),
            "openfda": self._provider_query(query, profile, provider="openfda"),
            "dailymed": self._provider_query(query, profile, provider="dailymed"),
            "rxnorm": self._provider_query(query, profile, provider="rxnorm"),
        }
        for provider_name, override_query in normalized_provider_query_overrides.items():
            if provider_name in provider_queries:
                provider_queries[provider_name] = override_query
        provider_map: dict[str, Any] = {
            "pubmed": lambda: self.retrieve_pubmed(
                provider_queries["pubmed"],
                top_k=top_k,
                timeout_seconds=timeout_seconds,
            ),
            "europepmc": lambda: self.retrieve_europe_pmc(
                provider_queries["europepmc"],
                top_k=top_k,
                timeout_seconds=timeout_seconds,
            ),
            "semantic_scholar": lambda: self.retrieve_semantic_scholar(
                provider_queries["semantic_scholar"],
                top_k=min(top_k, settings.semantic_scholar_max_results),
                timeout_seconds=settings.semantic_scholar_timeout_seconds,
            ),
            "openalex": lambda: self.retrieve_openalex(
                provider_queries["openalex"],
                top_k=top_k,
                timeout_seconds=timeout_seconds,
            ),
            "crossref": lambda: self.retrieve_crossref(
                provider_queries["crossref"],
                top_k=top_k,
                timeout_seconds=timeout_seconds,
            ),
            "clinicaltrials": lambda: self.retrieve_clinicaltrials(
                provider_queries["clinicaltrials"],
                top_k=top_k,
                timeout_seconds=max(timeout_seconds, 3.5),
            ),
            "openfda": lambda: self.retrieve_openfda(
                provider_queries["openfda"],
                top_k=top_k,
                timeout_seconds=max(timeout_seconds, 3.0),
            ),
            "dailymed": lambda: self.retrieve_dailymed(
                provider_queries["dailymed"],
                top_k=top_k,
                timeout_seconds=max(timeout_seconds, 3.0),
            ),
            "rxnorm": lambda: self.retrieve_rxnorm(
                provider_queries["rxnorm"],
                top_k=top_k,
                timeout_seconds=max(timeout_seconds, 3.0),
            ),
        }
        tasks: list[tuple[str, Any]] = [
            (provider_name, provider_map[provider_name]) for provider_name in provider_order
        ]
        if not tasks:
            if telemetry is not None:
                telemetry.clear()
                telemetry.update(
                    {
                        "query": query,
                        "requested_top_k": int(top_k),
                        "provider_events": [],
                        "provider_count": 0,
                        "provider_query_overrides": normalized_provider_query_overrides,
                        "documents_by_source": {},
                        "total_documents": 0,
                        "timeout_seconds": float(timeout_seconds),
                        "skipped_reason": "all_connectors_disabled_by_policy",
                    }
                )
            return []

        def _run_provider(
            provider_name: str, provider_task: Any
        ) -> tuple[str, list[Document], str | None, float]:
            started = perf_counter()
            try:
                result = provider_task()
                if not isinstance(result, list):
                    return (
                        provider_name,
                        [],
                        "invalid_result_type",
                        (perf_counter() - started) * 1000.0,
                    )
                filtered = self._filter_ddi_documents(profile=profile, documents=result)
                return provider_name, filtered, None, (perf_counter() - started) * 1000.0
            except Exception as exc:
                return (
                    provider_name,
                    [],
                    exc.__class__.__name__,
                    (perf_counter() - started) * 1000.0,
                )

        max_workers = max(1, min(len(tasks), int(settings.rag_external_parallel_workers)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_run_provider, provider_name, provider_task): provider_name
                for provider_name, provider_task in tasks
            }
            try:
                for future in as_completed(futures, timeout=max(timeout_seconds * 3.0, 2.0)):
                    provider_name = futures[future]
                    try:
                        name, result, error_name, duration_ms = future.result(
                            timeout=max(timeout_seconds, 0.5)
                        )
                    except Exception as exc:  # pragma: no cover - defensive
                        provider_events.append(
                            {
                                "provider": provider_name,
                                "source": provider_name,
                                "status": "error",
                                "error": exc.__class__.__name__,
                                "duration_ms": 0.0,
                                "documents": 0,
                                "query": provider_queries.get(provider_name, query),
                            }
                        )
                        continue

                    docs.extend(result)
                    provider_events.append(
                        {
                            "provider": name,
                            "source": name,
                            "status": "error" if error_name else "completed",
                            "error": error_name,
                            "duration_ms": round(float(duration_ms), 3),
                            "documents": len(result),
                            "query": provider_queries.get(name, query),
                        }
                    )
            except FuturesTimeoutError:
                for future, provider_name in futures.items():
                    if future.done():
                        continue
                    provider_events.append(
                        {
                            "provider": provider_name,
                            "source": provider_name,
                            "status": "timeout",
                            "error": "TimeoutError",
                            "duration_ms": round(max(timeout_seconds * 1000.0, 1.0), 3),
                            "documents": 0,
                            "query": provider_queries.get(provider_name, query),
                        }
                    )

        if telemetry is not None:
            by_source: dict[str, int] = {}
            for doc in docs:
                source_name = str((doc.metadata or {}).get("source") or "unknown")
                by_source[source_name] = by_source.get(source_name, 0) + 1
            telemetry.clear()
            telemetry.update(
                {
                    "query": query,
                    "requested_top_k": int(top_k),
                    "provider_events": provider_events,
                    "provider_count": len(provider_events),
                    "provider_query_overrides": normalized_provider_query_overrides,
                    "documents_by_source": by_source,
                    "total_documents": len(docs),
                    "timeout_seconds": float(timeout_seconds),
                }
            )

        return docs

    @staticmethod
    def _build_pubmed_query(query: str, profile: dict[str, Any]) -> str:
        if not profile.get("is_ddi_query"):
            return query

        primary = str(profile.get("primary_drug") or "").strip()
        co_drugs = [
            str(item).strip()
            for item in profile.get("co_drugs", [])
            if str(item).strip()
        ][:8]
        if not primary:
            return query
        if not co_drugs:
            co_drugs = ["ibuprofen", "naproxen", "diclofenac", "aspirin", "paracetamol", "nsaid"]

        co_clause = " OR ".join(f"{item}[Title/Abstract]" for item in co_drugs)
        return (
            f"({primary}[Title/Abstract]) AND ({co_clause}) AND "
            "(drug interaction[Title/Abstract] OR bleeding[Title/Abstract] "
            "OR INR[Title/Abstract] OR adverse event[Title/Abstract])"
        )

    @staticmethod
    def _build_europe_pmc_query(query: str, profile: dict[str, Any]) -> str:
        if not profile.get("is_ddi_query"):
            return query
        primary = str(profile.get("primary_drug") or "").strip()
        co_drugs = [
            str(item).strip()
            for item in profile.get("co_drugs", [])
            if str(item).strip()
        ][:6]
        if not primary:
            return query
        if not co_drugs:
            co_drugs = ["ibuprofen", "naproxen", "diclofenac", "aspirin", "paracetamol", "nsaid"]
        co_clause = " OR ".join(co_drugs)
        return (
            f"({primary}) AND ({co_clause}) AND "
            "(drug interaction OR bleeding OR INR OR adverse event)"
        )
