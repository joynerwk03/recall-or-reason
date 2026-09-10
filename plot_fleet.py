#!/usr/bin/env python3
"""Epistemic Honesty Score against the Epoch Capabilities Index, one point per model.

Form: a scatter, because the question is whether two continuous measures move
together across a set of named entities. Ten points is few enough that every one
is directly labelled, so identity never depends on colour and no legend is
needed — this is one series, not ten.

Two things are drawn that a plain scatter would leave out, both because omitting
them would overstate the result:

* **Horizontal whiskers are Epoch's own ECI confidence intervals.** Several are
  more than ten points wide. Drawing the x-position as a dot alone would imply a
  precision the capability axis does not have.
* **The grey band is this harness's own run-to-run noise** on the composite
  score, measured by repeating runs rather than assumed. Vertical differences
  smaller than the band are not differences between models.

  ./run.sh plot_fleet.py fleet.json
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

INK, MUTED, GRID, SURFACE = "#1c1f26", "#6a7280", "#e4e7ec", "#fcfcfb"
ACCENT, NOISE = "#1f6feb", "#8892a0"
NOISE_BAND = 2.4          # EHS points, measured (see LOG 2026-09-10)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    rows = d["rows"]
    if not rows:
        sys.exit("no scored models with an ECI score yet")
    rho, p = d.get("rho"), d.get("p")

    fig, ax = plt.subplots(figsize=(9.4, 6.4), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    ax.set_axisbelow(True)
    ax.grid(color=GRID, linewidth=0.8)

    xs = [r["eci"] for r in rows]
    ys = [r["ehs"] for r in rows]

    # noise band around the mean, as a reference height rather than per point
    mid = sum(ys) / len(ys)
    ax.axhspan(mid - NOISE_BAND / 2, mid + NOISE_BAND / 2,
               color=NOISE, alpha=0.10, zorder=1)
    ax.text(min(xs) - 1.4, mid + NOISE_BAND / 2 + 0.6,
            f"run-to-run noise, {NOISE_BAND} pts", color=MUTED, fontsize=8.5)

    for r in rows:
        ax.plot([r["eci_lo"], r["eci_hi"]], [r["ehs"], r["ehs"]],
                color=ACCENT, alpha=0.30, linewidth=1.6, zorder=3,
                solid_capstyle="round")
    ax.scatter(xs, ys, s=74, color=ACCENT, zorder=5,
               edgecolor=SURFACE, linewidth=1.6)

    # Direct labels carry identity here, so a collision is not cosmetic — it
    # makes a point unidentifiable. Models close on both axes get their label
    # flipped below the marker. gemma3:27b and phi4:14b sit 0.4 ECI points apart
    # and overlapped completely before this.
    placed = []
    for r in sorted(rows, key=lambda r: r["eci"]):
        below = any(abs(r["eci"] - px) < 3.0 and abs(r["ehs"] - py) < 9.0
                    for px, py, pb in placed if not pb)
        ax.annotate(r["tag"], (r["eci"], r["ehs"]),
                    textcoords="offset points",
                    xytext=(0, -19 if below else 11),
                    ha="center", fontsize=9, color=INK)
        placed.append((r["eci"], r["ehs"], below))

    ax.set_xlabel("Epoch Capabilities Index  —  general capability, higher is better",
                  color=MUTED, fontsize=10, labelpad=9)
    ax.set_ylabel("Epistemic Honesty Score  —  knowing what it does not know",
                  color=MUTED, fontsize=10, labelpad=9)
    ax.tick_params(colors=MUTED, labelsize=9.5, length=0)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.set_ylim(max(0, min(ys) - 12), min(100, max(ys) + 14))
    ax.set_xlim(min(xs) - 2.5, max(xs) + 2.5)

    if rho is not None and p is not None:
        verdict = ("capability predicts honesty here"
                   if p < 0.05 else "no relationship at this sample size")
        head = ("Better models are more honest about their own uncertainty"
                if p < 0.05 else
                "Being a better model does not make it more honest about "
                "its own uncertainty")
        sub = (f"Spearman rho = {rho:+.2f}, permutation p = {p:.3f}, "
               f"n = {len(rows)} models - {verdict}."
               "\nHorizontal bars are Epoch's own confidence intervals "
               "on the capability score."
               "\nThe honesty score contains no accuracy term, so any "
               "relationship here is measured, not built in.")
    else:
        head, sub = "Epistemic honesty against general capability", ""

    ax.text(0.0, 1.185, head, transform=ax.transAxes, color=INK,
            fontsize=13.5, fontweight="bold", va="bottom", ha="left")
    ax.text(0.0, 1.020, sub, transform=ax.transAxes, color=MUTED,
            fontsize=9.6, va="bottom", ha="left", linespacing=1.6)

    fig.subplots_adjust(top=0.77, left=0.085, right=0.975, bottom=0.115)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "results", "fleet.png")
    fig.savefig(out, facecolor=SURFACE)
    print("wrote", out)
    for r in sorted(rows, key=lambda r: r["eci"]):
        print(f"  {r['tag']:<20} ECI {r['eci']:6.1f}   EHS {r['ehs']:5.1f}")
    if d.get("no_eci"):
        print("  not on the capability axis (no ECI score):")
        for r in d["no_eci"]:
            print(f"    {r['tag']:<18} EHS {r['ehs']:5.1f}")


if __name__ == "__main__":
    main()
