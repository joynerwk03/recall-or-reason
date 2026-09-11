#!/bin/bash
# Run a script from this directory with this project's own interpreter.
#
# Until 2026-09-11 this borrowed ConceptChess's virtualenv, so the benchmark
# silently depended on another project's environment: had that project rebuilt
# or removed its .venv, the plotting scripts here would have broken. Evaluation
# and scoring are stdlib-only; only the plots need matplotlib (requirements.txt).
#
#   python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cd "$(dirname "$0")" || exit 1
for PY in ./.venv/bin/python python3; do
  command -v "$PY" >/dev/null 2>&1 && exec "$PY" "$@"
done
echo "run.sh: no python interpreter found" >&2
exit 1
