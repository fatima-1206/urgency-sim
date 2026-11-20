"""Figures for the Phase 4 research paper.

Everything here reads the COMMITTED .gz archives, so every figure in the paper
regenerates on a fresh clone with no re-simulation. Nothing in this script runs
a simulation except the saturation probe, which is explicitly marked and cached.

    .venv/bin/python scripts/figs_paper.py            # all figures
    .venv/bin/python scripts/figs_paper.py --only outspend
"""
from __future__ import annotations

import argparse
import collections
import glob
import gzip
import json
import os
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402
import numpy as np                 # noqa: E402
from scipy import stats            # noqa: E402

OUT = pathlib.Path("final_writeup/figs")
ARCHIVES = "results/experiments/*/runs.jsonl.gz"

# Matched means the two methods spent comparable airtime. The band is the same
# one used throughout the analysis, and the paper states it explicitly.
MATCHED_LO, MATCHED_HI = 0.9, 1.1

plt.rcParams.update({
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "legend.fontsize": 7.5,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "axes.spines.top": False,
    "axes.spines.right": False,
})

SHORT = {
    "e1_explorability": "mission length",
    "e2_connectivity": "coverage regions",
    "e4_budget_ceiling": "alarm ceiling",
    "e5_agent_speed": "drone speed",
    "e7_hazard": "hazard level",
    "e8_burstiness": "burst length",
    "e9_robustness": "other factors",
    "e10_replication": "replication, unseen seeds",
    "e12_low_hazard": "low hazard",
    "e13_recalibrate": "re-tuned, 20 seeds",
}


def plain_level(lv):
    """Turn a harness level tag into words, so no experiment code reaches the page."""
    lv = str(lv)
    for pre, fmt in (("count", "{} region(s)"), ("size", "region size x{}"),
                     ("h", "hazard {}"), ("t", "{} ticks"), ("v", "speed {}"),
                     ("b", "burst {}")):
        if lv.startswith(pre) and lv[len(pre):][:1].isdigit():
            return fmt.format(lv[len(pre):])
    return "default"


# ------------------------------------------------------------------ loading
def _sat_job(a):
    """Worker for the saturation probe. Must be module-level: a closure cannot
    be pickled across process boundaries."""
    import _harness as H
    build, mk, trig, seed = a
    return mk, trig, H._fires((build, 0.35, "predictable", "sparse", mk, trig, seed))


def _rows(path):
    with gzip.open(path, "rt") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue          # tolerate a torn final line


def cells(min_seeds: int = 30):
    """One record per paired comparison cell.

    A cell is (experiment, level, connectivity, scenario, budget). Both methods
    are paired on identical seeds, which is what makes the Wilcoxon test and the
    out-spend ratio meaningful.
    """
    out = []
    for path in sorted(glob.glob(ARCHIVES)):
        eid = os.path.basename(os.path.dirname(path))
        if eid == "e14_decoupled_threshold":
            continue      # separately pre-registered follow-up, reported on its own
        by = collections.defaultdict(dict)
        for r in _rows(path):
            by[(r["level"], r["conn"], r["scenario"], r["budget"],
                r["method"])][r["seed"]] = r
        for (lv, conn, scen, b, mk) in list(by):
            if mk != "proposed":
                continue
            P, T = by[(lv, conn, scen, b, "proposed")], by.get(
                (lv, conn, scen, b, "threshold"))
            if not T:
                continue                      # E4 is proposed-only by design
            seeds = sorted(set(P) & set(T))
            if len(seeds) < min_seeds:
                continue
            pf = np.mean([P[s]["n_fires"] for s in seeds])
            tf = np.mean([T[s]["n_fires"] for s in seeds])
            a = np.array([P[s]["on_time_ratio"] for s in seeds])
            t = np.array([T[s]["on_time_ratio"] for s in seeds])
            la = np.array([P[s]["mean_latency"] for s in seeds], float)
            lt = np.array([T[s]["mean_latency"] for s in seeds], float)
            ok = ~(np.isnan(la) | np.isnan(lt))
            d = a - t
            out.append(dict(
                eid=eid, level=lv, conn=conn, scen=scen, budget=b,
                n=len(seeds), p_fires=pf, t_fires=tf,
                ratio=pf / max(tf, 1e-9),
                d_ot=float(d.mean()),
                se=float(d.std(ddof=1) / np.sqrt(len(d))),
                d_lat=float(la[ok].mean() - lt[ok].mean()) if ok.any() else np.nan,
            ))
    return out


