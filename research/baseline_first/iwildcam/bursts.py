"""Summarize only official WILDS train and OOD validation rows of metadata.csv."""

import argparse
import csv
import json
from collections import Counter, defaultdict


def mode(counts):
    return min(counts, key=lambda k: (-counts[k], k))


def metrics(pairs):
    actual, predicted, correct = Counter(), Counter(), Counter()
    for (truth, label), count in pairs.items():
        actual[truth] += count
        predicted[label] += count
        if truth == label:
            correct[truth] += count
    labels = sorted(actual)
    return {
        "images": actual.total(),
        "classes": len(labels),
        "accuracy": correct.total() / actual.total(),
        "macro_f1": sum(2 * correct[k] / (actual[k] + predicted[k]) for k in labels) / len(labels),
    }


def summarize(groups):
    mode_pairs, neighbor_pairs = Counter(), Counter()
    multi = mixed = mixed_images = 0
    for counts in groups.values():
        size = counts.total()
        representative = mode(counts)
        multi += int(size > 1)
        mixed += int(len(counts) > 1)
        mixed_images += size if len(counts) > 1 else 0
        for truth, count in counts.items():
            mode_pairs[truth, representative] += count
            if size > 1:
                other = counts.copy()
                other[truth] -= 1
                neighbor_pairs[truth, mode(other)] += count
    return {
        "cameras": len({key[0] for key in groups}),
        "sequences": len(groups),
        "multi_sequences": multi,
        "mixed_sequences": mixed,
        "mixed_images": mixed_images,
        "mode_oracle": metrics(mode_pairs),
        "other_images_only": metrics(neighbor_pairs),
    }


def screen(source):
    splits = {name: defaultdict(Counter) for name in ("train", "val")}
    with open(source, newline="") as stream:
        for row in csv.DictReader(stream):
            if row["split"] in splits:
                key = int(row["location_remapped"]), int(row["sequence_remapped"])
                splits[row["split"]][key][int(row["y"])] += 1
    train, val = [{key[0] for key in groups} for groups in splits.values()]
    assert train.isdisjoint(val)
    return {name: summarize(groups) for name, groups in splits.items()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metadata_csv")
    print(json.dumps(screen(parser.parse_args().metadata_csv), indent=2))
