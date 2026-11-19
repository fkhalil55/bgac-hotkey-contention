"""Paper figures 1-4 and 6 from round-level data (clean = non-degraded rounds).
Usage: python3 figs.py rounds.csv OUT_DIR accuracy.csv   (file names follow the manuscript numbering)"""
import sys, os
import numpy as np, pandas as pd
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
d = pd.read_csv(src)
d["sr"] = 100 * d.succ / (d.succ + d.fail)
d["deg"] = d.send < 0.9 * d.load
d["good"] = d.send * d.succ / (d.succ + d.fail)
c = d[~d.deg]

COL = {"part": "#2a78d6", "deltawrite": "#eb6834", "partsum": "#1baf7a",
       "deltarange": "#eda100", "partceil": "#e87ba4", "single": "#55534d"}
MRK = {"part": "o", "deltawrite": "s", "partsum": "^", "deltarange": "D", "partceil": "v", "single": "X"}
NAME = {"single": "single key", "part": "partitioned (N=16)", "partsum": "read-all partitions (N=16)",
        "deltarange": "delta keys + range count", "deltawrite": "delta keys, write-only", "partceil": "partitioned, ceil (N=16)"}
INK, INK2, GRID = "#1f1e1c", "#6b6a63", "#e4e3de"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": INK2,
                     "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
                     "axes.axisbelow": True, "legend.frameon": False})

def ci(x):
    x = np.asarray(x, float); n = len(x)
    if n < 2: return x.mean() if n else np.nan, np.nan, n
    return x.mean(), stats.t.ppf(0.975, n - 1) * x.std(ddof=1) / np.sqrt(n), n

def model(n, b=10):
    return 100 * n * (1 - (1 - 1 / n) ** b) / b

def save(fig, name):
    fig.savefig(f"{out}/{name}.png", dpi=300, bbox_inches="tight")
    fig.savefig(f"{out}/{name}.pdf", bbox_inches="tight")
    plt.close(fig)

# ---------- Fig 1: E2 partition sweep vs model ----------
e2 = c[c.exp == "E2"]
fig, ax = plt.subplots(figsize=(6.2, 3.8))
Ns = np.array(sorted(e2.N.unique()))
xs = np.logspace(0, np.log2(64), 200, base=2)
ax.plot(xs, [model(x) for x in xs], color=INK, lw=1.4, ls="--", zorder=1)
ax.text(40, model(40) + 3.5, "block-occupancy model\nB = 10 requests/block", color=INK, fontsize=8, ha="right")
shade = {5: 1.0, 20: 0.65, 50: 0.35}
offs = {5: -0.06, 20: 0.0, 50: 0.06}
for load in (5, 20, 50):
    m = [ci(e2[(e2.N == n) & (e2.load == load)].sr) for n in Ns]
    xx = Ns * 2 ** offs[load]
    ax.errorbar(xx, [v[0] for v in m], yerr=[v[1] for v in m], fmt="o-", ms=5, lw=1.6, capsize=2.5,
                color="#2a78d6", alpha=shade[load], label=f"{load} tx/s offered", zorder=3)
ax.set_xscale("log", base=2); ax.set_xticks(Ns); ax.set_xticklabels(Ns)
ax.set_xlabel("Number of counter partitions N"); ax.set_ylabel("Commit success rate (%)")
ax.set_ylim(0, 100)
ax.set_title("At 5 and 20 tx/s success follows the model within 3 points;\nat 50 tx/s it falls 3–21 points below",
             loc="left", fontsize=10, color=INK)
ax.legend(loc="lower right")
save(fig, "Figure1_partition_sweep")

# ---------- Fig 2: E1 goodput vs offered load ----------
e1 = c[c.exp == "E1"]
loads = [5, 10, 20, 50]
fig, ax = plt.subplots(figsize=(6.2, 3.8))
ax.plot(loads, loads, color=INK2, lw=1, ls=":", zorder=1)
ax.text(44, 49.5, "ideal: every request commits", color=INK2, fontsize=7.5, ha="right", va="bottom")
for s in ["deltawrite", "part", "single", "partsum", "deltarange"]:
    m = [ci(e1[(e1.strategy == s) & (e1.load == L)].good) for L in loads]
    ax.errorbar(loads, [v[0] for v in m], yerr=[v[1] for v in m], marker=MRK[s], ms=5, lw=1.6,
                capsize=2.5, color=COL[s], label=NAME[s], zorder=3)
