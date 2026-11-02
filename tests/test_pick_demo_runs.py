from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import pick_demo_runs as pdr  # noqa: E402


def step(rnd, fp, sp, exploits=(), failed=()):
    return {
        "round": rnd, "code": "from flask import Flask\n", "functional_pass": fp,
        "secure_pass": sp, "failed_tests": list(failed),
        "exploits_triggered": [{"cwe": c, "name": n} for c, n in exploits],
        "tokens_in": 10, "tokens_out": 5, "latency_s": 1.0,
    }


def rec(arm, scenario, run, steps, framework="Python-Flask"):
    last = steps[-1]
    return {
        "arm": arm, "model": "m", "scenario": scenario, "framework": framework, "run": run,
        "functional_pass": last["functional_pass"], "secure_pass": last["secure_pass"],
        "cwes": sorted({e["cwe"] for e in last["exploits_triggered"]}),
        "rounds": len(steps), "tokens_in": 10, "tokens_out": 5, "cost_usd": 0.001,
        "latency_s": 1.0, "steps": steps,
    }


def fixed(arm, scenario, run, cwe, name, fix_round=1):
    steps = [step(0, True, False, [(cwe, name)])]
    for r in range(1, fix_round):
        steps.append(step(r, True, False, [(cwe, name)]))
    steps.append(step(fix_round, True, True))
    return rec(arm, scenario, run, steps)


def write(root, records):
    for r in records:
        d = root / r["arm"]
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{r['scenario']}__{r['framework']}__r{r['run']}.json").write_text(json.dumps(r))


def picks_for(tmp_path, records, **kw):
    write(tmp_path / "runs", records)
    return pdr.pick(pdr.load_runs(str(tmp_path / "runs")), **kw)


def test_cwe_priority_order(tmp_path):
    recs = [
        fixed("A3", "Upload", 1, 79, "xss"),
        fixed("A3", "Shell", 1, 78, "os_injection"),
        fixed("A6", "Files", 1, 22, "path_traversal"),
        fixed("A3", "Login", 1, 89, "sql_injection", fix_round=2),
    ]
    got = [c["rec"]["scenario"] for c in picks_for(tmp_path, recs)]
    assert got == ["Login", "Files", "Shell", "Upload"]


def test_caption_shape(tmp_path):
    c = picks_for(tmp_path, [fixed("A3", "Login", 1, 89, "sql_injection", fix_round=2)])[0]
    assert c["caption"] == "A3 Login: CWE-89 sql_injection fixed on round 2"
    assert c["kind"] == "exploit_fixed"


def test_caption_names_top_cwe_of_several(tmp_path):
    r = rec("A3", "Login", 1, [step(0, True, False, [(79, "xss"), (89, "sqli")]), step(1, True, True)])
    assert picks_for(tmp_path, [r])[0]["caption"] == "A3 Login: CWE-89 sqli fixed on round 1"


def test_earlier_fix_wins_within_cwe(tmp_path):
    recs = [fixed("A3", "Login", 1, 89, "s", fix_round=3), fixed("A6", "Login", 2, 89, "s", fix_round=1)]
    got = picks_for(tmp_path, recs)
    assert [c["rec"]["arm"] for c in got] == ["A6", "A3"]


def test_spread_across_scenarios_first(tmp_path):
    recs = [fixed("A3", "Login", r, 89, "s") for r in (1, 2, 3)] + [fixed("A3", "Files", 1, 22, "p")]
    got = [(c["rec"]["scenario"], c["rec"]["run"]) for c in picks_for(tmp_path, recs)]
    assert got == [("Login", 1), ("Files", 1), ("Login", 2), ("Login", 3)]


def test_max_five_including_before(tmp_path):
    recs = [fixed("A3", f"S{i}", 1, 89, "s") for i in range(8)]
    recs.append(rec("A2", "S3", 1, [step(0, True, False, [(89, "s")])]))
    got = picks_for(tmp_path, recs)
    assert len(got) == 5
    assert [c["kind"] for c in got] == ["exploit_fixed"] * 4 + ["before"]


