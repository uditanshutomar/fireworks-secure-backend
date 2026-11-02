"""Builds results.json for the dashboard from run records, and prints a Markdown table.

python scripts/results_table.py --runs results/runs --out results/results.json

Reads every *.json under --runs (CONTRACTS.md section 1), writes section 2.
Exit 0 on success, 2 on a missing, unreadable or malformed run record.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

# Arm order, default label and loop. --label overrides a label (e.g. the Qwen fallback).
ARMS = [
    ("A1", "DeepSeek V4.1 Flash, one-shot", "one-shot"),
    ("A6", "DeepSeek V4.1 Flash + repair", "repair"),
    ("A2", "Nemotron Lightning 3.5, one-shot", "one-shot"),
    ("A3", "Nemotron Lightning 3.5 + repair", "repair"),
    ("B1", "DeepSeek V4.1 Flash, security reminder", "one-shot"),
    ("B2", "Nemotron Lightning 3.5, security reminder", "one-shot"),
    ("A4", "Nemotron Nano 3 tuned, one-shot", "one-shot"),
    ("A5", "Nemotron Nano 3 tuned + repair", "repair"),
]
ARM_IDS = [a[0] for a in ARMS]

# Each repair arm and the one-shot arm it is compared with, record by record.
PAIRS = [("A6", "A1"), ("A3", "A2"), ("A5", "A4")]

Z95 = 1.959964  # two-sided 95% normal quantile

REQUIRED = {
    "arm": str, "model": str, "scenario": str, "framework": str, "run": int,
    "functional_pass": bool, "secure_pass": bool, "cwes": list,
    "cost_usd": (int, float), "latency_s": (int, float),
}


class InputError(Exception):
    pass


def _check(rec: object, where: str) -> dict:
    if not isinstance(rec, dict):
        raise InputError(f"{where}: run record is not a JSON object")
    for key, typ in REQUIRED.items():
        val = rec.get(key)
        # bool is an int in Python; do not let True pass as a run number or a cost.
        if not isinstance(val, typ) or (typ is not bool and isinstance(val, bool)):
            raise InputError(f"{where}: '{key}' missing or wrong type")
    if rec["arm"] not in ARM_IDS:
        raise InputError(f"{where}: unknown arm {rec['arm']!r}")
    if rec["secure_pass"] and not rec["functional_pass"]:
        raise InputError(f"{where}: secure_pass is true but functional_pass is false")
    if not all(isinstance(c, int) and not isinstance(c, bool) for c in rec["cwes"]):
        raise InputError(f"{where}: 'cwes' must be a list of CWE numbers")
    if rec["cost_usd"] < 0 or rec["latency_s"] < 0:
        raise InputError(f"{where}: negative cost_usd or latency_s")
    return rec


def load_runs(runs_dir: str) -> List[dict]:
    root = Path(runs_dir)
    if not root.is_dir():
        raise InputError(f"runs directory {runs_dir} not found")
    records, seen = [], {}
    for path in sorted(root.rglob("*.json")):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise InputError(f"{path}: cannot read run record: {e}") from e
        _check(rec, str(path))
        key = (rec["arm"], rec["scenario"], rec["framework"], rec["run"])
        if key in seen:
            raise InputError(f"{path}: same arm, scenario, framework and run as {seen[key]}")
        seen[key] = path
        records.append(rec)
    return records


def wilson(k: int, n: int, z: float = Z95) -> List[float]:
    """95% Wilson score interval for k successes in n trials, as [lo, hi] fractions."""
    if n <= 0 or not 0 <= k <= n:
        raise ValueError(f"need 0 <= k <= n and n > 0, got k={k}, n={n}")
    p = k / n
    z2 = z * z
    centre = (p + z2 / (2 * n)) / (1 + z2 / n)
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / (1 + z2 / n)
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def _arm_summary(arm: str, label: str, loop: str, recs: List[dict]) -> dict:
    models = sorted({r["model"] for r in recs})
    if len(models) > 1:
        raise InputError(f"arm {arm} mixes models: {', '.join(models)}")
    n = len(recs)
    secure = sum(r["secure_pass"] for r in recs)
    functional = sum(r["functional_pass"] for r in recs)
    total_cost = sum(r["cost_usd"] for r in recs)
    cwes = Counter(c for r in recs for c in set(r["cwes"]))
    return {
        "arm": arm,
        "label": label,
        "model": models[0],
        "loop": loop,
        "n": n,
        "functional_pass_rate": round(functional / n, 4),
        "secure_pass_rate": round(secure / n, 4),
        "cost_per_100_tasks_usd": round(total_cost / n * 100, 6),
        "cost_per_secure_app_usd": round(total_cost / secure, 6) if secure else None,
        "median_latency_s": round(statistics.median(r["latency_s"] for r in recs), 2),
        "cwe_counts": {str(c): cwes[c] for c in sorted(cwes)},
        "functional_pass_ci": wilson(functional, n),
        "secure_pass_ci": wilson(secure, n),
    }


def paired_gains(records: List[dict]) -> List[dict]:
    """Secure apps a repair arm gained and lost against its one-shot arm.

    Records pair on (scenario, framework, run). A record with no partner counts as unpaired.
    """
    by_arm: Dict[str, Dict[tuple, bool]] = {}
    for r in records:
        by_arm.setdefault(r["arm"], {})[(r["scenario"], r["framework"], r["run"])] = r["secure_pass"]
    out = []
    for repair, base in PAIRS:
        if repair not in by_arm or base not in by_arm:
            continue
        rep, one = by_arm[repair], by_arm[base]
        both = rep.keys() & one.keys()
        out.append({
            "arm": repair,
            "vs": base,
            "fixed": sum(rep[k] and not one[k] for k in both),
            "broken": sum(one[k] and not rep[k] for k in both),
            "same": sum(rep[k] == one[k] for k in both),
            "unpaired": len(rep.keys() ^ one.keys()),
        })
    return out


def build_results(records: List[dict], labels: Optional[Dict[str, str]] = None,
                  now: Optional[datetime] = None) -> dict:
    labels = labels or {}
    by_arm: Dict[str, List[dict]] = {}
    for r in records:
        by_arm.setdefault(r["arm"], []).append(r)
    arms = [_arm_summary(arm, labels.get(arm, label), loop, by_arm[arm])
            for arm, label, loop in ARMS if arm in by_arm]
    runs_per = Counter((r["arm"], r["scenario"], r["framework"]) for r in records)
    now = now or datetime.now(timezone.utc)
    out = {
        "generated_at": now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scenarios": len({r["scenario"] for r in records}),
        "runs_per_scenario": max(runs_per.values()) if runs_per else 0,
        "arms": arms,
        "paired": paired_gains(records),
    }
    if any(r.get("FAKE") for r in records):
        out = {"FAKE": True, **out}
    return out


def _money(x: Optional[float]) -> str:
    if x is None:
        return "n/a"
    return f"${x:.2f}" if x >= 1 else f"${x:.4f}"


def _rate_ci(rate: float, ci: List[float]) -> str:
    return f"{rate * 100:.1f}% ({ci[0] * 100:.0f}-{ci[1] * 100:.0f})"


def paired_lines(results: dict) -> List[str]:
    lines = []
    for g in results.get("paired", []):
        line = f"{g['arm']} vs {g['vs']}: +{g['fixed']} fixed, -{g['broken']} broken, {g['same']} same"
        if g["unpaired"]:
            line += f", {g['unpaired']} unpaired"
        lines.append(line)
    return lines


def markdown_table(results: dict) -> str:
    lines = [
        "| Arm | Label | n | Functional | Secure | Cost / 100 tasks | Cost / secure app | Median latency |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for a in results["arms"]:
        lines.append(
            f"| {a['arm']} | {a['label']} | {a['n']} "
            f"| {_rate_ci(a['functional_pass_rate'], a['functional_pass_ci'])} "
            f"| {_rate_ci(a['secure_pass_rate'], a['secure_pass_ci'])} "
            f"| {_money(a['cost_per_100_tasks_usd'])} | {_money(a['cost_per_secure_app_usd'])} "
            f"| {a['median_latency_s']:.1f} s |"
        )
    return "\n".join(lines)


def _parse_label(text: str) -> tuple:
    arm, sep, label = text.partition("=")
    if not sep or arm not in ARM_IDS or not label:
        raise argparse.ArgumentTypeError(f"expected ARM=label with ARM in {', '.join(ARM_IDS)}")
    return arm, label


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--runs", required=True, help="directory of run record JSON files")
    p.add_argument("--out", required=True, help="results.json to write")
    p.add_argument("--label", action="append", type=_parse_label, default=[],
                   metavar="ARM=LABEL", help="override an arm's label; may repeat")
    args = p.parse_args(argv)
    try:
        records = load_runs(args.runs)
        if not records:
            raise InputError(f"no run records under {args.runs}")
        results = build_results(records, dict(args.label))
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(markdown_table(results))
    pairs = paired_lines(results)
    if pairs:
        print()
        print("\n".join(pairs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
