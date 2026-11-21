# Generate and score the independent development cohort

The official PhysicsNeMo Darcy2D implementation draws uniform random Fourier coefficients, thresholds the resulting field and solves for pressure using multigrid red-black successive over-relaxation. Its FNO example consumes these generated tensors in situ. The generator reads zero stored training fields. This replay uses the public generative software release. Its generated cohort consists of new synthetic development examples. [Official generator](https://github.com/NVIDIA/physicsnemo/blob/5af5afd818bf2f120b61fbf4ad920759bfdc8372/physicsnemo/datapipes/benchmarks/darcy.py) · [Discrete pressure operator](https://github.com/NVIDIA/physicsnemo/blob/5af5afd818bf2f120b61fbf4ad920759bfdc8372/physicsnemo/datapipes/benchmarks/kernels/finite_difference.py) · [NVIDIA benchmark recipe](https://github.com/NVIDIA/physicsnemo/blob/5af5afd818bf2f120b61fbf4ad920759bfdc8372/examples/cfd/darcy_fno/train_fno_darcy.py)

The run used Linux, Python 3.12.3, NumPy 2.4.4, scikit-learn 1.8.0, Torch 2.7.1+cu118 and Warp 1.19.0. From this directory, run the commands below. The wrapper loads the upstream numerical modules directly, bypassing registration of unrelated ML models. The 16 workers partition the serial seed stream in contiguous five-batch pieces. The original batch size of eight determines the random Fourier coefficient indexing. The replay uses no GPU.

```bash
git clone https://github.com/NVIDIA/physicsnemo.git /tmp/nvidia-physicsnemo
git -C /tmp/nvidia-physicsnemo checkout 5af5afd818bf2f120b61fbf4ad920759bfdc8372
python -m pip install warp-lang==1.19.0
OMP_NUM_THREADS=1 python generate.py /tmp/nvidia-physicsnemo /tmp/darcy-independent
python audit.py /tmp/darcy-independent/fields.npz
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python evaluate.py /tmp/darcy-independent /tmp/darcy-independent-scores
node --check verify.mjs
node verify.mjs
```

The compressed archive contains two arrays with axes (field, row, column). Material is uint8 with 0 for permeability 0.5 and 1 for permeability 2. Pressure is the native unnormalized float32 output. Array SHA-256 digests use C order before compression. The interior residual audit evaluates the upstream stencil in float64 at the 30×30 nodes whose neighbors survive the upstream output crop. It checks labels independently of interpolation error.
