"""Builds the SFT dataset from training-set run records, keeping only apps that passed every
functional test and survived every exploit.

    .venv-bax/bin/python scripts/export_sft.py --runs data/gen --out data/sft.jsonl

Writes two files:
- data/sft.jsonl: messages + metadata (scenario, framework), checked by check_split.py
- data/sft_fireworks.jsonl: messages only, the file uploaded with `firectl dataset create`
Each example is BaxBench's original prompt answered by the final secure code in BaxBench's
<CODE> format, so the tuned model learns to answer the exact prompt the arms send.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from secure_backend import baxbench_runner as bax  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="data/gen")
    ap.add_argument("--out", default="data/sft.jsonl")
    args = ap.parse_args()

    records = [json.loads(p.read_text()) for p in sorted((ROOT / args.runs).rglob("*.json"))]
    kept, seen = [], set()
    for r in records:
        if not r["secure_pass"]:
            continue
        code = r["steps"][-1]["code"].strip()
        key = (r["scenario"], r["framework"], code)
        if not code or key in seen:
            continue
        seen.add(key)
        messages = bax.build_messages(r["scenario"], r["framework"]) + [
            {"role": "assistant", "content": f"<CODE>\n{code}\n</CODE>"}]
        kept.append({"messages": messages, "metadata": {"scenario": r["scenario"], "framework": r["framework"]}})

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        for ex in kept:
            f.write(json.dumps(ex) + "\n")
    with out.with_name(out.stem + "_fireworks.jsonl").open("w") as f:
        for ex in kept:
            f.write(json.dumps({"messages": ex["messages"]}) + "\n")

    by_fw: dict = {}
    for ex in kept:
        by_fw[ex["metadata"]["framework"]] = by_fw.get(ex["metadata"]["framework"], 0) + 1
    print(f"records {len(records)}, secure {sum(r['secure_pass'] for r in records)}, "
          f"kept {len(kept)} (after dedup), by framework {by_fw}, "
          f"scenarios {len({ex['metadata']['scenario'] for ex in kept})}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
