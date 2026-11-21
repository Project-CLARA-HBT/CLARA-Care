# A compressed exact projection eliminates this cardinality estimator

**Retire the candidate on this development workload.** Sorting six categorical attributes and compressing the full 32,561-row projection used 15,361 of the permitted 32,768 bytes. Counting over its decoded rows agreed exactly with the independent full-table counts on all 1,200 generated queries. Compressed sampling also retained every row. The unsmoothed tree was stronger than the hybrid even without the exact option.

| Method | Mean absolute log error | Joint predicates | Independently drawn predicates |
|---|---:|---:|---:|
| Independent marginals | 1.07638 | 0.75279 | 1.39997 |
| Maximum-information tree | 0.19056 | 0.20126 | 0.17986 |
| Uniform uncompressed sample | 0.20327 | 0.20164 | 0.20490 |
| Compressed uniform sample | 0 | 0 | 0 |
| Independence prior, strength four | 0.21699 | 0.20191 | 0.23207 |
| Tree prior, strength four | 0.22473 | 0.22051 | 0.22895 |
| Tree prior, strength 32 | 0.22234 | 0.21821 | 0.22648 |
| Adaptive tree prior | 0.22312 | 0.21905 | 0.22720 |
| Exact compressed projection | 0 | 0 | 0 |

The 4,762-byte tree left room for 4,667 uncompressed sample rows. Adding an estimated tree probability weighted by 32 equivalent rows at most had little influence at this sampling fraction. The separately evaluated fixed-strength ablation also beat adaptive weighting. Five seeds reused the same 600 queries per workload. No latency comparison or general performance claim follows from this size-limited, low-cardinality projection.

**Prior art.** BayesCard uses Bayesian networks for cardinality estimation. The comparator here is a direct maximum-mutual-information tree for a single table with exact sum-product marginalization, rather than the deployed BayesCard system. Naru learns an autoregressive density model and estimates query probability by progressive sampling. Neither full system was measured. Both papers place data-driven modeling and resolving correlated predicates firmly in prior work. A zero-error affordable comparator makes an accuracy win impossible on this specific workload. [BayesCard](https://arxiv.org/abs/2012.14743) · [Naru](https://arxiv.org/abs/1905.04278)

**Source and endpoint.** Kohavi and Becker's UCI Adult table is released under CC BY 4.0. The query workload is a derived experiment generated from the published external split. Each predicate selects three to five of the six fixed columns. Ground truth is a count in adult.data, including the explicit missing-value category. The paper-sized question is a systems one about serialized estimator size. Human records, predicate literals and classifications are excluded from the published artifacts. [Dataset and license](https://archive.ics.uci.edu/dataset/2/adult) · [Frozen protocol](PROTOCOL.md)

**Replay.** Run the commands from this directory. The executed Python and NumPy versions, summary sizes and sample counts are in the manifest. The numerical experiment ran on WSL2 on the RTX 4060 Ti host, using one CPU computation thread. The independent JavaScript scorer checks every query/seed unit, storage budgets and strata. A second WSL run decoded the exact synopsis independently and reproduced the original predictions and manifest byte for byte.

```sh
curl -fLsS https://archive.ics.uci.edu/static/public/2/adult.zip -o /tmp/adult-cardinality.zip
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python run.py /tmp/adult-cardinality.zip /tmp/cardinality-output
node --check score.mjs
node score.mjs /tmp/cardinality-output/predictions.csv /tmp/cardinality-output/manifest.json > /tmp/cardinality-output/summary.json
diff -ru results1 /tmp/cardinality-output
```

[Paired predictions](results1/predictions.csv) · [All strata](results1/summary.json) · [Executed environment](results1/manifest.json)
