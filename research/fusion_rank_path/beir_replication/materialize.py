"""Score full BEIR corpora and measure exact-text overlap with Nano development."""

import argparse
import csv
import hashlib
import itertools
import json
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import torch
import transformers

# Imported from the frozen retrieval and rank experiments using PYTHONPATH.
from generate import encode, lexical
from inputs import quantize
from transformers import AutoModel, AutoTokenizer


def table(root, source, part):
    return pq.read_table(root / source / (part + ".parquet")).to_pylist()


def texts(rows):
    return [(r.get("title", "") + " " + r["text"]).strip() for r in rows]


def fingerprints(strings):
    counts = Counter()
    for text in strings:
        s = " ".join(unicodedata.normalize("NFC", text).casefold().split())
        key = hashlib.sha256(s.encode("utf-8")).hexdigest() if s else ""
        counts[key] += 1
    return counts


def field_prints(corpus, query):
    return {
        "query": fingerprints([q["text"] for q in query]),
        "body": fingerprints([r["text"] for r in corpus]),
        "title_body": fingerprints(texts(corpus)),
    }


def main(args):
    checks = json.loads(args.nano_receipt.read_text())
    nano = args.nano
    for key, meta in checks.items():
        if hashlib.sha256((nano / key).read_bytes()).hexdigest() != meta["sha256"]:
            raise ValueError(f"pinned NanoBEIR input changed: {key}")
    tok = AutoTokenizer.from_pretrained(nano / "model", local_files_only=True)
    model = AutoModel.from_pretrained(nano / "model", local_files_only=True).eval().to("cuda")
    torch.backends.cuda.matmul.allow_tf32 = False
    dev = {
        s: field_prints(table(nano, s, "corpus"), table(nano, s, "queries"))
        for s in ("NanoArguAna", "NanoFiQA2018", "NanoSCIDOCS")
    }
    metrics, overlap = {}, []
    with args.output.open("x") as f:
        for source, expected in [("SciFact", 300), ("NFCorpus", 323)]:
            corpus = sorted(table(args.data, source, "corpus"), key=lambda r: str(r["_id"]))
            all_queries = table(args.data, source, "queries")
            docs = np.array([str(r["_id"]) for r in corpus])
            if len(set(docs)) != len(docs):
                raise ValueError("duplicate document ID")
            grades, labels, qids = Counter(), defaultdict(set), set()
            seen = set()
            with (args.data / source / "test.tsv").open() as handle:
                for row in csv.DictReader(handle, delimiter="\t"):
                    query, doc, grade = row["query-id"], row["corpus-id"], int(row["score"])
                    if (query, doc) in seen:
                        raise ValueError("duplicate test labels")
                    seen.add((query, doc))
                    qids.add(query)
                    grades[grade] += 1
                    if grade > 0:
                        labels[query].add(doc)
            queries = sorted(
                (r for r in all_queries if str(r["_id"]) in qids), key=lambda r: str(r["_id"])
            )
            if len(queries) != expected or {str(r["_id"]) for r in queries} != qids:
                raise ValueError(f"incomplete query cohort for {source}")
            ids = set(docs)
            unknown = sum(d not in ids for q, d in seen)
            if unknown:
                raise ValueError(f"qrels with absent document for {source}: {unknown}")
            source_prints = field_prints(corpus, queries)
            for dname, dprints in dev.items():
                for (ef, ec), (df, dc) in itertools.product(source_prints.items(), dprints.items()):
                    common = (ec.keys() & dc.keys()) - {""}
                    overlap.append(
                        dict(
                            source=source,
                            external_field=ef,
                            nano=dname,
                            nano_field=df,
                            shared_nonempty=len(common),
                            external_records_matched=sum(ec[k] for k in common),
                            development_records_matched=sum(dc[k] for k in common),
                            external_empty=ec[""],
                            development_empty=dc[""],
                        )
                    )
            ct, qt = texts(corpus), [r["text"] for r in queries]
            dense = (encode(model, tok, qt) @ encode(model, tok, ct).T).cpu().numpy()
            sparse = lexical(ct, qt)
            removed, removed_positive, reachable = 0, 0, 0
            for i, query in enumerate(queries):
                q = str(query["_id"])
                keep = docs != q
                removed += int((~keep).sum())
                removed_positive += int(q in labels[q] and q in ids)
                pos = np.isin(docs[keep], list(labels[q]))
                reachable += int(pos.sum())
                x, y = quantize(sparse[i, keep]), quantize(dense[i, keep])
                print(source, q, len(pos), file=f)
                np.savetxt(f, np.column_stack([x, y, pos]), fmt="%i")
            metrics[source] = dict(
                documents=len(corpus),
                queries=len(queries),
                qrels=len(seen),
                all_published_query_texts=len(all_queries),
                grade_counts=dict(sorted(grades.items())),
                self_matches_removed=removed,
                positive_self_matches_removed=removed_positive,
                retained_positive_pairs=reachable,
                qrels_with_missing_document=unknown,
            )
    receipt = dict(
        sources=metrics,
        overlap=overlap,
        pytorch=str(torch.__version__),
        transformers=transformers.__version__,
        gpu=torch.cuda.get_device_name(),
        cuda=torch.version.cuda,
        numpy=np.__version__,
        input_sha256=hashlib.sha256(args.output.read_bytes()).hexdigest(),
    )
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for opt in ("data", "nano", "nano_receipt", "output"):
        p.add_argument(opt, type=Path)
    main(p.parse_args())
