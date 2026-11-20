"""Feasibility checks. Writes figs/*.png and results/*.csv|json.

    python scripts/run_checks.py                  # everything, 200 seeds
    python scripts/run_checks.py --only 1,6
    python scripts/run_checks.py --seeds 20       # quick pass
    python scripts/run_checks.py --seed-start 2000 --seeds 300   # study block

Seed blocks must not overlap between pilot, sweep and study. The convention
is: pilot 0-199, speed sweep 1000-1029, study 2000+. --seed-start makes that
enforceable rather than conventional (F8), and the block used is recorded in
results/report.json.
"""
import argparse, collections, csv, dataclasses, json, pathlib, sys, time
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import wilcoxon

from urgency_sim.config import Config, with_scenario, with_conn
from urgency_sim.connectivity import coverage_fraction, ge_mean_multiplier
from urgency_sim.field import rollout_field, cfl_limit
from urgency_sim.metrics import summarise
from urgency_sim.methods import (ALL_KEYS, MAIN_FIVE, ABLATIONS,
                                 GP_TRIGGER_KEYS, NON_GP_TRIGGER_KEYS, METHODS)
from urgency_sim.sim import run, jitter_config

OUT = pathlib.Path("figs"); OUT.mkdir(exist_ok=True)
RES = pathlib.Path("results"); RES.mkdir(exist_ok=True)
SCEN = ["predictable", "unpredictable"]
CONN = ["sparse", "dense"]
WORKERS = 10
REPORT = {}
SEED0 = 0          # set by --seed-start; see module docstring


def seeds(n):
    """The n-seed block starting at SEED0. Every check draws its seeds from
    here so one flag moves the whole suite to a disjoint block."""
    return range(SEED0, SEED0 + n)


def _job(a):
    cfg, seed, mk = a
    return summarise(run(cfg, seed, mk))


def sweep(jobs, workers=WORKERS):
    with ProcessPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(_job, jobs, chunksize=4))


def table(rows, keys, group=("scenario", "method")):
    g = collections.defaultdict(list)
    for r in rows:
        g[tuple(r[k] for k in group)].append(r)
    out = {}
    for gk, rs in g.items():
        d = {}
        for k in keys:
            v = np.array([r[k] for r in rs], dtype=float)
            v = v[np.isfinite(v)]
            if v.size == 0:
                d[k] = (np.nan, np.nan); continue
            m = v.mean()
            ci = 1.96 * v.std(ddof=1) / np.sqrt(v.size) if v.size > 1 else 0.0
            d[k] = (float(m), float(ci))
        out[gk] = d
    return out


def paired(rows, a_key, b_key, metric, group_on=("scenario", "conn", "seed")):
    idx = {}
    for r in rows:
        idx.setdefault(r["method"], {})[tuple(r[k] for k in group_on)] = r
    ks = sorted(set(idx[a_key]) & set(idx[b_key]))
    a = np.array([idx[a_key][k][metric] for k in ks], dtype=float)
    b = np.array([idx[b_key][k][metric] for k in ks], dtype=float)
    m = np.isfinite(a) & np.isfinite(b)
    a, b = a[m], b[m]
    if a.size < 3 or np.allclose(a, b):
        return float(np.mean(a)) if a.size else np.nan, \
               float(np.mean(b)) if b.size else np.nan, np.nan, a.size
    try:
        _st, p = wilcoxon(a, b)
    except Exception:
        p = np.nan
    return float(a.mean()), float(b.mean()), float(p), int(a.size)


def pr(t):
    print("\n" + "=" * 86); print(t); print("=" * 86)


# ------------------------------------------------------------------ check 1
def check1():
    pr("CHECK 1 - RUNTIME")
    base = Config(); per = {}
    for mk in ALL_KEYS:
        ts, gp = [], 0
        for sd in range(2):
            t0 = time.perf_counter()
            log = run(with_conn(with_scenario(base, "unpredictable"), "sparse"), sd, mk)
            ts.append(time.perf_counter() - t0); gp = log.gp_seconds
        per[mk] = (float(np.mean(ts)), gp)
        print(f"  {mk:13s} {np.mean(ts):5.2f} s/run  "
              f"{np.mean(ts)/base.agent.mission_ticks*1e3:5.2f} ms/step  "
              f"GP {gp:4.2f} s ({gp/np.mean(ts)*100:4.1f}%)")
    mr = float(np.mean([v[0] for v in per.values()]))
    for label, n in [("200 seeds x 2 field x 7 methods", 200*2*7),
                     ("200 seeds x 2 field x 2 conn x 7 methods", 200*2*2*7)]:
        print(f"  {label} = {n} runs: {n*mr/60:6.1f} min serial, "
              f"{n*mr/60/WORKERS:5.1f} min on {WORKERS} workers")
    REPORT["check1"] = dict(per_method=per, mean_run_s=mr)


