# Float16 replication of selective Vietnamese transcription on a WSL GPU

This development experiment reuses the models, audio, decoding parameters and
prompt-grouped selection rules of the CPU study frozen in commit
`952e53bd`. It varies the implementation backend from CPU int8 to single-worker
CUDA float16. This setting can change transcripts, estimation features and the
chosen deferrals. The evidence unit is a source prompt. Hardware timing, new
speakers, clinical errors and transfer to other sources are outside the comparison.

[FLEURS](https://huggingface.co/datasets/google/fleurs/tree/70bb2e84b976b7e960aa89f1c648e09c59f894dd/data/vi_vn)
supplies the 361 Vietnamese dev recordings and reference text (CC BY 4.0).
The baseline and primary recognizers are [Whisper-base CT2](https://huggingface.co/Systran/faster-whisper-base/tree/ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66)
and [PhoWhisper-base](https://huggingface.co/vinai/PhoWhisper-base/tree/7ebdb9e88f5cc5271fb88f4d642c82ff9388650e).
The latter snapshot is converted with float16 storage. Verify the source
download and conversion instructions in the CPU study at its frozen revision.
The checksum file here validates the exact FLEURS dev archive, its reference,
and both converted models as used for inference.

## Reproduce

Use Python 3.12 and an isolated environment named .venv. Supply CUDA 12
cuBLAS, cuDNN 9 and the WSL driver library directory to LD_LIBRARY_PATH.
Place dev.tar.gz, dev.tsv, model/ and pho-model/ alongside the scripts, then run:

```sh
uv pip install -p .venv/bin/python -r requirements.txt
bash run.sh
node verify.mjs results
node report.mjs results/pho-model.json results/model.json > RESULTS.md
```

run.sh expects unused output filenames and checks all inference-input hashes
before extraction. It emits only numeric per-recording evidence. The same
paired feature and conditional bootstrap implementation as the CPU study
generates the macro decisions in RESULTS.md.
