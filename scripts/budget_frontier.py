"""Budget frontier: how do the proposed trigger and the threshold baseline
compare as a function of the ALARM BUDGET, not at one matched point?

Motivation. At 40x40 the matched-budget comparison (~11 fires/run against
~370 observable hazard events) is severely budget-starved: even the best
method detects ~12% of events. In that regime the optimal policy is simply
"spend every alarm on the most obviously hazardous reading", which is exactly
what the threshold baseline does, so it is unsurprising that it wins on
event timeliness. The interesting question is whether the proposed trigger
overtakes it once the obvious hazards are already covered.

For each method we first bisect the trigger level to hit a target fire rate,
then evaluate on-time ratio and map RMSE at that budget.

    .venv/bin/python scripts/budget_frontier.py
"""
import dataclasses, pathlib, sys, json
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import numpy as np
from urgency_sim.config import Config, with_scenario, with_conn
import urgency_sim.methods as mm
import urgency_sim.sim as ss
from urgency_sim.sim import run
from urgency_sim.metrics import summarise

SC = ["predictable", "unpredictable"]
CN = ["sparse", "dense"]
NS = 20                      # seeds per cell -> 4 * NS runs per point
TARGETS = [5, 11, 22, 45, 90]
METHODS = ["proposed", "threshold"]
# Bracket for the bisection, per method. Low trigger = many fires.
BRACKET = {"proposed": (0.05, 6.0), "threshold": (0.0, 1.2)}


def _one(a):
    cfg, sd, mk, trig = a
    M = dataclasses.replace(mm.METHODS[mk], trigger_level=trig)
    mm.METHODS[mk] = M
    ss.METHODS[mk] = M
    log = run(cfg, sd, mk)
    d = summarise(log)
    return d["n_fires"], d["on_time_ratio"], d["map_rmse"], d["false_alarm_rate"], d["detection_rate"]


def evaluate(mk, trig, seeds=NS):
    base = Config()
    jobs = [(with_conn(with_scenario(base, s), c), sd, mk, trig)
            for s in SC for c in CN for sd in range(seeds)]
    with ProcessPoolExecutor(max_workers=12) as ex:
        res = list(ex.map(_one, jobs))
    a = np.array(res, dtype=float)
    return dict(fires=float(np.nanmean(a[:, 0])),
                on_time=float(np.nanmean(a[:, 1])),
                rmse=float(np.nanmean(a[:, 2])),
                far=float(np.nanmean(a[:, 3])),
                det=float(np.nanmean(a[:, 4])),
                on_time_sem=float(np.nanstd(a[:, 1]) / np.sqrt(len(a))),
                rmse_sem=float(np.nanstd(a[:, 2]) / np.sqrt(len(a))))


def bisect_trigger(mk, target, iters=7, seeds=6):
    """Find the trigger whose fire rate is closest to `target`.

    Cheap seed count during the search (the fire rate is a much smoother
    function of the trigger than the outcome metrics are), then the chosen
    trigger is re-evaluated at full NS by the caller.
    """
    lo, hi = BRACKET[mk]
    best = None
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        f = evaluate(mk, mid, seeds=seeds)["fires"]
        if best is None or abs(f - target) < abs(best[1] - target):
            best = (mid, f)
        if f > target:          # too many fires -> raise the trigger
            lo = mid
        else:
            hi = mid
    return best[0]


if __name__ == "__main__":
    out = {}
    print(f"{'method':11s} {'target':>7s} {'trigger':>8s} {'fires':>7s} "
          f"{'on_time':>9s} {'+-':>6s} {'mapRMSE':>9s} {'+-':>6s} {'det':>6s} {'FAR':>6s}")
    for mk in METHODS:
        out[mk] = []
        for tg in TARGETS:
            tr = bisect_trigger(mk, tg)
            r = evaluate(mk, tr)
            r["trigger"], r["target"] = tr, tg
            out[mk].append(r)
            print(f"{mk:11s} {tg:7d} {tr:8.3f} {r['fires']:7.1f} "
                  f"{r['on_time']:9.3f} {r['on_time_sem']:6.3f} "
                  f"{r['rmse']:9.4f} {r['rmse_sem']:6.4f} "
                  f"{r['det']:6.3f} {r['far']:6.3f}")
    pathlib.Path("results").mkdir(exist_ok=True)
    json.dump(out, open("results/budget_frontier.json", "w"), indent=1)
    print("\nwrote results/budget_frontier.json")
