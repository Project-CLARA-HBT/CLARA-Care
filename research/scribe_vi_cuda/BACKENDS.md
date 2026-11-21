# Paired backend comparison on FLEURS vi_vn development

Each row compares CPU int8 with CUDA float16 on the same 361 recordings. The sign of the change refers to errors on a single clip under beam-five decoding.

| Recognizer | Fewer errors on CUDA | Equal | More | Full CPU token error | Full CUDA token error | Fractional policy CPU | Fractional policy CUDA |
|---|---:|---:|---:|---:|---:|---:|---:|
| PhoWhisper-base | 45 | 234 | 82 | 19.08% | 20.86% | 14.67% | 17.96% |
| Whisper-base | 127 | 151 | 83 | 44.39% | 41.48% | 37.25% | 41.23% |

The precision and device changed together. Equal error counts can come from different hypotheses. Each selector was refit on its backend-specific features with the same prompt fold assignments. The within-backend paired contrasts are in [the CUDA results](RESULTS.md) and [the CPU results](../scribe_vi/RESULTS.md).
