# Joining normalized Vietnamese and Korean message chunks

The form-aware rule, ICU normalized append, and ICU normalize-second-and-append each produced the whole-input reference at every tested cut. The rule found extra direct joins over ICU’s immediate boundary predicates in one rendering and only for decomposed output. A cap on the composition window missed entire runs of safe joins in the stress tests. We retire the algorithmic novelty claim. Unicode already describes boundary-local normalization, and the decomposed case follows from canonical ordering. [UAX #15 rev. 54](https://www.unicode.org/reports/tr15/tr15-54.html) · [Scherer, Canonical Equivalence in Applications](https://www.unicode.org/notes/tn5/)

## Natural text

The Ubuntu debconf catalogs contain 68 Vietnamese and 67 Korean translation entries after excluding the headers. We retained repeats, placeholders and whitespace, rendered each entry as distributed and with ICU NFD, and split it at every interior Unicode scalar boundary. At each cut we compared actual strings against ICU whole-input normalization and checked the latter against Python 3.12.3 (Unicode 15.0.0). ICU 74.2 uses Unicode 15.1. The 59,640 cut/form evaluations reuse the same messages. Each table entry below describes one output form at a time. NFC and NFKC had identical counts, as did NFD and NFKD. [Pre-run design](external-design.md) · [Complete paired counts](external-results/counts.csv)

| Catalog | Rendering | Cuts per form | Safe direct joins, NFC or NFKC | Safe direct joins, NFD or NFKD | Extra safe accepts over boundary union, composed / decomposed |
|---|---|---:|---:|---:|---:|
| Vietnamese | Packaged | 3,876 | 3,876 | 3,876 | 0 / 0 |
| Vietnamese | NFD | 4,834 | 3,876 | 4,834 | 0 / 294 |
| Korean | Packaged | 2,224 | 2,224 | 2,224 | 0 / 0 |
| Korean | NFD | 3,976 | 2,224 | 3,976 | 0 / 0 |

The form-aware rule accepted every safe direct join on these catalogs and lost zero safe accepts relative to the union. The historical four-per-side rule also accepted every safe join here. The unbounded window and full normalizedness check matched that coverage. The zero-class starter shortcut returned the wrong output on 1,752 cuts of NFD-rendered Korean in each composed form. The adjacent-pair shortcut made zero errors on the catalogs. For the two native API rows, the direct count measures how often the returned string equaled the independently normalized halves concatenated. Internal work was unobserved. Error locators use one-based sorted non-header message-key order and a cut measured in scalar values from the start of the rendering. [First failing cut by group](external-results/first-errors.json)

## Stress and coverage

For each run length we tested every cut of A followed by 64 or 256 class-220 marks (U+0316) and a final mark. With a further U+0316, the entire sequence is already ordered. In each composed form, all 65 or 257 joins were safe. The form-aware rule fell back on all of them, while the unbounded and whole-join tests accepted every one. With a final U+0334 (class 1), the cap also missed the sole safe join at each length. With a final grave accent (U+0300, class 230), every cut in each composed form required repair. The adjacent-pair shortcut accepted all of them incorrectly. In decomposed output the form-aware rule accepted exactly the safe joins across all three constructions. Both native APIs returned the reference throughout. [Stress rows in the counts](external-results/counts.csv)

## Supplemental latency observations

The committed design specified coverage and exact outputs. We measured latency separately in a compiled C++20 harness using the ICU C API on the same catalog cuts. Each method copied the same normalized left prefix into a reusable UTF-16 destination. With an already normalized right chunk we compared ICU append to the guard with append fallback. With an original right chunk we compared ICU normalizeSecondAndAppend to explicit right normalization followed by the guard. Every implementation reproduced every reference before timing, and the native guard reproduced each Python decision. Timings exclude input preparation, allocations for the caller’s buffers, and correctness comparisons.

Each cell is the median of eight round means in nanoseconds per join, with 16 passes over the stratum per round and rotating method order. Lower is faster within each input contract. This is one hot-buffer workload on a shared Intel Xeon E5-2696 v4 host, pinned to logical CPU 30, compiled with GCC 13.3.0 and `-O3`. The small differences have no established significance. [All round measurements](external-results/latency.csv) · [Benchmark](external_latency.cpp)

| Catalog | Rendering | Output | ICU append | Guard | ICU normalizeSecondAndAppend | Normalize then guard |
|---|---|---|---:|---:|---:|---:|
| ko | NFD | NFC | 177.6 | 172.7 | 479.6 | 619.8 |
| ko | NFD | NFD | 143.0 | 44.9 | 295.8 | 292.5 |
| ko | NFD | NFKC | 173.5 | 175.8 | 485.8 | 620.9 |
| ko | NFD | NFKD | 138.8 | 44.3 | 288.9 | 292.4 |
| ko | packaged | NFC | 120.8 | 34.0 | 197.6 | 207.4 |
| ko | packaged | NFD | 135.2 | 40.0 | 559.3 | 554.2 |
| ko | packaged | NFKC | 120.2 | 34.7 | 198.2 | 208.0 |
| ko | packaged | NFKD | 136.5 | 39.5 | 572.3 | 560.2 |
| vi | NFD | NFC | 173.3 | 143.6 | 1195.8 | 1273.0 |
| vi | NFD | NFD | 152.0 | 47.7 | 474.6 | 462.0 |
| vi | NFD | NFKC | 172.6 | 142.7 | 1205.7 | 1280.7 |
| vi | NFD | NFKD | 155.9 | 47.9 | 481.2 | 487.8 |
| vi | packaged | NFC | 129.0 | 43.2 | 215.2 | 224.6 |
| vi | packaged | NFD | 157.0 | 47.1 | 513.3 | 512.3 |
| vi | packaged | NFKC | 129.7 | 42.6 | 227.7 | 239.1 |
| vi | packaged | NFKD | 155.5 | 48.7 | 490.5 | 488.6 |

The guard had lower median time than normalized append in 15 of 16 strata. Its loss was NFKC on NFD-rendered Korean (175.8 versus 173.5 ns). With an original right chunk, normalizing then guarding had higher median time than native normalizeSecondAndAppend in 10 of 16 strata. Its largest relative loss was NFC on NFD-rendered Korean (619.8 versus 479.6 ns). These development measurements establish neither a general latency advantage nor performance on production chunk sizes.

## Source verification and replay

On 2026-11-21 between 07:47 and 07:54 UTC we verified the following SHA-256 fingerprints. The external design was committed at 07:41:05 UTC. The reference documents matched the copies saved by the earlier worker. The packaged catalogs matched the installed catalogs byte for byte.

| Source | SHA-256 |
|---|---|
| [Ubuntu debconf-i18n 1.5.86ubuntu1](https://archive.ubuntu.com/ubuntu/pool/main/d/debconf/debconf-i18n_1.5.86ubuntu1_all.deb) | `1d139fdc52af51c89a044d973937d411750c254f636b7b3228c8570085d59586` |
| Vietnamese debconf.mo (PO revision 2012-08-07 09:47 UTC) | `e16b70aca8589ab8b6a5f5692a1ace14b8737708ba2fd792b8320e9c91ab354b` |
| Korean debconf.mo (PO revision 2008-07-20 02:28 UTC) | `482727cd3763b9279d389539b584ee660a4a023156cecd4ccee06dab207ac2b2` |
| [UAX #15 revision 54](https://www.unicode.org/reports/tr15/tr15-54.html) | `01cf994cda71449fff3c23dbde1b08ad99e3f0ca4f42560e8aeb0201fef1ebe3` |
| [Canonical Equivalence in Applications](https://www.unicode.org/notes/tn5/) | `05709d036b1b5f76872e04ff17572fe11c78040c7390dea73cba8f19ac51240a` |
| [ICU 74.2 unorm2.h](https://raw.githubusercontent.com/unicode-org/icu/release-74-2/icu4c/source/common/unicode/unorm2.h) | `515e96020bacf9e14eb6ab83dfd0a8c6ca50741a7d3d1f7e9ce48e225bb9b723` |
| [NormalizationTest 15.1, preceding experiment](https://www.unicode.org/Public/15.1.0/ucd/NormalizationTest.txt) | `871238e37e3be0696ec2bd0891119a041b052da1a84485eda05a5438724b223e` |

From this directory on Ubuntu with ICU 74.2 and Python 3.12, the commands below reproduce the comparison in a temporary directory. Keep the extracted package, notices and per-cut message data outside Git. The program verifies both catalog digests and ICU versions before scoring. Set the timing CPU to an available core for a replay.

```sh
set -eu
experiment=$PWD
run=$(mktemp -d)
cd "$run"
apt-get download debconf-i18n=1.5.86ubuntu1 libicu-dev=74.2-1ubuntu3.1
dpkg-deb -x debconf-i18n*.deb corpus
dpkg-deb -x libicu-dev*.deb headers
python3 "$experiment/external.py" corpus/usr/share/locale results --bench-input cuts.tsv
diff "$experiment/external-results/counts.csv" results/counts.csv
diff "$experiment/external-results/first-errors.json" results/first-errors.json
g++ -O3 -std=c++20 -Iheaders/usr/include "$experiment/external_latency.cpp" -l:libicuuc.so.74 -o bench
taskset -c 30 ./bench < cuts.tsv > results/latency.csv
```
