"""E13 -- The load-bearing matched cells, recalibrated at 20 seeds.

This programme calibrated at 8 seeds per level. Phase 1 had already measured
that 5 seeds gave triggers up to 24% off budget and raised its own calibration
to 20, so 8 is below the standard the project settled on and had to be flagged
in the results.

What recalibration can and cannot fix
-------------------------------------
Of the 54 off-target flags in the programme, 52 are the threshold baseline and
every one of those is SATURATION, not calibration error: the baseline is asked
for 45 alarms and is physically capable of ~10, at any trigger including zero.
No number of calibration seeds changes that. Re-running the whole programme at
20 seeds would therefore remove approximately zero flags.

What it does change is the precision of the triggers at the budgets where
neither method is saturated -- budgets 5 and 11 -- and those are exactly the
cells that carry the programme's central result: at equal airtime the baseline
wins 42 of 42. If calibration noise were inflating the proposed method's alarm
count at budget 11, that result would be overstated. This experiment tests that
directly, on the same levels, changing only the calibration size.

It runs under its own eid so the 8-seed data stays intact and the two can be
compared. The harness refuses to mix them in one store in any case
(_check_triggers).

Prediction, written before the run: the matched-cell margin stays negative and
within 0.02 of the 8-seed value, i.e. the central result is not an artefact of
calibration noise. A margin that moves above zero would mean it is.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _harness import Experiment, main  # noqa: E402

from urgency_sim.config import Config, with_conn, with_scenario, with_hazard


def build(level, scenario, conn):
    return with_hazard(
        with_conn(with_scenario(Config(), scenario), conn), float(level))


EXP = Experiment(
    eid="e13_recalibrate",
    title="Matched cells recalibrated at 20 seeds",
    question="Is the equal-airtime result an artefact of 8-seed calibration?",
    levels=[0.25, 0.35, 0.50],
    tag=lambda h: f"h{h:g}",
    build=build,
    budgets=(5, 11),
)

if __name__ == "__main__":
    main(EXP)