# ------------------------------------------------------------------ fig 1
def fig_outspend(C):
    """The paper's central figure: the margin is bought with airtime."""
    x = np.log([c["ratio"] for c in C])
    y = np.array([c["d_ot"] for c in C])
    sl, ic, rv, pv, _ = stats.linregress(x, y)

    fig, ax = plt.subplots(figsize=(6.6, 3.5))
    # Fix the limits to the data before shading, so the "baseline wins" band
    # does not stretch the axis and squash the points into a strip.
    lo, hi = y.min(), y.max()
    pad = 0.09 * (hi - lo)
    ax.set_ylim(lo - pad, hi + pad)
    ax.axhspan(lo - pad, 0, color="#c0392b", alpha=0.06, zorder=0)
    ax.axvspan(np.log(MATCHED_LO), np.log(MATCHED_HI),
               color="#2c3e50", alpha=0.13, zorder=1)
    ax.axhline(0, color="#444", lw=0.9, zorder=2)

    eids = sorted({c["eid"] for c in C})
    cmap = plt.get_cmap("tab10")
    for i, e in enumerate(eids):
        sel = [c for c in C if c["eid"] == e]
        ax.scatter([np.log(c["ratio"]) for c in sel], [c["d_ot"] for c in sel],
                   s=17, alpha=0.82, color=cmap(i % 10), linewidths=0,
                   label=SHORT.get(e, e), zorder=3)

    xs = np.linspace(x.min() - 0.1, x.max() + 0.1, 100)
    ax.plot(xs, ic + sl * xs, color="#111", lw=1.5, zorder=4)
    ax.plot([0], [ic], marker="o", ms=7, mfc="white", mec="#111", mew=1.6,
            zorder=5)
    ax.annotate(f"fit at equal\nairtime {ic:+.3f}", xy=(0, ic),
                xytext=(np.log(0.52), lo + 0.15 * pad), fontsize=7.5,
                ha="left", va="bottom",
                arrowprops=dict(arrowstyle="->", lw=0.9, color="#111",
                                connectionstyle="arc3,rad=-0.2"))

    ticks = [0.5, 1, 2, 5, 10, 15]
    ax.set_xticks([np.log(t) for t in ticks])
    ax.set_xticklabels([f"{t:g}x" for t in ticks])
    ax.set_xlabel("alarms sent by the urgency trigger, as a multiple of the "
                  "baseline's  (log scale)")
    ax.set_ylabel("on-time ratio,\nurgency trigger $-$ baseline")
    # Inside the band and rotated, so it cannot collide with the legend.
    ax.text(np.log(1.0), 0.45 * hi, "equal airtime", rotation=90,
            fontsize=7.5, color="#2c3e50", ha="center", va="center")
    ax.legend(loc="upper left", frameon=False, ncol=2, columnspacing=1.0,
              handletextpad=0.35, borderaxespad=0.1)
    fig.savefig(OUT / "fig_outspend.png")
    plt.close(fig)
    print(f"  fig_outspend.png   r={rv:+.3f} p={pv:.2e} n={len(C)} "
          f"intercept={ic:+.4f}")