def test_before_prefers_shown_scenario_and_cwe(tmp_path):
    recs = [
        fixed("A3", "Login", 1, 89, "sql_injection"),
        rec("A2", "Alpha", 1, [step(0, True, False, [(89, "sql_injection")])]),
        rec("A2", "Login", 1, [step(0, True, False, [(79, "xss")])]),
        rec("A2", "Login", 2, [step(0, True, False, [(89, "sql_injection")])]),
    ]
    got = picks_for(tmp_path, recs)
    assert got[-1]["kind"] == "before"
    assert (got[-1]["rec"]["scenario"], got[-1]["rec"]["run"]) == ("Login", 2)
    assert got[-1]["caption"] == "A2 Login: CWE-89 sql_injection exploited, one-shot"


def test_secure_a2_is_not_a_before(tmp_path):
    recs = [fixed("A3", "Login", 1, 89, "s"), rec("A2", "Login", 1, [step(0, True, True)])]
    assert [c["kind"] for c in picks_for(tmp_path, recs)] == ["exploit_fixed"]


def test_fallback_fail_fixed_only_when_no_exploit_fixed(tmp_path):
    ff = rec("A3", "Todo", 1, [step(0, False, False, failed=["t1", "t2"]), step(1, True, True)])
    got = picks_for(tmp_path, [ff])
    assert got[0]["kind"] == "fail_fixed"
    assert got[0]["caption"] == "A3 Todo: 2 failing tests fixed on round 1"
    got = picks_for(tmp_path, [ff, fixed("A3", "Login", 1, 89, "s")])
    assert [c["kind"] for c in got] == ["exploit_fixed"]


def test_ignores_non_repair_arms_and_unfixed_runs(tmp_path):
    recs = [
        fixed("A1", "Login", 1, 89, "s"),
        fixed("A5", "Login", 1, 89, "s"),
        rec("A3", "Login", 1, [step(0, True, False, [(89, "s")]), step(1, True, False, [(89, "s")])]),
        rec("A3", "Easy", 1, [step(0, True, True)]),
    ]
    assert picks_for(tmp_path, recs) == []


def test_skips_bad_files(tmp_path, capsys):
    runs = tmp_path / "runs"
    write(runs, [fixed("A3", "Login", 1, 89, "s")])
    (runs / "junk.json").write_text("{not json")
    (runs / "raw.json").write_text(json.dumps({"exit": 0}))
    assert len(pdr.pick(pdr.load_runs(str(runs)))) == 1
    err = capsys.readouterr().err
    assert "junk.json" in err and "raw.json" in err


def test_write_demo_and_cli(tmp_path):
    runs = tmp_path / "runs"
    recs = [fixed("A3", "Login", 1, 89, "sql_injection", fix_round=2),
            rec("A2", "Login", 1, [step(0, True, False, [(89, "sql_injection")])])]
    recs[0]["FAKE"] = True
    write(runs, recs)
    out = tmp_path / "demo"
    (out / "runs").mkdir(parents=True)
    (out / "runs" / "stale.json").write_text("{}")
    p = subprocess.run([sys.executable, str(ROOT / "scripts" / "pick_demo_runs.py"),
                        "--runs", str(runs), "--out", str(out)],
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    index = json.loads((out / "index.json").read_text())
    assert index["FAKE"] is True
    assert [e["caption"] for e in index["runs"]] == [
        "A3 Login: CWE-89 sql_injection fixed on round 2",
        "A2 Login: CWE-89 sql_injection exploited, one-shot",
    ]
    files = sorted(f.name for f in (out / "runs").iterdir())
    assert files == ["A2__Login__Python-Flask__r1.json", "A3__Login__Python-Flask__r1.json"]
    for e in index["runs"]:
        assert json.loads((out / e["file"]).read_text())["arm"] == e["arm"]
    assert "fixed on round 2" in p.stdout


def test_cli_exit_2(tmp_path):
    script = str(ROOT / "scripts" / "pick_demo_runs.py")
    p = subprocess.run([sys.executable, script, "--runs", str(tmp_path / "nope"),
                        "--out", str(tmp_path / "demo")], capture_output=True, text=True)
    assert p.returncode == 2
    (tmp_path / "empty").mkdir()
    p = subprocess.run([sys.executable, script, "--runs", str(tmp_path / "empty"),
                        "--out", str(tmp_path / "demo")], capture_output=True, text=True)
    assert p.returncode == 2
    assert not (tmp_path / "demo" / "index.json").exists()


def test_max_one_prefers_repair(tmp_path):
    recs = [fixed("A3", "Login", 1, 89, "s"), rec("A2", "Login", 1, [step(0, True, False, [(89, "s")])])]
    assert [c["kind"] for c in picks_for(tmp_path, recs, max_picks=1)] == ["exploit_fixed"]
