#!/bin/bash
# Score the most recent run. Saves quoting a path through three shells.
cd "$(dirname "$0")" || exit 1
LATEST=$(ls -t results/*.jsonl 2>/dev/null | head -1)
[ -n "$LATEST" ] || { echo "no runs in results/"; exit 1; }
echo "scoring $LATEST"
echo
exec ./run.sh score.py "$LATEST"
