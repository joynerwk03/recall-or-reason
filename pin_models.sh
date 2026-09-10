#!/usr/bin/env bash
# Build a deterministic `-t0` copy of every model under test.
#
# Sampling CANNOT be set through `ollama run` from this harness: piped stdin is
# taken as the prompt, so a `/set parameter` line is prepended to the question
# instead of configuring the decode. It has to live in the model.
#
# num_predict matters as much as temperature here. The default is small enough
# that a reasoning model spends the whole budget inside <think> and never emits
# an answer — which arrives downstream looking like a model that could not
# answer rather than one that was cut off. 900 is enough for a scratchpad plus
# three lines; anything still truncated is recorded as truncated.
#
# Ollama layers are content-addressed, so `FROM <existing>` reuses the same
# weight blobs and only writes a new manifest. The size ollama reports per copy
# is the same weights, not a second download.
#
# Any number that gets quoted anywhere should come from a -t0 model.
set -uo pipefail
O="${OLLAMA_BIN:-/mnt/c/Users/joyne/AppData/Local/Programs/Ollama/ollama.exe}"

MODELS=(
  gemma3:4b llama3.1:8b qwen3:8b gemma3:12b phi4:14b
  qwen3:14b mistral-small:24b gpt-oss:20b gemma3:27b qwen3:32b
  devstral-small-2:latest lfm2:latest
)

pin () {
  local src="$1"
  local dst
  dst="$(echo "$src" | sed 's/:latest$//; s/[:.]/-/g')-t0"
  if ! "$O" list 2>/dev/null | tr -d '\r' | awk '{print $1}' | grep -qx "$src"; then
    echo "SKIP  $src  (not pulled)"
    return
  fi
  printf 'FROM %s\nPARAMETER temperature 0\nPARAMETER top_p 1\nPARAMETER top_k 1\nPARAMETER seed 42\nPARAMETER num_predict 2500\n' \
    "$src" > "/tmp/Modelfile.$dst"
  if "$O" create "$dst" -f "/tmp/Modelfile.$dst" >/dev/null 2>&1; then
    echo "PIN   $src -> $dst"
  else
    echo "FAIL  $src  (ollama create failed)"
  fi
}

for m in "${MODELS[@]}"; do pin "$m"; done
echo
echo "pinned models now available:"
"$O" list 2>/dev/null | tr -d '\r' | grep -- '-t0' || echo "  (none)"
