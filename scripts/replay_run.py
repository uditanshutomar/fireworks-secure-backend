"""Replays one repair run record in the terminal, round by round, for the demo video.

python3 scripts/replay_run.py ui/sample/runs/A5__FakeLogin__Python-Flask__r1.json --delay 1.0

Reads one run record (CONTRACTS.md section 1). For each round it prints the first
25 lines of code, the test result, any exploits, and the repair message that went
back to the model. Then one final line with the verdict, cost and time.
Exit 0 on success, 2 when the file is missing or is not a run record.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from secure_backend.repair_loop import build_repair_prompt  # noqa: E402

CODE_LINES = 25
REPLY_FORMAT = "reply with the full file inside <CODE></CODE> tags and nothing else"

_STYLES = {"bold": "1", "dim": "2", "red": "31", "green": "32", "yellow": "33"}


class InputError(Exception):
    pass


def paint(text: str, style: str, color: bool) -> str:
    if not color:
        return text
    return "\033[{}m{}\033[0m".format(_STYLES[style], text)


def money(usd: float) -> str:
    """$0.0012 style: at least 4 decimals, up to 6 so small Nemotron costs do not show as zero."""
    s = "{:.6f}".format(float(usd)).rstrip("0")
    whole, _, frac = s.partition(".")
    return "${}.{}".format(whole, frac.ljust(4, "0"))


def load_record(path: Path) -> Dict[str, Any]:
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise InputError("no such file: {}".format(path))
    except (OSError, ValueError) as e:
        raise InputError("cannot read {}: {}".format(path, e))
    steps = rec.get("steps") if isinstance(rec, dict) else None
    if not isinstance(steps, list) or not steps or not all(isinstance(s, dict) for s in steps):
        raise InputError("{} is not a run record (no steps)".format(path))
    return rec


def render_step(step: Dict[str, Any], is_last: bool, color: bool) -> List[str]:
    out = [paint("Round {}".format(step.get("round", 0)), "bold", color)]
    code = str(step.get("code") or "").splitlines()
    for line in code[:CODE_LINES]:
        out.append(paint("    " + line, "dim", color))
    if len(code) > CODE_LINES:
        out.append(paint("    ... ({} more lines)".format(len(code) - CODE_LINES), "dim", color))
    failed = [str(t) for t in step.get("failed_tests") or []]
    if step.get("functional_pass") and not failed:
        out.append(paint("PASS", "green", color))
    elif failed:
        for t in failed:
            out.append(paint("FAIL " + t, "red", color))
    else:
        out.append(paint("FAIL", "red", color))
    for e in step.get("exploits_triggered") or []:
        out.append(paint("EXPLOIT CWE-{} {}".format(int(e["cwe"]), e["name"]), "red", color))
    if not is_last:
        out.append(paint("Repair message sent to the model:", "yellow", color))
        for line in build_repair_prompt(step, REPLY_FORMAT).splitlines():
            out.append(paint("  > " + line, "yellow", color))
    return out


def final_line(rec: Dict[str, Any], color: bool) -> str:
    rounds = rec.get("rounds", len(rec["steps"]))
    if rec.get("secure_pass"):
        text = "SECURE after {} rounds, {}, {:.1f} s".format(
            rounds, money(rec.get("cost_usd", 0.0)), float(rec.get("latency_s", 0.0)))
        return paint(text, "green", color)
    return paint("NOT SECURE after {} rounds".format(rounds), "red", color)


def replay(rec: Dict[str, Any], delay: float = 0.0, color: bool = True, out: Any = None) -> None:
    out = out or sys.stdout
    title = "{} {} {} run {}".format(rec.get("arm", "?"), rec.get("scenario", "?"),
                                     rec.get("framework", "?"), rec.get("run", "?"))
    print(paint(title, "bold", color), file=out)
    steps = rec["steps"]
    for i, step in enumerate(steps):
        if i and delay > 0:
            out.flush()
            time.sleep(delay)
        print("", file=out)
        for line in render_step(step, i == len(steps) - 1, color):
            print(line, file=out)
    if delay > 0:
        out.flush()
        time.sleep(delay)
    print("", file=out)
    print(final_line(rec, color), file=out)


def main(argv: List[str] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("record", help="path to one run record JSON")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between rounds (default 1.0)")
    ap.add_argument("--no-color", action="store_true", help="plain text, no ANSI colors")
    args = ap.parse_args(argv)
    try:
        rec = load_record(Path(args.record))
    except InputError as e:
        print("replay_run: " + str(e), file=sys.stderr)
        return 2
    replay(rec, delay=max(args.delay, 0.0), color=not args.no_color)
    return 0


if __name__ == "__main__":
    sys.exit(main())
