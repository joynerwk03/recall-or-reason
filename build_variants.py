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

   The second batch added on 2026-09-11 states each prompt as a swap on the
   original's own text, `(old, new)`, so the wording cannot drift from the
   original's. `SAME_CONTEXT` carries the original's context over verbatim
   where it applies equally to the variant; it is dropped where it describes
   only the original's target, or would hand the model the variant's answer.

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

- **ocean-plastic-rivers.** The obvious variant was a continent swap (Africa
  for Asia), but the cited paper (Meijer et al., Science Advances 2021) states
  no share by continent in its main text or its Table 1, so there is no
  sourced number to swap to. The "80%" in its title is a different quantity:
  the share of global emissions from its top 1,656 rivers. Recorded in AUDIT.md.

- **Most items both models already answer well** turn out not to be perturbable
  at all: they are single famous studies (one PHE estimate on vaping, one
  genetics result, one exoneration study) with no other year, country or
  subgroup to move to. Perturbation needs *repeatedly measured* quantities —
  polls, national statistics, tracked databases. This shrinks the eligible pool
  considerably and was the main obstacle to reaching 20 variants. The way
  past it, on 2026-09-11, was subgroup swaps inside a single published
  sentence or table that also holds the original's figure.

  ./run.sh build_variants.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ITEMS = os.path.join(HERE, "data", "items.jsonl")
OUT = os.path.join(HERE, "data", "variants.jsonl")

