"""Replay registered pooling rules on development images with a frozen checkpoint."""

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torchvision import models, transforms

GRID = [0, 0.25, 0.5, 0.75, 1]


def verify(path, digest):
    with path.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
            raise ValueError(f"Unexpected digest for {path}")


def metric(y, pred, k):
    count = np.bincount(y, minlength=k) + np.bincount(pred, minlength=k)
    tp = np.bincount(y[y == pred], minlength=k)
    return dict(f1=float((2 * tp / count.clip(1)).mean()), accuracy=float((y == pred).mean()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["pixels", "weights", "metadata"]:
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    verify(args.weights, "ced39ca3638ad30829dc63a644a750f7b9f613264c99948dc12c101357c7d346")
    verify(args.metadata, "1886a57eddee108aeaabc9d4b79562374baee1b79d37dd782aa1a26a6d4706b6")
    weights = torch.load(args.weights, map_location="cpu", weights_only=True)
    k = len(weights["fc.bias"])
    counts = np.ones(k)
    val = {}
    with args.metadata.open() as f:
        for r in csv.DictReader(f):
            if r["split"] == "train":
                counts[int(r["y"])] += 1
            elif r["split"] == "val":
                val[r["filename"]] = (
                    int(r["location_remapped"]),
                    r["sequence_remapped"],
                    int(r["y"]),
                )
    prior = np.log(counts / counts.sum())
    rarity = (prior.max() - prior) / np.ptp(prior)
    groups = defaultdict(list)
    for r in json.loads((args.pixels / "manifest.json").read_text())["frames"]:
        cam, burst, label = val[r["file"]]
        assert (cam, burst, label) == (int(r["camera"]), r["burst"], r["y"])
        groups[cam, burst].append(r)
    torch.set_num_threads(2)
    model = models.resnet50(num_classes=k)
    model.load_state_dict(weights)
    model.eval()
    transform = transforms.Compose(
        [
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ]
    )
    cams, labels, scores = [], [], defaultdict(list)
    with torch.inference_mode():
        for (cam, _), rows in sorted(groups.items()):
            if len(rows) < 2:
                continue
            batch = []
            for row in rows:
                path = args.pixels / row["file"]
                verify(path, row["sha256"])
                with Image.open(path) as image:
                    batch.append(transform(image.convert("RGB")))
            logp = model(torch.stack(batch)).double().log_softmax(1).numpy()
            p = np.exp(logp)
            mean = p.mean(0)
            for name, score in dict(
                frame=logp,
                mean=np.log(mean),
                logmean=logp.mean(0),
                rare=np.log((1 - rarity) * mean + rarity * p.max(0)),
            ).items():
                scores[name].extend(np.broadcast_to(score, p.shape))
            cams.extend([cam] * len(rows))
            labels.extend(r["y"] for r in rows)
    cams, labels = np.array(cams), np.array(labels)
    tuning = sorted(set(cams.tolist()))[::2]
    tune = np.isin(cams, tuning)
    results = {}
    for name, score in scores.items():
        grid = []
        predictions = []
        for tau in GRID:
            pred = (np.asarray(score) - tau * prior).argmax(1)
            predictions.append(pred)
            grid.append(
                dict(
                    tau=tau,
                    tune=metric(labels[tune], pred[tune], k),
                    held=metric(labels[~tune], pred[~tune], k),
                )
            )
        idx = max(range(len(grid)), key=lambda j: grid[j]["tune"]["f1"])
        by_camera = {}
        for c in np.unique(cams[~tune]):
            sel = cams == c
            by_camera[int(c)] = dict(
                n=int(sel.sum()),
                raw=metric(labels[sel], predictions[0][sel], k),
                chosen=metric(labels[sel], predictions[idx][sel], k),
            )
        results[name] = dict(chosen_tau=GRID[idx], grid=grid, by_camera=by_camera)
    print(
        json.dumps(
            dict(
                classes=k,
                train_frames=int(counts.sum() - k),
                tune_cameras=tuning,
                tune_frames=int(tune.sum()),
                held_frames=int((~tune).sum()),
                results=results,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
