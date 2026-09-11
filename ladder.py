#!/usr/bin/env python3
"""Within-family size ladders: does the honesty score move with scale when the
training recipe is held roughly fixed?

The fleet-wide comparison (compare_capability.py) mixes labs, recipes and
generations, so where a model sits on the capability axis is tangled up with
who trained it and how. Two families in the fleet were pulled at three sizes of
one generation, which removes most of that confound:

  Gemma 3   4.3B, 12.2B, 27.4B
  Qwen3     8.2B, 14.8B, 32.8B

Parameter counts are from `ollama show` (2026-09-11), never the on-disk size.

Three points per family support no statistical claim, and this script makes
none. It reports each family in size order, whether each measure rises or falls
monotonically with size, and whether adjacent sizes are separated by more than
their own repeat-run spread. It is a description, and gets quoted as one.

Left out on purpose, because they are not ladders: Gemma 4 26B against 31B (a
mixture-of-experts with about 4B active parameters against a dense model),
Qwen3.6 35B-A3B against 27B (the same split), and Llama 3.2 1B against Llama
3.1 8B (two generations, and the 1B fails the parse rule).

  ./run.sh ladder.py results/fleet.json [--json results/ladder.json]
"""
import argparse
import json

FAMILIES = {
    "Gemma 3": [("gemma3:4b", 4.3), ("gemma3:12b", 12.2), ("gemma3:27b", 27.4)],
    "Qwen3": [("qwen3:8b", 8.2), ("qwen3:14b", 14.8), ("qwen3:32b", 32.8)],
}
MEASURES = ("ehs", "calibration", "honesty", "discrimination", "independence")


def direction(vals):
    if any(v is None for v in vals):
        return "incomplete"
    steps = [b - a for a, b in zip(vals, vals[1:])]
    if all(s > 0 for s in steps):
        return "rises with size"
    if all(s < 0 for s in steps):
        return "falls with size"
    return "no consistent direction"


def separated(a, b):
    """True when the repeat ranges of two models do not overlap; None when
    either has only one complete run, so there is no spread to compare."""
    if a.get("n_reps", 1) < 2 or b.get("n_reps", 1) < 2:
        return None
    return a["ehs_hi"] < b["ehs_lo"] or b["ehs_hi"] < a["ehs_lo"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fleet", help="results/fleet.json from compare_capability.py")
    ap.add_argument("--json", help="also write the ladders here")
    a = ap.parse_args()

    d = json.load(open(a.fleet, encoding="utf-8"))
    by_tag = {r["tag"]: r for r in d.get("rows", [])}
    excluded = {r["tag"] for r in d.get("excluded", [])}

    out = {}
    for fam, members in FAMILIES.items():
        print(f"\n{fam}")
        print(f"  {'model':<12}{'params':>8}{'ECI':>7}{'EHS':>7}{'range':>10}"
              f"{'cal':>6}{'hon':>6}{'disc':>6}{'ind':>6}")
        rows = []
        for tag, size in members:
            r = by_tag.get(tag)
            if r is None:
                why = "excluded" if tag in excluded else "no complete run"
                print(f"  {tag:<12}{size:>7.1f}B   ({why})")
                rows.append(None)
                continue
            spread = (f"[{r['ehs_lo']:.0f},{r['ehs_hi']:.0f}]"
                      if r.get("n_reps", 1) > 1 else "single")
            comps = "".join(f"{r[k]:>6.0f}" if r.get(k) is not None else f"{'-':>6}"
                            for k in MEASURES[1:])
            print(f"  {tag:<12}{size:>7.1f}B{r['eci']:>7.1f}{r['ehs']:>7.1f}"
                  f"{spread:>10}{comps}")
            rows.append(r)

        fam_out = {"members": [t for t, _ in members],
                   "params_b": [s for _, s in members], "complete": all(rows)}
        if all(rows):
            print()
            for k in MEASURES:
                vals = [r.get(k) for r in rows]
                fam_out[k] = {"values": vals, "direction": direction(vals)}
                print(f"    {k:<16}{direction(vals)}")
            seps = [separated(x, y) for x, y in zip(rows, rows[1:])]
            fam_out["ehs_adjacent_separated"] = seps
            words = ["yes" if s else ("no" if s is not None else "n/a, single run")
                     for s in seps]
            print(f"    EHS gap between adjacent sizes larger than repeat spread: "
                  f"{', '.join(words)}")
        out[fam] = fam_out

    print("\n  Three sizes per family: a description, not a test.")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)
        print(f"  wrote {a.json}")


if __name__ == "__main__":
    main()
