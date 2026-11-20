"""Shared harness for the experiment programme.

Every experiment is a declaration -- a list of levels and a function turning a
level into a Config -- and this module supplies everything else: per-level
trigger calibration, crash-safe resumable execution, and archiving.

It reuses rather than reimplements:
  urgency_sim.store     crash-safe append-only store, proven under SIGKILL
  urgency_sim.manifest  git SHA + config hash + library versions per row
  urgency_sim.metrics   summarise()
The bisection and resume loops are lifted from scripts/phase3.py and
scripts/phase4.py, which carried near-identical copies of both.

Governed by PROTOCOL_EXPERIMENTS.md. This module decides nothing the protocol
has not already fixed.
"""
from __future__ import annotations

import dataclasses
import json
import pathlib
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import numpy as np

from urgency_sim.config import Config
from urgency_sim.manifest import config_hash, manifest
from urgency_sim.metrics import summarise
from urgency_sim.store import ResultStore
import urgency_sim.methods as mm
import urgency_sim.sim as ss
from urgency_sim.sim import run

# PROTOCOL_EXPERIMENTS.md section 3: seed blocks, disjoint from every earlier
# phase (pilot 0-199, Phase 2 sweep 1000-1029, Phase 3 2000-3299).
CALIB_SEED0 = 5000
EVAL_SEED0 = 6000
REPLICATE_SEED0 = 7000

# Bisection brackets. The FLOOR MUST BE 0.0 for every content trigger: with a
# floor of 0.05 and 9 iterations the search could never go below ~0.065, which
# made the proposed method look as though it saturated at 138.5 alarms/run when
# its real ceiling at trigger 0 is ~150. A bracket artefact reported as a
# ceiling would have been a fabricated finding.
BRACKET = {
    "proposed": (0.0, 8.0), "threshold": (0.0, 1.2),
    # The decoupled baseline fires on the raw reading, so its bracket is in
    # concentration units and must reach down to 0 (fire on everything) and up
    # past the field maximum (fire on nothing).
    "threshold_dec": (0.0, 1.5),
    "surprise_abl": (0.0, 8.0), "raw_abl": (0.0, 3.0),
    "time_urg": (0.0, 8.0), "fixed_dl": (0.0, 8.0), "always_tx": (0.0, 8.0),
}

ROOT = pathlib.Path("results/experiments")
# Measured ~170 runs/min at 10 workers on the Phase 3 configuration.
SEC_PER_RUN = 3.5


@dataclass(frozen=True)
class Experiment:
    """One experiment. `build` is the only thing that varies between them."""
    eid: str
    title: str
    levels: Sequence[Any]
    tag: Callable[[Any], str]
    build: Callable[[Any, str, str], Config]      # (level, scenario, conn)
    question: str = ""
    methods: Sequence[str] = ("proposed", "threshold")
    budgets: Sequence[int] = (11, 45)
    conns: Sequence[str] = ("sparse", "dense")
    scenarios: Sequence[str] = ("predictable", "unpredictable")
    seeds: int = 100
    seed0: int = EVAL_SEED0
    # 20, not 8. Phase 1 measured that 5 calibration seeds gave triggers up to
    # 24% off budget, and raised its own calibration to 20; this programme then
    # shipped at 8, which is below that standard and had to be flagged in the
    # results. Changing this INVALIDATES cached calibrations (`calibrate` keys
    # on calib_n) and therefore invalidates runs made with the old triggers --
    # see _check_triggers, which refuses to mix them rather than silently
    # appending to a store whose rows were produced at a different trigger.
    calib_seeds: int = 20
    cost: Callable[[Any], float] = lambda _l: 1.0

    @property
    def dir(self) -> pathlib.Path:
        return ROOT / self.eid

    @property
    def store_path(self) -> pathlib.Path:
        return self.dir / "runs.jsonl"

    def cells(self) -> list:
        return [(s, c) for s in self.scenarios for c in self.conns]


