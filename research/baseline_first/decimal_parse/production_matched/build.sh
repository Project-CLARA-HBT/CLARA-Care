#!/usr/bin/env bash
set -eu
src=$1 # external/duckdb from duckdb 1.4.3 PyPI sdist
out=$2
mkdir -p "$out"
file="$src/src/execution/operator/csv_scanner/scanner/string_value_scanner.cpp"
cp "$file" "$out/base.cpp"
cp "$file" "$out/fast.cpp"
patch "$out/fast.cpp" < "$(dirname "$0")/scanner.patch"
echo "{ global: _ZN6duckdb17StringValueResult16AddValueToVectorEPKcmb; local: *; };" > "$out/exports.map"
for mode in base fast; do
  g++ -std=c++17 -O2 -DNDEBUG -Wl,--version-script="$out/exports.map" -I"$src/third_party/utf8proc/include" -fPIC -shared -I"$src/src/include" -I"$src/third_party/fast_float" -I"$src/third_party/fmt/include" "$out/$mode.cpp" -o "$out/$mode.so"
done
