"""2D advection-diffusion pollutant field, explicit finite differences.

Arrays are indexed c[x, y] so that positions read naturally; plotting
transposes once. Boundaries are open (zero halo), so plume leaves the domain.
"""
import numpy as np

from .config import Config, FieldCfg


def cfl_limit(fc: FieldCfg, wind) -> float:
    """Largest stable dt: advection and diffusion share the same explicit
    update, so their limits COMBINE rather than taking the minimum.

        dt <= 1 / (|u|/dx + |v|/dx + 4D/dx^2)

    Using min(adv, dif) instead is too permissive and lets the field diverge.
    """
    u, v = abs(wind[0]), abs(wind[1])
    rate = (u + v) / fc.dx + 4.0 * fc.diffusion / fc.dx ** 2
    return np.inf if rate <= 0 else 1.0 / rate


class PollutantField:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.fc = cfg.fld
        self.n = self.fc.n
        self.c = np.zeros((self.n, self.n), dtype=float)
        self.t = 0
        self.substeps = self._auto_substeps()
        self.dt = 1.0 / self.substeps
        self._check_cfl()
        for _ in range(self.fc.spinup):
            self.step(spinup=True)
        self.t = 0

    # -- scenario schedule -------------------------------------------------
    def wind_at(self, t: int):
        fc = self.fc
        if self.cfg.scenario == "unpredictable" and t >= fc.wind_shift_t:
            return fc.wind_after
        return fc.wind

    def sources_at(self, t: int):
        """Release rate over time. The primary source pulses slowly so that the
        field keeps evolving; a constant rate equilibrates and stops producing
        hazard crossings, which would make the predictable scenario degenerate.
        The pulse is smooth and periodic, so it remains learnable.

        If `wind_ref` is set the rate is additionally scaled by
        (|wind|/wind_ref)**dilution_exp, which holds the peak concentration
        roughly constant as the wind speed changes (F1). Without this a speed
        sweep varies difficulty and speed at the same time."""
        fc = self.fc
        mod = 1.0 + fc.pulse_amp * np.sin(2.0 * np.pi * t / fc.pulse_period)
        mod *= self._dilution_gain(t)
        s = [(fc.source_xy[0], fc.source_xy[1], fc.source_q * mod)]
        if self.cfg.scenario == "unpredictable" and t >= fc.new_source_t:
            # unscheduled second release, ramping in over ~15 ticks
            ramp = min(1.0, (t - fc.new_source_t) / 15.0)
            s.append((fc.new_source_xy[0], fc.new_source_xy[1],
                      fc.new_source_q * ramp * self._dilution_gain(t)))
        return s

    def _dilution_gain(self, t: int) -> float:
        fc = self.fc
        if fc.wind_ref is None or fc.wind_ref <= 0:
            return 1.0
        w = float(np.hypot(*self.wind_at(t)))
        return (w / fc.wind_ref) ** fc.dilution_exp

    SAFETY = 0.8   # fraction of the CFL limit we allow ourselves to use

    def _auto_substeps(self):
        """Choose substeps so one tick = 1.0 time unit AND dt stays inside the
        CFL budget for whatever wind this config has. Needed for the speed
        sweep: dt=0.5 is unstable once |wind| >= ~0.7 cells/tick."""
        fc = self.fc
        lim = min(cfl_limit(fc, fc.wind), cfl_limit(fc, fc.wind_after))
        need = int(np.ceil(1.0 / (self.SAFETY * lim)))
        return max(fc.substeps, need)

    def _check_cfl(self):
        fc = self.fc
        for w in (fc.wind, fc.wind_after):
            lim = cfl_limit(fc, w)
            if self.dt > self.SAFETY * lim:
                raise ValueError(
                    f"dt={self.dt} exceeds {self.SAFETY}x CFL limit {lim:.4f} "
                    f"for wind {w}, D={fc.diffusion}. Lower dt or raise substeps."
                )

    # -- integration -------------------------------------------------------
    def step(self, spinup: bool = False):
        """Advance one TICK, which is `substeps` integration substeps."""
        for _ in range(self.substeps):
            self._substep(spinup)
        if not spinup:
            self.t += 1
        return self.c

    def _substep(self, spinup: bool = False):
        fc = self.fc
        t = 0 if spinup else self.t
        u, v = self.wind_at(t)
        c = self.c
        p = np.pad(c, 1, mode="constant", constant_values=0.0)

        # first-order upwind advection (stable; diffusive but that is fine here)
        if u >= 0:
            dcdx = (p[1:-1, 1:-1] - p[:-2, 1:-1]) / fc.dx
        else:
            dcdx = (p[2:, 1:-1] - p[1:-1, 1:-1]) / fc.dx
        if v >= 0:
            dcdy = (p[1:-1, 1:-1] - p[1:-1, :-2]) / fc.dx
        else:
            dcdy = (p[1:-1, 2:] - p[1:-1, 1:-1]) / fc.dx

        lap = (p[2:, 1:-1] + p[:-2, 1:-1] + p[1:-1, 2:] + p[1:-1, :-2]
               - 4.0 * c) / fc.dx ** 2

        c_new = c + self.dt * (-u * dcdx - v * dcdy
                               + fc.diffusion * lap - fc.decay * c)
        for sx, sy, q in self.sources_at(t):
            c_new[sx, sy] += self.dt * q

        self.c = np.clip(c_new, 0.0, None)

    def sample(self, x: int, y: int, rng: np.random.Generator, noise: float) -> float:
        return float(self.c[x, y] + rng.normal(0.0, noise))


def rollout_field(cfg: Config, ticks: int):
    """Return the full true-field history, shape (ticks+1, n, n). Used by the
    evaluator (which needs ground truth) and by the animation."""
    f = PollutantField(cfg)
    hist = np.empty((ticks + 1, f.n, f.n), dtype=np.float32)
    hist[0] = f.c
    for i in range(1, ticks + 1):
        f.step()
        hist[i] = f.c
    return hist
