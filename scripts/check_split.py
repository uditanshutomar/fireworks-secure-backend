"""Fails if any SFT training example uses a scenario from the locked test split.

python scripts/check_split.py --split private/split.json --sft data/sft.jsonl

Exit 0: no overlap. Exit 1: overlap, each offending line is printed.
Exit 2: a file is missing, unreadable or malformed.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional, Set, Tuple


class InputError(Exception):
    pass


def _norm(name: str) -> str:
    # Case and outer spaces do not make a scenario a different one.
    return name.strip().casefold()


def load_test_scenarios(path: str) -> Set[str]:
    try:
        with open(path, encoding="utf-8") as f:
            split = json.load(f)
    except OSError as e:
        raise InputError(f"cannot read split {path}: {e}") from e
    except ValueError as e:
        raise InputError(f"split {path} is not valid JSON: {e}") from e
    if not isinstance(split, dict) or "test" not in split:
        raise InputError(f"split {path} has no 'test' list")
    test = split["test"]
    if not isinstance(test, list) or not all(isinstance(s, str) for s in test):
        raise InputError(f"split {path}: 'test' must be a list of strings")
    return {_norm(s) for s in test}


def find_overlap(sft_path: str, test: Set[str]) -> List[Tuple[int, str]]:
    """Returns (line number, scenario) for every SFT line whose scenario is in test."""
    hits = []
    try:
        f = open(sft_path, encoding="utf-8")
    except OSError as e:
        raise InputError(f"cannot read SFT file {sft_path}: {e}") from e
    with f:
        try:
            for lineno, line in enumerate(f, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except ValueError as e:
                    raise InputError(f"{sft_path} line {lineno}: not valid JSON: {e}") from e
                meta = row.get("metadata") if isinstance(row, dict) else None
                scenario = meta.get("scenario") if isinstance(meta, dict) else None
                if not isinstance(scenario, str):
                    raise InputError(f"{sft_path} line {lineno}: no metadata.scenario string")
                if _norm(scenario) in test:
                    hits.append((lineno, scenario))
        except UnicodeDecodeError as e:
            raise InputError(f"{sft_path} is not UTF-8: {e}") from e
    return hits


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--split", required=True, help="split JSON with a 'test' list")
    p.add_argument("--sft", required=True, help="SFT JSONL with metadata.scenario on each line")
    args = p.parse_args(argv)
    try:
        hits = find_overlap(args.sft, load_test_scenarios(args.split))
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    for lineno, scenario in hits:
        print(f"{args.sft}:{lineno}: test scenario {scenario!r} in training data")
    if hits:
        print(f"FAIL: {len(hits)} SFT line(s) use a test scenario", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
