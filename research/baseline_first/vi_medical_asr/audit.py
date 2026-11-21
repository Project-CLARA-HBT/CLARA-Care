"""Measure lexical errors on reviewed VietMed dev. Save counts only."""

import argparse
from collections import Counter, defaultdict
from functools import cache
import hashlib
import io
import json
from pathlib import Path
import re
import unicodedata

import pyarrow.parquet as pq


HASHES = {
    "train": "c316eda2f98b65da68cda370ca674c3109291a0977d3a6d7105c9b31fdb52d5f",
    "dev": "ddbce77039a150053a3a6dbe7c92c8f07a7924537a4681a1a1788aa2f917b18b",
}


def tokens(text):
    return re.findall(r"[^\W_]+", unicodedata.normalize("NFC", text.casefold()))


@cache
def fold(token):
    return "".join(ch for ch in unicodedata.normalize("NFD", token) if not unicodedata.combining(ch)).replace("đ", "d")


def align(ref, hyp):
    matrix = [list(range(len(hyp) + 1))]
    for i, word in enumerate(ref, 1):
        row = [i]
        prev = matrix[-1]
        for j, guess in enumerate(hyp, 1):
            row.append(min(prev[j - 1] + (word != guess), prev[j] + 1, row[-1] + 1))
        matrix.append(row)
    return matrix


def counts(ref, hyp, train_freq):
    matrix = align(ref, hyp)
    i, j = len(ref), len(hyp)
    c = Counter(ref_tokens=i, errors=matrix[-1][-1], clips=1)
    c["folded_errors"] = align(list(map(fold, ref)), list(map(fold, hyp)))[-1][-1]
    while i or j:
        if i and j and matrix[i][j] == matrix[i-1][j-1] + (ref[i-1] != hyp[j-1]):
            word, guess = ref[i-1], hyp[j-1]
            if word != guess:
                c["sub"] += 1
                c["sub_fold_equal"] += fold(word) == fold(guess)
                c["sub_rare"] += train_freq[word] < 2
            i -= 1
            j -= 1
        elif i and matrix[i][j] == matrix[i-1][j] + 1:
            c["del"] += 1
            c["del_rare"] += train_freq[ref[i-1]] < 2
            i -= 1
        else:
            c["ins"] += 1
            j -= 1
    assert c["errors"] == c["sub"] + c["del"] + c["ins"]
    return dict(c)


def read_split(directory, split):
    path = directory / (split + ".parquet")
    if hashlib.sha256(path.read_bytes()).hexdigest() != HASHES[split]:
        raise ValueError(f"invalid {split} hash")
    rows = pq.read_table(path).to_pylist()
    for r in rows:
        r["digest"] = hashlib.sha256(r["audio"]["bytes"]).hexdigest()
        r["normalized"] = tuple(tokens(r["text"]))
    return rows


def audit(directory):
    train, dev = (read_split(directory, split) for split in ("train", "dev"))
    cols = ["speaker_name", "audio_name", "utterance_id", "digest", "normalized"]
    splits = {}
    for key in cols:
        left, right = ({r[key] for r in rows} for rows in (train, dev))
        splits[key] = {"train_unique": len(left), "dev_unique": len(right), "shared": len(left & right),
                       "dev_rows_shared": sum(r[key] in left for r in dev)}
    by_speaker = defaultdict(list)
    for r in dev:
        by_speaker[r["speaker_name"]].append(r)
    selected = [r for name in sorted(by_speaker) for r in sorted(by_speaker[name], key=lambda r: r["digest"])[:8]]
    if len({r["digest"] for r in selected}) != len(selected):
        raise ValueError("duplicate audio selected")
    catalog = {"shards": HASHES, "train_rows": len(train), "dev_rows": len(dev), "overlap": splits,
               "selected_rows": len(selected), "selected_speakers": len(by_speaker),
               "selected_recordings": len({r["audio_name"] for r in selected}),
               "selected_ref_tokens": sum(len(r["normalized"]) for r in selected)}
    freq = Counter(token for r in train for token in r["normalized"])
    return catalog, selected, freq


def decode(directory, model_dir, out, model_tag):
    from faster_whisper import WhisperModel

    if out.exists():
        raise FileExistsError(out)
    catalog, selected, freq = audit(directory)
    speaker_indices = {v: i for i, v in enumerate(sorted({r["speaker_name"] for r in selected}))}
    source_indices = {v: i for i, v in enumerate(sorted({r["audio_name"] for r in selected}))}
    model = WhisperModel(str(model_dir), device="cuda", compute_type="float16", num_workers=1, cpu_threads=2)
    rows = []
    for ordinal, r in enumerate(selected):
        try:
            segments, _ = model.transcribe(io.BytesIO(r["audio"]["bytes"]), language="vi", beam_size=5,
                                           temperature=0.0, condition_on_previous_text=False, vad_filter=False)
            hyp = tokens(" ".join(seg.text for seg in segments))
            c = counts(r["normalized"], hyp, freq)
            c["success"] = True
        except Exception as exc:
            c = {"ref_tokens": len(r["normalized"]), "success": False, "failure_class": type(exc).__name__}
        rows.append({"ordinal": ordinal, "speaker": speaker_indices[r["speaker_name"]],
                     "recording": source_indices[r["audio_name"]], **c})
    result = {"model": model_tag, "catalog": catalog, "rows": rows}
    with out.open("x") as stream:
        json.dump(result, stream, separators=(",", ":"))
        stream.write("\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("directory", type=Path)
    p.add_argument("--model-dir", type=Path)
    p.add_argument("--model-tag", choices=["PhoWhisper-base", "PhoWhisper-large"])
    p.add_argument("--out", type=Path)
    args = p.parse_args()
    if args.model_dir is None:
        print(json.dumps(audit(args.directory)[0], indent=2))
    elif args.out and args.model_tag:
        decode(args.directory, args.model_dir, args.out, args.model_tag)
    else:
        p.error("decoding requires --out and --model-tag")


if __name__ == "__main__":
    main()
