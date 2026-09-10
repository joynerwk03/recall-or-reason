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

# Interval mode. Multiple choice can be answered by elimination, and elimination
# is not evidence of a world model. Asking for a number removes that crutch, and
# asking for an interval around it is the actual probe: a memorised value gives
# a tight interval that contains the truth, a reasoned estimate gives a wider one
# that usually does, and a bluff gives a tight one that does not. The joint
# distribution of width against error separates all three.
#
# There is a prior reason to expect this to be informative. In the v1 sweep
# neither model ever stated a confidence below 80 across 159 answers, so the
# percentage channel was barely used. An interval is a different format, and the
# open question is whether they can express doubt in it at all.
INTERVAL_TEMPLATE = """You are estimating a real-world statistic.

{context}Question: {prompt}

Answer with exactly three lines and nothing else:
ESTIMATE: <your single best number>
LOW: <low end of your 80% interval>
HIGH: <high end of your 80% interval>

Give {unit_hint}, digits only, no words or symbols.

An 80% interval means you think there is an 80% chance the true value lies
between LOW and HIGH. Make it as wide as it honestly needs to be. A narrow
interval that misses is worse than a wide one that contains the answer.
"""

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
    """Drive the Ollama CLI. Sampling is NOT set here — it cannot be.

    `ollama run` with piped stdin treats the whole of stdin as the prompt, so a
    leading `/set parameter temperature 0` is not a REPL command: it is silently
    prepended to the question as text. That was tried on 2026-09-09 and it
    contaminated every prompt while appearing to work, because the contaminated
    prompt happened to give stable short answers on the toy case used to test it.
    The giveaway was that the "pinned" answer (20) was not one of the values the
    unpinned run ever produced (1, 2) — temperature 0 narrows a distribution, it
    does not move it somewhere new. Two later runs of the real bank then differed
    on 35 of 50 items.

    Sampling is pinned instead in the model itself, via a Modelfile that sets
    temperature, top_p, top_k and seed. See `pin_models.sh`; use the `-t0`
    models for anything whose numbers get quoted.
    """
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


