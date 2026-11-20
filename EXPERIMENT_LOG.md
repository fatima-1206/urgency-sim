# Experiment log — complete record

*Information-Urgency-Driven Communication and Trajectory Planning for Mobile
Environmental Sensing under Intermittent Connectivity*
Fatima Tu Zahra (23I-2616) · Aleena Zahra (23I-2514) · FAST-NUCES

A chronological record of every experiment run on this project, what each one was
capable of showing, what it showed, and **what its result depends on**. The last point
is the one that matters most: nearly every conclusion in this project changed meaning at
least once when the setup around it changed, and several early claims were withdrawn for
exactly that reason.

Running totals: **≈120,000 simulation runs** across five phases.

| phase | what it was | runs | verdict |
|---|---|---|---|
| 0 | 30×30 feasibility pilot | ~4,000 | method looked promising; two of three findings later withdrawn |
| 1 | hardening, re-validation at 40×40 | ~12,000 | verdict did **not** flip; budget frontier discovered |
| 2 | protocol freeze | 0 | pre-registration written and frozen |
| 3 | confirmatory study | 34,000 | **NOT SUPPORTED**, 3 of 4 cells, at all three speeds |
| 4 | attribution of the Phase 3 failure | 8,000 | 5 of 8 predictions held; failure attributed to the wind shift |
| 5 | extensive programme, 10 experiments | 76,000 | negative result robust and now tested from 5 to 45 alarms/run; the positive result is airtime, not prioritisation |

---

## 0. Machinery common to every experiment

Interpretation of every result below depends on these, so they are stated once.

**What is simulated.** A single mobile agent surveys an advection–diffusion pollutant
plume on a grid and must decide *when* a reading is urgent enough to transmit and
*where* to fly to get a link good enough to deliver it. The field is integrated with
explicit first-order upwind advection plus central diffusion under the combined CFL
condition `dt ≤ 1/(|u|/dx + |v|/dx + 4D/dx²)`, with automatic substepping. The source
**pulses** (period ≈110 ticks); a constant source reaches steady state and stops
producing hazard crossings, which makes the predictable scenario degenerate.

**What a "method" is.** A (trigger × deadline rule × action rule) triple. Every method
builds the same cloud GP map; the baselines differ from the proposed method in exactly
one component. This is what makes the ablations interpretable.

| key | trigger | deadline | action |
|---|---|---|---|
| `proposed` | surprise + consequence | from urgency | MC rollout |
| `threshold` | value > hazard (no GP) | fixed | MC rollout |
| `fixed_dl` | surprise + consequence | fixed | MC rollout |
| `time_urg` | time since last delivery (no GP) | from urgency | MC rollout |
| `always_tx` | surprise + consequence | from urgency | transmit in place |
| `surprise_abl` | surprise only | from urgency | MC rollout |
| `raw_abl` | raw error (no σ) + consequence | from urgency | MC rollout |

**Matched alarm budget.** Every trigger is bisected so all methods fire at the same
rate, because a trigger that simply fires more would win on delivery for trivial
reasons. *This device is the single most important thing in the project, and Phase 5
showed it silently fails at high budgets — see §5.*

**Ground truth is method-independent.** Events are cells on a stride-2 lattice whose
**true** concentration crosses the hazard level. The set is identical for every method;
each deadline is the plume's travel time from the event cell to the sensitive zone along
the wind vector. A method affects only the outcome, never the question. (An early
hypothesis that methods were penalised by their own self-assigned deadlines was checked
against `metrics.event_outcomes` and **retracted** — on-time uses the physics deadline.)

**Statistics.** Paired Wilcoxon signed-rank on identical seeds, 95% CIs, Holm correction
where a family of tests is reported. Seed blocks are disjoint by design and the disjointness
is verified, not assumed.

**Provenance.** Every result row carries a git SHA, a config hash and library versions.
Raw runs are committed gzipped so every table regenerates with no re-simulation.

---

## Phase 0 — feasibility pilot (30×30)

**Setup.** 30×30 grid, 600 ticks, a minimal prototype built dumbest-first: static field
and one baseline first, then one component at a time.

**What it was capable of showing.** Whether the pieces run at all and whether the idea
is worth a full study. It was *not* capable of supporting comparative claims, which is
how it was treated at the time and should not have been.

**Results as reported then.**
- The consequence term earned its place: +0.032 on-time, p = 0.006.
- Dense connectivity reached 31.9% effective coverage.
- The proposed trigger looked competitive with the hazard threshold.

**What survived.** The architecture, the two-tier messaging rule, and the finding that
several design choices were load-bearing (additive rather than multiplicative urgency;
the frozen GP hyperparameters; the pulsing source).

