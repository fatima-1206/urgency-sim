"""Turning an observation into an urgency number and then into a deadline."""
from dataclasses import dataclass, replace
from typing import List, Optional

import numpy as np

from .config import UrgencyCfg


@dataclass
class Pending:
    """An observation the agent has decided is worth delivering."""
    x: int
    y: int
    t_obs: int
    value: float
    urgency: float
    deadline: float          # absolute tick by which it should reach the cloud
    fired_t: int
    surprise: float = 0.0
    consequence: float = 0.0


class UrgencyDetector:
    """Surprise and consequence, combined ADDITIVELY.

    The first prototype multiplied them, so when the cloud model was ignorant
    (large sd -> small surprise) the product collapsed and a reading far above
    the hazard level was not urgent. Adding them means a dangerous reading is
    urgent on its own merits:

        score = w_s * |obs - mu| / max(sd, sd_floor)
              + w_c * max(0, obs - hazard) / consequence_scale

    modes:
      'combined'   : both terms                              (proposed)
      'surprise'   : w_c = 0, uncertainty-scaled error only  (ablation)
      'raw'        : surprise term without the /sd           (ablation)
      'threshold'  : consequence term only, no model         (baseline)
      'level'      : the raw reading, fired at a FREE level theta (baseline)
      'time'       : urgency grows since last delivery       (baseline)
    """

    def __init__(self, ucfg: UrgencyCfg, mode: str = "combined",
                 trigger: Optional[float] = None, tau: float = 60.0):
        self.c = ucfg
        self.mode = mode
        self.trigger = ucfg.z_trigger if trigger is None else trigger
        self.tau = tau
        self.run = 0
        self.buf: List[float] = []
        self.last_parts = (0.0, 0.0)
        q = np.asarray(ucfg.urgency_q, dtype=float)
        # np.interp needs a strictly increasing table; ties are nudged apart.
        if q.size >= 2:
            q = np.maximum.accumulate(q)
            q += np.arange(q.size) * 1e-9
            self._q, self._p = q, np.linspace(0.0, 1.0, q.size)
        else:
            self._q = self._p = None

    # -- the two ingredients ----------------------------------------------
    def surprise(self, obs, mu, sd) -> float:
        return abs(obs - mu) / max(sd, self.c.sd_floor)

    def consequence(self, obs) -> float:
        return max(0.0, obs - self.c.hazard) / self.c.consequence_scale

    def score(self, obs, mu, sd, t, t_last_delivery) -> float:
        c = self.c
        if self.mode == "combined":
            s, g = self.surprise(obs, mu, sd), self.consequence(obs)
            self.last_parts = (s, g)
            return c.w_surprise * s + c.w_consequence * g
        if self.mode == "surprise":
            s = self.surprise(obs, mu, sd)
            self.last_parts = (s, 0.0)
            return c.w_surprise * s
        if self.mode == "raw":
            s, g = abs(obs - mu), self.consequence(obs)
            self.last_parts = (s, g)
            return c.w_surprise * s + c.w_consequence * g
        if self.mode == "threshold":
            g = self.consequence(obs)
            self.last_parts = (0.0, g)
            return g
        if self.mode == "level":
            # Decoupled threshold. 'threshold' scores max(0, obs - hazard),
            # which is identically zero below the hazard level h, so no choice
            # of trigger can make it fire there -- that is the ceiling reported
            # in the paper. Here the score IS the reading and the firing level
            # theta is free, so theta may fall below h. Everything else about
            # the baseline (fixed deadline, MC routing, k-of-k gate) is
            # unchanged, which is what makes the two comparable.
            self.last_parts = (0.0, float(obs))
            return float(obs)
        if self.mode == "time":
            self.last_parts = (0.0, 0.0)
            return float(np.exp((t - t_last_delivery) / self.tau) - 1.0)
        raise ValueError(self.mode)

    # -- k-of-k consistency gate ------------------------------------------
    def update(self, obs, mu, sd, t, t_last_delivery, x, y):
        s = self.score(obs, mu, sd, t, t_last_delivery)
        parts = self.last_parts
        # Every content-based trigger gets the same k-of-k debounce, so the
        # comparison isolates the trigger SIGNAL rather than rewarding whichever
        # rule happens to lack a consistency gate. 'time' is a timer, so
        # consecutive-above is automatic and the gate is meaningless there.
        k = 1 if self.mode == "time" else self.c.k_consistent
        if s > self.trigger:
            self.run += 1
            self.buf.append(s)
        else:
            self.run = 0
            self.buf.clear()
        if self.run < k:
            return None
        u = float(np.mean(self.buf[-k:]))
        self.run = 0
        self.buf.clear()
        return Pending(int(x), int(y), int(t), float(obs), u,
                       deadline=t + self.deadline_for(u), fired_t=int(t),
                       surprise=float(parts[0]), consequence=float(parts[1]))

    # -- urgency -> deadline ----------------------------------------------
    def deadline_for(self, urgency: float) -> float:
        """Map urgency onto [deadline_min, deadline_max], decreasing.

        'percentile' (default): interpolate the urgency's empirical RANK from
        the calibrated quantile table `urgency_q` and use that as the position
        in the deadline range. Deadlines are then spread across the range by
        construction. The linear map it replaces put 62% of deadlines at the
        ceiling, because urgency-at-fire is heavy-tailed.

        'linear': the pilot map, kept so old results can be reproduced.
        """
        c = self.c
        q = self._q
        if c.deadline_map == "percentile" and q is not None:
            f = float(np.interp(urgency, q, self._p))
        else:
            f = (urgency - c.urgency_lo) / max(1e-9, c.urgency_hi - c.urgency_lo)
        f = min(1.0, max(0.0, f))
        return c.deadline_max - (c.deadline_max - c.deadline_min) * f
