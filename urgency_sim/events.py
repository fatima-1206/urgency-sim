"""Ground-truth critical events, defined from the physics alone.

An event is a cell on a coarse lattice whose TRUE concentration crosses the
hazard level upward. The set of events is therefore identical for every
method -- the method only affects the OUTCOME (did the cloud find out in
time).  Each event's deadline is the time for the plume to travel from the
event cell to the sensitive zone along the wind vector; events that are not
upwind of the zone are never urgent.
"""
from dataclasses import dataclass
from typing import List

import numpy as np

from .config import Config


@dataclass
class CriticalEvent:
    x: int
    y: int
    t: int
    deadline: float
    value: float
    upwind: bool


def zone_mask(cfg: Config):
    n = cfg.fld.n
    zx, zy = cfg.ev.zone_xy
    h = cfg.ev.zone_half
    m = np.zeros((n, n), dtype=bool)
    m[max(0, zx - h):zx + h + 1, max(0, zy - h):zy + h + 1] = True
    return m


def wind_at(cfg: Config, t: int):
    fc = cfg.fld
    if cfg.scenario == "unpredictable" and t >= fc.wind_shift_t:
        return fc.wind_after
    return fc.wind


def deadline_for(cfg: Config, x, y, t):
    """Travel time along the wind vector to the sensitive zone."""
    zx, zy = cfg.ev.zone_xy
    u, v = wind_at(cfg, t)
    sp = float(np.hypot(u, v))
    T = cfg.agent.mission_ticks
    if sp < 1e-6:
        return float(T), False
    ux, uy = u / sp, v / sp
    proj = (zx - x) * ux + (zy - y) * uy
    if proj <= 0:
        return float(T), False          # not upwind of the zone: not urgent
    return float(min(T, t + proj / sp)), True


def extract_events(cfg: Config, hist: np.ndarray) -> List[CriticalEvent]:
    """hist: (T+1, n, n) true field history."""
    ev = cfg.ev
    haz = cfg.urg.hazard
    n = cfg.fld.n
    T = cfg.agent.mission_ticks
    out: List[CriticalEvent] = []
    ax = np.arange(0, n, ev.event_grid_stride)
    for x in ax:
        for y in ax:
            series = hist[:T + 1, x, y]
            above = series > haz
            if not above.any():
                continue
            # upward crossings
            cross = np.flatnonzero((~above[:-1]) & above[1:]) + 1
            if above[0]:
                cross = np.concatenate([[0], cross])
            last = -10 ** 9
            for tc in cross:
                if tc - last < ev.event_min_gap:
                    continue
                last = tc
                dl, up = deadline_for(cfg, x, y, int(tc))
                out.append(CriticalEvent(int(x), int(y), int(tc), dl,
                                         float(series[tc]), up))
    out.sort(key=lambda e: e.t)
    return out
