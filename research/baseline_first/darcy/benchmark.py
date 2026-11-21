"""Run with OPENBLAS_NUM_THREADS=1 and the converted training archive."""
import json
from time import perf_counter

import numpy as np
import pyamg
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import cg, spsolve


def assemble(bits):
    # Exploratory unit square, 16 interior nodes per axis, zero ghost values.
    a = np.where(bits, 12., 3.).ravel()
    grid = np.arange(a.size).reshape(bits.shape)
    i = np.r_[grid[:-1].ravel(), grid[:, :-1].ravel()]
    j = np.r_[grid[1:].ravel(), grid[:, 1:].ravel()]
    face = 2 * a[i] * a[j] / (a[i] + a[j])
    diag = np.bincount(i, face, minlength=a.size) + np.bincount(j, face)
    for edge in (grid[0], grid[-1], grid[:, 0], grid[:, -1]):
        diag[edge] += a[edge]
    matrix = coo_matrix((np.r_[diag, -face, -face],
                         (np.r_[grid.ravel(), i, j], np.r_[grid.ravel(), j, i]))).tocsr()
    different = a[i] != a[j]
    return matrix, i[different], j[different], face[different]


data = np.load("coef.npz")
x = data["x"].reshape(-1, 256).astype(float)
features = np.column_stack([np.ones(len(x)), x])
b = np.ones(256) / 17**2
# Linear warm-start control trained on exact exploratory solutions.
targets = [spsolve(assemble(bits)[0], b) for bits in data["x"][:512]]
f = features[:512]
weights = np.linalg.solve(f.T @ f + np.eye(257), f.T @ targets)
rows = []
for n in range(512, 640):
    t = perf_counter()
    A, i, j, faces = assemble(data["x"][n])
    hierarchy = pyamg.ruge_stuben_solver(A)
    M = hierarchy.aspreconditioner()
    setup = perf_counter() - t
    oracle = spsolve(A, b)
    ref = data["y"][n].ravel()
    # Allow an oracle scalar per sample to absorb arbitrary output units.
    ar = A @ ref
    scale = (ar @ b) / (ar @ ar)
    row = dict(index=n, setup_ms=1000*setup,
               reference_residual=np.linalg.norm(scale*ar-b)/np.linalg.norm(b),
               reference_error=np.linalg.norm(scale*ref-oracle)/np.linalg.norm(oracle))
    nodes = np.unique(np.r_[i, j])
    for method in ("amg", "cg", "warm", "jacobi", "interface"):
        t = perf_counter()
        guess = np.zeros_like(b) if method in ("cg", "amg") else features[n] @ weights
        if method in ("jacobi", "interface"):
            residual = b - A @ guess
            diagonal = A.diagonal()
            if method == "jacobi":
                guess[nodes] += (2/3)*residual[nodes]/diagonal[nodes]
            else:
                # Additive two-node block Jacobi along coefficient jumps.
                det = diagonal[i]*diagonal[j] - faces**2
                step_i = (diagonal[j]*residual[i]+faces*residual[j])/det
                step_j = (diagonal[i]*residual[j]+faces*residual[i])/det
                step = np.bincount(np.r_[i,j], np.r_[step_i,step_j], minlength=256)
                degree = np.bincount(np.r_[i,j], minlength=256)
                guess[nodes] += (2/3)*step[nodes]/degree[nodes]
        history = []
        if method == "amg":
            sol = hierarchy.solve(b, x0=guess, tol=1e-9, residuals=history)
            count = len(history)-1
        else:
            sol, info = cg(A, b, x0=guess, M=M, rtol=1e-9, callback=lambda _: history.append(1))
            assert info == 0
            count = len(history)
        elapsed = perf_counter()-t
        row[method] = [1000*(setup+elapsed), count, np.linalg.norm(A@sol-b)/np.linalg.norm(b)]
    rows.append(row)
print(json.dumps(rows, indent=1))