**What did not.** All three headline numbers above were later withdrawn. The +0.032
became −0.005 (p = 0.71) once the budget was correctly matched at 40×40. The 31.9%
coverage was reached only by **violating region separability**, which is why dense
region discovery was finding 0.96 of 4.00 regions.

**Interpretation, and its dependence on setup.** A 30×30 pilot with an uncalibrated
budget cannot distinguish "this trigger is smarter" from "this trigger fires more" or
from "the regions overlap so the geometry is wrong". Phase 0's positive findings were
artefacts of its own small, unvalidated setup. **This is the first instance of the
pattern that defines this project: a positive result that dissolved when the setup was
made rigorous.**

---

## Phase 1 — hardening and re-validation (40×40)

**Setup.** 40×40 grid, 800 ticks, 60 seeds × 2 field scenarios × 2 connectivity
scenarios = 240 paired runs per method (1,680 runs per sweep). Eight changes, each
fixing something the pilot had got wrong:

| id | change | effect |
|---|---|---|
| F1 | decouple plume dilution from wind speed | removes the confound in the speed sweep |
| F2 | 40×40 / 800 ticks, recalibrated scenarios | fixes the dense-region geometry conflict |
| F3 | percentile urgency→deadline map | deadlines at ceiling 62% → 22% |
| F4 | `validate_comm()` asserts separability at config load | dense discovery 0.96/4.00 → **3.92/4.00** |
| F5 | git SHA + config hash on every row | provenance |
| F6 | 56-test regression suite | regression safety |
| F8 | explicit disjoint seed blocks | pilot 0–199, sweep 1000–1029, study 2000+ |

### 1a. The headline re-validation

**Question.** Does a bigger, correctly configured grid change the verdict?

**Result.** No. Threshold still beats the proposed trigger on timely delivery,
**−0.089, p = 8.9 × 10⁻⁹**.

| vs | on-time | p |
|---|---|---|
| `fixed_dl` | −0.033 | 3.7e-03 |
| **`threshold`** | **−0.089** | **8.9e-09** |
| `surprise_abl` | −0.005 | 0.71 |
| `raw_abl` | −0.066 | 1.2e-06 |
| `time_urg` | +0.196 | 1.0e-36 |
| `always_tx` | +0.146 | 5.0e-25 |

**Interpretation and its setup-dependence.** Three things that look like separate
findings are all consequences of the same regime. With ~11 alarms against ~370
observable events per run, this is a **severely budget-starved** setting in which the
optimal policy is simply "spend every alarm on the most obviously hazardous reading" —
which is precisely what `threshold` does. The surprise term fires on *model error*,
which correlates only loosely with *hazard crossings*, so at a fixed budget it wastes
alarms (detection 8.9% vs 11.8%; false-alarm rate 0.255 vs 0.201). **None of this
generalises to a non-starved regime**, and Phase 3 §5 later confirmed it does not.

The `surprise_abl` row is the uncomfortable one: the consequence term, the thing that
distinguishes the method's core from a plain surprise trigger, buys −0.005 (p = 0.71).
**The core was doing no work at this budget.**

### 1b. Map RMSE is not an independent endpoint

**Result.** Across all seven methods, `on_time_ratio` and `map_rmse` are near-perfectly
rank-anti-aligned: **Spearman 0.96, Pearson r = +0.89, p = 0.007**. `time_urg` — a pure
timer, worst on-time of any method at 0.082 — has the **best** map RMSE at 0.194.

**Interpretation.** Map RMSE is largely a proxy for "how spatially diffuse are your
uploads". Claiming a win on RMSE while losing on on-time is claiming you sampled more
uniformly; it is not evidence the trigger is smart. **Consequence: RMSE was demoted to a
diagnostic and never again reported as a win.**

### 1c. The budget frontier — the genuinely new result

**Setup.** Rather than matching one point, the alarm budget itself was swept: for each
target rate the trigger was bisected to hit it, then evaluated.

| alarms/run | 5 | 11 | 22 | 45 | 90 |
|---|---|---|---|---|---|
| proposed on-time | 0.204 | 0.314 | 0.394 | 0.469 | **0.600** |
| threshold on-time | 0.263 | 0.334 | — | — | — |

**The threshold baseline cannot fire more than ~10.4 alarms/run.** Its trigger is
`max(0, obs − hazard)`; at trigger zero it already admits every hazard crossing the
agent sees, and there is nothing left to admit. Every entry past 11 is the same
saturated run.

**Interpretation and its setup-dependence.** This reframed the whole project. The
reference budget had been defined as *threshold at trigger 0* — the baseline's
**ceiling**, not a neutral operating point. Matching to it pins the proposed method to
the single worst point on its own operating curve and then declares the baseline the
winner. The honest claim became narrower but real: *the proposed trigger provides a
tunable alarm budget that a hazard threshold does not, and dominates once the budget
exceeds what a threshold can spend.*

