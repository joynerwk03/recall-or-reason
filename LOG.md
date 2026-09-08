# Research log

Dated entries: hypothesis → what was done → numbers → verdict. Modelled on
ConceptChess's loop. **Negative and boring results are recorded the same as
interesting ones**; a log that only contains wins is a marketing document.

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
