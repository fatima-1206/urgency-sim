# urgency-sim

Simulator, experiment programme and paper for *Equal Budgets, Unequal Airtime:
Re-Evaluating Event Triggers for Intermittently Connected Mobile Sensing*
(Fatima Tu Zahra and Aleena Zahra, FAST-NUCES).

A single UAV surveys an evolving pollutant plume over a bursty radio link. It must decide
which readings are urgent enough to transmit and where to move in order to deliver them.
The repository compares a Gaussian-process urgency trigger against hazard-threshold
baselines under a matched alarm budget, and shows that the threshold's alarm ceiling can
silently unmatch that budget.

## What is where

| Path | Contents |
|---|---|
| `urgency_sim/` | the simulator: field PDE, GPs, channel, urgency trigger, routing, metrics |
| `tests/` | regression suite (`bin/run_tests.sh`) |
| `scripts/experiments/` | the experiment programme (E1–E14), one declaration per file, shared harness |
| `results/experiments/*/` | committed run archives (`runs.jsonl.gz`), calibration records and per-experiment `RESULTS.md` |
| `final_writeup/` | paper source (`paper.tex`), bibliography, figures and compiled PDF |
| `PROTOCOL.md`, `PROTOCOL_EXPERIMENTS.md` | frozen protocols and the deviations log |
| `EXPERIMENT_LOG.md`, `FINDINGS.md`, `PHASE3_REPORT.*`, `FEASIBILITY_REPORT.md` | project history, earlier phases |

## Reproducing the paper

Every table and figure regenerates from the committed archives with no re-simulation:

```bash
bin/setup.sh                                    # venv + dependencies
bin/run_tests.sh                                # regression suite
.venv/bin/python scripts/figs_paper.py          # paper figures + final_writeup/figs/NUMBERS.md
.venv/bin/python scripts/fig_architecture.py    # architecture figure
cd final_writeup && pdflatex paper && bibtex paper && pdflatex paper && pdflatex paper
```

To re-run an experiment from scratch (long; each prints its ETA with `--dry`):

```bash
.venv/bin/python scripts/experiments/e14_decoupled_threshold.py --dry
.venv/bin/python scripts/experiments/e14_decoupled_threshold.py
.venv/bin/python scripts/experiments/e14_decoupled_threshold.py --archive   # gzip + RESULTS.md
```

Every result row records the git commit, a configuration hash and library versions.

The sections below date from the feasibility prototype and still describe the basic tools.

## Install and run

Only numpy, scipy, scikit-learn and matplotlib are used (see `requirements.txt`).
Debian's system Python is externally managed (PEP 668), so a venv is required;
`--system-site-packages` lets it reuse apt-installed numpy/scipy/matplotlib.

```bash
bin/setup.sh            # venv + dependencies, then verifies the install
bin/run_all.sh          # setup + smoke test + all checks + animations (~5 min)
```

Or step by step:

```bash
bin/run_smoke.sh                             # field stability only (seconds)
bin/run_checks.sh --seeds 20                 # quick pass (~10 min)
bin/run_checks.sh                            # full suite, 200 seeds (~85 min)
bin/run_checks.sh --only 5,6 --seeds 50      # a subset
bin/run_animations.sh --seed 3 --conn sparse # animations + timeline plots
bin/clean.sh                                 # remove generated output (asks first)
.venv/bin/python scripts/calibrate.py        # re-derive triggers + deadline mapping
```

`scripts/calibrate.py` must be re-run after any change to the delivery mechanics,
deadlines or field: it sets every trigger threshold so all methods fire at the same
rate, and sets the urgency->deadline endpoints from the observed urgency spread.
Skipping it silently invalidates the comparisons -- an intermediate run with drifted
budgets made the proposed method look much better than it is, purely because it was
firing twice as often as the baseline.

The scripts are thin wrappers; you can always call the Python directly, e.g.
`.venv/bin/python scripts/run_checks.py --only 6`.

Outputs land in `figs/` (PNG, MP4) and `results/` (CSV, JSON, console log).

## Results

[FINDINGS.md](FINDINGS.md) is the short version;
[FEASIBILITY_REPORT.md](FEASIBILITY_REPORT.md) has the full evidence.
Several findings are negative.

