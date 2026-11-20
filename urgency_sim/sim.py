"""One mission = one (scenario, connectivity, seed, method) run."""
import dataclasses
import time
from functools import lru_cache
from dataclasses import dataclass, field as dfield
from typing import List, Optional

import numpy as np

from .config import Config
from .connectivity import ConnectivityTruth, DiscoveredMap
from .decision import evaluate_actions, choose
from .events import extract_events
from .field import rollout_field
from .gpmodel import FieldGP
from .methods import Method, METHODS
from .urgency import UrgencyDetector, Pending


def jitter_config(cfg: Config, rng: np.random.Generator) -> Config:
    """Per-seed variation of the field, so different seeds are genuinely
    different realisations rather than the same plume with a different radio."""
    fc = cfg.fld
    n = fc.n
    sx = int(np.clip(fc.source_xy[0] + rng.integers(-2, 3), 2, n - 3))
    sy = int(np.clip(fc.source_xy[1] + rng.integers(-2, 3), 2, n - 3))
    s = float(rng.uniform(0.85, 1.15)) if fc.jitter_wind_mag else 1.0
    ang = float(rng.uniform(-0.25, 0.25))
    u, v = fc.wind
    wu = s * (u * np.cos(ang) - v * np.sin(ang))
    wv = s * (u * np.sin(ang) + v * np.cos(ang))
    return dataclasses.replace(cfg, fld=dataclasses.replace(
        fc, source_xy=(sx, sy), wind=(float(wu), float(wv)),
        pulse_period=float(fc.pulse_period * rng.uniform(0.8, 1.25))))


@lru_cache(maxsize=4)
def _field_and_events(cfg: Config, seed: int):
    """Jittered config, true-field history and ground-truth events for one
    (config, seed). Deterministic, and identical for every method, so it is
    computed once and shared: nine methods per seed otherwise repeat it nine
    times. Callers must treat the returned arrays as read-only."""
    cfg_j = jitter_config(cfg, np.random.default_rng(seed * 7919 + 13))
    hist = rollout_field(cfg_j, cfg_j.agent.mission_ticks)
    hist.flags.writeable = False
    return cfg_j, hist, extract_events(cfg_j, hist)


@dataclass
class RunLog:
    scenario: str
    seed: int
    method: str
    conn_scenario: str = "?"
    pos: List = dfield(default_factory=list)
    action: List = dfield(default_factory=list)
    score: List = dfield(default_factory=list)
    pending_dl: List = dfield(default_factory=list)
    fires: List = dfield(default_factory=list)
    tx: List = dfield(default_factory=list)          # (t, x, y, success)
    alerts: List = dfield(default_factory=list)      # (t, x, y) alert got through
    deliveries: List = dfield(default_factory=list)  # (t, n_samples) full upload
    dropped: List = dfield(default_factory=list)     # (t, reason)
    detours: List = dfield(default_factory=list)
    launch_upload: List = dfield(default_factory=list)
    action_evals: List = dfield(default_factory=list)
    region_diag: List = dfield(default_factory=list)
    n_regions: List = dfield(default_factory=list)
    region_found: List = dfield(default_factory=list)
    cloud_lat: List = dfield(default_factory=list)
    cloud_maps: List = dfield(default_factory=list)
    events: List = dfield(default_factory=list)
    truth: Optional[np.ndarray] = None
    regions_true: List = dfield(default_factory=list)
    cfg: Optional[Config] = None
    seconds: float = 0.0
    gp_seconds: float = 0.0
    dist: float = 0.0
    n_attempts: int = 0


