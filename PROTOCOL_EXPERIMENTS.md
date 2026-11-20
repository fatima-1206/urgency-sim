# PROTOCOL — the experiment programme

**Frozen 2026-11-18, before any programme run.** Same terms as `PROTOCOL.md`: if
something here turns out wrong it is recorded in §8 and reported, not amended.

This protocol does **not** amend `PROTOCOL.md`. The Phase 3 verdict stands at
**NOT SUPPORTED, 3 of 4 cells, at every speed**, whatever this programme produces.

---

## 1. What prompted this

Phase 3 left one question open: the primary endpoint failed in 3 of 12 conditions, all
unpredictable-plume cells, and a delivery-capacity mechanism proposed to explain it was
pre-registered and **falsified**.

Two observations suggest the answer is in the **regime** rather than the algorithm.
Both were measured before this protocol was written.

**Explorability** — the fraction of the domain the agent can directly sample in one
mission, `mission_ticks · speed / cells`. The agent is a strict point sensor
(`sim.py` reads `field.sample` at its own cell and nowhere else; `sensor_range` appears
only in `metrics.observability`, where it decides which events count as observable when
scoring). At the Phase 3 configuration this is **0.50**.

> **Correction on record.** The first version of `explorability()` multiplied by a
> `(2r+1)` sensing swath and reported **3.50**, and that figure was used to argue the
> domain was over-explorable. It was wrong — the swath does not exist. The corrected
> figure is 0.50, and the argument it supported does not survive in that form.

**Connectivity scarcity** — 5.5 regions on 1,600 cells puts the agent on average
**1.5–2.4 cells** from a usable uplink, so travelling to connectivity costs almost
nothing. That part stands.

**GP capacity** — `window · π · length_scale² / cells`, how many times over the cloud
GP's fixed 140-point sliding window can cover the domain. At the Phase 3 configuration
it is **9.9**: the map is well informed even though the agent samples only half the
cells. This, not sensing coverage, is why information is not scarce.

---

## 2. Co-primary endpoints

Phase 3 had one. This programme has **two**, each with its own success rule:

1. **On-time delivery ratio** over observable events.
2. **Mean latency** — ticks from an event to the cloud belief crossing the hazard level.

Latency is promoted because it needs **no deadline**. `events.deadline_for` derives each
deadline from plume travel time to the sensitive zone, so at zero wind every event
returns `upwind=False` and the on-time endpoint is undefined — while latency remains
well defined. Checked on existing Phase 3 data, latency reproduces the saturation
structure (the baseline flatlines at 107.0 ticks while the proposed method reaches 77.3)
and favours the proposed method in 8 of 12 Phase 3 conditions.

**Map RMSE remains a diagnostic**, never a standalone claim: Phase 3 established it is
rank-anti-aligned with on-time across methods (Spearman −0.86), so the two are one
endpoint reported twice.

---

## 3. Seeds, sample size, statistics

| block | use |
|---|---|
| 0–199, 1000–1029, 2000–3299 | earlier phases — **never reused here** |
| **5000–5299** | calibration |
| **6000–6299** | evaluation |
| **7000–7299** | replication (E10) |

n = 100 seeds per cell (E10: 300). Paired Wilcoxon signed-rank on identical seeds;
95% CIs on every reported difference; **Holm correction within each experiment's
family**; corrected and uncorrected p-values both reported. Any comparison reported as
null must carry its CI and be stated as *"smaller than this study can resolve"*, never
as *"no effect"*.

**Calibration.** Triggers bisected **per level**, 8 seeds per grid point, 9 iterations.
The **achieved fire rate is recorded next to every trigger and flagged when more than
10% off target** — the rule that caught the Phase 3 calibration fault. Calibration
records are cached on config hash **and** calibration size, so a cheap smoke pass can
never be reused by a real run.

---

## 4. The experiments and their predictions

### E1 — Explorability  ★ headline

`explorability` 0.125 → 1.00 via mission length at n=40 (primary arm, GP capacity held
at 9.9), plus n=60 at T=800 as an independent cross-check (explorability 0.22, GP
capacity 4.4).

**The grid arm stops at n=60, decided in advance.** GP capacity falls with area —
9.9, 4.4, 2.5, 1.1 at n = 40, 60, 80, 120 — and at n=120 every method collapses to
on-time 0.00–0.06 firing ~1 alarm per run. Scaling the GP with area restores
measurability (0.140 vs 0.143) but makes the methods identical, costs O(window³) in the
Cholesky solve, and drives map RMSE to 0.068 because a larger domain is mostly empty.
n ≥ 80 is excluded with its reason rather than run and explained away.

1. The advantage **grows as explorability falls**: the on-time gap at T=200
   (explorability 0.125) exceeds the gap at T=1600 (1.00), in both connectivity
   scenarios.
