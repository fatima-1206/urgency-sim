"""The field solver is the one component where a silent bug invalidates
everything downstream: an unstable integration still returns numbers."""
import dataclasses as dc

import numpy as np
import pytest

from urgency_sim.config import Config, with_speed, with_scenario
from urgency_sim.field import PollutantField, cfl_limit, rollout_field

RATIOS = [0.1, 0.25, 0.5, 0.75, 1.0, 1.5]


def test_cfl_is_the_combined_form_not_the_minimum():
    """Advection and diffusion share one explicit update, so their rate limits
    ADD. Using min(adv, dif) is too permissive and was the original bug: the
    field diverged to 1e35 once D was raised."""
    fc = dc.replace(Config().fld, diffusion=0.2, dx=1.0)
    lim = cfl_limit(fc, (0.3, 0.1))
    assert lim == pytest.approx(1.0 / (0.4 / 1.0 + 4 * 0.2))
    assert lim < min(1.0 / 0.4, 1.0 / (4 * 0.2))


@pytest.mark.parametrize("ratio", RATIOS)
@pytest.mark.parametrize("scen", ["predictable", "unpredictable"])
def test_substepping_keeps_dt_inside_cfl_for_every_swept_wind(ratio, scen):
    cfg = with_speed(with_scenario(Config(), scen), ratio)
    f = PollutantField(cfg)
    for w in (cfg.fld.wind, cfg.fld.wind_after):
        assert f.dt <= PollutantField.SAFETY * cfl_limit(cfg.fld, w)


@pytest.mark.parametrize("ratio", [0.1, 1.0, 1.5])
def test_field_stays_finite_and_bounded_across_the_sweep(ratio):
    hist = rollout_field(with_speed(Config(), ratio), 200)
    assert np.isfinite(hist).all()
    assert hist.min() >= 0.0            # concentration is clipped at zero
    assert hist.max() < 50.0            # no blow-up


def test_dilution_decoupling_flattens_peak_across_speeds():
    """F1. Without it the sweep confounds speed with difficulty: the peak fell
    5.58 -> 1.22 across ratio 0.1 -> 1.5. The correction must cut that spread
    by at least 3x. It is NOT expected to be exact -- the plume is not purely
    advective -- so the bound is deliberately loose."""
    def peaks(dec):
        return np.array([rollout_field(with_speed(Config(), r, decouple=dec),
                                       300).max() for r in RATIOS])
    off, on = peaks(False), peaks(True)
    spread = lambda a: a.max() / a.min()
    assert spread(off) > 4.0
    assert spread(on) < spread(off) / 3.0


def test_dilution_is_off_by_default():
    """Default configs must reproduce the pilot exactly, so wind_ref is None
    unless with_speed() sets it."""
    assert Config().fld.wind_ref is None
    assert PollutantField(Config())._dilution_gain(0) == 1.0


def test_pulsing_source_keeps_producing_variation():
    """A constant source equilibrates and stops producing hazard crossings,
    which made the 'predictable' scenario degenerate in the first prototype."""
    hist = rollout_field(Config(), 400)
    late = hist[200:].max(axis=(1, 2))
    assert late.std() / late.mean() > 0.02
