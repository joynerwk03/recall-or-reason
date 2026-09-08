#!/usr/bin/env python3
"""Build the item set from the Priors question bank.

Two sources, joined on the question id:

  ../priors/src/data/questions.ts   prompt, options, verified answer, category
  ../priors/QUESTIONS.md            the `Punctures` column — which worldview
                                    each finding contradicts

The Punctures tag is the part that makes this benchmark different from a
general-knowledge quiz: it turns "the model got it wrong" into "the model got it
wrong in a direction", which is measurable.

Parsing questions.ts with a regex rather than a TS toolchain is deliberate. The
file is generated-shaped and stable, the alternative is a Node dependency for
one job, and a mis-parse is loud rather than silent because every item is
checked for a well-formed answer index before it is written.

Writes data/items.jsonl and prints a summary. Idempotent.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PRIORS = os.path.join(HERE, "..", "priors")
QUESTIONS_TS = os.path.join(PRIORS, "src", "data", "questions.ts")
QUESTIONS_MD = os.path.join(PRIORS, "QUESTIONS.md")
OUT = os.path.join(HERE, "data", "items.jsonl")


def read(path):
    if not os.path.exists(path):
        sys.exit(f"missing source: {path}\n"
                 "This benchmark reads the Priors bank directly. Clone "
                 "github.com/joynerwk03/priors next to this repo.")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def js_string(raw):
    """Unescape a single-quoted JS string literal."""
    return (raw.replace("\\'", "'").replace('\\"', '"')
               .replace("\\n", " ").replace("\\\\", "\\")).strip()


def parse_questions(src):
    """Split on top-level object boundaries, then pull fields per block."""
    items, blocks = [], re.split(r"\n  \{\n", src)
    for block in blocks[1:]:
        block = block.split("\n  },")[0]

        def field(name):
            # Both quote styles appear in the source: a prompt containing an
            # apostrophe is written with double quotes. Matching only single
            # quotes silently dropped `vaping-harm`, which is exactly the kind
            # of quiet loss invariant 1 exists to prevent.
            for pat in (name + r":\s*\n?\s*'((?:[^'\\]|\\.)*)'",
                        name + r':\s*\n?\s*"((?:[^"\\]|\\.)*)"'):
                m = re.search(pat, block)
                if m:
                    return js_string(m.group(1))
            return None

        qid = field("id")
        prompt = field("prompt")
        category = field("category")
        context = field("context")

        opt_m = re.search(r"options:\s*\[(.*?)\]", block, re.S)
        ans_m = re.search(r"answerIndex:\s*(\d+)", block)
        if not (qid and prompt and opt_m and ans_m):
            continue

        options = [js_string(o) for o in
                   re.findall(r"'((?:[^'\\]|\\.)*)'|\"((?:[^\"\\]|\\.)*)\"",
                              opt_m.group(1))
                   for o in [o[0] or o[1]]]
        answer = int(ans_m.group(1))

        # Loud on a mis-parse rather than quietly writing a broken item.
        if not options or not (0 <= answer < len(options)):
            print(f"  SKIP {qid}: answerIndex {answer} outside "
                  f"{len(options)} options", file=sys.stderr)
            continue

        val, unit = numeric_answer(options[answer])
        items.append({
            "id": qid,
            "category": category,
            "prompt": prompt,
            "context": context,
            "options": options,
            "answer_index": answer,
            "answer_text": options[answer],
            "numeric_answer": val,
            "unit": unit,
        })
    return items


WORD_NUMBERS = {"zero": 0.0, "none": 0.0, "no": 0.0}


def numeric_answer(text):
    """Best-effort numeric value of the correct option, for interval mode.

    Multiple choice can be answered by elimination, and elimination is not
    evidence of a world model. Asking for a number instead removes that crutch —
    but only for items whose answer IS a number. This returns None otherwise,
    and interval mode simply skips those rather than inventing a value.

    Returns (value, unit_hint). "About 1 in 25 (4%)" resolves to the percentage
    in parentheses, because that is the quantity a model would estimate.
    """
    t = text.strip().lower()

    if t in WORD_NUMBERS:
        return WORD_NUMBERS[t], ""

    # A parenthesised percentage restates the headline figure; prefer it.
    m = re.search(r"\(([\d.]+)\s*%\)", t)
    if m:
        return float(m.group(1)), "%"

    # "1 in 25" -> 4.0%
    m = re.search(r"(\d+)\s+in\s+(\d[\d,]*)", t)
    if m:
        den = float(m.group(2).replace(",", ""))
        if den:
            return round(100.0 * float(m.group(1)) / den, 3), "%"

    m = re.search(r"(-?[\d,]*\.?\d+)\s*(%|°c|x|:1)?", t)
    if not m:
        return None, ""
    try:
        val = float(m.group(1).replace(",", ""))
    except ValueError:
        return None, ""
    return val, (m.group(2) or "").strip()


def parse_punctures(md):
    """Last column of each markdown table row, keyed by id."""
    tags = {}
    for line in md.splitlines():
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        qid, tag = cells[0], cells[-1]
        if not re.fullmatch(r"[a-z0-9-]+", qid) or tag.lower() == "punctures":
            continue
        tags[qid] = tag
    return tags


def main():
    items = parse_questions(read(QUESTIONS_TS))
    tags = parse_punctures(read(QUESTIONS_MD))

    tagged = 0
    for it in items:
        it["punctures"] = tags.get(it["id"])
        if it["punctures"]:
            tagged += 1

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        for it in items:
            fh.write(json.dumps(it, ensure_ascii=False) + "\n")

    print(f"wrote {len(items)} items -> {os.path.relpath(OUT, HERE)}")
    print(f"  with a punctures tag: {tagged}")
    print(f"  untagged:             {len(items) - tagged}")

    by_tag = {}
    for it in items:
        by_tag[it["punctures"] or "(untagged)"] = by_tag.get(it["punctures"] or "(untagged)", 0) + 1
    print("\n  tally (a diagnostic, never a target):")
    for tag, n in sorted(by_tag.items(), key=lambda kv: -kv[1]):
        print(f"    {tag:<16} {n}")

    opts = {len(it["options"]) for it in items}
    print(f"\n  option counts present: {sorted(opts)}")
    print("  NOTE: chance accuracy differs per item, so score against the "
          "per-item baseline, never a flat 25%.")

    numeric = [it for it in items if it["numeric_answer"] is not None]
    print(f"\n  items with a numeric answer: {len(numeric)}/{len(items)} "
          "(the interval-mode subset)")
    if len(items) - len(numeric):
        skipped = [it["id"] for it in items if it["numeric_answer"] is None]
        print(f"  qualitative, skipped by interval mode: {', '.join(skipped[:6])}"
              + (" …" if len(skipped) > 6 else ""))


if __name__ == "__main__":
    main()
