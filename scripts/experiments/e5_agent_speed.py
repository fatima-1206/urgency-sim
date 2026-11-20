"""E5 -- Agent speed.

Phase 3 varied only the PLUME; agent speed was fixed at 1. This moves the
plume/agent ratio from the other side, and also raises explorability
(3.50 -> 7.0 -> 10.5), so it is read jointly with E1.

Depends on the sim.py fix: before it, `agent.speed` was consulted only by the
decision code while the agent always stepped one cell, so any value but 1 made
the planner believe it moved faster than it did. speed=1 is bit-identical to
the pre-fix behaviour, verified over 40 runs.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _harness import Experiment, main  # noqa: E402

from urgency_sim.config import Config, with_conn, with_scenario, with_agent_speed


def build(level, scenario, conn):
    return with_agent_speed(
        with_conn(with_scenario(Config(), scenario), conn), int(level))


EXP = Experiment(
    eid="e5_agent_speed",
    title="Agent speed",
    question="Does a faster agent help the method or the baseline more?",
    levels=[1, 2, 3],
    tag=lambda s: f"v{s}",
    build=build,
)

if __name__ == "__main__":
    main(EXP)
