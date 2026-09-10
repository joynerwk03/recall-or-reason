# Asking the same model the same question two ways

**A benchmark separating expressible uncertainty from held uncertainty, and
recall from reasoning, on 80 primary-sourced statistics — and what it finds
across ten models**

William Joyner · draft of 2026-09-10 · *not published; every number below is
reproducible from this repository*

---

## Abstract

We evaluate two locally-run 24B language models on 80 real-world statistics,
each with a verified primary source and a tag naming the worldview it
contradicts. Asked to pick an answer and state a confidence from 0 to 100,
neither model ever states a confidence below 80 across 160 answers, and the more
accurate model is miscalibrated (ECE 0.092) in the familiar overconfident
direction. Asked instead for a point estimate and an 80% interval on the same
items, that same model covers the truth **72% of the time [58.3, 82.5]** —
statistically indistinguishable from the 80% requested. Its interval widths
track its errors (Spearman +0.647) and beat a shuffled-pairing null by 54.8
points, so the intervals are *placed*, not merely wide.

The uncertainty was there. The percentage scale could not carry it.

The rescue is not free: the weaker model covers 32.0% under the identical
request and is overconfident in both formats. Format gives a model a way to
express uncertainty; it does not create uncertainty the model lacks.

We then test recall against reasoning with 8 hand-built perturbed variants —
the same claim moved to a different year, country or population, each with its
own verified answer — plus one null control whose answer barely moves. The
stronger model produces **0/8** anchor echoes; the weaker produces **5/8**
(Fisher exact *p* = 0.026), answering with the current figure when asked about
2012, the US figure when asked about Canada, and twice repeating a number the
prompt itself supplied.

**Extended to ten models** spanning 22.6 points of the Epoch Capabilities Index,
the strongest result in this paper is a null: **general capability does not
predict epistemic honesty** (Spearman rho = +0.25, permutation p = 0.49, stable
across five weightings of the composite). Models a leaderboard treats as
equivalent differ by 27 points on it; a model 20 index points weaker than
another matches it. Calibration alone trends with capability, but does not
survive correcting for having tested four components. If you want to know
whether a model's stated confidence means anything, its leaderboard position
will not tell you.

Finally we document four ways this instrument produced confident wrong numbers
before those numbers were checked, and a further three found while scaling to
ten models. We think those sections are the most useful part of the paper.

---

## 1. What this measures and why

Benchmarks built on real-world statistics have a standing problem: a model that
reasons its way to roughly the right number and a model that saw the number
during training score identically. That makes the score close to useless for the
thing people actually want to know.

A second problem is quieter. Stated confidence is routinely read as if it were a
probability. If a model says 90, users act as though it is right nine times in
ten. Whether that number carries information is an empirical question and is
rarely asked.

This benchmark measures three things a single accuracy figure hides:

1. **Accuracy**, against a *per-item* chance baseline (options vary 3-4, so a
   flat 25% would flatter the model). Baseline here: **26.8%**.
2. **Calibration** — when it says 90, is it right 90% of the time?
3. **Recall versus reasoning** — does the answer move when the question moves?

### 1.1 The item set

80 questions inherited from *Priors*, a worldview quiz whose entire bank was
verified against primary sources before release. Each item carries the answer,
the source, and a `punctures` tag naming which worldview the finding
contradicts. That tagging is the rare part: it turns "the model was wrong" into
"the model was wrong in a *direction*", which is measurable.

50 of the 80 have a numeric answer and are the ones usable for interval work.
Items are selected on importance and evidence, never to balance the tag column —
the skew tally is a diagnostic, never a target.

### 1.2 Models

| | devstral-small-2 | lfm2 |
|---|---|---|
| parameters | 24.0B | 23.8B |
| architecture | `mistral3`, dense | `lfm2moe`, mixture-of-experts |
| quantisation | Q4_K_M | Q4_K_M |

**These models are the same size.** Their on-disk footprints (15GB and 14GB)
read like a large model and a small one and are not; the difference is
architecture. Any result below that looks like a scale effect is not one — this
study contains no scale ladder, and would need a model pulled at a genuinely
different size to have one.

### 1.3 Decoding

