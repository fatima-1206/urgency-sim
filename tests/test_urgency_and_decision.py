"""The urgency formula, the deadline map (F3) and the two-tier delivery rule
that the Option C contribution rests on."""
import dataclasses as dc

import numpy as np
import pytest

from urgency_sim.config import Config, UrgencyCfg
from urgency_sim.decision import rollout_upload
from urgency_sim.urgency import UrgencyDetector

U = UrgencyCfg()


def test_urgency_is_additive_not_multiplicative():
    """The multiplicative version collapsed to ~0 exactly when the cloud model
    was ignorant, so a reading far above the hazard level was not urgent."""
    d = UrgencyDetector(U, "combined")
    far_above_hazard_but_unsurprising = d.score(
        obs=U.hazard + 3 * U.consequence_scale, mu=U.hazard + 3 * U.consequence_scale,
        sd=1.0, t=0, t_last_delivery=0)
    assert far_above_hazard_but_unsurprising == pytest.approx(3.0)


def test_sd_floor_bounds_the_surprise_term():
    d = UrgencyDetector(U, "surprise")
    assert d.surprise(0.5, 0.0, sd=1e-12) == pytest.approx(0.5 / U.sd_floor)


@pytest.mark.parametrize("mode,uses_sd", [("combined", True), ("surprise", True),
                                          ("raw", False), ("threshold", False)])
def test_raw_ablation_differs_from_surprise_only_by_the_sd_scaling(mode, uses_sd):
    d = UrgencyDetector(U, mode)
    a = d.score(0.6, 0.2, 0.1, 0, 0)
    b = d.score(0.6, 0.2, 0.4, 0, 0)
    assert (a != b) == uses_sd


def test_every_content_trigger_shares_the_k_of_k_gate():
    """Otherwise the comparison rewards whichever rule happens to lack a
    debounce rather than isolating the trigger signal."""
    for mode in ("combined", "surprise", "raw", "threshold"):
        d = UrgencyDetector(U, mode, trigger=0.0)
        fired = [d.update(1.0, 0.0, 0.1, t, 0, 5, 5) for t in range(U.k_consistent)]
        assert fired[:-1] == [None] * (U.k_consistent - 1), mode
        assert fired[-1] is not None, mode
    timer = UrgencyDetector(U, "time", trigger=0.0)
    assert timer.update(0.0, 0.0, 1.0, 10, 0, 5, 5) is not None   # exempt


def test_a_run_of_sub_trigger_readings_resets_the_gate():
    d = UrgencyDetector(U, "combined", trigger=1.0)
    d.update(1.0, 0.0, 0.1, 0, 0, 5, 5)
    d.update(0.0, 0.0, 0.1, 1, 0, 5, 5)          # below trigger -> reset
    assert d.run == 0 and d.buf == []


@pytest.mark.parametrize("mapping", ["linear", "percentile"])
def test_deadline_map_is_decreasing_and_inside_the_range(mapping):
    c = dc.replace(U, deadline_map=mapping,
                   urgency_q=tuple(np.linspace(1.0, 12.0, 11)))
    d = UrgencyDetector(c)
    vals = [d.deadline_for(u) for u in np.linspace(0, 20, 50)]
    assert all(c.deadline_min <= v <= c.deadline_max for v in vals)
    assert all(b <= a + 1e-12 for a, b in zip(vals, vals[1:]))


def test_percentile_map_spreads_deadlines_where_linear_piles_them_up():
    """F3. Urgency-at-fire is heavy-tailed, so the linear map put most of the
    mass at the deadline ceiling. The percentile map is uniform by
    construction."""
    rng = np.random.default_rng(0)
    u = rng.lognormal(0.3, 1.0, 4000)            # heavy-tailed, like the real one
    q = tuple(np.percentile(u, np.linspace(0, 100, 11)))
    lin = UrgencyDetector(dc.replace(U, deadline_map="linear", urgency_q=q))
    pct = UrgencyDetector(dc.replace(U, deadline_map="percentile", urgency_q=q))

    def busiest_bin(d):
        dl = np.array([d.deadline_for(x) for x in u])
        h, _ = np.histogram(dl, bins=8, range=(U.deadline_min, U.deadline_max))
        return h.max() / h.sum()

    assert busiest_bin(lin) > 0.40, "the linear map was supposed to pile up"
    assert busiest_bin(pct) < 0.20, "the percentile map should be near-uniform"


def test_empty_quantile_table_falls_back_to_the_linear_map():
    """So an uncalibrated config degrades predictably instead of crashing."""
    d = UrgencyDetector(dc.replace(U, deadline_map="percentile", urgency_q=()))
    assert d.deadline_for(U.urgency_lo) == pytest.approx(U.deadline_max)
    assert d.deadline_for(U.urgency_hi) == pytest.approx(U.deadline_min)


def test_full_upload_needs_a_sustained_link_but_an_alert_does_not():
    """The two-tier rule is the Option C contribution: an alert needs one
    successful tick, a full upload needs `upload_consec` in a row."""
    cc = Config().comm
    rng = np.random.default_rng(0)
    weak = [0.25] * 400
    done, alert = zip(*[rollout_upload(weak, cc, rng, 1, cc.upload_consec,
                                       cc.upload_q_direct,
                                       cc.max_attempts_per_item)
                        for _ in range(300)])
    ok = lambda v: np.mean(np.isfinite(np.asarray(v, dtype=float)))
    assert ok(alert) > ok(done), "an alert must be easier than a full upload"


def test_retries_are_capped_not_free():
    cc = dc.replace(Config().comm, max_attempts_per_item=5)
    rng = np.random.default_rng(1)
    done, _ = rollout_upload([0.0] * 400, cc, rng, 1, cc.upload_consec,
                             cc.upload_q_direct, cc.max_attempts_per_item)
    assert not np.isfinite(np.asarray(done, dtype=float)).any()
