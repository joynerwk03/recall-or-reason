#!/usr/bin/env python3
"""Run the item set against a local model and record answer + stated confidence.

Ollama lives on the Windows side of this machine, so from WSL the host has to be
resolved rather than assumed. Order tried: an explicit --host, then localhost
(WSL2 mirrored networking), then the nameserver in /etc/resolv.conf (the classic
NAT setup).

Output is one JSON object per item in results/<model>-<timestamp>.jsonl,
including the raw completion. Keeping the raw text matters: when a parse looks
wrong later, the alternative to having it is re-running everything.

  ./run.sh run_eval.py --list-models
  ./run.sh run_eval.py --model lfm2 --limit 5
  ./run.sh run_eval.py --model lfm2 --dry-run
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

# Ollama runs on the Windows side of this machine and binds loopback only, so
# WSL cannot reach it over HTTP without a firewall rule this account cannot add.
# WSL can execute Windows binaries directly, though, so the CLI is used as a
# fallback transport. Same model, same weights, just a different pipe.
WIN_OLLAMA = "/mnt/c/Users/joyne/AppData/Local/Programs/Ollama/ollama.exe"
ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07|[\r\x0f]")

HERE = os.path.dirname(os.path.abspath(__file__))
ITEMS = os.path.join(HERE, "data", "items.jsonl")
RESULTS = os.path.join(HERE, "results")
LETTERS = "ABCDEFGH"

PROMPT_VERSION = "v1"
TEMPLATE = """You are answering a multiple-choice question about a real-world statistic.

{context}Question: {prompt}

{options}

Answer with exactly two lines and nothing else:
ANSWER: <letter>
CONFIDENCE: <integer 0-100, your probability that the answer is correct>

