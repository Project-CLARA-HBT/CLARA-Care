# MovieLens development result

The mining-only opportunity misses the 20% end-to-end threshold on this workload. The paired ceiling removes all mining time while preserving identical inputs, outputs and measured build and materialization times. It is an analytical bound.

| Minimum support | Closed sets | Median total (s) | Median paired time saving | Maximum paired time saving |
|---:|---:|---:|---:|---:|
| 500 | 17650 | 0.641 | 5.25% | 5.37% |
| 1000 | 212 | 0.575 | 1.25% | 1.37% |
| 1500 | 30 | 0.628 | 0.61% | 3.42% |

Run each support in a fresh WSL CPU process with Python 3.12.15 and pyfim 6.28 using `python screen.py /path/to/ml-25m.zip SUPPORT`. Repeat the three supports in ascending order three times. The archive SHA-256 was `8b21cfb7eb1706b4ec0aac894368d90acf26ebdfb6aced3ebd4ad5bd1eb9c6aa` and the native extension SHA-256 was `2b3b7142100c33f8db758ac807654fb734c81f4e3457e6d2913edc92986b59ed`. Timing excludes interpreter startup, hashing and oracle checks. Raw phase times are seconds.

An initial oracle check exposed the native default minimum output size of one. Applying that convention to exhaustive enumeration yielded exact sets and supports on all three 64-user, eight-movie slices. Full-workload hashes agreed across repeats at each support. No UCI holdout was accessed. The ceiling applies only when preprocessing and output materialization are held fixed.
