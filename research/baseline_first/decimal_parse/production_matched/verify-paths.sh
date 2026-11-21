#!/usr/bin/env bash
# Run after build.sh. Instrument separate copies and require each branch marker.
set -euo pipefail
src=$1
out=$2
wheel=$3
day=$4
here=$(dirname "$0")
for arm in base fast; do
  case "$arm" in
    base) pattern='case LogicalTypeId::DOUBLE:' ;;
    fast) pattern='if (valid) {' ;;
  esac
  awk -v target="$pattern" -v arm="$arm" '
    {print}
    !seen && index($0,target) {
      print "{ static bool first=true; if(first) { first=false; fprintf(stderr, \"entered " arm "\\n\"); } }"
      seen=1
    }
    END {if(!seen) exit 1}
  ' "$out/$arm.cpp" > "$out/probe-$arm.cpp"
  g++ -std=c++17 -O2 -DNDEBUG -shared -fPIC -Wl,--version-script="$out/exports.map" \
    -I"$src/src/include" -I"$src/third_party/fast_float" -I"$src/third_party/fmt/include" \
    -I"$src/third_party/utf8proc/include" "$out/probe-$arm.cpp" -o "$out/probe-$arm.so"
  PYTHONPATH="$(dirname "$wheel")" LD_PRELOAD="$out/probe-$arm.so:$wheel" \
    python3 "$here/run.py" worker "$day" 2>"$out/probe-$arm.log"
  grep -Fx "entered $arm" "$out/probe-$arm.log"
done
