#!/usr/bin/env bash
# Create temperature-pinned copies of the local models.
#
# Sampling CANNOT be set through `ollama run` from this harness: piped stdin is
# taken as the prompt, so a `/set parameter` line is prepended to the question
# instead of configuring the decode. Pinning has to live in the model itself.
#
# Ollama layers are content-addressed, so `FROM <existing>` reuses the same
# weight blobs and only writes a new manifest. The reported 15GB per copy is the
# same 15GB, not a second one.
#
# Any number that gets quoted anywhere should come from a -t0 model.
set -euo pipefail
OLLAMA="${OLLAMA_BIN:-/mnt/c/Users/joyne/AppData/Local/Programs/Ollama/ollama.exe}"

pin () {
  local src="$1" dst="$2"
  printf 'FROM %s\nPARAMETER temperature 0\nPARAMETER top_p 1\nPARAMETER top_k 1\nPARAMETER seed 42\n' "$src" > "/tmp/Modelfile.$dst"
  "$OLLAMA" create "$dst" -f "/tmp/Modelfile.$dst"
  echo "pinned $src -> $dst"
}

pin devstral-small-2:latest devstral-t0
pin lfm2:latest lfm2-t0
