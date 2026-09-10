#!/usr/bin/env bash
# Run the full benchmark over every pinned model.
#
# Resumable on purpose. A sweep over ten models is long enough that something
# will interrupt it — a download still running, a model that hangs, a machine
# that sleeps — and re-running from scratch each time would waste hours. Any
# model whose three result files already exist is skipped, so this can be run
# repeatedly as more models finish downloading.
#
# Each model gets three runs:
#   choice     80 items, answer + stated confidence
#   interval   50 numeric items, estimate + 80% range
#   variants   9 perturbed items (8 moved questions + 1 null control)
#
#   ./sweep_all.sh            # run everything not yet done
#   ./sweep_all.sh --list     # show what is done and what is pending
set -uo pipefail
cd "$(dirname "$0")"
R=results
mkdir -p "$R"

have () {   # have <model> <suffix>   -> newest matching result file, if any
  ls -t "$R"/"$1"-*"$2".jsonl 2>/dev/null | head -1
}

run_one () {
  local m="$1"
  local c i v
  c="$(have "$m" '')"          # choice files carry no suffix
  c="$(ls -t "$R"/"$m"-*.jsonl 2>/dev/null | grep -vE 'interval|variants' | head -1)"
  i="$(ls -t "$R"/"$m"-*-interval.jsonl 2>/dev/null | grep -v variants | head -1)"
  v="$(ls -t "$R"/"$m"-*-variants-interval.jsonl 2>/dev/null | head -1)"

  if [ -n "$c" ] && [ -n "$i" ] && [ -n "$v" ]; then
    echo "SKIP  $m  (already has all three runs)"
    return
  fi

  echo "=== $m  $(date +%H:%M:%S)"
  [ -z "$c" ] && ./run.sh run_eval.py --mode choice   --model "$m" --timeout 300 2>&1 | tail -2
  [ -z "$i" ] && ./run.sh run_eval.py --mode interval --model "$m" --timeout 300 2>&1 | tail -2
  [ -z "$v" ] && ./run.sh run_eval.py --mode interval --model "$m" --timeout 300 \
                    --items data/variants.jsonl --tag variants 2>&1 | tail -2
}

O="${OLLAMA_BIN:-/mnt/c/Users/joyne/AppData/Local/Programs/Ollama/ollama.exe}"
mapfile -t PINNED < <("$O" list 2>/dev/null | tr -d '\r' | awk '/-t0/{print $1}' | sed 's/:latest$//')

if [ "${1:-}" = "--list" ]; then
  echo "pinned models: ${#PINNED[@]}"
  for m in "${PINNED[@]}"; do
    n=$(ls "$R"/"$m"-*.jsonl 2>/dev/null | wc -l)
    echo "  $m  ($n result files)"
  done
  exit 0
fi

echo "sweeping ${#PINNED[@]} pinned models"
for m in "${PINNED[@]}"; do run_one "$m"; done
echo "SWEEP DONE $(date +%H:%M:%S)"
