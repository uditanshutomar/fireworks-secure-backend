# Contracts

Everyone builds against these shapes so the pieces fit at 2:00 PM. Change them only in an issue comment that tags everyone.

Python code must run on Python 3.9 (P2 runs 3.9). Use `from __future__ import annotations`, no `match`, no `X | Y` types at runtime. Standard library only, plus pytest for tests.

## Arms

| Arm | Model | Loop |
|---|---|---|
| A1 | DeepSeek V4.1 Flash 1017 (reference) | one-shot |
| A2 | Nemotron Nano 3 30B A3B, base | one-shot |
| A3 | Nemotron Nano 3 30B A3B, base | repair loop |
| A4 | Nemotron Nano 3 30B A3B, fine-tuned (LoRA SFT) | one-shot |
| A5 | Nemotron Nano 3 30B A3B, fine-tuned (LoRA SFT) | repair loop |

12 locked test scenarios x 3 runs per arm. The locked list lives only on P1 in `private/split.json` and is never committed until results are final.

## Definitions

- `functional_pass`: every BaxBench functional test passed.
- `secure_pass`: `functional_pass` is true AND no BaxBench exploit succeeded. This is BaxBench's "correct and secure".
- `cost_usd`: Fireworks list price x tokens, summed over every model call in the run (all repair rounds).
- `latency_s`: wall time of all model calls in the run, not Docker time.

## 1. Run record: `runs/<arm>/<scenario>__<framework>__r<run>.json`

One file per (arm, scenario, run).

```json
{
  "arm": "A3",
  "model": "accounts/fireworks/models/nemotron-nano-3-30b-a3b",
  "scenario": "Login",
  "framework": "Python-Flask",
  "run": 1,
  "functional_pass": true,
  "secure_pass": true,
  "cwes": [],
  "rounds": 2,
  "tokens_in": 5400,
  "tokens_out": 2100,
  "cost_usd": 0.0012,
  "latency_s": 9.4,
  "steps": [
    {
      "round": 0,
      "code": "from flask import Flask\n...",
      "functional_pass": true,
      "secure_pass": false,
      "failed_tests": [],
      "exploits_triggered": [{"cwe": 89, "name": "sql_injection_login"}],
      "tokens_in": 1800,
      "tokens_out": 1200,
      "latency_s": 4.1
    },
    {
      "round": 1,
      "code": "from flask import Flask\n...",
      "functional_pass": true,
      "secure_pass": true,
      "failed_tests": [],
      "exploits_triggered": [],
      "tokens_in": 3600,
      "tokens_out": 900,
      "latency_s": 5.3
    }
  ]
}
```

One-shot arms have exactly one step with `round: 0`. `cwes` is the union of CWE numbers triggered in the final step.

## 2. Results: `results/results.json` (dashboard reads this)

Built by `results_table.py` from all run records.

```json
{
  "generated_at": "2026-11-02T21:30:00Z",
  "scenarios": 12,
  "runs_per_scenario": 3,
  "arms": [
    {
      "arm": "A1",
      "label": "DeepSeek V4.1 Flash, one-shot",
      "model": "accounts/fireworks/models/deepseek-v4p1-flash-1017",
      "loop": "one-shot",
      "n": 36,
      "functional_pass_rate": 0.61,
      "secure_pass_rate": 0.39,
      "cost_per_100_tasks_usd": 0.42,
      "cost_per_secure_app_usd": 0.0108,
      "median_latency_s": 7.9,
      "cwe_counts": {"89": 3, "79": 5}
    }
  ]
}
```

- Rates are fractions 0 to 1, rounded to 4 places.
- `cost_per_100_tasks_usd` = mean `cost_usd` x 100.
- `cost_per_secure_app_usd` = total `cost_usd` / count of `secure_pass`; `null` when the count is 0.
- `cwe_counts` counts final-step CWEs across runs, keys are strings.
- Arms appear in order A1 to A5; an arm with no run records is left out.

## 3. Repair loop: `src/secure_backend/repair_loop.py`

```python
def repair_loop(client, task_prompt, run_tests, max_rounds=3, framework="Python-Flask"):
    """Returns a dict with keys rounds, functional_pass, secure_pass, cwes,
    tokens_in, tokens_out, latency_s, steps (shapes as in the run record)."""
```

- `client.generate(messages)` takes OpenAI-style `[{"role": ..., "content": ...}]` and returns `{"text": str, "tokens_in": int, "tokens_out": int, "latency_s": float}`.
- `run_tests(code)` returns `{"functional_pass": bool, "secure_pass": bool, "failed_tests": [str], "exploits_triggered": [{"cwe": int, "name": str}]}`.
- Round 0 is the first attempt. Stop as soon as `secure_pass` is true or after `max_rounds` repairs (so at most `max_rounds + 1` steps).
- The repair prompt names the failing test names and the CWE numbers and exploit names. It never includes exploit source code or test source code.
- Extract code from the model text: the first fenced code block, or the whole text if there is none.
- `max_rounds=0` gives the one-shot arms.

## 4. Split check: `scripts/check_split.py`

`python3 scripts/check_split.py --split private/split.json --sft data/sft.jsonl` exits 1 if any SFT example's `metadata.scenario` is in the split's `test` list, and prints the offending lines. Split shape: `{"test": ["Login", ...], "dev": [...], "train": [...]}`. SFT lines: `{"messages": [...], "metadata": {"scenario": "...", "framework": "..."}}`.
