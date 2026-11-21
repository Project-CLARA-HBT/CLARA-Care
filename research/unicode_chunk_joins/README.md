# Reproducing the Unicode chunk join comparison

The [paper](paper.md) reports the development experiment in [the design](design.md). From this directory on Linux, use Python 3.11+ and the ICU 74.2 shared library with Unicode data version 15.1 (the recorded run used Python 3.12.3 and Ubuntu's libicu74). No Python packages are required.

```sh
set -eu
run_dir=$(mktemp -d)
curl -fLSs https://www.unicode.org/Public/15.1.0/ucd/NormalizationTest.txt -o "$run_dir/NormalizationTest.txt"
python3 compare.py "$run_dir/NormalizationTest.txt" "$run_dir/results"
diff -ru results "$run_dir/results"
```

The runner checks the exact corpus SHA-256 and both ICU version numbers before scoring. Keep the downloaded data in its original form, including its copyright notice. [Unicode data and terms](https://www.unicode.org/terms_of_use.html)

[Counts](results/counts.csv) give the outcome of every policy by form and input group. Groups overlap. Each row records splits attempted, joins accepted directly, accepted joins with incorrect output, correct joins sent to repair, calls to the bounded window checker that examined the whole normalized join, and how many of those calls accepted. For policies without a window those last two counters are zero. The full-check control explicitly checks every whole join. [Audit metadata](results/audit.json) contain the file digest, input counts and the shortest observed examples for each failing heuristic, with ties broken by code-point sequence and cut position. All positions count Unicode scalar values.

The source-column sensitivity was specified before the first comparison. The longer-than-eight and derived-only Hangul Jamo groups are exploratory diagnostics. No input rows come from the CLARA repository.

The [natural-text extension](external-report.md) compares both ICU append operations on Vietnamese and Korean translation catalogs and reports the long-run stress results and supplemental native timings.
