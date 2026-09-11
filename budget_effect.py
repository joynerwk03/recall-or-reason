#!/usr/bin/env python3
"""How much did the 2,500-token budget distort the scores? Old runs against new.

Seven models ran out of token budget mid-thought at 2,500 tokens — qwen3.5:9b on
63% of its answers, gemma4:26b on 51%. They were re-run at 8,192, and their old
runs were kept in results/budget2500/ precisely so the distortion could be
measured rather than asserted. This measures it.

Only the three components computed identically under both budgets are compared:
calibration (choice mode), and honesty and discrimination (interval mode).
Independence is left out, because the variant set grew from 9 to 14 items
between the two runs — a difference there would mix the budget with the items.

Truncation does not just shrink the sample. It removes the answers a model
thought about longest, which are plausibly the hardest ones, so the old scores
could be biased in either direction. The sign of each change is the finding.

  ./run.sh budget_effect.py
"""
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import epistemic_score as ES   # noqa: E402
import have_complete as HC     # noqa: E402

MODELS = ["qwen3-8b-t0", "gpt-oss-20b-t0", "qwen3-5-9b-t0", "gemma4-26b-t0",
          "gemma4-31b-t0", "qwen3-6-35b-a3b-t0", "qwen3-6-27b-t0"]
OLD = os.path.join(HERE, "results", "budget2500")


def newest_complete(folder, model, kind):
    """Newest canonical file of this kind with the full row count, or None."""
    pat, want = HC.pattern(model, kind), HC.expected(kind)
    best, best_m = None, -1.0
    if not os.path.isdir(folder):
        return None
    for name in os.listdir(folder):
        if not pat.match(name):
            continue
        p = os.path.join(folder, name)
        with open(p, encoding="utf-8") as fh:
            n = sum(1 for line in fh if line.strip())
        if n == want and os.path.getmtime(p) > best_m:
            best, best_m = p, os.path.getmtime(p)
    return best


def score(model, choice, interval):
    s = ES.score_files(model, choice, interval, None)
    three = ES.combine((s["calibration"], s["honesty"], s["discrimination"]), (1, 1, 1))
    parse = min(s["choice"].get("parse_rate", 0.0), s["interval"].get("parse_rate", 0.0))
    return s, three, parse


def fmt(v):
    return f"{v:5.1f}" if v is not None else "    -"


def main():
    print(f"{'model':<21}{'cut old':>8}{'cut new':>8}   "
          f"{'calibration':>13}  {'honesty':>13}  {'discrim.':>13}  {'3-part score':>14}")
    print("-" * 100)
    deltas, rows_done = [], 0
    for m in MODELS:
        oc, oi = newest_complete(OLD, m, "choice"), newest_complete(OLD, m, "interval")
        nc, ni = HC.complete_file(m, "choice"), HC.complete_file(m, "interval")
        if not (oc and oi):
            print(f"{m:<21}  (no complete run at the old budget)")
            continue
        if not (nc and ni):
            print(f"{m:<21}  (re-run at 8,192 not complete yet)")
            continue
        so, to, po = score(m, oc, oi)
        sn, tn, pn = score(m, nc, ni)
        rows_done += 1
        cells = []
        for k in ("calibration", "honesty", "discrimination"):
            cells.append(f"{fmt(so[k])}->{fmt(sn[k])}")
        # A delta is only meaningful when all three components exist at BOTH
        # budgets. At 2,500 tokens gemma4:26b kept so few interval answers that
        # honesty and discrimination could not be computed, so its old "score"
        # was calibration alone — and differencing that against a full score
        # reported a -17.3 that was mostly the missing components.
        parts = ("calibration", "honesty", "discrimination")
        comparable = (all(so[k] is not None for k in parts)
                      and all(sn[k] is not None for k in parts))
        d = (tn - to) if comparable else None
        if d is not None:
            deltas.append(d)
        flag = ""
        if po < ES.MIN_PARSE <= pn:
            flag = "  <- unmeasurable at 2,500, measurable now"
        elif pn < ES.MIN_PARSE:
            flag = "  <- still below the parse bar at 8,192"
        # Built in two steps on purpose. The first version ended in
        # `f"..." + flag if d is not None else ""`, where the conditional binds
        # to the whole concatenation, so any row without a delta printed as a
        # blank line and the model vanished from the table without a word.
        if d is not None:
            tail = f"{fmt(to)}->{fmt(tn)} ({d:+.1f})"
        else:
            tail = f"{fmt(to)}->{fmt(tn)} (not comparable: a component is missing at one budget)"
        print(f"{m:<21}{so['truncated']:>8}{sn['truncated']:>8}   "
              f"{cells[0]:>13}  {cells[1]:>13}  {cells[2]:>13}  {tail}{flag}")

    if deltas:
        print()
        print(f"{rows_done} model(s) compared. Median change in the 3-part score: "
              f"{statistics.median(deltas):+.1f} points; largest: "
              f"{max(deltas, key=abs):+.1f}.")
        up = sum(1 for x in deltas if x > 0)
        print(f"Scores went UP with the bigger budget for {up} of {len(deltas)}. "
              "Truncated answers are dropped rather than scored wrong, so the")
        print("direction is not obvious in advance: dropping the hardest items can "
              "flatter a model, and a budget that lets it finish can expose it.")


if __name__ == "__main__":
    main()