def parse_interval(text):
    """Pull ESTIMATE, LOW and HIGH. Returns (est, lo, hi), any of which may be None.

    Tolerant of drift for the same reason the choice parser is: a strict parser
    would measure formatting compliance rather than estimation. If LOW and HIGH
    come back inverted they are swapped, since the intent is unambiguous and
    discarding the row would lose a real answer to a formatting slip.
    """
    def grab(label):
        m = re.search(label + r"\s*:?\s*\$?(-?[\d,]*\.?\d+)", text, re.I)
        if not m:
            return None
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            return None

    est, lo, hi = grab("ESTIMATE"), grab("LOW"), grab("HIGH")

    # Fallback: models frequently drop the labels and emit three bare numbers in
    # the requested order. Those are perfectly good answers, and discarding them
    # would bias the sample toward format-compliant responses rather than
    # accurate ones. Only used when the labelled parse is incomplete.
    if est is None or lo is None or hi is None:
        nums = re.findall(r"-?[\d,]*\.?\d+", text)
        vals = []
        for n in nums[:3]:
            try:
                vals.append(float(n.replace(",", "")))
            except ValueError:
                pass

        if len(vals) == 3:
            a, b, c = vals
            # Two conventions turn up, and assuming the wrong one silently
            # corrupts the answer. Disambiguate by ordering rather than by
            # model, because the test is a property of the numbers:
            #
            #   57, 52, 63  first value sits inside the other two -> the
            #               prompted ESTIMATE, LOW, HIGH order with the labels
            #               dropped
            #   0, 5, 10    strictly ascending -> LOW, ESTIMATE, HIGH, the
            #               ordinary way of writing a range
            #
            # Reading an ascending triple as (est, lo, hi) puts the estimate
            # outside its own interval every time. That self-contradiction is
            # evidence of a misparse, not of an incoherent model. Before this
            # check, 8 of lfm2's 12 "incoherent" answers on 2026-09-09 were
            # simply this bug, and one of them (9 / 90 / 100 on an item whose
            # truth was 9) scored a perfect baseline off a misread.
            if min(b, c) <= a <= max(b, c):
                est, lo, hi = a, b, c
            elif a <= b <= c:
                lo, est, hi = a, b, c
            else:
                # Neither convention fits; keep the prompted reading and let the
                # coherence check downstream flag it as the genuine mess it is.
                est, lo, hi = a, b, c

        elif len(vals) == 1 and est is None:
            # A bare point estimate with no range. Previously discarded whole,
            # which threw away a real answer and mislabelled a model that
            # answered-but-gave-no-interval as one that failed to answer. Keep
            # the estimate; lo/hi stay None so it is excluded from coverage.
            est = vals[0]

    if lo is not None and hi is not None and lo > hi:
        lo, hi = hi, lo
    return est, lo, hi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="lfm2")
    ap.add_argument("--mode", choices=["choice", "interval"], default="choice")
    ap.add_argument("--limit", type=int, default=0, help="0 = all items")
    ap.add_argument("--host", default=None)
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--dry-run", action="store_true",
                    help="build prompts and write a stub run, no model needed")
    ap.add_argument("--list-models", action="store_true")
    ap.add_argument("--items", default=ITEMS,
                    help="item file to run; defaults to the full bank. Perturbed "
                         "variants use data/variants.jsonl, which is deliberately "
                         "the same schema so it goes through this exact prompt "
                         "path — a variant scored against a different prompt "
                         "builder would not be comparable to its original.")
    ap.add_argument("--tag", default="",
                    help="suffix for the run filename, e.g. --tag variants")
    a = ap.parse_args()

    if a.list_models:
        host, cli = resolve_host(a.host), find_cli()
        if not (host or cli):
            sys.exit("no Ollama found over HTTP or as a binary.")
        print("transport:", "http " + host if host else "cli " + cli)
        for m in list_models(host, cli):
            print("  " + m)
        return

    items = [json.loads(l) for l in open(a.items, encoding="utf-8")]
    if a.mode == "interval":
        # Only items whose answer is a number. The rest are skipped rather than
        # coerced; inventing a numeric target for a qualitative claim would put
        # a fabricated ground truth into the scoring.
        before = len(items)
        items = [i for i in items if i.get("numeric_answer") is not None]
        print(f"interval mode: {len(items)} of {before} items have a numeric answer")
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
    suffix = (("-" + re.sub(r"[^a-zA-Z0-9._-]", "_", a.tag)) if a.tag else "")
    suffix += ("-interval" if a.mode == "interval" else "") + ("-dry" if a.dry_run else "")
    out = os.path.join(RESULTS, f"{tag}-{stamp}{suffix}.jsonl")

    n_ok = n_parsed = 0
    with open(out, "w", encoding="utf-8") as fh:
        for i, it in enumerate(items, 1):
            ctx = (it.get("context") or "").strip()
            if a.mode == "interval":
                unit_hint = ("a percentage between 0 and 100" if it.get("unit") == "%"
                             else "a plain number")
                prompt = INTERVAL_TEMPLATE.format(
                    prompt=it["prompt"], unit_hint=unit_hint,
                    context=(ctx + "\n\n") if ctx else "")
            else:
                opts = "\n".join(f"{LETTERS[j]}) {o}" for j, o in enumerate(it["options"]))
                prompt = TEMPLATE.format(prompt=it["prompt"], options=opts,
                                         context=(ctx + "\n\n") if ctx else "")

            raw, err = "", ("dry-run" if a.dry_run else None)
            if not a.dry_run:
                try:
                    raw = (ask(host, a.model, prompt, a.timeout) if host
                           else ask_cli(cli, a.model, prompt, a.timeout))
                except Exception as e:
                    raw, err = "", f"{type(e).__name__}: {e}"

            rec = {"id": it["id"], "category": it["category"],
                   "punctures": it["punctures"], "model": a.model,
                   "mode": a.mode, "prompt_version": PROMPT_VERSION,
                   "error": err, "raw": raw}

            # Carry perturbation metadata through to the result. Without this a
            # variant run cannot be paired back to its original and the gap is
            # unscoreable. Absent on ordinary bank items, so this is a no-op there.
            for k in ("base_id", "kind", "original_answer", "prompt_anchor",
                      "source_url", "verified"):
                if k in it:
                    rec[k] = it[k]

            if a.mode == "interval":
                est, lo, hi = parse_interval(raw) if raw else (None, None, None)
                truth = it["numeric_answer"]
                # None means "no interval to judge", which is different from
                # "the interval missed". Keeping them distinct matters: the
                # first is a parse failure, the second is a result.
                covered = None
                if lo is not None and hi is not None:
                    covered = (lo <= truth <= hi)
                rec.update({"truth": truth, "unit": it.get("unit", ""),
                            "estimate": est, "low": lo, "high": hi,
                            "covered": covered})
                if est is not None:
                    n_parsed += 1
                if covered:
                    n_ok += 1
                if not a.dry_run:
                    mark = "?" if est is None else ("in" if covered else "out")
                    span = f"[{lo:g}, {hi:g}]" if (lo is not None and hi is not None) else "[?]"
                    print(f"  [{i:>3}/{len(items)}] {mark:<3} {it['id']:<24} "
                          f"est {est if est is not None else '?'} {span} truth {truth:g}")
            else:
                choice, conf = parse(raw, len(it["options"])) if raw else (None, None)
                correct = (choice == it["answer_index"]) if choice is not None else None
                rec.update({"n_options": len(it["options"]),
                            "answer_index": it["answer_index"], "choice": choice,
                            "confidence": conf, "correct": correct})
                if correct:
                    n_ok += 1
                if choice is not None:
                    n_parsed += 1
                if not a.dry_run:
                    mark = "?" if choice is None else ("ok" if correct else "x ")
                    print(f"  [{i:>3}/{len(items)}] {mark} {it['id']}"
                          + (f"  conf {conf}" if conf is not None else ""))

            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"\nwrote {out}")
    if not a.dry_run and n_parsed:
        label = "covered" if a.mode == "interval" else "correct"
        scorer = "score_interval.py" if a.mode == "interval" else "score.py"
        print(f"  parsed {n_parsed}/{len(items)} · {label} {n_ok}/{n_parsed} "
              f"= {100*n_ok/n_parsed:.1f}%")
        print(f"  Score properly with: ./run.sh {scorer} " + os.path.relpath(out, HERE))


if __name__ == "__main__":
    main()