def run(cfg: Config, seed: int, method_key: str,
        record_maps: bool = False) -> RunLog:
    t_start = time.perf_counter()
    m: Method = METHODS[method_key]
    rng = np.random.default_rng(seed)

    cfg, hist, events = _field_and_events(cfg, seed)
    T = cfg.agent.mission_ticks
    n = cfg.fld.n
    cc = cfg.comm

    truth = ConnectivityTruth(cfg, rng)
    disc = DiscoveredMap(cfg)
    agent_gp = FieldGP(cfg.gp, "agent")
    cloud_gp = FieldGP(cfg.gp, "cloud")

    trig = m.trigger_level
    det = UrgencyDetector(cfg.urg, mode=m.trigger,
                          trigger=trig if trig is not None else None)

    x, y = cfg.agent.start_xy
    visited = np.zeros((n, n), dtype=bool)
    pending: Optional[Pending] = None
    undelivered: List = []
    t_last_delivery = 0
    cur_action, cur_target, cur_region = "explore", None, None
    explore_target = None
    last_decide = -10 ** 9
    dwell_until = cfg.agent.launch_dwell
    fixed_dl = 0.5 * (cfg.urg.deadline_min + cfg.urg.deadline_max)
    upload_streak = 0
    item_attempts = 0
    cloud_lat_cur = None
    alert_sent = False

    log = RunLog(cfg.scenario, seed, method_key, cfg.conn_scenario)
    log.cfg = cfg
    log.events = events
    log.truth = hist
    log.regions_true = [(r.cx, r.cy, r.radius, r.peak, r.is_launch)
                        for r in truth.regions]
    prev_nreg = len(disc.regions)

    def complete_upload(tick):
        """A full upload landed: everything the agent is carrying reaches
        the cloud and the cloud model is refitted."""
        nonlocal undelivered, t_last_delivery
        for (ux, uy, ut, uz) in undelivered:
            cloud_gp.add(ux, uy, ut, uz)
        cloud_gp.maybe_refit(tick, force=True)
        log.deliveries.append((tick, len(undelivered)))
        undelivered = []
        t_last_delivery = tick

    for t in range(T):
        visited[x, y] = True
        in_dwell = t < dwell_until

        # ---- sense -------------------------------------------------------
        z_obs = float(hist[t, x, y] + rng.normal(0.0, cfg.agent.sensor_noise))
        q_meas = truth.measure_quality(x, y, rng)
        disc.observe(x, y, q_meas, t)
        disc.maybe_relabel(t)
        if len(disc.regions) > prev_nreg:
            r = disc.regions[-1]
            log.region_found.append((t, r.cx, r.cy))
        prev_nreg = len(disc.regions)

        agent_gp.add(x, y, t, z_obs)
        agent_gp.maybe_refit(t)
        undelivered.append((x, y, t, z_obs))

        mu, sd = cloud_gp.predict([[x, y, t]])
        mu, sd = float(mu[0]), float(sd[0])

        # ---- urgency -------------------------------------------------------
        s_now = det.score(z_obs, mu, sd, t, t_last_delivery)
        log.score.append(s_now)
        if pending is None and not in_dwell:
            p = det.update(z_obs, mu, sd, t, t_last_delivery, x, y)
            if p is not None:
                if m.deadline == "fixed":
                    p = dataclasses.replace(p, deadline=t + fixed_dl)
                pending = p
                upload_streak, item_attempts, alert_sent = 0, 0, False
                log.fires.append((t, x, y, p.urgency, p.deadline))
                last_decide = -10 ** 9

        # ---- explore target -------------------------------------------------
        if t % 5 == 0 or explore_target is None:
            sdg = agent_gp.predict_grid(n, t, stride=cfg.gp.cand_grid_stride,
                                        want="std").copy()
            sdg[visited] *= 0.35
            ix = int(np.argmax(sdg))
            explore_target = (ix // n, ix % n)

        # ---- decide ----------------------------------------------------------
        if in_dwell:
            cur_action, cur_target, cur_region = "launch_upload", (x, y), None
        elif pending is not None:
            if m.action == "always_tx":
                cur_action, cur_target, cur_region = "transmit_now", (x, y), None
            elif t - last_decide >= cfg.dec.redecide_every:
                acts = evaluate_actions(cfg, disc, x, y, t, pending.deadline,
                                        explore_target, rng)
                a = choose(acts, cfg)
                if a.name.startswith("goto") and not cur_action.startswith("goto"):
                    log.detours.append((t, x, y, a.target, pending.fired_t))
                log.action_evals.append((t, [
                    (ac.name, round(float(ac.p_deliver), 4),
                     round(float(ac.exp_time), 2),
                     round(float(np.hypot(ac.target[0]-x, ac.target[1]-y))
                           if ac.target is not None else -1.0, 2))
                    for ac in acts], a.name))
                log.region_diag.append(dict(
                    t=t, chosen=a.name, n_disc=len(disc.regions),
                    horizon=float(pending.deadline - t),
                    regions=[dict(i=i, is_launch=r.is_launch,
                                  dist=float(np.hypot(r.cx-x, r.cy-y)),
                                  p_hat=float(r.p_hat()),
                                  q_best=float(r.q_best))
                             for i, r in enumerate(disc.regions)]))
                cur_action, cur_target, cur_region = a.name, a.target, a.region_idx
                last_decide = t
        else:
            cur_action, cur_target, cur_region = "explore", explore_target, None

        log.action.append(cur_action)
        log.pos.append((x, y))
        log.pending_dl.append(pending.deadline if pending else np.nan)
        log.n_regions.append(len(disc.regions))

        # ---- transmit ---------------------------------------------------------
        # Two tiers: one success pushes the short ALERT; the FULL UPLOAD needs
        # `upload_consec` consecutive successes, unless the link here is strong
        # enough (>= upload_q_direct) to push the payload in one go.
        q_true = truth.quality(x, y)
        need = 1 if q_true >= cc.upload_q_direct else cc.upload_consec

        if in_dwell:
            if undelivered:
                ok = truth.attempt(x, y, rng)
                log.n_attempts += 1
                log.tx.append((t, x, y, ok))
                log.launch_upload.append((t, ok))
                upload_streak = upload_streak + 1 if ok else 0
                if upload_streak >= need:
                    complete_upload(t)
                    upload_streak = 0
        elif pending is not None and t % cfg.dec.tx_attempt_every == 0:
            if item_attempts >= cc.max_attempts_per_item:
                log.dropped.append((t, "attempt_cap"))
                pending = None
                upload_streak, item_attempts, alert_sent = 0, 0, False
            else:
                ok = truth.attempt(x, y, rng)
                item_attempts += 1
                log.n_attempts += 1
                log.tx.append((t, x, y, ok))
                ridx = cur_region if cur_region is not None else disc.region_at(x, y)
                disc.record_attempt(ridx, ok, xy=(x, y))
                if ok and not alert_sent:
                    alert_sent = True
                    log.alerts.append((t, x, y))
                upload_streak = upload_streak + 1 if ok else 0
                if upload_streak >= need:
                    complete_upload(t)
                    pending = None
                    upload_streak, item_attempts, alert_sent = 0, 0, False
                    cur_action, cur_target, cur_region = "explore", explore_target, None
        cloud_gp.maybe_refit(t)

        # ---- record cloud belief ----------------------------------------------
        # Sampled every `cloud_lat_every` ticks and held in between; the log
        # still has one entry per tick so metrics index by tick unchanged.
        if t % cfg.ev.cloud_lat_every == 0 or cloud_lat_cur is None:
            cl = cloud_gp.predict_grid(n, t, stride=cfg.ev.event_grid_stride,
                                       want="mean")
            cloud_lat_cur = cl[::cfg.ev.event_grid_stride,
                               ::cfg.ev.event_grid_stride].copy()
        log.cloud_lat.append(cloud_lat_cur)
        if record_maps:
            cm = cloud_gp.predict_grid(n, t, stride=1, want="mean")
            log.cloud_maps.append(cm.astype(np.float32))

        # ---- move ---------------------------------------------------------------
        tgt = cur_target if cur_target is not None else explore_target
        if cur_action not in ("transmit_now", "launch_upload") and tgt is not None:
            # Take `speed` unit steps per tick. This previously took exactly one
            # step regardless of cfg.agent.speed, which the DECISION code does
            # consult (decision._path_qualities divides distance by it). At the
            # default speed of 1 the two agree, so the mismatch was invisible;
            # at any other speed the planner would have believed the agent moved
            # faster than it did. speed=1 is bit-identical to the old behaviour.
            for _ in range(max(1, int(cfg.agent.speed))):
                dx = int(np.sign(tgt[0] - x)); dy = int(np.sign(tgt[1] - y))
                if dx == 0 and dy == 0:
                    break
                nx = int(np.clip(x + dx, 0, n - 1)); ny = int(np.clip(y + dy, 0, n - 1))
                log.dist += float(np.hypot(nx - x, ny - y))
                x, y = nx, ny

        # ---- deadline expiry -------------------------------------------------------
        if pending is not None and t >= pending.deadline:
            log.dropped.append((t, "deadline"))
            pending = None
            upload_streak, item_attempts, alert_sent = 0, 0, False
            det.run = 0

    log.seconds = time.perf_counter() - t_start
    log.gp_seconds = agent_gp.fit_seconds + cloud_gp.fit_seconds
    log.visited = visited
    return log
