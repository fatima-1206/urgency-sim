"""Connectivity regions, Gilbert-Elliott burstiness, and the agent's
*discovered* map of coverage (it has no prior map).

Truth and belief are deliberately separate:
  - `ConnectivityTruth` knows where the regions really are.
  - `DiscoveredMap` is what the agent has worked out by moving around and
    by succeeding/failing at transmissions.
"""
from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np

from .config import Config, CommCfg


@dataclass
class Region:
    cx: float
    cy: float
    radius: float
    peak: float
    is_launch: bool = False

    def quality(self, x, y):
        """Geometric link quality in [0, peak]; Gaussian falloff.

        At d = radius the quality is exp(-2) = 13.5% of peak, so `radius` is
        the far tail rather than a coverage boundary. `r_half` below is the
        radius people actually mean when they look at a drawn circle.
        """
        d2 = (np.asarray(x) - self.cx) ** 2 + (np.asarray(y) - self.cy) ** 2
        sig = self.radius / 2.0
        return self.peak * np.exp(-0.5 * d2 / sig ** 2)

    def r_at(self, q: float) -> float:
        """Distance at which geometric quality falls to q (0 if never)."""
        if q >= self.peak:
            return 0.0
        return (self.radius / 2.0) * float(np.sqrt(2.0 * np.log(self.peak / q)))

    @property
    def r_half(self) -> float:
        """Radius of the delivery-probability = 0.5 contour."""
        return self.r_at(0.5)


def required_separation(cc: CommCfg) -> float:
    """Smallest centre-to-centre distance at which two regions can still be
    told apart by `DiscoveredMap`.

    Discovery marks cells whose quality exceeds `discover_threshold` and then
    groups them by connected components after a dilation of `cluster_dilate`
    cells. Two regions therefore merge into one phantom region unless their
    covered discs are separated by more than the dilation can bridge:

        sep > r_A(thr) + r_B(thr) + 2 * cluster_dilate

    evaluated at the WORST case (largest radius, highest peak), plus one cell
    of slack for the grid. This is what silently broke dense discovery in the
    pilot: it reported 0.96 regions where 4.00 existed.
    """
    worst = Region(0.0, 0.0, max(cc.radius_hi, cc.launch_radius),
                   max(cc.peak_hi, cc.launch_peak))
    return 2.0 * worst.r_at(cc.discover_threshold) + 2.0 * cc.cluster_dilate + 1.0


def validate_comm(cc: CommCfg) -> None:
    """Fail loudly at config load rather than quietly mis-counting regions."""
    need = required_separation(cc)
    if cc.min_separation < need:
        raise ValueError(
            f"min_separation={cc.min_separation:.1f} is too small for these "
            f"radii: regions with radius up to "
            f"{max(cc.radius_hi, cc.launch_radius):.1f} and peak up to "
            f"{max(cc.peak_hi, cc.launch_peak):.2f} stay connected at the "
            f"discovery threshold {cc.discover_threshold:.2f} after a "
            f"{cc.cluster_dilate}-cell dilation. Need >= {need:.1f}. "
            f"Either raise min_separation, shrink the radii, or raise "
            f"discover_threshold."
        )
    if cc.radius_lo > cc.radius_hi or cc.peak_lo > cc.peak_hi:
        raise ValueError("region radius/peak bounds are inverted")


def ge_mean_multiplier(cc: CommCfg) -> float:
    """Long-run mean of (1 - loss) under the Gilbert-Elliott chain."""
    pi_bad = cc.p_gb / (cc.p_gb + cc.p_bg)
    return (1 - pi_bad) * (1 - cc.loss_good) + pi_bad * (1 - cc.loss_bad)


