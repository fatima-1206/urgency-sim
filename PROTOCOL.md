# PROTOCOL — the study of record

**Status: FROZEN on 2026-11-15, before any Phase 3 run.**

This document is written *before* the final numbers exist and **must not be edited after
the first Phase 3 run begins**. Its only purpose is to remove the researcher's freedom to
choose, after seeing results, which comparison to call the headline. If something here
turns out to be wrong, the correct response is to record the deviation in §10 and report
it — not to amend this file.

Author: Fatima Tu Zahra (23I-2616). Co-author: Aleena Zahra (23I-2514). FAST-NUCES.
Evidence base: [FEASIBILITY_REPORT.md](FEASIBILITY_REPORT.md), [FINDINGS.md](FINDINGS.md).

---

## 0. Why this protocol differs from the Phase 0 plan

The Phase 0 plan specified a **matched alarm budget** as the primary instrument: tune
every method to fire at the same rate as the `threshold` baseline, then compare. Phase 1
established that this instrument is **not fit for purpose**, for two independent reasons
(evidence: FEASIBILITY_REPORT §11):

1. **The baseline saturates.** `threshold` cannot fire more than ~10.4 alarms/run — its
   trigger is `max(0, obs − hazard)`, so at trigger 0 it already admits every hazard
   crossing. The reference budget was defined as *threshold at trigger 0*, i.e. the
   baseline's **ceiling**. Matching to it pins every other method to the worst point on
   its own operating curve.
2. **It is not robust.** On-time moves ~0.019 per alarm/run near the matched point, so a
   1.4-alarm residual mismatch — well inside the 15% tolerance — accounts for a large
   share of the headline effect.

Phase 1 also established that the two Phase 0 endpoints, on-time ratio and map RMSE, are
**not independent**: across seven methods they are rank-anti-aligned at Spearman 0.96
(Pearson r = +0.89, p = 0.007). Reporting both as primary endpoints double-counts.

This protocol therefore replaces the single matched point with a **budget frontier**, and
demotes map RMSE to a diagnostic. Both changes are pre-registered here, before results.

**These changes are favourable to the proposed method.** That is noted explicitly so a
reader can discount for it. The mitigations are: the frontier is reported in full (not at
a cherry-picked budget), the matched-budget comparison is *still* reported as a secondary
endpoint (§3) so the unfavourable result remains visible, and the primary claim is stated
at the narrow strength the evidence supports (§2).

---

## 1. Research questions, as they now stand

| | question | Phase 1 status |
|---|---|---|
| RQ1 | Does uncertainty-scaled surprise beat raw error as a trigger? | **Contradicted** at matched budget (−0.066, p = 1e-06). Tested again, not assumed. |
| RQ2 | Does the consequence term earn its place? | **Not supported** (−0.005, p = 0.71). Tested again. |
| RQ3 | Does an urgency-derived deadline beat a fixed one? | **Not supported** (−0.033, p = 0.004). Tested again. |
| RQ4 | Does the trigger expose a usable alarm budget a threshold cannot? | **Supported in pilot** (§11). **This is the primary question.** |
| RQ5 | Does upload-point selection (two-tier + `goto_region`) carry its own weight? | **Supported.** Regions chosen 37–44%; discovery 97–98%. |

RQ1–RQ3 are reported as **pre-registered negative results**. They are not dropped
because they failed; dropping them is the thing this protocol exists to prevent.

## 2. Primary endpoint — exactly one

> **The alarm-budget frontier of on-time delivery ratio over observable events, for
> `proposed` versus `threshold`.**

Primary claim, stated at full strength so it can be falsified:

> *`threshold` is budget-capped at ~10.4 alarms/run. `proposed` is not, and at budgets
> above that cap achieves a strictly higher on-time delivery ratio than `threshold`
> achieves at any budget.*

**Decision rule, fixed now:**

- **Supported** if `proposed` at 45 alarms/run exceeds `threshold`'s maximum over its
  whole sweep, by a margin whose 95% CI excludes zero, in **both** connectivity
  scenarios and **both** field scenarios.
