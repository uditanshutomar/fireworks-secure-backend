"""Expands the exploit-filtered SFT set past Fireworks' recommended 100 examples.

python scripts/augment_sft.py

Each verified-secure app keeps its exact BaxBench task prompt and code; only the system
message varies, across SYSTEM_VARIANTS. It is still the same 24 unique apps and the same
training scenarios, so check_split.py gives the same answer as on the original file.
Writes training/sft_aug_with_metadata.jsonl (for check_split.py) and
training/sft_aug_fireworks.jsonl (messages only, for upload).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "training" / "sft_with_metadata.jsonl"

# The first is BaxBench's own system prompt, the one every arm sends at test time.
SYSTEM_VARIANTS = [
    "You are an experienced full-stack developer",
    "You are an experienced backend developer",
    "You are a senior software engineer who builds web APIs",
    "You are an experienced Python web developer",
    "You are a careful full-stack engineer",
]


def main() -> int:
    rows = [json.loads(line) for line in SRC.read_text(encoding="utf-8").splitlines() if line.strip()]
    out = []
    for row in rows:
        roles = [m["role"] for m in row["messages"]]
        if roles != ["system", "user", "assistant"]:
            raise SystemExit(f"unexpected roles {roles} for {row['metadata']}")
        for system in SYSTEM_VARIANTS:
            msgs = [dict(m) for m in row["messages"]]
            msgs[0]["content"] = system
            out.append({"messages": msgs, "metadata": dict(row["metadata"], system_variant=system)})
    with_meta = ROOT / "training" / "sft_aug_with_metadata.jsonl"
    plain = ROOT / "training" / "sft_aug_fireworks.jsonl"
    with_meta.write_text("".join(json.dumps(r) + "\n" for r in out), encoding="utf-8")
    plain.write_text("".join(json.dumps({"messages": r["messages"]}) + "\n" for r in out), encoding="utf-8")
    print(f"{len(rows)} apps x {len(SYSTEM_VARIANTS)} system prompts = {len(out)} examples")
    print(f"wrote {with_meta.relative_to(ROOT)} and {plain.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
