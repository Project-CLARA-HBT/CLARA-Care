"""Retrieve the registered ACNS seed texts and emit public-source receipts.

Run as a module. Requires pdftotext. Only metadata and hashes are emitted.
A retrieval error stays in the denominator. Screening is a separate procedure.
"""

import hashlib
import json
import re
import subprocess
import unicodedata
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

CORPUS = Path(__file__).resolve().parents[3] / "research/venue2027/acns/corpus/citation_corpus.json"

# Each phrase must occur in the decoded document. In particular, the HTML
# abstract and a PDF from a different paper cannot satisfy the paper check.
SOURCES = {
    "rats9334": [("https://www.rfc-editor.org/rfc/rfc9334.txt", "RATS Architecture")],
    "ct9162": [
        ("https://www.rfc-editor.org/rfc/rfc9162.txt", "Certificate Transparency Version 2.0")
    ],
    "macaroons14": [
        (
            "https://www.ndss-symposium.org/wp-content/uploads/2017/09/04_3_1.pdf",
            "Macaroons: Cookies with Contextual Caveats",
        )
    ],
    "zanzibar19": [
        ("https://www.usenix.org/system/files/atc19-pang.pdf", "Global Authorization System")
    ],
    "agentdojo24": [
        (
            "https://proceedings.nips.cc/paper_files/paper/2024/file/97091a5177d8dc64b1da8bf3e1f6fb54-Paper-Datasets_and_Benchmarks_Track.pdf",
            "AgentDojo: A Dynamic Environment",
        )
    ],
    "toolemu24": [
        (
            "https://proceedings.iclr.cc/paper_files/paper/2024/file/7274ed909a312d4d869cc328ad1c5f04-Paper-Conference.pdf",
            "LM-Emulated Sandbox",
        )
    ],
    "tauben25": [
        (
            "https://proceedings.iclr.cc/paper_files/paper/2025/file/1b126cc38b8638e07bef37e7b2bb72bf-Paper-Conference.pdf",
            "Interaction in Real-World Domains",
        )
    ],
    "fhir5": [
        (f"https://hl7.org/fhir/R5/{name}.html", f"Resource {name}")
        for name in ("consent", "auditevent", "provenance")
    ],
    "prov-dm": [
        ("https://www.w3.org/TR/2013/REC-prov-dm-20130430/", "PROV-DM: The PROV Data Model")
    ],
}


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def fingerprint(url, body, phrase):
    if url.endswith(".pdf"):
        if not body.startswith(b"%PDF-"):
            raise ValueError("invalid_pdf")
        text = subprocess.run(
            ["pdftotext", "-f", "1", "-l", "1", "-", "-"],
            input=body,
            check=True,
            capture_output=True,
            timeout=30,
        ).stdout.decode()
    else:
        text = body.decode("utf-8-sig")
        if not url.endswith(".txt"):
            parser = VisibleText()
            parser.feed(text)
            text = " ".join(parser.parts)

    def normalize(value):
        return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKC", value).lower())

    if normalize(phrase) not in normalize(text):
        raise ValueError("document_identity_mismatch")
    return {"sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}


def fetch(document):
    seed, url, phrase = document
    row = {"seed": seed, "requested_url": url, "identity_phrase": phrase}
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            row.update(resolved_url=response.geturl(), http_status=response.status)
            body = response.read()
        row.update(fingerprint(url, body, phrase), status="retrieved")
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        row.update(status="unverified", error=str(error))
    return row


def retrieve():
    corpus = json.loads(CORPUS.read_bytes())
    if set(SOURCES) != {row["id"] for row in corpus["entries"]} | {"prov-dm"}:
        raise ValueError("registered_seed_set_changed")
    documents = [
        (seed, url, phrase) for seed, sources in SOURCES.items() for url, phrase in sources
    ]
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(fetch, documents))
        for row in rows.copy():
            if row["seed"] == "macaroons14" and row["status"] != "retrieved":
                rows.append(
                    fetch(
                        (
                            "macaroons14",
                            "https://research.google.com/pubs/archive/41892.pdf",
                            row["identity_phrase"],
                        )
                    )
                )
    return {
        "scope": "registered seed acquisition only; prov-dm is a protocol seed absent from the shared registry",
        "retrieved_utc": datetime.now(UTC).isoformat(),
        "seed_register_sha256": hashlib.sha256(CORPUS.read_bytes()).hexdigest(),
        "documents": rows,
        "complete_seeds": sum(
            len(
                {
                    r["identity_phrase"]
                    for r in rows
                    if r["seed"] == seed and r["status"] == "retrieved"
                }
            )
            == len(SOURCES[seed])
            for seed in SOURCES
        ),
        "planned_seeds": len(SOURCES),
        "screening_decisions": 0,
    }


if __name__ == "__main__":
    print(json.dumps(retrieve(), indent=2))
