"""Out-of-fold, matched-coverage estimates for one fixed ASR recognizer."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def fold(prompt):
    return int.from_bytes(hashlib.sha256(str(prompt).encode()).digest()[:8], "big") % 5


def features(row):
    beam = row["beam_length"]
    greedy = row["greedy_length"]
    secs = row["samples"] / 16000
    confidence = row.get("confidence")
    return [
        confidence if confidence is not None else -10.0,
        row.get("disagreement", 1.0),
        beam,
        greedy,
        abs(beam - greedy),
        secs,
        beam / secs,
        greedy / secs,
        int(confidence is None),
        int("beam_failure" in row or "greedy_failure" in row),
    ]


def predict(train, target, test):
    center, scale = train.mean(axis=0), train.std(axis=0)
    scale[scale == 0] = 1
    normalized = (train - center) / scale
    weights = np.linalg.solve(
        normalized.T @ normalized + np.eye(train.shape[1]), normalized.T @ (target - target.mean())
    )
    return target.mean() + ((test - center) / scale) @ weights


def accepted(scores, keys):
    """Lower scores are accepted; ties use ascending file hashes."""
    n = len(keys)
    keep = np.zeros(n, dtype=bool)
    keep[np.lexsort((keys, scores))[: n - n // 5]] = True
    return keep


def fractional(errors, lengths, keys):
    ratio = errors.sum() / lengths.sum()
    for _ in range(len(keys) + 2):
        mask = accepted(errors - ratio * lengths, keys)
        revised = errors[mask].sum() / lengths[mask].sum()
        if abs(revised - ratio) < 1e-12:
            return mask
        ratio = revised
    raise RuntimeError("ratio selection did not converge")


def evaluate(rows):
    keys = np.array([r["key"] for r in rows])
    if len(rows) != 361 or len(set(keys)) != 361:
        raise ValueError("incomplete FLEURS dev")
    x = np.array([features(r) for r in rows])
    refs = np.array([r["ref"] for r in rows])
    err = np.array([r["beam_errors"] for r in rows])
    prompts = np.array([r["prompt"] for r in rows])
    folds = np.array([fold(p) for p in prompts])
    decisions = {}
    for f in range(5):
        tst = folds == f
        tr = ~tst
        k = keys[tst]
        e, n = (np.maximum(lb, predict(x[tr], y[tr], x[tst])) for lb, y in ((0, err), (1, refs)))
        scorers = dict(
            hash_control=k,
            confidence=-x[tst, 0],
            disagreement=x[tst, 1],
            confidence_ridge=predict(x[tr, :1], err[tr] / refs[tr], x[tst, :1]),
            multifeature_wer=predict(x[tr], err[tr] / refs[tr], x[tst]),
            error_count=e,
            predicted_ratio=e / n,
        )
        masks = {name: accepted(s, k) for name, s in scorers.items()}
        masks["fractional"] = fractional(e, n, k)
        for method, m in masks.items():
            decisions.setdefault(method, np.zeros(len(rows), dtype=bool))[tst] = m
    groups, group = np.unique(prompts, return_inverse=True)
    rng = np.random.default_rng(20261121)
    weights = rng.multinomial(len(groups), np.ones(len(groups)) / len(groups), size=2000)
    risks = {}
    result = {}
    for method, m in decisions.items():
        errors = np.bincount(group, weights=m * err)
        lengths = np.bincount(group, weights=m * refs)
        risks[method] = 100 * (weights @ errors) / (weights @ lengths)
        result[method] = dict(
            accepted=int(m.sum()),
            errors=int(err[m].sum()),
            reference_tokens=int(refs[m].sum()),
            accepted_wer_pct=float(100 * err[m].sum() / refs[m].sum()),
            deferred_audio_minutes=float(x[~m, 5].sum() / 60),
            fold_wer_pct=[
                float(100 * err[m & (folds == f)].sum() / refs[m & (folds == f)].sum())
                for f in range(5)
            ],
        )
    for method in result:
        delta = risks["fractional"] - risks[method]
        result[method]["fractional_minus_baseline_pp_interval"] = np.percentile(
            delta, [2.5, 97.5]
        ).tolist()
    return dict(
        prompts=len(groups),
        recordings=len(rows),
        ref_tokens=int(refs.sum()),
        total_beam_errors=int(err.sum()),
        beam_exceptions=sum("beam_failure" in r for r in rows),
        greedy_exceptions=sum("greedy_failure" in r for r in rows),
        methods=result,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("records", type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            evaluate([json.loads(line) for line in args.records.read_text().splitlines()]), indent=2
        )
    )
