"""All tunable parameters in one place.

Unit convention: 1 cell = 20 m, 1 tick = 10 s. The 40x40 grid is an 800 m
square and an 800-tick mission is about 2h15.

Grid/mission history: 50x50/400 -> 30x30/600 (pilot; 50x50 left path
coverage near a ~12% ceiling) -> 40x40/800 for the study. 40x40 keeps
coverage at ~0.33 and gives the connectivity regions room to be separable,
which 30x30 did not (dense discovery found 0.96 of 4.00 real regions).
Do NOT go to 50x50: coverage falls to ~0.22.
Lengths are in cells and unchanged; only POSITIONS and the mission length
are rescaled by 40/30.
"""
from dataclasses import dataclass, field, replace
from typing import Tuple


@dataclass(frozen=True)
class FieldCfg:
    n: int = 40
    dx: float = 1.0
    dt: float = 0.5             # integration substep
    substeps: int = 2           # one tick = substeps * dt = 1.0 time unit
    diffusion: float = 0.20
    decay: float = 0.002
    wind: Tuple[float, float] = (0.30, 0.10)
    source_xy: Tuple[int, int] = (8, 11)
    source_q: float = 1.6
    # Release is modulated: a constant tap reaches steady state and then stops
    # producing events at all.
    pulse_amp: float = 0.75
    pulse_period: float = 110.0
    # --- unpredictable scenario only ---
    wind_shift_t: int = 347
    wind_after: Tuple[float, float] = (-0.05, 0.33)
    new_source_t: int = 427
    new_source_xy: Tuple[int, int] = (25, 5)
    new_source_q: float = 1.3
    spinup: int = 20
    # set False for the speed sweep so |wind| is exactly the target ratio
    jitter_wind_mag: bool = True
    # --- dilution decoupling (F1) ---
    # In an advection-dominated plume the steady-state concentration near a
    # source falls as ~1/|wind|, so sweeping wind speed at fixed source_q
    # changes DIFFICULTY as well as speed: in the pilot sweep the peak fell
    # 5.76 -> 1.38 and alarms fell 44.5 -> 0.1 per run, which confounds the
    # staleness hypothesis with "there is nothing left to detect".
    # When wind_ref is set, every release rate is multiplied by
    #     (|wind(t)| / wind_ref) ** dilution_exp
    # so the peak concentration is held roughly constant across speeds.
    # None = off (the pilot behaviour), so existing results are unchanged.
    wind_ref: float | None = None
    # Exponent FITTED, not assumed. Pure advection would give 1.0, but the
    # plume is not advection-dominated here (D = 0.20 and the domain is
    # finite), and 1.0 over-corrects: it inverts the trend (peak 1.76 -> 5.80
    # across ratio 0.1 -> 1.5). 0.55 is the flattest over that range.
    dilution_exp: float = 0.55


@dataclass(frozen=True)
class CommCfg:
    """Connectivity regions.

    NOTE ON RADIUS. `quality(d) = peak * exp(-0.5 * d^2 / (radius/2)^2)`, so
    at d = radius the quality is exp(-2) = 13.5% of peak. The radius is the
    far tail, NOT a coverage boundary: the contour where delivery probability
    is 0.5 sits at roughly 0.57 * radius for a strong region. Use
    `coverage_fraction()` in connectivity.py to measure real coverage.
    """
    n_extra_lo: int = 2
    n_extra_hi: int = 4
    radius_lo: float = 3.0
    radius_hi: float = 5.0
    peak_lo: float = 0.55
    peak_hi: float = 0.92
    launch_radius: float = 4.5
    launch_peak: float = 0.95
    # Regions must be far enough apart that their USABLE areas do not
    # merge into one blob, otherwise 'move to a region' is meaningless.
    min_separation: float = 14.0
    # Gilbert-Elliott
    p_gb: float = 0.12
    p_bg: float = 0.35
    loss_good: float = 0.02
    loss_bad: float = 0.85
    # discovery: covered cells are grouped into regions by connected
    # components after a dilation, so one physical region cannot shatter into
    # several phantom ones (the old nearest-centroid merge reported 9-14
    # regions where 3-5 existed).
    # A cell counts as covered only if the link there is actually usable.
    # At 0.25 the covered areas of neighbouring regions overlap and the
    # clustering collapses them into a single region.
    discover_threshold: float = 0.50
    cluster_dilate: int = 1          # cells; bridges separate passes
    # --- two-tier messaging ---
    # A short ALERT can be pushed from anywhere with per-tick retries, but the
    # FULL UPLOAD that actually updates the cloud map needs a sustained link:
    # `upload_consec` consecutive successful ticks, OR an instantaneous
    # effective delivery probability above `upload_q_direct`.
    upload_consec: int = 3
    upload_q_direct: float = 0.80
    max_attempts_per_item: int = 45  # retries are capped, not free


