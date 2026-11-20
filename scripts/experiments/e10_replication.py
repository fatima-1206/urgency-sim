"""E10 -- Seed-stability replication.

The headline frontier re-run on a seed block disjoint from every block used to
calibrate or evaluate anything so far (pilot 0-199, Phase 2 sweep 1000-1029,
Phase 3 2000-3299, this programme's calibration 5000-5299 and evaluation
6000-6299). Block 7000-7299.

This is the cheapest available answer to "you tuned on those seeds".
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _harness import Experiment, main, REPLICATE_SEED0  # noqa: E402

from urgency_sim.config import Config, with_conn, with_scenario, with_speed


def build(level, scenario, conn):
    return with_conn(with_scenario(with_speed(Config(), 0.25), scenario), conn)


EXP = Experiment(
    eid="e10_replication",
    title="Seed-stability replication on a fresh block",
    question="Does the Phase 3 frontier reproduce on seeds never used before?",
    levels=[0],
    tag=lambda _l: "base",
    build=build,
    budgets=(5, 11, 22, 45, 90),
    seeds=300,
    seed0=REPLICATE_SEED0,
)

if __name__ == "__main__":
    main(EXP)