All quoted numbers come from models with sampling pinned in the model itself
(`temperature 0`, `top_p 1`, `top_k 1`, `seed 42`) via a Modelfile — the `-t0`
variants built by `pin_models.sh`. Section 5.1 explains why this is not the
throwaway methods sentence it appears to be.

🔴 **Correction, 2026-09-10: pinning does not buy full reproducibility, and it
is model-dependent.** An earlier version of this section claimed the runs were
"verified deterministic" on the strength of three identical calls on one prompt.
Measured across the whole bank:

| | repeat runs | items differing |
|---|---|---|
| gemma3:4b | 3 | **0 / 50** |
| devstral-small-2 | 2 | **6 / 50** |

Same weights, same pin, same parameters. The small model is bit-reproducible;
the 24B model is not — almost certainly non-associative floating-point reduction
whose order depends on batch and KV-cache state, which the larger model reaches
by a different execution path on this hardware. The practical consequence is
that **every devstral figure in this paper carries run-to-run noise**, measured
at roughly 2.4 points of the composite score in Section 8. Differences smaller
than that are not differences between models. A single verified prompt was not
evidence of determinism, and generalising from it was the same mistake as 5.1
in a smaller costume.

---

## 2. Result 1: the format decides whether uncertainty is expressible

### 2.1 Multiple choice with stated confidence

80 items, each answer carrying a confidence from 0 to 100.

| | devstral-t0 | lfm2-t0 |
|---|---|---|
| accuracy | **80.0%** [70.0, 87.3] | 48.8% [38.1, 59.5] |
| chance baseline | 26.8% | 26.8% |
| ECE | **0.092** | 0.430 |
| confidence values used | 80, 85, 90, 95 | 85, 90, 95, 100 |
| lowest confidence stated | 80 | 85 |

**Across 160 answers, neither model ever stated a confidence below 80.** Between
them they had four-fifths of the scale available and never touched it. Each used
exactly four distinct values all day.

This is not ordinary miscalibration. A miscalibrated model returns numbers that
are wrong; these models return numbers that are barely numbers, because a scale
exercised only from 80 to 100 is not measuring confidence, it is decorating an
answer. The weaker model told us it was at least 85% sure on every one of the 41
questions it got wrong.

Two things complicate the obvious pessimistic reading. Calibration does improve
with measured accuracy — the better model's ECE is 4.7x smaller. And the
ordering is informative even where the numbers are not: in both models, answers
stated at 95 were likelier to be right than answers stated at 85. Each model
knows which of its answers are better. It cannot say so on a percentage scale.

### 2.2 The same items, asked for an interval

The 50 numeric items, with an estimate and an 80% interval requested instead of
a choice.

| | devstral-t0 | lfm2-t0 |
|---|---|---|
| **coverage** (80% requested) | **72.0% [58.3, 82.5]** | 32.0% [20.8, 45.8] |
| verdict | indistinguishable from nominal | overconfident |
| median relative width | 0.70 | 0.91 |
| width vs error (Spearman, raw) | **+0.647** | +0.460 |
| shuffle null | 17.2% | 18.9% |
| margin over null | **+54.8** | +13.1 |
| estimate outside its own interval | 0/50 | 3/50 |

**devstral's 72% coverage contains the 80% it was asked for.** The same model,
on the same 50 questions, never once claimed to be less than 80% sure when the
answer had to be a percentage.

### 2.3 Two controls, because coverage alone proves nothing

A model answering "somewhere between 0 and 100" every time covers 100% of the
truth and knows nothing. Coverage is only meaningful against width.

**The shuffle null.** Score each interval against a *different* item's truth,
averaged over 2000 derangements. If the intervals were uniformly wide they would
bracket anything and the number would barely move. devstral falls from 72.0% to
17.2% — a **54.8 point** margin. The intervals are placed, not merely wide.
lfm2's margin is 13.1, and the scorer says outright that its intervals would
bracket almost any answer in the set.

**The subset control.** Interval mode uses only the 50 numeric items, so the
choice-mode run was rescored on exactly those 50. If that subset were simply
easier, it would explain the whole effect. It went the other way for both
models: devstral's ECE rises from 0.092 on the full bank to **0.122** on those
50, and lfm2's from 0.430 to 0.514. The subset is harder, not easier, so the
interval result is not inherited from an easy subset.

### 2.4 Result 2: the rescue is capability-dependent

