from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_split  # noqa: E402

SPLIT = {"test": ["FakeLogin", "FakeUpload"], "dev": ["FakeNotes"], "train": ["FakeShop"]}


def sft_line(scenario, framework="Python-Flask"):
    return json.dumps({
        "messages": [{"role": "user", "content": "x"}, {"role": "assistant", "content": "y"}],
        "metadata": {"scenario": scenario, "framework": framework},
    })


@pytest.fixture
def files(tmp_path):
    split = tmp_path / "split.json"
    split.write_text(json.dumps(SPLIT))
    sft = tmp_path / "sft.jsonl"

    def write(lines):
        sft.write_text("\n".join(lines) + "\n")
        return ["--split", str(split), "--sft", str(sft)]

    return write


def test_clean_exits_0(files, capsys):
    assert check_split.main(files([sft_line("FakeShop"), sft_line("FakeNotes")])) == 0
    assert capsys.readouterr().out == ""


def test_overlap_exits_1_and_prints_each_line(files, capsys):
    args = files([sft_line("FakeShop"), sft_line("FakeLogin"), sft_line("FakeShop"), sft_line("FakeUpload", "JavaScript-express")])
    assert check_split.main(args) == 1
    out = capsys.readouterr().out.splitlines()
    assert len(out) == 2
    assert ":2:" in out[0] and "FakeLogin" in out[0]
    assert ":4:" in out[1] and "FakeUpload" in out[1]


def test_case_and_spaces_still_count_as_overlap(files):
    assert check_split.main(files([sft_line(" fakelogin ")])) == 1


def test_blank_lines_are_skipped(files):
    assert check_split.main(files([sft_line("FakeShop"), "", "   ", sft_line("FakeShop")])) == 0


def test_empty_sft_is_clean(files, tmp_path):
    args = files([])
    (tmp_path / "sft.jsonl").write_text("")
    assert check_split.main(args) == 0


@pytest.mark.parametrize("bad", [
    "{not json",
    json.dumps(["a list"]),
    json.dumps({"messages": []}),
    json.dumps({"messages": [], "metadata": "Login"}),
    json.dumps({"messages": [], "metadata": {"framework": "Python-Flask"}}),
    json.dumps({"messages": [], "metadata": {"scenario": 7}}),
])
def test_malformed_sft_line_exits_2(files, capsys, bad):
    assert check_split.main(files([sft_line("FakeShop"), bad])) == 2
    assert "line 2" in capsys.readouterr().err


@pytest.mark.parametrize("split", [
    "{not json",
    json.dumps(["FakeLogin"]),
    json.dumps({"dev": ["FakeLogin"]}),
    json.dumps({"test": "FakeLogin"}),
    json.dumps({"test": ["FakeLogin", 3]}),
])
def test_malformed_split_exits_2(tmp_path, split):
    (tmp_path / "split.json").write_text(split)
    (tmp_path / "sft.jsonl").write_text(sft_line("FakeShop") + "\n")
    assert check_split.main(["--split", str(tmp_path / "split.json"), "--sft", str(tmp_path / "sft.jsonl")]) == 2


def test_missing_files_exit_2(tmp_path):
    (tmp_path / "split.json").write_text(json.dumps(SPLIT))
    assert check_split.main(["--split", str(tmp_path / "split.json"), "--sft", str(tmp_path / "nope.jsonl")]) == 2
    assert check_split.main(["--split", str(tmp_path / "nope.json"), "--sft", str(tmp_path / "nope.jsonl")]) == 2


def test_non_utf8_sft_exits_2(files, tmp_path):
    args = files([])
    (tmp_path / "sft.jsonl").write_bytes(b"\xff\xfe\x00bad\n")
    assert check_split.main(args) == 2


def test_cli_exit_code(files):
    args = files([sft_line("FakeLogin")])
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_split.py")] + args, capture_output=True, text=True)
    assert r.returncode == 1
    assert "FakeLogin" in r.stdout
