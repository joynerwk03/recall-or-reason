#!/usr/bin/env python3
"""Join Epistemic Honesty Score against the Epoch Capabilities Index.

The question: **is knowing what you don't know just another face of being
smart, or is it a separate axis?**

If EHS tracks ECI closely, this benchmark is measuring general capability by a
more expensive route and does not need to exist. If it doesn't, a model's
epistemic honesty is not predictable from its leaderboard position — worth
knowing before anyone reads a confidence number off a model and acts on it.

What changed on 2026-09-11, and why each matters for reading the output:

* **The headline carries a bootstrap confidence interval.** The ten-model
  result was rho = +0.25 with a 95% interval of [-0.64, +0.86] — compatible
  with a strong negative and a strong positive relationship alike. It had been
  written up as "capability does not predict honesty", which the data did not
  support. A null at small n is "not detected", and the interval says so.
* **Two intervals are reported.** `sampling` resamples models only. `full` also
  draws each model's score from its repeat runs and jitters its ECI within
  Epoch's own interval, so measurement noise on BOTH axes propagates into the
  correlation instead of being assumed away.
* **Each model's score is the mean of its complete repeat runs**, with the
  min-max across repeats as its error bar. Run-to-run noise at temperature 0 is
  model-dependent, so one band drawn for every model was an extrapolation.
* **Range restriction is checked directly.** The first ten models spanned the
  bottom 22.6 points of a scale whose frontier is ~50 points higher, and
  restricting a predictor's range attenuates correlation with it. The original
  ten are re-scored beside the extended fleet so the effect is measured.
* **Files are chosen by have_complete.complete_file**, which counts rows. A
  newest-by-mtime file can be an interrupted run; that bug already produced one
  retracted table.
* **Unreliable is not pending.** A model whose runs are complete but whose
  answers mostly failed to parse is listed as excluded, with the reason — never
  folded silently into "no data yet".

EHS deliberately contains no accuracy term, so any relationship found here is
discovered, not built in. See epistemic_score.py.

  ./run.sh compare_capability.py             # report
  ./run.sh compare_capability.py --json OUT  # also write data for plot + dashboard
"""
import argparse
import csv
import json
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import epistemic_score as ES          # noqa: E402
import have_complete as HC            # noqa: E402

ECI = os.path.join(HERE, "data", "eci.csv")
REPS = [None, "r2", "r3", "r4"]
KINDS = ("choice", "interval", "variants")

# Run, but Epoch does not score them, so they cannot enter the correlation.
EXTRA = ["devstral-small-2-t0", "lfm2-t0"]

# The fleet as it stood on 2026-09-10, before range extension. Kept so the
# effect of widening the capability range is measured, not asserted.
ORIGINAL_TEN = {"gemma3:4b", "llama3.1:8b", "gemma3:12b", "gemma3:27b",
                "phi4:14b", "mistral-small:24b", "qwen3:8b", "qwen3:14b",
                "qwen3:32b", "gpt-oss:20b"}

spearman = ES.spearman


def pinned(tag):
    return tag.replace(":latest", "").replace(":", "-").replace(".", "-") + "-t0"


def perm_p(xs, ys, trials=100000, seed=0):
    """Two-tailed permutation p for a rank correlation."""
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


def model_reps(model):
    """Score every COMPLETE repeat of a model. Returns (reliable, unreliable)."""
    good, bad = [], []
    for rep in REPS:
        files = {k: HC.complete_file(model, k, rep) for k in KINDS}
        if not all(files.values()):
            continue
        s = ES.score_files(model, files["choice"], files["interval"], files["variants"])
        if s.get("ehs") is None:
            continue
        s["rep"] = rep or "r1"
        (bad if any("unreliable" in f for f in s["flags"]) else good).append(s)
    return good, bad


def summarise(tag, reps):
    """Point estimate = mean over complete repeats; error bar = min..max."""
    ehs = [r["ehs"] for r in reps]
    row = {
        "tag": tag, "model": reps[0]["model"], "n_reps": len(reps),
        "ehs": round(statistics.mean(ehs), 2),
        "ehs_lo": round(min(ehs), 2), "ehs_hi": round(max(ehs), 2),
        "ehs_reps": ehs,
        "flags": sorted({f for r in reps for f in r["flags"]}),
        "truncated": sum(r["truncated"] for r in reps),
    }
    for k in ES.COMPONENTS:
        vals = [r[k] for r in reps if r[k] is not None]
        row[k] = round(statistics.mean(vals), 2) if vals else None
    return row


