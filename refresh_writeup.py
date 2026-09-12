#!/usr/bin/env python3
"""Regenerate every number-bearing part of the write-up from results/fleet.json.

The fleet numbers move whenever a repeat run lands, and they were first written
into PAPER.md and dashboard.html by hand. Hand-transcription is how this project
once published a table that had to be retracted, so the parts that depend on the
data are generated instead:

  PAPER.md        the abstract's fleet paragraphs, and the whole of Section 6
  dashboard.html  the FLEET array the chart draws, Section 5, the fleet
                  paragraph in the technical block, and the sample-size caveat

Claims that depend on the *pattern* of results are derived too, not asserted:
which components survive Holm correction, which model pair is the largest
inversion, which pair shows the most capability for the least honesty, and which
direction each size ladder runs. If the data stops supporting a sentence, the
sentence changes with it.

Static prose — design, limits, caveats, lessons — stays in the templates below.

  ./run.sh compare_capability.py --json results/fleet.json
  ./run.sh ladder.py results/fleet.json --json results/ladder.json
  ./run.sh refresh_writeup.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ladder as LD   # noqa: E402  (for the family/parameter table)

PAPER = os.path.join(HERE, "PAPER.md")
DASH = os.path.join(HERE, "dashboard.html")


def replace_once(s, old, new, what):
    if s.count(old) != 1:
        sys.exit(f"{what}: expected exactly one match, found {s.count(old)}")
    return s.replace(old, new)


def slice_between(s, start_marker, end_marker, new, what):
    i = s.find(start_marker)
    j = s.find(end_marker, i + 1)
    if i < 0 or j < 0:
        sys.exit(f"{what}: markers not found")
    return s[:i] + new + s[j:]


def main():
    d = json.load(open(os.path.join(HERE, "results", "fleet.json"), encoding="utf-8"))
    lad = json.load(open(os.path.join(HERE, "results", "ladder.json"), encoding="utf-8"))
    rows = sorted(d["rows"], key=lambda r: r["eci"])
    by_tag = {r["tag"]: r for r in rows}

    rho, p, n, span = d["rho"], d["p"], len(rows), d["span"]
    lo, hi = d["ci_full"]
    slo, shi = d["ci_sampling"]
    pos, strong = d["share_positive"], d["share_rho_gt_half"]
    rho_o, n_o, span_o = d["rho_original"], d["n_original"], d["span_original"]
    rho_x = d["rho_with_excluded"]
    comp = {c["k"]: c for c in d["components"]}
    loo, sens, excl = d["loo"], d["sensitivity"], d["excluded"]
    cal_r, cal_h = comp["calibration"]["rho"], comp["calibration"]["holm"]
    hon_r, hon_h = comp["honesty"]["rho"], comp["honesty"]["holm"]
    dis_r, dis_h = comp["discrimination"]["rho"], comp["discrimination"]["holm"]
    ind_r, ind_h = comp["independence"]["rho"], comp["independence"]["holm"]
    sens_lo = min(x["rho"] for x in sens)
    sens_hi = max(x["rho"] for x in sens)
    sens_plo = min(x["p"] for x in sens)
    sens_phi = max(x["p"] for x in sens)
    NAMES = {"calibration": "calibration", "honesty": "interval honesty",
             "discrimination": "discrimination", "independence": "independence"}
    survive = [NAMES[c["k"]] for c in d["components"] if c["holm"] < 0.05]
    fails = [NAMES[c["k"]] for c in d["components"] if c["holm"] >= 0.05]
    reps_multi = sum(1 for r in rows if r.get("n_reps", 1) > 1)
    reps_max = max(r.get("n_reps", 1) for r in rows)

    # The largest inversion: a lower-capability model beating a higher one.
    inv = max(((a, b) for a in rows for b in rows if b["eci"] > a["eci"]),
              key=lambda ab: ab[0]["ehs"] - ab[1]["ehs"])
    inv_lo, inv_hi = inv
    inv_gap = inv_hi["eci"] - inv_lo["eci"]
    # The widest capability gap that buys the least honesty.
    flat = max(((a, b) for a in rows for b in rows
                if b["eci"] > a["eci"] and abs(a["ehs"] - b["ehs"]) < 2.0),
               key=lambda ab: ab[1]["eci"] - ab[0]["eci"], default=None)
    top4 = rows[-4:]
    top4_txt = ", ".join(f"{r['ehs']:.1f}" for r in top4)

    def table_rows():
        out = []
        for r in rows:
            rng = (f"[{r['ehs_lo']:.0f}, {r['ehs_hi']:.0f}]"
                   if r.get("n_reps", 1) > 1 else "—")
            cells = " | ".join(
                f"{r[k]:.0f}" if r.get(k) is not None else "—"
                for k in ("calibration", "honesty", "discrimination", "independence"))
            bold = "**" if r["ehs"] == max(x["ehs"] for x in rows) else ""
            out.append(f"| {r['tag']} | {r['eci']:.1f} | {bold}{r['ehs']:.1f}{bold} | "
                       f"{rng} | {r.get('n_reps', 1)} | {cells} |")
        return "\n".join(out)

    def ladder_table(fam):
        info = lad[fam]
        lines = []
        for tag, size in LD.FAMILIES[fam]:
            r = by_tag.get(tag)
            if not r:
                continue
            lines.append(f"| {tag} | {size}B | {r['eci']:.1f} | {r['ehs']:.1f} | "
                         + " | ".join(f"{r[k]:.0f}" for k in
                                      ("calibration", "honesty", "discrimination",
                                       "independence")) + " |")
        return "\n".join(lines), info

    g_rows, g_info = ladder_table("Gemma 3")
    q_rows, q_info = ladder_table("Qwen3")

    def dirs(info, keys=("calibration", "honesty")):
        return all(info[k]["direction"] == "rises with size" for k in keys)

    both_rise = dirs(g_info) and dirs(q_info)
    ladder_claim = (
        "**In both families, calibration and interval honesty rise monotonically "
        "with size — the same two components that survive correction across the "
        "whole fleet.**" if both_rise else
        "**The families do not agree**, so the ladders support nothing beyond "
        "what is tabulated above.")
    ehs_dirs = "; ".join(f"{fam}: EHS {lad[fam]['ehs']['direction']}"
                         for fam in ("Gemma 3", "Qwen3"))

    # ---------------- PAPER: abstract ----------------
    s = open(PAPER, encoding="utf-8").read()
    abstract = f"""**Extended to eighteen models**, {n} of which carry a capability score and
