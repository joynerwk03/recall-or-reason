# Recall or Reason

A benchmark that separates **having a world model** from **having memorised the
answer**, and measures whether a model's stated confidence is worth anything.

Registry entry: `~/mission-control/projects/recall-or-reason.md`.

## The question

Most benchmarks that use real-world statistics cannot tell the difference
between a model that reasons its way to roughly the right number and one that
saw the number during training. Both score the same. That makes the score
almost useless for the thing people actually want to know.

This benchmark measures the difference directly, and it measures three things a
single accuracy number hides:

1. **Accuracy** — can it get the answer.
2. **Calibration** — when it says 90% sure, is it right 90% of the time?
   Overconfidence on contested empirical claims is the failure that matters,
   because that is the one a user acts on.
3. **Skew** — do errors correlate with *which worldview* the finding
   contradicts? Every item is tagged with the prior it punctures, so this is a
   direct measurement rather than an impression.

## Invariants (do not break these)

1. **Every item's answer traces to a primary source.** Inherited from Priors,
   where the whole bank was verified before launch. A benchmark whose ground
   truth is wrong is worse than no benchmark.
2. **Items are selected on importance and evidence, never to balance a column.**
   Also inherited. Selecting for balance is itself a bias; the skew tally is a
   *diagnostic*, never a target. See `context/balance-is-not-a-target` in the
   mission-control memory.
3. **Report the negative results.** If the memorisation gap turns out to be
   noise, that is the finding and it gets published as one.
4. **Never quote a score without the model, the prompt version and the item
   set.** A bare number here means as little as a bare Elo does.

## Design

**v1 — multiple choice plus stated confidence.** Uses the Priors bank exactly as
it is: 80 questions, four options, one verified answer, already tagged by the
prior it punctures. The model answers and states a confidence from 0 to 100.
Gives accuracy, calibration (ECE and a reliability curve) and skew immediately,
with no new data work and no parsing risk.

**v2 — the memorisation probe.** This is the novel part and the reason the
project exists. Two approaches, cheapest first:

- **Interval elicitation.** Ask for a point estimate and an 80% interval rather
  than a choice. A model that memorised gives a tight interval and is right; one
  that reasoned gives a wider interval and is roughly right; one that is
  bluffing gives a tight interval and is wrong. The joint distribution of
  *interval width* against *error* separates all three, and no new items are
  needed.
- **Perturbed variants.** Same claim, different country, year or subgroup, where
  the true answer genuinely differs. Recall collapses, reasoning mostly
  survives. **The gap between original and perturbed is the headline number.**
  Expensive, because each variant needs its own verified answer.

**Model ladder.** Local models through Ollama, free, so cost never gates the
work. Scale is meant to be informative rather than incidental: larger models
memorise more, so the gap should *widen* with scale if the probe measures what
it claims.

⚠️ **The two models currently installed are not a scale ladder.**
devstral-small-2 is 24.0B and lfm2 is 23.8B, both Q4_K_M — same size, different
architecture (dense vs MoE). Their 15GB/14GB on-disk footprints look like a big
model and a small one and are not. Do not describe either as "the larger model";
testing scale means pulling a model at a genuinely different size.

## Commands

```bash
python3 extract_items.py                 # priors bank -> data/items.jsonl
python3 run_eval.py --model lfm2 --limit 10        # a real run
python3 run_eval.py --model lfm2 --dry-run         # no model needed
python3 score.py results/<run>.jsonl               # accuracy, ECE, skew
```

Ollama is installed on the **Windows** side of this machine; from WSL reach it
at `http://<windows-host>:11434`. `run_eval.py --list-models` resolves the host
and prints what is available.

## Definition of done (v1)

- Every item carries its verified answer and its punctures tag.
- One local model runs the full bank end to end and produces a scored report.
- The report states accuracy, a calibration curve with ECE, and the skew table.
- `LOG.md` has an entry with the numbers and a verdict.
- A negative or boring result is written up the same as an interesting one.