# Resolved at build time to the original item's context, verbatim (rule 3).
SAME_CONTEXT = "<the original's context, verbatim>"

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
    # --- added 2026-09-11. Each is drawn from the SAME source as its original
    # --- item, and each original was checked against that source first: a
    # --- variant built on an original that disagrees with its own citation
    # --- would be measuring the defect, not the model.
    dict(
        base="depression-prevalence", suffix="adolescents", kind="subgroup",
        prompt="In a given year, what share of US adolescents aged 12 to 17 "
               "experience a major depressive episode (two weeks or more of "
               "depressed mood or loss of interest, plus other symptoms)?",
        context="",
        answer=20.1, unit="%",
        source="https://www.nimh.nih.gov/health/statistics/major-depression",
        note="NIMH, from the 2021 NSDUH: 8.3% of US adults and 20.1% of "
             "adolescents aged 12-17 had at least one major depressive episode "
             "in the past year. The original item's 8% is the adult figure from "
             "the same page and year, so only the population moves.",
        checked="2026-09-11",
    ),
    dict(
        base="abortion-timing", suffix="13weeks", kind="subgroup",
        prompt="What share of US abortions occur at or before 13 weeks of "
               "pregnancy?",
        context="",
        answer=92.8, unit="%",
        source="https://www.cdc.gov/mmwr/volumes/73/ss/ss7307a1.htm",
        note="CDC Abortion Surveillance, 2022 data: 92.8% at <=13 weeks, 6.1% at "
             "14-20 weeks, 1.1% at >=21 weeks. The original item's 1% is the "
             ">=21-week figure from the same table. A model reciting the famous "
             "late-abortion figure would answer near 1 here; the truth is near 93.",
        checked="2026-09-11",
    ),
    dict(
        base="replication-crisis", suffix="economics", kind="subgroup",
        prompt="Researchers rigorously re-ran 18 published laboratory "
               "experiments from top economics journals. What share produced a "
               "statistically significant effect in the same direction the "
               "second time?",
        context="",
        answer=61.1, unit="%",
        source="https://www.science.org/doi/10.1126/science.aaf0918",
        note="Camerer et al., Science 2016: 11 of 18 replications (61.1%) found "
             "a significant effect in the same direction, against 36% for "
             "psychology in the Open Science Collaboration (2015) — the original "
             "item. FLAGGED as a field swap across two papers rather than a swap "
             "within one table: the designs are parallel (pre-registered, high "
             "power) but not identical, so this is the loosest new variant.",
        checked="2026-09-11",
    ),
    dict(
        base="wealth-top1", suffix="bottom50", kind="subgroup",
        prompt="What share of all US household wealth is owned by the poorest "
               "half of households?",
        context="",
        answer=2.5, unit="%",
        source="https://www.federalreserve.gov/releases/z1/dataviz/download/zips/dfa.zip",
        note="Federal Reserve Distributional Financial Accounts, net-worth "
             "shares, 2024:Q1. Top 0.1% 13.8 + remaining top 1% 16.8 = 30.6% for "
             "the top 1%, matching the original item (which cites Q1 2024, "
             "~30.5%); the bottom 50% held 2.5% in the same quarter. Read from "
             "the Fed's machine-readable release rather than the interactive "
             "chart the original cites, which does not render without script.",
        checked="2026-09-11",
    ),
    dict(
        base="top1-tax-share", suffix="top10", kind="subgroup",
        prompt="What share of all federal income taxes is paid by the top 10% "
               "of earners?",
        context="",
        answer=70.5, unit="%",
        source="https://taxfoundation.org/data/all/federal/who-pays-federal-income-taxes-tax-year-2023/",
        note="Tax Foundation summary of IRS data, tax year 2023: the top 1% paid "
             "38.40%, the top 10% 70.54%, the bottom 50% 3.26%. The original "
             "item's 38% is the top-1% figure on this page. NOTE: the original "
             "cites a different Tax Foundation page — the '2025' summary, which "
             "covers tax year 2022 and shows 40.4%. Its number is right for 2023 "
             "but its link points at the wrong year, so this variant is built "
             "from the page that actually contains the original's figure.",
        checked="2026-09-11",
    ),
    # --- second batch, added 2026-09-11, taking the set from 13 perturbations
    # --- to 20. Five of the seven move only the population inside one
    # --- published sentence or table that also holds the original's figure:
    # --- same instrument, same year, one variable. The other two are flagged.
    dict(
        base="cannabis-dependence", suffix="cocaine", kind="subgroup",
        prompt=("cannabis", "cocaine"),
        context=SAME_CONTEXT,
        answer=20.9, unit="%",
        source="https://pubmed.ncbi.nlm.nih.gov/21145178/",
        note="Lopez-Quintero et al., Drug and Alcohol Dependence 2011 (NESARC): "
             "'The cumulative probability estimate of transition to dependence "
             "was 67.5% for nicotine users, 22.7% for alcohol users, 20.9% for "
             "cocaine users, and 8.9% for cannabis users' (abstract, read via "
             "Europe PMC). The original's 9% and both of its context anchors "
             "come from that one sentence, so the context is kept. No "
             "prompt_anchor is recorded: the alcohol anchor (22.7) sits within "
             "two points of the truth, so an anchor test could not tell echoing "
             "the context from answering correctly. Only an echo of the "
             "cannabis figure is tested.",
        checked="2026-09-11",
    ),
    dict(
        base="mobility", suffix="canada", kind="country",
        prompt=("US households", "Canadian households"),
        context=SAME_CONTEXT,
        answer=13.4, unit="%",
        source="https://opportunityinsights.org/wp-content/uploads/2018/03/mobility_geo.pdf",
        note="Chetty, Hendren, Kline and Saez, 'Where is the Land of "
             "Opportunity?' (QJE 2014), on the quintile transition matrix: the "
             "bottom-to-top probability 'is 7.5% in the U.S., compared with "
             "11.7% in Denmark (Boserup, Kopczuk and Kreiner 2013) and 13.4% in "
             "Canada (Corak and Heisz 1999).' Same sentence as the original's "
             "figure. FLAGGED: the Canadian estimate is Corak and Heisz's, on "
             "earlier cohorts, quoted by Chetty rather than computed from the "
             "same data, so this is a cross-study comparison inside one "
             "sentence. The context's 20% is a no-mobility benchmark shared by "
             "both questions, not a figure for the original, so it is not "
             "recorded as a prompt_anchor.",
        checked="2026-09-11",
    ),
    dict(
        base="lgbt-share", suffix="under30", kind="subgroup",
        prompt=("US adults", "US adults under age 30"),
        context="",
        answer=23.0, unit="%",
        source="https://news.gallup.com/poll/702206/lgbtq-identification-holds.aspx",
        note="Gallup, 'LGBTQ+ Identification Holds at 9% in U.S.' (February "
             "2026, 2025 data): 9% of all US adults and 23% of adults under 30. "
             "Same article as the original. The original's context (the public "
             "guesses about 23%) is dropped on purpose: here it would hand the "
             "model the answer.",
        checked="2026-09-11",
    ),
    dict(
        base="private-prisons", suffix="federal2015", kind="subgroup",
        prompt="In 2015, what share of US federal prisoners were held in "
               "private, for-profit prisons?",
        context=SAME_CONTEXT,
        answer=18.0, unit="%",
        source="https://www.pewresearch.org/short-reads/2017/04/11/u-s-private-prison-population-has-declined-in-recent-years/",
        note="Pew Research Center, from BJS National Prisoner Statistics: in "
             "2015, 8% of the nearly 1.53 million state and federal prisoners "
             "were in private facilities (the original item's figure) and "
             "'nearly 18%' of federal prisoners. Same article, same year. The "
             "year is written into the prompt because the federal share is set "
             "by policy and moves, so an undated question would not have one "
             "answer.",
        checked="2026-09-11",
    ),
    dict(
        base="iq-heritability", suffix="age9", kind="subgroup",
        prompt=("By adulthood", "At age 9"),
        context=SAME_CONTEXT,
        answer=41.0, unit="%",
        source="https://pubmed.ncbi.nlm.nih.gov/19488046/",
        note="Haworth et al., Molecular Psychiatry 2010, 11,000 twin pairs from "
             "four countries: heritability of general cognitive ability rises "
             "'from 41% in childhood (9 years) to 55% in adolescence (12 years) "
             "and to 66% in young adulthood (17 years)' (abstract, read via "
             "Europe PMC). FLAGGED as a cross-paper swap: the original cites "
             "Bouchard 2013, whose abstract puts the adult asymptote near 0.80 "
             "but gives no age-9 figure. The unit is set to % although the "
             "original's is blank, so the model is told the scale; a 0-to-1 "
             "answer would otherwise make an echo of 0.7 undetectable.",
        checked="2026-09-11",
    ),
    dict(
        base="top1-tax-share", suffix="bottom50", kind="subgroup",
        prompt=("top 1% of earners", "bottom 50% of earners"),
        context="",
        answer=3.26, unit="%",
        source="https://taxfoundation.org/data/all/federal/who-pays-federal-income-taxes-tax-year-2023/",
        note="Tax Foundation, tax year 2023, Table 1, share of total income "
             "taxes paid: top 1% 38.3980, top 10% 70.5426, bottom 50% 3.2601. "
             "Same table as the original and as top1-tax-share@top10. The "
             "original's context describes the top 1% only and is dropped.",
        checked="2026-09-11",
    ),
    dict(
        base="wealth-top1", suffix="top10", kind="subgroup",
        prompt=("richest 1%", "richest 10%"),
        context="",
        answer=67.1, unit="%",
        source="https://www.federalreserve.gov/releases/z1/dataviz/download/zips/dfa.zip",
        note="Federal Reserve DFA net-worth shares, 2024:Q1, the same file and "
             "quarter as the original and as wealth-top1@bottom50: top 0.1% "
             "13.8 + rest of the top 1% 16.8 + next 9% 36.5 = 67.1%. The "
             "original's context (an even split gives the top 1% 1%) describes "
             "the top 1% only and is dropped.",
        checked="2026-09-11",
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
            prompt, context = v["prompt"], v["context"]
            if isinstance(prompt, tuple):
                old, repl = prompt
                if b["prompt"].count(old) != 1:
                    sys.exit(f'{v["base"]}: swap text {old!r} must occur exactly '
                             f'once in the original prompt')
                prompt = b["prompt"].replace(old, repl)
            if context == SAME_CONTEXT:
                context = b.get("context") or ""
            rec = {
                "id": f'{v["base"]}@{v["suffix"]}',
                "base_id": v["base"],
                "kind": v["kind"],
                # joined from the base item, never retyped
                "category": b["category"],
                "punctures": b["punctures"],
                "prompt": prompt,
                "context": context,
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
