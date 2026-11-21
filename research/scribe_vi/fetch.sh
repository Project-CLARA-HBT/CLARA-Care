#!/usr/bin/env bash
# Fetch public development inputs to an external cache, then verify bytes.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$1"
cd "$1"
mkdir -p model pho-source
fleurs=https://huggingface.co/datasets/google/fleurs/resolve/70bb2e84b976b7e960aa89f1c648e09c59f894dd/data/vi_vn
base=https://huggingface.co/Systran/faster-whisper-base/resolve/ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66
pho=https://huggingface.co/vinai/PhoWhisper-base/resolve/7ebdb9e88f5cc5271fb88f4d642c82ff9388650e
fetch() { curl -fsSL --retry 3 -o "$2" "$1?download=true"; }
fetch "$fleurs/dev.tsv" dev.tsv
fetch "$fleurs/audio/dev.tar.gz" dev.tar.gz
for file in model.bin config.json tokenizer.json vocabulary.txt; do
    fetch "$base/$file" "model/$file"
done
for file in pytorch_model.bin tokenizer.json config.json preprocessor_config.json tokenizer_config.json special_tokens_map.json merges.txt added_tokens.json vocab.json generation_config.json normalizer.json; do
    fetch "$pho/$file" "pho-source/$file"
done
sha256sum -c "$here/inputs.sha256"
tar xzf dev.tar.gz
