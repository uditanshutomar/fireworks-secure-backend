"""Writes FAKE sample data to ui/sample/ so the dashboard can be built before real runs exist."""
from __future__ import annotations

import json
import random
from pathlib import Path

ARMS = [
    ("A1", "DeepSeek V4.1 Flash, one-shot", "accounts/fireworks/models/deepseek-v4p1-flash-1017", "one-shot", 0.62, 0.40, 0.0042),
    ("A2", "Nemotron Nano 3, one-shot", "accounts/fireworks/models/nemotron-nano-3-30b-a3b", "one-shot", 0.45, 0.22, 0.0009),
    ("A3", "Nemotron Nano 3 + repair", "accounts/fireworks/models/nemotron-nano-3-30b-a3b", "repair", 0.58, 0.36, 0.0024),
    ("A4", "Nemotron Nano 3 tuned, one-shot", "FAKE-tuned-model", "one-shot", 0.56, 0.38, 0.0009),
    ("A5", "Nemotron Nano 3 tuned + repair", "FAKE-tuned-model", "repair", 0.66, 0.52, 0.0021),
]
SCENARIOS = ["FakeLogin", "FakeUpload", "FakeNotes", "FakeShop"]
CWES = [79, 89, 22, 78, 20, 284, 400, 703]


def main() -> None:
    rng = random.Random(7)
    out = Path(__file__).resolve().parent.parent / "ui" / "sample"
    (out / "runs").mkdir(parents=True, exist_ok=True)
    arms = []
    for arm, label, model, loop, fp, sp, cost in ARMS:
        n = 36
        secure = round(sp * n)
        arms.append({
            "arm": arm, "label": label, "model": model, "loop": loop, "n": n,
            "functional_pass_rate": fp, "secure_pass_rate": sp,
            "cost_per_100_tasks_usd": round(cost * 100, 4),
            "cost_per_secure_app_usd": round(cost * n / secure, 4) if secure else None,
            "median_latency_s": round(rng.uniform(4, 14) * (2 if loop == "repair" else 1), 1),
            "cwe_counts": {str(c): rng.randint(0, 6) for c in rng.sample(CWES, 4)},
        })
    (out / "results.json").write_text(json.dumps({
        "FAKE": True, "generated_at": "2026-11-02T20:00:00Z",
        "scenarios": 12, "runs_per_scenario": 3, "arms": arms}, indent=2) + "\n")
    # One repair-loop run record for the run viewer.
    steps = [
        {"round": 0, "code": "from flask import Flask, request\nimport sqlite3\napp = Flask(__name__)\n\n@app.post('/login')\ndef login():\n    u = request.json['username']\n    row = db.execute(f\"SELECT * FROM users WHERE name = '{u}'\").fetchone()\n    ...\n",
         "functional_pass": True, "secure_pass": False, "failed_tests": [],
         "exploits_triggered": [{"cwe": 89, "name": "sql_injection_login"}], "tokens_in": 1800, "tokens_out": 1200, "latency_s": 4.1},
        {"round": 1, "code": "from flask import Flask, request\nimport sqlite3\napp = Flask(__name__)\n\n@app.post('/login')\ndef login():\n    u = request.json['username']\n    row = db.execute('SELECT * FROM users WHERE name = ?', (u,)).fetchone()\n    ...\n",
         "functional_pass": True, "secure_pass": True, "failed_tests": [],
         "exploits_triggered": [], "tokens_in": 3600, "tokens_out": 900, "latency_s": 5.3},
    ]
    record = {"FAKE": True, "arm": "A5", "model": "FAKE-tuned-model", "scenario": "FakeLogin", "framework": "Python-Flask",
              "run": 1, "functional_pass": True, "secure_pass": True, "cwes": [], "rounds": 2,
              "tokens_in": 5400, "tokens_out": 2100, "cost_usd": 0.0012, "latency_s": 9.4, "steps": steps}
    (out / "runs" / "A5__FakeLogin__Python-Flask__r1.json").write_text(json.dumps(record, indent=2) + "\n")


if __name__ == "__main__":
    main()
