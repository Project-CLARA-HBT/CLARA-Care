# Lazy version checks matched explicit ancestry on SGD embedding dispatches

On all 128 development dialogues, the two-node provenance cache (B4) and the lazy version-tag cache ran the encoder the same number of times. Both delivered identical authorized embeddings and cancelled the same reads. We retire the claim that explicit ancestry reduces reconstruction relative to every comparator on this workload, as specified before measurement. [Protocol](protocol.md)

| Arm | Encoder forwards | Authorized cache hits | Cancelled reads | Total timed replay (s) |
| --- | ---: | ---: | ---: | ---: |
| B1 full subject purge | 1,458 | 3,073 | 646 | 9.635 |
| B2 always recompute | 4,531 | 0 | 646 | 29.378 |
| Lazy dependency version check | 1,153 | 3,378 | 646 | 7.573 |
| B4 explicit ancestry | 1,153 | 3,378 | 646 | 7.718 |

B4 saved 305 forwards relative to B1, with fewer forwards in 127 dialogues and a tie in one. B4 saved 3,378 relative to B2 and won in all 128 dialogues. Against lazy checks B4 won zero dialogues, tied 128 and lost zero. Each delivered field has a single known dependency. Testing its version at read time preserved every cache hit the graph preserved. Public dialogue turns and values supplied repetition and changes. Withdrawal timing and permission labels were synthetic. [Per-dialogue counts](results1/histories.json)

Each arm produced 4,531 payloads of 1,536 bytes, totalling 6,959,616 authorized bytes. The independent verifier reconstructed the permission schedule from the source annotations, saw an empty payload on each of the 646 denied reads per arm, and checked every authorized byte against fresh computation. Byte agreement concerns the observed frames on this schedule. Embedding quality, device isolation, distributed ordering, missing lineage and multiple source dependencies were outside this experiment. The earlier cheap-projection development replay recorded higher median B4 latency than both B1 and B2. Here timings sum one rotated replay per dialogue on a shared RTX 4060 Ti. They describe this run only. [Verifier receipt](results1/verified.json) · [Device and software](results1/device.json)

## Reproduction

From the repository root, use a CUDA-enabled environment matching the device receipt, with Node available. The results directory must be new. The following downloads the pinned SGD training shard and the six MiniLM files. The runner checks the weight and tokenizer digests and the verifier checks the SGD digest. Vector frames are temporary.

```bash
study=research/venue2027/popets/embedding
inputs=$(mktemp -d)
curl -fsSL https://raw.githubusercontent.com/google-research-datasets/dstc8-schema-guided-dialogue/e852981ae34990f4358979625854259302feaa78/train/dialogues_001.json -o "$inputs/source.json"
python - "$study/model.json" "$inputs/model" <<'PY'
import json, pathlib, sys, urllib.request
manifest, model_dir = map(pathlib.Path, sys.argv[1:])
model_dir.mkdir()
for name, entry in json.loads(manifest.read_text()).items():
    urllib.request.urlretrieve(entry["url"], model_dir / name)
PY
PYTHONPATH=. python "$study/run.py" "$inputs/source.json" "$inputs/model" "$inputs/replay"
node "$study/report.mjs" "$inputs/replay"
node "$study/report.mjs" "$study/results1"
```

The source annotations come from the Schema-Guided Dialogue dataset by Abhinav Rastogi, Xiaoxue Zang, Srinivas Sunkara, Raghav Gupta and Pranav Khaitan. This adaptation encodes annotated service, slot and value tuples and publishes aggregate counts and timings. We distribute the adapted workload data under CC BY-SA 4.0. The encoder is sentence-transformers/all-MiniLM-L6-v2 at the pinned revision. [Dataset and attribution](https://github.com/google-research-datasets/dstc8-schema-guided-dialogue/blob/e852981ae34990f4358979625854259302feaa78/README.md) · [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) · [Model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/tree/1110a243fdf4706b3f48f1d95db1a4f5529b4d41)
