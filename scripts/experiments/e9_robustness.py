"""E9 -- Robustness battery.

Phase 3's sensitivity check ran at 8 seeds, which is a smoke test rather than
evidence: it could not separate a real effect from noise. This repeats it at
study scale, one factor at a time around the baseline, at budget 45 only.

`k_consistent` and `upload_consec` are decision-rule parameters the method
chose; `sensor_noise` and the GP `window` are environment and model parameters
it must tolerate. A conclusion that only holds at one setting of any of these
is not a conclusion.
"""
import sys, pathlib
from dataclasses import replace
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _harness import Experiment, main  # noqa: E402

from urgency_sim.config import Config, with_conn, with_scenario

LEVELS = ([("k", v) for v in (1, 2, 3, 5)]
          + [("noise", v) for v in (0.02, 0.04, 0.08)]
          + [("consec", v) for v in (1, 2, 3, 5)]
          + [("window", v) for v in (70, 140, 280)])


def build(level, scenario, conn):
    kind, v = level
    c = with_conn(with_scenario(Config(), scenario), conn)
    if kind == "k":
        return replace(c, urg=replace(c.urg, k_consistent=int(v)))
    if kind == "noise":
        return replace(c, agent=replace(c.agent, sensor_noise=float(v)))
    if kind == "consec":
        return replace(c, comm=replace(c.comm, upload_consec=int(v)))
    if kind == "window":
        return replace(c, gp=replace(c.gp, window=int(v)))
    raise ValueError(kind)


EXP = Experiment(
    eid="e9_robustness",
    title="Robustness battery at study scale",
    question="Does any Phase 3 conclusion depend on one parameter setting?",
    levels=LEVELS,
    tag=lambda l: f"{l[0]}{l[1]:g}",
    build=build,
    budgets=(45,),
)

if __name__ == "__main__":
    main(EXP)
