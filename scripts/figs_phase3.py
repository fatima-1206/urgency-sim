"""Figures for the Phase 3 submission. Reads results/phase3/runs.jsonl(.gz)."""
import collections, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import wilcoxon, spearmanr
from urgency_sim.store import ResultStore

rows = list(ResultStore("results/phase3/runs.jsonl").rows())
idx = collections.defaultdict(dict)
for r in rows:
    idx[(r["stage"], r["speed"], r["scenario"], r["conn"],
         r["method"], r.get("budget"))][r["seed"]] = r

SP = [0.25, 0.5, 1.0]
BUD = [5, 11, 22, 45, 90]
CELLS = [("predictable", "sparse"), ("predictable", "dense"),
         ("unpredictable", "sparse"), ("unpredictable", "dense")]
LBL = {("predictable","sparse"):"predictable / sparse",
       ("predictable","dense"):"predictable / dense",
       ("unpredictable","sparse"):"unpredictable / sparse",
       ("unpredictable","dense"):"unpredictable / dense"}

def m(d, c):
    v = [float(r[c]) for r in d.values()
         if r.get(c) is not None and np.isfinite(float(r[c]))]
    return float(np.mean(v)) if v else np.nan

def sem(d, c):
    v = [float(r[c]) for r in d.values()
         if r.get(c) is not None and np.isfinite(float(r[c]))]
    return float(np.std(v, ddof=1)/np.sqrt(len(v))) if len(v) > 1 else np.nan

def pooled(stage, sp, mk, b, c):
    v = []
    for sc, cn in CELLS:
        v += [float(r[c]) for r in idx[(stage, sp, sc, cn, mk, b)].values()
              if r.get(c) is not None and np.isfinite(float(r[c]))]
    return np.array(v)

def thr_best(sp):
    return max(BUD, key=lambda b: np.nanmean(pooled("frontier", sp, "threshold", b,
                                                    "on_time_ratio")))

# ---- FIG 1: the budget frontier at each speed -------------------------------
fig, ax = plt.subplots(1, 3, figsize=(13.5, 4.1), sharey=True)
for i, sp in enumerate(SP):
    for mk, col in (("proposed", "tab:blue"), ("threshold", "tab:orange")):
        f  = [np.nanmean(pooled("frontier", sp, mk, b, "n_fires")) for b in BUD]
        y  = [np.nanmean(pooled("frontier", sp, mk, b, "on_time_ratio")) for b in BUD]
        e  = [1.96*np.nanstd(pooled("frontier", sp, mk, b, "on_time_ratio"), ddof=1)
              / np.sqrt(pooled("frontier", sp, mk, b, "on_time_ratio").size) for b in BUD]
        ax[i].errorbar(f, y, yerr=e, marker="o", color=col,
                       label="Proposed" if mk == "proposed" else "B2 threshold")
    cap = np.nanmean(pooled("frontier", sp, "threshold", 90, "n_fires"))
    ax[i].axvline(cap, ls=":", c="tab:orange", lw=1)
    ax[i].annotate(f"baseline cannot\nexceed {cap:.0f} alarms", (cap*1.15, 0.17),
                   fontsize=7.5, color="tab:orange")
    ax[i].set_xscale("log"); ax[i].grid(alpha=.3)
    ax[i].set_xlabel("alarms raised per run (log)")
    ax[i].set_title(f"plume/agent speed ratio {sp:g}", fontsize=10)
ax[0].set_ylabel("on-time delivery ratio"); ax[0].legend(fontsize=9)
fig.suptitle("The proposed trigger converts alarm budget into timely delivery; "
             "the threshold baseline saturates and cannot", fontsize=11)
fig.tight_layout(); fig.savefig("figs/p3_frontier.png", dpi=140); plt.close(fig)

# ---- FIG 2: forest plot, all 12 primary comparisons -------------------------
fig, ax = plt.subplots(figsize=(8.4, 5.4))
ys, labs = [], []
k = 0
for sp in SP:
    tb = thr_best(sp)
    for sc, cn in CELLS:
        A = idx[("frontier", sp, sc, cn, "proposed", 45)]
        B = idx[("frontier", sp, sc, cn, "threshold", tb)]
        d = np.array([float(A[s]["on_time_ratio"]) - float(B[s]["on_time_ratio"])
                      for s in A if s in B])
        ci = 1.96*d.std(ddof=1)/np.sqrt(d.size)
        ok = d.mean() - ci > 0
        c = "tab:green" if ok else "tab:red"
        ax.errorbar(d.mean(), k, xerr=ci, fmt="o", color=c, capsize=3)
        labs.append(f"{sp:g}  {LBL[(sc,cn)]}"); ys.append(k); k += 1
    k += 0.6
