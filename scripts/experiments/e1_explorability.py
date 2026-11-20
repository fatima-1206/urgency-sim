"""E1 -- Explorability.  [headline]

Does the method need information to be SCARCE before it pays?

    explorability = mission_ticks * speed / cells

the fraction of the domain the agent can DIRECTLY SAMPLE in one mission. The
agent is a strict point sensor (sim.py reads field.sample at its own cell and
nowhere else), so this is the honest measure of how much of the forest it can
actually visit.

TWO ARMS, because the obvious lever does not work.

  mission arm (primary)  T in {200, 400, 800, 1600} at n=40
                         -> explorability 0.125, 0.25, 0.50, 1.00
                         Physics, plume, connectivity and GP are untouched;
                         only how long the agent has changes. Cost scales with T.

  grid arm (cross-check) n in {40, 60} at T=800
                         -> explorability 0.50, 0.22
                         An independent route to the same axis: a bigger world
                         rather than less time. If the two arms agree, the
                         finding is about explorability and not about either
                         lever.

WHY THE GRID ARM STOPS AT 60. The cloud GP rebuilds its map from a fixed
140-point sliding window with a 6-cell length scale (change C7), so its
capacity to cover the domain is fixed while the domain is not:

    n=40  gp_capacity 9.9     n=80   gp_capacity 2.5
    n=60  gp_capacity 4.4     n=120  gp_capacity 1.1

Measured at n=120, every method collapses to on-time 0.00-0.06 firing ~1 alarm
per run -- degenerate, and degenerate for the GP's reasons rather than the
agent's. Scaling the GP with area restores measurability (on-time 0.140 vs
0.143) but makes the two methods identical, costs O(window^3) in the Cholesky
solve, and drives map RMSE down to 0.068 because a larger domain is mostly
empty. n>=80 is therefore excluded in advance, with its reason, rather than
run and then explained away.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _harness import Experiment, main  # noqa: E402

from urgency_sim.config import (Config, with_conn, with_grid, with_mission,
                                with_scenario)

# ("mission", T) and ("grid", n). ("mission", 800) == ("grid", 40) is the
# Phase 3 configuration and anchors both arms.
LEVELS = [("mission", t) for t in (200, 400, 800, 1600)] + \
         [("grid", n) for n in (60,)]


def build(level, scenario, conn):
    kind, v = level
    # with_conn FIRST: with_grid scales whatever connectivity values are in
    # place, so applying it to the defaults would silently discard the scenario.
    cfg = with_conn(with_scenario(Config(), scenario), conn)
    return with_mission(cfg, int(v)) if kind == "mission" else with_grid(cfg, int(v))


EXP = Experiment(
    eid="e1_explorability",
    title="Explorability: does the method need information to be scarce?",
    question="Phase 3 ran at explorability 0.50. Does the advantage grow as it falls?",
    levels=LEVELS,
    tag=lambda l: f"{'t' if l[0]=='mission' else 'n'}{l[1]}",
    build=build,
    cost=lambda l: (l[1] / 800.0) if l[0] == "mission" else (l[1] / 40.0) ** 2,
)

if __name__ == "__main__":
    main(EXP)
