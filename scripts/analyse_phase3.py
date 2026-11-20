"""Analyse the Phase 3 store against PROTOCOL.md. Decides nothing the protocol
did not already fix: the endpoints, the decision rule and the correction are
all pre-registered.

    .venv/bin/python scripts/analyse_phase3.py
"""
import collections, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import numpy as np
from scipy.stats import wilcoxon, pearsonr, spearmanr

from urgency_sim.store import ResultStore

STORE = "results/phase3/runs.jsonl"
CELLS = [(s, c) for s in ("predictable", "unpredictable")
         for c in ("sparse", "dense")]


def load():
    rows = list(ResultStore(STORE).rows())
    idx = collections.defaultdict(dict)
    for r in rows:
        k = (r["stage"], r["speed"], r["scenario"], r["conn"],
             r["method"], r.get("budget"))
        idx[k][r["seed"]] = r
    return rows, idx


def paired(a, b, col):
    """Differences a-b on seeds present in both, finite in both."""
    d = []
    for sd, ra in a.items():
        rb = b.get(sd)
        if rb is None:
            continue
        x, y = ra.get(col), rb.get(col)
        if x is None or y is None:
            continue
        x, y = float(x), float(y)
        if np.isfinite(x) and np.isfinite(y):
            d.append(x - y)
    return np.array(d)


def ci95(d):
    return 1.96 * d.std(ddof=1) / np.sqrt(d.size)


def stars(p):
    return "***" if p < 1e-3 else "**" if p < 1e-2 else "*" if p < 0.05 else ""


def holm(pairs):
    """Holm-Bonferroni. pairs = [(label, p)] -> {label: corrected p}."""
    out, m = {}, len(pairs)
    run = 0.0
    for i, (lab, p) in enumerate(sorted(pairs, key=lambda t: t[1])):
        run = max(run, min(1.0, (m - i) * p))
        out[lab] = run
    return out