lfm2 covers 32.0% against the same 80% request and is overconfident in both
formats. The format is not a magic trick. It gives a model a channel through
which to express uncertainty; one of these two had little to express.

---

## 3. Result 3: recall versus reasoning

### 3.1 Design

Eight perturbed variants, each moving one thing — the year, the country, the
population, the follow-up window — to a value where the true answer genuinely
differs, with the prompt's anchor kept verbatim. Every variant answer traces to
a primary source recorded inline in `build_variants.py` with the date checked:
Gallup, Pew, EPI, Statistics Canada, BJS, EPA.

| variant | original -> perturbed | shift |
|---|---|---|
| `muslim-share@france` | 1% -> 8.8% | 780% |
| `scientists-god@public` | 50% -> 95% | 90% |
| `ceo-pay@1989` | 340x -> 61x | 82% |
| `interracial-marriage@1978` | 94% -> 36% | 62% |
| `lgbt-share@2012` | 9% -> 3.5% | 61% |
| `creationism-share@1999` | 37% -> 47% | 27% |
| `gun-suicides@canada` | 60% -> 75% | 25% |
| `recidivism@3year` | 80% -> 68% | 15% |
| `plastic-recycling@us` **(null control)** | 9% -> 8.7% | **3%** |

**The null control is the load-bearing part of the design.** It perturbs the
question without meaningfully perturbing the answer. If a model degrades there
too, then whatever is hurting it is the *rewording*, and no gap on the real
variants can be read as memorisation. Both models pass it.

### 3.2 Anchor echo, and why it is the measure that survives

The natural headline is the **gap**: relative error on the variant minus
relative error on the original. It is nearly useless for comparing models,
because it is only defined where the model got the *original* right. A model
that is wrong everywhere contributes almost no eligible pairs — lfm2 contributes
one — so the gap cannot separate "robust to perturbation" from "too inaccurate
to test". Worse, without that eligibility filter the metric **inverts**: a model
already 96% wrong has no room to degrade and scores as robust (Section 5.3).

**Anchor echo has neither problem.** An answer is an echo when the estimate
lands closer to a figure the model was already holding — the answer to the
unperturbed question, or a number quoted in the prompt — than to the truth. It
is defined on every item regardless of baseline accuracy, it is scale-free, and
it asks exactly the question the benchmark exists to ask: *did the model answer
the question in front of it, or the one it remembered?*

| | devstral-t0 | lfm2-t0 |
|---|---|---|
| anchor echoes | **0/8** | **5/8** |
| median gap (eligible pairs) | -0.01 (n=5) | +0.12 (n=1) |
| null control | +0.08, holds | +0.15, holds |

**Fisher exact, two-tailed: *p* = 0.026.**

lfm2's five echoes, in its own numbers:

| variant | said | truth | echoing |
|---|---|---|---|
| `lgbt-share@2012` | 10 | 3.5 | the *current* figure |
| `gun-suicides@canada` | 60 | 75 | the *US* figure |
| `scientists-god@public` | 62 | 95 | the *scientists'* figure |
| `ceo-pay@1989` | **21** | 61 | the 1965 ratio **stated in the prompt** |
| `interracial-marriage@1978` | **6** | 36 | the 1958 figure **stated in the prompt** |

The last two require no recall at all. They are the prompt echoing back.

devstral, on the same eight, moved with every perturbation — 75% for Canada, not
the US 60%; 8.8% for France, not the US 1%; 61x for 1989, not 340x.

### 3.3 What this does and does not establish

It rules out **reciting a single headline figure**. It does not rule out recall.
These variants are verifiable precisely *because* one primary source publishes
the whole series or cross-section — and that same property makes the variant
answers well-published too. A model that had memorised the entire Gallup trend
table would pass this test cleanly.

Escaping that would require variants whose answers are not published anywhere,
which means computing them, which means they can no longer be checked against a
source. We do not have a way around this tension and we do not think it should
be papered over.

**n = 8, and 8 is small.** The direction is clear, the failure mode is legible,
and *p* = 0.026 is one experiment rather than a replication.

### 3.4 Why 8 and not 20

Scaling the variant set is harder than it looks, for a structural reason worth
recording. We ranked all 50 numeric items by how well *both* models answered the
original, on the theory that only those carry information. Most of the resulting
shortlist turned out to be **unperturbable**: single famous studies — one public
health estimate on vaping, one twin study, one exoneration analysis — with no
other year, country or subgroup to move to.

