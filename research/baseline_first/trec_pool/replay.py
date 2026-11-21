"""Score all public round-one runs on two judgments of the same collection."""

import argparse
import csv
import hashlib
import json
import math
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from itertools import combinations
from pathlib import Path
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = "https://ir.nist.gov/trec-covid/"
EARLY = "data/qrels-covid_d1_j0.5-1.txt"
LATE = "data/qrels-covid_d1_j0.5-5.txt"


def fetch(cache, key):
    path = cache / key
    if not path.is_file():
        path.parent.mkdir(exist_ok=True, parents=True)
        with requests.Session() as session:
            session.mount(
                "https://",
                HTTPAdapter(
                    max_retries=Retry(
                        total=4, backoff_factor=1, status_forcelist=(429, 500, 502, 503, 504)
                    )
                ),
            )
            response = session.get(ROOT + key, timeout=60)
            response.raise_for_status()
            path.write_bytes(response.content)
    return path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def judgments(path, topics):
    grades = {}
    for row in path.read_text().splitlines():
        topic, _, doc, grade = row.split()
        key = (topic, doc)
        if topic not in topics or key in grades or grade not in {"0", "1", "2"}:
            raise ValueError(f"Invalid qrel in {path.name}: {row}")
        grades[key] = int(grade)
    return grades


def run_scores(executable, qrels, path):
    output = subprocess.check_output(
        [executable, "-c", "-m", "ndcg_cut.10", "-m", "P.5", qrels, path], text=True
    )
    return {metric: score for metric, _, score in (line.split() for line in output.splitlines())}


def compare(rows, metric):
    counts = Counter()
    for a, b in combinations(rows, 2):
        before = float(a["early_" + metric]) - float(b["early_" + metric])
        after = float(a["late_" + metric]) - float(b["late_" + metric])
        if before == after == 0:
            counts["tie_both"] += 1
        elif before == 0:
            counts["tie_early_only"] += 1
        elif after == 0:
            counts["tie_late_only"] += 1
        elif before * after < 0:
            counts["reversed"] += 1
        else:
            counts["preserved"] += 1
    comparable = counts["preserved"] + counts["reversed"]
    tau = (counts["preserved"] - counts["reversed"]) / math.sqrt(
        (comparable + counts["tie_early_only"]) * (comparable + counts["tie_late_only"])
    )
    return dict(pairs=sum(counts.values()), **counts, kendall_tau_b=tau)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    parser.add_argument("trec_eval", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=True, parents=True)
    keys = ["data/docids-rnd1.txt", "data/topics-rnd1.xml", EARLY, LATE]
    paths = {key: fetch(args.cache, key) for key in keys}
    docs = set(paths[keys[0]].read_text().splitlines())
    topics = {item.attrib["number"] for item in ElementTree.parse(paths[keys[1]]).findall("topic")}
    early, late = [judgments(paths[key], topics) for key in (EARLY, LATE)]
    index = fetch(args.cache, "archive/archive-round1.html")
    links = [
        "archive/" + link["href"]
        for link in BeautifulSoup(index.read_bytes(), "html.parser").select("a[href]")
        if "submission file" in link.get_text(" ", strip=True)
    ]
    if len(set(links)) != len(links) or not all(k.startswith("archive/round1/") for k in links):
        raise ValueError("Archive changed")

    def evaluate(key):
        path = fetch(args.cache, key)
        result = {"file": key, "sha256": digest(path)}
        for prefix, qrels in [("early_", EARLY), ("late_", LATE)]:
            scores = run_scores(args.trec_eval, paths[qrels], path)
            result.update({prefix + metric: score for metric, score in scores.items()})
        return result

    with ThreadPoolExecutor(max_workers=4) as pool:
        runs = list(pool.map(evaluate, sorted(links)))
    with (args.output / "runs.csv").open("w") as f:
        writer = csv.DictWriter(f, fieldnames=list(runs[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(runs)
    summary = dict(
        valid_docids=len(docs),
        topics=len(topics),
        runs=len(runs),
        qrels_early=len(early),
        qrels_late=len(late),
        off_frame_early=Counter(g for (_, d), g in early.items() if d not in docs),
        off_frame_late=Counter(g for (_, d), g in late.items() if d not in docs),
        grades_early=Counter(early.values()),
        grades_late=Counter(late.values()),
        added=len(late.keys() - early),
        removed=len(early.keys() - late),
        changed=sum(early[k] != late[k] for k in early.keys() & late),
        sources={key: digest(path) for key, path in paths.items()},
        comparisons={metric: compare(runs, metric) for metric in ["ndcg_cut_10", "P_5"]},
    )
    (args.output / "summary.json").write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