# ---------------------------------------------------------------- workers
def _apply(mk: str, trig):
    if trig is not None:
        M = dataclasses.replace(mm.METHODS[mk], trigger_level=float(trig))
        mm.METHODS[mk] = M
        ss.METHODS[mk] = M


_SPEC: dict = {}


def _register(exp: Experiment):
    """Workers are separate processes, so they need the build function. The
    experiment module is importable, so they re-import it by name."""
    _SPEC["mod"] = exp.build


def _one(a):
    eid, build, level, scen, conn, mk, trig, seed, budget, tag = a
    cfg = build(level, scen, conn)
    _apply(mk, trig)
    d = summarise(run(cfg, seed, mk))
    d.update(eid=eid, level=tag, scenario=scen, conn=conn, method=mk,
             seed=seed, budget=budget, trigger=trig,
             stage=eid, speed=0.0)          # store.key() compatibility
    return d


def _fires(a):
    build, level, scen, conn, mk, trig, seed = a
    cfg = build(level, scen, conn)
    _apply(mk, trig)
    return len(run(cfg, seed, mk).fires)


# ---------------------------------------------------------------- calibration
def _rate(ex, exp, level, mk, trig, n):
    jobs = [(exp.build, level, s, c, mk, trig, CALIB_SEED0 + i)
            for s in exp.scenarios for c in exp.conns for i in range(n)]
    return float(np.mean(list(ex.map(_fires, jobs, chunksize=1))))


def _bisect(ex, exp, level, mk, target, n, iters=9):
    """Returns (trigger, achieved_rate). The achieved rate is RETURNED, never
    assumed: a trigger is continuous but the fire rate it produces is not, and
    the threshold baseline cannot exceed ~10 alarms/run at any setting."""
    lo, hi = BRACKET[mk]
    best = None
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        f = _rate(ex, exp, level, mk, mid, n)
        if best is None or abs(f - target) < abs(best[1] - target):
            best = (mid, f)
        lo, hi = (mid, hi) if f > target else (lo, mid)
    return float(best[0]), float(best[1])


def calibrate(ex, exp: Experiment, level) -> dict:
    """Per level: triggers shift when the regime changes. Cached on config hash
    AND calibration size, so a cheap smoke pass can never be reused by a real
    one -- the fault that invalidated the first Phase 3 run."""
    d = exp.dir / "calib"
    d.mkdir(parents=True, exist_ok=True)
    tag = exp.tag(level)
    out = d / f"{tag}.json"
    h = config_hash(exp.build(level, exp.scenarios[0], exp.conns[0]))
    if out.exists():
        prev = json.loads(out.read_text())
        if prev.get("cfg_hash") == h and prev.get("calib_n", 0) >= exp.calib_seeds:
            print(f"  [calib {tag}] cached")
            return prev
    rec = dict(manifest(Config()))
    rec.update(cfg_hash=h, calib_n=exp.calib_seeds, level=tag,
               trig={}, got={}, off_budget=[])
    for mk in exp.methods:
        for b in exp.budgets:
            t, g = _bisect(ex, exp, level, mk, b, exp.calib_seeds)
            rec["trig"][f"{mk}|{b}"] = t
            rec["got"][f"{mk}|{b}"] = g
            off = abs(g - b) > 0.10 * b
            if off:
                rec["off_budget"].append(f"{mk}|{b}")
            print(f"  [calib {tag}] {mk:13s} b={b:4d} -> trig {t:.4f} -> "
                  f"{g:6.1f} fires"
                  + (f"   ** {100*(g-b)/b:+.0f}% OFF TARGET **" if off else ""))
    out.write_text(json.dumps(rec, indent=1))
    return rec


# ---------------------------------------------------------------- execution
def _done_keys(exp: Experiment) -> set:
    return {(r.get("level"), r["scenario"], r["conn"], r["method"],
             f"{r['budget']:g}", r["seed"]) for r in ResultStore(exp.store_path).rows()}


