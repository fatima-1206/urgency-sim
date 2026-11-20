# Pre-registered prediction for speed levels 0.50 and 1.00

**Written 2026-11-15, BEFORE either level was run.** Recorded so the mechanism
below is falsifiable rather than fitted after the fact.

## The mechanism found at speed 0.25

The primary-endpoint advantage decays monotonically across the four cells
(+0.134, +0.094, +0.060, +0.017). The cause is **not** false alarms — the
false-alarm difference tracks the decay at only r = +0.45, p = 0.55.

What tracks it is **latency** (r = −0.982, p = 0.018) and detection rate
(r = +0.963, p = 0.037):

| cell | gap | proposed@45 latency | threshold latency | advantage |
|---|---|---|---|---|
| predictable/sparse | +0.134 | 85.3 | 103.1 | **+17.8** |
| predictable/dense | +0.094 | 93.3 | 104.9 | +11.7 |
| unpredictable/sparse | +0.060 | 99.1 | 109.3 | +10.2 |
| unpredictable/dense | +0.017 | 108.3 | 110.8 | **+2.6** |

And the gap closes because **the proposed method degrades roughly four times
faster than the baseline does**, not because the baseline improves:

| cell | proposed@45 | threshold | proposed fall | threshold fall |
|---|---|---|---|---|
| predictable/sparse | 0.546 | 0.412 | — | — |
| unpredictable/dense | 0.387 | 0.370 | **−0.159** | **−0.042** |

**Interpretation — a delivery-capacity argument.** At budget 45 the proposed
method raises ~4.5x as many alarms as the saturated baseline (47.0 vs 10.5
fires/run). Extra alarms only convert into on-time deliveries while the delivery
pipeline has spare capacity. As conditions harden the pipeline saturates, the
queue backs up, latency balloons (+23 ticks for proposed against +7.7 for the
baseline), and the extra alarms stop paying. The baseline, firing a tenth as
often, is never capacity-bound and so degrades gently.

Consistent with this: in the dense scenarios the agent transmits in place far
more often (p_transmit_now 0.46/0.40 vs 0.24/0.27 sparse), so the baseline is
already delivering efficiently and there is little latency headroom left to win.

## The prediction

If the mechanism is a delivery-capacity limit, then **anything that makes the
mission harder should shrink the advantage**, and a faster plume is exactly that.

1. The primary-endpoint gap at speed 0.50 will be **smaller** than at 0.25 in
   every cell, and smaller again at 1.00.
2. The number of cells passing the §2 rule will **not increase**: at most 3 at
   speed 0.50, at most 3 at 1.00.
3. `proposed@45` mean latency will rise faster with speed than `threshold`'s.
4. The false-alarm difference will **not** explain the change (|r| < 0.6),
   because it did not explain it at 0.25.

**What would falsify it:** the gap widening at higher speed, or the §2 rule
passing in all four cells at 0.50 or 1.00. Either outcome means the
capacity argument is wrong and the decay has another cause.

**Note on expectations.** These predictions are all unfavourable to the method.
They are recorded anyway, before the runs, so that a result matching them counts
as a confirmed mechanism rather than a disappointment, and a result
contradicting them cannot be quietly reinterpreted.

---

# OUTCOME — scored 2026-11-15 after running both levels

| # | prediction | outcome |
|---|---|---|
| 1 | gap shrinks with speed in **every** cell | **FALSIFIED** — holds in 3 cells, but `unpredictable/dense` *grows*: +0.017 → +0.078 → +0.071 |
| 2 | no more than 3 of 4 cells pass at either speed | **HELD** — exactly 3/4 at 0.25, 0.50 and 1.00 |
| 3 | proposed's latency rises faster with speed than threshold's | **FALSIFIED** — latency *falls* with speed for both, and not faster for proposed |
| 4 | false alarms do not explain the variation | **HELD** — r = −0.21, p = 0.51 across 12 points |

**The delivery-capacity mechanism is rejected.** It rested on a 4-point
correlation at speed 0.25 (latency r = −0.982, p = 0.018). Across all 12
(speed x cell) points that correlation collapses to r = −0.381, p = 0.22, and
no measured quantity explains the gap at p < 0.05 (best: `n_fires`, r = −0.55,
p = 0.063). Four points were too few to support a mechanism, and the prediction
written in advance is what exposed that. The capacity story must not appear in
the write-up as an explanation.

## What replaced it — a cleaner and stronger boundary

Re-grouping the same 12 comparisons by **field scenario** rather than by speed
gives a split the speed axis does not:

| scenario | comparisons passing §2 |
|---|---|
| **predictable** | **6 of 6** — every speed, both connectivity levels |
| **unpredictable** | **3 of 6** |

Every predictable cell passes, at every speed, with the effect decaying smoothly
as speed rises (+0.134, +0.094, +0.090, +0.070, +0.040, +0.044) but never
reaching zero. No unpredictable cell is reliable: which one fails *moves*
between speeds (`unpredictable/dense` at 0.25, `unpredictable/sparse` at 0.50
and 1.00), which is itself evidence that the unpredictable result is unstable
rather than a fixed property of one configuration.

**This grouping was not pre-registered.** It is therefore an exploratory
finding, not a confirmatory one, and must be labelled as such: it is a
hypothesis for a future study, not a result of this one. The confirmatory
outcome remains **NOT SUPPORTED, 3 of 4 cells, at all three speeds**
(PROTOCOL §2).