**Caveat that took until Phase 5 to surface.** This is also the claim that later turned
out to be doing all the work in every subsequent "win" — because above the baseline's
cap the comparison stops being matched at all. Phase 1 saw the cap and read it as *the
baseline's limitation*. It is equally *the comparison's limitation*.

### 1d. Speed sweep (staleness)

**Setup.** F1 on, so plume dilution no longer tracks wind speed. Fresh seeds 1000–1029,
120 pairs per point, calibration re-run at every point.

| ratio | 0.10 | 0.25 | 0.50 | 0.75 | 1.00 | 1.50 |
|---|---|---|---|---|---|---|
| events/run | 149 | 341 | 390 | 346 | 313 | 266 |
| proposed | 0.451 | 0.349 | 0.321 | 0.244 | 0.206 | 0.152 |
| threshold | 0.575 | 0.348 | 0.363 | 0.323 | 0.295 | 0.232 |
| diff | −0.124 | +0.000 | −0.042 | −0.079 | −0.089 | −0.080 |

**Interpretation.** Staleness is real — on-time falls monotonically with speed for every
method, and with difficulty now roughly constant that decline is attributable to speed
rather than to the plume thinning out. **The earlier sweep could not make this claim**,
because dilution and speed moved together. It does not rescue the method: the gap is
present at five of six speeds and does not shrink as the plume slows.

**Excluded level.** Ratio 0.10 yields only 149 events/run because the plume never leaves
the source region within the mission. Reported as *a different problem, not a slower
one* — the first use of a rule that recurs throughout: **a level whose event supply
collapses is non-comparable and is reported, not averaged in.**

### 1e. The calibration bug that invalidated the first 40×40 run

`scripts/calibrate.py` used `NS = 5` (20 runs per grid point). Re-measured on the
60-seed block, its triggers were off budget by up to **+24%** (`surprise_abl`: 9.2
predicted, 14.0 actual). The alarm budget was silently unmatched, which flattered both
ablations. `NS` raised to 20; the invalidated run is preserved at
`results/report_40x40_unmatched.json` rather than deleted.

**Why this matters beyond itself.** It established the project's central discipline:
**the achieved alarm rate is measured and reported next to every trigger, never
assumed.** Every later phase carries that audit, and it is what made the Phase 5
saturation finding visible at all.

---

## Phase 2 — protocol freeze

No runs. `PROTOCOL.md` written and frozen before the confirmatory study:

- **§2** one primary endpoint, stated at full strength so it can be falsified, with a
  numeric decision rule fixed in advance: *supported* only if the proposed method at 45
  alarms/run exceeds the threshold's maximum over its whole sweep, CI excluding zero, in
  **both** connectivity and **both** field scenarios. **Three of four cells is
  explicitly defined as NOT SUPPORTED.**
- **§6** seeds, sample size, power.
- **§7** statistics and correction.
- **§10** a deviations log.
- **§11** what would falsify the claim.

**Why this was done.** Phases 0 and 1 had each produced a positive finding that
dissolved on inspection. Fixing the decision rule in advance removes the option of
deciding what counts as success after seeing the numbers.

---

## Phase 3 — the confirmatory study

**Setup.** 34,000 runs: 14,000 matched-budget + 20,000 frontier. Three plume speeds
(0.25, 0.50, 1.00), budgets {5, 11, 22, 45, 90}, 2 field × 2 connectivity scenarios,
n = 300 at speed 0.25 (n = 100 at 0.50 and 1.00 — the one logged deviation).
Seed blocks: calibration 2000, evaluation 3000.

### Primary result

**NOT SUPPORTED — 3 of 4 cells, at every speed.** Per PROTOCOL §2 this is a negative
result and was reported as one.

At speed 0.25 the advantage decays smoothly across cells: **+0.134, +0.094, +0.060,
+0.017**, failing in `unpredictable/dense`.

### The mechanism that was pre-registered and then rejected

A delivery-capacity argument was proposed: extra alarms only convert into on-time
deliveries while the pipeline has spare capacity; as conditions harden the queue backs
up and the extra alarms stop paying. It rested on latency correlating with the decay at
**r = −0.982, p = 0.018** — across four points.

It was **pre-registered before running speeds 0.50 and 1.00**, with explicit falsifiers.

**Outcome: REJECTED.** Across all 12 (speed × cell) points the correlation collapses to
**r = −0.381, p = 0.22**, and no measured quantity explains the gap at p < 0.05.
Prediction 1 falsified (the gap *grew* in `unpredictable/dense`: +0.017 → +0.078 →
+0.071); prediction 3 falsified (latency *falls* with speed for both methods).

