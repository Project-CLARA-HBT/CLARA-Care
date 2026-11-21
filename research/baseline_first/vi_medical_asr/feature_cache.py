"""One GPU pass. Persist only numeric candidate features and audit counts."""
from collections import Counter
from math import log
from pathlib import Path

from audit import read_split
from nbest import run


def extractor(train):
    pairs = Counter()
    contexts = Counter()
    vocab = set()
    for row in train:
        seq = ["<s>", *row["normalized"], "</s>"]
        vocab.update(seq[1:])
        for left, right in zip(seq, seq[1:]):
            pairs[left, right] += 1
            contexts[left] += 1

    def features(hypotheses, scores):
        result = []
        for words, score in zip(hypotheses, scores, strict=True):
            seq = ["<s>", *words, "</s>"]
            lm = sum(log((pairs[a, b] + 0.1) / (contexts[a] + 0.1 * (len(vocab) + 1)))
                     for a, b in zip(seq, seq[1:])) / (len(words) + 1)
            result.append([score, lm])
        return result

    return features


if __name__ == "__main__":
    data = Path("data")
    run(data, Path("ct2-large"), Path("features.json"), extractor(read_split(data, "train")))
