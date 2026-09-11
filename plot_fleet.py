#!/usr/bin/env python3
"""Epistemic Honesty Score against the Epoch Capabilities Index, one point per model.

Form: a scatter, because the question is whether two continuous measures move
together across a set of named entities. Every point is directly labelled, so
identity never depends on colour.

What is drawn, and why each piece is there:

* **Horizontal whiskers are Epoch's own ECI confidence intervals.** Several are
  more than ten points wide. A dot alone would imply a precision the capability
  axis does not have.
* **Vertical whiskers are the model's own run-to-run spread** — min to max across
  its complete repeat runs. They replace a single noise band once drawn across
  the whole chart, which had been measured on one model and extrapolated to all
  of them. A point with no vertical whisker has one complete run so far.
* **Filled points are the original ten; hollow points were added to widen the
  capability range.** Widening the range is the whole reason they are there, so
  the chart shows which points did it.
* **The title states what the confidence interval supports**, never the point
  estimate alone. An earlier version of this chart put a conclusion in its title
  that its own interval did not support.

  ./run.sh plot_fleet.py results/fleet.json
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

INK, MUTED, GRID, SURFACE = "#1c1f26", "#6a7280", "#e4e7ec", "#fcfcfb"
ACCENT = "#1f6feb"


def verdict_title(ci):
    if ci and ci[0] > 0:
        return "More capable models are more honest about their own uncertainty"
    if ci and ci[1] < 0:
        return "More capable models are less honest about their own uncertainty"
    return ("Does a more capable model know better what it doesn't know? "
            "This sample can't tell")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    rows = d["rows"]
    if not rows:
        sys.exit("no scored models with an ECI score yet")
    rho, ci_f = d.get("rho"), d.get("ci_full")
    excluded = d.get("excluded", [])

    fig, ax = plt.subplots(figsize=(10.4, 7.2), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    ax.set_axisbelow(True)
    ax.grid(color=GRID, linewidth=0.8)

    for r in rows:
        ax.plot([r["eci_lo"], r["eci_hi"]], [r["ehs"], r["ehs"]],
                color=ACCENT, alpha=0.26, linewidth=1.6, zorder=3,
                solid_capstyle="round")
        if r.get("n_reps", 1) > 1 and r["ehs_hi"] > r["ehs_lo"]:
            ax.plot([r["eci"], r["eci"]], [r["ehs_lo"], r["ehs_hi"]],
                    color=ACCENT, alpha=0.6, linewidth=2.4, zorder=4,
                    solid_capstyle="round")
        original = r.get("original_ten", True)
        ax.scatter([r["eci"]], [r["ehs"]], s=80, zorder=5,
                   color=ACCENT if original else SURFACE,
                   edgecolor=SURFACE if original else ACCENT,
                   linewidth=1.6 if original else 2.0)

    # Direct labels carry identity, so a collision makes a point unidentifiable.
    # Models close on both axes get their label flipped below the marker.
    placed = []
    for r in sorted(rows, key=lambda r: r["eci"]):
        below = any(abs(r["eci"] - px) < 3.2 and abs(r["ehs"] - py) < 8.0
                    for px, py, pb in placed if not pb)
        ax.annotate(r["tag"], (r["eci"], r["ehs"]), textcoords="offset points",
                    xytext=(0, -20 if below else 11), ha="center",
                    fontsize=8.8, color=INK)
        placed.append((r["eci"], r["ehs"], below))

    ys = [r["ehs"] for r in rows] + [r["ehs_lo"] for r in rows] + [r["ehs_hi"] for r in rows]
    xs = [r["eci_lo"] for r in rows] + [r["eci_hi"] for r in rows]
    ax.set_ylim(max(0, min(ys) - 10), min(100, max(ys) + 12))
    ax.set_xlim(min(xs) - 1.5, max(xs) + 1.5)
    ax.set_xlabel("Epoch Capabilities Index  —  general capability, higher is better",
                  color=MUTED, fontsize=10, labelpad=9)
    ax.set_ylabel("Epistemic Honesty Score  —  knowing what it does not know",
                  color=MUTED, fontsize=10, labelpad=9)
    ax.tick_params(colors=MUTED, labelsize=9.5, length=0)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)

    handles = [
        Line2D([], [], marker="o", linestyle="", markersize=8, color=ACCENT,
               markeredgecolor=SURFACE, label="the original ten models"),
        Line2D([], [], marker="o", linestyle="", markersize=8, color=SURFACE,
               markeredgecolor=ACCENT, markeredgewidth=2,
               label="added to widen the capability range"),
    ]
    leg = ax.legend(handles=handles, loc="lower right", frameon=False, fontsize=9)
    for t in leg.get_texts():
        t.set_color(INK)

    head = verdict_title(ci_f)
    lines = []
    if rho is not None and ci_f:
        lines.append(f"Spearman rho = {rho:+.2f} across {len(rows)} models spanning "
                     f"{d.get('span', 0):.0f} capability points; 95% interval with "
                     f"all uncertainty propagated: [{ci_f[0]:+.2f}, {ci_f[1]:+.2f}].")
    lines.append("Horizontal bars: Epoch's own uncertainty about each model's capability. "
                 "Vertical bars: the model's spread across repeat runs.")
    lines.append("The honesty score contains no accuracy term, so any relationship "
                 "here is measured, not built in.")
    ax.text(0.0, 1.20, head, transform=ax.transAxes, color=INK, fontsize=13.2,
            fontweight="bold", va="bottom", ha="left")
    ax.text(0.0, 1.025, "\n".join(lines), transform=ax.transAxes, color=MUTED,
            fontsize=9.2, va="bottom", ha="left", linespacing=1.6)

    notes = []
    if excluded:
        notes.append("Not plotted — complete runs, but answers that could not be "
                     "trusted: " + ", ".join(r["tag"] for r in excluded) + ".")
    single = [r["tag"] for r in rows if r.get("n_reps", 1) < 2]
    if single:
        notes.append("One complete run so far (no vertical bar): "
                     + ", ".join(single) + ".")
    if notes:
        fig.text(0.085, 0.018, "  ".join(notes), color=MUTED, fontsize=8.2,
                 ha="left", va="bottom", wrap=True)

    fig.subplots_adjust(top=0.77, left=0.085, right=0.975, bottom=0.14)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "results", "fleet.png")
    fig.savefig(out, facecolor=SURFACE)
    print("wrote", out)


if __name__ == "__main__":
    main()
