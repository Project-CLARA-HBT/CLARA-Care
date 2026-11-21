# Full-row streaming reader

Direct delimiter recognition reduced elapsed time by **22.07%** at the median development date compared with the same converter after delimiter prescanning. It won all 14 dates, with daily savings of 21.10% to 25.44%. Median daily import times were 121.1 µs direct and 155.1 µs split. Each measurement includes opening and closing a warm file, reading blocks, assembling complete rows, skipping the date and time, allocating and growing seven double columns and seven byte masks, and destroying the arrays. Each daily estimate uses eight measurements of 16 imports each, pinned to one logical CPU.

Both readers reproduced every expected binary64 word and mask byte for all 19,116 development rows, including 14 missing values. A separate three-row fixture exercised signed zero, scientific notation, long integer parts, malformed fields and missing values. The reader targets unquoted, newline-terminated UCI rows. Its fixed-width guard handles one to three digits before the decimal and exactly three after it. It uses fast_float for other present fields. The fixture checks native missing and invalid sentinels. It supplies no evidence about fallback-heavy throughput.

The existing pinned DuckDB 1.4.3 baseline took 1,829.7 µs at the median date for a warm SQL import through NumPy export. This contextual timing includes query and binding overhead, uses a RAM file, and comes from a separate run. Only the direct-versus-split comparison isolates delimiter handling. The prior matched DuckDB scanner modification saved 2.65% at the median date. The native gain applies to this specialized reader on these development files.

## Reproduction

Use GCC 13.3 and the existing fast_float 8.3.3 include tree. Set DAYS to the original fourteen day files, FF to the fast_float include directory, and BUILD to an existing scratch directory. Run from this directory.

~~~bash
sed '/^int main(/,$d' ../parse.cpp > "$BUILD/reference.hpp"
g++ -std=c++20 -O3 -I"$BUILD" -I"$FF" reader.cpp -o "$BUILD/reader"
python3 run.py "$BUILD/reader" "$DAYS" > reproduced.csv
~~~

For each arm and date, divide the median ns_per_16 by 16. Compute savings as one minus the direct-to-split time ratio, then take the median across dates. The DuckDB comparator uses the median base_ns per date from ../production_matched/timings.csv.