2. The two arms **agree**: the gap at n=60 (0.22) lies between the gaps at T=400 (0.25)
   and T=200 (0.125). If the arms disagree, the finding is about the lever, not about
   explorability, and must be reported that way.
3. Absolute on-time **falls** with explorability for *both* methods — a scarcer regime is
   harder for everyone, not just the baseline.

*Falsified if* the gap shrinks as explorability falls, or the arms disagree.

### E2 — Connectivity scarcity

Region **count** {1, 2, 4, 8} at fixed size; region **size** {0.6, 0.8, 1.0, 1.3} at
fixed count. The geometric ceiling (~0.34 effective coverage on 40×40) caps the size arm.

4. The advantage is **larger when connectivity is scarcer**, in both arms.
5. The **count** arm matters more than the **size** arm at equal coverage: upload-point
   selection is a choice between alternatives, and with one region there is no choice.

### E4 — Budget ceiling

Budgets {90, 180, 360, 720}, proposed only (the baseline is saturated and returns
identical runs above ~10.5 alarms).

6. On-time **plateaus below 0.80** — the method has its own ceiling, and Phase 3's
   still-climbing curve at 90 does not continue indefinitely.

### E8 — Channel burstiness

Mean bad-state dwell {1.0, 2.86, 8.0, 20.0} at constant stationary loss.

7. The **two-tier upload rule earns its place as bursts lengthen**: the advantage over
   the baseline grows with burst length. Under near-independent loss (mean burst 1.0)
   requiring three consecutive successes is merely a harder coin flip.

### E7 — Hazard level

{0.25, 0.35, 0.50}.

8. **No Phase 3 conclusion flips.** The sign of the proposed-vs-threshold on-time
   difference at matched budget is the same at all three levels.

### E5 — Agent speed

{1, 2, 3} cells/tick. Depends on the `sim.py` fix (§7).

9. A faster agent **helps the baseline more**, because it reduces the travel cost that
   upload-point selection exists to manage, shrinking the advantage.

### E9 — Robustness battery

`k_consistent` {1,2,3,5}, `sensor_noise` {0.02,0.04,0.08}, `upload_consec` {1,2,3,5},
GP `window` {70,140,280}, at budget 45.

10. **No single parameter reverses the matched-budget sign.** A conclusion that holds at
    only one setting is not a conclusion.

### E10 — Seed-stability replication

The Phase 3 frontier on block 7000–7299, n=300, budgets {5, 11, 22, 45, 90}.

11. The frontier **reproduces**: every budget's pooled on-time is within the Phase 3
    95% CI, and the baseline saturates at the same alarm count.

---

## 5. What is confirmatory and what is not

Every prediction in §4 is **confirmatory for itself**. Everything else — regroupings
found after inspecting the data, mechanisms fitted post hoc — is **exploratory and must
be labelled as such**, as the Phase 3 scenario regrouping was.

Predictions 6, 9 and the "both methods fall" half of 3 are **unfavourable or neutral to
the method**. They are recorded so that a matching result counts as a confirmed
mechanism rather than a disappointment.

---

## 6. Reporting

Each experiment's `RESULTS.md` scores its own predictions **HELD** or **FALSIFIED**, in
the format of `results/phase3/PREDICTION_speed.md`. Findings that contradict the method
are reported at the same prominence as findings that support it.

If E1 confirms that the advantage grows as explorability falls, the correct framing is
**where the method applies** — it needs information to be scarce — and never a reason to
discard the Phase 3 result.

---

## 7. A bug this programme required fixing

`agent.speed` was consulted only by the decision code (`decision._path_qualities`
divides distance by it) while `sim.py` always stepped exactly one cell via `np.sign`. At
the default speed of 1 the two agree, so the mismatch was invisible — but any other
speed would have made the planner believe the agent moved faster than it did, silently
invalidating E5. `sim.py` now takes `speed` steps per tick. **Verified bit-identical at
speed = 1 across 40 runs** (2 scenarios × 2 connectivity × 5 seeds × 2 methods), so every
Phase 3 result stands.

---

## 8. Deviations log

Recorded with date and reason, and reported. An empty section at the end is itself a
result.

