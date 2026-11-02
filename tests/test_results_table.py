from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import results_table  # noqa: E402

MODELS = {
    "A1": "accounts/fireworks/models/deepseek-v4p1-flash-1017",
    "A2": "accounts/fireworks/models/nemotron-nano-3-30b-a3b",
    "A3": "accounts/fireworks/models/nemotron-nano-3-30b-a3b",
}


def rec(arm, scenario, run, fp, sp, cost, latency, cwes=(), framework="Python-Flask"):
    return {
        "arm": arm, "model": MODELS[arm], "scenario": scenario, "framework": framework,
        "run": run, "functional_pass": fp, "secure_pass": sp, "cwes": list(cwes),
        "rounds": 1, "tokens_in": 100, "tokens_out": 50, "cost_usd": cost, "latency_s": latency,
        "steps": [],
    }


def write_runs(root, records):
    for r in records:
        d = root / r["arm"]
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{r['scenario']}__{r['framework']}__r{r['run']}.json").write_text(json.dumps(r))


RECORDS = [
    # A3: 4 runs, 3 secure, even-count median.
    rec("A3", "Login", 1, True, True, 0.002, 4.0),
    rec("A3", "Login", 2, True, True, 0.002, 6.0),
    rec("A3", "Upload", 1, True, False, 0.004, 9.0, cwes=(89, 79)),
    rec("A3", "Upload", 2, True, True, 0.004, 1.0),
    # A2: 3 runs, 0 secure.
    rec("A2", "Login", 1, False, False, 0.001, 3.0, cwes=(89,)),
    rec("A2", "Login", 2, True, False, 0.001, 5.0, cwes=(89, 22)),
    rec("A2", "Upload", 1, False, False, 0.001, 4.0),
]


def build(tmp_path, records=RECORDS):
    write_runs(tmp_path / "runs", records)
    return results_table.build_results(
        results_table.load_runs(str(tmp_path / "runs")),
        now=datetime(2026, 11, 2, 21, 30, tzinfo=timezone.utc))


def test_header_fields(tmp_path):
    res = build(tmp_path)
    assert res["generated_at"] == "2026-11-02T21:30:00Z"
    assert res["scenarios"] == 2
    assert res["runs_per_scenario"] == 2
    assert "FAKE" not in res


def test_arm_order_and_missing_arms_left_out(tmp_path):
    assert [a["arm"] for a in build(tmp_path)["arms"]] == ["A2", "A3"]


def test_repair_arm_numbers(tmp_path):
    a3 = build(tmp_path)["arms"][1]
    assert a3["label"] == "Nemotron Nano 3 + repair"
    assert a3["loop"] == "repair"
    assert a3["model"] == MODELS["A3"]
    assert a3["n"] == 4
    assert a3["functional_pass_rate"] == 1.0
    assert a3["secure_pass_rate"] == 0.75
    assert a3["cost_per_100_tasks_usd"] == pytest.approx(0.3)
    assert a3["cost_per_secure_app_usd"] == pytest.approx(0.004)
    assert a3["median_latency_s"] == 5.0  # median of 1, 4, 6, 9
    assert a3["cwe_counts"] == {"79": 1, "89": 1}


def test_zero_secure_gives_null_cost_per_secure_app(tmp_path):
    a2 = build(tmp_path)["arms"][0]
    assert a2["secure_pass_rate"] == 0.0
    assert a2["cost_per_secure_app_usd"] is None
    assert a2["functional_pass_rate"] == 0.3333
    assert a2["median_latency_s"] == 4.0
    assert a2["cwe_counts"] == {"22": 1, "89": 2}


def test_cwe_counted_once_per_run(tmp_path):
    res = build(tmp_path, [rec("A1", "Login", 1, False, False, 0.01, 1.0, cwes=(89, 89))])
    assert res["arms"][0]["cwe_counts"] == {"89": 1}


def test_label_override_and_cli_writes_file(tmp_path):
    write_runs(tmp_path / "runs", RECORDS)
    out = tmp_path / "results" / "results.json"
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "results_table.py"), "--runs", str(tmp_path / "runs"),
         "--out", str(out), "--label", "A3=Qwen tuned + repair"],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    res = json.loads(out.read_text())
    assert res["arms"][1]["label"] == "Qwen tuned + repair"
    table = r.stdout.splitlines()
    assert table[0].startswith("| Arm | Label | n |")
    assert table[2] == "| A2 | Nemotron Nano 3, one-shot | 3 | 33.3% | 0.0% | $0.1000 | n/a | 4.0 s |"
    assert table[3] == "| A3 | Qwen tuned + repair | 4 | 100.0% | 75.0% | $0.3000 | $0.0040 | 5.0 s |"


@pytest.mark.parametrize("change", [
    {"arm": "A9"},
    {"run": "1"},
    {"run": True},
    {"cost_usd": None},
    {"cost_usd": -1},
    {"secure_pass": "yes"},
    {"cwes": ["89"]},
    {"functional_pass": False, "secure_pass": True},
])
def test_bad_record_exits_2(tmp_path, change):
    write_runs(tmp_path / "runs", [dict(rec("A1", "Login", 1, True, True, 0.01, 1.0), **change)])
    assert results_table.main(["--runs", str(tmp_path / "runs"), "--out", str(tmp_path / "o.json")]) == 2
    assert not (tmp_path / "o.json").exists()


def test_bad_json_duplicates_mixed_models_and_empty_exit_2(tmp_path):
    args = ["--runs", str(tmp_path / "runs"), "--out", str(tmp_path / "o.json")]
    assert results_table.main(args) == 2  # no directory
    (tmp_path / "runs").mkdir()
    assert results_table.main(args) == 2  # no records
    (tmp_path / "runs" / "x.json").write_text("{nope")
    assert results_table.main(args) == 2
    (tmp_path / "runs" / "x.json").unlink()
    write_runs(tmp_path / "runs", [rec("A1", "Login", 1, True, True, 0.01, 1.0)])
    (tmp_path / "runs" / "copy.json").write_text(json.dumps(rec("A1", "Login", 1, True, True, 0.01, 1.0)))
    assert results_table.main(args) == 2  # duplicate run
    (tmp_path / "runs" / "copy.json").write_text(
        json.dumps(dict(rec("A1", "Login", 2, True, True, 0.01, 1.0), model="other")))
    assert results_table.main(args) == 2  # mixed models


def test_ui_sample_runs(tmp_path, capsys):
    out = tmp_path / "results.json"
    assert results_table.main(["--runs", str(ROOT / "ui" / "sample" / "runs"), "--out", str(out)]) == 0
    res = json.loads(out.read_text())
    assert res["FAKE"] is True
    assert res["scenarios"] == 1 and res["runs_per_scenario"] == 1
    (a5,) = res["arms"]
    assert a5["arm"] == "A5" and a5["n"] == 1
    assert a5["secure_pass_rate"] == 1.0
    assert a5["cost_per_100_tasks_usd"] == pytest.approx(0.12)
    assert a5["cost_per_secure_app_usd"] == pytest.approx(0.0012)
    assert a5["median_latency_s"] == 9.4
    assert a5["cwe_counts"] == {}
    assert "| A5 | Nemotron Nano 3 tuned + repair | 1 | 100.0% | 100.0% |" in capsys.readouterr().out