# ------------------------------------------------------------------ fig 2
def fig_matched_forest(C):
    """Every cell where the two methods spent the same airtime.

    Split into two side-by-side panels: at 79 cells a single column of rows
    would be almost a full page in a two-column paper, and shrinking the row
    pitch far enough to fit makes the labels unreadable.
    """
    M = [c for c in C if MATCHED_LO <= c["ratio"] <= MATCHED_HI]
    M.sort(key=lambda c: (c["eid"], c["budget"], c["d_ot"]))
    half = (len(M) + 1) // 2
    halves = [M[:half], M[half:]]

    all_eids = sorted({c["eid"] for c in C})
    cmap = plt.get_cmap("tab10")
    colour = {e: cmap(all_eids.index(e) % 10) for e in {c["eid"] for c in M}}
    lo = min(c["d_ot"] - 1.96 * c["se"] for c in M)
    hi = max(c["d_ot"] + 1.96 * c["se"] for c in M)
    pad = 0.06 * (hi - lo)

    fig, axes = plt.subplots(1, 2, figsize=(7.4, max(2.6, 0.135 * half)),
                             gridspec_kw={"wspace": 0.95})
    for ax, part in zip(axes, halves):
        ax.axvline(0, color="#444", lw=1.0, zorder=1)
        labels = []
        for i, c in enumerate(part):
            ax.errorbar(c["d_ot"], i, xerr=1.96 * c["se"], fmt="o", ms=2.4,
                        lw=0.8, capsize=1.2, color=colour[c["eid"]], zorder=3)
            scen = "pred." if c["scen"].startswith("predi") else "unpred."
            labels.append(f"{plain_level(c['level'])}, {scen} {c['conn']}, "
                          f"{c['budget']:g} alarms")
        ax.set_yticks(range(len(part)))
        ax.set_yticklabels(labels, fontsize=5.0)
        ax.set_ylim(-1, len(part))
        ax.set_xlim(lo - pad, hi + pad)
        ax.invert_yaxis()
        ax.tick_params(axis="x", labelsize=6.5)

    d = np.array([c["d_ot"] for c in M])
    fig.supxlabel("on-time ratio, urgency trigger $-$ baseline   "
                  "(negative favours the baseline)", fontsize=8)
    handles = [plt.Line2D([], [], color=colour[e], marker="o", ls="", ms=3,
                          label=SHORT.get(e, e))
               for e in sorted(colour)]
    fig.legend(handles=handles, loc="lower center", frameon=False, fontsize=6,
               ncol=4, bbox_to_anchor=(0.5, -0.055))
    fig.savefig(OUT / "fig_matched_forest.png")
    plt.close(fig)
    print(f"  fig_matched_forest.png   {len(M)} matched cells, "
          f"{int((d < 0).sum())} favour the baseline, mean {d.mean():+.4f}")


# ------------------------------------------------------------------ fig 3
def fig_saturation(workers=12, seeds=30):
    """The baseline's ceiling, measured by driving its trigger to zero.

    This is the one figure that runs simulations. The result is cached, because
    the claim it supports is the paper's load-bearing one and should not move
    between builds.
    """
    cache = OUT / "saturation.json"
    if cache.exists():
        data = json.loads(cache.read_text())
        print("  saturation probe: cached")
    else:
        import sys
        sys.path.insert(0, "scripts/experiments")
        sys.path.insert(0, ".")
        from concurrent.futures import ProcessPoolExecutor
        import _harness as H
        import e7_hazard as E7
        exp = E7.EXP
        trigs = [0.0, 1e-6, 1e-4, 1e-3, 4.7e-3, 9.4e-3, 1.875e-2, 3.75e-2,
                 7.5e-2, 0.15, 0.3]
        ptrigs = [0.0, 0.01, 0.05, 0.15, 0.4, 0.8, 1.5, 2.5, 4.0]
        jobs = ([("threshold", t, 6000 + i) for t in trigs for i in range(seeds)]
                + [("proposed", t, 6000 + i) for t in ptrigs
                   for i in range(seeds)])

        jobs = [(exp.build,) + j for j in jobs]
        acc = collections.defaultdict(list)
        with ProcessPoolExecutor(max_workers=workers) as ex:
            for mk, t, f in ex.map(_sat_job, jobs, chunksize=1):
                acc[(mk, t)].append(f)
        data = {"threshold": [[t, float(np.mean(acc[("threshold", t)]))]
                              for t in trigs],
                "proposed": [[t, float(np.mean(acc[("proposed", t)]))]
                             for t in ptrigs]}
        cache.write_text(json.dumps(data, indent=1))

    fig, ax = plt.subplots(figsize=(5.4, 3.5))
    FLOOR = 3e-7          # so trigger 0 is drawable on a log axis
    for mk, col, lab in (("proposed", "#1f77b4", "proposed (urgency)"),
                         ("threshold", "#c0392b", "baseline (hazard threshold)")):
        xy = sorted(data[mk])
        xs = [max(t, FLOOR) for t, _ in xy]
        ys = [v for _, v in xy]
        ax.plot(xs, ys, "o-", ms=3.6, lw=1.4, color=col, label=lab)
    ax.set_xscale("log")
    ax.set_yscale("log")
    thr0 = dict(data["threshold"])[0.0] if 0.0 in dict(data["threshold"]) \
        else sorted(data["threshold"])[0][1]
    prop0 = sorted(data["proposed"])[0][1]
    ax.axhline(thr0, color="#c0392b", ls=":", lw=1.0)
    ax.annotate(f"ceiling {thr0:.2f} alarms/run\n(trigger driven to 0)",
                xy=(1e-4, thr0), xytext=(2e-5, thr0 * 2.4), fontsize=7.5,
                color="#c0392b")
    ax.annotate(f"{prop0:.0f}", xy=(FLOOR, prop0), xytext=(FLOOR * 1.6,
                prop0 * 0.55), fontsize=7.5, color="#1f77b4")
    ax.set_xlabel("trigger threshold (leftmost point is exactly 0)")
    ax.set_ylabel("alarms per run")
    ax.set_title("The baseline cannot be made to send more")
    ax.legend(loc="center left", frameon=False)
    fig.savefig(OUT / "fig_saturation.png")
    plt.close(fig)
    print(f"  fig_saturation.png   baseline floor {thr0:.2f}, "
          f"proposed at trigger 0 {prop0:.1f}")


