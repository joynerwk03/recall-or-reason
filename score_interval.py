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
import random
import statistics
import sys

TARGET = 0.80


def spearman(xs, ys):
    """Rank correlation, no dependencies.

    This is the metric the quadrants only gesture at. A model with self-knowledge
    widens its interval exactly where it is about to be wrong, so width and error
    should correlate POSITIVELY. Near zero means the width is decorative: the
    model is not narrower where it is right.

    Rank-based on purpose, because relative error has a long tail and one wild
    miss would otherwise dominate a Pearson correlation.
    """
    n = len(xs)
    if n < 3:
        return None

    def rank(v):
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:                      # average ties, or ties bias the result
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    rx, ry = rank(xs), rank(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else None


def shuffle_null(usable, trials=2000, seed=0):
    """Coverage when each interval is scored against SOMEBODY ELSE'S truth.

    Coverage on its own proves nothing, because width buys it for free: a model
    answering [0, 100] to every percentage question covers 100% of the time and
    knows nothing. This is the null that separates the two. Derangement, so no
    interval is ever accidentally paired with its own item.

    Real coverage well above this null means the intervals are placed, not just
    wide. Real coverage AT this null means the model found a width that brackets
    the typical answer and applied it everywhere.
    """
    rng = random.Random(seed)
    idx = list(range(len(usable)))
    hits = 0
    for _ in range(trials):
        perm = idx[:]
        while True:                      # resample until nothing maps to itself
            rng.shuffle(perm)
            if all(p != i for i, p in enumerate(perm)):
                break
        hits += sum(1 for i, p in enumerate(perm)
                    if usable[i]["low"] <= usable[p]["truth"] <= usable[i]["high"])
    return hits / (trials * len(usable))


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
    print("    across models. The correlation below is the metric that can be.")

    null = shuffle_null(usable)
    print(f"\nshuffle null     {100*null:.1f}%  coverage when each interval is scored")
    print( "                 against a DIFFERENT item's truth")
    margin = cov / n - null
    if margin > 0.15:
        print(f"                 real coverage beats it by {100*margin:+.1f} points, so the")
        print( "                 intervals are placed, not merely wide")
    else:
        print(f"                 real coverage beats it by only {100*margin:+.1f} points — these")
        print( "                 intervals would bracket almost any answer in the set")

    # ---- self-knowledge ----
    # Raw first. Relative width and relative error share the denominator
    # max(|truth|,1), and dividing two quantities by the same number distorts
    # their correlation (Pearson's spurious correlation of ratios, 1897).
    #
    # Measured here, the distortion is large and does not have a consistent
    # sign: on the 2026-09-09 runs it pushed devstral DOWN (0.76 raw -> 0.28
    # normalised) and lfm2 UP (0.31 -> 0.50), which between them would have
    # reversed the ranking of the two models. So this is not a correction that
    # can be reasoned about and waved through — the raw pair is the only one
    # that means anything, and the normalised one is printed purely as a
    # standing reminder of how far off it can be.
    rho_raw = spearman([r["high"] - r["low"] for r in usable],
                       [abs(r["estimate"] - r["truth"]) for r in usable])
    rho_rel = spearman([r["_relwidth"] for r in usable], [r["_relerr"] for r in usable])
    rho = rho_raw
    print(f"\nself-knowledge   width vs error, Spearman rho = {rho_raw:.3f}  (raw)")
    print(f"                 {rho_rel:+.3f} on the normalised pair — reported only as a")
    print( "                 warning. Trust the raw number.")
    if rho is not None:
        if rho > 0.3:
            verdict = ("the model widens its interval where it is about to be "
                       "wrong. The width carries real information.")
        elif rho > 0.1:
            verdict = "weak but present: width tracks error a little."
        elif rho > -0.1:
            verdict = ("width is DECORATIVE. The model is no narrower where it "
                       "is right, so the interval expresses no self-knowledge "
                       "even if its coverage happens to look correct.")
        else:
            verdict = ("negative, which is worse than useless: it is narrowest "
                       "exactly where it is most wrong.")
        print(f"                 {verdict}")
        print("\n  Coverage and this correlation answer different questions.")
        print("  Coverage asks whether the intervals are the right SIZE on")
        print("  average. This asks whether they are put in the right PLACES.")
        print("  A model can pass the first and fail the second by emitting one")
        print("  habitual width for everything.")


if __name__ == "__main__":
    main()
