"""E8 -- Channel burstiness.

The two-tier upload rule requires three CONSECUTIVE successful ticks for a full
upload. That design only earns its place if losses are bursty: under
independent losses, three-in-a-row is merely a harder coin flip. `with_channel`
varies the mean bad-state dwell while holding the stationary loss probability
fixed, so burstiness varies alone rather than dragging the loss rate with it.

Phase 3 ran at mean burst 1/p_bg = 2.86 ticks throughout.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _harness import Experiment, main  # noqa: E402

from urgency_sim.config import Config, with_conn, with_scenario, with_channel


def build(level, scenario, conn):
    return with_channel(
        with_conn(with_scenario(Config(), scenario), conn), float(level))


EXP = Experiment(
    eid="e8_burstiness",
    title="Channel burstiness at constant mean loss",
    question="Does the two-tier upload rule earn its place as bursts lengthen?",
    levels=[1.0, 2.86, 8.0, 20.0],
    tag=lambda b: f"b{b:g}",
    build=build,
)

if __name__ == "__main__":
    main(EXP)