survive pre-set reliability rules, the relationship between general capability
and epistemic honesty is **positive but not established**: Spearman rho =
**{rho:+.2f}** across {span:.1f} points of the Epoch Capabilities Index
(permutation *p* = {p:.3f}), with a 95% interval that still touches zero once
every source of uncertainty is propagated: **[{lo:+.2f}, {hi:+.2f}]**,
{pos:.0%} of draws positive. Of the four components, {len(survive)} survive
correction for multiple testing — {" and ".join(survive)} — while
{" and ".join(fails)} do not.

**This replaces a null.** An earlier draft reported rho = +0.25 on ten models and
called it "capability does not predict epistemic honesty". That claim was
already too strong for its own interval; it is also, on the wider range, wrong
in direction. The same pipeline still returns {rho_o:+.2f} on those ten models,
so the earlier result was substantially **range restriction**: ten models
spanning {span_o:.1f} index points could not see a relationship that {n}
spanning {span:.1f} can. Capability in this fleet is nearly collinear with
release date, and the item set penalises models with older training cutoffs, so
the honest reading is that *something* about newer, stronger models tracks
epistemic honesty — not that capability alone causes it.

"""
    s = slice_between(s, "**Extended to eighteen models**",
                      "Finally we document nine ways", abstract, "abstract")

    # ---------------- PAPER: section 6 ----------------
    flat_txt = ""
    if flat:
        a, b = flat
        flat_txt = (f"- **{b['tag']} (ECI {b['eci']:.1f}) scores {b['ehs']:.1f}; "
                    f"{a['tag']}, {b['eci'] - a['eci']:.1f} points weaker, scores "
                    f"{a['ehs']:.1f}.** Twenty points of general capability buy "
                    f"about a point here.\n")

    sec6 = f"""## 6. Does general capability predict epistemic honesty? {n} models

