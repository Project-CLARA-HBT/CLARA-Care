# Rare shared values added zero links beyond instance-aware COMA

**Retire the schema-matching superiority claim.** The candidate and Valentine's instance-aware COMA emitted exactly the same links on all eleven development pairs. Allowing values owned by several columns also left every predicted set unchanged. The added evidence had no incremental effect at the frozen threshold and row budget.

| Published table family | Pairs | Header F1 | Cupid F1 | COMA schema F1 | COMA with values F1 | Added shared values F1 | Added rare values F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Magellan | 7 | 1.0000 | 0.6805 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| Wikidata | 4 | 0.2081 | 0.3187 | 0.6194 | 0.7869 | 0.7869 | 0.7869 |

Each cell is the equal-pair mean of exact-link F1. The seven Magellan pairs contain 41 published links and admit perfect header matching. The four Wikidata pairs share one musicians source family and contain 40 link labels across pairs. Two published links refer to a column spelling absent from a supplied header, one in the unionable pair and one in the view-union pair. Both remain in every arm's denominator. All arms received the first 96 rows of each table. Findings apply to that sample, these layouts and this implementation. Magneto was identified as a stronger learned comparator for a broader claim; the protocol's elimination rule already failed against COMA. [Frozen protocol](protocol.md) · [Paired link sets and missing-key audit](paired.json) · [Scores](scores.json)

## Reproduction

Koutras, Siachamis, Ionescu, Psarakis, Brons, Fragkoulis, Lofi, Bonifati and Katsifodimos published the original Valentine benchmark tables and mappings under CC BY 4.0. The paired artifact reproduces column-link labels and adds predictions. It contains no cell values. [Original deposit and license](https://doi.org/10.5281/zenodo.5084605)

A second execution reproduced both JSON artifacts byte for byte. All 81 table-pair gold links were cross-checked against the archive.

Use Python 3.12.3, the package versions in the paired JSON and the released Valentine 1.0.0 package used in the run. Download the benchmark ZIP from the deposit, preserving its bytes. From the repository root:

```sh
python -m pip install 'valentine==1.0.0' 'pandas==3.1.1' 'numpy==2.5.5' 'nltk==3.10.4' 'rapidfuzz==3.14.6'
python -m nltk.downloader punkt_tab omw-1.4 stopwords wordnet
study=research/schema_anchor
python "$study/run.py" /path/to/Valentine-datasets.zip /tmp/schema-paired.json
node --check "$study/score.mjs"
node "$study/score.mjs" /tmp/schema-paired.json > /tmp/schema-scores.json
cmp "$study/paired.json" /tmp/schema-paired.json
cmp "$study/scores.json" /tmp/schema-scores.json
```
