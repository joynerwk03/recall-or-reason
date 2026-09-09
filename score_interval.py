#!/usr/bin/env python3
"""Score an interval run: coverage, width, error, and the memorisation quadrants.

This is the probe the project exists for. Multiple choice cannot distinguish a
model that knows from one that remembers, because both pick the right option.
An interval can, because the three regimes have different shapes:

    tight and right   -> looks like recall
    wide and right    -> looks like reasoning
    tight and wrong   -> looks like a bluff
    wide and wrong    -> lost, and at least honest about it

Three deliberate choices:

1. **Coverage is compared against the 80% it was asked for**, not against zero.
   An 80% interval that covers 80% of the time is perfect; one that covers 30%
   is the failure mode worth naming.

2. **Width and error are relative to the truth**, since the items span
   percentages and raw counts. Absolute width would let one count-valued item
   dominate every percentage item. Denominator is max(|truth|, 1) so that items
   whose true answer is zero do not divide by it.

3. **Incoherent answers are counted, not dropped.** An estimate outside the
   model's own interval is a real observation about whether the numbers mean
   anything to it.

  ./run.sh score_interval.py results/<run>-interval.jsonl
"""
import json
import math
import statistics
import sys

TARGET = 0.80


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - m), min(1.0, c + m)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    rows = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8")]
    if not rows:
        sys.exit("empty run file")

    model = rows[0].get("model", "?")
    usable = [r for r in rows
              if r.get("estimate") is not None
              and r.get("low") is not None and r.get("high") is not None]
    unparsed = len(rows) - len(usable)

    print(f"model        {model}")
    print(f"items        {len(rows)}  (usable {len(usable)}, unparseable {unparsed})")
    if not usable:
        print("\nnothing scoreable.")
        return

    for r in usable:
        denom = max(abs(r["truth"]), 1.0)
        r["_relerr"] = abs(r["estimate"] - r["truth"]) / denom
        r["_relwidth"] = (r["high"] - r["low"]) / denom
        r["_coherent"] = r["low"] <= r["estimate"] <= r["high"]

    n = len(usable)
    cov = sum(1 for r in usable if r["covered"])
    lo, hi = wilson(cov, n)
    print(f"\ncoverage     {cov}/{n} = {100*cov/n:.1f}%  95% CI "
          f"[{100*lo:.1f}, {100*hi:.1f}]")
    print(f"             asked for {int(TARGET*100)}%, so this is "
          f"{'about right' if lo <= TARGET <= hi else 'OVERCONFIDENT' if cov/n < TARGET else 'underconfident'}")

    widths = sorted(r["_relwidth"] for r in usable)
    errs = sorted(r["_relerr"] for r in usable)
    print(f"\nrelative width   median {statistics.median(widths):.2f}  "
          f"(interval span as a multiple of the true value)")
    print(f"relative error   median {statistics.median(errs):.2f}")

    incoherent = [r for r in usable if not r["_coherent"]]
    print(f"\nincoherent       {len(incoherent)}/{n} answers put their own estimate "
          f"outside their own interval")
    if incoherent:
        print("                 " + ", ".join(r["id"] for r in incoherent[:6])
              + (" …" if len(incoherent) > 6 else ""))

    # ---- the quadrants ----
    mw = statistics.median(widths)
    me = statistics.median(errs)
    quad = {"tight & right": [], "wide & right": [],
            "tight & wrong": [], "wide & wrong": []}
    for r in usable:
        tight = r["_relwidth"] <= mw
        right = r["_relerr"] <= me
        key = ("tight " if tight else "wide ") + "& " + ("right" if right else "wrong")
        quad[key].append(r["id"])

    print(f"\nmemorisation quadrants  (split at the medians: width {mw:.2f}, error {me:.2f})")
    reading = {
        "tight & right": "looks like recall",
        "wide & right": "looks like reasoning",
        "tight & wrong": "looks like a bluff",
        "wide & wrong": "lost, but honest about it",
    }
    for k in ("tight & right", "wide & right", "tight & wrong", "wide & wrong"):
        print(f"  {k:<14} {len(quad[k]):>3}   {reading[k]}")

    print("\n  ⚠ The split is at this run's own medians, so the four counts are")
    print("    relative to each other by construction and cannot be compared")
    print("    across models. What compares across models is coverage, median")
    print("    width, and median error.")


if __name__ == "__main__":
    main()
