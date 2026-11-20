"""The GP was rewritten to bypass sklearn after the one-time hyperparameter
fit (G1). That is only safe if two things hold: the direct path agrees with
sklearn, and the hyperparameters really are frozen."""
import numpy as np
import pytest

from urgency_sim import gpmodel
from urgency_sim.config import Config


def test_direct_path_matches_a_live_sklearn_gp():
    """Guards the 2.41x speedup. If this fails the fast path is wrong, not
    merely different."""
    gpmodel.selftest(seed=0, n=120, m=60, tol=1e-8)


@pytest.mark.parametrize("want", ["mean", "std", "both"])
def test_want_is_a_pure_optimisation(want):
    """G2 skips work the caller will not use; it must not change the answer."""
    rng = np.random.default_rng(1)
    g = _fitted(rng)
    Q = rng.uniform(0, 20, size=(40, 3))
    mu, sd = g.predict(Q, return_std=True)
    got = g.predict(Q, want=want)
    if want == "mean":
        assert np.allclose(got, mu, atol=0, rtol=0)
    elif want == "std":
        assert np.allclose(got, sd, atol=0, rtol=0)
    else:
        assert np.allclose(got[0], mu) and np.allclose(got[1], sd)


def test_hyperparameters_stay_frozen_after_the_first_fit():
    """The fit is bounded and done once. If a later refit re-optimised, the
    hyperparameters could drift into the degenerate solution the pilot hit
    (length_scale [2, 2, 200], noise 0.52 -- 'it is all noise')."""
    rng = np.random.default_rng(2)
    g = _fitted(rng)
    ls0, amp0, noise0 = np.array(g._ls).copy(), g._amp, g._noise
    for t in range(60, 200, 7):
        g.add(*_obs(rng, t))
        g.maybe_refit(t)
    assert np.array_equal(np.array(g._ls), ls0)
    assert g._amp == amp0 and g._noise == noise0


def test_prior_sd_is_not_larger_than_the_field():
    """The bootstrap deadlock: with a prior sd of 1.0 against a field sd of
    ~0.13, |obs-mu|/sd never crosses any trigger, so nothing is ever sent and
    the sd never shrinks."""
    assert np.sqrt(Config().gp.amplitude) < 0.2


def _obs(rng, t):
    x, y = rng.integers(0, 30, 2)
    return int(x), int(y), int(t), float(rng.normal(0.2, 0.1))


def _fitted(rng):
    cfg = Config()
    g = gpmodel.FieldGP(cfg.gp)
    for t in range(0, 60):
        g.add(*_obs(rng, t))
    g.maybe_refit(59)
    assert g._L is not None, "GP did not fit"
    return g