# Connectivity scenarios, recalibrated for the 40x40 grid against
# "fraction of cells whose effective per-attempt delivery probability > 0.5"
# (connectivity.coverage_fraction(), 40 seeds):
#   sparse -> 13.4% effective coverage, 4.5 extra regions, all placed
#   dense  -> 33.9% effective coverage, 4.5 requested / 3.98 placed
#
# `min_separation` is per-scenario because it must clear
# connectivity.required_separation() for that scenario's radii (F4).
#
# GEOMETRIC CEILING, worth reporting as a limitation: on a 40x40 grid the
# dense scenario cannot exceed ~0.34 effective coverage while keeping regions
# separable at the discovery threshold. Pushing radii to [16,18] makes
# placement fail (0.65 of 5.5 regions placed) and coverage COLLAPSES to 0.127.
# The pilot's 31.9% at 30x30 was only reached by violating separability, which
# is exactly why dense discovery reported 0.96 regions where 4.00 existed.
CONN_SCENARIOS = {
    "sparse": dict(radius_lo=9.0, radius_hi=11.0, peak_lo=0.72, peak_hi=0.95,
                   n_extra_lo=4, n_extra_hi=5, launch_radius=9.0,
                   launch_peak=0.95, min_separation=15.5),
    "dense":  dict(radius_lo=15.0, radius_hi=16.0, peak_lo=0.88, peak_hi=0.97,
                   n_extra_lo=4, n_extra_hi=5, launch_radius=15.0,
                   launch_peak=0.97, min_separation=21.5),
}


@dataclass(frozen=True)
class AgentCfg:
    start_xy: Tuple[int, int] = (20, 20)
    speed: int = 1
    sensor_noise: float = 0.04
    mission_ticks: int = 800
    # Observability radius. The sensor is a point sensor, but the field is
    # smooth over the GP length scale, so a reading within this distance of a
    # cell carries real information about it. Used to decide which
    # ground-truth events were observable at all.
    sensor_range: float = 3.0
    # Pre-departure upload: the agent dwells at the launch point, sampling and
    # uploading, before it departs. This replaces the heartbeat and is what
    # bootstraps the cloud belief.
    launch_dwell: int = 12


@dataclass(frozen=True)
class GPCfg:
    window: int = 140
    refit_every: int = 6
    init_fit_at: int = 40
    length_scale: Tuple[float, float, float] = (6.0, 6.0, 60.0)
    noise: float = 0.0016       # = sensor_noise^2
    # Prior variance matched to the field's actual variation (measured
    # var ~ 0.016, sd ~ 0.13) so the prior sd is not larger than the field.
    amplitude: float = 0.016
    cand_grid_stride: int = 3


@dataclass(frozen=True)
class UrgencyCfg:
    hazard: float = 0.35
    k_consistent: int = 3
    # score = w_surprise * |obs-mu|/sd  +  w_consequence * max(0, obs-hazard)/scale
    # Additive, not multiplicative: a reading far above the hazard level is
    # urgent even where the cloud model is uncertain (and so surprise is small).
    w_surprise: float = 1.0
    w_consequence: float = 1.0
    consequence_scale: float = 0.25
    # Calibrated by scripts/calibrate.py against the threshold baseline's
    # rate (11.4 fires/run at 40x40), i.e. a matched alarm budget. Achieved:
    # proposed 9.8, surprise_abl 12.0, raw_abl 12.2, time_urg 12.3 -- all
    # within 15%. NOTE: calibration uses 5 seeds per cell and the fire-rate
    # curve is visibly noisy at that n (proposed: 7.3 at trigger 2.35 but 7.9
    # at 2.50), so treat the triggers as accurate to about +/-0.05.
    z_trigger: float = 2.2          # calibrated to a matched alarm budget
    sd_floor: float = 0.02
    # deadline mapping, recalibrated so urgency actually spreads the range
    # Tightened: with deadlines of 100+ ticks and per-tick retries, every
    # action reached P(deliver) ~ 1 and the choice was arbitrary. See
    # check 10 for deadline-vs-travel-time tightness.
    # Calibrated for tightness: 43% of decisions have horizon < 3x the
    # travel distance to the nearest region, 6% < 1x (moving is not even
    # possible). At [12,70] only 4% were inside 3x and the move was
    # always affordable, so the action choice carried no tension.
    deadline_min: float = 4.0
    deadline_max: float = 24.0
    # p10 and p90 of the observed urgency-at-fire distribution, so the
    # full deadline range is actually used (the first prototype had
    # urgency_ref=6 against a p90 of 2.7, making deadlines near-constant).
    urgency_lo: float = 2.66        # urgency at/below this -> deadline_max
    urgency_hi: float = 8.10        # urgency at/above this -> deadline_min
    # F3: the linear map above piled 62% of deadlines at the ceiling, because
    # urgency-at-fire is heavy-tailed: a linear interpolation between p10 and
    # p90 still leaves most of the mass bunched at the low end. The PERCENTILE
    # map instead sends the urgency's empirical rank to the deadline range, so
    # deadlines are uniform by construction and every bin is populated.
    # `urgency_q` is 11 quantiles at p0, p10, ... p100 of urgency-at-fire for
    # the calibrated method, produced by scripts/calibrate.py. Empty -> fall
    # back to the linear map, so the pilot behaviour is still reachable.
    deadline_map: str = "percentile"            # or "linear"
    urgency_q: Tuple[float, ...] = (2.258, 2.656, 2.903, 3.146, 3.452,
                                    3.825, 4.237, 4.964, 6.111, 8.097,
                                    23.265)


