#!/usr/bin/env python3
"""Where the sweep stands: which models have complete runs of which kind.

Replaces check_fleet.sh, which hard-coded a twelve-model list and silently
stopped covering the fleet the moment it grew. The model list here comes from
data/eci.csv plus the models run without an ECI score, so adding a model in one
place is enough and nothing can quietly fall out of the audit.

"Complete" means have_complete.complete_file: the right number of rows for the
current item set — not a file that merely exists, which is the distinction that
once produced a retracted table.

  ./run.sh fleet_status.py            # table, with parse and truncation counts
  ./run.sh fleet_status.py --line     # one-line summary, for a monitor

Exit code 0 once every model has a complete canonical run of all three kinds.
"""
import argparse
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import have_complete as HC   # noqa: E402

EXTRA = ["devstral-small-2-t0", "lfm2-t0"]   # run, but not in the ECI table
KINDS = ("choice", "interval", "variants")
REPS = (None, "r2", "r3")


def pinned(tag):
    return tag.replace(":latest", "").replace(":", "-").replace(".", "-") + "-t0"


def fleet():
    out = []
    with open(os.path.join(HERE, "data", "eci.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out.append((pinned(r["ollama_tag"]), float(r["eci"])))
    out.sort(key=lambda t: t[1])
    return out + [(m, None) for m in EXTRA]


def parse_stats(path, kind):
    with open(path, encoding="utf-8") as fh:
        rows = [json.loads(l) for l in fh if l.strip()]
    if kind == "choice":
        ok = sum(1 for r in rows
                 if r.get("choice") is not None and r.get("confidence") is not None)
    else:
        ok = sum(1 for r in rows
                 if r.get("estimate") is not None and r.get("low") is not None)
    cut = sum(1 for r in rows if r.get("used_scratchpad") and not r.get("answer"))
    return ok, len(rows), cut


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--line", action="store_true", help="one-line summary")
    a = ap.parse_args()

    models = fleet()
    status = {m: {rep: {k: HC.complete_file(m, k, rep) for k in KINDS} for rep in REPS}
              for m, _ in models}
    n = len(models)
    done = [m for m, _ in models if all(status[m][None].values())]
    counts = {k: sum(1 for m, _ in models if status[m][None][k]) for k in KINDS}
    reps = {r: sum(1 for m, _ in models if all(status[m][r].values())) for r in ("r2", "r3")}
    all_done = len(done) == n

    if a.line:
        pending = [m[:-3] for m, _ in models if not all(status[m][None].values())]
        head = "ALL CANONICAL COMPLETE" if all_done else "canonical"
        tail = "" if all_done else " | pending: " + " ".join(pending)
        print(f"{head} | choice {counts['choice']}/{n} interval {counts['interval']}/{n} "
              f"variants {counts['variants']}/{n} | full repeats r2 {reps['r2']} "
              f"r3 {reps['r3']}{tail}")
        sys.exit(0 if all_done else 1)

    print(f"{'model':<22}{'ECI':>7}   c/i/v   {'choice parsed':<16}{'interval parsed':<18}repeats")
    print("-" * 80)
    for m, eci in models:
        st = status[m][None]
        mark = "".join("x" if st[k] else "." for k in KINDS)
        cells = []
        for k in ("choice", "interval"):
            if st[k]:
                ok, tot, cut = parse_stats(st[k], k)
                cells.append(f"{ok}/{tot}" + (f" ({cut} cut)" if cut else ""))
            else:
                cells.append("-")
        rp = " ".join(r for r in ("r2", "r3") if all(status[m][r].values())) or "-"
        e = f"{eci:7.1f}" if eci is not None else "      -"
        print(f"{m:<22}{e}   {mark:<6}  {cells[0]:<16}{cells[1]:<18}{rp}")
    print()
    print(f"canonical complete: {len(done)}/{n}   "
          f"(x = complete; '(n cut)' = answers that ran out of token budget)")
    sys.exit(0 if all_done else 1)


if __name__ == "__main__":
    main()
