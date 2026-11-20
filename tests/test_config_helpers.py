"""Invariants for the experiment-programme config helpers.

Each helper moves ONE thing. These tests exist because the programme's
credibility rests on that: a helper that quietly changed a second quantity
would reintroduce exactly the class of confound F1 was added to remove.
"""
import numpy as np
import pytest

from urgency_sim.config import (Config, with_conn, with_grid, with_agent_speed,
                                with_mission, with_hazard, with_channel,
                                with_regions, with_region_size, with_deviation,
                                explorability, gp_capacity)
from urgency_sim.connectivity import coverage_fraction, required_separation
from urgency_sim.field import PollutantField, cfl_limit

GRIDS = [40, 60, 80, 120]
CONNS = ["sparse", "dense"]


# ---- explorability -----------------------------------------------------
def test_explorability_is_direct_sampling_only():
    """The agent is a strict POINT sensor: sim.py samples its own cell and
    nowhere else, and sensor_range appears only in metrics.observability. An
    earlier version multiplied by a (2r+1) swath and reported 3.50 for the
    Phase 3 configuration; the correct figure is 0.50."""
    assert explorability(Config()) == pytest.approx(0.5, abs=1e-9)
    wide = Config()
    wide = dataclasses_replace_sensor(wide, 10.0)
    assert explorability(wide) == explorability(Config())


def dataclasses_replace_sensor(cfg, r):
    from dataclasses import replace
    return replace(cfg, agent=replace(cfg.agent, sensor_range=r))


def test_explorability_spans_the_regime_boundary_via_mission_length():
    """Mission length is E1's primary lever precisely because it moves
    explorability across 1.0 while leaving the GP, the plume and the
    connectivity untouched."""
    e = [explorability(with_mission(Config(), t)) for t in (200, 400, 800, 1600)]
    assert e == sorted(e)
    assert e[0] < 1.0 <= e[-1]


def test_explorability_falls_as_the_domain_grows():
    e = [explorability(with_grid(Config(), n)) for n in GRIDS]
    assert e == sorted(e, reverse=True)


# ---- gp_capacity -------------------------------------------------------
def test_gp_capacity_falls_with_area_and_bounds_the_grid_arm():
    """The cloud GP rebuilds from a FIXED 140-point window, so its coverage of
    the domain shrinks as the domain grows. Measured at n=120 (capacity ~1.1)
    every method collapses to on-time 0.00-0.06, which is why E1's grid arm
    stops at n=60."""
    cap = {n: gp_capacity(with_grid(Config(), n)) for n in GRIDS}
    assert cap[40] > cap[60] > cap[80] > cap[120]
    assert cap[60] > 4.0, "n=60 must stay well clear of the degenerate boundary"
    assert cap[120] < 1.5, "n=120 is degenerate; the grid arm must exclude it"


def test_gp_capacity_scales_with_window_and_length_scale():
    from dataclasses import replace
    base = Config()
    wider = replace(base, gp=replace(base.gp, window=base.gp.window * 2))
    assert gp_capacity(wider) == pytest.approx(2 * gp_capacity(base))


# ---- with_grid ---------------------------------------------------------
@pytest.mark.parametrize("conn", CONNS)
@pytest.mark.parametrize("n", GRIDS)
def test_grid_keeps_regions_separable(conn, n):
    """Config.__post_init__ calls validate_comm, so constructing an unseparable
    layout raises. This is the guard that caught the dense-discovery bug."""
    cfg = with_grid(with_conn(Config(), conn), n)
    assert cfg.comm.min_separation >= required_separation(cfg.comm)


@pytest.mark.parametrize("conn", CONNS)
def test_grid_holds_coverage_fraction_roughly_constant(conn):
    """Scaling region count with AREA is what isolates explorability; without
    it, a bigger domain would also be a less connected one."""
    cov = [coverage_fraction(with_grid(with_conn(Config(), conn), n), 40)[1]
           for n in GRIDS]
    assert max(cov) / min(cov) < 1.35, cov


@pytest.mark.parametrize("n", GRIDS)
def test_grid_keeps_every_position_inside_the_domain(n):
    c = with_grid(Config(), n)
    for xy in (c.fld.source_xy, c.fld.new_source_xy, c.agent.start_xy,
               c.ev.zone_xy):
        assert 0 <= xy[0] < n and 0 <= xy[1] < n, xy