@dataclass(frozen=True)
class DecisionCfg:
    n_rollouts: int = 200
    tx_attempt_every: int = 1
    redecide_every: int = 8
    explore_tiebreak: float = 0.04
    # 'p_deliver'  : argmax P(full upload completes before the deadline)
    # 'exp_time'   : argmin expected time to complete the full upload
    #                (censored at the deadline). Use when P saturates near 1
    #                and the argmax becomes arbitrary.
    select_by: str = "exp_time"
    energy_per_attempt: float = 1.0


@dataclass(frozen=True)
class EvalCfg:
    zone_xy: Tuple[int, int] = (32, 27)
    zone_half: int = 2
    event_min_gap: int = 20
    event_grid_stride: int = 2
    match_radius: float = 4.0
    match_window: int = 25
    # How often the cloud belief is sampled on the event lattice. This exists
    # only to score events, and deadlines are ~18 ticks, so per-tick sampling
    # is far finer than the metric needs. Recomputing it every tick was 66% of
    # total runtime. k=2 measures 2.0x faster for a 0.002 shift in on-time
    # ratio; the shift is identical for every method, so paired comparisons are
    # unaffected, and it can only ever UNDER-report (a brief crossing between
    # samples is missed). k must be fixed across a study and recorded.
    cloud_lat_every: int = 2


@dataclass(frozen=True)
class Config:
    fld: FieldCfg = field(default_factory=FieldCfg)
    comm: CommCfg = field(default_factory=CommCfg)
    agent: AgentCfg = field(default_factory=AgentCfg)
    gp: GPCfg = field(default_factory=GPCfg)
    urg: UrgencyCfg = field(default_factory=UrgencyCfg)
    dec: DecisionCfg = field(default_factory=DecisionCfg)
    ev: EvalCfg = field(default_factory=EvalCfg)
    scenario: str = "predictable"       # or "unpredictable"
    conn_scenario: str = "sparse"       # or "dense"

    def __post_init__(self):
        # F4: region geometry must be discoverable, checked at load.
        from .connectivity import validate_comm
        validate_comm(self.comm)


def with_scenario(cfg: Config, scenario: str) -> Config:
    return replace(cfg, scenario=scenario)


def with_speed(cfg: Config, ratio: float, decouple: bool = True) -> Config:
    """Rescale BOTH wind vectors so |wind| = ratio * agent speed, keeping
    direction. Magnitude jitter is switched off so the sweep x-axis is exact;
    direction and source jitter are kept.

    `decouple` (F1) anchors `wind_ref` at the config's NATIVE wind speed, so
    release rates scale with |wind| and the plume's peak concentration stays
    roughly constant across the sweep. Gain is exactly 1 at the native speed,
    so the sweep is anchored on the pilot configuration. Pass decouple=False
    to reproduce the pilot's confounded sweep.
    """
    import numpy as _np
    sp = float(ratio) * cfg.agent.speed
    ref = float(_np.hypot(*cfg.fld.wind))
    def _scale(w):
        m = _np.hypot(*w)
        return (w[0] / m * sp, w[1] / m * sp) if m > 1e-12 else (sp, 0.0)
    return replace(cfg, fld=replace(cfg.fld, wind=_scale(cfg.fld.wind),
                                    wind_after=_scale(cfg.fld.wind_after),
                                    jitter_wind_mag=False,
                                    wind_ref=(ref if decouple else None)))