| date | deviation | reason |
|---|---|---|
| 2026-11-18 | E1's grid arm stops at n=60; n ∈ {80, 120} excluded | GP capacity falls to 2.5 and 1.1, and n=120 measured degenerate (on-time 0.00–0.06, ~1 alarm/run) for the GP's reasons rather than the agent's. Decided and recorded before the programme ran. |
| 2026-11-18 | E6 (mission length) merged into E1 | Mission length *is* the explorability lever; running it separately would have reported the same factor twice under two names. |
| 2026-11-18 | E3 (energy frontier) is analysis, not simulation | `energy` is already on every Phase 3 frontier row, so the matched-energy comparison needs no new runs. |
| 2026-11-18 | **E1: the alarm budget could not be matched at 8 of 10 cells.** The threshold baseline saturates far below the requested budget (2.5 alarms against a target of 45 at t200). The budget-45 comparisons are therefore **not matched-budget** and are reported as *proposed at 45 vs baseline at its own ceiling*, never as a like-for-like win. Discovered after the run; no analysis changed, only its labelling. | The baseline's alarm count is bounded by how many cells exceed the hazard line, which no trigger setting can raise. Lowering the baseline's trigger to zero still leaves it saturated. This is a property of the baseline, not a calibration fault, so it is reported rather than fixed. |
| 2026-11-18 | **E1 level t200: the predictable/unpredictable factor is degenerate.** `wind_shift_t=347` and `new_source_t=427` both fall after a 200-tick mission ends, so the two scenarios are the same simulation. The t200 rows for the two scenarios are identical by construction and must be counted once, not twice. | Found by noticing byte-identical rows. Rerunning t200 with a rescaled shift time would change two things at once (mission length and shift time), so t200 is reported as single-scenario instead. |
| 2026-11-18 | E4's `RESULTS.md` endpoint tables are empty. | `analyse.py` pairs the proposed method against a baseline; E4 is proposed-only by design, so there is nothing to pair. The ceiling is read off the budget-response curve instead, reported in E4's results section. |
| 2026-11-19 | Calibration size raised from 8 seeds to **20** for all future experiments (E12, E13). The eight completed experiments keep their 8-seed calibration and are **not** re-run. | 20 is the standard Phase 1 settled on after 5 seeds measured up to 24% off budget. Re-running the completed programme at 20 would remove essentially none of its flags: 52 of the 54 are the threshold baseline saturating, which is physics and not calibration noise. E13 instead tests the load-bearing matched cells directly, changing only the calibration size. |
| 2026-11-19 | **E12 added**: hazard {0.10, 0.15, 0.20, 0.25} at budgets {11, 22, 45}. Pre-registered in the script before any run. | Two reasons. It tests E7's untested lead (the matched-airtime latency penalty falls toward zero as hazard falls). More importantly it is the **only** regime where a matched comparison is possible at a high alarm rate: a probe shows the baseline fires 86 alarms/run at hazard 0.10, so budget 45 is reachable by both methods. Every other comparison in the programme is matched only at ~9-11 alarms/run. |
| 2026-11-19 | **E13 added**: the matched cells recalibrated at 20 seeds, under its own eid. | Tests whether the central negative result is an artefact of 8-seed calibration. Run separately rather than in place, so the 8-seed data stays intact and the two are comparable. |
| 2026-11-19 | `_check_triggers` added to the harness: it refuses to append runs to a store whose existing rows for the same (level, method, budget) were produced at a different trigger. | `store.key()` does not include the trigger, so re-calibrating an existing experiment would have applied the new trigger only to the runs not yet done, leaving one store holding two operating points under one label. Invisible in every table generated afterwards. This is the same class of fault that invalidated the first Phase 3 run. Verified to fire. |
| 2026-11-20 | **E13 scored: prediction HELD.** The 8-seed calibration did under-match the baseline at one point (hazard 0.35, budget 11: achieved 9.78 against 11.10 at 20 seeds), but correcting it moved the 12-cell mean margin from −0.0605 to −0.0585. No cell changed sign; all 24 comparisons favour the baseline. The calibration-size limitation is now tested rather than outstanding. | Recorded so the limitation is not restated in the paper as an open threat when it has been measured. |
| 2026-11-20 | **E12 scored: P1 and P2 HELD, P3 MIXED.** P3 predicted the matched latency penalty would reach ≤ 0 at hazard ≤ 0.15; measured +0.3, +0.1, +0.6, −0.6 ticks across hazard 0.10–0.25. The penalty has vanished relative to the +17…+44 measured at hazard 0.50, but it is flat near zero rather than monotone and at hazard 0.15 it is +0.1, not ≤ 0. Scored mixed rather than held. | The direction was right and the magnitude claim was not. Recording it as mixed rather than rounding +0.1 down to zero, since the prediction was written with a specific numeric form. |
| 2026-11-20 | **E14 added and scored: decoupled threshold (`threshold_dec`, fires at o > θ with θ free below h).** Hazard 0.35, speed 0.25, budgets {11, 90, 150}, 100 seeds, calibration 20. P1 PARTLY HELD (90 reached 91.9; 150 reached only 139.4, a second ceiling from the k-of-k gate). P2 HELD loosely (pooled gap to the coupled baseline at budget 11 is 0.015; one cell 0.021). P3 NOT HELD: the decoupled baseline does not beat the proposed method, but ties it at 90 (+0.011, CI [−0.012, +0.034]) and trails by +0.023 at 150, positive only in the unpredictable cells. | Added after the frozen programme because the paper's capacity claim depended on a baseline whose cap came from its parameterisation. About 92% of the capacity gap disappears. E14 is excluded from the 332-cell pool in `figs_paper.py` and reported separately. |
