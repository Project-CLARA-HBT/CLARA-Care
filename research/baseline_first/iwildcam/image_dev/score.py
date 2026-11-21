"""Compare three fixed rules on exactly the same visible validation burst frames."""

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import torch
from PIL import Image
from torchvision import models, transforms

WEIGHTS = "ced39ca3638ad30829dc63a644a750f7b9f613264c99948dc12c101357c7d346"


def metrics(y, pred):
    labels = sorted(set(y) | set(pred))
    f1 = []
    for label in labels:
        tp = sum(a == b == label for a, b in zip(y, pred, strict=True))
        f1.append(2 * tp / (y.count(label) + pred.count(label)))
    correct = sum(a == b for a, b in zip(y, pred, strict=True))
    return dict(correct=correct, accuracy=correct / len(y), macro_f1=sum(f1) / len(f1))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pixels", type=Path)
    parser.add_argument("weights", type=Path)
    args = parser.parse_args()
    with args.weights.open("rb") as f:
        if hashlib.file_digest(f, "sha256").hexdigest() != WEIGHTS:
            raise ValueError("Unknown checkpoint")
    manifest = json.loads((args.pixels / "manifest.json").read_text())
    groups = defaultdict(list)
    for row in manifest["frames"]:
        groups[(row["camera"], row["burst"])].append(row)
    torch.set_num_threads(2)
    weights = torch.load(args.weights, map_location="cpu", weights_only=True)
    model = models.resnet50(num_classes=weights["fc.weight"].shape[0])
    model.load_state_dict(weights, strict=True)
    model.eval()
    transform = transforms.Compose(
        [
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ]
    )
    records = []
    with torch.inference_mode():
        for (camera, burst), rows in sorted(groups.items()):
            if len(rows) < 2:
                continue
            inputs = []
            for row in rows:
                path = args.pixels / row["file"]
                if hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
                    raise ValueError("Corrupt frame")
                with Image.open(path) as img:
                    inputs.append(transform(img.convert("RGB")))
            p = model(torch.stack(inputs)).softmax(1)
            other = (p.sum(0) - p) / (len(p) - 1)
            disagreement = (p - other).abs().sum(1, keepdim=True) / 2
            alpha = (1 - p.amax(1, keepdim=True)) * (1 - disagreement)
            shrink = (1 - alpha) * p + alpha * other
            for i, row in enumerate(rows):
                records.append(
                    dict(
                        file=row["file"],
                        camera=camera,
                        burst=burst,
                        y=row["y"],
                        individual=int(p[i].argmax()),
                        mean=int(p.mean(0).argmax()),
                        shrink=int(shrink[i].argmax()),
                        sha256=row["sha256"],
                    )
                )
    y = [r["y"] for r in records]
    if not y:
        raise ValueError("No eligible bursts")
    print(
        json.dumps(
            dict(
                prefix_sha256=manifest["prefix_sha256"],
                validated_frames=len(manifest["frames"]),
                scored_frames=len(records),
                cameras=len({r["camera"] for r in records}),
                bursts=len({(r["camera"], r["burst"]) for r in records}),
                metrics={
                    k: metrics(y, [r[k] for r in records]) for k in ["individual", "mean", "shrink"]
                },
                frames=records,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
