# Secure Backend

Can a small open model, fine-tuned on Fireworks, write web backends that both work and survive real attacks?

We give a model a backend spec (an API to build in Python with Flask or FastAPI). [BaxBench](https://github.com/logic-star-ai/baxbench) then runs its functional tests and its expert-written exploits against the app in Docker. An app only counts if it passes every test and no exploit succeeds.

We compare five setups on 12 held-out scenarios, 3 runs each:

| Arm | Model | Loop |
|---|---|---|
| A1 | DeepSeek V4.1 Flash 1017 | one-shot |
| A2 | NVIDIA Nemotron Nano 3 30B A3B, base | one-shot |
| A3 | NVIDIA Nemotron Nano 3 30B A3B, base | repair loop |
| A4 | Nemotron Nano 3, fine-tuned on Fireworks | one-shot |
| A5 | Nemotron Nano 3, fine-tuned on Fireworks | repair loop |

**Fine-tuning data.** DeepSeek writes candidate apps for training scenarios that never overlap the test set. We keep only the apps that pass the tests and survive the exploits, and train a LoRA adapter on Nemotron Nano 3 with Fireworks supervised fine-tuning.

**Repair loop.** When an app fails, the model gets back the failing test names and the CWE of each exploit that worked, and tries again, up to 3 times.

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

- [Fireworks AI](https://fireworks.ai): inference for every arm, LoRA supervised fine-tuning, deployment of the tuned model
- [NVIDIA Nemotron](https://research.nvidia.com/labs/nemotron/): the base model we tune
- [BaxBench](https://github.com/logic-star-ai/baxbench) and [AutoBaxBuilder](https://arxiv.org/abs/2512.21132): scenarios, tests and exploits (third-party, used unchanged)

## Pre-existing code

BaxBench and AutoBaxBuilder are third-party open-source benchmarks, used as published. Everything in this repository was written during the event on November 2, 2026.

## Team

- Sukriti Sehgal (lead)
- Uditanshu Tomar

## License

MIT
