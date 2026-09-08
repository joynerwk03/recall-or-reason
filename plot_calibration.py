#!/usr/bin/env python3
"""Reliability diagram: stated confidence against measured accuracy.

The diagonal is perfect calibration. Everything below it is overconfidence, and
the vertical distance is how much. Bubble area encodes how many answers landed
in each bin, because a bin holding two answers should not read as loudly as one
holding sixty.

  ./run.sh plot_calibration.py results/<run>.jsonl [more runs...]
"""
import json
import math
import os
import sys
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

INK, MUTED, GRID, SURFACE = "#1c1f26", "#6a7280", "#e4e7ec", "#fcfcfb"
SERIES = ["#1f6feb", "#b4531f"]      # validated: lightness band and contrast pass


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - m), min(1.0, c + m)


def load(path):
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    rows = [r for r in rows if r.get("choice") is not None
            and r.get("confidence") is not None]
    bins = defaultdict(list)
    for r in rows:
        bins[min(9, int(r["confidence"] // 10))].append(bool(r["correct"]))
    pts = []
    for b, vals in sorted(bins.items()):
        pts.append(((b * 10 + 5) / 100, sum(vals) / len(vals), len(vals)))
    ece = sum((n / len(rows)) * abs(s - a) for s, a, n in pts)
    correct = sum(1 for r in rows if r["correct"])
    return rows[0]["model"], pts, ece, correct, len(rows)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    runs = [load(p) for p in sys.argv[1:]]

    fig, ax = plt.subplots(figsize=(7.6, 5), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    ax.set_axisbelow(True)
    ax.grid(color=GRID, linewidth=0.8)

    ax.plot([0, 1], [0, 1], color=MUTED, linewidth=1.1, linestyle=(0, (5, 4)), zorder=2)
    ax.text(0.60, 0.635, "perfect calibration", color=MUTED, fontsize=9,
            rotation=39, rotation_mode="anchor", va="bottom")

    for i, (model, pts, ece, k, n) in enumerate(runs):
        c = SERIES[i % len(SERIES)]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        sizes = [40 + 9 * p[2] for p in pts]
        ax.plot(xs, ys, color=c, linewidth=2.0, zorder=4, solid_capstyle="round")
        ax.scatter(xs, ys, s=sizes, color=c, zorder=5,
                   edgecolor=SURFACE, linewidth=1.6)
        ax.plot([], [], color=c, linewidth=2.0,
                label=f"{model} · {100*k/n:.0f}% correct · ECE {ece:.2f}")
        for x, y, m in pts:
            lo, hi = wilson(round(y * m), m)
            ax.plot([x, x], [lo, hi], color=c, linewidth=1.2, alpha=0.5, zorder=3)

    ax.set_xlim(0.45, 1.02)
    ax.set_ylim(0, 1.0)
    ax.set_xlabel("Confidence the model stated", color=MUTED, fontsize=10, labelpad=9)
    ax.set_ylabel("How often it was actually right", color=MUTED, fontsize=10, labelpad=9)
    ax.set_xticks([0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xticklabels([f"{int(t*100)}%" for t in [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]])
    ax.set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
    ax.tick_params(colors=MUTED, labelsize=9.5, length=0)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)

    leg = ax.legend(loc="upper left", frameon=False, fontsize=9.5)
    for t in leg.get_texts():
        t.set_color(INK)

    ax.text(0.0, 1.155, "Stated confidence is not worth much",
            transform=ax.transAxes, color=INK, fontsize=13.5, fontweight="bold",
            va="bottom", ha="left")
    ax.text(0.0, 1.035,
            "Every point sits below the diagonal, so every bin is overconfident.\n"
            "Bubble size is how many answers landed in that bin; bars are 95% intervals.",
            transform=ax.transAxes, color=MUTED, fontsize=10, va="bottom", ha="left")

    fig.subplots_adjust(top=0.80, left=0.11, right=0.97, bottom=0.13)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "results", "calibration.png")
    fig.savefig(out, facecolor=SURFACE)
    print("wrote", out)
    for model, pts, ece, k, n in runs:
        print(f"  {model}: {k}/{n} correct, ECE {ece:.3f}, "
              f"{len(pts)} populated bins")


if __name__ == "__main__":
    main()