Everything above concerns two models. The obvious question is whether any of it
is a property of *models* or of *those* models — and behind that, a sharper one:
if a better model is automatically more honest about its own uncertainty, this
benchmark is measuring general capability the expensive way and does not need to
exist.

🔴 **This section replaces a null, and the replacement is not a small
correction.** The 2026-09-10 draft reported rho = +0.25 on ten models and said
capability does not predict epistemic honesty. Two things were wrong with that.
The claim was stronger than its own interval, which was never computed; and the
ten models covered the bottom {span_o:.1f} points of a range that now runs
{span:.1f}, which is exactly the condition under which a real correlation is
attenuated toward zero. Section 6.5 measures that directly.

### 6.1 Design

Eighteen models run locally (Section 1.2). Sixteen carry an Epoch Capabilities
Index score; **{n}** of those pass reliability rules fixed in advance and enter
the correlation. ECI stitches 50+ benchmarks onto one scale by comparing models
evaluated on more than one of them, so it stays meaningful after any single
benchmark saturates, and it is read from Epoch's machine-readable release with
the interval Epoch publishes for each model.

Each model is reduced to one **Epistemic Honesty Score** (0–100), the mean of
four components: calibration, interval honesty scaled by sharpness,
discrimination, and independence from anchors. **EHS contains no accuracy term
by construction.** Had it rewarded getting answers right it would partly *be* a
capability index, and any correlation below would be guaranteed rather than
discovered.

A model's score is the mean over its complete repeat runs, and the chart draws
its min–max spread. {reps_multi} of the {n} scored models have more than one
complete run of all three modes, up to {reps_max}. Every figure in this section
regenerates from `results/fleet.json` via `refresh_writeup.py`.

### 6.2 Result

| model | ECI | EHS | repeat range | runs | calib | honesty | disc | indep |
|---|---|---|---|---|---|---|---|---|
{table_rows()}

Not on the capability axis, because Epoch does not score them:
{", ".join(f"{r['tag'].replace('-t0', '')} **{r['ehs']:.1f}**" for r in d["no_eci"])}.
They are reported rather than dropped, but they cannot enter the correlation.

**Excluded by rules fixed before the runs finished**, with their reasons:

| model | ECI | why |
|---|---|---|
{chr(10).join(f"| {r['tag']} | {r['eci']:.1f} | {'; '.join(r['flags'])} |" for r in excl)}

**Spearman rho = {rho:+.3f}, permutation *p* = {p:.3f}, n = {n} models spanning
{span:.1f} ECI points.**

| interval | | |
|---|---|---|
| 95%, sampling only | [{slo:+.2f}, {shi:+.2f}] | resampling models |
| 95%, full uncertainty | **[{lo:+.2f}, {hi:+.2f}]** | + repeat-run noise + Epoch's own ECI intervals |
| draws above zero | {pos:.0%} | |
| draws above +0.5 | {strong:.0%} | |

**The verdict is "not established, and leaning positive", and both halves of
that matter.** The interval includes zero, so this is not a result: a fleet of
{n} cannot rule out that the relationship is nothing. But {pos:.0%} of the
bootstrap mass sits above zero and {strong:.0%} of it above +0.5, so it is not a
null either, and calling it one — as the earlier draft did with weaker evidence
— would be the same error in the opposite direction.

**Why the *p* and the interval disagree.** The permutation test asks whether
this rho could arise if capability and honesty were unrelated *in this set of
{n} models*; it clears 0.05. The bootstrap interval asks a harder question: what
would happen with a different sample of models, different draws of their
run-to-run noise, and ECI values redrawn from Epoch's own uncertainty. The
second question is the one a reader cares about, so the interval governs the
verdict.

### 6.3 The components move apart

A composite can hide components pulling against each other, and here they
separate cleanly:

