"""Scoring a RunLog against the method-independent ground-truth event set.

Observability. The first prototype scored every ground-truth event, including
events the agent never went anywhere near, so ~80% of them were unreachable by
any method and every method was pinned near the same score. Metrics are now
reported over OBSERVABLE events: those whose cell came within `sensor_range`
of the agent at some point in the mission. The sensor is a point sensor, but
the field is smooth over the GP length scale, so a reading within a few cells
carries real information about that cell.

`on_time_ratio` is over observable events (the headline).
`on_time_ratio_all` keeps the old all-events number for comparison.
`on_time_ratio_near` uses the stricter rule that the agent must pass close to
the cell within +/- match_window ticks OF THE EVENT, not merely at some point.
"""
from typing import Dict, List

import numpy as np

from .manifest import manifest


def mean(v):
    """Mean that drops the horizon<=0 sentinel (`exp_time` returns 1e9 when
    the deadline has already passed). Averaging it in once produced a reported
    mean expected-delivery time of 3,114,114 ticks."""
    v = [z for z in v if np.isfinite(z) and z < 1e8]
    return float(np.mean(v)) if v else float("nan")


def _lat_index(cfg, x, y):
    s = cfg.ev.event_grid_stride
    return x // s, y // s


def observability(log):
    """For each event: nearest approach distance, and whether the agent came
    within sensor range (a) at any time, (b) near the event time."""
    cfg = log.cfg
    R = cfg.agent.sensor_range
    W = cfg.ev.match_window
    pos = np.asarray(log.pos, dtype=float)          # (T, 2)
    out = []
    for e in log.events:
        d = np.hypot(pos[:, 0] - e.x, pos[:, 1] - e.y)
        any_t = bool((d <= R).any())
        lo, hi = max(0, e.t - W), min(len(d), e.t + W + 1)
        near_t = bool((d[lo:hi] <= R).any()) if hi > lo else False
        out.append(dict(any_t=any_t, near_t=near_t, min_dist=float(d.min())))
    return out


def event_outcomes(log) -> List[Dict]:
    """Did the cloud belief cross the hazard level at that cell before the
    event's physics deadline?"""
    cfg = log.cfg
    haz = cfg.urg.hazard
    T = cfg.agent.mission_ticks
    lat = np.asarray(log.cloud_lat)
    obs = observability(log)
    out = []
    for e, ob in zip(log.events, obs):
        i, j = _lat_index(cfg, e.x, e.y)
        t0 = int(e.t)
        t1 = int(min(T - 1, np.floor(e.deadline)))
        known_t = None
        if t1 >= t0:
            hit = np.flatnonzero(lat[t0:t1 + 1, i, j] > haz)
            if hit.size:
                known_t = t0 + int(hit[0])
        hit_all = np.flatnonzero(lat[t0:, i, j] > haz)
        ever_t = t0 + int(hit_all[0]) if hit_all.size else None
        out.append(dict(x=e.x, y=e.y, t=e.t, deadline=e.deadline,
                        upwind=e.upwind, on_time=known_t is not None,
                        known_t=known_t, ever_t=ever_t,
                        latency=(ever_t - e.t) if ever_t is not None else None,
                        observable=ob["any_t"], observable_near=ob["near_t"],
                        min_dist=ob["min_dist"]))
    return out


def alarm_quality(log, only_observable=True) -> Dict:
    cfg = log.cfg
    R, W = cfg.ev.match_radius, cfg.ev.match_window
    outs = event_outcomes(log)
    evs = [e for e, o in zip(log.events, outs)
           if (o["observable"] or not only_observable)]
    fires = log.fires
    tp = 0
    for (t, x, y, u, dl) in fires:
        if any(abs(e.x - x) <= R and abs(e.y - y) <= R
               and -W <= (t - e.t) <= W for e in evs):
            tp += 1
    detected, delays = 0, []
    for e in evs:
        cand = [t for (t, x, y, u, dl) in fires
                if abs(e.x - x) <= R and abs(e.y - y) <= R and 0 <= (t - e.t) <= W]
        if cand:
            detected += 1
            delays.append(min(cand) - e.t)
    return dict(n_fires=len(fires), n_events=len(evs),
                true_alarms=tp, false_alarms=len(fires) - tp,
                false_alarm_rate=(len(fires) - tp) / max(1, len(fires)),
                detection_rate=detected / max(1, len(evs)),
                mean_delay=float(np.mean(delays)) if delays else np.nan)


