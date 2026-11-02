from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import replay_run as rr  # noqa: E402

SAMPLE = ROOT / "ui" / "sample" / "runs" / "A5__FakeLogin__Python-Flask__r1.json"


def step(rnd, fp, sp, exploits=(), failed=(), code="from flask import Flask\n"):
    return {
        "round": rnd, "code": code, "functional_pass": fp,
        "secure_pass": sp, "failed_tests": list(failed),
        "exploits_triggered": [{"cwe": c, "name": n} for c, n in exploits],
        "tokens_in": 10, "tokens_out": 5, "latency_s": 1.0,
    }


def rec(steps, cost=0.0012, latency=9.4):
    last = steps[-1]
    return {
        "arm": "A3", "model": "m", "scenario": "Login", "framework": "Python-Flask", "run": 1,
        "functional_pass": last["functional_pass"], "secure_pass": last["secure_pass"],
        "cwes": sorted({e["cwe"] for e in last["exploits_triggered"]}),
        "rounds": len(steps), "tokens_in": 10, "tokens_out": 5, "cost_usd": cost,
        "latency_s": latency, "steps": steps,
    }


def run(path, *extra):
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "replay_run.py"), str(path), "--no-color", "--delay", "0", *extra],
        capture_output=True, text=True,
    )


def write(tmp_path, record, name="r.json"):
    p = tmp_path / name
    p.write_text(json.dumps(record))
    return p


def test_sample_record_replays():
    r = run(SAMPLE)
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert "Round 0" in out and "Round 1" in out
    assert "EXPLOIT CWE-89 sql_injection_login" in out
    assert "Repair message sent to the model:" in out
    assert "<CODE></CODE> tags and nothing else" in out
    assert out.rstrip().splitlines()[-1] == "SECURE after 2 rounds, $0.0012, 9.4 s"
    assert "\033[" not in out


def test_repair_message_matches_build_repair_prompt(tmp_path):
    s0 = step(0, True, False, exploits=[(89, "sql_injection_login")])
    r = run(write(tmp_path, rec([s0, step(1, True, True)])))
    from secure_backend.repair_loop import build_repair_prompt
    for line in build_repair_prompt(s0, rr.REPLY_FORMAT).splitlines():
        assert "  > " + line in r.stdout


def test_no_repair_message_after_last_round(tmp_path):
    r = run(write(tmp_path, rec([step(0, True, True)])))
    assert "Repair message" not in r.stdout
    assert "PASS" in r.stdout
    assert r.stdout.rstrip().splitlines()[-1] == "SECURE after 1 rounds, $0.0012, 9.4 s"


def test_not_secure_final_line(tmp_path):
    steps = [step(i, False, False, failed=["func_test_login"]) for i in range(4)]
    r = run(write(tmp_path, rec(steps)))
    assert r.returncode == 0
    assert r.stdout.count("FAIL func_test_login") == 4
    assert r.stdout.count("Repair message sent to the model:") == 3
    assert r.stdout.rstrip().splitlines()[-1] == "NOT SECURE after 4 rounds"


def test_functional_fail_without_names_prints_fail(tmp_path):
    r = run(write(tmp_path, rec([step(0, False, False), step(1, True, True)])))
    lines = r.stdout.splitlines()
    assert "FAIL" in lines
    assert "no details" in r.stdout


def test_code_cut_to_25_lines(tmp_path):
    code = "".join("line{}\n".format(i) for i in range(40))
    r = run(write(tmp_path, rec([step(0, True, True, code=code)])))
    assert "    line24" in r.stdout
    assert "line25" not in r.stdout
    assert "... (15 more lines)" in r.stdout


def test_small_cost_not_zeroed():
    assert rr.money(0.000142) == "$0.000142"
    assert rr.money(0.0012) == "$0.0012"
    assert rr.money(0) == "$0.0000"


def test_color_output_has_ansi(tmp_path):
    p = write(tmp_path, rec([step(0, True, False, exploits=[(79, "xss")]), step(1, True, True)]))
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "replay_run.py"), str(p), "--delay", "0"],
                       capture_output=True, text=True)
    assert "\033[31mEXPLOIT CWE-79 xss\033[0m" in r.stdout
    assert "\033[32mPASS\033[0m" in r.stdout


def test_delay_sleeps_between_rounds(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(rr.time, "sleep", lambda s: calls.append(s))
    import io
    rr.replay(rec([step(0, True, False), step(1, True, True)]), delay=0.5, color=False, out=io.StringIO())
    assert calls == [0.5, 0.5]


def test_missing_file_exits_2(tmp_path):
    r = run(tmp_path / "nope.json")
    assert r.returncode == 2
    assert "no such file" in r.stderr


def test_not_a_record_exits_2(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text('{"arm": "A3"}')
    assert run(p).returncode == 2
    p.write_text("not json")
    assert run(p).returncode == 2
