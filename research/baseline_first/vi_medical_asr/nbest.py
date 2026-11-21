"""Measure finite-list oracle and equal-weight minimum edit-risk baselines."""

import argparse
import io
import json
from pathlib import Path

from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio, pad_or_trim
from faster_whisper.tokenizer import Tokenizer

from audit import align, audit, tokens


def distance(left, right):
    return align(left, right)[-1][-1]


def score(ref, hypotheses):
    errors = [distance(ref, hyp) for hyp in hypotheses]
    costs = [sum(distance(hyp, other) for other in hypotheses) for hyp in hypotheses]
    return {
        "errors_by_rank": errors,
        "within_list_edit_sums": costs,
        "unique_sequences": len(set(tuple(hyp) for hyp in hypotheses)),
    }


def run(data, model_dir, out):
    if out.exists():
        raise FileExistsError(out)
    catalog, selected, _ = audit(data)
    speakers = sorted({row["speaker_name"] for row in selected})
    recordings = sorted({row["audio_name"] for row in selected})
    model = WhisperModel(str(model_dir), device="cuda", compute_type="float16", cpu_threads=2)
    tokenizer = Tokenizer(model.hf_tokenizer, model.model.is_multilingual,
                          task="transcribe", language="vi")
    prompt = model.get_prompt(tokenizer, [], without_timestamps=True)
    results = []
    for ordinal, row in enumerate(selected):
        result = {
            "ordinal": ordinal,
            "speaker": speakers.index(row["speaker_name"]),
            "recording": recordings.index(row["audio_name"]),
            "ref_tokens": len(row["normalized"]),
        }
        try:
            samples = decode_audio(io.BytesIO(row["audio"]["bytes"]), sampling_rate=16000)
            if len(samples) > 30 * 16000:
                raise ValueError("Input exceeds one Whisper window")
            features = pad_or_trim(model.feature_extractor(samples))
            encoded = model.encode(features)
            generation = model.model.generate(
                encoded, [prompt], beam_size=5, num_hypotheses=5,
                patience=1, length_penalty=1, return_scores=True,
            )[0]
            sequences = generation.sequences_ids
            if len(sequences) != 5:
                raise RuntimeError("Incomplete N-best list")
            result.update(score(row["normalized"], [tokens(tokenizer.decode(s)) for s in sequences]))
        except Exception as exc:
            result["failure_class"] = type(exc).__name__
        results.append(result)
    with out.open("x") as stream:
        json.dump({"model": "PhoWhisper-large", "catalog": catalog, "rows": results}, stream)
        stream.write("\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("data", "model_dir", "out"):
        parser.add_argument(arg, type=Path)
    args = parser.parse_args()
    run(args.data, args.model_dir, args.out)
