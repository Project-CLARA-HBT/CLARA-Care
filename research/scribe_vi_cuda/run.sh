#!/usr/bin/env bash
# Run inside a job-private workspace containing the pinned inputs and inference tools.
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 HF_HUB_OFFLINE=1
sha256sum -c inference-inputs.sha256
tar -xzf dev.tar.gz
test -d dev
.venv/bin/python -c 'import ctranslate2; assert ctranslate2.get_cuda_device_count() >= 1 and "float16" in ctranslate2.get_supported_compute_types("cuda")'
mkdir -p results
for model in pho-model model; do
    .venv/bin/python decode.py . "results/$model.jsonl" --model-dir "$model"
    .venv/bin/python selection.py "results/$model.jsonl" > "results/$model.json"
done
.venv/bin/python check_pairs.py dev.tsv results/model.jsonl results/pho-model.jsonl
