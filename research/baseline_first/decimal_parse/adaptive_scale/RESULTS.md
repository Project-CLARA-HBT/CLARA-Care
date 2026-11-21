# Learning decimal scale from earlier fields

Learning scale increased median elapsed time versus detecting scale in the current token by 4.22% on electricity and 3.03% on CO₂. Current-token detection won all 14 daily comparisons and the complete CO₂ import. Both validated the same output. The first recognized field selected a scale per column, and subsequent mismatches took the general fallback. This design provides automatic scale selection, with a measured runtime cost on both development sources.

| Comparator | UCI median adaptive saving | Dates adaptive lost | CO₂ adaptive saving |
|---|---:|---:|---:|
| Current-token detection | −4.22% | 14/14 | −3.03% |
| Known source scale | −6.33% | 13/14 | −7.78% |
| General cursor and fast_float | +48.67% | 0/14 | +41.75% |
| Known three-digit tenths format | — | — | −10.96% |

Each percentage uses one minus the ratio of median elapsed times per file. The UCI summary takes the median of those fourteen savings. CO₂ adaptive took 35.60 µs versus 32.08 µs with known width and scale. Record layout supplied delimiter and column count to all arms. Only the specialized controls received source precision or width. All arms reproduced every binary64 word and mask byte for 19,116 UCI rows and 2,284 CO₂ rows, including 14 and 59 missing numeric fields respectively. Separate untimed fixtures exercised invalid text, changing scales, signed zero, scientific notation and CRLF. The measured rows give little information about performance after scale changes.

The earlier UCI experiment found only 0.36% additional savings from predicting integer width. The scale experiment also gives no evidence of a speed advantage from history. The gain over general parsing includes fused validated recognition and specialized conversion. Neither dataset establishes novelty, cross-source generalization, or performance in a production parser.

[All file-level results and losing round IDs](comparisons.csv) · [610 raw timings](timings.csv) · [Frozen design](PROTOCOL.md)

## Reproduce

From this directory, use GCC 13.3, the fast_float 8.3.3 include directory in FF, the original UCI development day files in DAYS, the pinned statsmodels CSV in CO2, and an existing scratch directory in BUILD. Every timed arm reopens the warm file, reads blocks, materializes column vectors, and destroys them. Rounds within one file share inputs and environment.

~~~bash
sed '/^int main(/,$d' ../parse.cpp > "$BUILD/reference.hpp"
g++ -std=c++20 -O3 -I"$BUILD" -I"$FF" reader.cpp -o "$BUILD/reader"
python3 run.py "$BUILD/reader" "$DAYS" "$CO2" > reproduced.csv
~~~
