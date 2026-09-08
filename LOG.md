# Research log

Dated entries: hypothesis → what was done → numbers → verdict. Modelled on
ConceptChess's loop. **Negative and boring results are recorded the same as
interesting ones**; a log that only contains wins is a marketing document.

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
