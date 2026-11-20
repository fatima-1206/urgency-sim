"""Phase 3 — the study of record. Resumable, and shippable in slices.

Governed by PROTOCOL.md, which is frozen. This script does not decide anything;
it executes what the protocol fixed.

TWO PROPERTIES THIS SCRIPT IS BUILT AROUND
------------------------------------------
1. **Crash safety.** Every completed run is fsync'd to a JSONL store before the
   next one starts, so an interruption costs at most one run (~1.5 s). Re-running
   the same command resumes: finished runs are skipped. There is no "resume"
   flag to remember -- resuming is the default and the only behaviour.

2. **Minimal slice first.** Work is ordered so that ONE COMPLETE SPEED LEVEL
   finishes before the next one starts, and within a level the calibration and
   the matched-budget comparison finish before the (much longer) frontier. So
   the study produces a complete, reportable result early and keeps producing
   them, instead of producing nothing until it is all done.

   Level 0.25 runs first: it is the level nearest the simulator's native
   operating point (0.32), so the first shippable slice is the most relevant one.

USAGE
-----
    .venv/bin/python scripts/phase3.py --plan              # what would run
    .venv/bin/python scripts/phase3.py --speed 0.25        # the first slice
    .venv/bin/python scripts/phase3.py                     # everything, in order
    .venv/bin/python scripts/phase3.py --report            # summarise what is done

Kill it at any point with Ctrl-C and run the same command again.
"""
import argparse
import dataclasses
import pathlib
import sys
import time
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import numpy as np

from urgency_sim.config import Config, with_conn, with_scenario, with_speed
from urgency_sim.manifest import config_hash, manifest
from urgency_sim.metrics import summarise
from urgency_sim.store import ResultStore, key
import urgency_sim.methods as mm
import urgency_sim.sim as ss
from urgency_sim.sim import run

# ---------------------------------------------------------------- protocol
# PROTOCOL.md section 5: factors. 0.10 is excluded there, with its reason.
# Ordered so the slice nearest the native operating point (0.32) ships first.
SPEEDS = [0.25, 0.50, 1.00]
SCENARIOS = ["predictable", "unpredictable"]
CONNS = ["sparse", "dense"]
METHODS = ["proposed", "fixed_dl", "threshold", "time_urg", "always_tx",
           "surprise_abl", "raw_abl"]

# PROTOCOL.md section 2: budget targets, fixed.
BUDGETS = [5, 11, 22, 45, 90]
FRONTIER_METHODS = ["proposed", "threshold"]

# PROTOCOL.md section 6: seed blocks. Calibration and evaluation are disjoint.
CALIB_SEED0, CALIB_N = 2000, 20
EVAL_SEED0, EVAL_N = 3000, 300

# PROTOCOL.md section 8: bisection bracket per method.
BRACKET = {"proposed": (0.05, 6.0), "threshold": (0.0, 1.2),
           "surprise_abl": (0.05, 6.0), "raw_abl": (0.02, 2.0),
           "time_urg": (0.1, 6.0)}

# Measured end-to-end on the 0.25 dry run: ~170 runs/min at 10 workers
# => ~3.5 s of CPU per run. Higher speed levels need more integrator substeps
# (3 at 0.75, 4 at 1.5), so 0.50 and 1.00 cost roughly 1.3x and 1.6x this.
SEC_PER_RUN = 3.5
SPEED_COST = {0.25: 1.0, 0.50: 1.3, 1.00: 1.6}
STORE = "results/phase3/runs.jsonl"
CALIB_DIR = pathlib.Path("results/phase3/calib")


# ---------------------------------------------------------------- workers
def _run_one(a):
    """One mission. Returns (identity, summary) so the parent can write it."""
    speed, scen, conn, mk, trig, seed, stage, budget = a
    cfg = with_conn(with_scenario(with_speed(Config(), speed), scen), conn)
    if trig is not None:
        M = dataclasses.replace(mm.METHODS[mk], trigger_level=trig)
        mm.METHODS[mk] = M
        ss.METHODS[mk] = M
    d = summarise(run(cfg, seed, mk))
    d.update(stage=stage, speed=speed, scenario=scen, conn=conn,
             method=mk, seed=seed, budget=budget, trigger=trig)
    return d


