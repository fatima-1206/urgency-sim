"""E12 -- Low hazard: the only regime where a MATCHED comparison is possible
at a high alarm rate.

Two findings from the programme point here.

1. E7's lead. The proposed method's latency penalty at matched airtime falls
   from +17..+44 ticks at hazard 0.50 to roughly zero at hazard 0.25. It does
   BETTER as events become plentiful -- the opposite of the information-scarcity
   premise the programme was built on. Whether it overtakes below 0.25 was never
   tested.

2. A structural gap. Every one of the 260 comparisons in the programme is either
   matched at ~9-11 alarms/run, or unmatched because the threshold baseline
   saturates. There is NO matched comparison at a high alarm rate anywhere, in
   either direction, because the baseline cannot be driven there.

   A probe at the default trigger shows the baseline is NOT saturated at low
   hazard -- it fires 86 alarms/run at hazard 0.10:

       hazard   events/run   baseline alarms
         0.10        405           86.1
         0.15        642           47.1
         0.20        682           31.5
         0.25        585           18.1
         0.35        344            6.5

   So at hazard 0.10-0.15 a budget of 45 is genuinely reachable by BOTH methods,
   and budget 22 is reachable at 0.20. This is the first and only place in the
   project where "matched alarm budget" can mean what it claims to mean at a
   high rate.

The programme's central negative result -- the baseline wins at equal airtime --
is established only at ~9-11 alarms/run. This experiment is the one test that
can extend or overturn it at 22 and 45.

Pre-registered predictions, written before the run:

  P1  At hazard 0.10 and 0.15 the baseline reaches budget 45 within 10% of
      target, so the alarm ratio lands in [0.9, 1.1] and the comparison is
      genuinely matched.
  P2  At those matched high-rate cells the on-time margin is NEGATIVE, matching
      every other matched cell in the programme. (This is the unfavourable
      prediction: it says the capacity advantage is the whole story.)
  P3  The matched-airtime latency penalty continues to fall as hazard falls,
      reaching <= 0 at hazard 0.15 or below.

  FALSIFIER for P2: a positive margin with a CI excluding zero at any matched
  cell at budget 22 or 45. That would be the first evidence in the project that
  the trigger wins on prioritisation rather than on airtime, and it would mean
  the negative result is specific to a starved alarm budget.

Calibration runs at 20 seeds (the Phase 1 standard), not the 8 this programme
shipped with.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _harness import Experiment, main  # noqa: E402

from urgency_sim.config import Config, with_conn, with_scenario, with_hazard


def build(level, scenario, conn):
    return with_hazard(
        with_conn(with_scenario(Config(), scenario), conn), float(level))


EXP = Experiment(
    eid="e12_low_hazard",
    title="Low hazard: a matched comparison at a high alarm rate",
    question="Does the baseline still win at equal airtime when equal airtime "
             "is possible at 22 and 45 alarms/run?",
    levels=[0.10, 0.15, 0.20, 0.25],
    tag=lambda h: f"h{h:g}",
    build=build,
    budgets=(11, 22, 45),
    # Low hazard means many more observable events, so each run does more work
    # in metrics and the GP. Measured ~1.5x the baseline configuration.
    cost=lambda h: 1.5,
)

if __name__ == "__main__":
    main(EXP)