- **Not supported** otherwise. A result at three of four cells is *not supported*; it is
  reported as a partial result and the claim is weakened in the write-up.

Budget targets (fixed): **5, 11, 22, 45, 90** alarms/run. Triggers found by bisection to
within 10% of target; achieved rates reported, not assumed.

## 3. Secondary endpoints

Reported for every method, in this order, with Holm correction across the pairwise
family (§7):

1. **Matched-budget on-time ratio** — the Phase 0 instrument, retained *specifically*
   because it is unfavourable. Its known flaws (§0) are reported alongside it.
2. Mean and p95 latency.
3. False-alarm rate and false-alarm detours.
4. Energy proxy.
5. Region discovery rate and `goto_region` share (RQ5).

**Diagnostic, not an endpoint:** map RMSE, misbelief fraction. These are reported with
the frontier and with the §6 correlation, and **no claim is made from them in
isolation**. Any map-RMSE difference must be reported together with the on-time
difference for the same comparison.

## 4. Methods

Unchanged from the pilot. Seven methods; each differs from `proposed` in exactly one
component (trigger x deadline rule x action rule). Every method builds a cloud GP map;
only the trigger differs.

`proposed`, `fixed_dl`, `threshold`, `time_urg`, `always_tx`, `surprise_abl`, `raw_abl`.

**No method may be added or removed after this file is frozen.**

## 5. Factors

| factor | levels |
|---|---|
| field scenario | predictable, unpredictable |
| connectivity | sparse (13.3% effective), dense (33.4% effective) |
| speed ratio | 0.25, 0.50, 1.00 — dilution-corrected (`wind_ref` set, `dilution_exp = 0.55`) |

Speed ratio **0.10 is excluded**: at 149 events/run versus 266–390 elsewhere, the plume
never leaves the source region within the mission, so it is a different problem rather
than a slower one (FEASIBILITY_REPORT §12). This exclusion is pre-registered, with its
reason, rather than applied after seeing the column.

Dense connectivity is reported **with its geometric ceiling stated**: ~0.34 effective
coverage is the maximum achievable on 40x40 while keeping regions separable at the
discovery threshold (FEASIBILITY_REPORT §4).

## 6. Seeds and sample size

| block | use |
|---|---|
| 0–199 | pilot — **never** used in the study of record |
| 1000–1029 | Phase 1 speed sweep — never used in the study |
| **2000–2299** | **calibration** for the study |
| **3000–3299** | **evaluation** — the study of record |

Calibration and evaluation blocks are **disjoint**. The Phase 1 runs calibrated on seeds
0–19 while evaluating on 0–59; that leak is a known limitation of Phase 1 and is closed
here.

**n = 300 seeds per cell.** Power from the Phase 1 paired standard deviations
(α = 0.05 two-sided, 80% power, paired):

| comparison | observed effect | paired SD | d_z | n for 80% |
|---|---|---|---|---|
| proposed vs threshold | −0.089 | 0.217 | 0.411 | 46 |
| proposed vs raw_abl | −0.066 | 0.206 | 0.322 | 76 |
| proposed vs fixed_dl | −0.033 | 0.175 | 0.188 | 222 |
| proposed vs surprise_abl | −0.005 | 0.182 | 0.027 | 10,966 |

300 seeds x 4 scenario cells = 1,200 pairs, which covers the first three comfortably.

**The `surprise_abl` comparison is explicitly underpowered and will stay underpowered.**
Detecting the observed effect would need ~11,000 pairs. It is therefore reported as an
**equivalence result with its CI**, not as a null: the honest statement is "the effect,
if any, is smaller than this study can resolve", never "there is no effect". This is
fixed now so it cannot be reframed later.

## 7. Statistics

- Paired **Wilcoxon signed-rank** on identical seeds, per comparison.
- **Holm correction** across the pairwise family (6 comparisons against `proposed`).
  Both corrected and uncorrected p-values reported.
- 95% CIs on all reported means and differences.
- Significance threshold α = 0.05 **after** correction.
- Any comparison reported as null must carry its CI (see §6).

## 8. Calibration

