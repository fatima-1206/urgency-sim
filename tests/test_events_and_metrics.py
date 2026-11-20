"""Ground truth must not depend on the method being scored, and the metrics
must mean what the report says they mean."""
import numpy as np
import pytest

from urgency_sim.config import Config, with_conn
from urgency_sim.events import extract_events
from urgency_sim.metrics import mean, summarise
from urgency_sim.sim import run, _field_and_events


def test_event_extraction_is_method_independent():
    """Events come from the PHYSICS only. If they depended on the method, each
    method would be scored against its own benchmark and the comparison would
    be meaningless."""
    cfg = Config()
    ref = None
    for mk in ("proposed", "threshold", "always_tx", "raw_abl"):
        log = run(cfg, 3, mk)
        ev = [(e.x, e.y, e.t) for e in log.events]
        if ref is None:
            ref = ev
        assert ev == ref, f"{mk} saw a different event set"
    assert len(ref) > 0


def test_event_extraction_is_deterministic_in_the_seed():
    cfg = Config()
    cfg_j, hist, ev = _field_and_events(cfg, 5)
    again = extract_events(cfg_j, hist)
    assert [(e.x, e.y, e.t) for e in again] == \
           [(e.x, e.y, e.t) for e in ev]


def test_field_cache_returns_identical_arrays():
    """F7 shares one field across the nine methods of a seed. If it ever
    returned a mutated array the methods would silently diverge."""
    c1, h1, e1 = _field_and_events(Config(), 7)
    c2, h2, e2 = _field_and_events(Config(), 7)
    assert np.array_equal(h1, h2) and not h1.flags.writeable
    assert c1 == c2 and len(e1) == len(e2)


def test_mean_filters_the_no_horizon_sentinel():
    """exp_time returns 1e9 when the horizon has already expired. Averaging it
    in once produced a reported mean of 3,114,114 ticks."""
    assert mean([2.0, 4.0, 1e9]) == pytest.approx(3.0)
    assert np.isnan(mean([1e9]))
    assert np.isnan(mean([]))
    assert mean([1.0, np.inf, np.nan, 3.0]) == pytest.approx(2.0)


@pytest.mark.parametrize("conn", ["sparse", "dense"])
def test_summarise_rows_are_well_formed(conn):
    d = summarise(run(with_conn(Config(), conn), 1, "proposed"))
    assert 0.0 <= d["on_time_ratio"] <= 1.0
    assert 0.0 <= d["observable_frac"] <= 1.0
    assert d["n_events_obs"] <= d["n_events_all"]
    assert d["n_deliveries"] <= d["n_attempts"]
    assert d["energy"] == pytest.approx(d["travel"] + d["n_attempts"])
    for k in ("git_sha", "cfg_hash", "lib"):      # F5
        assert d[k]