def false_alarm_detours(log) -> Dict:
    cfg = log.cfg
    R, W = cfg.ev.match_radius, cfg.ev.match_window
    evs = log.events
    n_fa, dist_fa = 0, 0.0
    for (t, x, y, target, fired_t) in log.detours:
        ok = any(abs(e.x - x) <= R and abs(e.y - y) <= R
                 and -W <= (fired_t - e.t) <= W for e in evs)
        if not ok:
            n_fa += 1
            if target is not None:
                dist_fa += float(np.hypot(target[0] - x, target[1] - y))
    return dict(n_detours=len(log.detours), n_false_detours=n_fa,
                false_detour_dist=dist_fa)


def map_error(log) -> float:
    cfg = log.cfg
    s = cfg.ev.event_grid_stride
    lat = np.asarray(log.cloud_lat)
    T = lat.shape[0]
    true_lat = log.truth[:T, ::s, ::s]
    half = T // 2
    return float(np.sqrt(np.mean((lat[half:] - true_lat[half:]) ** 2)))


def misbelief_fraction(log) -> float:
    cfg = log.cfg
    s = cfg.ev.event_grid_stride
    lat = np.asarray(log.cloud_lat)
    T = lat.shape[0]
    true_lat = log.truth[:T, ::s, ::s]
    return float(((true_lat > cfg.urg.hazard) & (lat <= cfg.urg.hazard)).mean())


def region_usage(log) -> Dict:
    """Why are discovered regions chosen so rarely? Snapshot at each decision
    taken while something was pending."""
    nd, chosen_r, chosen_l, chosen_tx, chosen_ex = 0, 0, 0, 0, 0
    dists_nonlaunch, phat_nonlaunch, dist_launch, phat_launch = [], [], [], []
    p_by_action, et_by_action = {}, {}
    horizons, tight_launch, tight_region = [], [], []
    n_disc_at_decision = []
    for d in log.region_diag:
        nd += 1
        horizons.append(d["horizon"])
        n_disc_at_decision.append(d["n_disc"])
        c = d["chosen"]
        if c == "explore":
            chosen_ex += 1
        elif c == "transmit_now":
            chosen_tx += 1
        elif c == "goto_launch":
            chosen_l += 1
        else:
            chosen_r += 1
        dl_n, dl_l = np.inf, np.inf
        for r in d["regions"]:
            if r["is_launch"]:
                dist_launch.append(r["dist"]); phat_launch.append(r["p_hat"])
                dl_l = min(dl_l, r["dist"])
            else:
                dists_nonlaunch.append(r["dist"]); phat_nonlaunch.append(r["p_hat"])
                dl_n = min(dl_n, r["dist"])
        # deadline tightness: is there time to travel there at all?
        # horizon / travel distance; distances below 1 cell are clamped so a
        # region the agent is standing on does not produce a huge ratio
        if np.isfinite(dl_l):
            tight_launch.append(d["horizon"] / max(dl_l, 1.0))
        if np.isfinite(dl_n):
            tight_region.append(d["horizon"] / max(dl_n, 1.0))
    for (t, evals, chosen) in log.action_evals:
        for (name, p, et, dist) in evals:
            key = ("goto_region" if name.startswith("goto_r") else name)
            p_by_action.setdefault(key, []).append(p)
            et_by_action.setdefault(key, []).append(et)
    return dict(
        n_decisions=nd,
        # counted AT DECISION TIME (the final-tick count can be lower, because
        # components merge as more of the map is covered)
        n_disc_regions=mean(n_disc_at_decision),
        n_disc_regions_max=float(max(log.n_regions)) if log.n_regions else 0.0,
        frac_chose_region=chosen_r / max(1, nd),
        frac_chose_launch=chosen_l / max(1, nd),
        frac_chose_tx=chosen_tx / max(1, nd),
        frac_chose_explore=chosen_ex / max(1, nd),
        mean_dist_nonlaunch=mean(dists_nonlaunch),
        mean_dist_launch=mean(dist_launch),
        mean_phat_nonlaunch=mean(phat_nonlaunch),
        mean_phat_launch=mean(phat_launch),
        mean_horizon=mean(horizons),
        p_transmit_now=mean(p_by_action.get("transmit_now", [])),
        p_goto_launch=mean(p_by_action.get("goto_launch", [])),
        p_goto_region=mean(p_by_action.get("goto_region", [])),
        p_explore=mean(p_by_action.get("explore", [])),
        et_transmit_now=mean(et_by_action.get("transmit_now", [])),
        et_goto_launch=mean(et_by_action.get("goto_launch", [])),
        et_goto_region=mean(et_by_action.get("goto_region", [])),
        et_explore=mean(et_by_action.get("explore", [])),
        # horizon / travel distance. < 1 means the deadline expires before the
        # agent could even get there, so the move is not a real option.
        tightness_launch=mean(tight_launch),
        tightness_region=mean(tight_region),
        frac_tight_launch=float(np.mean([v < 1.0 for v in tight_launch]))
        if tight_launch else np.nan,
        frac_tight_region=float(np.mean([v < 1.0 for v in tight_region]))
        if tight_region else np.nan,
        p_spread=mean([max(v) - min(v) for v in
                       zip(*[p_by_action[k] for k in p_by_action])])
        if len(p_by_action) > 1 else np.nan,
    )