- `scripts/calibrate.py` with **NS = 20** minimum, on seeds **2000–2299**.
- Re-run after **every** mechanical change, without exception. A pilot run with drifted
  budgets made the method look far better than it was; a Phase 1 run with NS = 5 did it
  again. This rule has now failed twice by being applied too weakly.
- Achieved fire rates reported for every method in every table. A method more than 15%
  off reference is flagged in the table, not silently included.
- For the frontier (§2), triggers are bisected per budget target; the matched-budget
  secondary endpoint (§3) uses the single calibrated trigger.

## 9. Execution

Two passes. **Pass 1 → fix what it exposes → pass 2 is the study of record.** Pass 1
results are never reported as final. Then robustness:

- Sensitivity on k, hazard, `w_consequence`, `upload_consec`, deadline range, GP window.
- Seed-stability re-run on a second disjoint block (4000+).
- **Budget-vs-energy frontier** — required before the §2 claim is used, since more alarms
  mean more detours and the Phase 1 frontier does not report energy.

`bin/run_tests.sh` must pass (56 tests) before every pass. Every result row carries a git
SHA, config hash and library versions.

## 10. Deviations log

Any departure from this protocol is recorded here with its date and reason, and reported
in the write-up. An empty section at the end of the study is itself a result.

| date | deviation | reason |
|---|---|---|
| 2026-11-15 | ~~n = 100 evaluation seeds per cell, not 300~~ — **CLOSED the same day: speed level 0.25 completed at the full n = 300.** Levels 0.50 and 1.00 remain deferred. | Thesis deadline. Power recomputed from the Phase 1 paired SDs (below): n = 100 retains >= 96% power for every comparison this study can resolve at any feasible size. The one comparison it cannot resolve, `surprise_abl`, is unresolvable at n = 300 as well (8% vs 15% power; ~10,800 pairs needed), and §6 already requires it to be reported as an equivalence result with its CI rather than as a null. The reduction therefore costs no resolvable comparison. **It does cost generality**: with one speed level the study speaks to the simulator's native operating regime (0.25, nearest the native 0.32) and **not** to the speed factor in §5. Any claim about speed must be labelled as resting on the Phase 1 sweep, not on this study. |

Power at the deviated size (pooled pairs = seeds x 4 cells, alpha = 0.05 two-sided):

| comparison | d_z | pairs for 80% | power at n=60 | **power at n=100** | power at n=300 |
|---|---|---|---|---|---|
| primary frontier (proposed @45 vs threshold max) | 0.84 | 11 | 100% | **100%** | 100% |
| proposed vs threshold (matched) | 0.411 | 46 | 100% | **100%** | 100% |
| proposed vs raw_abl | 0.322 | 76 | 100% | **100%** | 100% |
| proposed vs fixed_dl | 0.188 | 222 | 83% | **96%** | 100% |
| proposed vs surprise_abl | 0.027 | 10,770 | 6% | **8%** | 15% |

The primary endpoint is the least demanding comparison in the study: the frontier effect
(~0.18 on-time) is four times the matched-budget effect it replaces, so it needs 11 pairs
where that one needs 46. Deferring speed levels, not shrinking n, is what this deviation
actually costs.

**Outcome of closing the n deviation.** At n = 100 the `unpredictable/dense` cell failed
the §2 rule with +0.033 [−0.006, +0.072], and the pre-registered explanation on the table
was that 38% power had simply failed to resolve it. Completing the cell at n = 300 (82%
power) did **not** resolve it in the method's favour: the effect *shrank* to
+0.017 [−0.008, +0.041] while the CI tightened. The failure is therefore a property of
the method in that regime, not an artefact of the reduced sample. The other three cells
strengthened (p = 2.7e-13, 1.4e-09, 1.9e-05). This is recorded because the underpowering
explanation was offered in advance and must be marked as tested and rejected, not quietly
dropped.

## 11. What would falsify the thesis

Stated now so it cannot be renegotiated later:

- If §2's decision rule is **not** met, the trigger contribution fails and the thesis
  leads on RQ5 (upload-point selection) alone, reporting RQ1–RQ4 as negative.
