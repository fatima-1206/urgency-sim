"""Calibrate (a) trigger thresholds to a matched alarm budget and
(b) the urgency->deadline mapping to the observed urgency spread.

    .venv/bin/python scripts/calibrate.py
"""
import dataclasses, pathlib, sys
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import numpy as np
from urgency_sim.config import Config, with_scenario, with_conn
from urgency_sim.connectivity import coverage_fraction
import urgency_sim.methods as mm
import urgency_sim.sim as ss
from urgency_sim.sim import run

SC = ["predictable", "unpredictable"]
CN = ["sparse", "dense"]
# Calibration seed count. NS=5 (20 runs/grid point) proved far too noisy:
# the triggers it picked were off budget by up to +24% when re-measured on the
# 60-seed evaluation block (surprise_abl 9.2 predicted vs 14.0 actual), which
# silently un-matched the alarm budget and invalidated the ablation contrast.
NS = 20


def _fires(a):
    cfg, sd, mk, trig = a
    if trig is not None:
        M = dataclasses.replace(mm.METHODS[mk], trigger_level=trig)
        mm.METHODS[mk] = M; ss.METHODS[mk] = M
    log = run(cfg, sd, mk)
    return len(log.fires), [u for (_t, _x, _y, u, _d) in log.fires]


def budget(mk, trig=None, cfg=None, seeds=NS):
    base = cfg or Config()
    jobs = [(with_conn(with_scenario(base, s), c), sd, mk, trig)
            for s in SC for c in CN for sd in range(seeds)]
    with ProcessPoolExecutor(max_workers=12) as ex:
        res = list(ex.map(_fires, jobs))
    return float(np.mean([r[0] for r in res])), [u for r in res for u in r[1]]


if __name__ == "__main__":
    print("=== connectivity coverage (fraction of cells, delivery prob > 0.5) ===")
    print(f"{'conn':8s} {'geometric':>10s} {'effective':>10s} {'drawn circles':>14s}")
    for c in CN:
        g, e, d = coverage_fraction(with_conn(Config(), c), 150)
        print(f"{c:8s} {g*100:9.1f}% {e*100:9.1f}% {d*100:13.1f}%")

    print("\n=== reference alarm budget: threshold baseline ===")
    for tl in [0.0, 0.2, 0.4, 0.8]:
        f, _ = budget("threshold", tl)
        print(f"  threshold trigger {tl:4.2f} -> {f:6.1f} fires/run")
    ref, _ = budget("threshold", 0.0)
    print(f"  reference budget (threshold, trigger 0.0) = {ref:.1f} fires/run")

    print("\n=== trigger scan (target: match the threshold baseline) ===")
    # Grids must BRACKET the reference budget on both sides, or the "closest"
    # pick is just the grid edge and the budgets end up unmatched -- which is
    # what made an earlier pilot run look far better than it was.
    # The proposed score has a steep cliff between 2.0 and 2.5 fires/run
    # (14.2 -> 7.9), so it needs a finer grid there than the others.
    grids = {"proposed": [1.8, 2.0, 2.2, 2.4, 2.6, 2.8],
             "surprise_abl": [1.6, 1.9, 2.2, 2.5, 2.8, 3.2],
             "raw_abl": [0.25, 0.35, 0.45, 0.55, 0.7, 0.9],
             "time_urg": [1.0, 1.5, 2.0, 2.5, 3.0]}
    best = {}
    for mk, grid in grids.items():
        print(f"  {mk}:")
        rows = []
        for tr in grid:
            f, _ = budget(mk, tr)
            rows.append((tr, f))
            print(f"     trigger {tr:5.2f} -> {f:6.1f} fires/run")
        tr = min(rows, key=lambda r: abs(r[1] - ref))[0]
        best[mk] = tr
        f = dict(rows)[tr]
        off = abs(f - ref) > 0.15 * ref
        print(f"     --> closest to {ref:.1f}: trigger = {tr} ({f:.1f} fires)"
              + ("   *** {:.0f}% OFF BUDGET -- refine the grid; an unmatched "
                 "budget inflates BOTH detection and false alarms "
                 "***".format(100 * (f - ref) / ref) if off else ""))
    print("\n  calibrated triggers:", best)

    print("\n=== urgency distribution at fire time (proposed, calibrated) ===")
    _, us = budget("proposed", best["proposed"])
    us = np.array(us)
    if us.size:
        qs = np.percentile(us, [5, 10, 25, 50, 75, 90, 95, 99])
        print("   p5 p10 p25 p50 p75 p90 p95 p99 = " +
              " ".join(f"{v:.2f}" for v in qs))
        print(f"   --> set urgency_lo = p10 = {qs[1]:.2f}, "
              f"urgency_hi = p90 = {qs[5]:.2f}   (linear map)")
        # F3: percentile map table -- 11 quantiles at p0, p10, ... p100.
        tab = np.percentile(us, np.linspace(0, 100, 11))
        print("   --> set urgency_q = (" +
              ", ".join(f"{v:.3f}" for v in tab) + ")")
