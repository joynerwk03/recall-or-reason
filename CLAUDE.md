# Recall or Reason

A benchmark that separates **having a world model** from **having memorised the
answer**, and measures whether a model's stated confidence is worth anything.

Registry entry: `~/mission-control/projects/recall-or-reason.md`. Every dated
result, including the ones that turned out wrong: `LOG.md`. Write-up:
`PAPER.md`. Ground-truth checks against sources: `AUDIT.md`.

## The question

Most benchmarks that use real-world statistics cannot tell the difference
between a model that reasons its way to roughly the right number and one that
saw the number during training. Both score the same. That makes the score
almost useless for the thing people actually want to know.

This benchmark measures the difference directly, and it measures things a
single accuracy number hides:

1. **Accuracy** — can it get the answer.
2. **Calibration** — when it says 90% sure, is it right 90% of the time?
   Overconfidence on contested empirical claims is the failure that matters,
   because that is the one a user acts on.
3. **Recall versus reasoning** — does the answer move when the question moves?
4. **Skew** — do errors correlate with *which worldview* the finding
   contradicts? Every item is tagged with the prior it punctures.

## Invariants (do not break these)

1. **Every item's answer traces to a primary source.** A benchmark whose ground
   truth is wrong is worse than no benchmark. Items whose answer or prompt fails
   against its own cited source are excluded from scoring —
   `epistemic_score.DISPUTED`, evidence in `AUDIT.md` — and never "fixed" here:
   the Priors bank is a separate project with its own owner.
2. **Items are selected on importance and evidence, never to balance a column.**
   Selecting for balance is itself a bias; the skew tally is a *diagnostic*,
   never a target.
3. **Report the negative results.** A null is a finding and gets written up as
   one — with its confidence interval, so "not detected" is never dressed up as
   "no effect".
4. **Never quote a score without the model, the prompt version and the item
   set.** A bare number here means as little as a bare Elo does.
5. **Decoding is pinned in the model, never in the prompt.** `ollama run` with
   piped stdin treats all of stdin as the prompt, so a `/set parameter` line is
   silently prepended to the question as text. Quote numbers only from the `-t0`
   models built by `pin_models.sh` (temperature 0, seed 42, `num_predict`
   8192). Even pinned, the larger models are not bit-reproducible run to run,
   which is why every model gets repeat runs.
6. **A result file that exists is not a result.** Completeness is a row count
   against the current item set (`have_complete.py`). Four interrupted runs once
   passed an existence check and produced a retracted table.
7. **Capability numbers come from machine-readable releases**, never from a
   rendered leaderboard read through a summariser. `fetch_eci.py` pulls Epoch's
   own data; two leaderboard reads once disagreed with each other.
8. **Numbers in the write-up are generated, never typed.** `refresh_writeup.py`
   rebuilds the abstract, PAPER section 6 and the dashboard from
   `results/fleet.json`, deriving the claims that depend on the pattern of
   results as well as the figures. A table typed by hand is what produced the
   retracted comparison of 2026-09-10.

## Design

- **Multiple choice plus stated confidence** — the Priors bank as it is: 80
  questions, one verified answer each. Gives accuracy and calibration.
- **Interval elicitation** — the 50 numeric items, answered with an estimate and
  an 80% interval. Tests whether the uncertainty a model cannot state on a
  percentage scale shows up in a range.
- **Perturbed variants** — `build_variants.py`: the same claim moved to another
  year, country or population, each with its own sourced answer, plus a null
  control whose answer barely moves. Measures whether a model answers the
  question in front of it or the one it remembered.
- **Epistemic Honesty Score** — `epistemic_score.py`: four components, and
  deliberately **no accuracy term**, so any relationship with capability is
  discovered rather than built in.
- **Capability comparison** — `compare_capability.py`: EHS against the Epoch
  Capabilities Index, with bootstrap intervals that carry each model's repeat
  noise and Epoch's own uncertainty. The verdict follows the interval.

## The fleet

Eighteen local models through Ollama, from 1.2B to 35B parameters, spanning ECI
102.4 to 146.5. Sixteen are in Epoch's table; devstral-small-2 and lfm2 are not,
so they are run but never plotted against capability. **Model sizes come from
`ollama show`, not the on-disk footprint** — 15GB and 14GB once read as a big
model and a small one and were the same size.

## Running it

Everything goes through `./run.sh`, which uses this project's own `.venv`
(`requirements.txt`). The scoring is stdlib-only; the charts need matplotlib.

```bash
./run.sh extract_items.py        # Priors bank -> data/items.jsonl
./run.sh build_variants.py       # -> data/variants.jsonl
./run.sh fetch_eci.py            # Epoch ECI -> data/eci.csv
bash pin_models.sh               # build the pinned -t0 models
./run.sh fleet_status.py         # what is complete, with parse/truncation counts
./run.sh compare_capability.py --json results/fleet.json
./run.sh plot_fleet.py results/fleet.json
./run.sh ladder.py results/fleet.json   # within-family size ladders
./run.sh refresh_writeup.py            # regenerate the write-up from that JSON
./run.sh budget_effect.py        # what the old 2,500-token budget distorted
```

The full sweep is `sweep_windows.ps1`, run from **Windows** PowerShell. WSL2
shuts the distro down under long invocations, so the loop lives on the Windows
side and each `wsl.exe` call does one model in one mode. It skips any unit
already complete by row count, so resuming the sweep is re-running it.

Ollama is the **Windows** binary, driven from WSL through its CLI; its HTTP
server binds loopback and is unreachable from WSL. Shell-boundary gotchas —
eaten variables, halved backslashes, `pkill` matching itself — are in
`~/mission-control/docs/runbook.md`.

## Definition of done (v1, met 2026-09-08)

- Every item carries its verified answer and its punctures tag.
- One local model runs the full bank end to end and produces a scored report.
- The report states accuracy, a calibration curve with ECE, and the skew table.
- `LOG.md` has an entry with the numbers and a verdict.
- A negative or boring result is written up the same as an interesting one.
