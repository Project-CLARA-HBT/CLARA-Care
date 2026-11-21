#!/bin/bash
set -euo pipefail
root_dir=$1
cpu=$2
mkdir -p "$root_dir/out"
echo 'day,round,position,arm,passes,elapsed_ns' > "$root_dir/timings.csv"
for day_path in "$root_dir"/days/*.csv; do
    name=$(basename "$day_path")
    taskset -c "$cpu" "$root_dir/parse" "$day_path" "$root_dir/out/$name" |
        sed "s/^/${name%.csv},/" >> "$root_dir/timings.csv"
done
