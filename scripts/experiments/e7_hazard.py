"""E7 -- Hazard level.

The hazard threshold defines what counts as a critical event at all, so it
changes the event SET and not merely the difficulty. If the Phase 3 conclusions
are an artefact of one arbitrary threshold, this is where it shows.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _harness import Experiment, main  # noqa: E402

from urgency_sim.config import Config, with_conn, with_scenario, with_hazard


def build(level, scenario, conn):
    return with_hazard(
        with_conn(with_scenario(Config(), scenario), conn), float(level))


EXP = Experiment(
    eid="e7_hazard",
    title="Hazard level",
    question="Is any Phase 3 conclusion an artefact of hazard = 0.35?",
    levels=[0.25, 0.35, 0.50],
    tag=lambda h: f"h{h:g}",
    build=build,
)

if __name__ == "__main__":
    main(EXP)
