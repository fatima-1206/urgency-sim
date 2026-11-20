"""E2 -- Connectivity scarcity.

Phase 3 confounded two things under one "sparse/dense" switch: how MUCH of the
domain is covered, and how MANY separate upload points there are. They have
different consequences -- coverage decides whether delivery is cheap, count
decides whether there is a choice to make -- so they are varied separately.

At the Phase 3 setting the agent is on average 1.5-2.4 cells from a usable
uplink, i.e. travelling to connectivity costs almost nothing. This asks how
scarce connectivity has to be before upload-point selection matters.

Note the geometric ceiling: region separability caps effective coverage near
0.34 on a 40x40 grid, so the `size` arm cannot be pushed arbitrarily high.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _harness import Experiment, main  # noqa: E402

from urgency_sim.config import (Config, with_conn, with_scenario, with_regions,
                                with_region_size)

# ("count", k) varies HOW MANY uplinks at fixed region size.
# ("size", s) varies coverage fraction at a fixed number of uplinks.
LEVELS = [("count", k) for k in (1, 2, 4, 8)] + \
         [("size", s) for s in (0.6, 0.8, 1.0, 1.3)]


def build(level, scenario, conn):
    kind, v = level
    cfg = with_conn(with_scenario(Config(), scenario), conn)
    return with_regions(cfg, int(v)) if kind == "count" \
        else with_region_size(cfg, float(v))


EXP = Experiment(
    eid="e2_connectivity",
    title="Connectivity scarcity: region count vs coverage fraction",
    question="How scarce must connectivity be before upload-point choice matters?",
    levels=LEVELS,
    tag=lambda l: f"{l[0]}{l[1]:g}",
    build=build,
)

if __name__ == "__main__":
    main(EXP)
