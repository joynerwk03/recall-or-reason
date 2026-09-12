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
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

INK, MUTED, GRID, SURFACE = "#1c1f26", "#6a7280", "#e4e7ec", "#fcfcfb"
ACCENT = "#1f6feb"


def verdict_title(ci, share_pos=None):
    """The title states what the interval supports, and no more. An interval
    that includes zero but sits almost entirely on one side of it is neither a
    result nor a null, and the title says so rather than picking one."""
    if ci and ci[0] > 0:
        return "More capable models are more honest about their own uncertainty"
    if ci and ci[1] < 0:
        return "More capable models are less honest about their own uncertainty"
    if ci and share_pos is not None and share_pos >= 0.90 and ci[1] > 0.5:
        return ("More capable models look more honest about their own uncertainty "
                "— but the interval still touches zero")
    if ci and share_pos is not None and share_pos <= 0.10 and ci[0] < -0.5:
        return ("More capable models look less honest about their own uncertainty "
                "— but the interval still touches zero")
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

    ys = [r["ehs"] for r in rows] + [r["ehs_lo"] for r in rows] + [r["ehs_hi"] for r in rows]
    xs = [r["eci_lo"] for r in rows] + [r["eci_hi"] for r in rows]
    ax.set_ylim(max(0, min(ys) - 10), min(100, max(ys) + 12))
    xspan = max(xs) - min(xs)
    ax.set_xlim(min(xs) - 0.03 * xspan, max(xs) + 0.07 * xspan)
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

    head = "\n".join(textwrap.wrap(verdict_title(ci_f, d.get("share_positive")), 72))
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
    # Direct labels carry identity, so a collision makes a point unidentifiable.
    # Placement happens here, after the layout is final, and is measured in
    # display pixels. The previous version compared positions in DATA units
    # against thresholds picked when the axis spanned 22 capability points; at
    # 50 points those thresholds covered less than half the pixels they had
    # been tuned for, and two labels printed on top of each other.
    fig.canvas.draw()
    FS = 8.8
    ppp = fig.dpi / 72.0
    char_w, text_h = 0.63 * FS * ppp, 1.30 * FS * ppp
    ax_box = ax.get_window_extent()
    marker = {}
    for r in rows:
        mx, my = ax.transData.transform((r["eci"], r["ehs"]))
        marker[r["tag"]] = (mx - 9, my - 9, mx + 9, my + 9)
    try:
        lb = leg.get_window_extent()
        fixed = [(lb.x0 - 4, lb.y0 - 4, lb.x1 + 4, lb.y1 + 4)]
    except Exception:
        fixed = []

    def rect_at(px, py, dx, dy, w, ha):
        ox, oy = px + dx * ppp, py + dy * ppp
        if ha == "center":
            x0, x1 = ox - w / 2, ox + w / 2
        elif ha == "left":
            x0, x1 = ox, ox + w
        else:
            x0, x1 = ox - w, ox
        return (x0, oy - text_h / 2, x1, oy + text_h / 2)

    def overlap(a, b):
        """Area two label boxes share, in square pixels. Zero when they miss."""
        return (max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
                * max(0.0, min(a[3], b[3]) - max(a[1], b[1])))

    placed = []
    for r in sorted(rows, key=lambda r: r["eci"]):
        px, py = ax.transData.transform((r["eci"], r["ehs"]))
        w = len(r["tag"]) * char_w
        others = [v for k, v in marker.items() if k != r["tag"]]
        obstacles = placed + others + fixed
        # Every candidate is scored, so a crowded corner gets the least-bad
        # position instead of the default one. The first version stopped at
        # "none of the six is clean" and fell back to candidate one, which is
        # how two labels at the right edge ended up printed on top of each other.
        choice, best, best_cost = None, None, None
        for dx, dy, ha in ((0, 12, "center"), (0, -20, "center"),
                           (14, -4, "left"), (-14, -4, "right"),
                           (0, 25, "center"), (0, -33, "center"),
                           (13, 13, "left"), (-13, 13, "right"),
                           (13, -19, "left"), (-13, -19, "right"),
                           (0, 38, "center"), (0, -46, "center")):
            box = rect_at(px, py, dx, dy, w, ha)
            outside = max(0.0, ax_box.x0 - box[0]) + max(0.0, box[2] - ax_box.x1)
            cost = 30 * outside + sum(overlap(box, b) for b in obstacles)
            if cost == 0:
                choice = (dx, dy, ha, box)
                break
            if best_cost is None or cost < best_cost:
                best, best_cost = (dx, dy, ha, box), cost
        dx, dy, ha, box = choice or best
        ax.annotate(r["tag"], (r["eci"], r["ehs"]), textcoords="offset points",
                    xytext=(dx, dy), ha=ha, va="center",
                    fontsize=FS, color=INK)
        placed.append(box)

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "results", "fleet.png")
    fig.savefig(out, facecolor=SURFACE)
    print("wrote", out)


if __name__ == "__main__":
    main()
