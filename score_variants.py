#!/usr/bin/env python3
"""Score a perturbed-variant run against the same model's run on the originals.

The headline number is the **gap**: relative error on the perturbed question
minus relative error on the original. Memorisation predicts a large positive
gap. Reasoning predicts roughly zero. That is the whole experiment.

Two things make the gap readable rather than suggestive:

**The null control.** One variant is built so the true answer barely moves
(`plastic-recycling@us`). Error there measures what the rewording alone costs.
If the control is also damaged, the gap on the real variants cannot be
attributed to needing a different fact, and this script says so instead of
reporting a headline.

**Echo detection.** A wrong answer is more informative than its size. Two
distinct failures produce similar errors and mean different things:

  original-answer echo  the model answered the UNPERTURBED question — the
                        signature of recalling one memorised figure
  prompt-anchor echo    the model repeated a number handed to it in the prompt
                        ("in 1965 the ratio was 21x" -> answers 21) — available
                        with no recall at all, and the weaker failure

Both are scored as "closer to the anchor than to the truth", which is scale-free
and needs no threshold.

  ./run.sh score_variants.py <variants-run.jsonl> <originals-run.jsonl>
"""
import json
import statistics
import sys

# Relative error on the ORIGINAL below which a pair counts toward the gap.
BASELINE_OK = 0.15


def rel(est, truth):
    return abs(est - truth) / max(abs(truth), 1.0)