Give an honest confidence. A confident wrong answer is worse than an uncertain one.
"""


def candidate_hosts(explicit=None):
    if explicit:
        return [explicit]
    hosts = ["http://localhost:11434"]
    try:
        with open("/etc/resolv.conf", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("nameserver"):
                    hosts.append("http://" + line.split()[1] + ":11434")
    except OSError:
        pass
    return hosts


def resolve_host(explicit=None):
    for host in candidate_hosts(explicit):
        try:
            with urllib.request.urlopen(host + "/api/tags", timeout=4) as r:
                json.load(r)
            return host
        except Exception:
            continue
    return None


def find_cli():
    """The Ollama executable, whichever side of the machine it lives on."""
    for c in (shutil.which("ollama"), WIN_OLLAMA):
        if c and os.path.exists(c):
            return c
    return None


def clean(text):
    """Strip the progress spinner. `ollama run` writes braille frames and cursor
    codes to stdout even when piped, so the raw text is unusable without this."""
    return ANSI.sub("", text).strip()


def list_models(host=None, cli=None):
    if host:
        with urllib.request.urlopen(host + "/api/tags", timeout=10) as r:
            return [m["name"] for m in json.load(r).get("models", [])]
    out = subprocess.run([cli, "list"], capture_output=True, text=True, timeout=60).stdout
    return [l.split()[0] for l in out.splitlines()[1:] if l.strip()]


def ask_cli(cli, model, prompt, timeout):
    p = subprocess.run([cli, "run", model], input=prompt, capture_output=True,
                       text=True, timeout=timeout, errors="replace")
    if p.returncode != 0 and not p.stdout.strip():
        raise RuntimeError((p.stderr or "ollama exited " + str(p.returncode))[:200])
    return clean(p.stdout)


def ask(host, model, prompt, timeout):
    body = json.dumps({
        "model": model, "prompt": prompt, "stream": False,
        # Deterministic, so a re-run of the same items is comparable.
        "options": {"temperature": 0, "num_predict": 64},
    }).encode()
    req = urllib.request.Request(host + "/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r).get("response", "")


def parse(text, n_options):
    """Pull the letter and confidence out, tolerantly.

    Small models drift from any format instruction, so a strict parser would
    measure formatting compliance rather than knowledge. Unparseable stays
    unparseable though — it is recorded as such rather than guessed, because a
    silent default would land in the accuracy number as a real answer.
    """
    letter = conf = None
    m = re.search(r"ANSWER:\s*\(?([A-H])\)?", text, re.I)
    if not m:
        m = re.search(r"\b([A-H])[).:]", text.strip())
    if not m:
        m = re.search(r"\b([A-H])\b", text.strip())
    if m:
        idx = LETTERS.index(m.group(1).upper())
        if idx < n_options:
            letter = idx
    c = re.search(r"CONFIDENCE:\s*(\d{1,3})", text, re.I)
    if not c:
        c = re.search(r"(\d{1,3})\s*%", text)
    if c:
        v = int(c.group(1))
        if 0 <= v <= 100:
            conf = v
    return letter, conf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="lfm2")
    ap.add_argument("--limit", type=int, default=0, help="0 = all items")
    ap.add_argument("--host", default=None)
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--dry-run", action="store_true",
                    help="build prompts and write a stub run, no model needed")
    ap.add_argument("--list-models", action="store_true")
    a = ap.parse_args()

    if a.list_models:
        host, cli = resolve_host(a.host), find_cli()
        if not (host or cli):
            sys.exit("no Ollama found over HTTP or as a binary.")
        print("transport:", "http " + host if host else "cli " + cli)
        for m in list_models(host, cli):
            print("  " + m)
        return

    items = [json.loads(l) for l in open(ITEMS, encoding="utf-8")]
    if a.limit:
        items = items[:a.limit]

    host = cli = None
    if not a.dry_run:
        host = resolve_host(a.host)
        if not host:
            cli = find_cli()
        if not (host or cli):
            sys.exit("no Ollama found over HTTP or as a binary. Start it, or use --dry-run.")
        transport = ("http " + host) if host else ("cli " + os.path.basename(cli))
        print(f"{transport} · model {a.model} · {len(items)} items")

    os.makedirs(RESULTS, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    tag = re.sub(r"[^a-zA-Z0-9._-]", "_", a.model)
    out = os.path.join(RESULTS, f"{tag}-{stamp}{'-dry' if a.dry_run else ''}.jsonl")

    n_ok = n_parsed = 0
    with open(out, "w", encoding="utf-8") as fh:
        for i, it in enumerate(items, 1):
            opts = "\n".join(f"{LETTERS[j]}) {o}" for j, o in enumerate(it["options"]))
            ctx = (it.get("context") or "").strip()
            prompt = TEMPLATE.format(prompt=it["prompt"], options=opts,
                                     context=(ctx + "\n\n") if ctx else "")

            if a.dry_run:
                raw, err = "", "dry-run"
                choice = conf = None
            else:
                err = None
                try:
                    raw = (ask(host, a.model, prompt, a.timeout) if host
                           else ask_cli(cli, a.model, prompt, a.timeout))
                except Exception as e:
                    raw, err = "", f"{type(e).__name__}: {e}"
                choice, conf = parse(raw, len(it["options"])) if raw else (None, None)

            correct = (choice == it["answer_index"]) if choice is not None else None
            if correct:
                n_ok += 1
            if choice is not None:
                n_parsed += 1

            fh.write(json.dumps({
                "id": it["id"], "category": it["category"],
                "punctures": it["punctures"], "n_options": len(it["options"]),
                "answer_index": it["answer_index"], "choice": choice,
                "confidence": conf, "correct": correct,
                "model": a.model, "prompt_version": PROMPT_VERSION,
                "error": err, "raw": raw,
            }, ensure_ascii=False) + "\n")

            if not a.dry_run:
                mark = "?" if choice is None else ("ok" if correct else "x ")
                print(f"  [{i:>3}/{len(items)}] {mark} {it['id']}"
                      + (f"  conf {conf}" if conf is not None else ""))

    print(f"\nwrote {out}")
    if not a.dry_run and n_parsed:
        print(f"  parsed {n_parsed}/{len(items)} · correct {n_ok}/{n_parsed} "
              f"= {100*n_ok/n_parsed:.1f}%")
        print("  Score properly with: ./run.sh score.py " + os.path.relpath(out, HERE))


if __name__ == "__main__":
    main()
