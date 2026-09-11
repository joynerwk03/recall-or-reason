#!/usr/bin/env python3
"""Does <model> have a COMPLETE result file for <kind> [and repeat <rep>]?

Exit 0 and print the file name if yes; exit 1 if not.

Resume logic used to test whether a result file existed. That is not the same
question, and the difference cost a whole analysis: four runs were interrupted
partway — a killed task, two WSL teardowns — leaving files with 0, 9, 11 and 24
rows where 80, 80, 50 and 80 were expected. Every driver then saw a file, called
the unit done, and moved on. The scorer computed calibration for one model from
9 answers and honesty for another from 11 intervals, reported both to two decimal
places, and flagged nothing.

An interrupted run is not a shorter run. It is a missing run that looks present.

**Expected row counts are read from the item files at call time**, not
hard-coded. If the variant set grows, every existing variants run instantly
reads as incomplete and the driver re-runs it — which is exactly right, because a
score computed on the old set is not comparable to one on the new set.

Repeats. Run-to-run noise at temperature 0 turned out to be model-dependent — 0
of 50 items differed across three runs of gemma3:4b, 6 of 50 across two runs of
devstral — so every model gets repeat runs to put an error bar on its score.
The canonical run is repeat 1 and carries no tag. Repeats carry `r2`, `r3`, ...
and are written by run_eval.py as:

  choice    <model>-<stamp>-r2.jsonl
  interval  <model>-<stamp>-r2-interval.jsonl
  variants  <model>-<stamp>-variants-r2-interval.jsonl

Patterns are strict, so a repeat can never be mistaken for a canonical run and a
canonical run can never be counted as a repeat.

  ./run.sh have_complete.py <model> <choice|interval|variants> [r2|r3|...]
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
ITEMS = os.path.join(HERE, "data", "items.jsonl")
VARIANTS = os.path.join(HERE, "data", "variants.jsonl")

# Used only if the item files are missing, and announced when they are.
FALLBACK = {"choice": 80, "interval": 50, "variants": 9}
KINDS = ("choice", "interval", "variants")


def _rows(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def expected(kind):
    """Rows a finished run of this kind must contain, from the current items."""
    try:
        if kind == "choice":
            return len(_rows(ITEMS))
        if kind == "interval":
            return sum(1 for r in _rows(ITEMS) if r.get("numeric_answer") is not None)
        if kind == "variants":
            return len(_rows(VARIANTS))
    except OSError:
        print(f"warning: item file missing, using fallback count for {kind}",
              file=sys.stderr)
    return FALLBACK[kind]


def pattern(model, kind, rep=None):
    m = re.escape(model)
    stamp = r"-\d{8}-\d{6}"
    r = f"-{re.escape(rep)}" if rep else ""
    if kind == "choice":
        tail = r + r"\.jsonl"
    elif kind == "interval":
        tail = r + r"-interval\.jsonl"
    elif kind == "variants":
        tail = "-variants" + r + r"-interval\.jsonl"
    else:
        raise ValueError(kind)
    return re.compile("^" + m + stamp + tail + "$")


def complete_file(model, kind, rep=None):
    """Newest COMPLETE result file for this model/kind/repeat, or None."""
    if not os.path.isdir(RESULTS):
        return None
    pat, want = pattern(model, kind, rep), expected(kind)
    best, best_m = None, -1.0
    for name in os.listdir(RESULTS):
        if not pat.match(name):
            continue
        p = os.path.join(RESULTS, name)
        with open(p, encoding="utf-8") as fh:
            n = sum(1 for line in fh if line.strip())
        if n != want:
            continue
        m = os.path.getmtime(p)
        if m > best_m:
            best, best_m = p, m
    return best


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    model, kind = sys.argv[1], sys.argv[2]
    rep = sys.argv[3] if len(sys.argv) > 3 else None
    if kind not in KINDS:
        sys.exit(f"unknown kind {kind!r}")
    p = complete_file(model, kind, rep)
    if p:
        print(os.path.basename(p))
        sys.exit(0)
    sys.exit(1)


if __name__ == "__main__":
    main()
