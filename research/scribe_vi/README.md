# Estimating which Vietnamese ASR transcripts to defer

The [development protocol](PROTOCOL.md) asks whether fixed-coverage triage should estimate its aggregate token error objective directly. The selector estimates edit counts and reference lengths from other sentence prompts and optimizes the predicted ratio of their sums. An ablation uses the exact same two fitted regressions but ranks individual utterances by predicted error rate. All selectors see the same decoder outputs within each recognizer. The reference transcript is used only in training folds or post-selection scoring. An application that only needs beam confidence can skip the greedy decode.

## Data and scope

Google FLEURS supplies Vietnamese read speech and the normalized reference text, distributed under CC BY 4.0. All 361 development recordings, 149 distinct prompts and 71.659 minutes are in scope; all metadata rows report male gender. The ID repeats across different recordings of a sentence, and the published TSV has no independent speaker identifier. Neither population-level speaker independence nor clinical dictation accuracy can be inferred here. The reference tokens are Unicode letter/number runs. Whitespace segmentation in Vietnamese often yields syllables rather than lexical words. Record-level evidence contains counts, confidence and hashed file keys, with no audio, hypotheses or reference text. [FLEURS paper](https://arxiv.org/abs/2205.12446) · [Pinned dataset](https://huggingface.co/datasets/google/fleurs/tree/70bb2e84b976b7e960aa89f1c648e09c59f894dd/data/vi_vn)

PhoWhisper's Vietnamese adaptation used 844 hours of training data, including private recordings. The paper evaluates different benchmarks. Precise overlap with private and weakly supervised pretraining remains unverified. No further adaptation was applied to either recognizer here. [PhoWhisper](https://arxiv.org/abs/2406.02555) · [Whisper, ICML 2023](https://proceedings.mlr.press/v202/radford23a.html)

## Prior work and gap

TranscRater already learns transcript quality estimates from multiple features. e-WER estimates word error using recognizer information and a second recognizer. Decoder disagreement and predicting WER without references at inference time both have prior art. Fractional programming provides the ratio optimizer. The empirical question is whether optimizing a pooled-token objective rather than ranking per-recording estimates changes the outcome at the same deferral count. The regressions here are internal ablations; the experiments do not reproduce the complete published e-WER or TranscRater systems or establish algorithmic novelty. [TranscRater, ACL 2016](https://aclanthology.org/P16-4008/) · [e-WER, ACL 2018](https://aclanthology.org/P18-2004/) · [Dinkelbach, 1967](https://doi.org/10.1287/mnsc.13.7.492)

## Reproduction

Use Python 3.12 and the pinned dependency files. Run the following commands from this directory with a private scratch directory in ASR_CACHE. The summarizer needs NumPy. Reruns of the decode commands skip completed hashed file keys; use fresh result paths to repeat actual inference. The earlier av 19.0.0 attempt failed and its transcript-free failure log was excluded from method scoring. The successful run pins av 16.0.1. All splits other than the published dev split stay outside the experiment.

```sh
bash fetch.sh "$ASR_CACHE"
ct2-transformers-converter --model "$ASR_CACHE/pho-source" --output_dir "$ASR_CACHE/pho-model" --copy_files tokenizer.json preprocessor_config.json --quantization float16
python decode.py "$ASR_CACHE" "$ASR_CACHE/whisper.jsonl"
python decode.py "$ASR_CACHE" "$ASR_CACHE/pho.jsonl" --model-dir "$ASR_CACHE/pho-model"
python check_pairs.py "$ASR_CACHE/dev.tsv" "$ASR_CACHE/whisper.jsonl" "$ASR_CACHE/pho.jsonl"
python selection.py "$ASR_CACHE/pho.jsonl" > "$ASR_CACHE/pho.json"
python selection.py "$ASR_CACHE/whisper.jsonl" > "$ASR_CACHE/whisper.json"
node report.mjs "$ASR_CACHE/pho.json" "$ASR_CACHE/whisper.json"
```