def with_deviation(cfg: Config, shift_deg: float = 0.0,
                   src_frac: float = 0.0) -> Config:
    """Graded departure from predictability, replacing the binary
    predictable/unpredictable switch.

    The Phase 3 study had only two settings: no perturbation at all, or BOTH
    shocks at full strength -- an 80.2 degree wind reversal AND an unannounced
    second source at 81% of the primary release rate. That is a violent jump,
    and it conflates two different disturbances, so a failure in the
    unpredictable cells could not be attributed to either.

    `shift_deg` rotates `wind_after` away from `wind` by that many degrees,
    keeping speed fixed. `src_frac` scales the second source as a fraction of
    the Phase 3 value (0 = no second source).

    shift_deg=0, src_frac=0 reproduces the predictable scenario; shift_deg=80.2,
    src_frac=1.0 reproduces the unpredictable one. Everything between is new.
    """
    import numpy as _np
    th = _np.radians(float(shift_deg))
    w = _np.asarray(cfg.fld.wind, dtype=float)
    rot = _np.array([[_np.cos(th), -_np.sin(th)], [_np.sin(th), _np.cos(th)]])
    after = rot @ w
    # Keep the post-shift SPEED equal to the pre-shift speed, so the deviation
    # dial changes direction only. Otherwise rotating would also change the
    # dilution gain and reintroduce the confound F1 removed.
    after = after / max(1e-12, float(_np.hypot(*after))) * float(_np.hypot(*w))
    return replace(cfg, scenario="unpredictable",
                   fld=replace(cfg.fld,
                               wind_after=(float(after[0]), float(after[1])),
                               new_source_q=cfg.fld.new_source_q * float(src_frac)))


def explorability(cfg: Config) -> float:
    """Fraction of the domain the agent can DIRECTLY SAMPLE in one mission.

        mission_ticks * speed / cells

    The agent is a strict POINT sensor: sim.py reads field.sample(x, y) at its
    own cell and nowhere else. `agent.sensor_range` is NOT a sensing swath --
    it appears only in metrics.observability, where it decides which
    ground-truth events are counted as observable when scoring. An earlier
    version of this function multiplied by a (2r+1) swath and reported 3.50 for
    the Phase 3 configuration, which was wrong; the correct figure is 0.50.

    So the agent already cannot sample the whole domain. What makes information
    plentiful anyway is the cloud GP: a 6-cell length scale means one sample
    informs a neighbourhood, and a 140-point window covers 1600 cells
    comfortably. See `gp_capacity`, which is the quantity that actually binds.
    """
    return (cfg.agent.mission_ticks * cfg.agent.speed) / float(cfg.fld.n ** 2)


def gp_capacity(cfg: Config) -> float:
    """How many times over can the cloud GP's sliding window cover the domain?

        window * pi * length_scale^2 / cells

    The cloud map is rebuilt from at most `gp.window` delivered points, each
    informing roughly a length-scale disc. This is fixed while the domain is
    not, so map quality must degrade with area regardless of which method feeds
    the GP -- below about 1 the comparison degenerates because every method
    scores near zero. At the Phase 3 configuration it is ~71.

    This is a property of change C7 (hyperparameters fitted once then frozen,
    with a sliding window) and is the real reason a larger grid cannot be used
    to test explorability without scaling the GP with it.
    """
    import math
    L = float(cfg.gp.length_scale[0])
    return cfg.gp.window * math.pi * L * L / float(cfg.fld.n ** 2)


