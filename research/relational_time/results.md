# Lossless timestamp pairs on Synthea and Olist

**Decision. Retire the type-history predictor and block-selector superiority claims.** Removing history yielded the exact same byte count on every input. A simpler parent-relative or calendar-day encoding explains the improvement. The study does not qualify as a paper under the all-baselines criterion.

| Public development input | Pairs | Best fixed whole-file pair, pass 1 | Block selector, pass 1 | Basic joined predictor, pass 2 | Without history, pass 2 | Full candidate, pass 2 |
|---|---:|---:|---:|---:|---:|---:|
| Synthea latest sample | 8,054 | 11,664 B | 12,097 B | 10,247 B | 10,247 B | 10,247 B |
| Synthea November 2021 | 56,430 | 57,120 B | 58,612 B | 53,838 B | 53,838 B | 53,838 B |
| Olist reviews | 99,224 | 513,273 B | 541,905 B | 393,142 B | 338,115 B | 338,115 B |

The Olist gain of 55,027 bytes over the basic join arises when the encoder uses the calendar day of purchase as the anchor for the review creation time. The no-history comparator can make the same choice. The two Synthea releases prefer the parent encounter start without a calendar transform. These are marginal timestamp sizes when the decoder already has the ordered keys, event types and parent timestamps. End-to-end storage, parent fetch cost, throughput and random access were unmeasured. Both passes selected configurations using data from the whole development input. The second pass searched 120 endpoint configurations. This is an optimistic upper bound on selection performance for deployment.

Related work already uses horizontal correlations and selects correlations automatically in an open columnar format. The experiments implement explicit predictors with PyArrow, not the published Corra or Virtual systems. An independent all-baseline claim would require executable comparisons and evidence that a new mechanism adds value after removing its cheaper alternatives. The observed ablation tie already rejects the present claim. [Corra](https://arxiv.org/abs/2403.17229) · [Virtual](https://arxiv.org/abs/2410.14066)

## Reproduction

Download the two [Synthea sample releases](https://github.com/synthetichealth/synthea-sample-data/tree/e468b9163e04c34ad389ffa9160a3bacab22e892/downloads) and the [public Olist release](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). Each committed JSON records the source archive hash and PyArrow version. Use the original ZIPs, preserving input order. Run from the repository root, replacing the sample path and dataset name for each input. The reader decodes every candidate stream before reporting its size. Only aggregate bytes and encoder choices are published.

```sh
python -m evaluation.relational_time.benchmark olist /path/to/olist.zip
python -m evaluation.relational_time.granularity olist /path/to/olist.zip
```

[Prespecified choices and sequencing](protocol.md) · [Latest](pass2_latest.json) · [November 2021](pass2_2021.json) · [Olist](pass2_olist.json)
