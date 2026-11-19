"""Figure 5 (deferred enforcement, E5).
Usage: python3 fig6.py accuracy_E5.csv OUT_DIR"""
import sys, pandas as pd, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
a = pd.read_csv(sys.argv[1]).sort_values("partitions"); out = sys.argv[2]
INK, INK2, GRID = "#1f1e1c", "#6b6a63", "#e4e3de"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "axes.axisbelow": True, "axes.edgecolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "legend.frameon": False})
lab = {0: "no monitor", 20: "every 20\n(~1 s)", 40: "every 40\n(~2 s)", 100: "every 100\n(~5 s)"}
fig, ax = plt.subplots(figsize=(6.2, 3.6))
x = range(len(a))
correct = a.admitted - a.over_admit
ax.bar(x, correct, 0.55, color="#b9b8b0", label="admitted within the limit")
ax.bar(x, a.over_admit, 0.55, bottom=correct, color="#c0392b", alpha=0.75, label="admitted beyond the limit")
for i, r in enumerate(a.itertuples()):
    ax.text(i, r.admitted + 4, f"{r.admitted:.0f} admitted\n+{r.over_admit:.0f} over", ha="center", fontsize=7.5, color=INK)
ax.axhline(50, color=INK, ls="--", lw=1.2); ax.text(2.5, 42, "limit = 50", ha="center", fontsize=7.5, color=INK)
ax.set_xticks(list(x)); ax.set_xticklabels([lab[int(k)] for k in a.partitions])
ax.set_xlabel("Off-chain monitor checks the committed count every K requests"); ax.set_ylabel("Requests admitted (of ~200)")
ax.set_ylim(0, 250)
ax.set_title("Write-only deltas commit 98–100% of requests; overshoot grows with the check interval",
             loc="left", fontsize=10, color=INK)
ax.legend(loc="upper right", fontsize=7.5)
fig.savefig(f"{out}/Figure5_deferred_enforcement.png", dpi=300, bbox_inches="tight"); fig.savefig(f"{out}/Figure5_deferred_enforcement.pdf", bbox_inches="tight")