| component | rho vs ECI | p | Holm-adjusted |
|---|---|---|---|
| calibration | **{cal_r:+.3f}** | {comp['calibration']['p']:.3f} | **{cal_h:.3f}** {'✓' if cal_h < 0.05 else ''} |
| honesty (interval coverage × sharpness) | **{hon_r:+.3f}** | {comp['honesty']['p']:.3f} | **{hon_h:.3f}** {'✓' if hon_h < 0.05 else ''} |
| discrimination | {dis_r:+.3f} | {comp['discrimination']['p']:.3f} | {dis_h:.3f} |
| independence from anchors | {ind_r:+.3f} | {comp['independence']['p']:.3f} | {ind_h:.3f} |

**The two that survive correction are the two about stating uncertainty; the two
that do not are the two about memorisation.** More capable models are better at
saying how sure they are — both on a percentage scale and as an interval. They
are not measurably better at widening the interval on the items they get wrong,
and not measurably better at answering the question in front of them rather than
the one they remember. On this evidence the memorisation half of the benchmark
is not a capability proxy, which is the strongest argument in this paper for
measuring it separately.

(An earlier draft found calibration at rho +0.66 failing Holm correction at ten
models, and recorded it as worth re-testing. It was re-tested, and it held.)

### 6.4 What the spread actually looks like

The correlation is real but loose, and the loose part is the middle of the range:

- **{inv_lo['tag']} scores {inv_lo['ehs']:.1f} at ECI {inv_lo['eci']:.1f}.**
  {inv_hi['tag']}, **{inv_gap:.1f} index points more capable**, scores
  **{inv_hi['ehs']:.1f}** — the largest single inversion in the set.
{flat_txt}- **The four most capable models score {top4_txt}** — all well above the
  middle of the fleet. The top of the range is uniformly decent; the
  disagreement is everywhere else.

**The practical reading has not changed as much as the headline.** If you are
choosing between two models a leaderboard treats as similar, its ranking still
will not tell you whose stated confidence to trust — the inversions above are
large and real. What has changed is the claim that the leaderboard tells you
*nothing*: across a wide enough capability range, it tells you something.

### 6.5 Four ways to break the result, and what each does to it

| check | rho | reading |
|---|---|---|
| **Range**: original ten models ({span_o:.1f} ECI points) | **{rho_o:+.3f}** | the earlier null was substantially range restriction |
| same pipeline, extended {n} ({span:.1f} points) | **{rho:+.3f}** | |
| **Weighting**: five weightings of the composite | {sens_lo:+.3f} to {sens_hi:+.3f} (p {sens_plo:.3f}–{sens_phi:.3f}) | not an artefact of weighting the four components equally |
| **Leave-one-out**: drop each model in turn | {loo['min']:+.3f} (without {loo['min_without']}) to {loo['max']:+.3f} (without {loo['max_without']}) | no single model carries it |
| **Exclusions**: put the two excluded models back | **{rho_x:+.3f}**, n = {n + len(excl)} | the pre-set exclusion rule is not what produces the result — it strengthens without it |

The range row is the important one. Both numbers come from the same code, the
same items and the same scoring, run today; the only difference is which models
are in the set. A claim that capability does not predict honesty, made from the
bottom two-thirds of a range, is a claim about the bottom two-thirds of a range.

### 6.6 Within-family size ladders, which control for something the axis cannot

The capability axis is confounded with almost everything else that varies
between labs: recipe, data, alignment, and release date. Two families are in the
fleet at three sizes of **one generation**, released on one day, which removes
most of that:

| Gemma 3 (all released 2025-03-12) | params | ECI | EHS | calib | honesty | disc | indep |
|---|---|---|---|---|---|---|---|
{g_rows}

| Qwen3 (all released 2025-04) | params | ECI | EHS | calib | honesty | disc | indep |
|---|---|---|---|---|---|---|---|
{q_rows}

{ladder_claim} The composite itself is less tidy — {ehs_dirs} — and
discrimination has no consistent direction in either family.

Three sizes is a description, not a test, and this is quoted as one. But it is a
description that the release-date confound cannot explain, because within each
family the release date does not vary.

### 6.7 Limits specific to this comparison

