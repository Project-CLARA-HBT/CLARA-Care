# Bearing development screen

Before scoring, select bearing section 00, both domains, all development test clips and the first 32 sorted source and all target training clips. Use normalized log spectral band means and standard deviations. Compare nearest neighbor, nearest centroid, pooled diagonal variance and count-dependent diagonal variance shrinkage in four training clusters. Stop at a matched control within three standardized pAUC points or insufficient machine replication. This single-machine screen cannot establish cross-machine improvement.

[Development audio and license](https://doi.org/10.5281/zenodo.10902294) · [Official evaluator](https://github.com/nttcslab/dcase2024_task2_evaluator)

Run on CPU with Python 3.11+, NumPy, SciPy and scikit-learn.

```sh
curl -fL --retry 3 https://zenodo.org/api/records/10902294/files/dev_bearing.zip/content -o dev_bearing.zip
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python screen.py > results.json
```

All methods share the same training-only standardization. Cluster models share a seeded four-centroid fit. The proposed estimator adds ten pooled pseudo-observations to each cluster variance. Its controls use local-only, pooled-only or equal local/pooled weight, with the same variance floor. The harmonic score combines source AUC, target AUC and pooled standardized pAUC for this development section.

## Decision

Stop at the matched-control gate. On 200 clips, count-dependent shrinkage gained 4.05 pAUC points over unstable local variances and 2.05 over fixed blending. It lost 0.68 to pooled variance, 3.47 to nearest neighbor and 4.53 to nearest centroid. Against centroid, the paired 95% percentile interval was −8.00 to −1.26 points. Even the upper endpoint falls below the required +3. Results apply to this training sample, encoder and machine. Clip resampling conditions on the fitted model and does not measure variation between machines, recording sessions or training sets. Strong pretrained and challenge systems were outside this stopped screen. See results.json for every method and comparison.
