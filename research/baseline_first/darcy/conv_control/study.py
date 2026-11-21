"""CPU subpixel residual comparator for the Darcy development replay."""
import argparse
import csv
from pathlib import Path

import torch
from torch import nn

OUT = Path(__file__).resolve().parent
PARITY = [(0, 1), (1, 0), (1, 1)]


class Model(nn.Module):
    def __init__(self, channels):
        super().__init__()
        self.layers = nn.Sequential(
            nn.Conv2d(channels, 32, 3, padding=1), nn.GELU(),
            nn.Conv2d(32, 32, 3, padding=1), nn.GELU(),
            nn.Conv2d(32, 32, 3, padding=1), nn.GELU(),
            nn.Conv2d(32, 3, 1),
        )

    def forward(self, x):
        return self.layers(x)


def fit(p, a, y, n, material, epochs, validation):
    torch.manual_seed(412)
    x = p[:, None] / p[:n].std()
    if material:
        x = torch.cat((x, a[:, None] * 2 - 1), dim=1)
    residual = torch.stack([y[:, i::2, j::2] - p for i, j in PARITY], dim=1)
    scale = residual[:n].std()
    model = Model(x.shape[1])
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.002)
    history = []
    for epoch in range(1, epochs + 1):
        for group in torch.randperm(n).split(32):
            loss = (model(x[group]) - residual[group] / scale).square().mean()
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        if validation:
            with torch.no_grad():
                truth = y[n:]
                truth = torch.stack([truth[:, i::2, j::2] for i, j in PARITY], dim=1)
                error = model(x[n:]) * scale - residual[n:]
                history.append((epoch, (error.flatten(1).norm(dim=1) /
                                        truth.flatten(1).norm(dim=1)).mean().item()))
    if validation:
        return history
    with torch.no_grad():
        return model(x[n:]) * scale


def main(data, output=OUT, fit_size=512, train_size=448, count=640, epochs=35):
    assert 0 < train_size < fit_size < count
    output.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(2)
    coarse, fine = [torch.load(data / f'darcy_train_{s}.pt', weights_only=True)
                    for s in (16, 32)]
    p, a, y = coarse['y'][:count], coarse['x'][:count].float(), fine['y'][:count]
    assert torch.equal(p, y[:, ::2, ::2])
    assert torch.equal(a, fine['x'][:count, ::2, ::2])
    missing = torch.ones((32, 32), dtype=torch.bool)
    missing[::2, ::2] = False
    edge = torch.zeros_like(missing)
    edge[-1] = edge[:, -1] = True
    with (output / 'convergence.csv').open('w') as h, (output / 'fields.csv').open('w') as f:
        history, fields = (csv.writer(file, lineterminator='\n') for file in (h, f))
        history.writerow(['arm', 'epoch', 'validation_relative_l2'])
        fields.writerow(['training_index', 'arm', 'all', 'interior', 'exterior'])
        for arm, material in [('pressure', False), ('material', True)]:
            curve = fit(p[:fit_size], a[:fit_size], y[:fit_size], train_size, material, epochs, True)
            history.writerows((arm, *row) for row in curve)
            epoch, _ = min(curve, key=lambda row: row[1])
            delta = fit(p, a, y, fit_size, material, epoch, False)
            pred = p[fit_size:].repeat_interleave(2, 1).repeat_interleave(2, 2)
            for k, (i, j) in enumerate(PARITY):
                pred[:, i::2, j::2] += delta[:, k]
            assert torch.equal(pred[:, ::2, ::2], p[fit_size:])
            scores = []
            for mask in [missing, missing & ~edge, edge]:
                truth = y[fit_size:, mask]
                scores.append((pred[:, mask] - truth).norm(dim=1) / truth.norm(dim=1))
            fields.writerows((idx, arm, *row) for idx, row in
                             enumerate(torch.stack(scores, dim=1).tolist(), fit_size))
            print(arm, epoch, [col.mean().item() for col in scores], flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('data', type=Path)
    parser.add_argument('--output', type=Path, default=OUT)
    parser.add_argument('--fit-size', type=int, default=512)
    parser.add_argument('--train-size', type=int, default=448)
    parser.add_argument('--count', type=int, default=640)
    parser.add_argument('--epochs', type=int, default=35)
    args = parser.parse_args()
    main(args.data, args.output, args.fit_size, args.train_size, args.count, args.epochs)