**Interpretation.** Four points were too few to support a mechanism. The prediction
written in advance is what exposed that — had it been fitted afterwards it would have
been reported as an explanation. **The capacity story does not appear in the write-up.**

### What replaced it — exploratory, and labelled so

Regrouping the same 12 comparisons by **field scenario** rather than by speed:

| scenario | comparisons passing §2 |
|---|---|
| **predictable** | **6 of 6** — every speed, both connectivity levels |
| unpredictable | 3 of 6 |

Every predictable cell passes at every speed, decaying smoothly but never reaching zero.
No unpredictable cell is reliable, and *which* one fails moves between speeds — itself
evidence of instability rather than a fixed property.

**This grouping was not pre-registered**, so it is exploratory: a hypothesis for a future
study, not a result of this one. The confirmatory outcome remains NOT SUPPORTED.

### Testing the underpowering explanation

The failing cell was completed at n = 300. The effect **shrank** (+0.033 → +0.017) while
the CI tightened. The explanation was tested and **rejected**: the cell does not fail for
want of seeds.

---

## Phase 4 — attribution (8,000 runs, 81 min)

**Question.** Phase 3 said the method fails in the unpredictable scenario. *Which* shock
causes it? The scenario fires two at once: a wind shift at t = 347 and an unannounced
second source at t = 427. Two user intuitions prompted this: that the failure might be
the wind specifically, and that a static plume might suit the method.

**Setup.** `with_deviation(cfg, shift_deg, src_frac)` turns the binary switch into two
independent dials. Rotation preserves wind **speed**, so the dial changes direction only
— otherwise it would reintroduce the dilution confound F1 removed. Pre-registered in
`results/phase4/PREREGISTRATION.md` with 8 predictions.

### Experiment A — graded deviation

**Wind arm** (second source off), proposed @45 vs threshold @11 (its saturated best):

| wind shift | sparse | dense |
|---|---|---|
| 0° | +0.143 | +0.106 |
| **20°** | **+0.132** | **+0.079** |
| 40° | +0.112 | +0.019 ns |
| 60° | +0.084 | +0.041 ns |
| 80.2° (Phase 3) | +0.065 | +0.026 ns |

**Source arm** (no wind shift):

| second source | sparse | dense |
|---|---|---|
| none | +0.143 | +0.106 |
| half | +0.119 | +0.112 |
| **full** | **+0.161** | **+0.168** |

