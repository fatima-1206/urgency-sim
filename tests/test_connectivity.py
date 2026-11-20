"""Region geometry (F4) and the coverage numbers the scenarios are named for."""
import dataclasses as dc

import numpy as np
import pytest

from urgency_sim.config import Config, CONN_SCENARIOS, with_conn
from urgency_sim.connectivity import (ConnectivityTruth, Region,
                                      coverage_fraction, ge_mean_multiplier,
                                      required_separation, validate_comm)


@pytest.mark.parametrize("conn", list(CONN_SCENARIOS))
def test_scenarios_satisfy_the_separation_requirement(conn):
    cc = with_conn(Config(), conn).comm
    assert cc.min_separation >= required_separation(cc)


def test_too_close_regions_are_rejected_at_config_load():
    """This is the bug the assertion exists for: at 30x30 the dense scenario
    had min_separation 14.0 against a requirement of 16.6, and discovery
    silently reported 0.96 regions where 4.00 existed."""
    cfg = Config()
    bad = dc.replace(cfg.comm, radius_lo=10.0, radius_hi=12.0, peak_hi=0.95,
                     min_separation=14.0)
    with pytest.raises(ValueError, match="min_separation"):
        validate_comm(bad)
    with pytest.raises(ValueError, match="min_separation"):
        dc.replace(cfg, comm=bad)           # Config.__post_init__


def test_inverted_bounds_are_rejected():
    cfg = Config()
    with pytest.raises(ValueError, match="inverted"):
        validate_comm(dc.replace(cfg.comm, radius_lo=9.0, radius_hi=3.0))


@pytest.mark.parametrize("conn,lo,hi", [("sparse", 0.10, 0.15),
                                        ("dense", 0.30, 0.40)])
def test_effective_coverage_is_in_the_advertised_band(conn, lo, hi):
    """The scenarios are DEFINED by effective coverage -- the fraction of
    cells whose per-attempt delivery probability, Gilbert-Elliott included,
    exceeds 0.5. If this drifts, the sparse/dense factor stops meaning what
    the report says."""
    _, eff, _ = coverage_fraction(with_conn(Config(), conn), n_seeds=40)
    assert lo <= eff <= hi, f"{conn} effective coverage {eff:.3f}"


@pytest.mark.parametrize("conn", list(CONN_SCENARIOS))
def test_most_requested_regions_are_actually_placed(conn):
    """Placement is rejection sampling against min_separation. If the grid is
    too small for the requested count it quietly places fewer -- which is how
    coverage COLLAPSED to 0.127 when radii were pushed to [16,18]."""
    cfg = with_conn(Config(), conn)
    got = np.mean([len(ConnectivityTruth(cfg, np.random.default_rng(s)).regions) - 1
                   for s in range(40)])
    want = (cfg.comm.n_extra_lo + cfg.comm.n_extra_hi) / 2
    assert got >= 0.85 * want, f"{conn}: placed {got:.2f} of {want:.1f}"


def test_radius_is_the_far_tail_not_a_coverage_boundary():
    """Documented in CommCfg and easy to misread off an animation: quality at
    d = radius is exp(-2) = 13.5% of peak."""
    r = Region(0.0, 0.0, 10.0, 0.9)
    assert r.quality(10.0, 0.0) == pytest.approx(0.9 * np.exp(-2.0))
    assert r.r_half < 0.6 * r.radius
    assert r.r_at(0.9 * 0.9) == pytest.approx(r.radius / 2 *
                                              np.sqrt(2 * np.log(1 / 0.9)))


def test_gilbert_elliott_multiplier_matches_the_stationary_chain():
    cc = Config().comm
    pi_bad = cc.p_gb / (cc.p_gb + cc.p_bg)
    assert ge_mean_multiplier(cc) == pytest.approx(
        (1 - pi_bad) * (1 - cc.loss_good) + pi_bad * (1 - cc.loss_bad))
    assert 0.0 < ge_mean_multiplier(cc) < 1.0


def test_overlapping_regions_combine_by_max_not_by_sum():
    """The agent only ever uses the best available link, so quality must not
    accumulate where regions overlap."""
    cfg = Config()
    truth = ConnectivityTruth(cfg, np.random.default_rng(0))
    for (x, y) in [(10, 10), (20, 20), (5, 30)]:
        assert truth.quality(x, y) == pytest.approx(
            max(r.quality(x, y) for r in truth.regions))
        assert truth.quality(x, y) <= max(r.peak for r in truth.regions)
