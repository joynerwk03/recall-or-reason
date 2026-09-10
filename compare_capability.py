#!/usr/bin/env python3
"""Join Epistemic Honesty Score against the Epoch Capabilities Index.

The question: **is knowing what you don't know just another face of being
smart, or is it a separate axis?**

If EHS tracks ECI closely, this benchmark is measuring general capability by a
more expensive route and does not need to exist. If it doesn't, then a model's
epistemic honesty is not predictable from its leaderboard position, which is
worth knowing before anyone reads a confidence number off a model and acts on it.

Design notes that matter for reading the output:

* **EHS deliberately contains no accuracy term.** Any correlation found here is
  discovered, not built in. See `epistemic_score.py`.
* **n is the number of models, not the number of questions.** Ten models is a
  small sample for a correlation, so the p-value comes from an exact permutation
  test rather than a normal approximation, and the interval is wide no matter
  what the point estimate says.
* **Models without an ECI score are excluded from the correlation and reported
  separately.** They are not plotted at zero and not dropped silently.
* **Models whose runs failed validity checks are excluded from the correlation**
  and listed. A model that could not produce parseable answers has a meaningless
  score, not a low one.

  ./run.sh compare_capability.py             # table
  ./run.sh compare_capability.py --json OUT  # write data for the dashboard
"""
import argparse
import csv
import glob
import json
import math
import os
import random
import re
import subprocess
import sys

# Pin names that are the same weights as a canonical entry and would otherwise
# appear twice. devstral-t0 was the first pin of devstral-small-2, built before
# num_predict was set; its results are still cited in the paper, so the files
# stay, but it is not a second model.
SUPERSEDED = {"devstral-t0": "devstral-small-2-t0"}

HERE = os.path.dirname(os.path.abspath(__file__))
ECI = os.path.join(HERE, "data", "eci.csv")
RESULTS = os.path.join(HERE, "results")


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
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else None


def perm_p(xs, ys, trials=200000, seed=0):
    """Two-tailed permutation p for a rank correlation.

    With ten models the normal approximation for Spearman is not trustworthy,
    and shuffling one axis is both exact in spirit and easy to explain.
    """
    obs = spearman(xs, ys)
    if obs is None:
        return None
    rng = random.Random(seed)
    y = list(ys)
    hits = 0
    for _ in range(trials):
        rng.shuffle(y)
        r = spearman(xs, y)
        if r is not None and abs(r) >= abs(obs) - 1e-12:
            hits += 1
    return (hits + 1) / (trials + 1)


# Strict filename matching, not loose globbing. Result files are
# <model>-<stamp>[-<tag>][-interval].jsonl, and a tagged run — a repeatability
# check, an ablation — must never be mistaken for the canonical run for a model.
# A loose glob would have silently picked up a `-repeat-interval` file as *the*
# interval result and no error would have appeared anywhere.
PAT = {
    "choice":   re.compile(r"^(?P<m>.+)-\d{8}-\d{6}\.jsonl$"),
    "interval": re.compile(r"^(?P<m>.+)-\d{8}-\d{6}-interval\.jsonl$"),
    "variants": re.compile(r"^(?P<m>.+)-\d{8}-\d{6}-variants-interval\.jsonl$"),
}


def newest(model, kind):
    pat = PAT[kind]
    c = []
    for p in glob.glob(os.path.join(RESULTS, "*.jsonl")):
        m = pat.match(os.path.basename(p))
        if m and m.group("m") == model:
            c.append(p)
    return max(c, key=os.path.getmtime) if c else None