def plan(exp: Experiment, workers: int = 10) -> float:
    done = _done_keys(exp)
    total_min = 0.0
    print(f"{exp.eid} -- {exp.title}")
    for lv in exp.levels:
        tag = exp.tag(lv)
        ev = sum(1 for mk in exp.methods for b in exp.budgets
                 for s, c in exp.cells() for i in range(exp.seeds)
                 if (tag, s, c, mk, f"{b:g}", exp.seed0 + i) not in done)
        cal = 0
        cf = exp.dir / "calib" / f"{tag}.json"
        if not cf.exists():
            cal = (len(exp.methods) * len(exp.budgets) * 9
                   * len(exp.cells()) * exp.calib_seeds)
        mins = SEC_PER_RUN * exp.cost(lv) * (ev + cal) / workers / 60
        total_min += mins
        print(f"   {tag:14s} calib {cal:6d} + eval {ev:6d}  ~{mins:5.0f} min"
              f"   (cost x{exp.cost(lv):.1f})")
    print(f"   TOTAL ~{total_min/60:.1f} h at {workers} workers\n")
    return total_min


class _Tee:
    """Mirror stdout into the experiment's own log, so the console record is
    committed with the data rather than living only in a terminal."""

    def __init__(self, path):
        self.f = open(path, "a", buffering=1)
        self.out = sys.stdout

    def write(self, s):
        self.out.write(s)
        self.f.write(s)

    def flush(self):
        self.out.flush()
        self.f.flush()

    def close(self):
        self.f.close()


def run_experiment(exp: Experiment, workers: int = 10, dry: bool = False):
    exp.dir.mkdir(parents=True, exist_ok=True)
    if dry:
        plan(exp, workers)
        return
    tee = _Tee(exp.dir / "run.log")
    real_stdout = sys.stdout
    sys.stdout = tee
    try:
        _run_experiment(exp, workers)
    finally:
        sys.stdout = real_stdout
        tee.close()


def _check_triggers(exp: Experiment, level, cal: dict) -> None:
    """Refuse to append runs at a trigger that differs from the one the stored
    rows were produced at.

    store.key() does NOT include the trigger, so a row is "done" purely on
    (level, scenario, conn, method, budget, seed). If a calibration is redone
    -- a different calib_seeds, a changed config, a widened bracket -- the new
    trigger would apply only to the runs not yet done, and the store would hold
    a silent mixture of two operating points under one label. That is the kind
    of fault that invalidated the first Phase 3 run, and it would be invisible
    in every table generated afterwards.
    """
    tag = exp.tag(level)
    seen = {}
    for r in ResultStore(exp.store_path).rows():
        if r.get("level") != tag:
            continue
        seen.setdefault((r["method"], f"{r['budget']:g}"), set()).add(
            round(float(r["trigger"]), 10))
    bad = []
    for mk in exp.methods:
        for b in exp.budgets:
            k = (mk, f"{b:g}")
            if k not in seen:
                continue
            new = round(float(cal["trig"][f"{mk}|{b}"]), 10)
            old = seen[k]
            if old != {new}:
                bad.append(f"    {tag} {mk}@{b}: stored {sorted(old)} "
                           f"but calibration now says {new}")
    if bad:
        raise SystemExit(
            f"\nREFUSING TO RUN: {exp.eid} level {tag} already holds runs made "
            f"at a different trigger.\n" + "\n".join(bad) +
            "\n\n  The store cannot hold two operating points under one label. "
            "Either\n  restore the previous calibration, or run this under a new "
            "eid so the\n  old data stays intact and the two are comparable.\n")


