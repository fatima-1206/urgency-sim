"""E4 -- Budget ceiling extension.

Phase 3 stopped at 90 alarms/run with on-time still climbing (0.533, no
plateau), so the method's own ceiling was never found. The threshold baseline
saturates near 10.5 alarms in this regime and returns byte-identical runs above
that, so only the proposed method needs the extra points.

The proposed method HAS a ceiling of its own, measured at ~150 alarms/run at
trigger 0: the k-of-k consistency gate (k = 3) admits at most one alarm every
three ticks, bounding the rate at mission_ticks/3 = 266, and the trigger cannot
go below zero. 180 is therefore included deliberately as an UNREACHABLE target
-- calibration will flag it as off budget, which is the evidence for the
ceiling rather than an error.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _harness import Experiment, main  # noqa: E402

from urgency_sim.config import Config, with_conn, with_scenario, with_speed


def build(level, scenario, conn):
    # Speed 0.25, matching the Phase 3 level whose frontier this extends.
    return with_conn(with_scenario(with_speed(Config(), 0.25), scenario), conn)


EXP = Experiment(
    eid="e4_budget_ceiling",
    title="Budget ceiling: where does the proposed method stop improving?",
    question="Phase 3 ended at 90 alarms/run still climbing. Where is the plateau?",
    levels=[0],
    tag=lambda _l: "base",
    build=build,
    methods=("proposed",),
    budgets=(90, 120, 150, 180),
)

if __name__ == "__main__":
    main(EXP)