**Results.** The wind shift alone reproduces essentially all of the Phase 3 degradation
(+0.065/+0.026 against the full scenario's +0.060/+0.017). **An unannounced second
source makes the method better, not worse** — by the largest margins measured anywhere.

**Interpretation.** The two shocks act in **opposite directions**, which is exactly what
a surprise-based trigger should do: a wind reversal invalidates the spatial structure the
GP has learned, while a new release is precisely what that GP is for. The user's
intuition was vindicated. There is a usable operating region out to ~20° deviation.

**Setup-dependence.** This comparison is proposed @45 vs threshold @11 — the baseline at
its ceiling. Phase 5 later showed that is an unmatched comparison, so these margins are
**capacity margins**, not prioritisation margins. The *relative* ordering across the
graded dials is still valid, because the out-spend ratio is roughly constant along each
arm; the absolute values are not like-for-like.

### Experiment B — static and near-static plume

**Primary endpoint: latency**, because on-time is undefined at zero wind — deadlines
derive from plume travel time, so with no wind every event returns `upwind=False`. The
sanity check confirms it: on-time reads 0.940 at ratio 0, which is meaningless rather
than excellent.

| plume speed | sparse | dense |
|---|---|---|
| **0 (static)** | **−23.6** | +4.4 ns |
| 0.1 | +1.0 ns | +3.7 ns |
| 0.25 | −16.1 | −12.3 ns |

**Result.** The static field is the method's **best** latency regime. The prediction said
it would be smaller; it is larger.

**Interpretation.** The earlier argument that a static plume could not be studied
conflated the scenario with the metric and was wrong. Event supply is thin (74 events/run
at ratio 0), and ratio 0.1 is thin *and* unmeasurable, so it is reported as a weak cell.

### Prediction 6 — a correction to a Phase 3 claim

| level | threshold @11 | threshold @45 | saturated? |
|---|---|---|---|
| **static** | 19.8 | **36.8** | **no** |
| r0.1 | 8.7 | 10.1 | no |
| r0.25 | 10.3 | 10.3 | yes |
| wind 80.2° | 9.4 | 9.4 | yes |

**The ~10.5 ceiling is scenario-dependent, not universal.** In a static field the plume
pools instead of dispersing, so far more of the domain sits permanently above the hazard
level and the baseline has many more crossings to fire on.

What survives: *the baseline cannot reach an arbitrary budget — asked for 45 it delivered
36.8 — because its ceiling is set by how much of the field exceeds the hazard level,
which it does not control.* What does not survive is "~10.5" as a constant.

**Score: 5 of 8 predictions held, 3 falsified.** Two of the three were wrong in the
method's favour.

---

## Phase 5 — the extensive programme (76,000 runs, 10 experiments, ~12 h)

**Why.** Two user observations suggested the problem was the regime rather than the
algorithm: the domain might be too small relative to the agent ("a forest too large for a
drone to ever fully explore"), and the connectivity regions might be too many. Both were
measurable.

Checking them first found that **explorability had been computed wrongly**: an earlier
version multiplied by a (2r+1) sensing swath and reported 3.50. The agent is a strict
**point** sensor — `sensor_range` appears only in `metrics.observability` — verified by
sweeping sensor_range 3→0 with fires, on-time and latency unchanged. Correct value:
**0.50**.

**Setup.** `PROTOCOL_EXPERIMENTS.md` frozen first, with 11 predictions, co-primary
endpoints (**on-time and latency** — latency needs no deadline, so it is the only valid
endpoint in a static field), disjoint seed blocks (calibration 5000, evaluation 6000,
replication 7000), and a deviations log. A shared harness (`scripts/experiments/`) with
crash-safe append-only JSONL, `fsync` per row, and config-hash-validated resume.

**A bug caught before the programme ran.** The smoke pass asked E4 for 180, 360 and 720
alarms/run and got the identical trigger and identical 138.5 alarms at all three — which
reads as a ceiling. It was not: the bisection bracket floor was 0.05, so the search could
never go below ~0.065. **A bracket artefact reported as a ceiling would have been a
fabricated finding.** Floors set to 0.0; E4's budgets changed to {90, 120, 150, 180}
where 180 is *deliberately unreachable* and its off-target flag is the evidence.

**A second bug, found while writing the config helpers.** `agent.speed` was consulted by
`decision._path_qualities` but ignored by the movement loop, which always stepped one
cell. At the default speed of 1 the two agree, so the mismatch was invisible — but it
would have silently invalidated E5. Fixed and verified bit-identical at speed 1 across 40
runs.

### E1 — explorability / mission length (8,000 runs) ★ headline

**Setup.** Mission length 200/400/800/1600 ticks, plus one grid level at n = 60. The grid
arm stops at 60 because GP capacity falls to 2.5 and 1.1 at n = 80 and 120, and n = 120
measured degenerate (on-time 0.00–0.06) **for the GP's reasons rather than the agent's** —
recorded in the deviations log before the programme ran.

**Two design faults found after the run, both recorded:**

1. **The budget is not matched at 8 of 10 cells.** The threshold baseline fires 2.5
   alarms against a target of 45 at t200. The large budget-45 differences are therefore
   *proposed at 45 vs baseline at its own ceiling*.
2. **Level t200's scenario factor is degenerate.** `wind_shift_t = 347` and
   `new_source_t = 427` both fall after a 200-tick mission ends, so predictable and
   unpredictable are the **same simulation** — visible as byte-identical rows.

**The only two genuinely matched cells** (t800 @ 11, ratio 1.10×; t1600 @ 11, ratio
0.94×) both **favour the baseline** (−0.056, −0.070).

**Result: inconclusive on its own primary prediction**, and the premise is not supported:

| level | explorability | mission | margin @45, pred/dense |
|---|---|---|---|
| t400 | 0.25 | 400 ticks / 1,600 cells | **+0.295** |
| n60 | 0.22 | 800 ticks / 3,600 cells | **+0.060** |

Nearly identical explorability, five-fold difference in effect. **It is mission length,
not the ratio of mission to domain — the opposite of the premise E1 was built to test.**

### E2 — connectivity scarcity (12,800 runs)

**Setup.** Region count {1, 2, 4, 8} at fixed coverage, and region size {0.6, 0.8, 1.0,
1.3} at fixed count — decoupling two factors previously confounded.

**Result.** At matched airtime, **26 of 27 cells favour the baseline**. The single
positive (+0.014) is not significant, p = 0.37. Squeezing connectivity down to one small
region flips nothing.

**Interpretation.** The user's "too many connectivity regions" hypothesis is **falsified**.

### E4 — budget ceiling (1,600 runs)

**Setup.** Proposed method only — the baseline is saturated, so its extra points would be
byte-identical reruns.

| budget | alarms | on-time | latency | energy |
|---|---|---|---|---|
| 90 | 87.5 | 0.615 | 71.6 | 1452 |
| 120 | 124.9 | 0.702 | 58.3 | 1538 |
| **150** | **157.9** | **0.747** | **46.1** | 1572 |
| 180 | 157.9 | 0.747 | 46.1 | 1572 |

**Result.** The ceiling is **~150 alarms/run**, and it is structural: the `k_consistent =
3` gate admits at most one alarm every three ticks. Phase 3 stopped at 90 and reported
on-time "still climbing (0.533, no plateau)". **It climbs to 0.747**, with latency falling
36%.

**Interpretation and its setup-dependence.** This is the project's strongest surviving
positive result. The energy cost is +8.2%, but energy in this simulator is dominated by
flight rather than transmission, **so the energy figure is a property of the energy model
and must not be quoted as an operational result.** Under sparse connectivity the count of
runs delivering nothing rises with budget (2 → 9 of 100), so sparse latency means are
taken over a shrinking subset; the dense columns carry the claim.

### E5 — agent speed (4,800 runs)

**Result.** At speeds 1 and 2 the baseline wins at matched airtime, as everywhere else.
At speed 3 the proposed method wins **+0.046** — the best non-out-spent cell in the
programme.

**It is confounded.** At speed 3 the baseline's alarm count collapses from ~9 to ~6 while
observing the *same* ~366 events. The `k_consistent` gate requires agreement across
consecutive ticks, and a 3-cell-per-tick agent has moved nine cells between the first
observation and the third. **The fast agent breaks the baseline's consistency gate.**
That is a finding about the gate, not evidence the method wins at speed.

### E7 — hazard level (4,800 runs)

**Setup.** Hazard {0.25, 0.35, 0.50} — this changes what counts as an event at all, so it
tests whether every earlier conclusion is an artefact of one threshold.

**Result.** **12 of 12 matched cells favour the baseline.** Phase 3's verdict is not an
artefact of its hazard level.

**But E7 produced the programme's most useful measurement.** The hazard level controls how
badly the baseline saturates, so it controls how fair the budget-45 comparison is:

| hazard | events/run | baseline alarms @45 | out-spend | margin |
|---|---|---|---|---|
| 0.25 | 571 | 23.4 | **2.6×** | **+0.127** |
| 0.35 | 354 | 9.8 | 5.3× | +0.178 |
| 0.50 | 170 | 5.3 | 11.0× | +0.128 |

**The fairer the comparison, the smaller the margin.** First direct evidence that the
budget-45 advantage is substantially a saturation artefact. Not proof — hazard 0.50 breaks
the monotone pattern and there are only three points — but it agrees with the matched
column, which is unambiguous.

**One untested lead.** The matched-airtime latency penalty falls from +17…+44 ticks at
hazard 0.50 to ≈0 at hazard 0.25. The method does **better** when events are plentiful —
again the opposite of the scarcity premise. Whether it overtakes below 0.25 is **not
tested**.

### E8 — channel burstiness (6,400 runs)

**Setup.** Gilbert-Elliott mean burst length {1, 2.86, 8, 20}, mean loss held constant so
burstiness varies alone. Directly tests whether the **two-tier upload rule** (3 consecutive
successes) earns its place.

**Result.** **Falsified.** An eight-fold increase in burst length moves the matched-airtime
margin by nothing (−0.035 to −0.109, no trend). Latency is also worse by +8 to +25 ticks
at every matched cell — notable because latency was added as the endpoint *friendlier* to
the method.

### E9 — robustness battery (11,200 runs)

**Setup.** One factor at a time at study scale, where Phase 3 had used an 8-seed smoke
test: `k_consistent` {1,2,3,5}, `sensor_noise` {0.02,0.04,0.08}, `upload_consec` {1,2,3,5},
GP `window` {70,140,280}. Budget 45 only.

**Result.** The margin tracks `k_consistent` almost perfectly — and so does the out-spend
ratio:

| k | out-spend | margin |
|---|---|---|
| 1 | 1.4× | +0.008 |
| 2 | 2.7× | +0.037 |
| 3 | 4.9× | +0.144 |
| 5 | 9.0× | +0.247 |

**Interpretation.** `k_consistent` is not improving the trigger; it is throttling the
*baseline* harder than the proposed method, which widens the airtime gap. At k = 1, where
the ratio is closest to matched, the margin is within noise.

### E10 — fresh-seed replication (12,000 runs)

**Setup.** The headline frontier re-run on seed block 7000–7299, n = 300. Disjointness
**verified**: overlap with each of the seven other experiments is exactly **0 seeds**.

**Result.** Replicates. At matched airtime (budgets 5 and 11) the baseline wins 6 of 6.
Above that the proposed method leads while out-spending 2.5–10×.

**Interpretation.** The negative result is **not a seed artefact**. Nobody can claim the
result was tuned on these seeds.

### E3 and E11 — not run

- **E3 (matched-energy frontier)** was declared analysis-only in the deviations log, since
  `energy` is on every frontier row. **The matched-energy comparison has still not been
  written.** Phase 3 §8.3 flagged it as *"the most important outstanding gap"*, and it
  remains open.
- **E11** (closing the Phase 3 n = 300 deviation at speeds 0.50 and 1.00) was deferred as
  lowest priority — it strengthens an existing negative result rather than answering an
  open question.

---

### E12 — low hazard: the first matched comparison at a high alarm rate (9,600 runs)

**Why.** Every comparison in the programme up to this point was matched only at roughly
9--11 alarms per run, because the baseline saturates there. A probe showed the baseline
fires 86 alarms/run at hazard 0.10, so at a low enough hazard level the budget becomes
reachable by both methods.

**Setup.** Hazard {0.10, 0.15, 0.20, 0.25}, budgets {11, 22, 45}, calibration at 20 seeds.
Three predictions pre-registered in the script.

**Results.** P1 **HELD** — the baseline reaches budget 45 on target at hazard 0.10 and
0.15 (44.98, 45.40) and saturates at 0.20 (36.9) and 0.25 (22.1), as predicted. P2
**HELD** — the matched margin stays negative: 23 of 25 E12 matched cells.
P3 **MIXED** — the matched latency penalty has vanished across the whole low-hazard range
(+0.3, +0.1, +0.6, −0.6 ticks against +17…+44 at hazard 0.50) but is flat near zero rather
than monotone, and at hazard 0.15 it is +0.1, not ≤ 0.

**The controlled demonstration.** Holding the requested budget at 45 and varying only the
hazard level isolates the programme's central claim within one experiment:

| hazard | baseline fired | out-spend | margin |
|---|---|---|---|
| 0.10 | 36.9–49.4 | 0.92–1.07× | −0.051 to +0.003 |
| 0.15 | 37.6–50.7 | 0.88–1.05× | −0.045 to −0.020 |
| 0.20 | 29.8–40.9 | 1.12–1.41× | −0.032 to +0.022 |
| 0.25 | 18.4–24.9 | 1.86–2.23× | **+0.034 to +0.104** |

The proposed method's alarm count is on target in every row. **Only the baseline's ability
to spend the budget changes**, and the margin reverses with it. Where the rest of the
programme establishes this by correlation across 332 cells, E12 establishes it by control
within one experiment.

**Interpretation and setup-dependence.** This closes the limitation the sanity check
exposed. It also adds a qualification: the deficit **narrows with budget** (−0.0718 at 5,
−0.0562 at 11, −0.0270 at 22, −0.0235 at 45) and two of 79 matched cells reach a
statistical tie. Two of 79 is not parity and the mean is negative at every budget tested,
so the honest statement is that the deficit shrinks roughly threefold and stops short of
closing.

### E13 — recalibration at 20 seeds (4,800 runs)

**Why.** The programme calibrated at 8 seeds where Phase 1 had settled on 20, and that was
the one limitation the sanity check could not clear.

**Result. Prediction HELD.** Recalibration did correct a genuinely off-target point — at
hazard 0.35 and budget 11 the baseline's achieved rate rose from 9.78 to 11.10, so those
cells had been slightly *less* matched than reported — and moved the 12-cell mean margin
from −0.0605 to −0.0585. No cell changed sign; all 24 comparisons still favour the
baseline. Budget 5, new at these levels, extends the result downward with a *larger*
deficit (−0.034 to −0.151).

**Interpretation.** A legitimate objection, tested directly, moved the headline by 0.002.
The calibration default is now 20 for all future experiments.

## 6. The finding that reorganises all of the above

Pooling **all 332 paired comparison cells** across the programme:

| method out-spends baseline by | cells | mean margin | wins | losses |
|---|---|---|---|---|
| < 0.9× | 27 | −0.046 | 0 | 27 |
| **0.9–1.1× (equal airtime)** | **79** | **−0.052** | **2** | **77** |
| 1.1–2× | 49 | −0.044 | 7 | 42 |
| 2–5× | 117 | +0.073 | 109 | 8 |
| > 5× | 60 | +0.156 | 60 | 0 |

The on-time margin tracks log(out-spend ratio) at **r = +0.861, p = 5.6 × 10⁻⁹⁹**.
Extrapolating that fit to equal airtime predicts **−0.054**; the measured value is −0.052.

**The reported advantage is airtime, not prioritisation.**

At equal airtime: mean **−0.0516**, 95% CI [−0.0572, −0.0459], **77 of 79 cells favour the
baseline**, p = 1.4 × 10⁻¹⁴, and the method is 7.2 ticks slower. It holds independently in
each of the eight experiments contributing matched cells, E10's fresh seeds included, and
— after E12 — at budgets 5, 11, 22 and 45 rather than only at the rate where the baseline
saturates.

### Sanity checks run against this conclusion

| check | outcome |
|---|---|
| Is saturation real, or another bracket artefact? | **REAL.** Trigger driven to exactly 0.0: baseline fires **8.50** alarms/run, flat from 0.0 to 0.001. Proposed at trigger 0 reaches **148.0**. |
| Is out-spend ratio just a proxy for budget? | **NO.** Within budget 11 alone (96 cells): r = +0.831. Within budget 45 alone (152 cells): r = +0.643. |
| Is the baseline flat across budgets? | **YES.** Pins at ~10.3 from budget 22 up while proposed tracks target within 2%. |
| Are E10's seeds disjoint? | **YES.** 0 overlap with all seven others. |
| Does a headline number regenerate independently? | **YES.** −0.066, matches. |

### The limitation this exposed in my own claim

All 42 matched cells sit at budgets 5 and 11 — **roughly 9–11 alarms/run**. There is **no
matched comparison at a high alarm rate anywhere**, in either direction, because the
baseline cannot be taken there.

So the claim must be stated precisely: *at equal airtime around 9–11 alarms/run, the
baseline wins 42 of 42.* It is **not** established that the method would lose at equal
airtime at 45 or 90 alarms — that comparison is **impossible** with this baseline, not
merely unrun. This is both the honest form of the result and the reason E4's capacity
finding is the contribution that survives.

### Not cleared

Phase 5 calibration used **8 seeds per level**, where Phase 1 raised its own to 20 after 5
proved to give triggers 24% off budget. Achieved rates are recorded and the proposed
method lands within 2% of target, so this is unlikely to have distorted the comparison —
but it is below the standard the earlier phase settled on. Re-running calibration at 20
seeds is the cheapest remaining improvement.

---

## 7. How the interpretation moved, phase by phase

| phase | the claim, as understood then | why it changed |
|---|---|---|
| 0 | the urgency trigger beats a hazard threshold | budget was unmatched and regions overlapped |
| 1 | it loses at matched budget, but the baseline is budget-capped, so the match is unfair | the cap is real; the inference from it was incomplete |
| 3 | above the cap the method dominates — but NOT SUPPORTED under the frozen rule | pre-registration prevented reinterpreting 3/4 as success |
| 4 | the failure is the wind shift specifically; a second source *helps* | correct, but measured at an unmatched budget |
| 5 | the dominance above the cap **is** the unmatched budget | 260 cells; r = +0.862; confirmed at trigger zero |

**Three mechanisms were proposed and all three were rejected by the data**: the deadline
confound (retracted on inspection), delivery capacity (pre-registered, then falsified at
12 points), and information scarcity / explorability (falsified by its own headline
experiment). Each was rejected rather than quietly replaced, and each rejection is in the
repository with the prediction that preceded it.

---

## 8. What stands

1. **Negative, and robust.** At equal airtime around 9–11 alarms/run a plain hazard
   threshold beats the proposed urgency trigger — across mission length, domain size,
   region count, region size, hazard level, burstiness, agent speed, sensor noise, GP
   window and both gate parameters, and on seeds never used for tuning.
2. **Positive, and real.** The baseline cannot be driven past ~8.5 alarms/run at any
   trigger setting. The proposed method reaches ~150 and converts that into on-time
   **0.747** and latency **46.1 ticks**, against the baseline's ceiling of ~0.40. *It can
   spend bandwidth the baseline physically cannot.*
3. **Methodological.** Matched-alarm-budget comparison **silently stops being matched**
   once the budget exceeds the baseline's ceiling. Any table quoting a margin at budget 22
   or above must print the achieved alarm counts beside it, or it misleads the reader.
4. **Attributed.** The unpredictable-scenario failure is the wind shift, not the
   unannounced source — which in fact *helps*, by the largest margins measured.

## 9. Open

- **E3, matched-energy comparison** — still unwritten, and now the only major gap. It is
  the comparison an operator would actually make.
- **E11** — the Phase 3 n = 300 deviation at speeds 0.50 and 1.00. Lowest priority; it
  strengthens an existing negative result rather than answering an open question.
- **Budgets beyond 45 at matched airtime.** The deficit narrows with budget
  (−0.072 → −0.024 from budget 5 to 45) without reversing. Testing whether it continues to
  narrow needs a hazard level below 0.10, where the baseline could spend still more.

### Closed since this log was first written

- **Phase 5 calibration at 20 seeds** — done (E13). It corrected one off-target point and
  moved the headline margin by 0.002.
- **The hazard < 0.25 lead** — tested (E12). It did *not* produce a matched-airtime win:
  23 of 25 matched cells still favour the baseline. What it produced instead was the
  first matched comparison at a high alarm rate, and the controlled demonstration that
  the programme's apparent wins are the baseline's saturation.
