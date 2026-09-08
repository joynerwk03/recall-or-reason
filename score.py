#!/usr/bin/env python3
"""Score a run: accuracy against the right baseline, calibration, and skew.

Three deliberate choices, each because the obvious alternative would mislead:

1. **Chance is computed per item, not assumed.** Items have three or four
   options, so a flat 25% baseline would understate chance and flatter the
   model. The baseline here is the mean of 1/n_options over the items actually
   scored.

2. **Unparseable answers are reported, never silently dropped or counted
   wrong.** A model that fails to follow the format is telling you something
   different from a model that answers incorrectly, and folding them together
   loses that.

3. **The skew table is a diagnostic, never a target.** It shows whether errors
   correlate with the worldview each finding contradicts. It is not a score to
   optimise, and a lopsided result is a prompt to ask what was never asked, not
   a defect to even out. See `context/balance-is-not-a-target` in mission-control.

  ./run.sh score.py results/<run>.jsonl
"""
import json
import math
import sys
from collections import defaultdict


def wilson(k, n, z=1.96):
    """Wilson interval. At these sample sizes the normal approximation is not
    good enough to quote, and quoting a bare point estimate off 80 items would
    repeat the mistake ConceptChess spent a session learning."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - m), min(1.0, c + m))


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    rows = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8")]
    if not rows:
        sys.exit("empty run file")

    model = rows[0].get("model", "?")
    scored = [r for r in rows if r.get("choice") is not None]
    unparsed = [r for r in rows if r.get("choice") is None]
    errors = [r for r in rows if r.get("error")]

    n = len(scored)
    k = sum(1 for r in scored if r["correct"])
    chance = sum(1.0 / r["n_options"] for r in scored) / n if n else 0.0
    lo, hi = wilson(k, n)

    print(f"model            {model}")
    print(f"items            {len(rows)}  (scored {n}, unparseable {len(unparsed)}, "
          f"errored {len(errors)})")
    if not n:
        print("\nnothing scoreable — check the raw field in the run file.")
        return
    print(f"accuracy         {k}/{n} = {100*k/n:.1f}%  95% CI "
          f"[{100*lo:.1f}, {100*hi:.1f}]")
    print(f"chance baseline  {100*chance:.1f}%  (per-item, options vary)")
    verdict = ("above chance" if lo > chance else
               "NOT distinguishable from chance" if hi > chance else "below chance")
    print(f"verdict          {verdict}")

    # ---- calibration ----
    conf = [r for r in scored if r.get("confidence") is not None]
    print(f"\ncalibration      {len(conf)}/{n} answers carried a confidence")
    if conf:
        bins = defaultdict(list)
        for r in conf:
            bins[min(9, int(r["confidence"] // 10))].append(bool(r["correct"]))
        ece = 0.0
        print("  bin        n   stated   actual")
        for b in sorted(bins):
            vals = bins[b]
            stated = (b * 10 + 5) / 100
            actual = sum(vals) / len(vals)
            ece += (len(vals) / len(conf)) * abs(stated - actual)
            print(f"  {b*10:>3}-{b*10+9:<3} {len(vals):>4}   "
                  f"{100*stated:>5.0f}%   {100*actual:>5.0f}%")
        print(f"  ECE {ece:.3f}   (0 = perfectly calibrated)")
        spread = max(r["confidence"] for r in conf) - min(r["confidence"] for r in conf)
        if spread <= 5:
            print("  ⚠ confidence is essentially constant, so it carries no "
                  "information. A model that says 85 every time is not "
                  "expressing uncertainty, and ECE is not meaningful here.")

    # ---- skew ----
    print("\nskew by the prior each finding contradicts")
    print("  (a diagnostic, never a target)")
    by = defaultdict(lambda: [0, 0])
    for r in scored:
        t = r.get("punctures") or "(untagged)"
        by[t][1] += 1
        by[t][0] += 1 if r["correct"] else 0
    for tag in sorted(by, key=lambda t: -by[t][1]):
        c, tot = by[tag]
        blo, bhi = wilson(c, tot)
        print(f"  {tag:<16} {c:>3}/{tot:<3} = {100*c/tot:>5.1f}%  "
              f"[{100*blo:.0f}, {100*bhi:.0f}]")
    print("\n  Intervals this wide at this item count cannot separate the "
          "groups.\n  Treat any apparent skew as unmeasured until the "
          "counts are much larger.")

    if unparsed:
        print(f"\nunparseable ids: {', '.join(r['id'] for r in unparsed[:8])}"
              + (" …" if len(unparsed) > 8 else ""))


if __name__ == "__main__":
    main()
