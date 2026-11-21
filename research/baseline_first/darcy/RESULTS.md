# Darcy development benchmark

The candidate coarse operator failed the reference check. Across 128 development fields the median relative residual of the supplied solution was 0.986, even after choosing the best output multiplier separately for every field by least squares. At that multiplier the median relative solution error against a sparse direct solve was 0.939. The source operator remains unresolved.

## Exploratory CPU measurements

The input is the [NeuralOperator 16×16 training archive](https://github.com/neuraloperator/neuraloperator/blob/main/neuralop/data/datasets/data/darcy_train_16.pt), SHA-256 `0be662acdb1dab7dfd1a1da0b140e97f75cc94f98a14edcf768abe6968b3b418`. For this experiment the Boolean mask selects permeability 12 or 3, with harmonic face averages, uniform unit forcing and zero Dirichlet ghost nodes. A linear ridge predictor uses direct solutions from training indices 0–511. Measurements use indices 512–639 of that same archive. All solves ran on the WSL CPU with one OpenBLAS thread.

| Method | Median setup + solve (ms) | Median iterations | Worst relative residual |
|---|---:|---:|---:|
| Ruge–Stüben AMG V-cycles | 3.153 | 9 | 9.48e-10 |
| CG with AMG | 2.924 | 6 | 1.00e-9 |
| Warm CG with AMG | 2.919 | 6 | 9.48e-10 |
| Warm + interface-node Jacobi | 2.895 | 6 | 9.29e-10 |
| Warm + interface-edge block Jacobi | 2.880 | 6 | 9.83e-10 |

Both corrections use one residual evaluation, the same jump mask and damping, and update the same nodes before CG. The edge method solves overlapping two-node blocks and averages their corrections, which costs extra arithmetic. Median shared assembly and AMG setup was 1.851 ms. Times include warm prediction and correction where applicable, exclude offline fitting, and use a single fixed method order per field. The 0.5% difference between corrected medians does not establish a speed advantage. Neither correction reduced the median iteration count.

The registered PDEBench/FNO and independent RPB evaluation remains unverified. The [DaRUS dataset](https://doi.org/10.18419/darus-2986) identifies a separate train file (133219). These measurements use only NeuralOperator training pairs and cannot establish the registered 20% gate. No independent RPB data was accessed.

## Reproduction

Download the linked archive as darcy_train_16.pt, verify its digest, then run in an environment with NumPy, SciPy, PyTorch and PyAMG:

```sh
python -c "import numpy as np, torch; np.savez('coef.npz', **torch.load('darcy_train_16.pt', weights_only=True))"
OPENBLAS_NUM_THREADS=1 python benchmark.py > runs.json
```

Each method entry in runs.json records total milliseconds, iterations and measured relative residual in that order.