class ConnectivityTruth:
    """Ground-truth coverage plus the Gilbert-Elliott channel state."""

    def __init__(self, cfg: Config, rng: np.random.Generator):
        cc = cfg.comm
        self.cc = cc
        n = cfg.fld.n
        sx, sy = cfg.agent.start_xy
        self.regions: List[Region] = [
            Region(float(sx), float(sy), cc.launch_radius, cc.launch_peak, True)
        ]
        k = int(rng.integers(cc.n_extra_lo, cc.n_extra_hi + 1))
        tries = 0
        while len(self.regions) < k + 1 and tries < 800:
            tries += 1
            cx, cy = rng.uniform(3, n - 3), rng.uniform(3, n - 3)
            # keep regions apart so discovery is a real task
            if min(np.hypot(cx - r.cx, cy - r.cy)
                   for r in self.regions) < cc.min_separation:
                continue
            self.regions.append(Region(
                cx, cy,
                float(rng.uniform(cc.radius_lo, cc.radius_hi)),
                float(rng.uniform(cc.peak_lo, cc.peak_hi)),
            ))
        self.state_bad = False   # Gilbert-Elliott state

    def quality(self, x, y):
        return max(r.quality(x, y) for r in self.regions)

    def quality_grid(self, n):
        gx, gy = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
        return np.max([r.quality(gx, gy) for r in self.regions], axis=0)

    def tick_channel(self, rng: np.random.Generator):
        cc = self.cc
        if self.state_bad:
            if rng.random() < cc.p_bg:
                self.state_bad = False
        else:
            if rng.random() < cc.p_gb:
                self.state_bad = True

    def attempt(self, x, y, rng: np.random.Generator) -> bool:
        """One transmission attempt from (x, y). ACKs are assumed reliable."""
        cc = self.cc
        loss = cc.loss_bad if self.state_bad else cc.loss_good
        p = self.quality(x, y) * (1.0 - loss)
        return bool(rng.random() < p)

    def measure_quality(self, x, y, rng: np.random.Generator) -> float:
        """What the agent's radio reports as signal quality at this cell.
        Noisy but does not require transmitting."""
        q = self.quality(x, y)
        return float(np.clip(q + rng.normal(0.0, 0.03), 0.0, 1.0))


@dataclass
class DiscoveredRegion:
    cx: float
    cy: float
    q_best: float
    n_cells: int = 1
    succ: float = 0.0
    fail: float = 0.0
    found_t: int = 0
    is_launch: bool = False

    def p_hat(self, prior_m: float = 3.0) -> float:
        """Per-attempt success estimate: Beta counts with a pseudo-count prior
        centred on the measured link quality."""
        return (self.succ + prior_m * self.q_best) / (
            self.succ + self.fail + prior_m)


