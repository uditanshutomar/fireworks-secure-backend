"""Runs one arm on a set of scenarios and writes one run record per (scenario, framework, run).

    .venv-bax/bin/python scripts/run_arm.py --arm A1 --set test --runs 3
    .venv-bax/bin/python scripts/run_arm.py --arm A1 --set train --runs 2 --out data/gen   # training data

Docker and the Fireworks key are needed, so this runs only on P1.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from secure_backend import baxbench_runner as bax  # noqa: E402
from secure_backend.fireworks_client import FireworksClient  # noqa: E402
from secure_backend.repair_loop import repair_loop  # noqa: E402


def load_examples(arm, split):
    """Worked examples for in-context distillation: exploit-verified training apps, never a test scenario."""
    picks = arm.get("examples")
    if not picks:
        return None
    rows = [json.loads(l) for l in (ROOT / "training" / "sft_with_metadata.jsonl").read_text().splitlines() if l]
    out = []
    for scenario, framework in picks:
        if scenario in split["test"]:
            sys.exit(f"example scenario {scenario} is in the test set")
        row = next(r for r in rows if r["metadata"] == {"scenario": scenario, "framework": framework})
        out += [m for m in row["messages"] if m["role"] in ("user", "assistant")]
    return out


def run_task(arm_id, arm, client, scenario, framework, run, out_dir, examples=None):
    path = out_dir / arm_id / f"{scenario}__{framework}__r{run}.json"
    if path.exists():
        return path, "skip"
    messages = bax.build_messages(scenario, framework, arm.get("safety_prompt", "none"))
    code_file = bax.ENVS[framework].code_filename or "app.py"

    def run_tests(code):
        return bax.run_tests(scenario, framework, {code_file: code} if code else {})

    # Every arm gets BaxBench's own system prompt and parser, so arms differ only by model and loop.
    out = repair_loop(client, messages[-1]["content"], run_tests, max_rounds=arm["max_rounds"],
                      framework=framework, system_prompt=messages[0]["content"],
                      extract=lambda t: next(iter(bax.extract_files(framework, t).values()), ""),
                      reply_format="reply with the full file inside <CODE></CODE> tags and nothing else",
                      examples=examples)
    record = {"arm": arm_id, "model": arm["model"], "scenario": scenario, "framework": framework, "run": run,
              "functional_pass": out["functional_pass"], "secure_pass": out["secure_pass"], "cwes": out["cwes"],
              "rounds": out["rounds"], "tokens_in": out["tokens_in"], "tokens_out": out["tokens_out"],
              "cost_usd": round(client.cost(out["tokens_in"], out["tokens_out"]), 6),
              "latency_s": round(out["latency_s"], 3), "steps": out["steps"]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2) + "\n")
    return path, "secure" if record["secure_pass"] else ("functional" if record["functional_pass"] else "fail")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True)
    ap.add_argument("--set", choices=["test", "train"], required=True)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--scenarios", nargs="*", help="subset of the set, for smoke runs")
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--out", default="results/runs")
    args = ap.parse_args()

    arm = json.loads((ROOT / "arms.json").read_text())[args.arm]
    split = json.loads((ROOT / "private" / "split.json").read_text())
    scenarios = args.scenarios or split[args.set]
    unknown = set(scenarios) - set(split[args.set])
    if unknown:
        sys.exit(f"not in the {args.set} set: {sorted(unknown)}")
    frameworks = split["framework_test"] if args.set == "test" else split["frameworks_train"]
    client = FireworksClient(arm["model"], price_model=arm.get("price_model"), max_tokens=arm.get("max_tokens", 8192),
                             key_env=arm.get("key_env", "FIREWORKS_API_KEY"))
    out_dir = ROOT / args.out
    examples = load_examples(arm, split)
    jobs = [(s, f, r) for s in scenarios for f in frameworks for r in range(1, args.runs + 1)]
    print(f"{args.arm}: {len(jobs)} runs, {args.jobs} at a time", flush=True)
    start = time.time()
    counts: dict = {}
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        futs = {pool.submit(run_task, args.arm, arm, client, s, f, r, out_dir, examples): (s, f, r) for s, f, r in jobs}
        for fut in concurrent.futures.as_completed(futs):
            s, f, r = futs[fut]
            try:
                _, status = fut.result()
            except Exception:  # noqa: BLE001
                status = "error"
                traceback.print_exc()
            counts[status] = counts.get(status, 0) + 1
            print(f"[{time.time() - start:6.0f}s] {s} {f} r{r}: {status}  {counts}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