Perturbation needs *repeatedly measured* quantities: polls, national statistics,
tracked databases. A bank assembled for interest and evidential quality is not
automatically a bank of time series, and this constrains the method more than
the labour of sourcing does.

---

## 4. Ideological skew

Every item carries a tag naming the prior it punctures, so error direction is
measurable rather than impressionistic. **This is a diagnostic and never a
target**; selecting items to balance the column would itself be a bias.

At n = 80 split across six tags, the per-tag intervals are far too wide to
support any claim. We report the tally because withholding it would be worse,
and we decline to interpret it.

---

## 5. Four ways this instrument lied, and how each was caught

Every result above survived a bug that had already produced a confident,
plausible, wrong number. We list them because the fixes are the reusable part.

### 5.1 Non-determinism wearing the costume of determinism

`ask_cli` invoked `ollama run` with no sampling options, while the HTTP function
*directly beneath it* set `temperature: 0` and carried the comment
"Deterministic, so a re-run of the same items is comparable." On this machine
Ollama binds loopback on the Windows side, so the CLI path is the one that runs.
Every number for three days was a single draw from a stochastic decode.

The first fix was worse than the bug. Piping `/set parameter temperature 0`
ahead of the prompt looked like it worked — three calls returned an identical
answer. But `ollama run` with piped stdin treats *all* of stdin as the prompt,
so that line was never a command; it was **silently prepended to every question
as text**. The tell was there and initially missed: the "pinned" answer (20) was
not one of the values the unpinned run had ever produced (1, 2). *Temperature 0
narrows a distribution; it does not move it somewhere new.* Two subsequent runs
of the full bank then differed on **35 of 50 items**.

Sampling is now pinned in the model, via Modelfile, and verified on the real
harness prompt rather than a toy one.

> **The lesson.** A comment asserting a property is not a test of that property,
> and the path with the comment on it was not the path that ran. Verify the
> property on the real input, and treat *an answer outside the original support*
> as evidence your intervention changed the question.

### 5.2 A parser that manufactured accuracy

The interval parser accepted three bare numbers in the prompted `ESTIMATE, LOW,
HIGH` order when labels were dropped. lfm2 emits ascending triples — `0 / 5 /
10`, `4 / 10 / 20` — which is the ordinary `LOW, ESTIMATE, HIGH` way of writing
a range. Read the wrong way round, the estimate lands outside its own interval
every time.

This produced **11 of lfm2's 12 "incoherent" answers**, which had been reported
as a finding about the model. It also produced a worse artefact: on an item
whose truth was 9, lfm2's `9 / 90 / 100` was read as *estimate 9*, scoring a
**perfect baseline error of 0.00** off a misread — which then made a well-formed
wrong answer on the variant look like catastrophic degradation.

The parser now disambiguates by ordering (first value inside the other two ->
prompted order; strictly ascending -> low/estimate/high) and flags genuine
garble. Six answers that were single bare numbers, previously discarded whole,
now keep their estimate and are excluded only from coverage. After the fix both
models parse 50/50.

> **The lesson.** Lenient parsing buys coverage and pays in ground truth. A
> tolerant fallback must be *unambiguous*, not merely tolerant — and any parse
> that yields a self-contradictory answer should be treated as a suspected
> misparse before it is treated as a finding about the model.

### 5.3 A metric that inverted under a ceiling effect

The first scoring of the perturbation experiment reported lfm2 at median -0.05
and printed "no meaningful degradation" — the opposite of the truth. A model
already 60-96% wrong on an original has no room to get worse, so being wrong
twice scored as robust. Restricting to pairs where the model got the original
within 15% moved lfm2 from -0.05 to +0.51.

This is also why Section 3.2 leads with anchor echo rather than the gap.

### 5.4 A correlation that reversed the model ranking

Interval width and error were both normalised by `max(|truth|, 1)`. Two ratios
sharing a denominator correlate even when the underlying quantities are
independent — Pearson's spurious correlation of ratios, 1897. The distortion was
large and had **no consistent sign**: devstral 0.761 raw -> 0.281 normalised,
lfm2 0.312 -> 0.501. Reported that way it would have reversed the two models'
ranking. The scorer now reports the raw correlation and prints the normalised
one beside it only as a standing warning.