def _run_experiment(exp: Experiment, workers: int = 10):
    done = _done_keys(exp)
    store = ResultStore(exp.store_path)
    print(f"=== {exp.eid}: {exp.title} ===")
    if exp.question:
        print(f"    {exp.question}")
    print(f"    {len(done)} runs already complete\n")
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=workers) as ex, store as st:
        for lv in exp.levels:
            tag = exp.tag(lv)
            print(f"--- level {tag} ---")
            cal = calibrate(ex, exp, lv)
            _check_triggers(exp, lv, cal)
            jobs = []
            for mk in exp.methods:
                for b in exp.budgets:
                    trig = cal["trig"][f"{mk}|{b}"]
                    for s, c in exp.cells():
                        for i in range(exp.seeds):
                            sd = exp.seed0 + i
                            if (tag, s, c, mk, f"{b:g}", sd) in done:
                                continue
                            jobs.append((exp.eid, exp.build, lv, s, c, mk,
                                         trig, sd, b, tag))
            if not jobs:
                print(f"  [{tag}] already complete")
                continue
            n, tl = 0, time.time()
            for d in ex.map(_one, jobs, chunksize=1):
                st.append(d)
                n += 1
                if n % 200 == 0 or n == len(jobs):
                    el = time.time() - tl
                    print(f"  [{tag}] {n}/{len(jobs)}  {el/60:.1f} min, "
                          f"{el/n*(len(jobs)-n)/60:.1f} left", flush=True)
            print(f"  [{tag}] done")
    print(f"\n{exp.eid} total {(time.time()-t0)/60:.1f} min")


# ---------------------------------------------------------------- archiving
def archive(exp: Experiment):
    """Gzip the store so it can be committed (plain .jsonl is gitignored).
    ResultStore reads the .gz transparently, so analysis still works from a
    fresh clone with no extra step."""
    import gzip
    import shutil
    p = exp.store_path
    if not p.exists():
        print(f"{exp.eid}: nothing to archive")
        return
    gz = p.with_suffix(p.suffix + ".gz")
    with p.open("rb") as fi, gzip.open(gz, "wb", compresslevel=9) as fo:
        shutil.copyfileobj(fi, fo)
    print(f"{exp.eid}: {p.stat().st_size/1e6:.1f} MB -> "
          f"{gz.stat().st_size/1e6:.1f} MB  {gz}")
    write_summary(exp)
    update_index()


def write_summary(exp: Experiment):
    """A per-experiment RESULTS.md with the co-primary endpoints and the
    calibration audit, so the repo carries readable results beside the data."""
    import collections
    from scipy.stats import wilcoxon

    rows = list(ResultStore(exp.store_path).rows())
    if not rows:
        return
    idx = collections.defaultdict(dict)
    for r in rows:
        idx[(r.get("level"), r["scenario"], r["conn"], r["method"],
             f"{r['budget']:g}")][r["seed"]] = r

    def paired(a, b, col):
        d = [float(a[s][col]) - float(b[s][col]) for s in a if s in b
             and a[s].get(col) is not None and b[s].get(col) is not None
             and np.isfinite(float(a[s][col])) and np.isfinite(float(b[s][col]))]
        return np.array(d)

    L = [f"# {exp.eid} — {exp.title}", ""]
    if exp.question:
        L += [f"> {exp.question}", ""]
    L += [f"{len(rows)} runs. Generated by `scripts/experiments/analyse.py`; "
          f"regenerates from the committed `.gz` with no re-simulation.", ""]

    # calibration audit
    L += ["## Calibration audit", "",
          "| level | method / budget | trigger | achieved | flag |", "|---|---|---|---|---|"]
    for lv in exp.levels:
        f = exp.dir / "calib" / f"{exp.tag(lv)}.json"
        if not f.exists():
            continue
        rec = json.loads(f.read_text())
        for k, t in rec["trig"].items():
            got = rec["got"][k]
            tgt = float(k.split("|")[1])
            off = abs(got - tgt) > 0.10 * tgt
            L.append(f"| {exp.tag(lv)} | {k.replace('|', ' @ ')} | {t:.4f} | {got:.1f} | "
                     f"{'**%+.0f%% OFF**' % (100*(got-tgt)/tgt) if off else 'ok'} |")
    L.append("")

    base = exp.methods[0]
    for col, better in (("on_time_ratio", "higher is better"),
                        ("mean_latency", "lower is better")):
        L += [f"## {col} ({better})", "",
              "| level | scenario/conn | budget | " + base
              + " | other | diff | 95% CI | p |", "|---|---|---|---|---|---|---|---|"]
        for lv in exp.levels:
            for scen, conn in exp.cells():
                for b in exp.budgets:
                    A = idx[(exp.tag(lv), scen, conn, base, f"{b:g}")]
                    for mk in exp.methods[1:]:
                        B = idx[(exp.tag(lv), scen, conn, mk, f"{b:g}")]
                        d = paired(A, B, col)
                        if d.size < 10:
                            continue
                        ci = 1.96 * d.std(ddof=1) / np.sqrt(d.size)
                        pv = wilcoxon(d).pvalue
                        ma = np.nanmean([float(r[col]) for r in A.values()
                                         if np.isfinite(float(r[col]))])
                        mb = np.nanmean([float(r[col]) for r in B.values()
                                         if np.isfinite(float(r[col]))])
                        L.append(f"| {exp.tag(lv)} | {scen[:5]}/{conn} | {b} | "
                                 f"{ma:.3f} | {mb:.3f} | {d.mean():+.3f} | "
                                 f"[{d.mean()-ci:+.3f}, {d.mean()+ci:+.3f}] | {pv:.1e} |")
        L.append("")
    (exp.dir / "RESULTS.md").write_text("\n".join(L) + "\n")