def jitter_eci(rng, r):
    """Draw an ECI from Epoch's own interval (split normal: the CIs are
    asymmetric, so each side gets its own spread)."""
    z = rng.gauss(0.0, 1.0)
    side = (r["eci"] - r["eci_lo"]) if z < 0 else (r["eci_hi"] - r["eci"])
    return r["eci"] + z * side / 1.96


def boot_ci(rows, full, trials=20000, seed=1):
    rng = random.Random(seed)
    n, out = len(rows), []
    for _ in range(trials):
        pick = [rows[rng.randrange(n)] for _ in range(n)]
        if full:
            xs = [jitter_eci(rng, r) for r in pick]
            ys = [rng.choice(r["ehs_reps"]) for r in pick]
        else:
            xs = [r["eci"] for r in pick]
            ys = [r["ehs"] for r in pick]
        v = spearman(xs, ys)
        if v is not None:
            out.append(v)
    out.sort()
    return out[int(0.025 * len(out))], out[int(0.975 * len(out))], out


def holm(results):
    order = sorted(results, key=lambda t: t[2])
    adj, running, n = {}, 0.0, len(order)
    for i, (k, _, p) in enumerate(order):
        running = max(running, min(1.0, p * (n - i)))
        adj[k] = running
    return adj


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write joined rows here for plot + dashboard")
    a = ap.parse_args()

    eci = {}
    with open(ECI, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            eci[r["ollama_tag"]] = r

    rows, pending, excluded = [], [], []
    for tag, e in eci.items():
        good, bad = model_reps(pinned(tag))
        if good:
            row = summarise(tag, good)
            row.update({"eci": float(e["eci"]), "eci_lo": float(e["eci_ci_low"]),
                        "eci_hi": float(e["eci_ci_high"]), "eci_name": e["eci_name"],
                        "org": e["org"], "original_ten": tag in ORIGINAL_TEN})
            rows.append(row)
        elif bad:
            xr = summarise(tag, bad)
            xr.update({"eci": float(e["eci"]), "eci_lo": float(e["eci_ci_low"]),
                       "eci_hi": float(e["eci_ci_high"]), "eci_name": e["eci_name"],
                       "original_ten": tag in ORIGINAL_TEN})
            excluded.append(xr)
        else:
            pending.append(tag)
    rows.sort(key=lambda r: r["eci"])

    no_eci = []
    for m in EXTRA:
        good, _ = model_reps(m)
        if good:
            no_eci.append(summarise(m, good))

    # ---------- table ----------
    w = 20
    print(f"{'model':<{w}}{'ECI':>7}{'EHS':>7}{'  range':>13}{'reps':>5}"
          f"{'cal':>6}{'hon':>6}{'disc':>6}{'ind':>6}")
    print("-" * (w + 56))
    for r in rows:
        rng_s = f"[{r['ehs_lo']:.0f},{r['ehs_hi']:.0f}]" if r["n_reps"] > 1 else "   single"
        print(f"{r['tag']:<{w}}{r['eci']:>7.1f}{r['ehs']:>7.1f}{rng_s:>13}"
              f"{r['n_reps']:>5}"
              + "".join(f"{(r[k] if r[k] is not None else float('nan')):>6.0f}"
                        for k in ES.COMPONENTS))
    if no_eci:
        print("\nrun but not in the ECI table (excluded from the correlation):")
        for r in no_eci:
            print(f"  {r['tag']:<{w}}  EHS {r['ehs']:5.1f}  reps {r['n_reps']}")
    if excluded:
        print("\nEXCLUDED — complete runs, but the answers cannot be trusted:")
        for r in excluded:
            print(f"  {r['tag']:<{w}}  ECI {r['eci']:5.1f}  {'; '.join(r['flags'])}")
    if pending:
        print("\nno complete run yet: " + ", ".join(pending))

    flagged = [(r["tag"], f) for r in rows for f in r["flags"]]
    if flagged:
        print("\nflags on included models:")
        for t, f in flagged:
            print(f"  {t:<{w}} {f}")

    report = {"rows": rows, "no_eci": no_eci, "pending": pending, "excluded": excluded}
    if len(rows) >= 4:
        xs = [r["eci"] for r in rows]
        ys = [r["ehs"] for r in rows]
        rho = spearman(xs, ys)
        p = perm_p(xs, ys)
        s_lo, s_hi, _ = boot_ci(rows, full=False)
        f_lo, f_hi, fdist = boot_ci(rows, full=True)
        share_strong = sum(1 for v in fdist if v > 0.5) / len(fdist)
        span = max(xs) - min(xs)
        print(f"\nEHS vs ECI   rho = {rho:+.3f}   permutation p = {p:.4f}   "
              f"n = {len(rows)} models spanning {span:.1f} ECI points")
        print(f"             95% CI, sampling only       [{s_lo:+.2f}, {s_hi:+.2f}]")
        print(f"             95% CI, full uncertainty    [{f_lo:+.2f}, {f_hi:+.2f}]"
              f"   (models + repeat noise + Epoch's own ECI intervals)")
        print(f"             draws with rho > +0.5: {share_strong:.0%}")
        if f_lo > 0:
            verdict = "capability predicts honesty: the interval excludes zero"
        elif f_hi < 0:
            verdict = "capability predicts LESS honesty: the interval excludes zero"
        elif f_hi - f_lo > 1.0:
            verdict = ("NOT DETECTED, and the interval is too wide to call it absent. "
                       "This sample cannot say whether capability predicts honesty.")
        else:
            verdict = "no relationship detected; the interval is narrow enough to bound it"
        print(f"             {verdict}")
        report.update({"rho": rho, "p": p, "ci_sampling": [s_lo, s_hi],
                       "ci_full": [f_lo, f_hi], "share_rho_gt_half": share_strong,
                       "span": span, "verdict": verdict})

        orig = [r for r in rows if r["original_ten"]]
        if 4 <= len(orig) < len(rows):
            ro = spearman([r["eci"] for r in orig], [r["ehs"] for r in orig])
            o_span = max(r["eci"] for r in orig) - min(r["eci"] for r in orig)
            print(f"\nrange check  original {len(orig)} models ({o_span:.1f} ECI points): "
                  f"rho {ro:+.3f}")
            print(f"             extended {len(rows)} models ({span:.1f} ECI points): "
                  f"rho {rho:+.3f}")
            report.update({"rho_original": ro, "span_original": o_span,
                           "n_original": len(orig)})

        print("\nper component vs ECI (Holm-corrected across the four):")
        comp = []
        for k in ES.COMPONENTS:
            v = [r[k] for r in rows]
            if all(x is not None for x in v):
                comp.append((k, spearman(xs, v), perm_p(xs, v, trials=40000)))
        adj = holm(comp)
        for k, rr, pp in comp:
            star = "  *" if adj[k] < 0.05 else ""
            print(f"    {k:<16} rho {rr:+.3f}   p {pp:.3f}   Holm {adj[k]:.3f}{star}")
        report["components"] = [{"k": k, "rho": rr, "p": pp, "holm": adj[k]}
                                for k, rr, pp in comp]

        print("\nsensitivity to the weighting of the composite:")
        sens = []
        for name, wts in ES.WEIGHTINGS.items():
            alt = [ES.combine(tuple(r[k] for k in ES.COMPONENTS), wts) for r in rows]
            if all(x is not None for x in alt):
                rr = spearman(xs, alt)
                pp = perm_p(xs, alt, trials=40000)
                sens.append({"w": name, "rho": rr, "p": pp})
                print(f"    {name:<22} rho {rr:+.3f}   p {pp:.3f}")
        report["sensitivity"] = sens

        # The exclusion rule was fixed before the re-runs finished (LOG
        # 2026-09-11). Putting the excluded models back shows whether the rule
        # drives the answer. Their unparseable items are already dropped.
        if excluded:
            plus = rows + excluded
            rp = spearman([r["eci"] for r in plus], [r["ehs"] for r in plus])
            print()
            print(f"robustness   with the {len(excluded)} excluded model(s) put back: "
                  f"rho {rp:+.3f}, n = {len(plus)}")
            print("             the exclusion rule was fixed in advance; this shows")
            print("             whether it is what drives the answer")
            report["rho_with_excluded"] = rp

        print(f"\n  ⚠ n = {len(rows)} models. Read the full-uncertainty interval, not")
        print("    the point estimate. A null that wide is an absence of evidence.")

    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=1)
        print(f"\nwrote {a.json}")


if __name__ == "__main__":
    main()
