"""E14 -- Does a decoupled threshold remove the baseline's ceiling?

Why this exists
---------------
The programme's capacity claim rests on one structural fact: the threshold
baseline scores max(0, obs - h), where h is the SAME hazard level that defines
which cells count as events. That score is identically zero below h, so no
trigger setting -- zero included -- makes the baseline fire there, and its
alarm rate caps near 10.5 per run in the Table 6 configuration while the
proposed method goes on to 150.

That cap is a property of how the baseline was written, not a property of
threshold triggering. A baseline firing at obs > theta with theta free to fall
below h has no such cap. If it reaches the high budgets AND still beats the
proposed method at matched airtime, the capacity half of the paper's claim is
gone and the equal-airtime finding is the whole result. If it reaches the high
budgets and LOSES there, the capacity claim survives on much stronger ground,
because it would then be a statement about triggering rather than about an
artefact of one implementation.

Only the trigger changes. Fixed deadline, Monte-Carlo routing and the k-of-k
consistency gate are identical to `threshold`, so the comparison isolates the
firing rule.

Configuration is E4's (speed 0.25, hazard 0.35 default) -- the cell the paper's
budget ladder is drawn on -- so the new baseline lands on the same axis as the
numbers already reported.

Predictions, written before the run
-----------------------------------
P1  The decoupled baseline reaches budgets 90 and 150 within 10%, where the
    coupled baseline cannot. (Near-certain; it is the point of the design.)
    A failure here would mean the cap is NOT the hazard coupling and the
    paper's structural explanation is wrong.
P2  At budget 11, where the coupled baseline is unsaturated, the decoupled
    baseline matches it to within 0.02 on-time. The two rules should be close
    when neither is capped, and a large gap would mean the new trigger changed
    more than intended.
P3  At budgets 90 and 150 the decoupled baseline beats the proposed method
    (margin negative), extending the equal-airtime finding to high budgets and
    removing the capacity claim.
    Stated this way deliberately: P3 is the outcome that costs the paper the
    most, so it is the one worth being wrong about.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _harness import Experiment, main  # noqa: E402

from urgency_sim.config import Config, with_conn, with_scenario, with_speed


def build(level, scenario, conn):
    return with_conn(with_scenario(with_speed(Config(), 0.25), scenario), conn)


EXP = Experiment(
    eid="e14_decoupled_threshold",
    title="Decoupled threshold: does a free firing level remove the ceiling?",
    question="Is the baseline's alarm ceiling a property of triggering, or of "
            "tying its firing level to the hazard level?",
    levels=[0],
    tag=lambda _l: "base",
    build=build,
    methods=("proposed", "threshold", "threshold_dec"),
    budgets=(11, 90, 150),
)

if __name__ == "__main__":
    main(EXP)
