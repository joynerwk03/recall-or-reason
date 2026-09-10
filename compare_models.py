#!/usr/bin/env python3
"""Compare two models on the perturbed variants, using the one measure that survives.

The median gap is the natural headline and it is nearly useless for comparing
models, because it is only defined on pairs where the model got the ORIGINAL
right. A model that is wrong everywhere contributes almost no eligible pairs —
lfm2 contributes one — so the gap cannot separate "robust to perturbation" from
"too inaccurate to test".

**Anchor echo does not have that problem.** An answer is an echo when the
estimate lands closer to a figure the model was already holding (the answer to
the unperturbed question, or a number quoted in the prompt) than to the truth.
It is defined on every item regardless of baseline accuracy, it is scale-free,
and it asks the question the benchmark exists to ask: did the model answer the
question in front of it, or the one it remembered?

Fisher's exact test, because n is 8 per model and a chi-square would be lying.

  ./run.sh compare_models.py <modelA-variants.jsonl> <modelB-variants.jsonl>
"""
import json
import sys
from math import comb


def fisher_two_tailed(a, b, c, d):
    """Two-tailed Fisher exact p for [[a,b],[c,d]], by summing tables no more
    likely than the observed one. Exact arithmetic, no scipy."""
    n = a + b + c + d
    r1, c1 = a + b, a + c

    def prob(x):
        if x < 0 or x > min(r1, c1) or (r1 - x) < 0 or (c1 - x) < 0:
            return 0.0
        if (n - r1 - c1 + x) < 0:
            return 0.0
        return (comb(c1, x) * comb(n - c1, r1 - x)) / comb(n, r1)

    obs = prob(a)
    return min(1.0, sum(p for x in range(0, min(r1, c1) + 1)
                        if (p := prob(x)) <= obs + 1e-12))


def echoes(path):
    model, hits, total, detail = None, 0, 0, []
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        model = r.get("model", model)
        if r.get("kind") == "null-control" or r.get("estimate") is None:
            continue
        total += 1
        est, truth = r["estimate"], r["truth"]
        why = []
        for key, label in (("original_answer", "original answer"),
                           ("prompt_anchor", "prompt anchor")):
            v = r.get(key)
            if v is not None and abs(est - v) < abs(est - truth):
                why.append(label)
        if why:
            hits += 1
            detail.append((r["id"], est, truth, " + ".join(why)))
    return model, hits, total, detail


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    A = echoes(sys.argv[1])
    B = echoes(sys.argv[2])

    for model, hits, total, detail in (A, B):
        print(f"{model:<14} anchor echoes {hits}/{total}")
        for i, est, truth, why in detail:
            print(f"                 {i:<26} said {est:g}, truth {truth:g}  ({why})")

    a, b = A[1], A[2] - A[1]
    c, d = B[1], B[2] - B[1]
    p = fisher_two_tailed(a, b, c, d)
    print(f"\nFisher exact     p = {p:.4f}  ({A[0]} {a}/{A[2]} vs {B[0]} {c}/{B[2]})")
    if p < 0.05:
        print("                 The two models differ in how often they answer with a")
        print("                 figure they were already holding. This is the one")
        print("                 cross-model claim in the perturbation experiment that")
        print("                 does not depend on either model's baseline accuracy.")
    else:
        print("                 Not separable at this n. Report the counts, not a verdict.")
    print(f"\n  ⚠ n = {A[2]} per model. A two-tailed exact test on a 2x2 this small")
    print("    detects only large differences, and a p below .05 here is one")
    print("    experiment, not a replication.")


if __name__ == "__main__":
    main()