# ------------------------------------------------------------------ check 2
def check2():
    pr("CHECK 2 - FIELD SANITY AND PATH COVERAGE")
    base = Config()
    worst = min(cfl_limit(jitter_config(base, np.random.default_rng(s*7919+13)).fld, w)
                for s in seeds(50)
                for w in (jitter_config(base, np.random.default_rng(s*7919+13)).fld.wind,
                          base.fld.wind_after))
    print(f"  grid {base.fld.n}x{base.fld.n}, mission {base.agent.mission_ticks} ticks")
    print(f"  worst combined CFL limit over 50 seeds: {worst:.4f}; "
          f"dt={base.fld.dt} -> ratio {base.fld.dt/worst:.2f} (need < 0.8)")
    fig, axes = plt.subplots(2, 5, figsize=(16, 6.8))
    st = {}
    for r, scen in enumerate(SCEN):
        c = jitter_config(with_scenario(base, scen), np.random.default_rng(13))
        hist = rollout_field(c, c.agent.mission_ticks)
        com = []
        for k, t in enumerate(np.linspace(0, c.agent.mission_ticks, 5).astype(int)):
            ax = axes[r, k]
            ax.imshow(hist[t].T, origin="lower", cmap="inferno", vmin=0,
                      vmax=float(np.percentile(hist, 99.9)))
            m = hist[t].astype(float); ssum = m.sum()
            xs, ys = np.indices(m.shape)
            cx, cy = (xs*m).sum()/ssum, (ys*m).sum()/ssum
            com.append((int(t), round(float(cx), 2), round(float(cy), 2)))
            ax.plot(cx, cy, "c+", ms=11)
            ax.set_title(f"{scen} t={t}  max={m.max():.2f}", fontsize=9)
            ax.set_xticks([]); ax.set_yticks([])
        st[scen] = dict(com=com, finite=bool(np.isfinite(hist).all()),
                        frac_above_hazard=float((hist > c.urg.hazard).mean()))
        print(f"  {scen:14s} finite={st[scen]['finite']} "
              f"frac>hazard={st[scen]['frac_above_hazard']:.4f}  com={com}")
    plt.tight_layout(); plt.savefig(OUT/"check2_field_sanity.png", dpi=110); plt.close()
    # path coverage
    rows = sweep([(with_conn(with_scenario(base, s), c), sd, "proposed")
                  for s in SCEN for c in CONN for sd in range(12)])
    cov = np.array([r["coverage"] for r in rows])
    print(f"\n  PATH COVERAGE: mean {cov.mean()*100:.1f}% "
          f"(min {cov.min()*100:.1f}%, max {cov.max()*100:.1f}%) of {base.fld.n**2} cells")
    print(f"    ceiling is {base.agent.mission_ticks/base.fld.n**2*100:.0f}% "
          f"(one cell per tick, no revisits); was 12% in the first prototype")
    obsf = np.array([r["observable_frac"] for r in rows])
    print(f"  OBSERVABLE EVENTS: {obsf.mean()*100:.1f}% of events come within "
          f"sensor range at some point;")
    nn = np.array([r["n_events_near"] for r in rows], float)
    na = np.array([r["n_events_all"] for r in rows], float)
    print(f"    {np.mean(nn/na)*100:.1f}% within sensor range near the event time "
          f"(+/-{base.ev.match_window} ticks)")
    REPORT["check2"] = dict(worst_cfl=float(worst), stats=st,
                            coverage_mean=float(cov.mean()),
                            observable_any=float(obsf.mean()),
                            observable_near=float(np.mean(nn/na)))
    print("  -> figs/check2_field_sanity.png")