## Layout

```
bin/               bash wrappers: setup, smoke, checks, animations, clean
urgency_sim/
  config.py        every tunable parameter, as frozen dataclasses
  field.py         advection-diffusion field, explicit FD with CFL checking
  connectivity.py  true coverage + Gilbert-Elliott, and the agent's DISCOVERED map
  gpmodel.py       sklearn GP with hyperparameters frozen after one fit
  urgency.py       the four trigger modes and the urgency -> deadline mapping
  decision.py      Monte-Carlo rollouts, P(deliver before deadline), action choice
  events.py        ground-truth critical events (physics only) and their deadlines
  methods.py       the method matrix: trigger x deadline rule x action rule
  sim.py           one mission = one (scenario, seed, method) run
  metrics.py       scoring a run against the ground-truth event set
scripts/
  smoke_field.py   stage-A: is the field stable, does the plume move
  run_checks.py    feasibility checks 1-8
  animate.py       animations and timeline plot (kept out of the package)
```

`scripts/animate.py` is separate from `urgency_sim/` so batch runs never pay for the
animation machinery. Simulation runs only store the data needed for metrics unless
`run(..., record_maps=True)` is passed.

## Units

1 cell = 20 m, 1 tick = 10 s, so the 50x50 grid is a 1 km square and a 400-tick mission
is about 67 minutes. The agent moves 1 cell/tick (2 m/s). Nothing in the code depends on
this mapping; it only makes the numbers physical.

## Determinism

Every run is `run(cfg, seed, method)`. The seed drives one `numpy.random.Generator` for
sensor noise, channel state and transmission outcomes, and a second, separately derived
generator for per-seed field jitter (source position, wind magnitude and angle, pulse
period) so that different seeds are genuinely different plume realisations rather than
the same plume with a different radio. Re-running a given `(cfg, seed, method)` always
reproduces the same trajectory.

## The method matrix

| key | trigger | deadline | action |
|---|---|---|---|
| `proposed` | surprise + consequence (additive) | from urgency | MC rollout choice |
| `fixed_dl` | surprise + consequence | fixed | MC rollout choice |
| `threshold` | measured value > hazard (no GP in trigger) | fixed | MC rollout choice |
| `time_urg` | time since last delivery (no GP in trigger) | from urgency | MC rollout choice |
| `always_tx` | surprise + consequence | from urgency | always transmit in place |
| `surprise_abl` | surprise only (no consequence term) | from urgency | MC rollout choice |
| `raw_abl` | raw error (no sigma scaling) + consequence | from urgency | MC rollout choice |

Every method builds a cloud GP map; only the TRIGGER differs. Two scenario axes are
crossed with these: field (`predictable` / `unpredictable`) and connectivity
(`sparse` ~13% / `dense` ~32% of cells with delivery probability > 0.5).

Trigger thresholds are calibrated so that every method raises roughly the same number of
alarms per run (~16), so comparisons are at a matched alarm budget rather than reflecting
one method simply being more trigger-happy. See `FEASIBILITY_REPORT.md`.

## Known additions to the proposal's design

Three things had to be added or changed to make the prototype run at all; each is
justified in `FEASIBILITY_REPORT.md`:

1. **Launch-point upload.** Without a baseline upload the cloud GP never receives data,
   so its posterior sd stays at the prior, so uncertainty-scaled error never exceeds the
   trigger, so nothing is ever sent -- a deadlock. The agent now dwells at the launch
   point for 12 ticks, sampling and uploading, before departing.
2. **A pulsing source.** A constant source with constant wind reaches steady state and
   then produces no further hazard crossings, making "predictable" degenerate.
3. **An explore tie-break.** Exploring wins near-ties, since it also earns information.
   Without it the agent abandons its survey whenever anything is pending.
4. **Two-tier messaging.** A short alert needs one successful tick; the full upload that
   actually updates the cloud needs 3 consecutive successes (or 1 where link quality
   >= 0.80). Without this every action reached P(deliver) ~ 1 and the decision rule was
   vacuous.
5. **Capped retries.** 45 attempts per pending item, each counted in the energy proxy.
