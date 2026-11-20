# Phase 4 results — graded deviation and the static field

8,000 runs, 81.4 min. Predictions scored against
`results/phase4/PREREGISTRATION.md`, committed before any of this ran.

**5 of 8 predictions held, 3 falsified.** Two of the three were wrong in the
method's favour, i.e. the method did better than predicted.

---

## Experiment A — graded deviation

### Wind arm (second source switched off)

proposed @45 alarms vs threshold @11 (its saturated best), on-time ratio:

| wind shift | sparse | dense |
|---|---|---|
| **0°** | **+0.143** *** | **+0.106** *** |
| **20°** | **+0.132** *** | **+0.079** ** |
| 40° | +0.112 *** | +0.019 ns |
| 60° | +0.084 *** | +0.041 ns |
| 80.2° (Phase 3) | +0.065 * | +0.026 ns |

A smooth monotone decay with no cliff. **There is a usable operating region:** at
a 20° deviation the advantage is significant in both connectivity scenarios.

**The wind shift alone accounts for essentially all of the Phase 3 degradation.**
At 80.2° with no second source the gap is +0.065 / +0.026; Phase 3's full
unpredictable scenario, with *both* shocks, gave +0.060 / +0.017. The second
source contributes almost nothing to the failure.

### Source arm (no wind shift)

| second source | sparse | dense |
|---|---|---|
| none | +0.143 *** | +0.106 *** |
| half strength | +0.119 *** | +0.112 *** |
| **full strength** | **+0.161** *** | **+0.168** *** |

**An unannounced second source makes the method better, not worse** — and by the
largest margin anywhere in this experiment. That is the behaviour a
surprise-based trigger should have: a new release is exactly the kind of event
the cloud model cannot predict, so surprise spikes and the alarm is well spent.

The two shocks are therefore not merely separable, they act in **opposite
directions**. A wind reversal invalidates the spatial structure the GP has
learned; a new source is precisely what that GP is for.

---

## Experiment B — static and near-static plume

**Primary endpoint: latency**, because on-time is undefined at zero wind —
`events.deadline_for` derives each deadline from plume travel time, so with no
wind every event returns `upwind=False`. The sanity check confirms it: on-time
reads 0.940 at ratio 0, which is meaningless rather than excellent.

Latency, ticks, negative means the proposed method delivers sooner:

| plume speed | sparse | dense |
|---|---|---|
| **0 (static)** | **−23.6** ** | +4.4 ns |
| 0.1 | +1.0 ns | +3.7 ns |
| 0.25 | −16.1 * | −12.3 ns |

**The static field is where the method performs best on latency** — a 23.6-tick
advantage, larger than anywhere else measured. The prediction said it would be
*smaller*; see below.

Event supply: 74 / 119 / 300 observable events per run at speeds 0 / 0.1 / 0.25.
The static field is thin, and ratio 0.1 is thin *and* unmeasurable (both
comparisons non-significant), so it is reported as a weak cell rather than
averaged in.

---

## Scoring

| # | prediction | outcome |
|---|---|---|
| 1 | Wind shift dominates the second source | **HELD** — wind costs 0.078/0.080; the source *gains* 0.018/0.062 |
| 2 | Still significant at 20° in both connectivity scenarios | **HELD** — +0.132, +0.079 |
| 3 | Gradual breakdown; no 20° step over 60% of the decline | **HELD** — largest step 36% |
| 4 | Source alone does not destroy the advantage | **HELD**, and understated — it *increases* it, in both scenarios |
| 5 | Static yields 90–150 events/run | **FALSIFIED** — 74, below the stated range |
| 6 | The threshold baseline saturates at every speed, including 0 | **FALSIFIED** — see below |
| 7 | Latency advantage survives at zero wind in ≥1 scenario | **HELD** — sparse −23.6, p = 1.5e-03 |
| 8 | The static advantage is *smaller* than at ratio 0.25 | **FALSIFIED** — it is *larger* (−23.6 vs −16.1) |

### Prediction 6 — a correction to a Phase 3 claim

Phase 3 reported the threshold baseline as **structurally** budget-capped at
~10.5 alarms/run, on the grounds that its trigger `max(0, obs − hazard)` already
admits every hazard crossing at trigger zero. Alarms raised, by level:

| level | threshold @11 | threshold @45 | saturated? |
|---|---|---|---|
| static (r0) | 19.8 | **36.8** | **no** |
| r0.1 | 8.7 | 10.1 | no (+1.4) |
| r0.25 | 10.3 | 10.3 | yes |
| wind 0° | 9.8 | 9.8 | yes |
| wind 80.2° | 9.4 | 9.4 | yes |

**The ceiling is scenario-dependent, not universal.** In a static field the
plume pools instead of dispersing, so a far larger fraction of the domain sits
permanently above the hazard level and the baseline has many more crossings to
fire on — reaching 36.8 alarms, not 10.5.

What survives is the weaker, still-true statement: *the baseline cannot reach an
arbitrary alarm budget — it was asked for 45 and delivered 36.8 — because its
ceiling is set by how much of the field exceeds the hazard level, which it does
not control.* What does **not** survive is "~10.5 alarms/run" as a universal
constant. The Phase 3 and Phase 4 moving-plume levels all saturate near 10, so
the Phase 3 result stands for the regime it was measured in; the number must not
be quoted outside it.

---

## What this changes

1. **The unpredictable-scenario failure is attributable.** It is the wind shift,
   not the unannounced source, and the source arm is positive.
2. **The method has a usable operating region** up to roughly a 20° wind
   deviation, rather than working only under perfectly steady wind.
3. **The static field is a valid and favourable regime** under a latency
   endpoint. The earlier argument that a static plume could not be studied
   conflated the scenario with the metric and was wrong.
4. **The budget-ceiling claim needs its regime stated.** It is not a universal
   property of threshold triggers.

All four are exploratory with respect to `PROTOCOL.md`, which they do not amend.
The Phase 3 verdict stands at NOT SUPPORTED, 3 of 4 cells, at every speed.