# ------------------------------------------------------------------ numbers
def dump_numbers(C):
    """Every number the paper quotes, written to one auditable file."""
    x = np.log([c["ratio"] for c in C])
    y = np.array([c["d_ot"] for c in C])
    sl, ic, rv, pv, _ = stats.linregress(x, y)
    M = [c for c in C if MATCHED_LO <= c["ratio"] <= MATCHED_HI]
    d = np.array([c["d_ot"] for c in M])
    lat = np.array([c["d_lat"] for c in M])
    lat = lat[~np.isnan(lat)]

    lines = ["# Numbers quoted in the paper",
             "",
             "Regenerated by `scripts/figs_paper.py` from the committed "
             "archives. Every figure in", "the paper must match this file.", "",
             f"- comparison cells: **{len(C)}**",
             f"- margin vs log(out-spend): r = **{rv:+.3f}**, p = {pv:.2e}, "
             f"slope {sl:+.4f}",
             f"- fit at equal airtime: **{ic:+.4f}**",
             f"- matched cells (ratio {MATCHED_LO}-{MATCHED_HI}): **{len(M)}**",
             f"- matched mean margin: **{d.mean():+.4f}**, 95% CI "
             f"[{d.mean()-1.96*d.std(ddof=1)/len(d)**.5:+.4f}, "
             f"{d.mean()+1.96*d.std(ddof=1)/len(d)**.5:+.4f}]",
             f"- baseline better in **{int((d<0).sum())}/{len(d)}**, "
             f"p = {stats.wilcoxon(d).pvalue:.2e}",
             f"- matched latency: **{lat.mean():+.1f}** ticks "
             f"(positive = proposed slower)",
             "", "## By out-spend band", "",
             "| band | cells | mean margin | wins | losses |",
             "|---|---|---|---|---|"]
    for lo, hi, nm in ((0, 0.9, "< 0.9x"), (0.9, 1.1, "0.9-1.1x (equal)"),
                       (1.1, 2, "1.1-2x"), (2, 5, "2-5x"), (5, 1e9, "> 5x")):
        s = [c for c in C if lo <= c["ratio"] < hi]
        if not s:
            continue
        v = np.array([c["d_ot"] for c in s])
        lines.append(f"| {nm} | {len(s)} | {v.mean():+.3f} | "
                     f"{int((v>0).sum())} | {int((v<0).sum())} |")
    lines += ["", "## Within-budget control", "",
              "| budget | cells | r | p |", "|---|---|---|---|"]
    for b in sorted({c["budget"] for c in C}):
        s = [c for c in C if c["budget"] == b]
        if len(s) < 8:
            continue
        _, _, r2, p2, _ = stats.linregress(
            np.log([c["ratio"] for c in s]), [c["d_ot"] for c in s])
        lines.append(f"| {b:g} | {len(s)} | {r2:+.3f} | {p2:.1e} |")
    lines += ["", "## Matched cells by experiment", "",
              "| experiment | cells | mean | baseline better in |",
              "|---|---|---|---|"]
    for e in sorted({c["eid"] for c in M}):
        v = np.array([c["d_ot"] for c in M if c["eid"] == e])
        lines.append(f"| `{e}` | {len(v)} | {v.mean():+.4f} | "
                     f"{int((v<0).sum())}/{len(v)} |")
    (OUT / "NUMBERS.md").write_text("\n".join(lines) + "\n")
    print(f"  NUMBERS.md         {len(C)} cells, {len(M)} matched")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    want = set(a.only) if a.only else {"outspend", "forest", "saturation",
                                       "numbers"}
    C = cells()
    print(f"loaded {len(C)} comparison cells from "
          f"{len({c['eid'] for c in C})} experiments")
    if "outspend" in want:
        fig_outspend(C)
    if "forest" in want:
        fig_matched_forest(C)
    if "numbers" in want:
        dump_numbers(C)
    if "saturation" in want:
        fig_saturation(a.workers)


if __name__ == "__main__":
    main()
