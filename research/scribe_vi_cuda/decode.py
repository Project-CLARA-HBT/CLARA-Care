"""Decode only FLEURS vi_vn development. Persist numeric evidence, never text."""

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from pathlib import Path

from faster_whisper import WhisperModel


def tokens(text):
    text = unicodedata.normalize("NFC", text.casefold())
    return re.findall(r"[^\W_]+", text)


def edits(left, right):
    row = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        previous = row
        row = [i]
        for j, b in enumerate(right, 1):
            row.append(min(row[-1] + 1, previous[j] + 1, previous[j - 1] + (a != b)))
    return row[-1]


def setup(model_dir):
    global model
    model = WhisperModel(str(model_dir), device="cuda", compute_type="float16", num_workers=1, cpu_threads=2)


def decode(item):
    path, fields = item
    prompt, filename, _, reference, _, samples, _ = fields
    ref = tokens(reference)
    record = dict(
        key=hashlib.sha256(filename.encode()).hexdigest()[:16],
        prompt=int(prompt),
        samples=int(samples),
        ref=len(ref),
    )
    hypotheses = {}
    for name, beam in (("greedy", 1), ("beam", 5)):
        try:
            segments, _ = model.transcribe(
                str(path / "dev" / filename),
                language="vi",
                temperature=0.0,
                beam_size=beam,
                condition_on_previous_text=False,
                vad_filter=False,
            )
            segments = list(segments)
            hyp = tokens(" ".join(seg.text for seg in segments))
            hypotheses[name] = hyp
            record[name + "_errors"] = edits(ref, hyp)
            record[name + "_length"] = len(hyp)
            if name == "beam":
                weights = [len(seg.tokens) for seg in segments]
                record["confidence"] = (
                    sum(seg.avg_logprob * w for seg, w in zip(segments, weights)) / sum(weights)
                    if sum(weights)
                    else None
                )
        except Exception as exc:
            record[name + "_failure"] = type(exc).__name__
            record[name + "_errors"] = len(ref)
            record[name + "_length"] = 0
    if len(hypotheses) == 2:
        left, right = hypotheses.values()
        record["disagreement"] = edits(left, right) / max(1, len(left), len(right))
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cache", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--model-dir", type=Path)
    args = parser.parse_args()
    with (args.cache / "dev.tsv").open(encoding="utf8") as f:
        rows = list(csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE))
    seen = set()
    if args.output.exists():
        records = [json.loads(line) for line in args.output.read_text().splitlines()]
        seen = {r["key"] for r in records}
        if len(seen) != len(records):
            raise ValueError("duplicate prior recordings")
    keys = {hashlib.sha256(row[1].encode()).hexdigest()[:16] for row in rows}
    if not seen <= keys:
        raise ValueError("prior recordings do not match source split")
    todo = [r for r in rows if hashlib.sha256(r[1].encode()).hexdigest()[:16] not in seen]
    setup(args.model_dir or args.cache / "model")
    with args.output.open("x") as out:
        for row in rows:
            record = decode((args.cache, row))
            print(json.dumps(record, ensure_ascii=True), file=out, flush=True)



if __name__ == "__main__":
    main()