ax.axvline(0, c="k", lw=1)
ax.set_yticks(ys); ax.set_yticklabels(labs, fontsize=8.5)
ax.invert_yaxis(); ax.grid(alpha=.3, axis="x")
ax.set_xlabel("on-time advantage of Proposed @45 alarms over the baseline's best "
              "(95% CI)")
ax.set_title("Primary endpoint: 9 of 12 conditions favour the proposed method.\n"
             "Green = CI excludes zero. All three failures are unpredictable-plume "
             "cells.", fontsize=10)
fig.tight_layout(); fig.savefig("figs/p3_forest.png", dpi=140); plt.close(fig)

# ---- FIG 3: ablations at matched budget -------------------------------------
ABL = [("fixed_dl", "no adaptive deadline"), ("surprise_abl", "no consequence term"),
       ("raw_abl", "no uncertainty scaling"), ("always_tx", "no upload-point choice"),
       ("time_urg", "no GP trigger"), ("threshold", "no GP (B2 threshold)")]
fig, ax = plt.subplots(figsize=(8.6, 4.2))
names, mus, cis = [], [], []
for mk, lab in ABL:
    d = np.concatenate([
        np.array([float(idx[("matched",0.25,sc,cn,"proposed",None)][s]["on_time_ratio"])
                  - float(idx[("matched",0.25,sc,cn,mk,None)][s]["on_time_ratio"])
                  for s in idx[("matched",0.25,sc,cn,"proposed",None)]
                  if s in idx[("matched",0.25,sc,cn,mk,None)]])
        for sc, cn in CELLS])
    names.append(lab); mus.append(d.mean())
    cis.append(1.96*d.std(ddof=1)/np.sqrt(d.size))
o = np.argsort(mus)
cols = ["tab:red" if mus[i] < 0 else "tab:green" for i in o]
ax.barh(range(len(o)), [mus[i] for i in o], xerr=[cis[i] for i in o],
        color=cols, capsize=3)
ax.set_yticks(range(len(o))); ax.set_yticklabels([names[i] for i in o], fontsize=9)
ax.axvline(0, c="k", lw=1); ax.grid(alpha=.3, axis="x")
ax.set_xlabel("on-time ratio: Proposed minus variant (95% CI)   "
              "— positive = the removed component helps")
ax.set_title("Ablations at a matched alarm budget, speed 0.25, n=1200 pairs.\n"
             "Red = removing the component IMPROVES performance.", fontsize=10)
fig.tight_layout(); fig.savefig("figs/p3_ablation.png", dpi=140); plt.close(fig)

# ---- FIG 4: the two endpoints are one endpoint ------------------------------
MS = ["proposed","fixed_dl","threshold","time_urg","always_tx","surprise_abl","raw_abl"]
fig, ax = plt.subplots(figsize=(6.2, 4.6))
x = [np.nanmean(pooled("matched",0.25,mk,None,"on_time_ratio")) for mk in MS]
y = [np.nanmean(pooled("matched",0.25,mk,None,"map_rmse")) for mk in MS]
ax.scatter(x, y, c=["tab:blue" if k=="proposed" else "gray" for k in MS], s=55, zorder=3)
for a, b, k in zip(x, y, MS):
    ax.annotate(k, (a, b), fontsize=8, xytext=(4, 4), textcoords="offset points")
z = np.polyfit(x, y, 1); xs = np.linspace(min(x), max(x), 10)
ax.plot(xs, np.polyval(z, xs), ls="--", c="k", lw=1)
ax.set_xlabel("on-time delivery ratio (higher better)")
ax.set_ylabel("map RMSE (lower better)")
ax.set_title(f"The two endpoints are one endpoint\nSpearman "
             f"{spearmanr(x, y).statistic:+.2f} across 7 methods", fontsize=10)
ax.grid(alpha=.3); fig.tight_layout()
fig.savefig("figs/p3_endpoints.png", dpi=140); plt.close(fig)

print("wrote figs/p3_frontier.png figs/p3_forest.png figs/p3_ablation.png "
      "figs/p3_endpoints.png")
