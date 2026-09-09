#!/usr/bin/env python3
"""Build data/variants.jsonl — perturbed counterparts to items in the main bank.

A perturbed variant asks the *same claim* about a different year, country or
subgroup, where the true answer genuinely differs. A model that reasoned its way
to the original should mostly survive the move; a model that recalled a
memorised figure should not, because the memorised figure is now wrong. The gap
between error-on-original and error-on-variant is the number this project was
set up to produce.

Rules this file exists to enforce:

1. **Every variant answer traces to a primary source, recorded inline below with
   the date it was checked.** This is invariant 1 and it is the whole reason the
   variants are hand-built rather than generated. A plausible-looking invented
   number would corrupt the ground truth and be nearly impossible to spot later.

2. **Metadata is joined from the base item, never retyped.** Category and the
   punctures tag come from `items.jsonl` at build time, so a variant cannot
   silently disagree with its original about what it is.

3. **The anchor stays, only the target moves.** Where the original prompt
   supplies a reference point ("In 1965 the ratio was 21x"), the variant keeps
   it verbatim and changes only the year being asked about. Otherwise the
   variant is a different *question*, not a perturbation, and the comparison
   means nothing.

4. **One null control is included on purpose** (`plastic-recycling@us`), where
   the perturbed answer is ~the same as the original. It separates two failure
   modes that otherwise look identical: a model thrown by needing a *different
   fact*, versus one thrown merely by the question being *reworded*. If error
   rises on the control too, the gap on the real variants cannot be read as
   memorisation.

Rejected, and why — kept here because a rejection is a result:

- **extreme-poverty.** Its prompt states "In 1990, about 36% of humanity lived
  in extreme poverty (under $3.00/day)". The World Bank series for that exact
  line ($3.00, 2021 PPP) puts 1990 at **43.4%**; 36.2% is its figure for **2000**.
  The item's own answer (~10%) does match 2024 (10.4%), so the item appears to
  pair a current answer with an anchor from an older vintage or a different
  line. That is a ground-truth problem in the bank rather than in this file, so
  no variant is built on it until the anchor is reconciled. Flagged in LOG.md.
  Source: https://api.worldbank.org/v2/country/WLD/indicator/SI.POV.DDAY

- **Most items both models already answer well** turn out not to be perturbable
  at all: they are single famous studies (one PHE estimate on vaping, one
  genetics result, one exoneration study) with no other year, country or
  subgroup to move to. Perturbation needs *repeatedly measured* quantities —
  polls, national statistics, tracked databases. This shrinks the eligible pool
  considerably and is the main obstacle to reaching 20 variants.

  ./run.sh build_variants.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ITEMS = os.path.join(HERE, "data", "items.jsonl")
OUT = os.path.join(HERE, "data", "variants.jsonl")

# base_id, suffix, kind, prompt, context, answer, unit, source, note, checked
VARIANTS = [
    dict(
        base="lgbt-share", suffix="2012", kind="year",
        prompt="What share of US adults identified as LGBT in 2012?",
        context="",
        answer=3.5, unit="%",
        source="https://news.gallup.com/poll/702206/lgbtq-identification-holds.aspx",
        note="Gallup describes the current 9% as more than double the 3.5% "
             "recorded in 2012, the first year it measured LGBTQ+ incidence. "
             "Original and variant therefore share one source.",
        checked="2026-09-09",
    ),
    dict(
        base="creationism-share", suffix="1999", kind="year",
        prompt="In 1999, what share of Americans said God created humans in "
               "their present form within the last 10,000 years?",
        context="",
        answer=47.0, unit="%",
        source="https://news.gallup.com/poll/647594/majority-credits-god-humankind-not-creationism.aspx",
        note="Gallup gives 47% as the 1999 peak of its four-decade trend and "
             "37% as the current reading. Same article covers both.",
        checked="2026-09-09",
    ),
    dict(
        base="muslim-share", suffix="france", kind="country",
        prompt="What share of the population of France is Muslim?",
        context="",
        answer=8.8, unit="%",
        source="https://www.pewresearch.org/religion/2017/11/29/europes-growing-muslim-population/",
        note="Pew estimates 5.7 million Muslims in France as of mid-2016, 8.8% "
             "of the population. Against roughly 1% for the US, this is the "
             "largest shift in the set.",
        checked="2026-09-09",
    ),
    dict(
        base="ceo-pay", suffix="1989", kind="year",
        prompt="In 1965, the CEO of a big US firm earned about 21x the typical "
               "worker. What was that ratio in 1989?",
        context="",
        answer=61.0, unit="", prompt_anchor=21.0,
        source="https://www.epi.org/publication/ceo-pay-in-2023/",
        note="EPI realized-compensation series: 21-to-1 in 1965, 31-to-1 in "
             "1978, 61-to-1 in 1989. Same measure and same source as the "
             "original item, so only the target year moves.",
        checked="2026-09-09",
    ),
    dict(
        base="interracial-marriage", suffix="1978", kind="year",
        prompt="In 1958, 4% of Americans approved of marriage between Black and "
               "white people. What was approval in 1978?",
        context="",
        answer=36.0, unit="%", prompt_anchor=4.0,
        source="https://news.gallup.com/vault/212717/gallup-vault-americans-slow-back-interracial-marriage.aspx",
        note="Gallup Vault states that in 1978 only 36% of Americans approved "
             "while 54% still disapproved. The 1958 anchor is kept verbatim "
             "from the original prompt.",
        checked="2026-09-09",
    ),
    dict(
        base="gun-suicides", suffix="canada", kind="country",
        prompt="Of all gun deaths in Canada, what share are suicides?",
        context="",
        answer=75.0, unit="%",
        source="https://www150.statcan.gc.ca/n1/pub/85-002-x/2022001/article/00009-eng.htm",
        note="Statistics Canada vital statistics, 2019: of 708 firearm-related "
             "deaths, 75% were suicides and 23% homicides. US figure is ~60%, "
             "so the direction of the difference matters as well as the size.",
        checked="2026-09-09",
    ),
    dict(
        base="scientists-god", suffix="public", kind="subgroup",
        prompt="What share of the US general public say they believe in God or "
               "a universal spirit / higher power?",
        context="",
        answer=95.0, unit="%",
        source="https://www.pewresearch.org/religion/2009/11/05/scientists-and-belief/",
        note="Pew 2009: 51% of AAAS scientists believe in God or a higher power "
             "against 95% of the American public (Pew survey, July 2006), both "
             "reported in the same write-up. A subgroup swap rather than a year "
             "swap, and a cleaner perturbation for it — identical wording, "
             "identical instrument, only the population moves.",
        checked="2026-09-09",
    ),
    dict(
        base="recidivism", suffix="3year", kind="horizon",
        prompt="Of US state prisoners released in 2005, what share were "
               "rearrested within 3 years?",
        context="",
        answer=68.0, unit="%",
        source="https://bjs.ojp.gov/content/pub/pdf/18upr9yfup0514.pdf",
        note="BJS 2018 Update on Prisoner Recidivism, 2005 cohort across 30 "
             "states: 68% rearrested within 3 years, 79% within 6, 83% within "
             "9. FLAGGED: the base item is framed on a 2008 cohort at 10 years, "
             "so this moves the cohort as well as the window and is not a pure "
             "one-variable swap. Kept because the follow-up window is the "
             "dominant term, but it is the weakest variant in the set and "
             "should be the first dropped if the gap ever hinges on it.",
        checked="2026-09-09",
    ),
    dict(
        base="plastic-recycling", suffix="us", kind="null-control",
        prompt="Of all the plastic waste the United States generates, what "
               "share actually gets recycled?",
        context="",
        answer=8.7, unit="%",
        source="https://www.epa.gov/facts-and-figures-about-materials-waste-and-recycling/plastics-material-specific-data",
        note="NULL CONTROL, included deliberately. EPA puts the US plastics "
             "recycling rate at 8.7% for 2018, against ~9% globally for the "
             "original. The right answer barely moves, so a model that only "
             "needs to hold its ground should score the same here. Error rising "
             "on this item means the rewording alone is doing damage, which "
             "would invalidate reading the other gaps as memorisation.",
        checked="2026-09-09",
    ),
]


def main():
    base = {}
    for line in open(ITEMS, encoding="utf-8"):
        r = json.loads(line)
        base[r["id"]] = r

    missing = [v["base"] for v in VARIANTS if v["base"] not in base]
    if missing:
        sys.exit(f"base items not found in the bank: {missing}")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        for v in VARIANTS:
            b = base[v["base"]]
            if b.get("numeric_answer") is None:
                sys.exit(f"{v['base']} has no numeric answer; it cannot be "
                         f"perturbed in interval mode")
            rec = {
                "id": f'{v["base"]}@{v["suffix"]}',
                "base_id": v["base"],
                "kind": v["kind"],
                # joined from the base item, never retyped
                "category": b["category"],
                "punctures": b["punctures"],
                "prompt": v["prompt"],
                "context": v["context"],
                "options": [],
                "answer_index": None,
                "answer_text": "",
                "numeric_answer": v["answer"],
                "unit": v["unit"],
                "original_answer": b["numeric_answer"],
                # A reference figure stated in the prompt itself, where there is
                # one. Two different failures look alike in the error column and
                # are worth telling apart: answering the ORIGINAL question
                # (original_answer) versus simply echoing a number handed to the
                # model in the prompt (prompt_anchor). Only the second is
                # available without any recall at all.
                "prompt_anchor": v.get("prompt_anchor"),
                "source_url": v["source"],
                "source_note": v["note"],
                "verified": v["checked"],
            }
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"wrote {OUT}  ({len(VARIANTS)} variants)")
    real = [v for v in VARIANTS if v["kind"] != "null-control"]
    print(f"  {len(real)} perturbations + "
          f"{len(VARIANTS)-len(real)} null control")
    for v in VARIANTS:
        b = base[v["base"]]
        shift = abs(v["answer"] - b["numeric_answer"])
        rel = shift / max(abs(b["numeric_answer"]), 1e-9)
        flag = "  <- control" if v["kind"] == "null-control" else ""
        print(f'  {v["base"]+"@"+v["suffix"]:<28} '
              f'{b["numeric_answer"]:>7g} -> {v["answer"]:<7g} '
              f'shift {rel*100:>5.0f}%{flag}')


if __name__ == "__main__":
    main()
