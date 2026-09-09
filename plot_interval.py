#!/usr/bin/env python3
"""Interval width against error — the plot that shows whether a width means anything.

One panel per model, because the two share an axis and a dual-axis chart would be
a lie about the comparison.

  x  half the interval the model asked for
  y  how far its point estimate actually landed from the truth

The diagonal is where the two are equal. **Below it the truth fell inside the
interval.** A model with self-knowledge stretches its points along that diagonal:
narrow where it is right, wide where it is wrong. A model whose width is
decorative smears them vertically — same width everywhere, error all over.

Three choices worth stating:

1. **Symlog on both axes.** The items mix percentages with raw counts, so the
   values run from 0.5 to 25,000. On a linear scale four counts would own the
   plot and the forty-six percentage items would pile up in a corner. Symlog
   rather than log because a dozen answers are exactly right, and log has
   nothing to say about zero.

2. **Fill encodes coverage, not colour.** Filled means the truth was inside.
   Hollow means it was not. Coverage never depends on hue alone.

3. **Coverage comes from the run's own `covered` flag, not from the diagonal.**
   The two agree 50/50 for devstral but only 43/48 for lfm2, because an interval
   may sit off-centre around its estimate. The flag is the truth; the diagonal
   is a reading aid, and the mismatches are drawn as they really are.

  ./run.sh plot_interval.py results/<run>-interval.jsonl [more runs...]
"""
import json
import os
import statistics
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

INK, MUTED, GRID, SURFACE = "#1c1f26", "#6a7280", "#e4e7ec", "#fcfcfb"
SERIES = ["#1f6feb", "#b4531f"]      # validated: lightness band and contrast pass
LIM = (0.0, 60000.0)

# From `ollama show`, not from the on-disk size, which misleads: these two are
# 15GB and 14GB and look like a big model and a small one. They are not. Same
# parameter count to within 1%, same quantisation — the difference is dense
# against mixture-of-experts. Any "larger model" phrasing about this pair is wrong.
SPEC = {"devstral-small-2": "24.0B dense, Q4_K_M",
        "lfm2": "23.8B MoE, Q4_K_M"}


def spearman(xs, ys):
    n = len(xs)
    if n < 3:
        return None

    def rank(v):
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2.0 + 1
            i = j + 1
        return r

    rx, ry = rank(xs), rank(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else None


def load(path):
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    u = [r for r in rows
         if r.get("estimate") is not None
         and r.get("low") is not None and r.get("high") is not None]
    for r in u:
        r["_hw"] = (r["high"] - r["low"]) / 2.0
        r["_err"] = abs(r["estimate"] - r["truth"])
    cov = sum(1 for r in u if r["covered"])
    rho = spearman([r["_hw"] for r in u], [r["_err"] for r in u])
    return rows[0]["model"], u, cov, len(u), rho


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    runs = [load(p) for p in sys.argv[1:]]

    fig, axes = plt.subplots(1, len(runs), figsize=(4.6 * len(runs), 6.4), dpi=150,
                             sharex=True, sharey=True)
    if len(runs) == 1:
        axes = [axes]
    fig.patch.set_facecolor(SURFACE)

    for i, (ax, (model, u, cov, n, rho)) in enumerate(zip(axes, runs)):
        c = SERIES[i % len(SERIES)]
        ax.set_facecolor(SURFACE)
        ax.set_axisbelow(True)
        ax.grid(color=GRID, linewidth=0.8)
        ax.set_xscale("symlog", linthresh=1)
        ax.set_yscale("symlog", linthresh=1)

        # y = x is genuinely straight here: both axes carry the same symlog
        # transform and the same limits, so equal data values map to equal
        # display offsets. That is what lets fill_between shade the triangle.
        ax.plot(LIM, LIM, color=MUTED, linewidth=1.1, linestyle=(0, (5, 4)), zorder=2)
        ax.fill_between(LIM, 0, LIM, color=MUTED, alpha=0.06, zorder=1)
        ax.text(0.955, 0.045, "below the line,\nthe truth was inside",
                transform=ax.transAxes, color=MUTED, fontsize=8.5,
                va="bottom", ha="right", linespacing=1.5)

        inside = [r for r in u if r["covered"]]
        outside = [r for r in u if not r["covered"]]
        ax.scatter([r["_hw"] for r in inside], [r["_err"] for r in inside],
                   s=46, color=c, zorder=5, edgecolor=SURFACE, linewidth=1.3)
        ax.scatter([r["_hw"] for r in outside], [r["_err"] for r in outside],
                   s=46, facecolor="none", zorder=4, edgecolor=c, linewidth=1.5)

        ax.set_title(f"{model}  ({SPEC.get(model, '?')})\n"
                     f"{100*cov/n:.0f}% coverage  ·  rho {rho:+.2f}",
                     color=INK, fontsize=11.5, fontweight="bold", pad=11,
                     linespacing=1.6)
        ax.set_xlabel("Half-width the model asked for", color=MUTED,
                      fontsize=9.5, labelpad=8)
        if i == 0:
            ax.set_ylabel("How far the estimate actually missed by",
                          color=MUTED, fontsize=9.5, labelpad=8)
        ax.tick_params(colors=MUTED, labelsize=9, length=0)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color(GRID)
        ax.set_xlim(0, LIM[1])
        ax.set_ylim(0, LIM[1])

    h = [axes[0].scatter([], [], s=46, color=MUTED, edgecolor=SURFACE, linewidth=1.3,
                         label="truth inside the interval"),
         axes[0].scatter([], [], s=46, facecolor="none", edgecolor=MUTED,
                         linewidth=1.5, label="truth outside it")]
    leg = fig.legend(handles=h, loc="upper right", bbox_to_anchor=(0.978, 0.945),
                     frameon=False, fontsize=9, ncol=1, labelspacing=0.75,
                     handletextpad=0.6)
    for t in leg.get_texts():
        t.set_color(INK)

    fig.text(0.052, 0.975, "Two 24B models, and only one of them knows what it "
             "does not know",
             color=INK, fontsize=13.5, fontweight="bold", va="top", ha="left")
    fig.text(0.052, 0.928,
             "Points along the diagonal mean a model widening exactly where it is "
             "about to be wrong.\ndevstral tracks it and covers 76% against the 80% it "
             "asked for; lfm2 misses two-thirds.\nSame parameter count and quantisation "
             "— the difference is architecture, not size.\nBoth axes are symlog: the "
             "items mix percentages with raw counts.",
             color=MUTED, fontsize=9.6, va="top", ha="left", linespacing=1.6)

    fig.subplots_adjust(top=0.695, left=0.092, right=0.975, bottom=0.10, wspace=0.09)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "results", "interval.png")
    fig.savefig(out, facecolor=SURFACE)
    print("wrote", out)
    for model, u, cov, n, rho in runs:
        med_hw = statistics.median(r["_hw"] for r in u)
        print(f"  {model}: {cov}/{n} covered = {100*cov/n:.1f}%, "
              f"rho {rho:+.3f}, median half-width {med_hw:.1f}")


if __name__ == "__main__":
    main()
