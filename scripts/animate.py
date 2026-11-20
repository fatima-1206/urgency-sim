"""Animations and the per-run timeline plot. Kept out of the simulation
package so batch runs never import matplotlib's animation machinery.

Usage:
    python scripts/animate.py                 # both scenarios, both methods
    python scripts/animate.py --seed 3 --fps 20
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, FFMpegWriter, PillowWriter
from matplotlib.patches import Rectangle

from urgency_sim.config import Config, with_scenario, with_conn
from urgency_sim.connectivity import ge_mean_multiplier
from urgency_sim.events import zone_mask
from urgency_sim.sim import run

OUT = pathlib.Path("figs")
ACTION_COLOR = {"explore": "#4da3ff", "transmit_now": "#ffd166"}


def _draw_static(ax, log, cfg, title):
    n = cfg.fld.n
    zx, zy = cfg.ev.zone_xy
    h = cfg.ev.zone_half
    ax.add_patch(Rectangle((zx - h - .5, zy - h - .5), 2 * h + 1, 2 * h + 1,
                           fill=False, ec="#00e5ff", lw=1.8, ls="--", zorder=5))
    ax.set_xlim(-.5, n - .5); ax.set_ylim(-.5, n - .5)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(title, fontsize=10)


def animate_run(log, path, fps=18, show_contour=True):
    cfg = log.cfg
    n = cfg.fld.n
    T = len(log.pos)
    truth = log.truth
    cloud = log.cloud_maps
    vmax = float(np.percentile(truth[:T], 99.5))

    n = cfg.fld.n
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(11.6, 6.0))
    fig.patch.set_facecolor("#111318")
    for ax in (axL, axR):
        ax.set_facecolor("#111318")

    imL = axL.imshow(truth[0].T, origin="lower", cmap="inferno",
                     vmin=0, vmax=vmax, interpolation="nearest")
    imR = axR.imshow(cloud[0].T, origin="lower", cmap="inferno",
                     vmin=0, vmax=vmax, interpolation="nearest")
    _draw_static(axL, log, cfg, "TRUE field + agent")
    _draw_static(axR, log, cfg, "CLOUD belief")
    for ax in (axL, axR):
        ax.title.set_color("w")

    # true connectivity regions: grey until the agent discovers them
    # --- connectivity overlay -------------------------------------------
    # A semi-transparent blue tile layer whose opacity tracks the EFFECTIVE
    # per-attempt delivery probability (geometric quality x the mean
    # Gilbert-Elliott multiplier). Regions are combined with max(), exactly as
    # the simulator does when it decides delivery -- so overlapping regions do
    # NOT compound into something darker than the stronger one. Cells below
    # p = 0.05 are left fully transparent so the plume stays readable.
    ge = ge_mean_multiplier(cfg.comm)
    SHOW_CONTOUR = show_contour
    gx, gy = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
    reg_p, reg_disc_t = [], []
    for (cx, cy, rad, peak, is_launch) in log.regions_true:
        d2 = (gx - cx) ** 2 + (gy - cy) ** 2
        reg_p.append(peak * np.exp(-0.5 * d2 / (rad / 2.0) ** 2) * ge)
        # discovered once the agent has stood somewhere the link is usable
        r_disc = ((rad / 2.0) * np.sqrt(2.0 * np.log(
            peak / cfg.comm.discover_threshold))
            if peak > cfg.comm.discover_threshold else 0.0)
        dt = None
        if is_launch:
            dt = 0
        else:
            for ti, (px, py) in enumerate(log.pos):
                if np.hypot(px - cx, py - cy) <= r_disc:
                    dt = ti
                    break
        reg_disc_t.append(dt)
    reg_p = np.asarray(reg_p)
    # Alpha ramps from zero AT the hide threshold rather than jumping to
    # p*alpha, so weak tails stay invisible instead of hazing the whole panel.
    P_ALPHA, P_HIDE = 0.42, 0.12

    def _rgba(pmap, rgb):
        a = np.clip((np.clip(pmap, 0, 1) - P_HIDE) / (1.0 - P_HIDE), 0, 1) * P_ALPHA
        img = np.zeros((n, n, 4))
        img[..., 0], img[..., 1], img[..., 2] = rgb
        img[..., 3] = a
        return np.transpose(img, (1, 0, 2))

    zeros = np.zeros((n, n))
    ov_undisc = axL.imshow(_rgba(zeros, (0.55, 0.57, 0.60)), origin="lower",
                           zorder=2, interpolation="nearest")
    ov_disc = axL.imshow(_rgba(zeros, (0.25, 0.55, 1.0)), origin="lower",
                         zorder=3, interpolation="nearest")
    half_contour = [None]

    def update_overlay(k):
        mask_d = np.array([dt is not None and dt <= k for dt in reg_disc_t])
        pd = reg_p[mask_d].max(axis=0) if mask_d.any() else zeros
        pu = reg_p[~mask_d].max(axis=0) if (~mask_d).any() else zeros
        pu = np.where(pd >= pu, 0.0, pu)       # discovered wins where both
        ov_disc.set_data(_rgba(pd, (0.25, 0.55, 1.0)))
        ov_undisc.set_data(_rgba(pu, (0.55, 0.57, 0.60)))
        if half_contour[0] is not None:
            for c in half_contour[0].collections:
                c.remove()
        half_contour[0] = axL.contour(
            gx, gy, pd, levels=[0.5], colors=["#bcd9ff"],
            linewidths=0.7, alpha=0.30, zorder=5) \
            if (SHOW_CONTOUR and pd.max() > 0.5) else None

    update_overlay(0)
    sx, sy = cfg.agent.start_xy
    axL.plot([sx], [sy], marker="*", ms=16, color="#7CFC00", zorder=7)

    path_line, = axL.plot([], [], "-", color="#9fd3ff", lw=1.0, alpha=.75, zorder=6)
    agent_dot, = axL.plot([], [], "o", ms=8, mec="w", mew=1.2,
                          color="#4da3ff", zorder=8)
    tx_ok = axL.scatter([], [], s=55, marker="^", c="#39ff88",
                        edgecolors="k", linewidths=.4, zorder=9)
    tx_no = axL.scatter([], [], s=28, marker="x", c="#ff5555", zorder=9)
    fire_sc = axL.scatter([], [], s=150, marker="o", facecolors="none",
                          edgecolors="#ff2d95", linewidths=2.0, zorder=10)
    ev_sc = axR.scatter([], [], s=42, marker="s", facecolors="none",
                        edgecolors="#00e5ff", linewidths=1.2, zorder=9)

    label = fig.text(.5, .965, "", ha="center", color="w", fontsize=11)
    sub = fig.text(.5, .935, "", ha="center", color="#aab", fontsize=9)
    fig.text(.5, .032, "blue = delivery probability: more blue = stronger link "
                       "(regions combined with max(), as the simulator does)    "
                       "grey = region not yet discovered    "
                       "pale line = p = 0.5",
             ha="center", color="#8891a0", fontsize=8)
    fig.text(.5, .010, "★ launch    cyan dashed = sensitive zone    ▲ delivered    "
                       "✕ failed    ○ pink = urgency fired    "
                       "▫ cyan = live critical event",
             ha="center", color="#8891a0", fontsize=8)

    fires = list(log.fires)
    txs = list(log.tx)
    det_t = {t for (t, *_rest) in log.detours}
    found = {}
    for (t, cx, cy) in log.region_found:
        found.setdefault((round(cx), round(cy)), t)

    def frame(k):
        imL.set_data(truth[k].T)
        imR.set_data(cloud[k].T)
        px = [p[0] for p in log.pos[:k + 1]]
        py = [p[1] for p in log.pos[:k + 1]]
        path_line.set_data(px, py)
        agent_dot.set_data([px[-1]], [py[-1]])
        act = log.action[k]
        agent_dot.set_color(ACTION_COLOR.get(act, "#ff9f1c"))

        ok = [(x, y) for (t, x, y, s) in txs if t <= k and s]
        no = [(x, y) for (t, x, y, s) in txs if t <= k and not s]
        tx_ok.set_offsets(np.array(ok) if ok else np.empty((0, 2)))
        tx_no.set_offsets(np.array(no) if no else np.empty((0, 2)))
        fr = [(x, y) for (t, x, y, u, dl) in fires if t <= k]
        fire_sc.set_offsets(np.array(fr) if fr else np.empty((0, 2)))

        live = [(e.x, e.y) for e in log.events if e.t <= k <= e.deadline]
        ev_sc.set_offsets(np.array(live) if live else np.empty((0, 2)))

        update_overlay(k)

        nd = sum(1 for (t, *_r) in log.detours if t <= k)
        ndel = sum(1 for (t, _n) in log.deliveries if t <= k)
        pend = log.pending_dl[k]
        label.set_text(f"{getattr(log,'conn_scenario','?')} | {log.scenario} | "
                       f"{log.method} | seed {log.seed} | "
                       f"t={k}   ACTION: {act.upper()}"
                       + ("  [DETOUR]" if k in det_t else ""))
        sub.set_text(f"fires {len(fr)}   deliveries {ndel}   detours {nd}   "
                     f"regions found {log.n_regions[k]}   "
                     + (f"deadline t={pend:.0f}" if np.isfinite(pend) else "no pending item"))
        return []

    anim = FuncAnimation(fig, frame, frames=T, interval=1000 / fps, blit=False)
    path = pathlib.Path(path)
    try:
        anim.save(str(path), writer=FFMpegWriter(fps=fps, bitrate=2400))
    except Exception as exc:
        print("  ffmpeg failed (%s); falling back to gif" % exc)
        path = path.with_suffix(".gif")
        anim.save(str(path), writer=PillowWriter(fps=fps))
    plt.close(fig)
    print("  wrote", path)
    return path


def timeline_plot(log, path):
    cfg = log.cfg
    T = len(log.pos)
    fig, (a0, a1) = plt.subplots(2, 1, figsize=(12, 6.4), sharex=True,
                                 gridspec_kw=dict(height_ratios=[2, 1.5]))
    sc = np.asarray(log.score)
    a0.plot(sc, lw=.9, color="#4da3ff", label="urgency score")
    a0.axhline(cfg.urg.z_trigger, color="#ff2d95", ls="--", lw=1,
               label=f"trigger = {cfg.urg.z_trigger}")
    a0.set_yscale("symlog", linthresh=1.0)
    for (t, x, y, u, dl) in log.fires:
        a0.axvline(t, color="#ff2d95", alpha=.35, lw=1)
        a0.annotate("", xy=(dl, u), xytext=(t, u),
                    arrowprops=dict(arrowstyle="->", color="#ffd166", lw=1.4))
    for (t, nn) in log.deliveries:
        a0.axvline(t, color="#39ff88", alpha=.5, lw=1.2)
    a0.set_ylabel("urgency")
    a0.set_title(f"{log.scenario} | {log.method} | seed {log.seed}   "
                 "(pink = urgency fired, yellow arrow = its deadline, "
                 "green = delivery)", fontsize=10)
    a0.legend(fontsize=8, loc="upper left")

    from urgency_sim.metrics import event_outcomes
    outs = event_outcomes(log)
    for i, o in enumerate(outs):
        y = i
        a1.plot([o["t"], min(o["deadline"], T)], [y, y], color="#888", lw=1.6)
        a1.plot([o["t"]], [y], "o", ms=3.5, color="#00e5ff")
        if o["ever_t"] is not None:
            a1.plot([o["ever_t"]], [y], "*", ms=8,
                    color="#39ff88" if o["on_time"] else "#ff5555")
    a1.set_xlabel("tick"); a1.set_ylabel("critical event #")
    a1.set_title("cyan = event occurs, grey bar = its physics deadline, "
                 "green star = cloud learned in time, red star = learned late, "
                 "nothing = never learned", fontsize=9)
    a1.set_xlim(0, T)
    plt.tight_layout(); plt.savefig(path, dpi=115); plt.close(fig)
    print("  wrote", path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=3)
    ap.add_argument("--fps", type=int, default=18)
    ap.add_argument("--methods", default="proposed,threshold")
    ap.add_argument("--conn", default="sparse,dense")
    ap.add_argument("--no-contour", action="store_true",
                    help="hide the p=0.5 contour line")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    base = Config()
    for conn in args.conn.split(","):
        for scen in ["predictable", "unpredictable"]:
            for mk in args.methods.split(","):
                print(f"[{conn}/{scen}/{mk}] simulating...")
                log = run(with_conn(with_scenario(base, scen), conn),
                          args.seed, mk, record_maps=True)
                animate_run(log, OUT / f"anim_{conn}_{scen}_{mk}.mp4",
                            fps=args.fps, show_contour=not args.no_contour)
                if mk == "proposed":
                    timeline_plot(log, OUT / f"timeline_{conn}_{scen}.png")


if __name__ == "__main__":
    main()
