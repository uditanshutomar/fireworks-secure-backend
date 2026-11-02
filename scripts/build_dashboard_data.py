"""Bundles results.json and the run records into ui/data.js so the dashboard opens from a file.

python scripts/build_dashboard_data.py                                  # sample data (ui/sample)
python scripts/build_dashboard_data.py --results results/results.json --runs results/runs   # real data

Browsers block fetch() from file://, so the data ships as a script that sets window.DASHBOARD_DATA.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[1]


def load_runs(runs_dir: Path) -> List[dict]:
    runs = []
    for path in sorted(runs_dir.rglob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(rec, dict) and "arm" in rec and "steps" in rec:
            runs.append(rec)
    return runs


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--results", default=str(ROOT / "ui" / "sample" / "results.json"))
    p.add_argument("--runs", default=str(ROOT / "ui" / "sample" / "runs"))
    p.add_argument("--out", default=str(ROOT / "ui" / "data.js"))
    args = p.parse_args(argv)
    try:
        results = json.loads(Path(args.results).read_text(encoding="utf-8"))
        runs = load_runs(Path(args.runs))
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    data = {"results": results, "runs": runs}
    Path(args.out).write_text("window.DASHBOARD_DATA = " + json.dumps(data, indent=1) + ";\n", encoding="utf-8")
    print(f"wrote {args.out}: {len(results.get('arms', []))} arms, {len(runs)} run records")
    return 0


if __name__ == "__main__":
    sys.exit(main())