# -------------------------------------------------------------- check conn
def check_conn():
    pr("CHECK C - CONNECTIVITY SCENARIOS: WHAT DOES THE DRAWN RADIUS MEAN?")
    base = Config()
    ge = ge_mean_multiplier(base.comm)
    print("  quality(d) = peak * exp(-0.5 d^2/(radius/2)^2)")
    print(f"    at d = radius      -> exp(-2) = 13.5% of peak  (what the circle shows)")
    print(f"    delivery prob 0.5  -> d ~ 0.57 * radius for a strong region")
    print(f"  Gilbert-Elliott mean multiplier = {ge:.3f}, so effective p = q * {ge:.3f}")
    print(f"\n  {'conn':8s} {'geometric>0.5':>14s} {'effective>0.5':>14s} "
          f"{'inside drawn circle':>20s}")
    res = {}
    for c in CONN:
        g, e, d = coverage_fraction(with_conn(base, c), 200)
        res[c] = dict(geometric=g, effective=e, drawn=d)
        print(f"  {c:8s} {g*100:13.1f}% {e*100:13.1f}% {d*100:19.1f}%")
    print("\n  => the drawn circles overstate real coverage by roughly 3-5x.")
    REPORT["check_conn"] = res


# ---------------------------------------------------------------- check 3/4
def check34(nseeds):
    pr(f"CHECK 3 & 4 - DETECTION, AND DO THE TWO URGENCY TERMS EARN THEIR PLACE? "
       f"({nseeds} seeds)")
    base = Config()
    ms = ["proposed", "surprise_abl", "raw_abl", "threshold"]
    rows = sweep([(with_conn(with_scenario(base, s), c), sd, mk)
                  for s in SCEN for c in CONN for sd in seeds(nseeds) for mk in ms])
    t = table(rows, ["n_fires", "detection_rate", "false_alarm_rate", "mean_delay",
                     "n_detours", "n_false_detours"], group=("conn", "method"))
    print(f"  {'conn':8s} {'method':13s} {'fires':>6s} {'detect':>8s} {'FA rate':>9s} "
          f"{'delay':>7s} {'detours':>8s} {'falseDet':>9s}")
    for cn in CONN:
        for mk in ms:
            d = t[(cn, mk)]
            print(f"  {cn:8s} {mk:13s} {d['n_fires'][0]:6.1f} "
                  f"{d['detection_rate'][0]:7.3f} {d['false_alarm_rate'][0]:9.3f} "
                  f"{d['mean_delay'][0]:7.1f} {d['n_detours'][0]:8.1f} "
                  f"{d['n_false_detours'][0]:9.1f}")
        print()
    print("  paired tests on false-alarm rate (lower is better):")
    for other in ["surprise_abl", "raw_abl", "threshold"]:
        a, b, p, n = paired(rows, "proposed", other, "false_alarm_rate")
        print(f"    proposed {a:.3f} vs {other:13s} {b:.3f}  diff={a-b:+.3f}  "
              f"p={p:.4f}  (n={n})")
    print("  paired tests on detection rate (higher is better):")
    for other in ["surprise_abl", "raw_abl", "threshold"]:
        a, b, p, n = paired(rows, "proposed", other, "detection_rate")
        print(f"    proposed {a:.3f} vs {other:13s} {b:.3f}  diff={a-b:+.3f}  "
              f"p={p:.4f}  (n={n})")
    REPORT["check3_4"] = {f"{k[0]}|{k[1]}": v for k, v in t.items()}
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    for ax, key, ttl in zip(axes, ["detection_rate", "false_alarm_rate", "n_false_detours"],
                            ["detection rate (higher better)",
                             "false-alarm rate (lower better)",
                             "false-alarm detours (lower better)"]):
        w = .38
        for i, cn in enumerate(CONN):
            v = [t[(cn, m)][key][0] for m in ms]; e = [t[(cn, m)][key][1] for m in ms]
            ax.bar(np.arange(len(ms))+i*w, v, w, yerr=e, capsize=3, label=cn)
        ax.set_xticks(np.arange(len(ms))+w/2)
        ax.set_xticklabels(ms, rotation=20, ha="right", fontsize=8)
        ax.set_title(ttl, fontsize=10); ax.legend(fontsize=8)
    plt.tight_layout(); plt.savefig(OUT/"check34_detection.png", dpi=115); plt.close()
    print("  -> figs/check34_detection.png")


