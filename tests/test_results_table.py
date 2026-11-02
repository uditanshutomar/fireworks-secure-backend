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
    assert a3["label"] == "Nemotron Lightning 3.5 + repair"
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
    assert table[2] == ("| A2 | Nemotron Lightning 3.5, one-shot | 3 | 33.3% (6-79) | 0.0% (0-56) "
                        "| $0.1000 | n/a | 4.0 s |")
    assert table[3] == ("| A3 | Qwen tuned + repair | 4 | 100.0% (51-100) | 75.0% (30-95) "
                        "| $0.3000 | $0.0040 | 5.0 s |")
    assert table[4:] == ["", "A3 vs A2: +2 fixed, -0 broken, 1 same, 1 unpaired"]


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
    assert "| A5 | Nemotron Nano 3 tuned + repair | 1 | 100.0% (21-100) | 100.0% (21-100) |" \
        in capsys.readouterr().out
    assert res["paired"] == []


@pytest.mark.parametrize("k, n, ci", [
    (0, 12, [0.0, 0.2425]),
    (6, 12, [0.2538, 0.7462]),
    (12, 12, [0.7575, 1.0]),
    (8, 12, [0.3906, 0.8619]),  # the issue's 66.7% (39-86)
    (1, 1, [0.2065, 1.0]),
])
def test_wilson_known_values(k, n, ci):
    assert results_table.wilson(k, n) == ci


@pytest.mark.parametrize("k, n", [(0, 0), (-1, 3), (4, 3)])
def test_wilson_rejects_bad_counts(k, n):
    with pytest.raises(ValueError):
        results_table.wilson(k, n)


def test_arm_ci_fields(tmp_path):
    a2, a3 = build(tmp_path)["arms"]
    assert a3["secure_pass_ci"] == results_table.wilson(3, 4)
    assert a3["functional_pass_ci"] == results_table.wilson(4, 4)
    assert a2["secure_pass_ci"] == results_table.wilson(0, 3)
    assert a2["functional_pass_ci"] == results_table.wilson(1, 3)


def test_pairing_on_scenario_framework_and_run():
    base = [
        rec("A1", "Login", 1, False, False, 0.01, 1.0),  # fixed
        rec("A1", "Login", 2, True, True, 0.01, 1.0),  # broken
        rec("A1", "Upload", 1, True, True, 0.01, 1.0),  # same, both secure
        rec("A1", "Forum", 1, True, False, 0.01, 1.0),  # same, both insecure
        # Same scenario and run as the Forum pair, other framework: no partner.
        rec("A1", "Forum", 1, True, True, 0.01, 1.0, framework="Python-FastAPI"),
    ]
    repair = [dict(r, arm="A6") for r in [
        rec("A1", "Login", 1, True, True, 0.01, 1.0),
        rec("A1", "Login", 2, True, False, 0.01, 1.0),
        rec("A1", "Upload", 1, True, True, 0.01, 1.0),
        rec("A1", "Forum", 1, False, False, 0.01, 1.0),
        # Same scenario, other run: no partner, so not counted as fixed.
        rec("A1", "Forum", 2, True, True, 0.01, 1.0),
    ]]
    assert results_table.paired_gains(base + repair) == [
        {"arm": "A6", "vs": "A1", "fixed": 1, "broken": 1, "same": 2, "unpaired": 2},
    ]
    res = {"paired": results_table.paired_gains(base + repair)}
    assert results_table.paired_lines(res) == ["A6 vs A1: +1 fixed, -1 broken, 2 same, 2 unpaired"]


def test_pairing_skips_missing_arms_and_keeps_order():
    recs = [rec("A3", "Login", 1, True, True, 0.01, 1.0), rec("A2", "Login", 1, True, False, 0.01, 1.0),
            rec("A1", "Login", 1, True, True, 0.01, 1.0)]
    assert results_table.paired_gains(recs) == [
        {"arm": "A3", "vs": "A2", "fixed": 1, "broken": 0, "same": 0, "unpaired": 0},
    ]
    assert results_table.paired_lines({"paired": results_table.paired_gains(recs)}) == [
        "A3 vs A2: +1 fixed, -0 broken, 0 same"]
