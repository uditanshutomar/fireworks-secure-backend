from __future__ import annotations

import pytest

from secure_backend.repair_loop import build_repair_prompt, extract_code, repair_loop

EXPLOIT_SOURCE = "requests.post(url, json={'username': \"' OR 1=1 --\"})"
TEST_SOURCE = "def test_login_ok(app): assert app.post('/login').status_code == 200"


class FakeClient:
    """Returns canned replies and records every message list it was sent."""

    def __init__(self, texts, tokens_in=100, tokens_out=50, latency_s=1.5):
        self.texts = list(texts)
        self.calls = []
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.latency_s = latency_s

    def generate(self, messages):
        self.calls.append([dict(m) for m in messages])
        n = len(self.calls)
        return {
            "text": self.texts[n - 1],
            "tokens_in": self.tokens_in * n,
            "tokens_out": self.tokens_out,
            "latency_s": self.latency_s,
        }


def fenced(body, lang="python"):
    return "Here is the app:\n```{}\n{}\n```\nDone.".format(lang, body)


SECURE = {"functional_pass": True, "secure_pass": True, "failed_tests": [], "exploits_triggered": []}
SQLI = {
    "functional_pass": True,
    "secure_pass": False,
    "failed_tests": [],
    "exploits_triggered": [{"cwe": 89, "name": "sql_injection_login"}],
}
BROKEN = {
    "functional_pass": False,
    "secure_pass": False,
    "failed_tests": ["test_login_ok", "test_register"],
    "exploits_triggered": [{"cwe": 79, "name": "xss_profile"}, {"cwe": 89, "name": "sqli_search"}],
}


def scripted(results):
    seen = []

    def run_tests(code):
        seen.append(code)
        return dict(results[len(seen) - 1])

    run_tests.seen = seen
    return run_tests


def test_secure_on_round_0_has_one_step():
    client = FakeClient([fenced("app = 1")])
    out = repair_loop(client, "Build a login API.", scripted([SECURE]))
    assert out["rounds"] == 1
    assert len(out["steps"]) == 1
    assert out["steps"][0]["round"] == 0
    assert out["secure_pass"] and out["functional_pass"]
    assert out["cwes"] == []
    assert len(client.calls) == 1


def test_fixed_on_round_2():
    client = FakeClient([fenced("v0"), fenced("v1"), fenced("v2"), fenced("v3")])
    run = scripted([BROKEN, SQLI, SECURE])
    out = repair_loop(client, "spec", run, max_rounds=3)
    assert [s["round"] for s in out["steps"]] == [0, 1, 2]
    assert out["rounds"] == 3
    assert out["secure_pass"] is True
    assert out["cwes"] == []
    assert run.seen == ["v0\n", "v1\n", "v2\n"]
    assert out["steps"][0]["failed_tests"] == ["test_login_ok", "test_register"]
    assert out["steps"][1]["exploits_triggered"] == [{"cwe": 89, "name": "sql_injection_login"}]


def test_never_fixed_runs_max_rounds_plus_one_steps():
    client = FakeClient([fenced("v{}".format(i)) for i in range(3)])
    out = repair_loop(client, "spec", scripted([BROKEN] * 3), max_rounds=2)
    assert len(out["steps"]) == 3
    assert out["rounds"] == 3
    assert out["secure_pass"] is False
    assert out["functional_pass"] is False
    assert out["cwes"] == [79, 89]
    assert len(client.calls) == 3


def test_max_rounds_0_is_one_shot():
    client = FakeClient([fenced("v0")])
    out = repair_loop(client, "spec", scripted([SQLI]), max_rounds=0)
    assert len(out["steps"]) == 1
    assert out["secure_pass"] is False
    assert out["cwes"] == [89]
    assert len(client.calls) == 1


def test_negative_max_rounds_is_rejected():
    with pytest.raises(ValueError):
        repair_loop(FakeClient([]), "spec", scripted([]), max_rounds=-1)


def test_extract_code_with_fence():
    text = "Intro\n```python\nprint(1)\n```\nmore\n```\nprint(2)\n```"
    assert extract_code(text) == "print(1)\n"


def test_extract_code_with_bare_fence():
    assert extract_code("```\nx = 1\n```") == "x = 1\n"


def test_extract_code_without_fence_returns_whole_text():
    text = "from flask import Flask\napp = Flask(__name__)\n"
    assert extract_code(text) == text


def test_extract_code_unclosed_fence_takes_rest():
    assert extract_code("```python\nx = 1\n") == "x = 1\n"


def test_loop_uses_extracted_code():
    client = FakeClient(["no fence here"])
    run = scripted([SECURE])
    out = repair_loop(client, "spec", run)
    assert run.seen == ["no fence here"]
    assert out["steps"][0]["code"] == "no fence here"


def test_tokens_and_latency_are_summed():
    client = FakeClient([fenced("a"), fenced("b"), fenced("c")], tokens_in=100, tokens_out=40, latency_s=1.1)
    out = repair_loop(client, "spec", scripted([SQLI, SQLI, SECURE]))
    assert out["tokens_in"] == 100 + 200 + 300
    assert out["tokens_out"] == 120
    assert out["latency_s"] == pytest.approx(3.3)
    assert out["tokens_in"] == sum(s["tokens_in"] for s in out["steps"])


def test_repair_prompt_names_tests_and_cwes_but_no_source():
    result = dict(BROKEN)
    # Extra keys a harness might carry must not leak into the prompt.
    result["exploit_source"] = EXPLOIT_SOURCE
    result["test_source"] = TEST_SOURCE
    prompt = build_repair_prompt(result)
    for name in ("test_login_ok", "test_register", "xss_profile", "sqli_search"):
        assert name in prompt
    assert "CWE-79" in prompt and "CWE-89" in prompt
    assert EXPLOIT_SOURCE not in prompt
    assert TEST_SOURCE not in prompt
    assert "OR 1=1" not in prompt


def test_loop_sends_repair_prompt_without_exploit_source():
    leaky = dict(SQLI, exploit_source=EXPLOIT_SOURCE, test_source=TEST_SOURCE)
    client = FakeClient([fenced("v0"), fenced("v1")])
    repair_loop(client, "Build a login API.", scripted([leaky, SECURE]))
    second = client.calls[1]
    assert [m["role"] for m in second] == ["system", "user", "assistant", "user"]
    assert second[1]["content"] == "Build a login API."
    repair = second[-1]["content"]
    assert "CWE-89" in repair and "sql_injection_login" in repair
    assert EXPLOIT_SOURCE not in repair and TEST_SOURCE not in repair
    assert "exploit_source" not in str(client.calls)


def test_framework_reaches_system_prompt():
    client = FakeClient([fenced("v0")])
    repair_loop(client, "spec", scripted([SECURE]), framework="Python-FastAPI")
    assert "Python-FastAPI" in client.calls[0][0]["content"]


def test_steps_match_run_record_shape():
    client = FakeClient([fenced("v0"), fenced("v1")])
    out = repair_loop(client, "spec", scripted([SQLI, SECURE]))
    keys = {"round", "code", "functional_pass", "secure_pass", "failed_tests",
            "exploits_triggered", "tokens_in", "tokens_out", "latency_s"}
    for s in out["steps"]:
        assert set(s) == keys
    assert set(out) == {"rounds", "functional_pass", "secure_pass", "cwes",
                        "tokens_in", "tokens_out", "latency_s", "steps"}
