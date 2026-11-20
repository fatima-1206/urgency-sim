# Phase 4 pre-registration — graded deviation and the static field

**Written 2026-11-18, BEFORE any Phase 4 run.** Frozen on the same terms as
`PROTOCOL.md`: if something here turns out wrong, it is recorded as a deviation
and reported, not amended.

## Why these two experiments

Phase 3 left one question open and one argument wrong.

**Open:** the primary endpoint failed in 3 of 12 conditions, all of them
unpredictable-plume cells. A delivery-capacity mechanism was proposed,
pre-registered, and falsified (`results/phase3/PREDICTION_speed.md`). No
replacement explanation has been tested.

**Wrong:** it was argued that a static plume could not be studied because
"information must go stale for urgency to mean anything". That conflated the
*scenario* with the *endpoint*. The on-time endpoint derives each deadline from
plume travel time to the sensitive zone (`events.deadline_for`), so at zero wind
every event returns `upwind=False` and the endpoint is undefined. **Latency is
not**: `event_outcomes` computes it from the first time the cloud belief crosses
the hazard level, independent of any deadline. A static field is therefore
perfectly measurable under a latency endpoint, and the objection applied to the
metric, not to the scenario.

Supporting this, the latency endpoint already reproduces the Phase 3 structure on
existing data (speed 0.25, pooled):

| alarms/run | 4.7 | 11.2 | 21.7 | 47.0 | 98.6 |
|---|---|---|---|---|---|
| proposed latency | 115.8 | 118.0 | 108.8 | 96.5 | **77.3** |
| threshold latency | 112.1 | 107.0 | 107.0 | 107.0 | 107.0 |

The baseline's latency flatlines at 107.0 because its runs are identical past
saturation. The proposed method reaches 77.3, **28% faster**, and is faster with
a CI excluding zero in 8 of 12 Phase 3 conditions.

## Experiment A — graded deviation

Phase 3 had only two settings: no perturbation, or **both** shocks at full
strength — an **80.2 degree** wind reversal *and* a second source at 81% of the
primary release rate. That is a violent jump and it confounds two disturbances.

`config.with_deviation(cfg, shift_deg, src_frac)` makes each a dial. Two arms,
sharing their origin at (0, 0) which reproduces the predictable scenario:

| arm | levels | held |
|---|---|---|
| **wind** | `shift_deg` ∈ {0, 20, 40, 60, 80.2} | `src_frac` = 0 |
| **source** | `src_frac` ∈ {0, 0.5, 1.0} | `shift_deg` = 0 |

Rotation preserves wind *speed*, so the dial changes direction only and does not
reintroduce the dilution confound that F1 removed.

Speed 0.25, both connectivity scenarios, budgets {11, 45}, methods {proposed,
threshold}, n = 100 seeds/cell, evaluation block 3000–3299, calibration bisected
per level on block 2000–2299.

### Predictions (A)

1. **The wind shift is the dominant disturbance.** The on-time advantage at
   budget 45 will fall monotonically with `shift_deg`, and the fall across
   0 → 80.2 degrees will be **larger** than the fall across `src_frac` 0 → 1.
2. **There is a usable operating region.** The advantage will remain significant
   (CI excluding zero) at `shift_deg` = 20 in both connectivity scenarios.
3. **The breakdown is gradual, not a cliff.** No single 20-degree step will
   account for more than 60% of the total decline.
4. The second source alone (`src_frac` = 1, `shift_deg` = 0) will **not** by
   itself destroy the advantage: it will stay significant in at least one
   connectivity scenario.

**Falsified if:** the source arm shows the larger decline (contradicts 1), or the
advantage is already lost at 20 degrees (contradicts 2), or one step dominates
(contradicts 3).

## Experiment B — static and near-static field, latency endpoint

Levels: plume/agent speed ratio ∈ {0, 0.1, 0.25}. At ratio 0 the dilution
correction is disabled, since `(|w|/w_ref)^0.55` is zero at zero wind and would
silently switch the source off.

**Primary endpoint for Experiment B: mean latency** (ticks from event to the
cloud belief crossing the hazard level). Lower is better. On-time ratio is
**not** reported at ratio 0 — it is undefined there, and reporting it would be
meaningless rather than merely weak.

Predictable scenario only, both connectivity scenarios, budgets {11, 45},
methods {proposed, threshold}, n = 100.

### Predictions (B)

5. **The static field is thin but not degenerate.** It yields roughly 90–150
   events per run against 310–431 in Phase 3 — enough to measure latency, and
   this reduction is reported as a limitation rather than hidden.
6. **The saturation result is scenario-independent.** The threshold baseline will
   raise the same number of alarms at budget 11 and budget 45 at every speed
   including 0, because the ceiling follows from its trigger definition.
7. **The latency advantage survives at zero wind.** `proposed` at budget 45 will
   have lower mean latency than `threshold` at its best budget, CI excluding
   zero, in at least one connectivity scenario.
8. **But the advantage will be smaller than at ratio 0.25**, because a static
   field is easier for the baseline: the hazard region stops moving, so a
   value-threshold trigger stops missing it.

**Falsified if:** prediction 7 fails in both connectivity scenarios (the method
needs a moving plume), or prediction 6 fails (the ceiling is an artefact of the
moving-plume scenarios rather than structural).

## Status of these results

Both experiments are **confirmatory for their own stated predictions** and
**exploratory with respect to Phase 3**, whose frozen protocol they do not
amend. The Phase 3 verdict stands at NOT SUPPORTED, 3 of 4 cells, at every
speed, regardless of what these produce. Nothing here may be used to restate
Phase 3's outcome.