def summarise(log) -> Dict:
    outs = event_outcomes(log)
    obs = [o for o in outs if o["observable"]]
    near = [o for o in outs if o["observable_near"]]
    lat_vals = [o["latency"] for o in obs if o["latency"] is not None]
    aq = alarm_quality(log, only_observable=True)
    fa = false_alarm_detours(log)
    ru = region_usage(log)
    frac = lambda v, k: float(np.mean([o[k] for o in v])) if v else np.nan
    lu = [ok for (_t, ok) in log.launch_upload]
    d = dict(
        scenario=log.scenario, conn=getattr(log, "conn_scenario", "?"),
        seed=log.seed, method=log.method,
        n_events_all=len(outs), n_events_obs=len(obs), n_events_near=len(near),
        observable_frac=frac(outs, "observable"),
        on_time_ratio=frac(obs, "on_time"),
        on_time_ratio_all=frac(outs, "on_time"),
        on_time_ratio_near=frac(near, "on_time"),
        ever_known_ratio=float(np.mean([o["ever_t"] is not None for o in obs]))
        if obs else np.nan,
        mean_latency=float(np.mean(lat_vals)) if lat_vals else np.nan,
        p95_latency=float(np.percentile(lat_vals, 95)) if lat_vals else np.nan,
        map_rmse=map_error(log), misbelief_frac=misbelief_fraction(log),
        coverage=float(log.visited.mean()),
        n_fires=aq["n_fires"], detection_rate=aq["detection_rate"],
        false_alarm_rate=aq["false_alarm_rate"], mean_delay=aq["mean_delay"],
        n_detours=fa["n_detours"], n_false_detours=fa["n_false_detours"],
        n_deliveries=len(log.deliveries), n_attempts=log.n_attempts,
        n_alerts=len(log.alerts), n_dropped=len(log.dropped),
        n_dropped_cap=sum(1 for (_t, r) in log.dropped if r == "attempt_cap"),
        n_dropped_deadline=sum(1 for (_t, r) in log.dropped if r == "deadline"),
        n_regions_true=max(0, len(log.regions_true) - 1),
        travel=log.dist, energy=log.dist + log.n_attempts,
        n_regions=log.n_regions[-1], seconds=log.seconds,
        gp_seconds=log.gp_seconds,
        launch_upload_ok=int(sum(lu)), launch_upload_tries=len(lu),
    )
    d.update(ru)
    if log.cfg is not None:          # F5: provenance on every row
        d.update(manifest(log.cfg))
    return d
