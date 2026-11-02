"""Picks the best repair stories from run records for the dashboard's run viewer.

python scripts/pick_demo_runs.py --runs results/runs --out ui/demo

Reads every *.json under --runs (CONTRACTS.md section 1). Copies up to 5 picks to
<out>/runs/ and writes <out>/index.json with a one-line caption for each.

Picks, in order:
1. Repair runs (A3, A6) whose round 0 had an exploit and a later round is secure_pass.
   CWE-89 first, then CWE-22, then CWE-78, then anything else.
2. Only if there are none: repair runs that went from failing to secure_pass.
3. One A2 one-shot run that was exploited, as the "before" example.

A file that is not a run record is skipped with a warning. Exit 0 on success,
2 when the runs directory is missing or no run qualifies.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional, Tuple

REPAIR_ARMS = ("A3", "A6")
BEFORE_ARM = "A2"
CWE_ORDER = (89, 22, 78)
MAX_PICKS = 5


class InputError(Exception):
    pass


def _is_record(rec: object) -> bool:
    if not isinstance(rec, dict):
        return False
    if not all(isinstance(rec.get(k), str) for k in ("arm", "scenario", "framework")):
        return False
    steps = rec.get("steps")
    return isinstance(steps, list) and bool(steps) and all(isinstance(s, dict) for s in steps)


def load_runs(runs_dir: str) -> List[Tuple[Path, dict]]:
    root = Path(runs_dir)
    if not root.is_dir():
        raise InputError(f"runs directory {runs_dir} not found")
    out = []
    for path in sorted(root.rglob("*.json")):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            print(f"warning: skipping {path}: {e}", file=sys.stderr)
            continue
        if not _is_record(rec):
            print(f"warning: skipping {path}: not a run record", file=sys.stderr)
            continue
        out.append((path, rec))
    return out


def _exploits(step: dict) -> List[dict]:
    ex = step.get("exploits_triggered") or []
    return [e for e in ex if isinstance(e, dict) and isinstance(e.get("cwe"), int)]


def _cwe_rank(cwe: int) -> int:
    return CWE_ORDER.index(cwe) if cwe in CWE_ORDER else len(CWE_ORDER)


def _worst_exploit(step: dict) -> Optional[dict]:
    """The exploit to name in a caption: highest CWE priority, then lowest CWE number."""
    ex = _exploits(step)
    return min(ex, key=lambda e: (_cwe_rank(e["cwe"]), e["cwe"], str(e.get("name", "")))) if ex else None


def _fixed_round(rec: dict) -> Optional[int]:
    """Round of the first secure_pass step after round 0, or None."""
    for i, s in enumerate(rec["steps"][1:], start=1):
        if s.get("secure_pass") is True:
            return s.get("round", i)
    return None


def _key(rec: dict) -> tuple:
    return (rec["arm"], rec["scenario"], rec["framework"], rec.get("run", 0))


def _spread(cands: List[dict], limit: int) -> List[dict]:
    """Take candidates in order, one per scenario first, then fill with the rest."""
    picked, seen = [], set()
    for c in cands:
        if len(picked) < limit and c["rec"]["scenario"] not in seen:
            picked.append(c)
            seen.add(c["rec"]["scenario"])
    for c in cands:
        if len(picked) < limit and c not in picked:
            picked.append(c)
    return picked


def pick(records: List[Tuple[Path, dict]], max_picks: int = MAX_PICKS) -> List[dict]:
    exploit_fixed, fail_fixed, before = [], [], []
    for path, rec in records:
        steps = rec["steps"]
        first = steps[0]
        if rec["arm"] in REPAIR_ARMS:
            rnd = _fixed_round(rec)
            if rnd is None:
                continue
            ex = _worst_exploit(first)
            if ex is not None:
                caption = (f"{rec['arm']} {rec['scenario']}: CWE-{ex['cwe']} "
                           f"{ex.get('name', 'exploit')} fixed on round {rnd}")
                exploit_fixed.append({"path": path, "rec": rec, "kind": "exploit_fixed",
                                      "caption": caption,
                                      "sort": (_cwe_rank(ex["cwe"]), rnd) + _key(rec)})
            elif first.get("secure_pass") is not True:
                n = len(first.get("failed_tests") or [])
                what = f"{n} failing test{'s' if n != 1 else ''}" if n else "failing run"
                caption = f"{rec['arm']} {rec['scenario']}: {what} fixed on round {rnd}"
                fail_fixed.append({"path": path, "rec": rec, "kind": "fail_fixed",
                                   "caption": caption, "sort": (rnd,) + _key(rec)})
        elif rec["arm"] == BEFORE_ARM and rec.get("secure_pass") is not True:
            ex = _worst_exploit(steps[-1])
            if ex is not None:
                caption = (f"{rec['arm']} {rec['scenario']}: CWE-{ex['cwe']} "
                           f"{ex.get('name', 'exploit')} exploited, one-shot")
                before.append({"path": path, "rec": rec, "kind": "before", "caption": caption,
                               "cwe": ex["cwe"], "sort": (_cwe_rank(ex["cwe"]),) + _key(rec)})

    repairs = sorted(exploit_fixed or fail_fixed, key=lambda c: c["sort"])
    room = max_picks - 1 if before and repairs and max_picks > 1 else max_picks
    picked = _spread(repairs, room)
    if before and len(picked) < max_picks:
        # Prefer a "before" run on a scenario and CWE shown fixed in the picks.
        shown = {(c["rec"]["scenario"], _worst_exploit(c["rec"]["steps"][0])["cwe"])
                 for c in picked if c["kind"] == "exploit_fixed"}
        scen = {c["rec"]["scenario"] for c in picked}
        before.sort(key=lambda c: ((c["rec"]["scenario"], c["cwe"]) not in shown,
                                   c["rec"]["scenario"] not in scen) + c["sort"])
        picked.append(before[0])
    return picked


def _file_name(rec: dict) -> str:
    safe = lambda s: "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in str(s))
    return f"{safe(rec['arm'])}__{safe(rec['scenario'])}__{safe(rec['framework'])}__r{safe(rec.get('run', 0))}.json"


def write_demo(picks: List[dict], out_dir: str) -> dict:
    out = Path(out_dir)
    runs = out / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    for old in runs.glob("*.json"):
        old.unlink()
    entries = []
    for c in picks:
        rec = c["rec"]
        name = _file_name(rec)
        (runs / name).write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
        entries.append({
            "file": f"runs/{name}", "arm": rec["arm"], "scenario": rec["scenario"],
            "framework": rec["framework"], "run": rec.get("run"), "kind": c["kind"],
            "caption": c["caption"],
        })
    index = {"runs": entries}
    if any(c["rec"].get("FAKE") for c in picks):
        index = {"FAKE": True, **index}
    (out / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    return index


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--runs", default="results/runs", help="directory of run record JSON files")
    p.add_argument("--out", default="ui/demo", help="demo folder to write")
    p.add_argument("--max", type=int, default=MAX_PICKS, help="most runs to pick (default 5)")
    args = p.parse_args(argv)
    if args.max < 1:
        p.error("--max must be at least 1")
    try:
        picks = pick(load_runs(args.runs), args.max)
        if not picks:
            raise InputError(f"no demo-worthy runs under {args.runs}")
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    index = write_demo(picks, args.out)
    for e in index["runs"]:
        print(f"{e['file']}  {e['caption']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