# ------------------------------------------------------------------ check 5
def check5(nseeds):
    pr(f"CHECK 5 - ACTION CHOICE, DEADLINE TIGHTNESS, AND REGION USAGE "
       f"({nseeds} seeds)")
    base = Config()
    allrows = {}
    for rule in ["p_deliver", "exp_time"]:
        cfg = dataclasses.replace(base, dec=dataclasses.replace(
            base.dec, select_by=rule))
        allrows[rule] = sweep([(with_conn(with_scenario(cfg, s), c), sd, "proposed")
                               for s in SCEN for c in CONN for sd in seeds(nseeds)])
    print("  --- selection rule comparison (how often each action is chosen) ---")
    print(f"  {'rule':11s} {'conn':8s} {'transmit':>9s} {'launch':>8s} "
          f"{'region':>8s} {'explore':>8s} {'on-time':>8s} {'cov':>6s}")
    for rule in ["p_deliver", "exp_time"]:
        tt = table(allrows[rule], ["frac_chose_tx", "frac_chose_launch",
                                   "frac_chose_region", "frac_chose_explore",
                                   "on_time_ratio", "coverage"], group=("conn",))
        for cn in CONN:
            d = tt[(cn,)]
            print(f"  {rule:11s} {cn:8s} {d['frac_chose_tx'][0]*100:8.1f}% "
                  f"{d['frac_chose_launch'][0]*100:7.1f}% "
                  f"{d['frac_chose_region'][0]*100:7.1f}% "
                  f"{d['frac_chose_explore'][0]*100:7.1f}% "
                  f"{d['on_time_ratio'][0]:8.3f} {d['coverage'][0]:6.2f}")
    REPORT["check5_rules"] = {
        r: {k[0]: v for k, v in table(allrows[r],
            ["frac_chose_tx", "frac_chose_launch", "frac_chose_region",
             "frac_chose_explore", "on_time_ratio"], group=("conn",)).items()}
        for r in allrows}
    print()
    rows = allrows[base.dec.select_by]
    keys = ["n_disc_regions", "n_disc_regions_max", "n_regions_true",
            "tightness_launch", "tightness_region", "frac_tight_launch",
            "frac_tight_region", "et_transmit_now", "et_goto_launch",
            "et_goto_region", "et_explore",
            "frac_chose_region", "frac_chose_launch",
            "frac_chose_tx", "frac_chose_explore", "mean_dist_nonlaunch",
            "mean_dist_launch", "mean_phat_nonlaunch", "mean_phat_launch",
            "mean_horizon", "p_transmit_now", "p_goto_launch", "p_goto_region",
            "p_explore", "n_decisions"]
    t = table(rows, keys, group=("conn",))
    for cn in CONN:
        d = t[(cn,)]
        print(f"  --- {cn} connectivity ---")
        print(f"    decisions while pending: {d['n_decisions'][0]:.1f}/run")
        print(f"    regions: {d['n_disc_regions'][0]:.2f} discovered at decision time "
              f"(peak {d['n_disc_regions_max'][0]:.2f}) vs "
              f"{d['n_regions_true'][0]:.2f} real")
        print(f"    action chosen:  transmit_now {d['frac_chose_tx'][0]*100:5.1f}%   "
              f"goto_launch {d['frac_chose_launch'][0]*100:5.1f}%   "
              f"goto_region {d['frac_chose_region'][0]*100:5.1f}%   "
              f"explore {d['frac_chose_explore'][0]*100:5.1f}%")
        print(f"    distance when pending:  launch {d['mean_dist_launch'][0]:5.1f} cells,"
              f"  other regions {d['mean_dist_nonlaunch'][0]:5.1f} cells")
        print(f"    estimated p(success):   launch {d['mean_phat_launch'][0]:.3f},"
              f"       other regions {d['mean_phat_nonlaunch'][0]:.3f}")
        print(f"    mean P(deliver) scored per action: "
              f"transmit_now {d['p_transmit_now'][0]:.3f}  "
              f"goto_launch {d['p_goto_launch'][0]:.3f}  "
              f"goto_region {d['p_goto_region'][0]:.3f}  "
              f"explore {d['p_explore'][0]:.3f}")
        print(f"    mean E[time to upload]:  transmit_now {d['et_transmit_now'][0]:6.1f}  "
              f"goto_launch {d['et_goto_launch'][0]:6.1f}  "
              f"goto_region {d['et_goto_region'][0]:6.1f}  "
              f"explore {d['et_explore'][0]:6.1f}")
        print(f"    deadline horizon {d['mean_horizon'][0]:.1f} ticks; tightness "
              f"(horizon/travel): launch {d['tightness_launch'][0]:.1f}, "
              f"region {d['tightness_region'][0]:.1f}")
        print(f"    fraction where the deadline expires before the agent could "
              f"arrive: launch {d['frac_tight_launch'][0]*100:.0f}%, "
              f"region {d['frac_tight_region'][0]*100:.0f}%\n")
    REPORT["check5"] = {k[0]: v for k, v in t.items()}


