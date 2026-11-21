# Top-ten disagreement does not justify changing the fusion weight here

**Retire the disagreement-only fusion claim.** On 150 labeled queries from three NanoBEIR sources, gating the dense score weight by top-ten overlap underperformed a single weight trained on the same two external sources by 0.00445 macro nDCG@10. The paired stratified query bootstrap interval was [−0.01762, 0.00789]. The gated method won 20 queries, tied 106 and lost 24. The registered advancement margin was +0.02 with a positive gain on every source.

| Held-out source | Documents | Low-overlap queries / 50 | Dense alone | Tuned RRF | Trained convex | Gated convex | Per-query oracle |
|---|---:|---:|---:|---:|---:|---:|---:|
| NanoArguAna | 3,635 | 5 | .64054 | .59656 | .64438 | .63147 | .72459 |
| NanoFiQA2018 | 4,598 | 26 | .47745 | .49809 | .50563 | .50563 | .60003 |
| NanoSCIDOCS | 2,210 | 11 | .43281 | .40824 | .43435 | .43390 | .47862 |

All three global fits selected a dense weight of 0.9. For low/high overlap the folds selected 0.9/0.8, 0.9/0.9 and 0.8/1.0, respectively. The direction of the partition effect changed across training pairs, and the middle pair selected one identical parameter. The oracle's gains indicate that individual queries can favor different weights. The tested overlap statistic supplied insufficient information to choose them reliably. The candidate's advantage over default RRF vanishes against a tuned convex baseline. The group-specific means and uncertainty describe these three development sources. The small benchmarks do not estimate web-scale corpus behavior or the performance of other encoders. The full learned DAT system was not executed. Loss to the simpler matched arm sufficed for the prespecified retirement decision. [Prespecified design and closest studies](PROTOCOL.md) · [All comparator results](results/summary.json) · [Every query](results/query_scores.csv)

## Sources and reproduction

Zeta Alpha published the NanoBEIR subsets and their binary judgments under CC BY 4.0. The ordered candidate IDs retain published query identifiers. Sources were transformed into aggregate scores, overlap counts, weight grids and query lengths; texts and model weights remain external. Each archive in the score-generation step used its publisher's pinned version. [NanoArguAna](https://huggingface.co/datasets/zeta-alpha-ai/NanoArguAna) · [NanoFiQA2018](https://huggingface.co/datasets/zeta-alpha-ai/NanoFiQA2018) · [NanoSCIDOCS](https://huggingface.co/datasets/zeta-alpha-ai/NanoSCIDOCS) · [Apache-licensed MiniLM](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) · [Source checksums](sources.json)

The NVIDIA RTX 4060 Ti ran corpus and query encoding on WSL2 with PyTorch 2.6.0+cu124, transformers 4.49.0 and pyarrow 18.1.0. Both ranking methods scored every released document. Twenty ArgUana queries also appeared as document IDs and were excluded as potential self-matches. All 417 published binary links remained reachable. The oracle uses labels from the evaluated query and serves only as a diagnostic upper bound for the chosen grid. [Device record](results/device.json)

Run the following from this directory with Python 3.12 and the specified CUDA stack. A repeated comparison from the same complete score arrays reproduced the three ranking-dependent result files byte for byte. The independent Node checker reconstructs the cross-source fits from the per-query grid. Exact dense scores can depend on the CUDA runtime.

```sh
python fetch.py /tmp/nanobeir-data > /tmp/nanobeir-receipts.json
diff sources.json /tmp/nanobeir-receipts.json
python generate.py /tmp/nanobeir-data /tmp/nanobeir-scores
python compare.py /tmp/nanobeir-scores /tmp/nanobeir-results
node verify.mjs
```
