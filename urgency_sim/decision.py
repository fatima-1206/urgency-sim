"""Monte-Carlo action selection under two-tier messaging.

A short ALERT can be pushed from anywhere with per-tick retries. The FULL
UPLOAD -- the thing that actually updates the cloud map, and the only thing
that counts for on-time delivery -- needs a sustained link: either the cell's
link quality is above `upload_q_direct` (one success is enough to push the
payload) or `upload_consec` consecutive successful ticks are required.

That asymmetry is what makes the action choice non-trivial. With a single
per-tick attempt and a long deadline, every action reached P(deliver) ~ 1.
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from .config import Config


@dataclass
class ActionEval:
    name: str
    target: Optional[Tuple[float, float]]
    p_deliver: float          # P(full upload completes before the deadline)
    exp_time: float           # expected ticks to complete, censored
    p_alert: float            # P(the short alert gets through)
    region_idx: Optional[int] = None


def _stationary_bad(cc):
    return cc.p_gb / (cc.p_gb + cc.p_bg)


def rollout_upload(q_seq: np.ndarray, cc, rng, n_roll: int,
                   consec: int, q_direct: float, max_attempts: int):
    """Simulate the link along a per-tick quality sequence.

    Returns (completion_tick_or_inf, alert_tick_or_inf), each shape (n_roll,).
    """
    R = n_roll
    T = len(q_seq)
    if T == 0:
        inf = np.full(R, np.inf)
        return inf, inf
    bad = rng.random(R) < _stationary_bad(cc)
    streak = np.zeros(R, dtype=int)
    attempts = np.zeros(R, dtype=int)
    done = np.full(R, np.inf)
    alert = np.full(R, np.inf)
    for k in range(T):
        q = float(q_seq[k])
        flip = rng.random(R)
        bad = np.where(bad, ~(flip < cc.p_bg), flip < cc.p_gb)
        if q <= 1e-4:
            streak[:] = 0
            continue
        p = q * (1.0 - np.where(bad, cc.loss_bad, cc.loss_good))
        live = (~np.isfinite(done)) & (attempts < max_attempts)
        ok = (rng.random(R) < p) & live
        attempts[live] += 1
        # the short alert needs one success anywhere
        first_alert = ok & (~np.isfinite(alert))
        alert[first_alert] = k
        streak = np.where(ok, streak + 1, 0)
        need = 1 if q >= q_direct else consec
        newly = live & (streak >= need) & (~np.isfinite(done))
        done[newly] = k
        if np.isfinite(done).all():
            break
    return done, alert


def _path_qualities(disc, x0, y0, tx, ty, n_ticks, speed):
    d = float(np.hypot(tx - x0, ty - y0))
    steps = int(np.ceil(d / max(speed, 1e-9)))
    qs = []
    for k in range(min(steps, n_ticks)):
        f = (k + 1) / max(steps, 1)
        px, py = x0 + (tx - x0) * f, y0 + (ty - y0) * f
        qs.append(disc.local_quality_estimate(int(round(px)), int(round(py))))
    rest = n_ticks - len(qs)
    if rest > 0:
        qs.extend([disc.local_quality_estimate(int(round(tx)), int(round(ty)))]
                  * rest)
    return np.asarray(qs, dtype=float), steps


def _score(done, alert, horizon):
    p = float(np.mean(done <= horizon))
    # expected completion time, censored. Not completing is penalised at twice
    # the horizon so that "never finishes" is worse than "finishes at the
    # deadline", which a plain censor at `horizon` would not capture.
    t = np.where(done <= horizon, done, 2.0 * horizon)
    return p, float(np.mean(t)), float(np.mean(alert <= horizon))


def evaluate_actions(cfg: Config, disc, x, y, t, deadline,
                     explore_target, rng) -> List[ActionEval]:
    cc = cfg.comm
    n_roll = cfg.dec.n_rollouts
    horizon = int(max(0, np.floor(deadline - t)))
    horizon = min(horizon, cfg.agent.mission_ticks - t)
    out: List[ActionEval] = []
    if horizon <= 0:
        return [ActionEval("transmit_now", (x, y), 0.0, 1e9, 0.0)]

    def ev(name, target, qs, region_idx=None):
        done, alert = rollout_upload(qs, cc, rng, n_roll, cc.upload_consec,
                                     cc.upload_q_direct,
                                     cc.max_attempts_per_item)
        p, et, pa = _score(done, alert, horizon)
        out.append(ActionEval(name, target, p, et, pa, region_idx))

    q_here = disc.local_quality_estimate(x, y)
    ev("transmit_now", (x, y), np.full(horizon, q_here))

    if explore_target is not None:
        qs, _ = _path_qualities(disc, x, y, explore_target[0],
                                explore_target[1], horizon, cfg.agent.speed)
        ev("explore", tuple(explore_target), qs)

    for i, r in enumerate(disc.regions):
        qs, steps = _path_qualities(disc, x, y, r.cx, r.cy, horizon,
                                    cfg.agent.speed)
        if steps < horizon:
            qs[steps:] = r.p_hat()
        ev("goto_launch" if r.is_launch else f"goto_r{i}", (r.cx, r.cy), qs, i)
    return out


def choose(actions: List[ActionEval], cfg: Config) -> ActionEval:
    """Pick an action. `select_by` switches between maximising the probability
    of delivering in time and minimising the expected time to deliver. The
    latter still discriminates when every probability saturates near 1.
    Exploring wins near-ties, since it also earns information.
    """
    tb = cfg.dec.explore_tiebreak
    if cfg.dec.select_by == "exp_time":
        best = min(a.exp_time for a in actions)
        # tie-break margin scaled to the spread of the options
        margin = max(1.0, 0.05 * best)
        for a in actions:
            if a.name == "explore" and a.exp_time <= best + margin:
                return a
        return min(actions, key=lambda a: a.exp_time)
    best = max(a.p_deliver for a in actions)
    for a in actions:
        if a.name == "explore" and a.p_deliver >= best - tb:
            return a
    return max(actions, key=lambda a: a.p_deliver)
