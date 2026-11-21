# Full BEIR external validation of the fusion audit

**Retire the universal 20% runtime-saving claim.** On both external collections, prefix elimination produced the same exact rank paths as its bounded-summary ablation. Its median paired saving against that ablation was only 0.31% on SciFact and 3.02% on NFCorpus. On SciFact it saved 8.39% against the earlier scalar clipping method. The two external results reinforce the failed NanoBEIR development criterion. [Prespecified protocol](PROTOCOL.md) · [Every comparator, interval and round loss](results/paired.csv)

| External test | Queries | Documents | Positive pairs | Saving vs LP-CTA port | Saving vs DirectRank port | Saving vs bounded-summary ablation, order-statistic interval | Faster / tied / slower vs ablation |
|---|---:|---:|---:|---:|---:|---:|---:|
| SciFact | 300 | 5,183 | 339 | 98.29% | 97.36% | 0.31% [−25.02%, 7.84%] | 6 / 0 / 6 |
| NFCorpus | 323 | 3,633 | 12,334 | 94.37% | 81.63% | 3.02% [−73.93%, 12.94%] | 8 / 0 / 4 |

Each of ten methods produced all 12,673 curves correctly in every timed round. The independent binary-search oracle matched all **830,537,728** clipped ranks, with 5,607 stable full-sort controls on the actual data. The outcome measures exactness and time to audit rank changes at every representable weight, after computing dense and sparse scores. It does not measure improved retrieval quality, clinical relevance or downstream decisions. The original LP-CTA port recomputes skylines; the primary SIGMOD and KDD implementations have separate fidelity limitations. [Oracle](results/verification.json) · [Per-positive curves](results/curves.tsv) · [Port fidelity](../PRIOR.md)

The reported saving is the median of 12 within-round fractional reductions on a complete corpus-specific query batch. Timing includes per-query preprocessing from common in-memory score rows. The interval uses the second and eleventh order statistics. Its nominal median coverage under independent, identically distributed continuous draws is 99.37%. The 12 rounds share one WSL2 host and the same workload; this range describes timing dispersion. It provides no cross-host or cross-query population confidence guarantee. The RTX 4060 Ti ran the pinned MiniLM encoder. Wall-time comparisons ran on CPU 0 after scoring. The strongest simple ablation met neither source's 20% margin. [Round order and nanoseconds](results/timings.csv) · [Executable hash and toolchain](results/runtime.json)

## External source quality and independence

Thakur et al. included both datasets in BEIR, published in the NeurIPS 2021 Datasets and Benchmarks track. We used each entire corpus with all queries appearing in its test qrels. No self-matches or positive pairs were lost. SciFact comes from Wadden et al.'s scientific-claim verification dataset (EMNLP 2020). NFCorpus comes from Boteva et al.'s medical-information retrieval corpus (ECIR 2016). NFCorpus derives graded relevance from direct and indirect citations on NutritionFacts.org. Those grades indicate links between queries and documents. The benchmark treats positive grades as membership in the set to audit, including all 576 NFCorpus grade-2 pairs. [BEIR](https://datasets-benchmarks-proceedings.neurips.cc/paper/2021/hash/65b9eea6e1cc6bb9f0cd2a47751a186f-Abstract-round2.html) · [SciFact](https://aclanthology.org/2020.emnlp-main.609/) · [NFCorpus and original terms](https://www.cl.uni-heidelberg.de/statnlpgroup/nfcorpus/)

All 54 normalized exact-text comparisons between the two external collections and the three NanoBEIR development collections found zero shared nonempty fingerprints. The comparison covers queries, document bodies and title-plus-body, including cross-field matches. Empty strings were counted separately. A paraphrase or a partial passage can escape this check. The two new tasks were chosen for their small enough corpora to score all documents, and their label density differs substantially. Generalization to larger corpora needs separate evidence. [Input counts and overlap by field](results/materialized.json)

The original BEIR ZIP endpoint timed out on WSL. We used the BEIR maintainers' Hugging Face releases, with four pinned revisions, six SHA-256 checksums and 623 held-out query IDs. The Hugging Face cards label their releases CC BY-SA 4.0. The original NFCorpus site permits academic use and refers other NutritionFacts uses to its terms. Raw texts remain external. Derived BEIR labels and curves here are attributed to the original authors and BEIR under CC BY-SA 4.0. [Source digests](results/sources.json) · [BEIR SciFact](https://huggingface.co/datasets/BeIR/scifact/tree/b3b5335604bf5ee3c4447671af975ea25143d4f5) · [BEIR NFCorpus](https://huggingface.co/datasets/BeIR/nfcorpus/tree/b5026a0e96e8a7ac4f95f482a596389289d46269)

## Reproduction

Use a fresh directory on a CUDA host with the versions recorded in the input receipt and GCC 13 supporting AVX2. Run from the repository root at the frozen method revision with this replication directory available. The existing NanoBEIR downloader obtains the development overlap inputs and pinned encoder. The scorer validates every NanoBEIR and model asset against its recorded digest.

```bash
s=research/fusion_rank_path/beir_replication
p=research/fusion_rank_path
r=research/retrieval_disagreement
python "$s/fetch_data.py" "$OUT/external" > "$OUT/sources.json"
diff "$s/results/sources.json" "$OUT/sources.json"
python "$r/fetch.py" "$OUT/nano" > "$OUT/nano-sources.json"
PYTHONPATH="$r:$p" python "$s/materialize.py" "$OUT/external" "$OUT/nano" "$r/sources.json" "$OUT/data.txt" > "$OUT/materialized.json"
g++ -Wall -Wextra -Werror -O3 -mavx2 -std=c++17 -static -DRANKPATH_EXTENSIONS -DRANKPATH_PUBLISHED "$p/path.cpp" -o "$OUT/benchmark"
taskset -c 0 "$OUT/benchmark" "$OUT/data.txt" "$OUT/curves.tsv" "$OUT/timings.csv"
cmp "$OUT/curves.tsv" "$s/results/curves.tsv"
python "$p/verify.py" "$OUT/data.txt" "$OUT/curves.tsv" "$OUT/benchmark" > "$OUT/verification.json"
node --check "$s/report.mjs"
node "$s/report.mjs" "$OUT"
```