def load(path):
    out = {}
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        if r.get("estimate") is None:
            continue
        lo, hi = r.get("low"), r.get("high")
        # An estimate sitting outside its own interval means the answer was
        # malformed, and its point estimate is not a measurement. This matters
        # more than it sounds: lfm2 answered the original plastics item with the
        # bare triple "9 / 90 / 100", which the parser reads as estimate 9 with
        # interval [90, 100]. The truth is 9, so that garbled answer scored a
        # PERFECT baseline error of 0.00 — and the gap against it then read as
        # the model being destroyed by a rewording. Counting these manufactures
        # both spurious accuracy and spurious degradation.
        r["_coherent"] = (lo is not None and hi is not None
                          and lo <= r["estimate"] <= hi)
        out[r["id"]] = r
    return out


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    var = load(sys.argv[1])
    orig = load(sys.argv[2])
    if not var:
        sys.exit("no parseable rows in the variants run")

    model = next(iter(var.values())).get("model", "?")
    print(f"model        {model}")

    rows = []
    for vid, v in var.items():
        base = v.get("base_id")
        o = orig.get(base)
        if o is None:
            print(f"  ! {vid}: no run for base item {base}, skipped")
            continue
        rows.append(dict(
            id=vid, kind=v.get("kind", "?"),
            e_var=rel(v["estimate"], v["truth"]),
            e_orig=rel(o["estimate"], o["truth"]),
            est=v["estimate"], truth=v["truth"],
            coh=bool(v["_coherent"]) and bool(o["_coherent"]),
            orig_ans=v.get("original_answer"),
            anchor=v.get("prompt_anchor"),
            covered=bool(v.get("covered")),
        ))
    if not rows:
        sys.exit("nothing paired; are these the same model?")

    for r in rows:
        r["gap"] = r["e_var"] - r["e_orig"]
        # Echo tests: is the estimate closer to an anchor than to the truth?
        # Meaningless on the null control, where the original answer and the
        # truth are the same number by construction, so every answer is
        # trivially "close to the original". Suppressed rather than reported.
        live = r["kind"] != "null-control"
        r["echo_orig"] = (live and r["orig_ans"] is not None
                          and abs(r["est"] - r["orig_ans"]) < abs(r["est"] - r["truth"]))
        r["echo_prompt"] = (live and r["anchor"] is not None
                            and abs(r["est"] - r["anchor"]) < abs(r["est"] - r["truth"]))

    real = [r for r in rows if r["kind"] != "null-control"]
    ctrl = [r for r in rows if r["kind"] == "null-control"]

    # Only pairs where the model got the ORIGINAL roughly right can say anything
    # about degradation. This is not a nicety — without it the metric inverts.
    # A model that was already 94% wrong on the original has no room to get
    # worse, so its gap comes out near zero or negative and reads as "robust"
    # when it is simply bad everywhere. On the 2026-09-09 run that ceiling
    # effect made lfm2 look untouched by the perturbation while it was in fact
    # failing every item it had previously got right.
    elig = [r for r in real if r["e_orig"] <= BASELINE_OK and r["coh"]]
    dropped = [r for r in real if r["e_orig"] <= BASELINE_OK and not r["coh"]]

    print(f"items        {len(rows)}  ({len(real)} perturbations, "
          f"{len(ctrl)} null control)\n")

    hdr = f'  {"variant":<28}{"orig":>7}{"var":>8}{"gap":>9}   flags'
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for r in sorted(rows, key=lambda x: -x["gap"]):
        flags = []
        if r["kind"] == "null-control":
            flags.append("CONTROL")
        if r["echo_orig"]:
            flags.append("echoed the original answer")
        if r["echo_prompt"]:
            flags.append("echoed the prompt anchor")
        if not r["covered"]:
            flags.append("missed")
        if not r["coh"]:
            flags.append("MALFORMED, excluded")
        print(f'  {r["id"]:<28}{r["e_orig"]:>7.2f}{r["e_var"]:>8.2f}'
              f'{r["gap"]:>+9.2f}   {", ".join(flags)}')

    if not elig:
        print(f'\ngap          UNSCOREABLE. The model got none of the '
              f'{len(real)} originals')
        print(f'             within {BASELINE_OK:.0%}, so there is no baseline to '
              f'degrade from.')
        med, worse = None, 0
    else:
        med = statistics.median(r["gap"] for r in elig)
        worse = sum(1 for r in elig if r["gap"] > 0)
        print(f'\ngap          median {med:+.2f} relative error, '
              f'worse on {worse}/{len(elig)} perturbations')
        print(f'             counted over the {len(elig)} of {len(real)} pairs the '
              f'model got within {BASELINE_OK:.0%} on the')
        print( '             original — the rest have no baseline to degrade from '
               'and')
        print( '             would otherwise score as robust for being wrong twice')

    if dropped:
        print(f'             {len(dropped)} further pair(s) dropped as malformed: '
              + ", ".join(r["id"] for r in dropped))

    if ctrl:
        c = ctrl[0]
        print(f'control      {c["id"]}: gap {c["gap"]:+.2f}')
        if not c["coh"]:
            print("             ⚠ UNUSABLE. One side of this pair put its estimate")
            print("               outside its own interval, so the control cannot")
            print("               certify anything and the gap above is unsupported")
            print("               in either direction.")
        elif abs(c["gap"]) > 0.15:
            print("             ⚠ the control moved too. The rewording alone is")
            print("               doing damage, so the gap above CANNOT be read")
            print("               as memorisation. Fix the prompt before quoting")
            print("               any headline number from this run.")
        else:
            print("             control holds, so the gap above is about needing a")
            print("             different fact rather than about the rewording")

    ne_o = sum(1 for r in real if r["echo_orig"])
    ne_p = sum(1 for r in real if r["echo_prompt"])
    print(f'\nechoes       {ne_o}/{len(real)} closer to the original answer than '
          f'to the truth')
    print(f'             {ne_p}/{len(real)} closer to a number quoted in the prompt')

    print()
    if med is None:
        print("reading      nothing to read. The model is not accurate enough on")
        print("             the originals for a perturbation to tell us anything.")
    elif med > 0.30 and ne_o + ne_p > 0:
        print("reading      the model degrades when the question moves, and does so")
        print("             by falling back on a number it was already holding.")
        print("             That is what memorisation looks like.")
    elif med > 0.30:
        print("reading      the model degrades when the question moves, but not by")
        print("             echoing an anchor, so this looks more like the variant")
        print("             simply being harder than like recall.")
    else:
        print("reading      no meaningful degradation. On these items the model is")
        print("             tracking the year or country it was asked about rather")
        print("             than reciting one figure.")
    print("\n  ⚠ Selection caveat, and it limits every reading above: these")
    print("    variants were chosen because ONE primary source publishes the")
    print("    whole series or cross-section, which is what makes the answers")
    print("    verifiable. That same property makes the variant answers")
    print("    well-published too. A model that memorised the entire Gallup")
    print("    trend table would pass this test. It rules out reciting a single")
    print("    headline figure; it does not rule out recall.")


if __name__ == "__main__":
    main()