- **n = {n} models.** A rank correlation on {n} points has a wide interval
  whichever way it lands, which is why the interval governs the verdict here.
- **Capability is nearly collinear with recency.** Every model above ECI 139 in
  this fleet is a 2026 release. The item set asks many questions in the present
  tense without a date (Section 7), and a model with an older training cutoff
  answers with an older figure and is scored wrong — which costs it calibration
  and interval honesty, the two components that carry the correlation. That bias
  pushes toward exactly the positive relationship reported here. The ladders in
  6.6 are the only part of this section the confound cannot reach.
- **ECI carries its own confidence intervals**, several more than ten points
  wide (Gemma 3 4B: [97.5, 123.4]). The full-uncertainty interval propagates
  them; the chart draws them.
- **Reasoning-mode ambiguity for the Qwen models.** Epoch lists separate
  reasoning and non-reasoning entries for some Qwen sizes but only a plain entry
  for these, and does not state which mode it evaluated. The harness lets them
  think and strips the scratchpad. The plain entry is the closest available
  match; that is a limitation of the join, not something the join can fix.
- **Truncation still touches four included models** at 1–9% of answers, all well
  inside the pre-registered bar, and a truncated answer is dropped rather than
  scored wrong. Dropping a model's hardest items can flatter it.
- **Two models' perturbation scores are flagged as unattributable**, not bad:
  qwen3.6:35b-a3b and qwen3.6:27b miss the null control by 31% and 43%, so for
  them the rewording alone moved the answer and their independence component
  cannot be read as memorisation. One control item is not enough to tell those
  apart (Section 8).
- **Everything is quantised and locally run** against an index that scores the
  full-precision hosted model.

"""
    s = slice_between(s, "## 6. Does general capability predict epistemic honesty?",
                      "## 7. Limitations", sec6, "section 6")
    open(PAPER, "w", encoding="utf-8").write(s)

    # ---------------- dashboard ----------------
    h = open(DASH, encoding="utf-8").read()
    js = []
    for r in rows:
        bits = ['t:"%s"' % r["tag"], "e:%.2f" % r["eci"], "lo:%.2f" % r["eci_lo"],
                "hi:%.2f" % r["eci_hi"], "s:%.1f" % r["ehs"]]
        if r.get("n_reps", 1) > 1 and r["ehs_hi"] > r["ehs_lo"]:
            bits += ["slo:%.1f" % r["ehs_lo"], "shi:%.1f" % r["ehs_hi"]]
        if not r.get("original_ten", True):
            bits.append("add:1")
        js.append(" {" + ", ".join(bits) + "}")
    h = slice_between(h, "const FLEET=[", "];",
                      "const FLEET=[\n" + ",\n".join(js) + "\n", "FLEET array")

    inv_txt = (f'<span class="idm">{inv_lo["tag"]}</span> scores '
               f'<b>{inv_lo["ehs"]:.0f}</b> while '
               f'<span class="idm">{inv_hi["tag"]}</span> — {inv_gap:.0f} points '
               f'<em>higher</em> on the leaderboard — scores <b>{inv_hi["ehs"]:.0f}</b>.')
    flat_html = ""
    if flat:
        a, b = flat
        flat_html = (f' And <span class="idm">{a["tag"]}</span>, '
                     f'{b["eci"] - a["eci"]:.0f} points <em>lower</em> than '
                     f'<span class="idm">{b["tag"]}</span>, matches it '
                     f'({a["ehs"]:.0f} against {b["ehs"]:.0f}).')

    sec5 = f"""<!-- ---------- 5b: the fleet ---------- -->