if __name__ == "__main__":
    rows, idx = load()
    speeds = sorted({r["speed"] for r in rows})
    print(f"{len(rows)} runs. speed levels present: "
          f"{', '.join(f'{s:g}' for s in speeds)}")
    # Report the realised seed count PER SPEED, not pooled. Taking a max across
    # speeds hid that 0.50 and 1.00 ran at n=100 while 0.25 ran at n=300, and
    # printed "no deviations" for a study that had two.
    n_by_speed = {sp: min(len(d) for k, d in idx.items()
                          if k[0] == "frontier" and k[1] == sp)
                  for sp in speeds}
    dev = [f"speed {sp:g}: n={n}/cell (protocol 300)"
           for sp, n in sorted(n_by_speed.items()) if n < 300]
    missing = {0.25, 0.5, 1.0} - set(speeds)
    if missing:
        dev.append("speed levels "
                   + ", ".join(f"{s:g}" for s in sorted(missing)) + " not run")
    print("PROTOCOL section 10 deviations in force: "
          + ("; ".join(dev) if dev else "NONE") )
    print("  seeds per cell: "
          + ", ".join(f"{sp:g}->{n}" for sp, n in sorted(n_by_speed.items())) + "\n")

    for sp in speeds:
        # ---------------- PRIMARY ENDPOINT (PROTOCOL section 2) -----------
        print("=" * 78)
        print(f"PRIMARY ENDPOINT - alarm-budget frontier, speed {sp:g}")
        print("=" * 78)
        print("Claim: proposed @45 alarms/run > threshold's MAXIMUM over its whole")
        print("sweep, CI excluding zero, in BOTH field x BOTH connectivity cells.\n")

        # threshold's best budget, chosen on the pooled mean (it saturates, so
        # every budget at or above the cap is the same run).
        best_b, best_m = None, -np.inf
        for b in (5, 11, 22, 45, 90):
            v = [float(r["on_time_ratio"])
                 for (st, s2, sc, cn, mk, bb), d in idx.items()
                 if st == "frontier" and s2 == sp and mk == "threshold" and bb == b
                 for r in d.values() if np.isfinite(float(r["on_time_ratio"]))]
            if v and np.mean(v) > best_m:
                best_b, best_m = b, float(np.mean(v))
        print(f"threshold's best budget = {best_b} (on-time {best_m:.3f})\n")

        print(f"{'cell':26s}{'proposed@45':>12s}{'thresh_max':>12s}"
              f"{'diff':>9s}{'95% CI':>18s}{'p':>10s}")
        verdicts = []
        for sc, cn in CELLS:
            A = idx[("frontier", sp, sc, cn, "proposed", 45)]
            B = idx[("frontier", sp, sc, cn, "threshold", best_b)]
            d = paired(A, B, "on_time_ratio")
            if d.size < 10:
                print(f"{sc[:5]+'/'+cn:26s}  insufficient data ({d.size})")
                verdicts.append(False)
                continue
            ma = np.mean([float(r["on_time_ratio"]) for r in A.values()])
            mb = np.mean([float(r["on_time_ratio"]) for r in B.values()])
            lo, hi = d.mean() - ci95(d), d.mean() + ci95(d)
            p = wilcoxon(d).pvalue
            ok = lo > 0
            verdicts.append(ok)
            print(f"{sc[:5]+'/'+cn:26s}{ma:12.3f}{mb:12.3f}{d.mean():+9.3f}"
                  f"  [{lo:+.3f},{hi:+.3f}]{p:10.1e} {stars(p)}"
                  f"{'' if ok else '   <-- CI includes 0'}")

        print(f"\n  VERDICT: {'SUPPORTED' if all(verdicts) else 'NOT SUPPORTED'}"
              f"  ({sum(verdicts)}/4 cells)")
        if not all(verdicts):
            print("  PROTOCOL section 2: a result in fewer than 4 cells is NOT")
            print("  supported; it is reported as partial and the claim is weakened.")

        # saturation evidence
        tv = {}
        for b in (5, 11, 22, 45, 90):
            v = [float(r["on_time_ratio"])
                 for (st, s2, sc, cn, mk, bb), dd in idx.items()
                 if st == "frontier" and s2 == sp and mk == "threshold" and bb == b
                 for r in dd.values()]
            fv = [float(r["n_fires"])
                  for (st, s2, sc, cn, mk, bb), dd in idx.items()
                  if st == "frontier" and s2 == sp and mk == "threshold" and bb == b
                  for r in dd.values()]
            tv[b] = (np.mean(fv), np.mean(v))
        print("\n  threshold saturation (PROTOCOL section 0):")
        print("    budget:  " + "".join(f"{b:>9d}" for b in tv))
        print("    fires:   " + "".join(f"{tv[b][0]:9.1f}" for b in tv))
        print("    on-time: " + "".join(f"{tv[b][1]:9.3f}" for b in tv))

        # ---------------- SECONDARY 1: matched budget ---------------------
        print("\n" + "=" * 78)
        print(f"SECONDARY 1 - matched alarm budget, speed {sp:g}")
        print("(retained because it is UNFAVOURABLE; PROTOCOL section 3)")
        print("=" * 78)
        others = ["fixed_dl", "threshold", "time_urg", "always_tx",
                  "surprise_abl", "raw_abl"]
        raw = {}
        for mk in others:
            d = np.concatenate([
                paired(idx[("matched", sp, sc, cn, "proposed", None)],
                       idx[("matched", sp, sc, cn, mk, None)], "on_time_ratio")
                for sc, cn in CELLS])
            raw[mk] = (d.mean(), ci95(d), wilcoxon(d).pvalue, d.size)
        cor = holm([(mk, v[2]) for mk, v in raw.items()])
        print(f"{'vs':14s}{'diff':>9s}{'95% CI':>18s}{'p':>11s}{'p(Holm)':>11s}{'n':>7s}")
        for mk in others:
            m, c, p, n = raw[mk]
            print(f"{mk:14s}{m:+9.3f}  [{m-c:+.3f},{m+c:+.3f}]{p:11.1e}"
                  f"{cor[mk]:11.1e} {stars(cor[mk]):3s}{n:7d}")

        # equivalence statement required by PROTOCOL section 6
        m, c, p, n = raw["surprise_abl"]
        print(f"\n  PROTOCOL section 6 - surprise_abl is pre-declared underpowered.")
        print(f"  Required statement: the effect, if any, lies in "
              f"[{m-c:+.3f}, {m+c:+.3f}] and is smaller than this study resolves.")
        print(f"  It is NOT reported as 'no effect'.")

        # ---------------- DIAGNOSTIC: are the endpoints one endpoint? -----
        print("\n" + "=" * 78)
        print("DIAGNOSTIC - is map RMSE independent of on-time? (PROTOCOL section 3)")
        print("=" * 78)
        ms = ["proposed"] + others
        ot, rm = [], []
        for mk in ms:
            v = [r for (st, s2, sc, cn, m2, bb), dd in idx.items()
                 if st == "matched" and s2 == sp and m2 == mk
                 for r in dd.values()]
            ot.append(np.nanmean([float(x["on_time_ratio"]) for x in v]))
            rm.append(np.nanmean([float(x["map_rmse"]) for x in v]))
        pr = pearsonr(ot, rm); sr = spearmanr(ot, rm)
        print(f"  across {len(ms)} methods: Pearson r={pr.statistic:+.3f} "
              f"p={pr.pvalue:.4f}, Spearman={sr.statistic:+.3f}")
        print("  (lower RMSE is better, so r > 0 means better delivery => worse map)")
        for mk, a, b in sorted(zip(ms, ot, rm), key=lambda t: -t[1]):
            print(f"    {mk:14s} on-time {a:.3f}   map RMSE {b:.4f}")