def with_grid(cfg: Config, n: int, scale_regions: bool = True) -> Config:
    """Resize the domain to n x n, scaling every SPATIAL quantity by n/40.

    Positions (sources, launch point, sensitive zone) and lengths (region
    radii, launch radius, minimum separation) all scale together, so the layout
    is geometrically similar at every size and only the SCALE changes. Scaling
    positions without scaling region geometry would vary layout and scale at
    once -- the same class of confound F1 removed from the speed sweep.

    `scale_regions` additionally scales the region COUNT with area, holding the
    effective coverage fraction roughly constant so that explorability varies
    alone. Pass False to hold the count fixed, which makes connectivity scarcer
    as the domain grows (that is E2's job, not E1's).

    Mission length, wind and agent speed are deliberately untouched: the point
    is to move `explorability` by changing the size of the world.
    """
    k = float(n) / float(cfg.fld.n)

    def pos(xy):
        return (int(round(xy[0] * k)), int(round(xy[1] * k)))

    area = k * k
    cc = cfg.comm
    n_lo, n_hi = cc.n_extra_lo, cc.n_extra_hi
    if scale_regions:
        n_lo = max(1, int(round(cc.n_extra_lo * area)))
        n_hi = max(n_lo, int(round(cc.n_extra_hi * area)))
    return replace(
        cfg,
        fld=replace(cfg.fld, n=int(n), source_xy=pos(cfg.fld.source_xy),
                    new_source_xy=pos(cfg.fld.new_source_xy)),
        comm=replace(cc, radius_lo=cc.radius_lo * k, radius_hi=cc.radius_hi * k,
                     launch_radius=cc.launch_radius * k,
                     min_separation=cc.min_separation * k,
                     n_extra_lo=n_lo, n_extra_hi=n_hi),
        agent=replace(cfg.agent, start_xy=pos(cfg.agent.start_xy)),
        ev=replace(cfg.ev, zone_xy=pos(cfg.ev.zone_xy),
                   zone_half=max(1, int(round(cfg.ev.zone_half * k))),
                   match_radius=cfg.ev.match_radius * k),
    )


def with_agent_speed(cfg: Config, speed: int) -> Config:
    """Cells the agent moves per tick.

    NOTE: before this programme, `speed` was consulted only by the DECISION
    code (decision._path_qualities) while sim.py always stepped exactly one
    cell, so any value other than 1 made the planner believe the agent was
    faster than it was. sim.py now takes `speed` steps per tick; speed=1 is
    bit-identical to the previous behaviour.
    """
    return replace(cfg, agent=replace(cfg.agent, speed=int(speed)))


def with_mission(cfg: Config, ticks: int) -> Config:
    """Mission length. Also moves `explorability`, so E6 is analysed jointly
    with E1 on an explorability axis rather than as an independent factor."""
    return replace(cfg, agent=replace(cfg.agent, mission_ticks=int(ticks)))


def with_hazard(cfg: Config, hazard: float) -> Config:
    """The concentration that defines a critical event. Changing it changes the
    EVENT SET itself, so every endpoint moves with it; that is the point."""
    return replace(cfg, urg=replace(cfg.urg, hazard=float(hazard)))


def with_channel(cfg: Config, mean_burst: float) -> Config:
    """Gilbert-Elliott burstiness at (approximately) constant mean loss.

    The chain's stationary bad-state probability is p_gb / (p_gb + p_bg), and
    the mean dwell in the bad state is 1 / p_bg ticks. Holding the stationary
    probability at the Phase 3 value while setting 1/p_bg = mean_burst varies
    BURSTINESS alone -- longer, rarer outages for the same average loss. That
    isolates what the two-tier upload rule (3 consecutive successes) is for.
    """
    cc = cfg.comm
    pi_bad = cc.p_gb / (cc.p_gb + cc.p_bg)
    p_bg = 1.0 / float(mean_burst)
    p_gb = pi_bad * p_bg / (1.0 - pi_bad)
    return replace(cfg, comm=replace(cc, p_gb=float(p_gb), p_bg=float(p_bg)))


def with_regions(cfg: Config, n_extra: int) -> Config:
    """Number of coverage regions beyond the launch point, holding each
    region's SIZE fixed -- so coverage fraction moves with the count."""
    return replace(cfg, comm=replace(cfg.comm, n_extra_lo=int(n_extra),
                                     n_extra_hi=int(n_extra)))


def with_region_size(cfg: Config, scale: float) -> Config:
    """Scale region radii, holding the COUNT fixed, so coverage fraction moves
    without changing how many upload points there are to choose between.

    `min_separation` scales with the radii, since separability is what
    validate_comm enforces and what the geometric ceiling comes from.
    """
    cc = cfg.comm
    return replace(cfg, comm=replace(
        cc, radius_lo=cc.radius_lo * scale, radius_hi=cc.radius_hi * scale,
        launch_radius=cc.launch_radius * scale,
        min_separation=cc.min_separation * max(1.0, scale)))


def with_conn(cfg: Config, conn: str) -> Config:
    """Apply one of the named connectivity scenarios."""
    if conn not in CONN_SCENARIOS:
        raise ValueError(f"unknown connectivity scenario {conn!r}")
    return replace(cfg, conn_scenario=conn,
                   comm=replace(cfg.comm, **CONN_SCENARIOS[conn]))
