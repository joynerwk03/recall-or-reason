#!/usr/bin/env bash
# Report, per model and mode, whether a COMPLETE result file exists.
# Exists-and-complete are different questions; see have_complete.py.
cd "$(dirname "$0")"
MODELS="gemma3-4b-t0 llama3-1-8b-t0 gemma3-12b-t0 mistral-small-24b-t0 gemma3-27b-t0 phi4-14b-t0 qwen3-8b-t0 gpt-oss-20b-t0 qwen3-14b-t0 qwen3-32b-t0 devstral-small-2-t0 lfm2-t0"
missing=0
for m in $MODELS; do
  line="  $m"
  for k in choice interval variants; do
    if python3 have_complete.py "$m" "$k" >/dev/null 2>&1; then
      line="$line  $k=ok"
    else
      line="$line  $k=MISSING"
      missing=$((missing + 1))
    fi
  done
  echo "$line"
done
echo
echo "missing units: $missing"
