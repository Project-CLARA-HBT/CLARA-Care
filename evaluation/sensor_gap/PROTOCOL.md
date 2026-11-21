# Transformer oil-temperature gap reconstruction

This external development experiment asks whether learning a correction to linear interpolation improves retrospective reconstruction of a single missing sensor channel. Both flanking temperatures and all six load channels are observable. Evaluation is fully automatic and uses equipment measurements. Artificial contiguous gaps represent a temperature sensor outage while load measurements continue.

## Data and partition

Use [ETDataset hourly transformer records](https://github.com/zhouhaoyi/ETDataset/tree/1d16c8f4f943005d613b5bc962e9eeb06058cf07/ETT-small), ETTh1 and ETTh2, with a separate fit per record. Verify the raw bytes by SHA-256.

| File | SHA-256 |
| --- | --- |
| ETTh1.csv | f18de3ad269cef59bb07b5438d79bb3042d3be49bdeecf01c1cd6d29695ee066 |
| ETTh2.csv | a3dc2c597b9218c7ce1cd55eb77b283fd459a1d09d753063f944967dd6b9218b |

Use the first 72 complete weeks for training and the remaining complete weeks for scoring. Discard trailing partial weeks. Within each partition reserve the first and last week for observed context. No cross-partition features. Each mask is a separate outage applied to an otherwise observed record.

## Fixed comparison

Use lengths 6, 24 and 72 hours. For training, start one example at a uniformly chosen hour per eligible day and length. For scoring, choose one start per eligible week and length uniformly among starts that keep the gap in that week. Seed NumPy's default generator with 20261121 plus the length, adding 1000 for scoring. Use identical start indices on both records. Pool training lengths within each record.

1. Linear interpolation between the last and next observed temperatures.
2. Seasonal interpolation between the same hour before and after the gap, offset by the gap length rounded up to a whole day (equal weights).
3. Direct multivariate Extra Trees regression on the six current loads, their preceding 6-hour averages (including current), hour-of-day sine and cosine, both temperature endpoints, fractional gap position, gap length, linear and seasonal estimates.
4. Candidate uses identical features and forest settings, learning the signed residual from linear interpolation. Add its prediction back to the line.

Fix 96 trees, minimum leaf size 5, all features, single worker and seed 42. No tuning or test-time model selection. Record MAE and squared-error sums for every outage and method. Report MAE in source temperature units by record and duration. Primary loss is the unweighted mean of the six cell MAEs. Report every comparison including regressions. Call the candidate superior only if its primary loss is at least 5% below each baseline and every paired 95% interval for the primary MAE reduction excludes zero on the positive side. Otherwise retain the baseline comparison as inconclusive for superiority.

For uncertainty, jointly resample the ordered evaluation weeks across both records and all lengths using circular contiguous blocks of four weeks, truncating each sample to the observed week count. Use 10,000 replicates and seed 712. Use percentile intervals without multiplicity adjustment. Intervals describe variation over weeks conditional on these records and masks. This is a development comparison with two records, a single target and simulated gaps.