# ------------------------------------------------------------------ check 6
def check6(nseeds):
    pr(f"CHECK 6 - DO METHODS ACTUALLY DIFFER? ({nseeds} seeds x 2 field x 2 conn)")
    base = Config()
    jobs = [(with_conn(with_scenario(base, s), c), sd, mk)
            for s in SCEN for c in CONN for sd in seeds(nseeds) for mk in ALL_KEYS]
    print(f"  {len(jobs)} runs on {WORKERS} workers ...")
    t0 = time.perf_counter()
    rows = sweep(jobs)
    print(f"  done in {(time.perf_counter()-t0)/60:.1f} min")
    with open(RES/"check6_runs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader()
        w.writerows(rows)
    keys = ["on_time_ratio", "on_time_ratio_near", "on_time_ratio_all",
            "mean_latency", "p95_latency", "map_rmse", "misbelief_frac",
            "coverage", "n_false_detours", "n_deliveries", "energy", "n_fires"]
    t = table(rows, keys, group=("scenario", "conn", "method"))
    print(f"\n  {'scen':6s} {'conn':7s} {'method':13s} {'on-time(obs)':>14s} "
          f"{'near':>7s} {'latency':>8s} {'mapRMSE':>9s} {'falseDet':>9s} {'energy':>7s}")
    for sc in SCEN:
        for cn in CONN:
            for mk in ALL_KEYS:
                d = t[(sc, cn, mk)]
                print(f"  {sc[:5]:6s} {cn:7s} {mk:13s} "
                      f"{d['on_time_ratio'][0]:6.3f}+-{d['on_time_ratio'][1]:5.3f} "
                      f"{d['on_time_ratio_near'][0]:7.3f} {d['mean_latency'][0]:8.1f} "
                      f"{d['map_rmse'][0]:9.4f} {d['n_false_detours'][0]:9.1f} "
                      f"{d['energy'][0]:7.0f}")
            print()
    print("  === paired Wilcoxon, proposed vs each method, pooled over all cells ===")
    stats = {}
    for metric in ["on_time_ratio", "map_rmse", "mean_latency"]:
        print(f"  -- {metric} --")
        for mk in ALL_KEYS:
            if mk == "proposed":
                continue
            a, b, p, n = paired(rows, "proposed", mk, metric)
            star = "***" if p < .001 else "**" if p < .01 else "*" if p < .05 else ""
            print(f"    proposed {a:8.4f} vs {mk:13s} {b:8.4f}  "
                  f"diff={a-b:+8.4f}  p={p:.2e} {star}  (n={n})")
            stats[f"{metric}|{mk}"] = dict(proposed=a, other=b, diff=a-b, p=p, n=n)
    print("\n  === map RMSE: GP-trigger methods vs non-GP-trigger methods ===")
    print("  (every method builds a cloud GP map; only the TRIGGER differs)")
    for mk in ALL_KEYS:
        d = np.mean([t[(s, c, mk)]["map_rmse"][0] for s in SCEN for c in CONN])
        tag = "GP trigger" if mk in GP_TRIGGER_KEYS else "no GP trigger"
        print(f"    {mk:13s} {d:.4f}   [{tag}]")
    REPORT["check6"] = dict(table={f"{k[0]}|{k[1]}|{k[2]}": v for k, v in t.items()},
                            stats=stats, nseeds=nseeds)
    # plot
    fig, axes = plt.subplots(2, 3, figsize=(16, 8))
    for row, cn in enumerate(CONN):
        for ax, key, ttl in zip(axes[row],
                ["on_time_ratio", "map_rmse", "n_false_detours"],
                [f"{cn}: on-time ratio (observable events)",
                 f"{cn}: cloud map RMSE (lower better)",
                 f"{cn}: false-alarm detours"]):
            w = .38
            for i, sc in enumerate(SCEN):
                v = [t[(sc, cn, m)][key][0] for m in ALL_KEYS]
                e = [t[(sc, cn, m)][key][1] for m in ALL_KEYS]
                ax.bar(np.arange(len(ALL_KEYS))+i*w, v, w, yerr=e, capsize=3, label=sc)
            ax.set_xticks(np.arange(len(ALL_KEYS))+w/2)
            ax.set_xticklabels(ALL_KEYS, rotation=35, ha="right", fontsize=8)
            ax.set_title(ttl, fontsize=10); ax.legend(fontsize=8)
    plt.tight_layout(); plt.savefig(OUT/"check6_methods.png", dpi=115); plt.close()
    print("  -> figs/check6_methods.png  results/check6_runs.csv")


# ------------------------------------------------------------------ check 7
def check7(nseeds):
    pr(f"CHECK 7 - REGION DISCOVERY ({nseeds} seeds)")
    base = Config(); agg = {}
    for cn in CONN:
        found, true_n, times = [], [], []
        for sc in SCEN:
            for sd in seeds(nseeds):
                log = run(with_conn(with_scenario(base, sc), cn), sd, "proposed")
                found.append(log.n_regions[-1]-1); true_n.append(len(log.regions_true)-1)
                times += [t for (t, _cx, _cy) in log.region_found]
        agg[cn] = dict(mean_found=float(np.mean(found)),
                       mean_true=float(np.mean(true_n)),
                       median_tick=float(np.median(times)) if times else None)
        print(f"  {cn:8s}: discovered {np.mean(found):.2f} of {np.mean(true_n):.2f} "
              f"real extra regions ({np.mean(found)/max(np.mean(true_n),1e-9)*100:.0f}%), "
              f"median discovery tick {np.median(times) if times else float('nan'):.0f} "
              f"of {base.agent.mission_ticks}")
    REPORT["check7"] = agg


# ------------------------------------------------------------------ check 8
def check8(nseeds):
    pr(f"CHECK 8 - SENSITIVITY ({nseeds} seeds)")
    base = Config(); variants = {}
    for lo, hi in [(1.3, 8.3), (1.0, 4.0), (2.0, 15.0)]:
        variants[f"urgency[{lo},{hi}]"] = dataclasses.replace(
            base, urg=dataclasses.replace(base.urg, urgency_lo=lo, urgency_hi=hi))
    for k in [1, 2, 3, 5]:
        variants[f"k_consistent={k}"] = dataclasses.replace(
            base, urg=dataclasses.replace(base.urg, k_consistent=k))
    for h in [0.25, 0.35, 0.50]:
        variants[f"hazard={h}"] = dataclasses.replace(
            base, urg=dataclasses.replace(base.urg, hazard=h))
    for wc in [0.0, 1.0, 3.0]:
        variants[f"w_consequence={wc}"] = dataclasses.replace(
            base, urg=dataclasses.replace(base.urg, w_consequence=wc))
    jobs, meta = [], []
    for name, cfg in variants.items():
        for sc in SCEN:
            for cn in CONN:
                for sd in seeds(nseeds):
                    for mk in ["proposed", "threshold"]:
                        jobs.append((with_conn(with_scenario(cfg, sc), cn), sd, mk))
                        meta.append(name)
    rows = sweep(jobs)
    for r, name in zip(rows, meta):
        r["variant"] = name
    t = table(rows, ["on_time_ratio", "n_false_detours", "map_rmse", "n_fires"],
              group=("variant", "method"))
    print(f"  {'variant':22s} {'method':10s} {'on-time':>14s} {'falseDet':>9s} "
          f"{'mapRMSE':>9s} {'fires':>7s}   verdict")
    res = {}
    for name in variants:
        a, b = t[(name, "proposed")], t[(name, "threshold")]
        diff = a["on_time_ratio"][0] - b["on_time_ratio"][0]
        win = "proposed" if diff > 0.005 else ("THRESHOLD" if diff < -0.005 else "tie")
        for mk, d in [("proposed", a), ("threshold", b)]:
            print(f"  {name:22s} {mk:10s} "
                  f"{d['on_time_ratio'][0]:7.3f}+-{d['on_time_ratio'][1]:5.3f} "
                  f"{d['n_false_detours'][0]:9.1f} {d['map_rmse'][0]:9.4f} "
                  f"{d['n_fires'][0]:7.1f}" + (f"   {win}" if mk == "proposed" else ""))
        res[name] = dict(proposed=a["on_time_ratio"][0],
                         threshold=b["on_time_ratio"][0], verdict=win)
        print()
    REPORT["check8"] = res


# ------------------------------------------------------------------ check 9
def check9(nseeds):
    pr(f"CHECK 9 - URGENCY -> DEADLINE DISTRIBUTION ({nseeds} seeds)")
    base = Config()
    U, D = [], []
    for sc in SCEN:
        for cn in CONN:
            for sd in seeds(nseeds):
                log = run(with_conn(with_scenario(base, sc), cn), sd, "proposed")
                for (t, _x, _y, u, dl) in log.fires:
                    U.append(u); D.append(dl - t)
    U, D = np.array(U), np.array(D)
    print(f"  urgency at fire:  " +
          "  ".join(f"p{q}={np.percentile(U,q):.2f}" for q in [10, 25, 50, 75, 90]))
    print(f"  assigned deadline (allowed {base.urg.deadline_min:.0f}"
          f"..{base.urg.deadline_max:.0f} ticks):")
    print("    " + "  ".join(f"p{q}={np.percentile(D,q):.0f}"
                             for q in [5, 10, 25, 50, 75, 90, 95]))
    print(f"    mean {D.mean():.1f}  std {D.std():.1f}  "
          f"at floor {np.mean(D <= base.urg.deadline_min+5)*100:.0f}%  "
          f"at ceiling {np.mean(D >= base.urg.deadline_max-5)*100:.0f}%")
    fig, (a0, a1) = plt.subplots(1, 2, figsize=(11, 4))
    a0.hist(U[U < np.percentile(U, 99)], bins=50, color="#4da3ff")
    a0.set_title("urgency at fire time (99th pct clipped)", fontsize=10)
    a0.axvline(base.urg.urgency_lo, color="g", ls="--", label="urgency_lo")
    a0.axvline(base.urg.urgency_hi, color="r", ls="--", label="urgency_hi")
    a0.legend(fontsize=8)
    a1.hist(D, bins=np.arange(base.urg.deadline_min, base.urg.deadline_max+10, 10),
            color="#ffd166")
    a1.set_title(f"assigned deadlines (std {D.std():.0f} ticks)", fontsize=10)
    a1.set_xlabel("ticks ahead")
    plt.tight_layout(); plt.savefig(OUT/"check9_deadlines.png", dpi=115); plt.close()
    REPORT["check9"] = dict(urgency_pct={str(q): float(np.percentile(U, q))
                                         for q in [10, 25, 50, 75, 90]},
                            deadline_pct={str(q): float(np.percentile(D, q))
                                          for q in [5, 25, 50, 75, 95]},
                            deadline_std=float(D.std()))
    print("  -> figs/check9_deadlines.png")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--seeds", type=int, default=200)
    ap.add_argument("--seed-start", type=int, default=0,
                    help="first seed of the block (pilot 0, sweep 1000, "
                         "study 2000) -- blocks must not overlap")
    a = ap.parse_args()
    SEED0 = a.seed_start
    want = set(a.only.split(",")) if a.only else None
    ns = a.seeds
    diag = max(8, min(40, ns // 5))
    t0 = time.perf_counter()
    plan = [("1", check1), ("2", check2), ("C", check_conn),
            ("34", lambda: check34(max(10, ns // 4))),
            ("5", lambda: check5(diag)), ("6", lambda: check6(ns)),
            ("7", lambda: check7(diag)), ("8", lambda: check8(max(8, ns // 12))),
            ("9", lambda: check9(diag))]
    for name, fn in plan:
        if want is not None:
            sel = {"3", "4", "34"} if name == "34" else {name}
            if not (want & sel):
                continue
        fn()
    print(f"\ntotal {(time.perf_counter()-t0)/60:.1f} min")
    out = {}
    rp = RES/"report.json"
    if rp.exists():
        try:
            out = json.load(open(rp))
        except Exception:
            out = {}
    REPORT["seed_block"] = dict(start=SEED0, n=ns, end=SEED0 + ns - 1)
    out.update(REPORT)
    with open(rp, "w") as f:
        json.dump(out, f, indent=1, default=float)
    print(f"wrote results/report.json ({len(out)} checks: {', '.join(sorted(out))})")
