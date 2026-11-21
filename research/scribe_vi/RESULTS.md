# Prompt-held-out lexical error at matched deferral

The candidate fails the all-baselines criterion. Retire the present superiority claim.

## PhoWhisper-base

All 361 recordings gave a beam-five token error rate of 19.08% (1989/10422). Decoder exceptions were 0 with beam five and 0 with greedy decoding. Each policy accepted 291 recordings.

| Policy | Errors / accepted reference tokens | Error rate | Fractional minus policy, pp (conditional 95% interval) |
|---|---:|---:|---:|
| hash_control | 1533 / 8314 | 18.44% | -3.77 (-5.45, -2.19) |
| confidence | 1314 / 8771 | 14.98% | -0.31 (-1.16, 0.45) |
| disagreement | 1332 / 8412 | 15.83% | -1.16 (-2.31, -0.07) |
| confidence_ridge | 1314 / 8771 | 14.98% | -0.31 (-1.16, 0.45) |
| multifeature_wer | 1226 / 8507 | 14.41% | 0.26 (-0.18, 0.73) |
| error_count | 1209 / 7819 | 15.46% | -0.79 (-1.39, -0.20) |
| predicted_ratio | 1241 / 8515 | 14.57% | 0.10 (-0.32, 0.50) |
| fractional | 1205 / 8213 | 14.67% | reference |

## Whisper-base

All 361 recordings gave a beam-five token error rate of 44.39% (4626/10422). Decoder exceptions were 0 with beam five and 0 with greedy decoding. Each policy accepted 291 recordings.

| Policy | Errors / accepted reference tokens | Error rate | Fractional minus policy, pp (conditional 95% interval) |
|---|---:|---:|---:|
| hash_control | 3602 / 8314 | 43.32% | -6.08 (-10.20, -2.67) |
| confidence | 3803 / 8889 | 42.78% | -5.54 (-10.12, -1.62) |
| disagreement | 3180 / 8519 | 37.33% | -0.08 (-1.16, 0.98) |
| confidence_ridge | 3878 / 8456 | 45.86% | -8.61 (-13.05, -5.24) |
| multifeature_wer | 3127 / 8392 | 37.26% | -0.02 (-0.50, 0.46) |
| error_count | 2903 / 7500 | 38.71% | -1.46 (-2.57, -0.46) |
| predicted_ratio | 3209 / 8545 | 37.55% | -0.31 (-1.00, 0.34) |
| fractional | 3062 / 8221 | 37.25% | reference |

All deltas use percentage points. Negative values favor fractional selection. Intervals resample prompt clusters and keep fitted models and allocations fixed. These development intervals do not establish external superiority.

[Protocol and endpoint](PROTOCOL.md) · [Data sources, related work, and limitations](README.md)
