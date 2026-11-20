"""The system architecture figure for the paper.

Drawn here rather than reused from the Phase 2 proposal, whose diagram is the
twelve-step research process and not a system architecture. What matters and
must be visible: the agent's own GP and the cloud-belief GP are DISTINCT, and
urgency is scored against the cloud belief -- what the operator currently holds
-- not against what the agent knows.

    .venv/bin/python scripts/fig_architecture.py
"""
from __future__ import annotations

import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                      # noqa: E402
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch  # noqa: E402

OUT = pathlib.Path("final_writeup/figs")

AGENT = "#e8f0f8"
CLOUD = "#fdf0e4"
CHAN = "#efe8f4"
EDGE = "#2c3e50"


def box(ax, x, y, w, h, title, sub=None, fc=AGENT, bold=True):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.02",
        linewidth=1.0, edgecolor=EDGE, facecolor=fc, zorder=2))
    ax.text(x + w / 2, y + h * (0.62 if sub else 0.5), title,
            ha="center", va="center", fontsize=6.9,
            fontweight="bold" if bold else "normal", zorder=3)
    if sub:
        ax.text(x + w / 2, y + h * 0.27, sub, ha="center", va="center",
                fontsize=5.9, color="#44525e", zorder=3)
    return (x, y, w, h)


def arrow(ax, p, q, style="-|>", rad=0.0, color=EDGE, lw=1.0, ls="-"):
    ax.add_patch(FancyArrowPatch(
        p, q, arrowstyle=style, mutation_scale=9, linewidth=lw,
        color=color, linestyle=ls, zorder=1,
        connectionstyle=f"arc3,rad={rad}", shrinkA=1.5, shrinkB=1.5))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.1, 2.45))
    ax.set_xlim(0, 11.9)
    ax.set_ylim(0.1, 3.5)
    ax.axis("off")

    TOP, BOT, H = 2.42, 0.42, 0.68

    # Seven equal boxes with a uniform gap, so no subtitle overruns its box.
    W, GAP = 1.50, 0.18
    xs = [0.10 + i * (W + GAP) for i in range(7)]
    sens = box(ax, xs[0], TOP, W, H, "sensor", "1 cell / tick")
    agp = box(ax, xs[1], TOP, W, H, "agent GP", "all readings")
    urg = box(ax, xs[2], TOP, W, H, "urgency", r"Eq. (2)")
    gate = box(ax, xs[3], TOP, W, H, "$k$-of-$k$ gate", "queue, deadline")
    route = box(ax, xs[4], TOP, W, H, "routing", "upload point")
    chan = box(ax, xs[5], TOP, W, H, "channel", "G-E bursts", fc=CHAN)
    cloud = box(ax, xs[6], TOP, W, H, "cloud map", "operator's view", fc=CLOUD)

    # Wider than the row boxes: its label is the longest in the figure.
    cgp = box(ax, xs[2] - 0.25, BOT, W + 0.5, H, "cloud-belief GP",
              "delivered data only", fc=CLOUD)

    def r(b, f=0.5):
        return (b[0] + b[2], b[1] + b[3] * f)

    def l(b, f=0.5):
        return (b[0], b[1] + b[3] * f)

    def t(b, f=0.5):
        return (b[0] + b[2] * f, b[1] + b[3])

    def bo(b, f=0.5):
        return (b[0] + b[2] * f, b[1])

    for a, b in ((sens, agp), (agp, urg), (urg, gate), (gate, route),
                 (route, chan), (chan, cloud)):
        arrow(ax, r(a), l(b))

    # The distinction this figure exists to make: urgency is scored against the
    # cloud belief, not against the agent's own model.
    arrow(ax, t(cgp), bo(urg), color="#c0392b", lw=1.4)
    ax.text(xs[2] - 0.12, 1.42, "scored against what\nthe operator already has",
            ha="right", va="center", fontsize=6.0, color="#c0392b")

    # Only successful full uploads reach the cloud belief.
    arrow(ax, bo(cloud, 0.45), r(cgp, 0.5), rad=-0.18, color="#b08f63",
          ls=(0, (3, 2)))
    ax.text(xs[5] + W / 2, 0.38, "successful full uploads only", ha="center",
            fontsize=6.1, color="#b08f63")

    # Link quality is measured in flight and feeds the routing rollouts. Drawn as
    # an annotation on the block that consumes it: routed as an arrow it ran
    # behind the row and read as a stray line.
    arrow(ax, (xs[4] + W / 2, TOP - 0.46), bo(route, 0.5), color="#5b7a95",
          ls=(0, (3, 2)))
    ax.text(xs[4] + W / 2, TOP - 0.56,
            "link quality measured in flight\n$\\rightarrow$ discovered regions",
            ha="center", va="top", fontsize=6.0, color="#5b7a95")

    ax.text(0.10, 3.30, "onboard the agent", fontsize=6.4, color="#7d8d9a",
            style="italic")
    ax.text(xs[6], 3.30, "operator", fontsize=6.4, color="#b08f63",
            style="italic")

    fig.savefig(OUT / "fig_architecture.png", dpi=320, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {OUT / 'fig_architecture.png'}")


if __name__ == "__main__":
    main()
