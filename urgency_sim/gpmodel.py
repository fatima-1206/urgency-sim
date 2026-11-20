"""GP over (x, y, t) with frozen hyperparameters.

Hyperparameters are learned exactly once, by sklearn, within deliberately tight
physically-motivated bounds. After that the model is a plain Cholesky solve done
directly in numpy/scipy:

  * sklearn's per-call input validation and kernel dispatch were ~30% of total
    simulation runtime and buy nothing once the kernel is fixed;
  * the posterior variance needs a triangular solve with one right-hand side per
    query point, which is the dominant cost -- and most callers want only the
    mean (the cloud-belief lattice) or only the std (the exploration target).
    `want=` lets each caller pay for only what it uses.

The maths is identical to sklearn's with normalize_y=False; `selftest()` checks
that against a live GaussianProcessRegressor.
"""
import warnings

import numpy as np
from scipy.linalg import cho_solve, cholesky, solve_triangular
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel

from .config import GPCfg

JITTER = 1e-8          # matches the alpha sklearn is constructed with


class FieldGP:
    def __init__(self, cfg: GPCfg, name: str = "gp"):
        self.cfg = cfg
        self.name = name
        self.X: list = []
        self.y: list = []
        self._fitted_n = -1
        self._hyper_locked = False
        self._kernel = (ConstantKernel(cfg.amplitude, (1e-3, 1e1))
                        * RBF(list(cfg.length_scale),
                              [(4.0, 20.0), (4.0, 20.0), (20.0, 150.0)])
                        + WhiteKernel(cfg.noise, (1e-4, 5e-3)))
        # frozen-kernel state
        self._amp = float(cfg.amplitude)
        self._ls = np.asarray(cfg.length_scale, dtype=float)
        self._noise = float(cfg.noise)
        self._Xtr = None
        self._L = None
        self._alpha = None
        self.n_refits = 0
        self.fit_seconds = 0.0

    # -- data --------------------------------------------------------------
    def add(self, x, y, t, z):
        self.X.append((float(x), float(y), float(t)))
        self.y.append(float(z))

    @property
    def n(self):
        return len(self.y)

    def _window(self):
        w = self.cfg.window
        if len(self.y) <= w:
            return np.asarray(self.X), np.asarray(self.y)
        recent = slice(len(self.y) - w + w // 4, len(self.y))
        old_idx = np.linspace(0, len(self.y) - w + w // 4 - 1, w // 4).astype(int)
        Xa, ya = np.asarray(self.X), np.asarray(self.y)
        return (np.vstack([Xa[old_idx], Xa[recent]]),
                np.concatenate([ya[old_idx], ya[recent]]))

    # -- kernel ------------------------------------------------------------
    def _k(self, A, B):
        """Signal part of the kernel. WhiteKernel contributes only on the
        diagonal of the training matrix, never to cross-covariances."""
        A = np.asarray(A, dtype=float) / self._ls
        B = np.asarray(B, dtype=float) / self._ls
        d2 = (np.einsum("ij,ij->i", A, A)[:, None]
              + np.einsum("ij,ij->i", B, B)[None, :]
              - 2.0 * (A @ B.T))
        return self._amp * np.exp(-0.5 * np.maximum(d2, 0.0))

    def _freeze_from(self, kernel):
        k1, k2 = kernel.k1, kernel.k2            # (Constant * RBF), White
        self._amp = float(k1.k1.constant_value)
        ls = np.atleast_1d(np.asarray(k1.k2.length_scale, dtype=float))
        self._ls = np.resize(ls, 3) if ls.size != 3 else ls
        self._noise = float(k2.noise_level)

    # -- fitting -----------------------------------------------------------
    def maybe_refit(self, t: int, force: bool = False):
        import time
        c = self.cfg
        if self.n == 0:
            return
        due = force or (self._fitted_n < 0) or (t % c.refit_every == 0)
        if not due:
            return
        X, Y = self._window()
        t0 = time.perf_counter()
        if not self._hyper_locked and self.n >= c.init_fit_at:
            gp = GaussianProcessRegressor(kernel=self._kernel, normalize_y=False,
                                          n_restarts_optimizer=0, alpha=JITTER)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                gp.fit(X, Y)
            self._kernel = gp.kernel_
            self._freeze_from(gp.kernel_)
            self._hyper_locked = True
        # frozen-kernel Cholesky, done directly
        K = self._k(X, X)
        K[np.diag_indices_from(K)] += self._noise + JITTER
        try:
            L = cholesky(K, lower=True)
        except np.linalg.LinAlgError:
            K[np.diag_indices_from(K)] += 1e-6
            L = cholesky(K, lower=True)
        self._Xtr, self._L = X, L
        self._alpha = cho_solve((L, True), Y)
        self.fit_seconds += time.perf_counter() - t0
        self._fitted_n = self.n
        self.n_refits += 1

    # -- prediction --------------------------------------------------------
    def predict(self, Q, return_std=True, want=None):
        """want: 'mean' | 'std' | 'both' (default follows return_std).

        Returns (mu, sd) for 'both', mu for 'mean', sd for 'std'.
        Skipping the variance avoids a triangular solve with one right-hand
        side per query point, which is the dominant cost.
        """
        want = want or ("both" if return_std else "mean")
        Q = np.atleast_2d(np.asarray(Q, dtype=float))
        if self._L is None:                      # prior
            mu = np.zeros(len(Q))
            sd = np.full(len(Q), float(np.sqrt(self._amp + self._noise)))
            return (mu, sd) if want == "both" else (mu if want == "mean" else sd)
        Ks = self._k(Q, self._Xtr)               # (m, n)
        if want != "std":
            mu = Ks @ self._alpha
            if want == "mean":
                return mu
        else:
            mu = None
        V = solve_triangular(self._L, Ks.T, lower=True)
        var = (self._amp + self._noise) - np.einsum("ij,ij->j", V, V)
        sd = np.sqrt(np.maximum(var, 1e-6))
        return sd if want == "std" else (mu, sd)

    def predict_grid(self, n, t, stride=1, want="both"):
        """Posterior on a (possibly subsampled) grid, returned at full n x n
        resolution by nearest-neighbour upsampling."""
        ax = np.arange(0, n, stride)
        gx, gy = np.meshgrid(ax, ax, indexing="ij")
        Q = np.column_stack([gx.ravel(), gy.ravel(), np.full(gx.size, float(t))])
        out = self.predict(Q, want=want)
        idx = np.clip(np.arange(n) // stride, 0, len(ax) - 1) if stride != 1 else None

        def _up(a):
            a = a.reshape(gx.shape)
            return a if idx is None else a[np.ix_(idx, idx)]

        if want == "both":
            return _up(out[0]), _up(out[1])
        return _up(out)


def selftest(seed=0, n=120, m=60, tol=1e-8):
    """Check the direct path reproduces sklearn to numerical precision."""
    rng = np.random.default_rng(seed)
    cfg = GPCfg()
    gp = FieldGP(cfg)
    for i in range(n):
        gp.add(rng.uniform(0, 30), rng.uniform(0, 30), i, rng.normal(0, 0.3))
    gp.maybe_refit(0, force=True)
    Q = np.column_stack([rng.uniform(0, 30, m), rng.uniform(0, 30, m),
                         np.full(m, float(n))])
    mu, sd = gp.predict(Q)
    ref = GaussianProcessRegressor(kernel=gp._kernel, optimizer=None,
                                   normalize_y=False, alpha=JITTER)
    X, Y = gp._window()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ref.fit(X, Y)
        rmu, rsd = ref.predict(Q, return_std=True)
    dmu, dsd = np.abs(mu - rmu).max(), np.abs(sd - rsd).max()
    assert np.allclose(mu, gp.predict(Q, want="mean")), "mean-only path differs"
    assert np.allclose(sd, gp.predict(Q, want="std")), "std-only path differs"
    ok = dmu < tol and dsd < tol
    return ok, float(dmu), float(dsd)
