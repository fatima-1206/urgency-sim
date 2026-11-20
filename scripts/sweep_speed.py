"""Speed sweep: does the proposed method underperform because the plume
outruns the agent, making GP predictions stale and surprise uninformative?

Sweeps |wind| / agent_speed, re-running the matched-alarm-budget calibration
at every point, on a FRESH seed block (1000+) disjoint from the main study.

    .venv/bin/python scripts/sweep_speed.py              # 30 seeds (~10 min)
    .venv/bin/python scripts/sweep_speed.py --seeds 10   # quick
"""
import argparse, dataclasses, json, pathlib, sys, time
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import wilcoxon

from urgency_sim.config import Config, with_scenario, with_conn, with_speed
from urgency_sim.events import extract_events
from urgency_sim.field import rollout_field, cfl_limit, PollutantField
from urgency_sim.metrics import summarise
import urgency_sim.methods as mm
import urgency_sim.sim as ss
from urgency_sim.sim import run, jitter_config

OUT = pathlib.Path("figs"); OUT.mkdir(exist_ok=True)
RES = pathlib.Path("results"); RES.mkdir(exist_ok=True)

RATIOS = [0.1, 0.25, 0.5, 0.75, 1.0, 1.5]
METHODS = ["proposed", "threshold", "fixed_dl", "raw_abl"]
SCEN = ["predictable", "unpredictable"]
CONN = ["sparse", "dense"]
SEED0 = 1000              # fresh block, disjoint from the main study's 0-199
CAL_SEEDS = 4
WORKERS = 10
GRIDS = {"proposed": [0.6, 1.0, 1.6, 2.4, 3.6, 5.4],
         "raw_abl":  [0.15, 0.25, 0.40, 0.65, 1.00, 1.60]}


def _fires(a):
    cfg, sd, mk, trig = a
    if trig is not None:
        M = dataclasses.replace(mm.METHODS[mk], trigger_level=trig)
        mm.METHODS[mk] = M; ss.METHODS[mk] = M
    log = run(cfg, sd, mk)
    return len(log.fires), [u for (_t, _x, _y, u, _d) in log.fires]


def _summary(a):
    cfg, sd, mk, trig = a
    if trig is not None:
        M = dataclasses.replace(mm.METHODS[mk], trigger_level=trig)
        mm.METHODS[mk] = M; ss.METHODS[mk] = M
    s = summarise(run(cfg, sd, mk))
    s["trigger"] = trig
    return s


def _cells(cfg, nseeds, seed0=SEED0):
    return [(with_conn(with_scenario(cfg, s), c), seed0 + i)
            for s in SCEN for c in CONN for i in range(nseeds)]


def rate(ex, cfg, mk, trig, nseeds=CAL_SEEDS):
    jobs = [(c, sd, mk, trig) for (c, sd) in _cells(cfg, nseeds)]
    res = list(ex.map(_fires, jobs))
    return float(np.mean([r[0] for r in res])), [u for r in res for u in r[1]]