def update_index():
    """Status table across every experiment with data on disk."""
    ROOT.mkdir(parents=True, exist_ok=True)
    L = ["# Experiment programme — index", "",
         "Governed by [PROTOCOL_EXPERIMENTS.md](../../PROTOCOL_EXPERIMENTS.md), "
         "frozen before any run.", "",
         "| experiment | runs | levels | archive | results |", "|---|---|---|---|---|"]
    for d in sorted(ROOT.iterdir()):
        if not d.is_dir():
            continue
        if not (d / "runs.jsonl").exists() and not (d / "runs.jsonl.gz").exists():
            continue        # a --dry run creates the directory but no data
        gz = d / "runs.jsonl.gz"
        n = sum(1 for _ in ResultStore(d / "runs.jsonl").rows())
        lv = len(list((d / "calib").glob("*.json"))) if (d / "calib").exists() else 0
        L.append(f"| `{d.name}` | {n} | {lv} | "
                 f"{'`runs.jsonl.gz` %.1f MB' % (gz.stat().st_size/1e6) if gz.exists() else '—'} | "
                 f"{'[RESULTS.md](%s/RESULTS.md)' % d.name if (d/'RESULTS.md').exists() else '—'} |")
    (ROOT / "INDEX.md").write_text("\n".join(L) + "\n")


# ---------------------------------------------------------------- entry point
def main(exp: Experiment, argv=None):
    """Shared CLI, so every experiment module is a declaration plus one call."""
    import argparse
    ap = argparse.ArgumentParser(description=exp.title)
    ap.add_argument("--dry", action="store_true",
                    help="print what would run and the ETA; run nothing")
    ap.add_argument("--seeds", type=int, default=None,
                    help=f"evaluation seeds per cell (protocol: {exp.seeds})")
    ap.add_argument("--calib-seeds", type=int, default=None)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--archive", action="store_true",
                    help="gzip the store for committing; run nothing")
    a = ap.parse_args(argv)

    e = exp
    if a.seeds is not None or a.calib_seeds is not None:
        e = dataclasses.replace(
            exp,
            seeds=a.seeds if a.seeds is not None else exp.seeds,
            calib_seeds=(a.calib_seeds if a.calib_seeds is not None
                         else exp.calib_seeds))
        print(f"!! --seeds {e.seeds} / --calib-seeds {e.calib_seeds}; protocol "
              f"is {exp.seeds} / {exp.calib_seeds}. This is a SMOKE pass, not "
              f"a result.\n")
    if a.archive:
        archive(e)
        return
    run_experiment(e, workers=a.workers, dry=a.dry)
