"""Phase 4 — graded deviation (Experiment A) and the static field (Experiment B).

Governed by results/phase4/PREREGISTRATION.md, frozen before any run. Shares the
crash-safe store and the resume semantics of scripts/phase3.py: interrupt at any
point and re-run the same command.

    .venv/bin/python scripts/phase4.py --plan
    .venv/bin/python scripts/phase4.py --exp A
    .venv/bin/python scripts/phase4.py            # both
"""
import argparse, dataclasses, json, pathlib, sys, time
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import numpy as np
from urgency_sim.config import (Config, with_conn, with_scenario, with_speed,
                                with_deviation)
from urgency_sim.manifest import config_hash, manifest
from urgency_sim.metrics import summarise
from urgency_sim.store import ResultStore, key
import urgency_sim.methods as mm
import urgency_sim.sim as ss
from urgency_sim.sim import run

CONNS = ["sparse", "dense"]
METHODS = ["proposed", "threshold"]
BUDGETS = [11, 45]
CALIB_SEED0, EVAL_SEED0 = 2000, 3000
BRACKET = {"proposed": (0.05, 6.0), "threshold": (0.0, 1.2)}
STORE = "results/phase4/runs.jsonl"
CALIB = pathlib.Path("results/phase4/calib")

# Experiment A: two arms sharing their origin at the predictable scenario.
A_WIND   = [(d, 0.0) for d in (0.0, 20.0, 40.0, 60.0, 80.2)]
A_SOURCE = [(0.0, f) for f in (0.5, 1.0)]        # (0,0) already in A_WIND
A_LEVELS = A_WIND + A_SOURCE
# Experiment B: static and near-static. decouple=False at 0 (see pre-reg).
B_LEVELS = [0.0, 0.1, 0.25]


def build(exp, level, conn):
    """The config for one (experiment, level, connectivity) point."""
    if exp == "A":
        shift, src = level
        cfg = with_deviation(with_speed(Config(), 0.25), shift, src)
    else:
        r = float(level)
        cfg = with_scenario(with_speed(Config(), r, decouple=(r > 0.0)),
                            "predictable")
    return with_conn(cfg, conn)


def _run_one(a):
    exp, level, conn, mk, trig, seed, budget = a
    cfg = build(exp, level, conn)
    if trig is not None:
        M = dataclasses.replace(mm.METHODS[mk], trigger_level=trig)
        mm.METHODS[mk] = M; ss.METHODS[mk] = M
    d = summarise(run(cfg, seed, mk))
    d.update(stage=f"p4{exp}", speed=lvl_tag(exp, level), scenario=f"exp{exp}",
             conn=conn, method=mk, seed=seed, budget=budget, trigger=trig,
             level=lvl_tag(exp, level))
    return d


def _fires(a):
    exp, level, conn, mk, trig, seed = a
    cfg = build(exp, level, conn)
    M = dataclasses.replace(mm.METHODS[mk], trigger_level=trig)
    mm.METHODS[mk] = M; ss.METHODS[mk] = M
    return len(run(cfg, seed, mk).fires)


def lvl_tag(exp, level):
    return f"w{level[0]:g}s{level[1]:g}" if exp == "A" else f"r{level:g}"


def rate(ex, exp, level, mk, trig, n):
    jobs = [(exp, level, c, mk, trig, CALIB_SEED0 + i)
            for c in CONNS for i in range(n)]
    return float(np.mean(list(ex.map(_fires, jobs, chunksize=1))))


def bisect(ex, exp, level, mk, target, n, iters=9):
    lo, hi = BRACKET[mk]; best = None
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        f = rate(ex, exp, level, mk, mid, n)
        if best is None or abs(f - target) < abs(best[1] - target):
            best = (mid, f)
        lo, hi = (mid, hi) if f > target else (lo, mid)
    return float(best[0]), float(best[1])


