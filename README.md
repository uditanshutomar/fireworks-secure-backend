# Secure Backend

Can a small, cheap open model write web backends that both work and survive real attacks, if it gets told which attacks worked?

We give a model a backend spec (an API to build in Python with Flask). [BaxBench](https://github.com/logic-star-ai/baxbench) then runs its functional tests and its expert-written exploits against the app in Docker. An app only counts if it passes every test and no exploit succeeds.

We compare four setups on 12 held-out scenarios:

| Arm | Model | Loop |
|---|---|---|
| A1 | DeepSeek V4.1 Flash 1017 | one-shot |
| A6 | DeepSeek V4.1 Flash 1017 | repair loop |
| A2 | NVIDIA Nemotron Lightning 3.5 30B A3B | one-shot |
| A3 | NVIDIA Nemotron Lightning 3.5 30B A3B | repair loop |

**Repair loop.** When an app fails, the model gets back the failing test names and the CWE of each exploit that worked, and tries again, up to 3 times. It never sees exploit or test source code.

**Fine-tuning (attempted).** We built an exploit-filtered training set: DeepSeek wrote apps for 16 training scenarios that never overlap the test set, and we kept only the 24 that passed every test and survived every exploit (`scripts/export_sft.py`, checked by `scripts/check_split.py`). Nemotron Nano 3 30B is LoRA-tunable on Fireworks, but dataset uploads were disabled on our account during the event, so the tuned arms did not run.

**Metrics.** Secure-pass rate, functional pass rate, cost per 100 tasks, cost per secure app, median latency.

## Results

Filled in from `results/results.json` at the end of the build.

## Why this matters for health apps

Clinics and health startups are starting to ship backends written by AI. Several of our held-out scenarios are the same shapes those backends take, and BaxBench attacks them with the exploits that expose patient data:

| Test scenario | Health-app equivalent | Exploits BaxBench runs |
|---|---|---|
| SecretStorage | Per-patient record storage | one user reading another user's data (CWE-284), SQL injection (CWE-89), weak password storage (CWE-522) |
| Login | Patient or clinician portal | SQL injection (CWE-89), weak password storage (CWE-522) |
| UserCreation | Invite-only staff or patient sign-up | signing up without an invite, guessable invite IDs (CWE-284) |
| FileSearch, ZipToTxt | Lab result and document uploads | path traversal outside your own files (CWE-22), zip bombs (CWE-400) |
| Monitor | Internal ops tools | OS command injection (CWE-78) |

This measures exploitability, not regulatory compliance: an app that survives these exploits is not certified for anything, but an app that fails them would leak records. A dedicated patient-records scenario with its own access-control exploits is the obvious next one to add.

## Layout

| Path | What |
|---|---|
| `src/secure_backend/` | harness, repair loop, Fireworks client |
| `scripts/` | data export, split check, results table |
| `results/` | `results.json` and per-run records |
| `ui/` | dashboard |
| `docs/CONTRACTS.md` | data shapes everyone builds against |

## Run it

Needs Docker and a Fireworks API key in `.env` (`FIREWORKS_API_KEY=...`, never committed).

```bash
git clone --depth 1 https://github.com/logic-star-ai/baxbench vendor/baxbench
uv venv --python 3.12 .venv-bax
VIRTUAL_ENV=.venv-bax uv pip install requests docker httpx openai anthropic tabulate simple-parsing tqdm termcolor pdfplumber imageio matplotlib pyyaml pytest
# private/split.json holds the locked test list ({"test": [...], "train": [...], "framework_test": ["Python-Flask"], "frameworks_train": [...]})
.venv-bax/bin/python scripts/run_arm.py --arm A1 --set test --runs 1 --jobs 2
.venv-bax/bin/python scripts/results_table.py --runs results/runs --out results/results.json
```

Keep `--jobs` low on a 16 GB laptop: some BaxBench resource-exhaustion exploits build multi-GB payloads in the test process.

## Built with

- [Fireworks AI](https://fireworks.ai): serverless inference for every arm
- [NVIDIA Nemotron](https://research.nvidia.com/labs/nemotron/): Nemotron Lightning 3.5, the small model under test
- [BaxBench](https://github.com/logic-star-ai/baxbench): scenarios, functional tests and exploits (third-party, MIT)

## Pre-existing code

BaxBench is a third-party open-source benchmark (MIT), cloned into the gitignored `vendor/` folder and used as published. Our harness works around two environment issues without changing its tests or exploits: Debian bullseye's security mirror no longer serves `sqlite3`, and host Docker credential helpers broke unattended builds. Everything in this repository was written during the event on November 2, 2026.

## Team

- Sukriti Sehgal (lead)
- Uditanshu Tomar

## License

MIT