class DiscoveredMap:
    """The agent's coverage knowledge, built from what it has measured.

    Cells whose measured link quality exceeds `discover_threshold` form a
    binary mask; that mask is dilated (to bridge separate passes through the
    same physical region) and then split into connected components. Each
    component is one discovered region. This replaces a nearest-centroid merge
    that shattered a single large region into many phantom ones.
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.cc = cfg.comm
        self.n = cfg.fld.n
        self.covered = np.zeros((self.n, self.n), dtype=bool)
        self.qgrid = np.zeros((self.n, self.n), dtype=float)
        self.quality_seen = {}
        self.attempts = {}            # (x, y) -> [succ, fail]
        self.first_seen = {}          # (x, y) -> tick
        sx, sy = cfg.agent.start_xy
        # the agent knows it launched from somewhere with a good link
        self.covered[sx, sy] = True
        self.qgrid[sx, sy] = cfg.comm.launch_peak
        self.first_seen[(sx, sy)] = 0
        self._start = (sx, sy)
        self.regions: List[DiscoveredRegion] = []
        self._dirty = True
        self._relabel(0)

    # -- observation -------------------------------------------------------
    def observe(self, x: int, y: int, q: float, t: int):
        self.quality_seen[(x, y)] = q
        self.qgrid[x, y] = max(self.qgrid[x, y], q)
        if q >= self.cc.discover_threshold and not self.covered[x, y]:
            self.covered[x, y] = True
            self.first_seen[(x, y)] = t
            self._dirty = True

    def record_attempt(self, region_idx, success: bool, xy=None):
        if xy is not None:
            rec = self.attempts.setdefault(tuple(xy), [0.0, 0.0])
            rec[0 if success else 1] += 1.0
            self._dirty = True
        if region_idx is not None and 0 <= region_idx < len(self.regions):
            r = self.regions[region_idx]
            if success:
                r.succ += 1.0
            else:
                r.fail += 1.0

    # -- clustering --------------------------------------------------------
    def _relabel(self, t: int):
        from scipy import ndimage
        d = self.cc.cluster_dilate
        if self.covered.sum() == 0:
            self.regions = []
            self._dirty = False
            return
        st = np.ones((2 * d + 1, 2 * d + 1), dtype=bool)
        grown = ndimage.binary_dilation(self.covered, structure=st)
        lab, nlab = ndimage.label(grown, structure=np.ones((3, 3), dtype=bool))
        regions = []
        sxy = self._start
        for i in range(1, nlab + 1):
            comp = (lab == i) & self.covered
            if not comp.any():
                continue
            xs, ys = np.nonzero(comp)
            w = self.qgrid[xs, ys]
            cx = float((xs * w).sum() / max(w.sum(), 1e-9))
            cy = float((ys * w).sum() / max(w.sum(), 1e-9))
            succ = fail = 0.0
            for (ax, ay), (sc, fl) in self.attempts.items():
                if comp[ax, ay]:
                    succ += sc; fail += fl
            ft = min((self.first_seen[(a, b)] for a, b in zip(xs, ys)
                      if (a, b) in self.first_seen), default=t)
            regions.append(DiscoveredRegion(
                cx, cy, float(self.qgrid[xs, ys].max()), int(comp.sum()),
                succ, fail, int(ft), bool(comp[sxy[0], sxy[1]])))
        self.regions = regions
        self._dirty = False

    def maybe_relabel(self, t: int):
        if self._dirty:
            self._relabel(t)

    # -- queries -----------------------------------------------------------
    def nearest(self, x, y):
        if not self.regions:
            return None
        return min(self.regions, key=lambda r: np.hypot(x - r.cx, y - r.cy))

    def region_at(self, x, y, tol=5.0):
        best, bi, bd = None, None, np.inf
        for i, r in enumerate(self.regions):
            d = np.hypot(x - r.cx, y - r.cy)
            if d < bd:
                best, bi, bd = r, i, d
        return bi if (best is not None and bd <= tol) else None

    def local_quality_estimate(self, x, y) -> float:
        """Estimated link quality where the agent stands."""
        x = int(np.clip(x, 0, self.n - 1)); y = int(np.clip(y, 0, self.n - 1))
        if (x, y) in self.quality_seen:
            return self.quality_seen[(x, y)]
        r = self.nearest(x, y)
        if r is None:
            return 0.0
        d = float(np.hypot(x - r.cx, y - r.cy))
        return float(r.q_best * np.exp(-0.5 * (d / 4.0) ** 2))


def coverage_fraction(cfg: Config, n_seeds: int = 200, thresh: float = 0.5):
    """Fraction of cells whose delivery probability exceeds `thresh`.

    Returns (geometric, effective, drawn):
      geometric  - max over regions of the geometric link quality
      effective  - geometric x the mean Gilbert-Elliott multiplier, i.e. the
                   actual expected per-attempt delivery probability
      drawn      - fraction inside the nominal `radius` circles, which is what
                   a plot of the regions appears to show
    """
    n = cfg.fld.n
    ge = ge_mean_multiplier(cfg.comm)
    gx, gy = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
    g, e, d = [], [], []
    for sd in range(n_seeds):
        t = ConnectivityTruth(cfg, np.random.default_rng(sd))
        q = t.quality_grid(n)
        g.append((q > thresh).mean())
        e.append((q * ge > thresh).mean())
        m = np.zeros_like(q, dtype=bool)
        for r in t.regions:
            m |= ((gx - r.cx) ** 2 + (gy - r.cy) ** 2) <= r.radius ** 2
        d.append(m.mean())
    return float(np.mean(g)), float(np.mean(e)), float(np.mean(d))
