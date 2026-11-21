# Matched DuckDB 1.4.3 CSV imports

Across 14 development dates the median daily time saving was 2.65%. The candidate won 10 dates. All four daily losses occurred in December 2006 on the 16th (4.92% slower), 17th (6.51%), 19th (4.35%) and 20th (1.71%). Each daily saving is one minus the ratio of the candidate and baseline median import times. Four paired rounds per date give limited precision. This result falls below the earlier 20% development target.

Both arms use the same Python wheel, schema, projection, RAM file, single-thread configuration and pinned CPU. Linux symbol interposition replaces StringValueResult::AddValueToVector with the same-toolchain build of the baseline or patched scanner. Only that method is exported. The baseline calls DuckDB's TryDoubleCast. The candidate recognizes unsigned decimal fields with one to five integer digits and exactly three fractional digits. All 133,798 present fields qualified. The fallback therefore has no timing coverage here. Each timed import verified every binary64 word against Python Fraction and every missing mask position (14 across 19,116 rows). SQL execution through NumPy export is timed after one warmup per fresh worker. Startup, file loading and correctness checks are outside the timer. Order alternates within and across dates. Concurrent machine activity can affect these short measurements.

The baseline loader trace showed the wheel binding AddValueToVector to base.so. Separate instrumented builds printed “entered base” inside the baseline DOUBLE case and “entered fast” inside the successful guard during verified imports of December 16. Both probes passed. Timed builds omit the instrumentation.

## Reproduction

Use Linux x86-64, CPython 3.12 with NumPy, GCC 13.3, and the DuckDB 1.4.3 PyPI source distribution (SHA-256 fea43e03604c713e25a25211ada87d30cd2a044d8f27afab5deba26ac49e5268). Set SRC to its external/duckdb directory, WHEEL to the absolute path of the unpacked wheel's _duckdb shared library (SHA-256 f8dba4b1f5c8e5f6e872f83e3b327f94c6f962f2bd3cb0acf5551cf60bbfaba2), OUT to an absolute scratch directory, and DAYS to the fourteen dates extracted with ../prepare.py. Run from this directory.

```bash
manifest=$PWD/days.sha256
(cd "$DAYS" && sha256sum -c "$manifest")
bash build.sh "$SRC" "$OUT"
bash verify-paths.sh "$SRC" "$OUT" "$WHEEL" "$DAYS/2006-12-16.csv"
python3 run.py "$DAYS" "$OUT" "$WHEEL" > reproduced.csv
```
