# Research log

Dated entries: hypothesis → what was done → numbers → verdict. Modelled on
ConceptChess's loop. **Negative and boring results are recorded the same as
interesting ones**; a log that only contains wins is a marketing document.

---

## 2026-09-08 — both models: calibration tracks capability, and neither model
## ever admits doubt

**What.** Full 80 items on both local models. 80/80 parsed for lfm2, 80/80 for
devstral-small-2 (one answer carried no confidence).

| | lfm2 | devstral-small-2 |
|---|---|---|
| accuracy | 46.2% [35.7, 57.1] | **78.8% [68.6, 86.3]** |
| chance | 26.8% | 26.8% |
| ECE | 0.460 | **0.104** |
| stated 85 → right | 32% | 73% |
| stated 95 → right | 52% | 87% |

**Finding 1: calibration tracks capability.** The more accurate model is also
the far better calibrated one, by a factor of four on ECE. Both still sit below
the diagonal, so both overclaim, but the gap shrinks sharply with capability.
That is a cleaner statement than "models are overconfident" and it is the
headline of the run.

**Finding 2, and the more interesting one: neither model ever expresses real
uncertainty.** Across **159 answers the lowest confidence either model ever
stated was 80.** Not once did either say 40, or 60, or "I don't know". lfm2 used
five distinct values (80, 85, 90, 95, 99); devstral used **two** (85, 95).

That reframes the problem. The confidence channel is not badly calibrated so
much as **barely used**: both models operate in the top fifth of the scale and
never touch the rest of it. A model at 46% accuracy that never says it is less
than 80% sure is not making a calibration error, it is declining to represent
doubt at all.

Note the counterintuitive detail: the *better* model uses the *coarser*
vocabulary. Two values, better calibrated. So expressive range and calibration
are not the same axis.

**Finding 3: confidence is ordinally informative in both.** 95 beats 85 in both
models (52 vs 32, and 87 vs 73). They do know which of their answers are better.
They cannot say so on a 0–100 scale, and they never use the low end.

**Skew: still unmeasured, in both.** devstral runs Right 77.4%, Left 75.0%,
Secular 75.0%, with intervals 25–35 points wide. Nothing separable.
**Do not report a skew result from 80 items.**

⚠️ **A prediction of mine was wrong.** The 2026-09-07 entry guessed, from three
items all reading 85, that confidence might be constant. Across 80 it is not.
The three-item sample could not see it — the exact error the scorer is built to
refuse, made by me rather than by the scorer.

🔴 **The result that most needs interrogating: devstral scoring 78.8%.** These
questions were written so reasoning beats recall, and a 15GB model getting four
in five on contested public statistics is exactly what memorisation would look
like. **This is not evidence of a world model until the memorisation probe runs.**
It is the strongest argument yet for checkpoint 3, and the number should not be
quoted as a capability result before then.

**Chart.** `results/calibration.png`, both models.

**Next.** Interval elicitation on the 50 numeric items. The motivation is now
sharper than "try another channel": the models never use the low end of a
percentage scale, so the question is whether an interval is a format in which
they *can* express doubt. If interval widths also collapse to near-zero, the
finding is about the models' unwillingness to represent uncertainty in any
format, which is a bigger claim than a calibration number.

---

## 2026-09-08 — full sweep, lfm2: real signal, badly miscalibrated

**What.** All 80 items, one model, multiple choice with stated confidence.
80/80 parsed, no errors.

```
accuracy         37/80 = 46.2%   95% CI [35.7, 57.1]
chance baseline  26.8%           (per-item; options vary 3-4)
verdict          above chance
ECE              0.460

stated 85  ->  right 32%   (22 answers)
stated 95  ->  right 52%   (58 answers)
```

**Finding 1: there is real signal.** 46.2% against a 26.8% baseline, with the
interval clearing it. The model is not guessing. That matters because it means
the calibration result below is about a model that partly knows things, not one
producing noise.

**Finding 2: stated confidence is worth almost nothing in absolute terms.**
Every bin sits far below the diagonal. It says 95 and is right half the time.
ECE 0.460 is not "poorly calibrated", it is closer to uninformative as a
probability.

**Finding 3, and the one worth chasing: confidence carries ORDINAL information
but not CARDINAL.** The 95 bin (52%) genuinely outperforms the 85 bin (32%), so
the model does know which of its answers are better. It simply cannot express
that on a 0–100 scale. **Ranking works, numbers do not.** That is a more useful
and more publishable claim than "it is overconfident", which everyone already
believes.

⚠️ **A hypothesis of mine was wrong and is recorded as such.** After three items
all returning 85, the 2026-09-07 entry predicted confidence might be constant
across the bank. It is not: values range 80–95. The three-item sample was too
small to see it, which is exactly the error this project's scorer is built to
refuse. The revised finding (compressed but non-degenerate, ordinally
informative) is better than the one I guessed.

**Skew: unmeasured, and the scorer says so.** Right 45.2%, Left 50.0%, Both
50.0%, Secular 50.0%, with intervals spanning roughly 30 points each. Nothing is
separable at this item count. Religious is 0/2, which means nothing whatsoever.
**Do not report a skew result from this run**; the honest statement is that 80
items cannot resolve it.

**Chart.** `results/calibration.png`, reliability diagram with bin counts as
bubble area and Wilson intervals.

**Consequence for checkpoint 3.** Interval elicitation is still the right next
probe, but for a changed reason. Not "confidence is useless so try something
else" — rather, the model has a usable internal ordering it cannot express as a
percentage, and an interval may be a channel it can actually use. Numeric
extraction for that mode is built (`numeric_answer` in `extract_items.py`).

---

## 2026-09-07 — v1 harness, first end-to-end run

**What.** Built the item extractor, the runner and the scorer, and put one
local model through three items to prove the path works.

**Item set.** 80 questions extracted from the Priors bank, every one carrying a
verified answer and a `punctures` tag. Tally: Right 31, Left 24, Both 12,
Secular 8, Religious 2, plus four mixed. **This independently reproduces the
tally William reviewed by hand in August**, which is a real check on both the
parser and that audit.

**A parse bug worth recording.** The first extraction produced 79 of 80.
`vaping-harm` was silently dropped because its prompt is double-quoted in the
source (the text contains an apostrophe) and the regex matched single quotes
only. Ground truth integrity is invariant 1, so a quiet 1-in-80 loss is a real
defect, not a rounding error. `check_coverage.py` exists so the next one is
loud.

**Transport.** Ollama runs on the Windows side of this machine and binds
loopback only; WSL cannot reach it over HTTP without a firewall rule this
account cannot add. WSL *can* execute Windows binaries, so the runner falls
back to driving `ollama.exe` directly. Its stdout carries progress-spinner
escape codes even when piped, which are stripped.

**Numbers (lfm2, 3 items).**

```
accuracy         1/3 = 33.3%   95% CI [6.1, 79.2]
chance baseline  27.8%          (per-item; options vary 3-4)
verdict          NOT distinguishable from chance
confidence       85 on all three answers
```

**Verdict.** Harness ACCEPTED. The measurement itself says nothing yet and the
scorer correctly refuses to pretend otherwise.

**One early observation worth chasing.** The model returned exactly 85
confidence on every item. If that holds across the full bank it is a finding in
itself: stated confidence carrying no information at all is a cleaner negative
result than poor calibration, and it would mean the confidence channel needs a
different elicitation before any calibration claim is possible.

**Next.** Full 80-item sweep on both local models, then decide whether interval
elicitation or perturbed variants is the cheaper route to the memorisation
probe.
