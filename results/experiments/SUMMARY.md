# Experiment programme — programme-level summary

76,000 simulation runs, 10 experiments, 332 paired comparison cells.

> **Read the update at the end first.** The body below was written after the first eight
> experiments and is preserved as written. E12 and E13 then closed the main limitation it
> records (§3 of the sanity check) and changed the headline counts. Every number in the
> body that E12/E13 superseded is corrected in
> [the update](#update-after-e12-and-e13), which is what the paper uses.
Governed by [PROTOCOL_EXPERIMENTS.md](../../PROTOCOL_EXPERIMENTS.md), frozen before any
run. Every number here regenerates from the committed `.gz` archives with no
re-simulation.

## The single finding that organises everything else

The programme set out to find a regime where urgency-driven triggering beats a plain
hazard threshold. It instead found why the comparison looked favourable in the first
place.

The threshold baseline **saturates**: its alarm count is bounded by how many observed
cells exceed the hazard line, and no trigger setting raises that. So at the higher alarm
budgets the two methods are not spending the same airtime — the proposed method sends
several times more messages. Across all 260 cells:

| the method out-spends the baseline by | cells | mean on-time margin | wins | losses | mean latency |
|---|---|---|---|---|---|
| less than 0.9× | 10 | −0.059 | 0 | 10 | — |
| **0.9–1.1× (equal airtime)** | **42** | **−0.060** | **0** | **42** | **+10.2 ticks** |
| 1.1–2× | 36 | −0.043 | 4 | 32 | +8.1 |
| 2–5× | 112 | +0.075 | 106 | 6 | −10.4 |
| more than 5× | 60 | +0.156 | 60 | 0 | −18.1 |

The on-time margin tracks the out-spend ratio almost perfectly: **r = +0.862,
p = 4.3 × 10⁻⁷⁸** against log(ratio). Extrapolating that fit to equal airtime predicts a
margin of **−0.065**, which is what is actually measured there (−0.060).

**The reported advantage is airtime, not prioritisation.**

## At equal airtime the baseline wins everywhere

Restricting to the 42 cells where the two methods spent comparable airtime (0.9–1.1×):

- on-time ratio: mean **−0.0605**, 95% CI [−0.0658, −0.0552], **42 of 42 cells favour
  the baseline**, p = 4.6 × 10⁻¹³
- latency: mean **+10.2 ticks slower**, p = 5.2 × 10⁻⁹

And it holds in every experiment independently:

| experiment | matched cells | mean margin | baseline better in |
|---|---|---|---|
| E1 explorability / mission length | 6 | −0.067 | 6/6 |
| E2 connectivity scarcity | 12 | −0.053 | 12/12 |
| E5 agent speed | 5 | −0.062 | 5/5 |
| E7 hazard level | 6 | −0.060 | 6/6 |
| E8 channel burstiness | 7 | −0.062 | 7/7 |
| E10 fresh-seed replication | 6 | −0.068 | 6/6 |

E10 used seed block 7000–7299, disjoint from every seed used in Phase 3 or anywhere else
in this programme. The negative result **replicates on seeds never used for any tuning**.

Phase 3's verdict of NOT SUPPORTED stands, and is now shown to be robust to mission
length, domain size, connectivity region count, region size, hazard level, channel
burstiness, agent speed, sensor noise, GP window length, and both gate parameters.

## The four exceptions, reported in full

Four cells out of 260 show a positive margin at an out-spend ratio below 2×:

| experiment | level | condition | out-spend | margin |
|---|---|---|---|---|
| E5 agent speed | speed 3 | predictable/sparse | 1.68× | **+0.046** |
| E5 agent speed | speed 3 | predictable/dense | 1.56× | +0.010 |
| E2 connectivity | 2 regions | predictable/sparse | 1.51× | +0.014 |
| E9 robustness | k=1 | predictable/sparse | 1.41× | +0.008 |

Three are within noise. The E5 speed-3 result is the only one with a real effect size,
and it is **confounded**: at speed 3 the baseline's alarm count collapses from ~9 to ~6
while observing the same number of events, because the `k_consistent` gate requires
agreement across consecutive ticks and a 3-cell-per-tick agent has moved nine cells
between the first observation and the third. The faster agent breaks the baseline's
consistency gate. That is a finding about the gate, not about urgency ranking, and it is
**not** evidence the method wins at speed.

## What the method does have

**E4 — capacity.** The baseline cannot be driven above roughly 10 alarms per run however
its trigger is set. The proposed method reaches a ceiling of ~150, and converts that into
on-time **0.747** and latency **46.1 ticks** — against the baseline's ceiling of ~0.40.
Phase 3 stopped at 90 alarms and reported on-time "still climbing"; it climbs to 0.747.

This is a real and useful property: *the method can spend bandwidth the baseline
physically cannot.* It is a much narrower claim than the one the project set out to make,
and it costs 8.2% more energy in a simulator whose energy is dominated by flight rather
than transmission, so the energy figure should not be quoted as an operational result.

## Predictions that were falsified

| prediction | outcome |
|---|---|
| The advantage grows as explorability falls (E1, headline) | **Falsified as stated.** The budget could not be matched at 8 of 10 levels, so the prediction is unscoreable there; and t400 vs n60 sit at explorability 0.25 and 0.22 with a five-fold difference in measured effect, so explorability is not the driver. |
| Scarcer connectivity favours the method (E2) | **Falsified.** 26 of 27 matched cells favour the baseline, down to a single small region. |
| The two-tier upload rule earns its keep as bursts lengthen (E8) | **Falsified.** An eight-fold increase in burst length moves the margin by nothing. |
| Conclusions are an artefact of one hazard threshold (E7) | **Falsified.** 12 of 12 matched cells favour the baseline at every hazard level. |
| The Phase 3 result is a seed artefact (E10) | **Falsified.** Replicates on a disjoint seed block at n=300. |

## One untested lead

E7 found the method's matched-airtime latency penalty falls from +17…+44 ticks at hazard
0.50 to roughly zero at hazard 0.25 — it does **better** when events are plentiful, the
opposite of the information-scarcity premise the programme was built on. Whether it would
overtake the baseline below hazard 0.25 is **not tested here** and is recorded as a lead,
not a result.

## Honest statement of what this programme is

It is a thorough negative result with one genuine positive finding (E4) and one
methodological finding (baseline saturation) that corrects how the earlier phases'
numbers should be read. Any table in the project that quotes a margin at alarm budget 22
or above must print the achieved alarm counts beside it, or it misleads the reader.

---

# Sanity check of the above

Six checks, run after the conclusions were written, aimed at breaking them.

## 1. Is the baseline's saturation real, or another bisection artefact? ✅ REAL

This is the claim the whole summary rests on, and it has the same shape as the bracket
bug caught before the programme started. Tested directly by driving the threshold
baseline's trigger to **exactly zero** rather than trusting the bisection:

| trigger | alarms/run |
|---|---|
| **0.000000** | **8.50** |
| 0.000001 | 8.50 |
| 0.000100 | 8.50 |
| 0.001000 | 8.50 |
| 0.0094 | 8.37 |
| 0.0375 | 8.03 |

Perfectly flat from zero to 0.001. The baseline genuinely cannot be driven past ~8.5
alarms/run; there is no setting that gets it to 45. Under the same conditions the
proposed method at trigger zero reaches **148.0**. The saturation is a property of the
method, not of the search.

## 2. Is "out-spend ratio" just a proxy for "alarm budget"? ❌ NO — the relationship survives

The obvious objection: higher budgets produce both higher ratios and higher margins, so
the r = +0.862 could be budget in disguise. Tested by holding the budget fixed:

| budget | cells | ratio range within that budget | r | p |
|---|---|---|---|---|
| 11 | 96 | 0.79× – 5.38× | **+0.831** | 1.1 × 10⁻²⁵ |
| 45 | 152 | 1.22× – 15.35× | **+0.643** | 4.2 × 10⁻¹⁹ |

At one single budget, the cells where the method out-spends the baseline more are the
cells where it wins more. The relationship is to airtime, not to the budget label.

## 3. Where do the 42 matched cells actually come from? ⚠️ A REAL LIMITATION — SINCE CLOSED BY E12

| budget | matched cells | mean margin |
|---|---|---|
| 5 | 3 | −0.077 |
| 11 | 39 | −0.059 |
| 22, 45, 90 | **0** | — |

**Every matched comparison in this programme sits at roughly 5–11 alarms per run.** There
is no matched comparison at a high alarm rate anywhere, in either direction, because the
baseline cannot be taken there.

So the claim must be stated precisely: *at equal airtime **around 9–11 alarms per run**,
the baseline wins 42 of 42 cells.* It is **not** established that the method would lose
at equal airtime at 45 or 90 alarms — that comparison is impossible to run with this
baseline, not merely unrun. This is the strongest honest form of the result, and it is
also precisely why E4's capacity finding is the contribution that survives.

## 4. Is the baseline flat across budgets? ✅ YES

| requested budget | baseline fired | proposed fired |
|---|---|---|
| 5 | 5.22 | 4.99 |
| 11 | 8.85 | 10.79 |
| 22 | 10.29 | 26.03 |
| 45 | 10.50 | 45.54 |
| 90 | 10.29 | 92.78 |

The baseline pins at ~10.3 from budget 22 upward while the proposed method tracks its
target to within 2%. The divergence begins between budget 11 and 22.

## 5. Are E10's replication seeds genuinely disjoint? ✅ YES

E10 uses seeds 7000–7299. Every other experiment uses 6000–6099. Measured overlap with
each of the seven other experiments: **0 seeds**. Phase 3 used block 3000. The
replication is clean.

## 6. Does a headline number regenerate independently? ✅ YES

Recomputed E10's budget-11 predictable/sparse cell straight from the committed archive
with a separate script: n = 300, proposed 0.341, threshold 0.407, **diff −0.066** —
matching the reported value.

## One thing the sanity check did not clear — since cleared by E13

Calibration used **8 seeds per level** (`calib_seeds = 8`). Phase 3 raised its own
calibration to 20 seeds after 5 proved to give triggers up to 24% off budget. The
achieved rates are recorded for every trigger and the proposed method's land within ~2%
of target, so this did not distort the comparison — but 8 is below the standard the
earlier phase settled on, and the numbers should be read with that in mind. Re-running
calibration at 20 seeds is the cheapest remaining improvement to this programme.


---

# Update after E12 and E13

Two further experiments were run after the above was written. Both were pre-registered in
their own scripts before any runs.

## E13 — the calibration limitation is cleared

The programme calibrated with 8 seeds per level where Phase 1 had settled on 20.
Recalibrating the load-bearing cells at 20 seeds **did** correct one genuinely off-target
point — at hazard 0.35 and budget 11 the baseline's achieved rate rose from 9.78 to
11.10, so those cells had been slightly *less* matched than reported — and changed the
conclusion by **0.002**: the 12-cell mean margin moved from −0.0605 to −0.0585, no cell
changed sign, and all 24 comparisons still favoured the baseline. The default is now 20.

## E12 — the "no matched comparison at a high alarm rate" limitation is closed

Sanity check §3 recorded that all matched cells sat at roughly 9–11 alarms per run, and
that a matched comparison at a higher rate was *impossible* against this baseline. That
was true only at the hazard levels then studied. At a lower hazard level more of the field
exceeds the threshold, the baseline is no longer saturated, and at hazard 0.10 and 0.15 it
reaches a requested budget of 45 on target (44.98 and 45.40 achieved).

**Matched cells now exist at budgets 5, 11, 22 and 45, and the result holds at all four.**

## Corrected headline figures

| quantity | before | **after E12 + E13** |
|---|---|---|
| comparison cells | 260 | **332** (9 experiments) |
| margin vs log(out-spend) | r = +0.862 | **r = +0.861**, p = 5.6 × 10⁻⁹⁹ |
| fit at equal airtime | −0.0647 | **−0.0540** |
| matched cells | 42 | **79** |
| matched mean margin | −0.0605 | **−0.0516** [−0.0572, −0.0459] |
| baseline better in | 42 of 42 | **77 of 79** |
| matched latency penalty | +10.2 ticks | **+7.2 ticks** |
| budgets with a matched cell | 5, 11 | **5, 11, 22, 45** |

| out-spend | cells | mean margin | wins | losses |
|---|---|---|---|---|
| < 0.9× | 27 | −0.046 | 0 | 27 |
| **0.9–1.1× (equal)** | **79** | **−0.052** | **2** | **77** |
| 1.1–2× | 49 | −0.044 | 7 | 42 |
| 2–5× | 117 | +0.073 | 109 | 8 |
| > 5× | 60 | +0.156 | 60 | 0 |

## The controlled demonstration E12 adds

Everything above is observational: it pools cells differing in many ways. E12 gives the
controlled version. Each row is the **same method at the same requested budget of 45**;
only the hazard level changes, and with it whether the baseline can spend that budget.

| hazard | baseline fired | out-spend | margin |
|---|---|---|---|
| 0.10 | 36.9–49.4 | 0.92–1.07× | −0.051 to +0.003 |
| 0.15 | 37.6–50.7 | 0.88–1.05× | −0.045 to −0.020 |
| 0.20 | 29.8–40.9 | 1.12–1.41× | −0.032 to +0.022 |
| 0.25 | 18.4–24.9 | 1.86–2.23× | **+0.034 to +0.104** |

The proposed method's own alarm count is on target throughout (44.80, 44.89, 44.91,
45.06). **Nothing about it changes between these rows.** As the baseline saturates, the
out-spend ratio climbs and the margin reverses.

## One qualification E12 adds

The deficit **narrows with budget**:

| budget | matched cells | mean margin | baseline better |
|---|---|---|---|
| 5 | 10 | −0.0718 | 10/10 |
| 11 | 52 | −0.0562 | 52/52 |
| 22 | 10 | −0.0270 | 9/10 |
| 45 | 7 | −0.0235 | 6/7 |

Two of the 79 matched cells have confidence intervals spanning zero. **Two of 79 is not
parity**, and the mean stays negative at every budget tested. The defensible statement is
that the deficit shrinks roughly threefold as the budget grows and stops short of closing.

## What is now the only genuinely open gap

The **matched-energy comparison** — what the extra alarms cost at equal energy rather than
equal alarms. It has not been performed, and it is the comparison an operator would
actually make.