---

## 6. Does general capability predict epistemic honesty? Ten models

Everything above concerns two models. The obvious question is whether any of it
is a property of *models* or of *those* models — and behind that, a sharper one:
if a better model is automatically more honest about its own uncertainty, this
benchmark is measuring general capability the expensive way and does not need to
exist.

### 6.1 Design

Ten locally-run open-weights models, spanning **116.0 to 138.5** on the
**Epoch Capabilities Index** — 22.6 points, roughly the distance from Gemma 3 4B
to Qwen3-32B. ECI stitches 50+ benchmarks onto one scale by comparing models
evaluated on more than one of them, so it stays meaningful after any single
benchmark saturates.

ECI is taken from Epoch's own machine-readable release
(`epoch.ai/data/benchmark_data.zip`), not transcribed from a rendered
leaderboard. That was not fastidiousness: two attempts at reading interactive
leaderboards through a page summariser returned figures that disagreed with each
other.

Each model is reduced to one **Epistemic Honesty Score** (0-100), the mean of
four components — calibration, interval honesty scaled by sharpness,
discrimination, and independence from anchors. **EHS contains no accuracy term
by construction.** Had it rewarded getting answers right it would partly *be* a
capability index, and any correlation below would be guaranteed rather than
discovered.

### 6.2 Result

| model | ECI | EHS | calib | honesty | disc | indep |
|---|---|---|---|---|---|---|
| gemma3:4b | 116.0 | 33.5 | 8 | 20 | 30 | 75 |
| llama3.1:8b | 116.5 | 54.7 | 56 | 39 | 37 | 88 |
| gemma3:12b | 123.5 | 75.2 | 71 | 74 | 56 | 100 |
| mistral-small:24b | 127.1 | **87.6** | 82 | 99 | 69 | 100 |
| gemma3:27b | 130.0 | 69.8 | 88 | 84 | 45 | 62 |
| phi4:14b | 130.4 | 65.5 | 66 | 61 | 35 | 100 |
| qwen3:8b | 136.2 | 53.4 | 73 | 54 | 36 | 50 |
| gpt-oss:20b | 137.8 | 55.2 | 67 | 53 | 26 | 75 |
| qwen3:14b | 138.2 | 65.1 | 82 | 58 | 44 | 75 |
| qwen3:32b | 138.5 | 82.2 | 94 | 98 | 50 | 88 |

Not on the capability axis, because Epoch does not score them:
devstral-small-2 **83.6**, lfm2 **26.7**. They are reported rather than dropped,
but they cannot enter the correlation — which is awkward, since devstral is one
of the strongest models in the set on this benchmark.

**Spearman rho = +0.25, permutation p = 0.49, n = 10.** No relationship
separable from chance.

The conclusion does not depend on how the composite is weighted. Under five
different weightings rho stays between +0.19 and +0.35 and p never falls below
0.33:

| weighting | rho | p |
|---|---|---|
| equal | +0.248 | 0.495 |
| intervals-heavy | +0.333 | 0.351 |
| calibration-heavy | +0.345 | 0.331 |
| memorisation-heavy | +0.188 | 0.609 |
| drop discrimination | +0.248 | 0.495 |

### 6.3 The components move in different directions

A composite can hide components pulling against each other, and here they do:

| component | rho vs ECI | p | Holm-adjusted |
|---|---|---|---|
| calibration | **+0.661** | 0.044 | 0.176 |
| honesty | +0.321 | 0.370 | 1.000 |
| discrimination | -0.006 | 1.000 | 1.000 |
| independence | **-0.231** | 0.519 | 1.000 |

Calibration — does a stated 90 mean 90 — is the one component that trends with
capability, and it is the one people usually mean by "is the model
well-calibrated". **But four components were tested against the same axis, and
after Holm correction the calibration result does not survive.** Reported here
as a hypothesis worth re-testing on a larger fleet, not as a finding. Quoting
p = 0.044 without that correction would be the multiple-comparisons version of
every other mistake in Section 5.

The independence correlation is *negative*. More capable models echoed a figure
they were already holding slightly **more** often, not less — which is at least
consistent with more capable models having memorised more, though at this n it
is indistinguishable from noise and should not be leaned on.

### 6.4 What the spread actually looks like