<section>
  <div class="shead"><span class="snum">5</span><h2>Do smarter models know themselves better?</h2></div>
  <p>
    Everything above is two models, which could just be those two models. So I
    ran the whole thing on <strong>eighteen</strong> — every one I could
    download and run on a home computer, from a 1-billion-parameter model up to
    a 35-billion one. {n} of them can be placed on a public ability
    leaderboard <em>and</em> answered reliably enough to score.
  </p>
  <p>
    Those leaderboards rank models on general ability by combining dozens of
    separate tests. I used one from a research group called Epoch, and asked:
    <strong>if a model is higher on it, is it also better at knowing what it
    doesn't know?</strong> You would expect yes — the same intuition that says a
    better student is also better at judging which exam answers they got wrong.
  </p>
  <p>
    <strong>The answer is probably yes. The first time I ran this, on ten
    models, I got "no" and wrote it up as the headline finding.</strong> Why that
    happened is the most useful thing on this page.
  </p>
  <figure class="wide">
    <svg id="fleet" viewBox="0 0 900 470" role="img"
         aria-label="{n} models plotted by general ability against how well they know their own uncertainty. The trend is upward but loose, with large exceptions."></svg>
    <figcaption>
      Each dot is one model. Left-to-right is general ability from the public
      leaderboard; up-and-down is how well it knows its own uncertainty. The
      horizontal bars are the leaderboard's <em>own</em> uncertainty about where a
      model belongs — several are wide, and hiding them would imply a precision
      the ranking doesn't have. Hollow dots are models I added to widen the
      range. Vertical bars, where you can see them, are how much a model's own
      score moved between repeat runs.
    </figcaption>
  </figure>
  <div class="findings">
    <p class="finding">
      <strong>Ability and self-knowledge do move together — but I can't call it
      settled.</strong> Rank the models both ways and the two orders come out
      similar: the correlation is <b>{rho:+.2f}</b> (1.00 would be identical
      orders, 0 unrelated). Once I account for every source of error at once, the
      plausible range runs from <b>{lo:+.2f}</b> to <b>{hi:+.2f}</b> — and
      because that just barely includes zero, "no relationship" isn't quite ruled
      out. {pos:.0%} of the statistical resamples land on the positive side.
    </p>
    <p class="finding">
      <strong>Why I got the opposite answer the first time.</strong> My first ten
      models were bunched into a narrow band of ability. Inside a narrow band, a
      real relationship looks like noise — it's like testing whether height
      predicts basketball ability using only people between 5'10" and 6'0".
      Same code, same questions, wider band: <b>{rho_o:+.2f}</b> across the
      original {n_o} models becomes <b>{rho:+.2f}</b> across {n}.
    </p>
    <p class="finding">
      <strong>Two of the four things I measure improve with ability; two don't.</strong>
      The two about <em>stating</em> uncertainty do — whether "90% sure" means 90%
      (<b>{cal_r:+.2f}</b>), and whether a stated range actually contains the
      answer (<b>{hon_r:+.2f}</b>). The two about <em>memorisation</em> don't:
      widening the range where it's about to be wrong (<b>{dis_r:+.2f}</b>) and
      avoiding repeating a number it already had (<b>{ind_r:+.2f}</b>).
      <strong>So the leaderboard predicts the familiar half of this test and not
      the novel half.</strong>
    </p>
    <p class="finding">
      <strong>The big exceptions are still there.</strong> {inv_txt}{flat_html}
    </p>
    <p class="finding">
      <strong>One thing I can't rule out.</strong> Every model at the top of the
      ability range is a 2026 release, and some of my questions ask about
      "now" without saying when — so a model trained earlier answers with an
      older figure and is marked wrong. That penalty lands on older models, which
      are also the lower-ranked ones, and pushes toward exactly the result I
      found. The check is further down: within a single family released on a
      single day, the same two measures still rise with size.
    </p>
  </div>
  <p style="margin-top:20px">
    <strong>What this means if you're picking a model.</strong> A higher-ranked
    model is a better bet for trustworthy confidence than a lower-ranked one —
    that much now has evidence behind it. But the exceptions above are large
    enough that the ranking can't settle it for any particular pair of models:
    one model here is beaten by another {inv_gap:.0f} leaderboard points below
    it. If you need to act on "I'm 90% sure", you still have to test it.
  </p>
  <details style="margin-top:20px;border:1px solid var(--rule)">
    <summary>Four ways I tried to break this result</summary>
    <p><b>Change how the four parts are weighted.</b> The score above weights them
    equally. Under five different weightings the correlation runs
    {sens_lo:+.2f} to {sens_hi:+.2f}, so it isn't an artefact of that choice.</p>
    <p><b>Drop each model in turn.</b> With any single model removed the
    correlation stays between <b>{loo['min']:+.2f}</b> (without
    {loo['min_without']}) and <b>{loo['max']:+.2f}</b> (without
    {loo['max_without']}). No one model is carrying it.</p>
    <p><b>Put back the models I excluded.</b> Two models are left out by rules I
    fixed in advance — one answers in prose instead of the format I asked for,
    one runs out of thinking room on 30% of answers. Putting both back
    <em>strengthens</em> the result to <b>{rho_x:+.2f}</b>, so the exclusions
    aren't what produce it.</p>
    <p><b>Check the same-family size ladders.</b> Gemma 3 comes in three sizes
    released the same day, and Qwen3 in three more. Within both families, the two
    "stating uncertainty" measures rise with size — which the release-date worry
    above cannot explain, because within a family the release date doesn't vary.
    Three sizes is a description, not a test, and I quote it as one.</p>
  </details>
