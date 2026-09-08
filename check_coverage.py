#!/usr/bin/env python3
"""Which source questions failed to extract, and why.

Ground truth integrity is invariant 1, so a silently dropped item is a real
defect rather than a rounding error. Run after extract_items.py.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
TS = os.path.join(HERE, "..", "priors", "src", "data", "questions.ts")

src_ids = re.findall(r"^    id: '([a-z0-9-]+)'", open(TS, encoding="utf-8").read(), re.M)
got = [json.loads(l)["id"] for l in open(os.path.join(HERE, "data", "items.jsonl"), encoding="utf-8")]

missing = [i for i in src_ids if i not in got]
print(f"source questions : {len(src_ids)}")
print(f"extracted        : {len(got)}")
print(f"missing          : {missing or 'none'}")

# Show the raw block for anything missed, so the parse gap is diagnosable.
if missing:
    text = open(TS, encoding="utf-8").read()
    for qid in missing:
        start = text.find(f"id: '{qid}'")
        print(f"\n----- raw block for {qid} -----")
        print(text[max(0, start - 20): start + 700])
