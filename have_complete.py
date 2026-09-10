#!/usr/bin/env python3
"""Does <model> have a COMPLETE result file for <kind>? Exit 0 if yes.

Resume logic used to test whether a result file existed. That is not the same
question, and the difference cost a whole analysis: four runs were interrupted
partway — a killed task, two WSL teardowns — leaving files with 0, 9, 11 and 24
rows where 80, 80, 50 and 80 were expected. Every driver then saw a file, called
the unit done, and moved on. The scorer computed calibration for one model from
9 answers and honesty for another from 11 intervals, reported both to two decimal
places, and flagged nothing.

An interrupted run is not a shorter run. It is a missing run that looks present.

  ./run.sh have_complete.py <model> <choice|interval|variants>
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")

# rows a finished run must have: the full bank, the numeric subset, the variants
EXPECTED = {"choice": 80, "interval": 50, "variants": 9}
SUFFIX = {"choice": "", "interval": "-interval", "variants": "-variants-interval"}


def complete_file(model, kind):
    """Newest complete result file for this model+kind, or None."""
    pat = re.compile(r"^" + re.escape(model) + r"-\d{8}-\d{6}"
                     + re.escape(SUFFIX[kind]) + r"\.jsonl$")
    best, best_m = None, -1
    for name in os.listdir(RESULTS) if os.path.isdir(RESULTS) else []:
        if not pat.match(name):
            continue
        p = os.path.join(RESULTS, name)
        with open(p, encoding="utf-8") as fh:
            n = sum(1 for line in fh if line.strip())
        if n != EXPECTED[kind]:
            continue
        m = os.path.getmtime(p)
        if m > best_m:
            best, best_m = p, m
    return best


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    model, kind = sys.argv[1], sys.argv[2]
    if kind not in EXPECTED:
        sys.exit(f"unknown kind {kind!r}")
    p = complete_file(model, kind)
    if p:
        print(os.path.basename(p))
        sys.exit(0)
    sys.exit(1)


if __name__ == "__main__":
    main()