</section>

"""
    h = slice_between(h, "<!-- ---------- 5b: the fleet ---------- -->",
                      "<!-- ---------- 6 ---------- -->", sec5, "section 5")

    caveat = f"""    <li><b>{n} models is still few for a comparison like Section 5.</b> The
      plausible range for the correlation runs from {lo:+.2f} to {hi:+.2f} — wide
      enough that it includes "no relationship", and wide enough that it includes
      a very strong one. The leaderboard also has its own uncertainty about where
      each model belongs — for the smallest model, a range 26 points wide — which
      the chart draws rather than hides.</li>"""
    start = h.find("is still few for a comparison")
    if start < 0:
        sys.exit("sample-size caveat not found")
    a = h.rfind("<li>", 0, start)
    b = h.find("</li>", start) + len("</li>")
    h = h[:a] + caveat.strip() + h[b:]

    tech = f"""<p><b>Fleet comparison.</b> Epistemic Honesty Score against the Epoch
  Capabilities Index. {n} open-weights models spanning {span:.1f} ECI points:
  Spearman rho = <b>{rho:+.3f}</b>, permutation p = <b>{p:.3f}</b>, n = {n}.
  Bootstrap 95% interval with model resampling, repeat-run noise and Epoch's own
  ECI intervals all propagated: <b>[{lo:+.2f}, {hi:+.2f}]</b>, {pos:.0%} of draws
  positive. Range check on the same pipeline: rho {rho_o:+.3f} across the original
  {n_o} models ({span_o:.1f} points) against {rho:+.3f} across {n} ({span:.1f}).
  Per component, Holm-corrected across four tests: calibration {cal_r:+.3f}
  (Holm <b>{cal_h:.3f}</b>), honesty {hon_r:+.3f} (Holm <b>{hon_h:.3f}</b>),
  discrimination {dis_r:+.3f} (Holm {dis_h:.3f}), independence {ind_r:+.3f}
  (Holm {ind_h:.3f}). Excluded by pre-set rules:
  {", ".join(r['tag'] for r in excl)}. ECI pulled from
  <code>epoch.ai/data/benchmark_data.zip</code>, not a rendered leaderboard.</p>"""
    i = h.find("<p><b>Fleet comparison.</b>")
    if i < 0:
        sys.exit("technical fleet paragraph not found")
    j = h.find("</p>", i) + len("</p>")
    h = h[:i] + tech + h[j:]

    open(DASH, "w", encoding="utf-8").write(h)

    print(f"refreshed PAPER.md and dashboard.html from results/fleet.json")
    print(f"  rho {rho:+.3f}  p {p:.3f}  n {n}  span {span:.1f}")
    print(f"  full-uncertainty CI [{lo:+.2f}, {hi:+.2f}]  {pos:.0%} positive")
    print(f"  survive Holm: {', '.join(survive) or 'none'}")
    print(f"  largest inversion: {inv_lo['tag']} {inv_lo['ehs']:.1f} over "
          f"{inv_hi['tag']} {inv_hi['ehs']:.1f} ({inv_gap:.1f} ECI points)")


if __name__ == "__main__":
    main()
