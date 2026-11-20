"""Stage A smoke test: is the field stable and does the plume actually move?"""
import sys, pathlib, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from urgency_sim.config import Config, with_scenario
from urgency_sim.field import PollutantField, rollout_field, cfl_limit

cfg = Config()
print("CFL limit (initial wind):", round(cfl_limit(cfg.fld, cfg.fld.wind), 3),
      " dt =", cfg.fld.dt)
print("CFL limit (shifted wind):", round(cfl_limit(cfg.fld, cfg.fld.wind_after), 3))

TICKS = cfg.agent.mission_ticks
fig, axes = plt.subplots(2, 5, figsize=(17, 7))
for r, scen in enumerate(["predictable", "unpredictable"]):
    c = with_scenario(cfg, scen)
    t0 = time.perf_counter()
    hist = rollout_field(c, TICKS)
    el = time.perf_counter() - t0
    print(f"{scen:14s} {TICKS} ticks in {el*1000:7.1f} ms "
          f"({el/TICKS*1e6:5.1f} us/tick)  max={hist.max():.3f} "
          f"finite={np.isfinite(hist).all()}")
    for k, t in enumerate([0, 100, 200, 300, 400]):
        ax = axes[r, k]
        ax.imshow(hist[t].T, origin="lower", cmap="inferno",
                  vmin=0, vmax=float(hist.max()))
        ax.set_title(f"{scen[:5]} t={t}", fontsize=9)
        ax.set_xticks([]); ax.set_yticks([])
        # centre of mass, to show the plume really translates
        m = hist[t].astype(float); s = m.sum()
        if s > 1e-9:
            xs, ys = np.indices(m.shape)
            ax.plot((xs*m).sum()/s, (ys*m).sum()/s, "c+", ms=10)
plt.tight_layout(); plt.savefig("figs/check2_field_sanity.png", dpi=110)
print("wrote figs/check2_field_sanity.png")

# centre-of-mass drift table
for scen in ["predictable", "unpredictable"]:
    hist = rollout_field(with_scenario(cfg, scen), TICKS)
    print(f"\n{scen}: centre of mass")
    for t in [0, 100, 200, 300, 400]:
        m = hist[t].astype(float); s = m.sum()
        xs, ys = np.indices(m.shape)
        print(f"   t={t:3d}  com=({(xs*m).sum()/s:5.2f},{(ys*m).sum()/s:5.2f})"
              f"  mass={s:8.1f}  max={m.max():.3f}")
