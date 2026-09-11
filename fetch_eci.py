#!/usr/bin/env python3
"""Fetch Epoch Capabilities Index scores for the models under test.

Why ECI and not a scraped leaderboard: Epoch ships the whole thing as a
machine-readable zip with per-model confidence intervals, so the capability axis
of the comparison is auditable rather than transcribed off a rendered page. Two
attempts at reading interactive leaderboards through a page summariser returned
figures that disagreed with each other, which is exactly the failure this avoids.

  source: https://epoch.ai/data/benchmark_data.zip
  file:   epoch_capabilities_index/eci_scores.csv
  code:   https://github.com/epoch-research/eci-public

ECI stitches 50+ benchmarks into one scale by comparing models evaluated on more
than one of them, so it stays meaningful after any single benchmark saturates.
Higher is better; the frontier sits near 166 as of this pull.

**Matching is the risk here, not fetching.** An Ollama tag and an ECI display
name are written by different people, and quietly pairing `qwen3:8b` with a
*Thinking* variant's score would corrupt the capability axis without any error
appearing. So the map below is explicit, one line per model, and anything not
listed is reported as uncovered rather than guessed at.

  ./run.sh fetch_eci.py            # writes data/eci.csv
"""
import csv
import io
import json
import os
import sys
import urllib.request
import zipfile

URL = "https://epoch.ai/data/benchmark_data.zip"
INNER = "epoch_capabilities_index/eci_scores.csv"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "eci.csv")

# ollama tag -> exact ECI "Display name".
#
# ⚠️ Qwen3 ships reasoning on by default and the harness does NOT turn it off —
# it lets the model think and strips the scratchpad before parsing, because that
# is the behaviour a user actually gets. Epoch lists plain "Qwen3-8B" alongside
# separate "-Thinking" and "-Instruct" entries for other sizes, and which mode
# the plain entry was evaluated in is not stated. These map to the plain entries
# as the closest available match, and that ambiguity is a real limitation of the
# capability axis for the three Qwen models rather than something this map can
# resolve.
MAP = {
    "gemma3:4b":         "Gemma 3 4B",
    "llama3.1:8b":       "Llama 3.1-8B",
    "gemma3:12b":        "Gemma 3 12B",
    "gemma3:27b":        "Gemma 3 27B",
    "phi4:14b":          "Phi-4",
    # NOT 3.2. The ollama `24b` tag resolves to `24b-instruct-2501` — January
    # 2025 — which is Mistral Small 3, and Epoch dates its "Mistral Small 3"
    # entry 2025-01-30. Mapping this to 3.2 would have moved the model 4.7 ECI
    # points up the capability axis with nothing to show it was wrong.
    "mistral-small:24b": "Mistral Small 3",
    "qwen3:8b":          "Qwen3-8B",
    "qwen3:14b":         "Qwen3-14B",
    "qwen3:32b":         "Qwen3-32B",
    "gpt-oss:20b":       "gpt-oss-20b",

    # Range extension, added 2026-09-11. The first ten models spanned ECI
    # 116.0-138.5, the bottom slice of a scale whose frontier sits near 166, and
    # restricting the range of a predictor attenuates any correlation with it.
    # These six are free to run and take the span to 102.4-146.5.
    #
    # Tags are explicit where ollama's are ambiguous: `qwen3.6:35b` and
    # `qwen3.6:35b-a3b` are the same size on ollama's tag page, and the explicit
    # form removes the guess. Exact ECI display names are validated at fetch
    # time, so a wrong string fails loudly rather than joining to nothing.
    #
    # Same reasoning-mode caveat as the Qwen3 entries above applies to the
    # Qwen3.5 and Qwen3.6 models: Epoch lists one entry each and does not say
    # which mode it evaluated.
    "llama3.2:1b":       "Llama 3.2 1B",
    "qwen3.5:9b":        "Qwen3.5-9B",
    "gemma4:26b":        "Gemma 4 26B A4B",
    "gemma4:31b":        "Gemma 4 31B IT",
    "qwen3.6:35b-a3b":   "Qwen 3.6 35B-A3B",
    "qwen3.6:27b":       "Qwen3.6 27B",
}

# Run but not plottable: Epoch does not score these, so they have no capability
# axis. Recorded here so the omission is deliberate and visible rather than an
# empty row someone later fills in with a guess.
UNCOVERED = {
    "devstral-small-2": "Mistral's Devstral Small — not in the ECI table",
    "lfm2":             "Liquid AI LFM2 — not in the ECI table",
}


def main():
    print(f"fetching {URL} …")
    with urllib.request.urlopen(URL, timeout=180) as r:
        blob = r.read()
    z = zipfile.ZipFile(io.BytesIO(blob))
    rows = list(csv.DictReader(io.StringIO(z.read(INNER).decode("utf-8"))))
    print(f"  {len(rows)} models in the ECI table")

    by_name = {r["Display name"]: r for r in rows}
    missing = [n for n in MAP.values() if n not in by_name]
    if missing:
        sys.exit("ECI display names not found — the table changed, fix MAP:\n  "
                 + "\n  ".join(missing))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["ollama_tag", "eci_name", "eci", "eci_ci_low", "eci_ci_high",
                    "released", "org", "source"])
        for tag, name in sorted(MAP.items(), key=lambda kv: float(by_name[kv[1]]["eci"])):
            r = by_name[name]
            w.writerow([tag, name, r["eci"], r["eci_ci_low"], r["eci_ci_high"],
                        r["date"], r["Organization"], URL])
            print(f"  {float(r['eci']):7.2f}  [{r['eci_ci_low']:>6}, {r['eci_ci_high']:>6}]"
                  f"  {tag:<18} -> {name}")
    for tag, why in UNCOVERED.items():
        print(f"  {'—':>7}  {'':>16}  {tag:<18} -> NOT COVERED ({why})")

    lo = min(float(by_name[n]["eci"]) for n in MAP.values())
    hi = max(float(by_name[n]["eci"]) for n in MAP.values())
    print(f"\nwrote {OUT}")
    print(f"capability spread across the set: {lo:.1f} to {hi:.1f} "
          f"= {hi-lo:.1f} ECI points")
    print(f"{len(UNCOVERED)} model(s) will be run but cannot be plotted "
          f"against capability")


if __name__ == "__main__":
    main()