def _fires_only(a):
    """Fire count only -- used by the calibration bisection, which does not
    need the metrics and should not pay for them."""
    speed, scen, conn, mk, trig, seed = a
    cfg = with_conn(with_scenario(with_speed(Config(), speed), scen), conn)
    M = dataclasses.replace(mm.METHODS[mk], trigger_level=trig)
    mm.METHODS[mk] = M
    ss.METHODS[mk] = M
    return len(run(cfg, seed, mk).fires)


def _fire_rate(ex, speed, mk, trig, n):
    jobs = [(speed, s, c, mk, trig, CALIB_SEED0 + i)
            for s in SCENARIOS for c in CONNS for i in range(n)]
    return float(np.mean(list(ex.map(_fires_only, jobs, chunksize=1))))


# ---------------------------------------------------------------- stages
def stage_calibrate(ex, speed, calib_n):
    """PROTOCOL.md section 8. Cached per speed level: calibration is
    deterministic given the config, so once written it is never redone."""
    CALIB_DIR.mkdir(parents=True, exist_ok=True)
    out = CALIB_DIR / f"speed_{speed:g}.json"
    cfg_hash = config_hash(with_speed(Config(), speed))
    if out.exists():
        import json
        prev = json.loads(out.read_text())
        if (prev.get("cfg_hash") == cfg_hash
                and prev.get("calib_n", 0) >= calib_n):
            print(f"  [calib {speed:g}] cached")
            return prev
        print(f"  [calib {speed:g}] config changed -- recalibrating")

    print(f"  [calib {speed:g}] reference budget ...")
    ref = _fire_rate(ex, speed, "threshold", 0.0, calib_n)
    print(f"  [calib {speed:g}] reference = {ref:.1f} fires/run")

    def _flag(got, want):
        return "" if abs(got - want) <= 0.10 * want else \
            f"   ** {100*(got-want)/want:+.0f}% off target **"

    matched, matched_rate = {"threshold": 0.0}, {"threshold": ref}
    for mk in ["proposed", "surprise_abl", "raw_abl", "time_urg"]:
        matched[mk], matched_rate[mk] = _bisect(ex, speed, mk, ref, calib_n)
        print(f"  [calib {speed:g}] {mk:13s} trigger {matched[mk]:.3f}"
              f"  -> {matched_rate[mk]:5.1f} fires{_flag(matched_rate[mk], ref)}")

    frontier, frontier_rate = {}, {}
    for mk in FRONTIER_METHODS:
        frontier[mk], frontier_rate[mk] = {}, {}
        for b in BUDGETS:
            tr, got = _bisect(ex, speed, mk, b, max(4, calib_n // 2))
            frontier[mk][str(b)], frontier_rate[mk][str(b)] = tr, got
            print(f"  [calib {speed:g}] {mk:13s} budget {b:3d} "
                  f"-> trigger {tr:.3f}  -> {got:5.1f} fires{_flag(got, b)}")

    import json
    # manifest() already carries a cfg_hash (of the BASE config); the one we
    # key on is the speed-adjusted config, so it is set after the splat.
    rec = dict(manifest(Config()))
    rec.update(speed=speed, cfg_hash=cfg_hash, reference=ref, calib_n=calib_n,
               matched=matched, matched_rate=matched_rate,
               frontier=frontier, frontier_rate=frontier_rate)
    out.write_text(json.dumps(rec, indent=1))
    return rec


def _bisect(ex, speed, mk, target, n, iters=9):
    """Returns (trigger, achieved_fire_rate).

    The achieved rate is returned, never assumed: a trigger is a continuous
    knob but the fire rate it produces is not, so some targets are simply
    unreachable. `threshold` in particular cannot exceed ~10 fires/run at any
    trigger (FEASIBILITY_REPORT section 11), and at low budgets its rate steps
    rather than slides. PROTOCOL section 8 requires the achieved rate to be
    reported in every table; callers flag anything more than 10% off target.
    """
    lo, hi = BRACKET[mk]
    best = None
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        f = _fire_rate(ex, speed, mk, mid, n)
        if best is None or abs(f - target) < abs(best[1] - target):
            best = (mid, f)
        if f > target:
            lo = mid            # too many fires -> raise the trigger
        else:
            hi = mid
    return float(best[0]), float(best[1])


def _execute(ex, store, jobs, label):
    """Run `jobs`, writing each result the moment it lands. This is the whole
    crash-safety story: results are never held in memory waiting for a batch."""
    if not jobs:
        print(f"  [{label}] already complete")
        return 0
    t0, n = time.time(), 0
    for d in ex.map(_run_one, jobs, chunksize=1):
        store.append(d)
        n += 1
        if n % 50 == 0 or n == len(jobs):
            el = time.time() - t0
            eta = el / n * (len(jobs) - n)
            print(f"  [{label}] {n}/{len(jobs)}  {el/60:.1f} min elapsed, "
                  f"{eta/60:.1f} min left", flush=True)
    return n


def stage_matched(ex, store, done, speed, calib, nseeds, cfg_hash):
    """PROTOCOL.md section 3, secondary endpoint 1."""
    jobs = []
    for mk in METHODS:
        trig = calib["matched"].get(mk)
        for scen in SCENARIOS:
            for conn in CONNS:
                for i in range(nseeds):
                    sd = EVAL_SEED0 + i
                    k = key("matched", speed, scen, conn, mk, None, sd)
                    if k in done:
                        continue
                    jobs.append((speed, scen, conn, mk, trig, sd,
                                 "matched", None))
    return _execute(ex, store, jobs, f"matched {speed:g}")


def stage_frontier(ex, store, done, speed, calib, nseeds, cfg_hash):
    """PROTOCOL.md section 2, the primary endpoint."""
    jobs = []
    for mk in FRONTIER_METHODS:
        for b in BUDGETS:
            trig = calib["frontier"][mk][str(b)]
            for scen in SCENARIOS:
                for conn in CONNS:
                    for i in range(nseeds):
                        sd = EVAL_SEED0 + i
                        k = key("frontier", speed, scen, conn, mk, b, sd)
                        if k in done:
                            continue
                        jobs.append((speed, scen, conn, mk, trig, sd,
                                     "frontier", b))
    return _execute(ex, store, jobs, f"frontier {speed:g}")


# ---------------------------------------------------------------- reporting
def report(store):
    import collections
    rows = list(store.rows())
    if not rows:
        print("nothing run yet")
        return
    cnt = collections.Counter((r["stage"], r["speed"]) for r in rows)
    print(f"{len(rows)} runs on disk\n")
    print(f"{'stage':10s}{'speed':>7s}{'runs':>9s}{'complete':>11s}")
    for (stage, speed), n in sorted(cnt.items()):
        if stage == "matched":
            want = len(METHODS) * len(SCENARIOS) * len(CONNS) * EVAL_N
        else:
            want = (len(FRONTIER_METHODS) * len(BUDGETS)
                    * len(SCENARIOS) * len(CONNS) * EVAL_N)
        print(f"{stage:10s}{speed:7g}{n:9d}{100*n/want:10.1f}%")

    # Primary endpoint, as far as it is computed.
    front = [r for r in rows if r["stage"] == "frontier"]
    if front:
        print("\n--- primary endpoint: alarm-budget frontier (PROTOCOL section 2) ---")
        g = collections.defaultdict(list)
        for r in front:
            g[(r["speed"], r["method"], r["budget"])].append(r)
        print(f"{'speed':>6s}{'method':>11s}{'budget':>8s}{'fires':>8s}"
              f"{'on_time':>9s}{'+-':>7s}{'n':>6s}")
        for (sp, mk, b), v in sorted(g.items()):
            ot = np.array([x["on_time_ratio"] for x in v], dtype=float)
            ot = ot[np.isfinite(ot)]
            fr = np.nanmean([x["n_fires"] for x in v])
            print(f"{sp:6g}{mk:>11s}{b:8g}{fr:8.1f}{ot.mean():9.3f}"
                  f"{1.96*ot.std(ddof=1)/np.sqrt(ot.size):7.3f}{ot.size:6d}")


# ---------------------------------------------------------------- main
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--speed", type=float, default=None,
                    help="run only this speed level (default: all, in order)")
    ap.add_argument("--stage", choices=["calibrate", "matched", "frontier"],
                    default=None, help="run only this stage")
    ap.add_argument("--seeds", type=int, default=EVAL_N,
                    help=f"evaluation seeds per cell (protocol: {EVAL_N})")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--calib-seeds", type=int, default=CALIB_N,
                    help=f"calibration seeds per cell (protocol minimum: {CALIB_N})")
    ap.add_argument("--store", default=STORE)
    ap.add_argument("--plan", action="store_true",
                    help="print what would run, run nothing")
    ap.add_argument("--report", action="store_true",
                    help="summarise what is already on disk")
    a = ap.parse_args()

    store = ResultStore(a.store)
    if a.report:
        report(store)
        sys.exit(0)

    if a.seeds != EVAL_N or a.calib_seeds < CALIB_N:
        print(f"!! --seeds {a.seeds} (protocol {EVAL_N}), --calib-seeds "
              f"{a.calib_seeds} (protocol minimum {CALIB_N}).\n"
              f"!! This is a pilot pass, NOT the study of record. PROTOCOL.md "
              f"section 9 requires pass 2 at full size.\n")

    speeds = [a.speed] if a.speed is not None else SPEEDS
    cfg_hash = config_hash(Config())
    done = store.done_keys()
    print(f"store: {a.store}   {len(done)} runs already complete")
    print(f"git {manifest(Config())['git_sha']}   cfg {cfg_hash}\n")

    if a.plan:
        total = 0.0
        ncell = len(SCENARIOS) * len(CONNS)
        for sp in speeds:
            m = len(METHODS) * ncell * a.seeds
            f = len(FRONTIER_METHODS) * len(BUDGETS) * ncell * a.seeds
            md = sum(1 for k in done if k[0] == "matched" and k[1] == f"{sp:g}")
            fd = sum(1 for k in done if k[0] == "frontier" and k[1] == f"{sp:g}")
            # calibration: reference + 4 matched bisections + the frontier ones
            cal, cf = 0, CALIB_DIR / f"speed_{sp:g}.json"
            cached = False
            if cf.exists():
                import json as _j
                _p = _j.loads(cf.read_text())
                cached = (_p.get("cfg_hash")
                          == config_hash(with_speed(Config(), sp))
                          and _p.get("calib_n", 0) >= a.calib_seeds)
            if not cached:
                cal = (ncell * a.calib_seeds
                       + 4 * 9 * ncell * a.calib_seeds
                       + len(FRONTIER_METHODS) * len(BUDGETS) * 9
                         * ncell * max(4, a.calib_seeds // 2))
            cost = SPEED_COST.get(sp, 1.6)
            mins = SEC_PER_RUN * cost * (cal + m - md + f - fd) / a.workers / 60
            total += mins
            print(f"speed {sp:g}: calib {cal:6d} | matched {m-md:6d}/{m} | "
                  f"frontier {f-fd:6d}/{f}   ~{mins/60:.1f} h")
        print(f"\ntotal ~{total/60:.1f} h at {a.workers} workers "
              f"(pass 1 + pass 2 => ~{2*total/60:.0f} h, PROTOCOL section 9)")
        sys.exit(0)

    t0 = time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as ex, store as st:
        for sp in speeds:
            print(f"\n{'='*70}\nSPEED LEVEL {sp:g}\n{'='*70}")
            calib = stage_calibrate(ex, sp, a.calib_seeds)
            if a.stage == "calibrate":
                continue
            # Matched budget first: it is the smaller stage, so the slice
            # becomes reportable sooner.
            if a.stage in (None, "matched"):
                stage_matched(ex, st, done, sp, calib, a.seeds, cfg_hash)
            if a.stage in (None, "frontier"):
                stage_frontier(ex, st, done, sp, calib, a.seeds, cfg_hash)
            print(f"  SPEED {sp:g} COMPLETE -- this slice is reportable on its own")
    print(f"\ntotal {(time.time()-t0)/60:.1f} min")
    report(store)