def calibrate(ex, exp, level, n):
    CALIB.mkdir(parents=True, exist_ok=True)
    tag = lvl_tag(exp, level)
    out = CALIB / f"{exp}_{tag}.json"
    h = config_hash(build(exp, level, "sparse"))
    if out.exists():
        prev = json.loads(out.read_text())
        if prev.get("cfg_hash") == h and prev.get("calib_n", 0) >= n:
            print(f"  [calib {exp} {tag}] cached"); return prev
    rec = dict(manifest(Config())); rec.update(cfg_hash=h, calib_n=n,
                                               level=tag, trig={}, got={})
    for mk in METHODS:
        for b in BUDGETS:
            t, g = bisect(ex, exp, level, mk, b, n)
            rec["trig"][f"{mk}|{b}"] = t; rec["got"][f"{mk}|{b}"] = g
            flag = "" if abs(g-b) <= 0.10*b else f"  ** {100*(g-b)/b:+.0f}% off **"
            print(f"  [calib {exp} {tag}] {mk:10s} b={b:3d} -> trig {t:.3f} "
                  f"-> {g:5.1f} fires{flag}")
    out.write_text(json.dumps(rec, indent=1))
    return rec


def execute(ex, st, done, exp, level, cal, nseeds):
    tag = lvl_tag(exp, level); jobs = []
    for mk in METHODS:
        for b in BUDGETS:
            t = cal["trig"][f"{mk}|{b}"]
            for c in CONNS:
                for i in range(nseeds):
                    sd = EVAL_SEED0 + i
                    if key(f"p4{exp}", 0.0, f"exp{exp}", c, mk, b, sd) in done:
                        continue
                    if (f"p4{exp}", tag, f"exp{exp}", c, mk, f"{b:g}", sd) in done:
                        continue
                    jobs.append((exp, level, c, mk, t, sd, b))
    if not jobs:
        print(f"  [{exp} {tag}] already complete"); return
    t0 = 0; n = 0
    import time as _t; t0 = _t.time()
    for d in ex.map(_run_one, jobs, chunksize=1):
        st.append(d); n += 1
        if n % 100 == 0 or n == len(jobs):
            el = _t.time() - t0
            print(f"  [{exp} {tag}] {n}/{len(jobs)}  {el/60:.1f} min, "
                  f"{el/n*(len(jobs)-n)/60:.1f} left", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp", choices=["A", "B"], default=None)
    ap.add_argument("--seeds", type=int, default=100)
    ap.add_argument("--calib-seeds", type=int, default=8)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--plan", action="store_true")
    a = ap.parse_args()

    store = ResultStore(STORE)
    done = {(r["stage"], r.get("level"), r["scenario"], r["conn"],
             r["method"], f"{r['budget']:g}", r["seed"]) for r in store.rows()}
    plan = [("A", l) for l in A_LEVELS] if a.exp != "B" else []
    plan += [("B", l) for l in B_LEVELS] if a.exp != "A" else []
    per = len(METHODS) * len(BUDGETS) * len(CONNS)
    if a.plan:
        tot = 0
        for exp, l in plan:
            ev = per * a.seeds
            cal = per * 9 * len(CONNS) * a.calib_seeds // len(CONNS) * len(CONNS)
            cal = len(METHODS)*len(BUDGETS)*9*len(CONNS)*a.calib_seeds
            tot += ev + cal
            print(f"  {exp} {lvl_tag(exp,l):10s} calib {cal:5d} + eval {ev:5d}")
        print(f"\ntotal {tot} runs, ~{tot*3.5/a.workers/60:.0f} min at {a.workers} workers")
        sys.exit(0)

    print(f"store {STORE}: {len(done)} runs already complete\n")
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as ex, store as st:
        for exp, l in plan:
            print(f"--- Experiment {exp}, level {lvl_tag(exp,l)} ---")
            cal = calibrate(ex, exp, l, a.calib_seeds)
            execute(ex, st, done, exp, l, cal, a.seeds)
    print(f"\ntotal {(time.time()-t0)/60:.1f} min")
