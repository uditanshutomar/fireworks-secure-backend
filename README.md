# Secure Backend

Can a small open model, fine-tuned on Fireworks, write web backends that both work and survive real attacks?

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

Steps are added as the harness lands.

## Built with

- [Fireworks AI](https://fireworks.ai): serverless inference for every arm
- [NVIDIA Nemotron](https://research.nvidia.com/labs/nemotron/): Nemotron Lightning 3.5, the small model under test
- [BaxBench](https://github.com/logic-star-ai/baxbench) and [AutoBaxBuilder](https://arxiv.org/abs/2512.21132): scenarios, tests and exploits (third-party, used unchanged)

## Pre-existing code

BaxBench and AutoBaxBuilder are third-party open-source benchmarks, used as published. Everything in this repository was written during the event on November 2, 2026.

## Team

- Sukriti Sehgal (lead)
- Uditanshu Tomar

## License

MIT
