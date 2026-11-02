"""Builds BaxBench prompts and runs its functional tests and exploits on generated code.

Runs only on P1 (needs Docker and the BaxBench checkout in vendor/baxbench, Python 3.12).
"""
from __future__ import annotations

import logging
import multiprocessing
import os
import pathlib
import sys
import tempfile
import uuid

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

# A clean Docker client config: the user's own config has registry credential helpers
# (gcloud) that break unattended builds. Public base images need no credentials.
_DOCKER_CONFIG = REPO_ROOT / "vendor" / "docker-config"
_DOCKER_CONFIG.mkdir(parents=True, exist_ok=True)
(_DOCKER_CONFIG / "config.json").write_text("{}\n")
os.environ["DOCKER_CONFIG"] = str(_DOCKER_CONFIG)
_desktop_sock = pathlib.Path.home() / ".docker" / "run" / "docker.sock"
if "DOCKER_HOST" not in os.environ and _desktop_sock.exists():
    os.environ["DOCKER_HOST"] = f"unix://{_desktop_sock}"
sys.path.insert(0, str(REPO_ROOT / "vendor" / "baxbench" / "src"))

import cwes as bax_cwe  # noqa: E402
import env as bax_env  # noqa: E402
import scenarios as bax_scenarios  # noqa: E402
from prompts import _SYSTEM_PROMPT, Parser  # noqa: E402
from scenarios.base import AppInstance  # noqa: E402
from tasks import ContainerRunner, SlotManager, run_test_with_timeout  # noqa: E402

# BaxBench's stock commands (apt-get install sqlite3) fail on Debian bullseye now: the security
# mirror's index points at a pool file that is gone. Main's sqlite3 needs the matching library pin.
DOCKER_RUN_COMMANDS = [
    "sed -i '/bullseye-security/d' /etc/apt/sources.list",
    "apt-get update",
    "apt-get install -y --allow-downgrades libsqlite3-0=3.34.1-3 sqlite3",
]

ENVS = {e.id: e for e in bax_env.all_envs}
SCENARIOS = {s.id: s for s in bax_scenarios.all_scenarios}

_manager = None

# Some BaxBench resource-exhaustion exploits build multi-GB payloads inside the test worker
# process; on a 16 GB laptop several at once pushed the Mac into heavy swap and crashed Docker.
# A worker over the cap is killed. The test then errors, which BaxBench itself scores the same
# way as a timed-out test (no CWE recorded).
WORKER_RSS_CAP = int(os.environ.get("BAX_WORKER_RSS_CAP_GB", "3")) * 1024 ** 3
_watchdog_started = False


def _start_memory_watchdog() -> None:
    global _watchdog_started
    if _watchdog_started:
        return
    _watchdog_started = True
    import threading

    import psutil

    me = psutil.Process()

    def watch() -> None:
        while True:
            try:
                for child in me.children(recursive=True):
                    try:
                        if child.memory_info().rss > WORKER_RSS_CAP:
                            logging.getLogger("bax-watchdog").warning(
                                "killing test worker %d at %.1f GB", child.pid, child.memory_info().rss / 1024 ** 3)
                            child.kill()
                    except psutil.Error:
                        pass
            except psutil.Error:
                pass
            threading.Event().wait(0.5)

    threading.Thread(target=watch, daemon=True, name="bax-memory-watchdog").start()
_ports = None


def _port_manager(num_slots: int = 64, min_port: int = 12345) -> SlotManager:
    global _manager, _ports
    if _ports is None:
        _start_memory_watchdog()
        _manager = multiprocessing.Manager()
        _ports = SlotManager(_manager, num_slots, min_port)
    return _ports


def build_messages(scenario_id: str, framework: str, safety_prompt: str = "none") -> list:
    """safety_prompt is BaxBench's own: none, generic, or specific (names the scenario's CWEs)."""
    prompt = SCENARIOS[scenario_id].build_prompt(ENVS[framework], "openapi", safety_prompt, agent=False)
    return [{"role": "system", "content": _SYSTEM_PROMPT}, {"role": "user", "content": prompt}]


def extract_files(framework: str, text: str, logger: logging.Logger | None = None) -> dict:
    """Uses BaxBench's own parser. Returns {} when the response has no usable code."""
    files = Parser(ENVS[framework], logger or logging.getLogger("parser")).parse_response(text)
    if pathlib.Path("failed") in files:
        return {}
    return files


def _cwe_num(c) -> int:
    return int(c.value["num"])


def run_tests(scenario_id: str, framework: str, files: dict, timeout: int = 120) -> dict:
    """Contract-shaped result: functional_pass, secure_pass, failed_tests, exploits_triggered."""
    scenario = SCENARIOS[scenario_id]
    env = ENVS[framework]
    ports = _port_manager()
    work = pathlib.Path(tempfile.mkdtemp(prefix="bax-"))
    logger = logging.getLogger(f"bax-{uuid.uuid4().hex[:8]}")
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(work / "test.log")
    logger.addHandler(handler)
    failed_tests: list = []
    exploits: list = []
    try:
        if not files:
            return {"functional_pass": False, "secure_pass": False,
                    "failed_tests": ["no_code_extracted"], "exploits_triggered": [], "log": str(work)}
        packages = (DOCKER_RUN_COMMANDS + scenario.needed_packages.get("_all_", [])
                    + scenario.needed_packages.get(env.language, []))
        try:
            image_id = env.build_docker_image(
                {pathlib.Path(k): v for k, v in files.items()}, packages, logger, no_cache=False)
        except Exception as e:  # noqa: BLE001
            logger.exception("build failed: %s", e)
            return {"functional_pass": False, "secure_pass": False,
                    "failed_tests": ["docker_build_failed"], "exploits_triggered": [], "log": str(work)}

        crash = bax_cwe.CWE.IMPROPER_CHECK_OR_HANDLING_OF_EXCEPTIONAL_CONDITIONS
        for ft in scenario.functional_tests:
            passed = False
            try:
                with ContainerRunner(env, ports, image_id, logger) as cr:
                    ran_before = env.process_still_running(cr.container.id, logger)
                    passed = bool(run_test_with_timeout(ft, AppInstance(
                        port=cr.port, log_file_path=work / f"{ft.__name__}.log",
                        container_id=cr.container.id, env=env), timeout))
                    if ran_before and not env.process_still_running(cr.container.id, logger):
                        exploits.append({"cwe": _cwe_num(crash), "name": f"{ft.__name__}:server_crash"})
            except Exception as e:  # noqa: BLE001
                logger.exception("functional test error: %s", e)
            if not passed:
                failed_tests.append(ft.__name__)

        for st in scenario.security_tests:
            found = set()
            try:
                with ContainerRunner(env, ports, image_id, logger) as cr:
                    ran_before = env.process_still_running(cr.container.id, logger)
                    found = run_test_with_timeout(st, AppInstance(
                        port=cr.port, log_file_path=work / f"{st.__name__}.log",
                        container_id=cr.container.id, env=env), timeout) or set()
                    if ran_before and not env.process_still_running(cr.container.id, logger):
                        if bax_cwe.CWE.UNCONTROLLED_RESOURCE_CONSUMPTION not in found:
                            found = set(found) | {crash}
            except Exception as e:  # noqa: BLE001
                logger.exception("security test error: %s", e)
            for c in found:
                exploits.append({"cwe": _cwe_num(c), "name": st.__name__})

        functional = not failed_tests
        return {"functional_pass": functional, "secure_pass": functional and not exploits,
                "failed_tests": failed_tests, "exploits_triggered": exploits, "log": str(work)}
    finally:
        handler.close()
        logger.removeHandler(handler)
