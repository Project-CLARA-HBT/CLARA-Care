"""Verify the direct Gaussian smoother against an independent Kalman/RTS recursion."""

import numpy as np
from scipy.linalg import block_diag

from .run import SETTINGS, structural_covariance, trend_covariance


def model(slope, harmonic):
    trend = np.array([[1.0, 1.0], [0.0, 1.0]])
    damp = np.exp(-1 / 36)
    rotations = []
    for period in (24, 12):
        angle = 2 * np.pi / period
        rotations.append(
            damp * np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
        )
    transition = block_diag(trend, *rotations)
    process = np.diag(
        [1.0, slope, *([harmonic * (1 - damp**2)] * 2), *([0.5 * harmonic * (1 - damp**2)] * 2)]
    )
    prior = np.diag([1e4, 1.0, harmonic, harmonic, 0.5 * harmonic, 0.5 * harmonic])
    if not harmonic:
        return trend, process[:2, :2], prior[:2, :2], np.array([1.0, 0.0])
    return transition, process, prior, np.array([1.0, 0.0, 1.0, 0.0, 1.0, 0.0])


def rts(series, settings):
    slope, harmonic, noise = settings
    transition, process, covariance, h = model(slope, harmonic)
    state = np.zeros(len(h))
    prior, posterior = [], []
    for y in series:
        prior.append((state, covariance))
        if np.isfinite(y):
            gain = covariance @ h / (h @ covariance @ h + noise)
            state = state + gain * (y - h @ state)
            complement = np.eye(len(h)) - np.outer(gain, h)
            covariance = complement @ covariance @ complement.T + noise * np.outer(gain, gain)
        posterior.append((state, covariance))
        state = transition @ state
        covariance = transition @ covariance @ transition.T + process
    smooth = posterior[-1][0]
    predictions = [h @ smooth]
    for i in reversed(range(len(series) - 1)):
        state, covariance = posterior[i]
        next_state, next_cov = prior[i + 1]
        gain = np.linalg.solve(next_cov.T, transition @ covariance.T).T
        smooth = state + gain @ (smooth - next_state)
        predictions.append(h @ smooth)
    return np.array(predictions[::-1])


def main():
    highest = 0.0
    for length in (6, 24, 72):
        size = length + 48
        gap = np.arange(24, 24 + length)
        flank = np.r_[0:24, 24 + length : size]
        y = np.random.default_rng(length).normal(size=size)
        y[gap] = np.nan
        for settings in SETTINGS["structural"]:
            slope = settings[0]
            transition, process, cov, _ = model(slope, 0.0)
            expected = np.empty((size, size))
            for i in range(size):
                cross = cov
                for j in range(i, size):
                    expected[j, i] = expected[i, j] = cross[0, 0]
                    cross = transition @ cross
                cov = transition @ cov @ transition.T + process
            np.testing.assert_allclose(
                trend_covariance(size, slope), expected, rtol=1e-12, atol=1e-8
            )
            full = structural_covariance(size, settings)
            conditional = full[np.ix_(gap, flank)] @ np.linalg.solve(
                full[np.ix_(flank, flank)], y[flank]
            )
            maximum = float(np.abs(conditional - rts(y, settings)[gap]).max())
            highest = max(highest, maximum)
            assert maximum < 1e-6, (length, settings, maximum)
    print(f"81 complete gap predictions match RTS, maximum absolute error {highest:.3g}")


if __name__ == "__main__":
    main()