def test_grid_scales_positions_proportionally():
    base, big = Config(), with_grid(Config(), 120)
    k = 3.0
    assert big.fld.source_xy == tuple(round(v * k) for v in base.fld.source_xy)
    assert big.comm.radius_hi == pytest.approx(base.comm.radius_hi * k)


def test_grid_leaves_time_and_wind_alone():
    """with_grid must move SIZE only; mission length and wind are E6's and the
    speed sweep's levers respectively."""
    base, big = Config(), with_grid(Config(), 80)
    assert big.agent.mission_ticks == base.agent.mission_ticks
    assert big.fld.wind == base.fld.wind
    assert big.agent.speed == base.agent.speed


@pytest.mark.parametrize("n", GRIDS)
def test_grid_field_stays_stable(n):
    cfg = with_grid(Config(), n)
    f = PollutantField(cfg)
    assert f.dt <= f.SAFETY * cfl_limit(cfg.fld, cfg.fld.wind) + 1e-12
    for _ in range(25):
        f.step()
    assert np.isfinite(f.c).all() and f.c.min() >= 0.0


def test_grid_can_hold_region_count_fixed():
    """scale_regions=False is E2's lever: a bigger world with the same number
    of uplinks is a scarcer one."""
    big = with_grid(Config(), 120, scale_regions=False)
    assert big.comm.n_extra_lo == Config().comm.n_extra_lo


# ---- the one-thing-at-a-time helpers -----------------------------------
def test_agent_speed_moves_only_speed():
    base, fast = Config(), with_agent_speed(Config(), 3)
    assert fast.agent.speed == 3
    assert fast.agent.mission_ticks == base.agent.mission_ticks
    assert fast.fld.wind == base.fld.wind
    assert explorability(fast) == pytest.approx(3 * explorability(base))


def test_mission_moves_only_length():
    base, long = Config(), with_mission(Config(), 1600)
    assert long.agent.mission_ticks == 1600
    assert long.fld.n == base.fld.n and long.agent.speed == base.agent.speed
    assert explorability(long) == pytest.approx(2 * explorability(base))


def test_hazard_moves_only_hazard():
    base, h = Config(), with_hazard(Config(), 0.5)
    assert h.urg.hazard == 0.5
    assert h.urg.z_trigger == base.urg.z_trigger
    assert h.fld == base.fld


@pytest.mark.parametrize("mean_burst", [1.0, 2.86, 8.0, 20.0])
def test_channel_varies_burstiness_at_constant_mean_loss(mean_burst):
    """Longer, rarer outages for the same average loss -- otherwise a
    burstiness sweep would also be a loss-rate sweep."""
    base = Config()
    pi0 = base.comm.p_gb / (base.comm.p_gb + base.comm.p_bg)
    c = with_channel(base, mean_burst)
    pi = c.comm.p_gb / (c.comm.p_gb + c.comm.p_bg)
    assert pi == pytest.approx(pi0, rel=1e-9)
    assert 1.0 / c.comm.p_bg == pytest.approx(mean_burst, rel=1e-9)
    assert c.comm.loss_good == base.comm.loss_good


def test_regions_moves_count_not_size():
    c = with_regions(Config(), 2)
    assert c.comm.n_extra_lo == c.comm.n_extra_hi == 2
    assert c.comm.radius_hi == Config().comm.radius_hi


def test_region_size_moves_size_not_count():
    base = with_conn(Config(), "sparse")
    c = with_region_size(base, 1.4)
    assert c.comm.n_extra_lo == base.comm.n_extra_lo
    assert c.comm.radius_hi == pytest.approx(base.comm.radius_hi * 1.4)
    assert c.comm.min_separation >= required_separation(c.comm)


# ---- composition -------------------------------------------------------
def test_helpers_compose_without_breaking_validation():
    """The programme applies several at once; none may invalidate another."""
    c = with_region_size(
        with_channel(
            with_hazard(
                with_mission(
                    with_agent_speed(
                        with_grid(with_conn(Config(), "dense"), 80), 2),
                    1200),
                0.25),
            8.0),
        1.0)
    assert c.fld.n == 80 and c.agent.speed == 2
    assert c.agent.mission_ticks == 1200 and c.urg.hazard == 0.25
    assert c.comm.min_separation >= required_separation(c.comm)


def test_deviation_origin_reproduces_predictable():
    """with_deviation(0, 0) must be the predictable scenario in every respect
    that matters, so the graded sweep is anchored rather than offset."""
    base = Config()
    c = with_deviation(base, 0.0, 0.0)
    assert c.fld.new_source_q == 0.0
    assert np.allclose(c.fld.wind_after, base.fld.wind)
