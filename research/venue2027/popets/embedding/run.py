"""Replay the four arms on identical, independently validated embedding dispatches."""

import argparse
import hashlib
import json
import platform
import struct
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from time import perf_counter_ns

import torch
import transformers
from transformers import AutoModel, AutoTokenizer

from evaluation.venue2027.popets.candidate import RevocationCompleteCache
from evaluation.venue2027.popets.sgd_workload import extract, histories

ARMS = ("B1", "B2", "lazy", "B4")
HERE = Path(__file__).resolve().parent
HEADER = struct.Struct("<HHBBH")


def texts(dialogue):
    versions = {}
    for turn in dialogue["turns"]:
        if turn["speaker"] == "USER":
            for frame in turn["frames"]:
                for slot, values in sorted(frame["state"]["slot_values"].items()):
                    key = (frame["service"], slot, tuple(values))
                    versions.setdefault(
                        key, json.dumps(key, separators=(",", ":"), ensure_ascii=False)
                    )
    return list(versions.values())


@torch.inference_mode()
def embed(text, tok, model):
    batch = tok(text, truncation=True, max_length=256, return_tensors="pt").to("cuda")
    hidden = model(**batch).last_hidden_state
    mask = batch.attention_mask.unsqueeze(-1)
    vector = torch.nn.functional.normalize((hidden * mask).sum(1) / mask.sum(1), dim=1)
    return vector.cpu().numpy().astype("<f4").tobytes()


def dispatch(frame, idx, history, material, arm, encode):
    retired = next((s for s in history.sources if s.retired is not None), None)
    graph = RevocationCompleteCache() if arm == "B4" else None
    # Entries carry the flattened source tag and version on lazy validation.
    entries = {}
    epochs = Counter()
    stats = Counter({"build": 0, "hit": 0, "deny": 0})
    start = perf_counter_ns()
    for seq, req in enumerate(history.requests):
        if retired and req.time >= retired.retired:
            epochs[retired.purpose] += 1
            if arm == "B1":
                entries.clear()
            if graph is not None:
                graph.revoke(history.subject, retired.purpose, 0)
            retired = None
        key = f"state/{req.source}"
        cached = entries.get(key)
        if graph is not None:
            hit = graph.get(key, req.purpose, 0).status == "HIT"
        elif arm == "lazy":
            hit = cached is not None and cached[:2] == (req.purpose, epochs[req.purpose])
        else:
            hit = cached is not None
        if hit:
            data = cached[-1]
            op = "hit"
        else:
            source = history.sources[req.source]
            if (
                source.purpose != req.purpose
                or source.visit > req.time
                or (source.retired is not None and req.time >= source.retired)
            ):
                data, op = b"", "deny"
            else:
                data, op = encode(material[req.source]), "build"
                if len(data) != 1536:
                    raise ValueError("unexpected embedding size")
                if graph is not None:
                    parent = f"source/{req.source}"
                    # The graph manages eligibility, while the payload store carries binary values.
                    graph.put(parent, source.value, [(history.subject, req.purpose, 0)])
                    graph.put(
                        key, source.value, [("queue", req.purpose, 0)], derived_from=(parent,)
                    )
                if arm != "B2":
                    entries[key] = (req.purpose, epochs[req.purpose], data)
        frame.write(
            HEADER.pack(idx, seq, ARMS.index(arm), ("deny", "build", "hit").index(op), len(data))
        )
        frame.write(data)
        stats[op] += 1
    return dict(dialogue=idx, arm=arm, **stats, elapsed_ns=perf_counter_ns() - start)


def main(source, model_dir, output):
    schedule = histories(extract(source))
    raw = json.loads(source.read_bytes())
    files = json.loads((HERE / "model.json").read_bytes())
    if not files or any(
        hashlib.sha256((model_dir / k).read_bytes()).hexdigest() != v["sha256"]
        for k, v in files.items()
    ):
        raise ValueError("model files differ from pinned release")
    model = AutoModel.from_pretrained(model_dir, local_files_only=True).eval().to("cuda")
    tok = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
    torch.backends.cuda.matmul.allow_tf32 = False
    embed("warmup", tok, model)
    output.mkdir(exist_ok=False)
    stats = []
    with tempfile.TemporaryDirectory(dir=output) as tmp:
        path = Path(tmp) / "frames.bin"
        with path.open("wb", buffering=0) as frames:
            for idx, (dialogue, history) in enumerate(zip(raw, schedule, strict=True)):
                material = texts(dialogue)
                if len(material) != len(history.sources):
                    raise ValueError("field versions misaligned")
                for arm in ARMS[idx % 4 :] + ARMS[: idx % 4]:
                    stats.append(
                        dispatch(
                            frames, idx, history, material, arm, lambda t: embed(t, tok, model)
                        )
                    )
        receipt = subprocess.check_output(["node", HERE / "verify.mjs", source, path], text=True)
        (output / "verified.json").write_text(receipt)
    (output / "histories.json").write_text(json.dumps(stats, indent=2) + "\n")
    (output / "device.json").write_text(
        json.dumps(
            dict(
                gpu=torch.cuda.get_device_name(),
                cuda=torch.version.cuda,
                torch=str(torch.__version__),
                transformers=transformers.__version__,
                python=platform.python_version(),
                platform=platform.release(),
            ),
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for key in ("source", "model", "output"):
        p.add_argument(key, type=Path)
    args = p.parse_args()
    main(args.source, args.model, args.output)