ax.annotate("single key, read-all partitions and\ndelta + range overlap (~10% of load)", xy=(20, 2.2), xytext=(23, 9),
            fontsize=7.5, color=INK, arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
ax.set_xlabel("Offered load (tx/s)"); ax.set_ylabel("Goodput (committed tx/s)")
ax.set_xticks(loads); ax.set_ylim(0, 55)
ax.set_title("Write-only delta keys scale with load; every design that reads\na shared counter is capped near one commit per key per block",
             loc="left", fontsize=10, color=INK)
ax.legend(loc="upper left", fontsize=7.5)
save(fig, "Figure3_goodput")

# ---------- Fig 3: E3 actors at 20 tx/s ----------
e3 = c[(c.exp == "E3") & (c.load == 20)]
def pred(strat, A, N=16, B=10):
    k = [B // A + (1 if i < B % A else 0) for i in range(A)] if A <= B else [1] * B
    if strat == "single": return 100 * sum(1 for x in k if x > 0) / B
    if strat == "deltawrite": return 100.0
    return 100 * sum(N * (1 - (1 - 1 / N) ** x) for x in k) / B
fig, ax = plt.subplots(figsize=(6.2, 3.6))
A_ = [1, 3, 10]; strats = ["single", "part", "deltawrite"]; w = 0.26
for i, s in enumerate(strats):
    for j, A in enumerate(A_):
        mu, h, n = ci(e3[(e3.strategy == s) & (e3.actors == A)].sr)
        x = j + (i - 1) * w
        ax.bar(x, mu, w * 0.9, color=COL[s], edgecolor="white", lw=1, label=NAME[s] if j == 0 else None)
        ax.errorbar(x, mu, yerr=h, color=INK, capsize=2, lw=1)
        p = pred(s, A)
        ax.plot([x - w * 0.42, x + w * 0.42], [p, p], color=INK, lw=1.6, ls="--")
        ax.text(x, mu - 6, f"{mu:.0f}", ha="center", fontsize=7.5, color="white", fontweight="bold")
ax.plot([], [], color=INK, ls="--", lw=1.6, label="model prediction")
ax.set_xticks(range(3)); ax.set_xticklabels([f"{a} actor{'s' if a > 1 else ''}" for a in A_])
ax.set_ylabel("Commit success rate (%)"); ax.set_ylim(0, 105); ax.set_yticks(range(0, 101, 20))
ax.set_title("Spreading the same 20 tx/s over more actors removes contention,\nas the model predicts", loc="left", fontsize=10, color=INK)
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), fontsize=7.5, ncol=4)
save(fig, "Figure2_actors")

# ---------- Fig 4: E4 accuracy ----------
acc = pd.read_csv(sys.argv[3])
e4 = c[c.exp == "E4"]
order = [("single", 1), ("partsum", 16), ("deltarange", 1), ("part", 4), ("part", 16), ("partceil", 16), ("part", 32)]
lab = {("single", 1): "single key", ("partsum", 16): "read-all, N=16", ("deltarange", 1): "delta + range",
       ("part", 4): "partitioned, N=4", ("part", 16): "partitioned, N=16", ("partceil", 16): "partitioned ceil, N=16",
       ("part", 32): "partitioned, N=32"}
fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.2, 3.9), sharey=True, gridspec_kw={"width_ratios": [1, 1.25]})
ys = np.arange(len(order))[::-1]
for y, (s, n) in zip(ys, order):
    mu, h, _ = ci(e4[(e4.strategy == s) & (e4.N == n)].sr)
    a1.barh(y, mu, 0.6, color=COL[s]); a1.errorbar(mu, y, xerr=h, color=INK, capsize=2, lw=1)
    a1.text(mu + (h if h == h else 0) + 2, y, f"{mu:.0f}%", va="center", fontsize=7.5, color=INK)
    r = acc[(acc.strategy == s) & (acc.partitions == n)].iloc[0]
    correct = r.admitted - r.over_admit
    a2.barh(y, correct, 0.6, color="#b9b8b0", label="correctly admitted" if y == ys[0] else None)
    a2.barh(y, r.over_admit, 0.6, left=correct, color="#c0392b", alpha=0.75, label="wrongly admitted" if y == ys[0] else None)
    a2.text(70, y, f"{r.admitted:.0f} admitted\n{r.over_admit:.0f} wrongly admitted, {r.early_deny:.0f} wrongly denied", va="center", fontsize=6.8, color=INK)
a2.axvline(50, color=INK, ls="--", lw=1.2); a2.text(50.8, ys[0] + 0.55, "limit = 50", fontsize=7.5, color=INK)
a1.set_yticks(ys); a1.set_yticklabels([lab[o] for o in order])
a1.set_xlim(0, 100); a1.set_xlabel("Commit success (%)")
a2.set_xlim(0, 125); a2.set_xticks(range(0, 71, 10)); a2.set_xlabel("Requests admitted (of 200, limit 50)")
a2.legend(loc="upper center", bbox_to_anchor=(0.35, -0.16), fontsize=7, ncol=2)
fig.suptitle("Exact designs never reach the limit because ~90% of requests fail to commit;\npartitioned designs commit but admit too few or too many",
             x=0.01, ha="left", fontsize=10, color=INK)
fig.tight_layout()
save(fig, "Figure4_accuracy")

# ---------- Fig 5: latency mechanism ----------
x = c[(c.strategy == "part") & (c.N == 16) & (c.actors == 1) & (c.load == 50) & c.exp.isin(["E1", "E2", "E3"])]
fig, ax = plt.subplots(figsize=(5.2, 3.4))
ax.scatter(x.avg_lat, x.sr, s=18, color="#2a78d6", alpha=0.7, edgecolor="white", lw=0.5)
r, p = stats.pearsonr(x.avg_lat, x.sr)
ax.axhline(model(16), color=INK, ls="--", lw=1.2); ax.text(x.avg_lat.max(), model(16) + 2, "model, no cross-block conflicts", ha="right", fontsize=7.5)
ax.set_xlabel("Mean commit latency in the round (s)"); ax.set_ylabel("Commit success rate (%)")
ax.set_ylim(0, 100)
ax.set_title(f"At 50 tx/s, rounds with slower commits lose more requests\n(partitioned N=16; r = {r:.2f}, n = {len(x)} rounds)", loc="left", fontsize=10, color=INK)
save(fig, "Figure6_latency")
print("figures written; fig5 r=%.2f p=%.2g n=%d" % (r, p, len(x)))
