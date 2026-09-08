#!/bin/bash
# Full 80-item sweep across every local model, then score each.
# Long-running: roughly half an hour per model through the CLI transport.
#
# ⚠ RUN THIS IN THE FOREGROUND, and keep the invoking shell alive.
#
# Backgrounding it from a transient `wsl.exe -- bash -lc "... &"` does NOT work:
# WSL2 shuts the distro down once the invoking shell's last process exits, and
# it takes the nohup'd job with it. That failure is silent — an empty log, no
# process, and no error anywhere — which is worse than a crash. Learned
# 2026-09-08 after an hour of watching a sweep that had never started.
cd "$(dirname "$0")" || exit 1
mkdir -p results
LOG=results/sweep.log
: > "$LOG"

MODELS="${*:-lfm2 devstral-small-2}"

for m in $MODELS; do
  echo "===== $m =====" | tee -a "$LOG"
  date -u +"start %Y-%m-%dT%H:%M:%SZ" | tee -a "$LOG"
  ./run.sh run_eval.py --model "$m" >> "$LOG" 2>&1
  date -u +"end   %Y-%m-%dT%H:%M:%SZ" | tee -a "$LOG"
  echo | tee -a "$LOG"
done

echo "===== SCORES =====" | tee -a "$LOG"
for f in $(ls -t results/*.jsonl 2>/dev/null | grep -v dry | head -${#MODELS[@]}); do
  echo "--- $f ---" | tee -a "$LOG"
  ./run.sh score.py "$f" 2>&1 | tee -a "$LOG"
  echo | tee -a "$LOG"
done

echo "SWEEP COMPLETE" | tee -a "$LOG"
