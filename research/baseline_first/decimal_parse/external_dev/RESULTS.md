# Mauna Loa weekly CO₂ development replication

The original three-fractional-digit guard recognized **0 of 2,284** fields and direct delimiter recognition took **2.02% longer** than prescanning. Adapting both arms to the observed tenths scale yielded **15.29% lower** median elapsed time for direct recognition. The adapted guard recognized all 2,225 present measurements. Both arms routed the 59 empty fields through fallback. All four configurations matched every binary64 word and mask byte against the exact-fraction oracle before timing.

| Guard | Median direct µs/import | Median split µs/import | Direct wins / rounds |
|---|---:|---:|---:|
| Original milliscale | 57.43 | 56.29 | 7/16 |
| Adapted tenths | 30.21 | 35.66 | 16/16 |

Original-guard losses by zero-based round, expressed as percentage extra elapsed time: 0 (3.33%), 3 (0.80%), 4 (7.47%), 5 (3.51%), 7 (4.01%), 11 (10.03%), 12 (7.93%), 13 (11.11%), 14 (15.90%). All observations are in timings.csv. The adapted guard had no round losses.

The CSV distributed by statsmodels v0.14.5 reproduces a public-domain 1958–2001 weekly series from Hawaii. It contains an eight-digit calendar date and an atmospheric CO₂ concentration in ppmv. The independently sourced record qualifies the delimiter technique on a second decimal scale when the schema is known. The original guard's fallback-only result limits claims about transfer without adaptation. The single small warm file, one materialized column, one processor and repeated rounds provide no across-station inference or production-engine result. [Source metadata and attribution](https://github.com/statsmodels/statsmodels/blob/v0.14.5/statsmodels/datasets/co2/data.py)

## Reproduction

Run from this directory with GCC 13.3. The recorded processor was an Intel Xeon E5-2696 v4. Protocol commit d7e7fc1f precedes timings.

~~~bash
BUILD=$(mktemp -d)
curl -fLsS https://raw.githubusercontent.com/statsmodels/statsmodels/v0.14.5/statsmodels/datasets/co2/co2.csv -o "$BUILD/co2.csv"
git clone https://github.com/fastfloat/fast_float.git "$BUILD/ff"
git -C "$BUILD/ff" checkout dbeabeeb3e6791cb96994c2a7a084c36e62ccfb2
sed '/^int main(/,$d' ../parse.cpp > "$BUILD/reference.hpp"
g++ -O3 -std=c++20 -I"$BUILD" -I"$BUILD/ff/include" reader.cpp -o "$BUILD/reader"
python3 run.py "$BUILD/reader" "$BUILD/co2.csv" > "$BUILD/timings.csv"
~~~

SHA-256 of the input is pinned in run.py and PROTOCOL.md. Recorded binary SHA-256 was ee9fc1a69af64ece19a146148a5c446a0c7142625e934264e84b6d6810a20457. Raw timing file SHA-256 is 2412573a2877fee72a7904cf55e86ce5ea1844f52290e3afd988a0679e760fc9.
