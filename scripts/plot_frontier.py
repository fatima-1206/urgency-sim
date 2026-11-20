"""Plot the alarm-budget frontier written by scripts/budget_frontier.py."""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

d = json.load(open("results/budget_frontier.json"))
fig, ax = plt.subplots(1, 3, figsize=(13, 3.8))
col = {"proposed": "tab:blue", "threshold": "tab:orange"}
for mk, rows in d.items():
    f = [r["fires"] for r in rows]
    ax[0].errorbar(f, [r["on_time"] for r in rows],
                   yerr=[r["on_time_sem"] for r in rows],
                   marker="o", color=col[mk], label=mk)
    ax[1].errorbar(f, [r["rmse"] for r in rows],
                   yerr=[r["rmse_sem"] for r in rows],
                   marker="o", color=col[mk], label=mk)
    ax[2].plot([r["on_time"] for r in rows], [r["rmse"] for r in rows],
               marker="o", color=col[mk], label=mk)
for a, (xl, yl) in zip(ax, [("alarms per run", "on-time ratio"),
                            ("alarms per run", "map RMSE (lower better)"),
                            ("on-time ratio", "map RMSE (lower better)")]):
    a.set_xlabel(xl); a.set_ylabel(yl); a.grid(alpha=.3); a.legend(fontsize=8)
ax[0].set_xscale("log"); ax[1].set_xscale("log")
# The threshold baseline cannot fire more than ~10 alarms/run: its trigger is
# max(0, obs - hazard), so trigger -> 0 already admits every hazard crossing.
ax[0].axvline(10.4, ls=":", c="tab:orange")
ax[0].annotate("threshold saturates", (10.4, 0.22), fontsize=7,
               rotation=90, color="tab:orange", va="bottom")
fig.suptitle("Alarm-budget frontier: the proposed trigger can spend a larger "
             "budget; the threshold baseline cannot", fontsize=9)
fig.tight_layout()
fig.savefig("figs/budget_frontier.png", dpi=130)
print("-> figs/budget_frontier.png")
