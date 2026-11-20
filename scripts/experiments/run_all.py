"""Run the whole experiment programme, in priority order, resumably.

    .venv/bin/python scripts/experiments/run_all.py --dry      # costs only
    .venv/bin/python scripts/experiments/run_all.py            # everything
    .venv/bin/python scripts/experiments/run_all.py --only e1_explorability

Interrupt at any point and re-run: each completed simulation is fsync'd before
the next begins, so resuming skips what is already on disk. Ordered so the
regime question is answered first and each experiment is reportable alone.
"""
import argparse, importlib, pathlib, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from _harness import run_experiment, plan, archive  # noqa: E402

ORDER = [
    "e1_explorability",     # headline: does the method need scarcity?
    "e4_budget_ceiling",    # cheap, and finishes an unfinished Phase 3 curve
    "e2_connectivity",      # is "sparse" sparse enough to matter?
    "e8_burstiness",        # does the two-tier upload rule earn its place?
    "e7_hazard",            # is anything an artefact of hazard = 0.35?
    "e5_agent_speed",       # the ratio from the other side
    "e9_robustness",        # Phase 3's 8-seed sensitivity, done properly
    "e10_replication",      # fresh seed block
]


def load(eid):
    return importlib.import_module(eid).EXP


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--archive", action="store_true")
    ap.add_argument("--workers", type=int, default=10)
    a = ap.parse_args()

    eids = a.only if a.only else ORDER
    if a.archive:
        for e in eids:
            archive(load(e))
        sys.exit(0)
    if a.dry:
        tot = sum(plan(load(e), a.workers) for e in eids)
        print(f"PROGRAMME TOTAL ~{tot/60:.1f} h at {a.workers} workers")
        sys.exit(0)

    t0 = time.time()
    for e in eids:
        run_experiment(load(e), workers=a.workers)
        archive(load(e))
        print(f"--- {e} COMPLETE, reportable on its own ---\n")
    print(f"PROGRAMME total {(time.time()-t0)/60:.1f} min")