def score_model(model):
    args = [sys.executable, os.path.join(HERE, "epistemic_score.py"),
            "--model", model, "--json"]
    for kind, flag in (("choice", "--choice"), ("interval", "--interval"),
                       ("variants", "--variants")):
        p = newest(model, kind)
        if p:
            args += [flag, p]
    out = subprocess.run(args, capture_output=True, text=True)
    if out.returncode != 0 or not out.stdout.strip():
        return None
    return json.loads(out.stdout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write joined rows here for the dashboard")
    a = ap.parse_args()

    eci = {}
    with open(ECI, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            eci[r["ollama_tag"]] = r

    # ollama tag -> the -t0 model name the sweep produced
    def pinned(tag):
        return tag.replace(":latest", "").replace(":", "-").replace(".", "-") + "-t0"

    rows, no_eci, invalid = [], [], []
    seen = set()
    for tag, e in eci.items():
        m = pinned(tag)
        seen.add(m)
        s = score_model(m)
        if s is None or s.get("ehs") is None:
            continue
        s["eci"] = float(e["eci"])
        s["eci_lo"] = float(e["eci_ci_low"])
        s["eci_hi"] = float(e["eci_ci_high"])
        s["eci_name"] = e["eci_name"]
        s["org"] = e["org"]
        s["tag"] = tag
        blocking = [f for f in s["flags"] if "unreliable" in f]
        (invalid if blocking else rows).append(s)

    # models we ran that ECI does not cover
    for p in sorted(glob.glob(os.path.join(RESULTS, "*-t0-*.jsonl"))):
        m = os.path.basename(p).split("-20")[0]
        if m in seen or m in SUPERSEDED or any(x["model"] == m for x in no_eci):
            continue
        s = score_model(m)
        if s and s.get("ehs") is not None:
            s["tag"] = m
            no_eci.append(s)

    rows.sort(key=lambda r: r["eci"])

    w = 22
    print(f"{'model':<{w}}{'ECI':>8}{'EHS':>7}{'calib':>7}{'hon':>7}"
          f"{'disc':>7}{'indep':>7}   flags")
    print("-" * (w + 43 + 8))
    for r in rows:
        print(f"{r['tag']:<{w}}{r['eci']:>8.1f}{r['ehs']:>7.1f}"
              f"{r['calibration'] or 0:>7.0f}{r['honesty'] or 0:>7.0f}"
              f"{r['discrimination'] or 0:>7.0f}{r['independence'] or 0:>7.0f}"
              f"   {'; '.join(r['flags'])[:44]}")

    if no_eci:
        print(f"\nrun but not in the ECI table (excluded from the correlation):")
        for r in no_eci:
            print(f"  {r['tag']:<{w}}{'—':>8}{r['ehs']:>7.1f}")
    if invalid:
        print(f"\nexcluded — runs failed validity checks:")
        for r in invalid:
            print(f"  {r['tag']:<{w}}  {'; '.join(r['flags'])}")

    if len(rows) >= 3:
        xs = [r["eci"] for r in rows]
        ys = [r["ehs"] for r in rows]
        rho = spearman(xs, ys)
        p = perm_p(xs, ys)
        print(f"\nEHS vs ECI       Spearman rho = {rho:+.3f}   "
              f"permutation p = {p:.4f}   n = {len(rows)} models")
        if p is not None and p < 0.05:
            print("                 Epistemic honesty tracks general capability on")
            print("                 this sample: the leaderboard largely predicts it.")
        else:
            print("                 **Not separable from chance at this n.** Position on")
            print("                 a general capability index does not predict how")
            print("                 honestly a model reports its own uncertainty here.")
        print(f"\n  ⚠ n = {len(rows)} models. A rank correlation on ten points has a very")
        print("    wide interval whichever way it lands, and ECI itself carries")
        print("    confidence intervals several points wide. Treat the direction as")
        print("    a hypothesis, not a measurement.")

        # per-component, since the composite can hide opposing movements
        print("\n  per component vs ECI:")
        for k in ("calibration", "honesty", "discrimination", "independence"):
            v = [r[k] for r in rows]
            if all(x is not None for x in v):
                rr = spearman(xs, v)
                pp = perm_p(xs, v, trials=50000)
                print(f"    {k:<16} rho {rr:+.3f}   p {pp:.3f}")

    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump({"rows": rows, "no_eci": no_eci, "invalid": invalid,
                       "rho": spearman([r["eci"] for r in rows],
                                       [r["ehs"] for r in rows]) if len(rows) >= 3 else None,
                       "p": perm_p([r["eci"] for r in rows],
                                   [r["ehs"] for r in rows]) if len(rows) >= 3 else None},
                      fh, indent=1)
        print(f"\nwrote {a.json}")


if __name__ == "__main__":
    main()
