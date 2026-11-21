# Prompt-held-out lexical error at matched deferral

The candidate fails the all-baselines criterion. Retire the present superiority claim.

## PhoWhisper-base

All 361 recordings gave a beam-five token error rate of 20.86% (2174/10422). Decoder exceptions were 0 with beam five and 0 with greedy decoding. Each policy accepted 291 recordings.

| Policy | Errors / accepted reference tokens | Error rate | Fractional minus policy, pp (conditional 95% interval) |
|---|---:|---:|---:|
| hash_control | 1703 / 8314 | 20.48% | -2.53 (-4.06, -1.10) |
| confidence | 1494 / 8794 | 16.99% | 0.97 (0.16, 1.86) |
| disagreement | 1527 / 8450 | 18.07% | -0.12 (-2.18, 2.72) |
| confidence_ridge | 1494 / 8794 | 16.99% | 0.97 (0.16, 1.86) |
| multifeature_wer | 1464 / 8469 | 17.29% | 0.67 (0.17, 1.25) |
| error_count | 1310 / 7791 | 16.81% | 1.14 (-0.97, 4.30) |
| predicted_ratio | 1523 / 8560 | 17.79% | 0.16 (-0.77, 1.01) |
| fractional | 1451 / 8081 | 17.96% | reference |

## Whisper-base

All 361 recordings gave a beam-five token error rate of 41.48% (4323/10422). Decoder exceptions were 0 with beam five and 0 with greedy decoding. Each policy accepted 291 recordings.

| Policy | Errors / accepted reference tokens | Error rate | Fractional minus policy, pp (conditional 95% interval) |
|---|---:|---:|---:|
| hash_control | 3372 / 8314 | 40.56% | 0.67 (-1.45, 3.55) |
| confidence | 3484 / 8854 | 39.35% | 1.88 (0.75, 3.08) |
| disagreement | 3340 / 8687 | 38.45% | 2.78 (0.42, 5.56) |
| confidence_ridge | 3484 / 8854 | 39.35% | 1.88 (0.75, 3.08) |
| multifeature_wer | 3276 / 8148 | 40.21% | 1.02 (0.39, 1.78) |
| error_count | 2929 / 7371 | 39.74% | 1.49 (-0.88, 4.63) |
| predicted_ratio | 3374 / 8269 | 40.80% | 0.42 (-0.41, 1.13) |
| fractional | 3264 / 7917 | 41.23% | reference |

All deltas use percentage points. Negative values favor fractional selection. Intervals resample prompt clusters and keep fitted models and allocations fixed. These development intervals do not establish external superiority.

[Protocol and endpoint](PROTOCOL.md) · [Data sources, related work, and limitations](README.md)