def calibrate(ex, cfg, ratio):
    """Match every trigger to the threshold baseline's alarm rate, then set the
    urgency->deadline endpoints from the observed urgency spread."""
    ref, _ = rate(ex, cfg, "threshold", 0.0)
    chosen = {"threshold": 0.0}
    for mk, grid in GRIDS.items():
        rows = [(t, rate(ex, cfg, mk, t)[0]) for t in grid]
        chosen[mk] = min(rows, key=lambda r: abs(r[1] - ref))[0]
        print(f"      {mk:10s} ref={ref:5.1f}  " +
              " ".join(f"{t}:{f:.0f}" for t, f in rows) +
              f"  -> {chosen[mk]}")
    chosen["fixed_dl"] = chosen["proposed"]        # same trigger family
    _, us = rate(ex, cfg, "proposed", chosen["proposed"])
    lo, hi = (float(np.percentile(us, 10)), float(np.percentile(us, 90))) \
        if len(us) > 10 else (cfg.urg.urgency_lo, cfg.urg.urgency_hi)
    if hi - lo < 0.2:
        hi = lo + 0.2
    cfg = dataclasses.replace(cfg, urg=dataclasses.replace(
        cfg.urg, urgency_lo=lo, urgency_hi=hi))
    print(f"      urgency_lo/hi = {lo:.2f}/{hi:.2f}   ref budget {ref:.1f}/run")
    return cfg, chosen, ref


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=30)
    a = ap.parse_args()
    base = Config()
    t_start = time.perf_counter()

    print("=" * 86)
    print("CURRENT plume advection speed vs agent speed")
    print("=" * 86)
    for tag, w in [("predictable", base.fld.wind),
                   (f"unpredictable after t={base.fld.wind_shift_t}",
                    base.fld.wind_after)]:
        print(f"  {tag:34s} |wind| = {np.hypot(*w):.3f} cells/tick, "
              f"agent {base.agent.speed} -> ratio {np.hypot(*w)/base.agent.speed:.3f}")
    mags = [np.hypot(*jitter_config(base, np.random.default_rng(s*7919+13)).fld.wind)
            for s in range(200)]
    print(f"  with per-seed jitter: mean {np.mean(mags):.3f}, "
          f"range {min(mags):.3f}-{max(mags):.3f}")

    print("\n" + "=" * 86)
    print(f"SPEED SWEEP  ({a.seeds} seeds x {len(SCEN)} field x {len(CONN)} conn "
          f"= {a.seeds*4} pairs/point, seeds {SEED0}-{SEED0+a.seeds-1})")
    print("=" * 86)

    all_rows, scen_info = [], {}
    with ProcessPoolExecutor(max_workers=WORKERS) as ex:
        for r in RATIOS:
            cfg_r = with_speed(base, r)
            f = PollutantField(jitter_config(cfg_r, np.random.default_rng(SEED0*7919+13)))
            # how hard is the scenario at this speed?
            ev, pk = [], []
            for s in SCEN:
                c = jitter_config(with_scenario(cfg_r, s),
                                  np.random.default_rng(SEED0*7919+13))
                h = rollout_field(c, c.agent.mission_ticks)
                ev.append(len(extract_events(c, h))); pk.append(float(h.max()))
            scen_info[r] = dict(substeps=f.substeps, dt=f.dt,
                                events=float(np.mean(ev)), peak=float(np.mean(pk)))
            print(f"\n  --- ratio {r} (substeps {f.substeps}, dt {f.dt:.3f}, "
                  f"peak {np.mean(pk):.2f}, {np.mean(ev):.0f} events/run) ---")
            print("    calibrating:")
            cfg_r, trig, ref = calibrate(ex, cfg_r, r)
            jobs = [(c, sd, mk, trig[mk])
                    for (c, sd) in _cells(cfg_r, a.seeds) for mk in METHODS]
            rows = list(ex.map(_summary, jobs, chunksize=4))
            for row in rows:
                row["ratio"] = r
            all_rows += rows

    # ---------------- report ----------------
    import csv
    with open(RES/"sweep_speed.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(all_rows[0].keys()))
        w.writeheader(); w.writerows(all_rows)

    def pick(r, mk):
        return [x for x in all_rows if x["ratio"] == r and x["method"] == mk]

    def mci(v):
        v = np.array([x for x in v if np.isfinite(x)], dtype=float)
        if v.size == 0:
            return np.nan, np.nan
        return float(v.mean()), float(1.96*v.std(ddof=1)/np.sqrt(v.size))

    print("\n" + "=" * 86)
    print("RESULTS  (on-time ratio over observable events; latency in ticks)")
    print("=" * 86)
    print(f"  {'ratio':>5s} {'method':10s} {'fires':>6s} {'on-time':>14s} "
          f"{'latency':>8s} {'FA rate':>8s} {'mapRMSE':>8s}")
    summary = {}
    for r in RATIOS:
        for mk in METHODS:
            rs = pick(r, mk)
            m, ci = mci([x["on_time_ratio"] for x in rs])
            lat, _ = mci([x["mean_latency"] for x in rs])
            fa, _ = mci([x["false_alarm_rate"] for x in rs])
            mr, _ = mci([x["map_rmse"] for x in rs])
            fi, _ = mci([x["n_fires"] for x in rs])
            summary[(r, mk)] = dict(on_time=m, ci=ci, latency=lat, fa=fa, rmse=mr,
                                    fires=fi)
            print(f"  {r:5.2f} {mk:10s} {fi:6.1f} {m:7.3f}+-{ci:5.3f} "
                  f"{lat:8.1f} {fa:8.3f} {mr:8.4f}")
        print()

    print("=" * 86)
    print("PAIRED TESTS AT EACH SPEED (same seeds; Wilcoxon signed-rank)")
    print("=" * 86)
    pairs = [("proposed", "threshold"), ("proposed", "fixed_dl"),
             ("proposed", "raw_abl")]
    stats = {}
    for metric in ["on_time_ratio", "mean_latency", "false_alarm_rate"]:
        print(f"\n  -- {metric} (negative diff = proposed lower) --")
        hdr = "  ratio  " + "".join(f"{a_+' vs '+b_:>30s}" for a_, b_ in pairs)
        print(hdr)
        for r in RATIOS:
            line = f"  {r:5.2f}  "
            for a_, b_ in pairs:
                ka = {(x["scenario"], x["conn"], x["seed"]): x[metric]
                      for x in pick(r, a_)}
                kb = {(x["scenario"], x["conn"], x["seed"]): x[metric]
                      for x in pick(r, b_)}
                ks = sorted(set(ka) & set(kb))
                va = np.array([ka[k] for k in ks], float)
                vb = np.array([kb[k] for k in ks], float)
                m = np.isfinite(va) & np.isfinite(vb)
                va, vb = va[m], vb[m]
                try:
                    p = wilcoxon(va, vb)[1] if not np.allclose(va, vb) else 1.0
                except Exception:
                    p = np.nan
                d = va.mean() - vb.mean()
                star = "***" if p < .001 else "**" if p < .01 else "*" if p < .05 else " "
                line += f"{d:+9.3f} p={p:<8.1e}{star:<3s}"
                stats[f"{metric}|{r}|{a_}v{b_}"] = dict(diff=float(d), p=float(p),
                                                        n=int(va.size))
            print(line)

    # ---------------- plot ----------------
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.6))
    colors = {"proposed": "#4da3ff", "threshold": "#ff2d95",
              "fixed_dl": "#ffd166", "raw_abl": "#39ff88"}
    for ax, key, ttl, inv in [
            (axes[0], "on_time", "on-time delivery ratio (higher better)", False),
            (axes[1], "latency", "mean event->cloud latency (lower better)", True),
            (axes[2], "fa", "false-alarm rate (lower better)", True)]:
        for mk in METHODS:
            y = [summary[(r, mk)][key] for r in RATIOS]
            e = [summary[(r, mk)]["ci"] if key == "on_time" else 0 for r in RATIOS]
            ax.errorbar(RATIOS, y, yerr=e, marker="o", capsize=3, lw=1.8,
                        color=colors[mk], label=mk)
        ax.axvline(0.316, color="#888", ls="--", lw=1)
        ax.annotate("current\n0.32", xy=(0.316, ax.get_ylim()[0]), fontsize=7,
                    color="#888", ha="center", va="bottom")
        ax.set_xlabel("plume advection speed / agent speed")
        ax.set_title(ttl, fontsize=10)
        ax.grid(alpha=.25)
        ax.legend(fontsize=8)
    plt.tight_layout(); plt.savefig(OUT/"sweep_speed.png", dpi=120); plt.close()

    with open(RES/"sweep_speed.json", "w") as fh:
        json.dump(dict(ratios=RATIOS, seeds=a.seeds, seed0=SEED0,
                       scenario_info={str(k): v for k, v in scen_info.items()},
                       summary={f"{k[0]}|{k[1]}": v for k, v in summary.items()},
                       paired=stats), fh, indent=1, default=float)
    print(f"\ntotal {(time.perf_counter()-t_start)/60:.1f} min")
    print("  -> figs/sweep_speed.png  results/sweep_speed.csv  results/sweep_speed.json")


if __name__ == "__main__":
    main()
