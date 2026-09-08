#!/bin/bash
# Convenience wrapper. There is no venv of this project's own yet, so it borrows
# ConceptChess's interpreter; the scripts are stdlib-only, so any python3 works.
PY="$HOME/mission-control/projects/conceptchess/.venv/bin/python"
[ -x "$PY" ] || PY="python3"
cd "$(dirname "$0")" || exit 1
exec "$PY" "$@"
