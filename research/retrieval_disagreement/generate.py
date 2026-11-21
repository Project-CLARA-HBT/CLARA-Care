"""Generate BM25 and dense scores. Raw text and complete score arrays remain external."""

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import torch
import transformers
from fetch import SETS
from transformers import AutoModel, AutoTokenizer


def tokens(text):
    return re.findall(r"[^\W_]+", text.casefold())


def lexical(corpus, queries):
    docs = [Counter(tokens(t)) for t in corpus]
    dl = np.array([sum(c.values()) for c in docs])
    index = defaultdict(list)
    for i, counts in enumerate(docs):
        for term, tf in counts.items():
            index[term].append((i, tf))
    normal = 1.2 * (0.25 + 0.75 * dl / dl.mean())
    result = np.zeros((len(queries), len(docs)), dtype=np.float64)
    for q, text in enumerate(queries):
        for term, n in Counter(tokens(text)).items():
            postings = index.get(term)
            if not postings:
                continue
            rows, tf = np.array(postings).T
            idf = np.log1p((len(docs) - len(rows) + 0.5) / (len(rows) + 0.5))
            result[q, rows] += n * idf * 2.2 * tf / (tf + normal[rows])
    return result


@torch.inference_mode()
def encode(model, tok, texts):
    vectors = []
    for i in range(0, len(texts), 32):
        batch = tok(
            texts[i : i + 32], truncation=True, max_length=256, padding=True, return_tensors="pt"
        ).to("cuda")
        mask = batch.attention_mask.unsqueeze(-1)
        hidden = model(**batch).last_hidden_state
        vectors.append(torch.nn.functional.normalize((hidden * mask).sum(1) / mask.sum(1), dim=1))
    return torch.cat(vectors)


def main(data, out):
    out.mkdir(exist_ok=False)
    tok = AutoTokenizer.from_pretrained(data / "model", local_files_only=True)
    model = AutoModel.from_pretrained(data / "model", local_files_only=True).eval().to("cuda")
    torch.backends.cuda.matmul.allow_tf32 = False
    for name in SETS:
        corpus = sorted(
            pq.read_table(data / name / "corpus.parquet").to_pylist(), key=lambda r: str(r["_id"])
        )
        queries = sorted(
            pq.read_table(data / name / "queries.parquet").to_pylist(), key=lambda r: str(r["_id"])
        )
        labels = pq.read_table(data / name / "qrels.parquet").to_pylist()
        ct = [(" ".join([r.get("title", ""), r["text"]])).strip() for r in corpus]
        qt = [r["text"] for r in queries]
        dense = (encode(model, tok, qt) @ encode(model, tok, ct).T).cpu().numpy()
        np.savez_compressed(
            out / (name + ".npz"),
            dense=dense,
            sparse=lexical(ct, qt),
            length=[len(tokens(t)) for t in qt],
            docs=[str(r["_id"]) for r in corpus],
            queries=[str(r["_id"]) for r in queries],
            positive=np.array([[str(r["query-id"]), str(r["corpus-id"])] for r in labels]),
        )
    (out / "device.json").write_text(
        json.dumps(
            dict(
                gpu=torch.cuda.get_device_name(),
                torch=str(torch.__version__),
                transformers=transformers.__version__,
                cuda=torch.version.cuda,
                peak_bytes=torch.cuda.max_memory_allocated(),
            ),
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for arg in ("data", "out"):
        p.add_argument(arg, type=Path)
    args = p.parse_args()
    main(args.data, args.out)
