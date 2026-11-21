# Does residual learning help reconstruct equipment temperature during an outage?

This development experiment isolates a change to the regression target. Two forests receive the same covariates, temperature anchors, tree count and seed. The direct model predicts the hidden temperature. The residual model adds a learned correction to the line between the two anchors. Each deployment would need a *future* temperature observation to reconstruct the missing segment.

The first 72 weeks of each station train its own pair of models. At each station the scoring window contributes 29 paired weeks and three separately applied masks per week. The stations share the calendar and gap masks. The 174 scored station-week-duration combinations are paired experimental cases. Inference resamples weeks in blocks, jointly across stations, rather than treating the temperatures or methods as independent replicates. Each source contains 17,420 consecutive hours across all seven finite measurement columns. Both the training and evaluation data come from upstream preprocessed hourly series. Missingness here consists entirely of newly masked, previously observed temperatures. Each station has its own trained models, so this design estimates temporal transfer within a station; transfer to a new station is unmeasured. [Frozen protocol and data fingerprints](PROTOCOL.md) · [ETDataset source and attribution](https://github.com/zhouhaoyi/ETDataset/tree/1d16c8f4f943005d613b5bc962e9eeb06058cf07)

## Relationship to published imputation methods

BRITS already learns temporal and cross-feature estimates with bidirectional recurrent processing. GRIN uses graph message passing to reconstruct missing measurements from spatial and temporal dependencies. SAITS learns a reconstruction using attention over observed values and masks. The presence of a second endpoint, multivariate loads and a masked benchmark therefore supplies no broad claim to novelty. The estimand here is narrower: how much does changing the response from temperature to deviation from a linear bridge change error when the features and forest are held fixed? A comparison to any of those full models would require a matched external run. [BRITS, NeurIPS 2018](https://proceedings.neurips.cc/paper/2018/hash/734e6bfcd358e25ac1db0a4241b95651-Abstract.html) · [GRIN, ICLR 2022](https://openreview.net/forum?id=kOu3-S3wJ7) · [SAITS source](https://github.com/WenjieDu/SAITS)

## Replay

From the repository root, using Python 3.12 and the pinned packages:

```sh
python -m pip install -r evaluation/sensor_gap/requirements.txt
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python evaluation/sensor_gap/run.py --cache /tmp/ett-hourly --out /tmp/ett-replay
node evaluation/sensor_gap/verify.mjs /tmp/ett-hourly /tmp/ett-replay/losses.csv
diff -ru evaluation/sensor_gap/results /tmp/ett-replay
```

The runner downloads the two upstream CSV files if missing and checks their SHA-256 fingerprints before fitting. The independent checker verifies every interpolation control against the original measurements, the pairing across all four methods, and the case accounting. The Python runner also computes the predeclared week-block percentile intervals. [Every scored outage](results/losses.csv) · [Primary endpoint, all six cells and uncertainty](results/comparison.md)

## Second development comparison

Accounting for daily shape and preserving the two observed endpoints reduced the macro MAE to 1.4157, compared with 2.1018 for linear interpolation and 2.0017 for the residual forest. A training-only daily profile achieved 1.4258. The improvement over that inexpensive comparator was 0.71% with a paired 95% interval of −0.1227 to 0.1500 in temperature units. The local six-day profile without attenuation also missed the 5% superiority margin. The same 174 outages were used to diagnose the first approach and to evaluate this change. The proposed reliability weighting fails the all-baseline requirement. Classical seasonal adjustment before interpolation is already a published method. [imputeTS](https://journal.r-project.org/articles/RJ-2017-009/) · [Protocol](bridge-protocol.md) · [Every comparison](periodic_results/comparison.csv)

Run the following in the repository root with an unused temporary output path. Each masked target is set to NaN before the candidate receives the series.

```sh
python -m evaluation.sensor_gap.periodic_bridge /tmp/ett-hourly evaluation/sensor_gap/results/losses.csv /tmp/periodic-losses.csv
```

## Conditional regression on the adjacent hours

Reading a full day on either side of the missing segment reduced the error further. On the same two records the prespecified high/low-volatility regressors reached macro MAE 1.2415. A single pooled ridge using the identical features scored 1.2361, and soft routing scored 1.2420. The hard split lost to the pooled estimator by 0.44% and the paired interval for the absolute improvement includes zero. Retire the volatility-routing claim. These results quantify the benefit of the adjacent hours on already inspected development outages. Sensor-disjoint transfer, measured natural outages and matched published imputation systems remain untested. [Frozen design](conditional-protocol.md) · [All paired comparisons](conditional_results/comparison.csv)

```sh
OPENBLAS_NUM_THREADS=1 python -m evaluation.sensor_gap.conditional /tmp/ett-hourly evaluation/sensor_gap/periodic_results/losses.csv /tmp/conditional-losses.csv
```