The clearest way to see the null is to look at models that are close on one axis
and far apart on the other:

- **mistral-small:24b scores 87.6 at ECI 127.1.** gpt-oss:20b, **10.7 ECI points
  more capable**, scores 55.2.
- **qwen3:8b (ECI 136.2) scores 53.4. llama3.1:8b, 19.7 ECI points weaker,
  scores 54.7.** Twenty points of general capability buy nothing here.
- The three most capable models in the set — qwen3:32b, qwen3:14b, gpt-oss:20b,
  within 0.7 ECI points of each other — score **82.2, 65.1 and 55.2**. A 27-point
  spread among models that a capability leaderboard treats as equivalent.

**The practical reading.** If you are choosing a model and you care whether its
stated confidence means anything, its position on a general capability
leaderboard will not tell you. That is the case for a benchmark like this one
existing, and it is the strongest result in this paper — considerably stronger
than anything in Sections 2 to 4, which rest on two models.

### 6.5 Limits specific to this comparison

- **n = 10 models.** A rank correlation on ten points has a very wide interval
  whichever way it lands. A null at this n is "no relationship detected", not
  "no relationship".
- **ECI carries its own confidence intervals**, several of them more than ten
  points wide (Gemma 3 4B: [97.5, 123.4]). The capability axis is not precise
  either, and the chart draws those intervals rather than hiding them.
- **Reasoning-mode ambiguity for the three Qwen models.** Epoch lists separate
  reasoning and non-reasoning entries for some Qwen sizes but only a plain entry
  for these, and does not state which mode it evaluated. The harness lets them
  think and strips the scratchpad. The plain entry is the closest available
  match; that is a limitation of the join, not something the join can fix.
- **Truncation is not neutral.** qwen3:8b and gpt-oss:20b ran out of token
  budget mid-thought on 3 and 5 answers respectively. Those record no answer
  rather than a scavenged one, but a reasoning model runs out of budget on the
  items it thinks longest about, so excluding them may flatter those two models.
- **Everything is Q4_K_M quantised and locally run**, while ECI scores the
  full-precision hosted model. That is a real mismatch on both axes at once.

## 7. Limitations

- **Two models, one prompt version, one language.** Everything here could be a
  property of this prompt.
- **n = 80 items; n = 50 for intervals; n = 8 for perturbations.**
- **No scale ladder.** The two models are the same size. Nothing here speaks to
  how any of this varies with scale.
- **The perturbation caveat of Section 3.3**, which more items will not fix.
- **One ground-truth defect found and not yet repaired:** the `extreme-poverty`
  item states a 1990 anchor of 36% while the World Bank's $3.00 (2021 PPP)
  series puts 1990 at 43.4% and 36.2% at 2000. The item appears to pair a
  current answer with an anchor from another vintage. It is excluded from the
  variant work and flagged for repair.
- **Local quantised models.** Q4_K_M is lossy; these are not the full-precision
  models.

## 8. What we would do next

1. **More variants**, weighted toward repeatedly-measured quantities
   (Section 3.4) - roughly 20 would let the echo contrast carry an interval
   rather than a single *p*.
2. **A real scale ladder** — the same bank against 3B / 8B / 24B of one family,
   which is the only way to ask whether echo rate falls with scale.
3. **A frontier API model**, to test whether the format effect survives at the
   capability level people actually deploy.
4. **Elicit the interval first, the choice second**, to check the format effect
   is not an ordering effect.

---

## Reproducing

```bash
./pin_models.sh                                    # build the -t0 models
./run.sh extract_items.py                          # bank -> data/items.jsonl
./run.sh build_variants.py                         # -> data/variants.jsonl
./run.sh run_eval.py --mode choice   --model devstral-t0
./run.sh run_eval.py --mode interval --model devstral-t0
./run.sh run_eval.py --mode interval --model devstral-t0 \
         --items data/variants.jsonl --tag variants
./run.sh score.py           results/<choice run>.jsonl
./run.sh score_interval.py  results/<interval run>.jsonl
./run.sh score_variants.py  results/<variants run>.jsonl results/<interval run>.jsonl
./run.sh compare_models.py  results/<A variants>.jsonl results/<B variants>.jsonl
```

Every dated claim, including the ones that turned out wrong, is in `LOG.md`.
