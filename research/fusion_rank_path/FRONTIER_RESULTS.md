# A small exact summary did not clear the runtime gate

The second algorithm needs at most the first ten rising crossing weights and the last ten falling crossing weights per judged document, plus the count of permanent outrankers capped at ten. To see why, fix a weight. Removing all rising crossings after the tenth preserves the number already crossed whenever that number is below ten. Otherwise the clipped rank is already eleven. The same argument applies in reverse order to falling crossings. Ties use the first integer at which stable document order changes. This bounds the crossing summary; the benchmark still reads the input, builds endpoint columns, and produces the complete requested output. [Prespecified follow-up](FRONTIER_PROTOCOL.md)

**Retire the claim that prefix elimination saves at least 20% against every strong comparator.** The shared AVX2 implementation without the prefix check was faster on seven of 12 NanoArguAna rounds in the original eight-arm comparison. In a second experiment that added two published-method ports it also won seven of 12 NanoFiQA2018 rounds. Both methods returned exactly the same rank curves. The condition for advancing failed in both experiments. [Eight-arm pairs](frontier_results/paired.csv) · [Ten-arm pairs](published_results/paired.csv)

| Source | vs bounded summary without prefix check, 8 arms | vs same ablation, 10 arms | vs LP-CTA port, 10 arms | vs DirectRank port, 10 arms |
|---|---:|---:|---:|---:|
| NanoArguAna | −1.68% | −1.59% | 98.36% | 97.11% |
| NanoFiQA2018 | 7.53% | −6.72% | 97.79% | 97.55% |
| NanoSCIDOCS | −0.08% | 7.10% | 96.24% | 93.87% |

Each cell is the median of paired fractions of runtime saved on the same 50 queries in 12 shuffled rounds. Negative values mean the candidate took longer. Method IDs in the raw files are 0 sweep, 1 skyband plus sweep, 2 early stopping, 3 first clipping method, 4 skyband plus clipping, 5 AVX2 sweep, 6 bounded summary, 7 bounded summary with prefix check, 8 LP-CTA adaptation, and 9 DirectRank adaptation. Every algorithm was compiled with the same flags. Both new ports share computations across the positives of a query. All preprocessing from the common in-memory score rows is timed. Implementation choices materially limit transfer of the observed savings to the authors' algorithms. Our LP-CTA port recomputes skylines; the published algorithm uses incremental skyline maintenance. The DirectRank port reconstructs top k at ambiguous integer crossing events. [LP-CTA fidelity](cta/README.md) · [DirectRank fidelity](directrank/README.md)

Schedules, complete paired outputs and verification receipts are archived for [eight arms](frontier_results/timings.csv) and [ten arms](published_results/timings.csv). All methods matched the original verified curves. On these development queries the 21-point grid detected every positive that any of the 65,536 weights ever retrieved in the top ten. The exact audit still found missed internal rank changes on some individual queries. The largest source-level optimal nDCG@10 gain over a 101-point grid was 0.00196. [Impact and every missed interval](impact/RESULTS.md)

## Reproduction

Use the input checksum and score-generation instructions in [the first experiment](RESULTS.md). Both experiments used CPU 0 of the shared WSL2 i5-12600K. Compile without the published-method flag for the eight-arm experiment and omit it from the command below; pass `--stage frontier` to the summarizer in that case.

```bash
g++ -std=c++17 -O3 -mavx2 -static -DRANKPATH_EXTENSIONS -DRANKPATH_PUBLISHED path.cpp -o "$OUT/benchmark"
taskset -c 0 "$OUT/benchmark" "$OUT/data.txt" "$OUT/curves.tsv" "$OUT/timings.csv"
cmp "$OUT/curves.tsv" results/changes.tsv
python verify.py "$OUT/data.txt" "$OUT/curves.tsv" "$OUT/benchmark"
python summarize.py --stage published "$OUT/timings.csv"
```