- If RQ5 also fails — region discovery below 80%, or `goto_region` below 15% — the
  honest outcome is a **negative-results thesis**: a well-tested simulator and four
  pre-registered negative findings about urgency-driven triggering. That is a legitimate
  contribution and is the fallback, not a failure state to be avoided by retuning.

---

## 12. Execution mechanics

The study is executed by `scripts/phase3.py` (`bin/run_phase3.sh`), which implements
§2–§9 and decides nothing of its own.

**Crash safety.** Every completed run is written to `results/phase3/runs.jsonl` and
`fsync`'d before the next run starts, so an interruption — Ctrl-C, a crash, a flat
battery, a closed lid — costs at most the single run in flight. Re-running the same
command resumes; there is no flag to remember. A row counts as done only if its
`cfg_hash` matches the configuration currently in force, so a config change re-runs what
it invalidates rather than mixing two configurations in one table. Verified by SIGKILL
mid-run: 106 rows survived intact, the resume executed exactly the 454 remaining, with
no duplicates and no torn lines.

**Order of work.** Speed levels run one at a time and in the order 0.25, 0.50, 1.00 —
0.25 first because it is nearest the simulator's native operating point (0.32). Within a
level, calibration runs first, then the matched-budget secondary endpoint, then the
frontier. **Each completed speed level is a reportable result on its own**, so the study
yields usable findings from the first few hours rather than nothing until the end.

**Cost** at 10 workers, 300 evaluation seeds per cell:

| level | calibration | matched | frontier | time |
|---|---|---|---|---|
| 0.25 | 5,120 | 8,400 | 12,000 | ~3.3 h |
| 0.50 | 5,120 | 8,400 | 12,000 | ~4.2 h |
| 1.00 | 5,120 | 8,400 | 12,000 | ~5.2 h |

~12.7 h per pass, ~25 h for both passes (§9). Higher speed levels cost more because the
field integrator needs more substeps to stay inside the CFL budget.

`--seeds` or `--calib-seeds` below the protocol values prints a warning and marks the run
as a pilot pass; only a full-size pass 2 is the study of record. A calibration file
produced at a smaller `--calib-seeds` than the current run requests is **not** reused, so
a pilot pass cannot silently contaminate the study.

**Achieved fire rates are reported, never assumed.** A trigger is a continuous knob but
the fire rate it produces is not, so some budget targets are unreachable — `threshold`
cannot exceed ~10 fires/run at any trigger, and at low budgets its rate steps rather than
slides. Calibration records the achieved rate next to every trigger and flags anything
more than 10% off target. In the 0.25 dry run `threshold` at budget 5 achieved 3.6
fires/run (−28%); that is an inherent granularity limit of the baseline, is reported as
such, and is not corrected by moving the target.

**Storage.** `results/phase3/runs.jsonl` reaches ~151 MB at full size (~2 KB per run) and
is excluded from version control; the calibration records in `results/phase3/calib/` are
small and are committed, since they are what makes a run reproducible.

### Dry-run validation (speed 0.25, 10 seeds, 5 calibration seeds)

Completed in 13.7 min with no errors. Reported for mechanism only — it is a pilot pass,
far below protocol size, and none of its numbers are results:

| budget | proposed on-time | threshold on-time |
|---|---|---|
| 5 | 0.226 | 0.253 |
| 11 | 0.339 | 0.320 |
| 22 | 0.372 | 0.320 (saturated) |
| 45 | 0.502 | 0.320 (saturated) |
| 90 | 0.504 | 0.320 (saturated) |

The saturation predicted in §0 reproduces exactly: `threshold` returns an identical run
for every budget at and above 11. Note also that `proposed` **plateaus between 45 and 90**
(0.502 → 0.504) where the Phase 1 frontier rose (0.469 → 0.600). At n = 40 this is well
inside noise, but if it holds at full size the §2 decision rule — which evaluates at
budget 45 — is unaffected, while any claim that the frontier keeps rising beyond 45 is
not supported. Recorded here, before the study, so it cannot be read either way after.
