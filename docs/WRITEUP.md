# Teach'O'tron: write-up

**In one line:** the same small NVIDIA Nemotron model, taught with three apps that survived real attacks in a sandbox, writes 2.7× more safe backends and gives 722 safe apps per $1, against 154 untaught and 372 for DeepSeek V4.1 Flash at about 6× the token price.

| Setup (12 held-out scenarios) | Secure | Safe apps per $1 | Median wait |
|---|---:|---:|---:|
| Nemotron Lightning, as is | 12.5% | 154 | 6.3 s |
| Nemotron + repair loop | 25.0% | 83 | 62.7 s |
| Nemotron + 3 sandbox-verified examples | 20.8% | 321 | 2.8 s |
| Nemotron + examples + repair | 33.3% | 178 | 31.2 s |
| **Teach'O'tron: examples + 4k answer cap** | **33.3%** | **722** | **2.5 s** |
| DeepSeek V4.1 Flash | 66.7% | 372 | 5.9 s |

The cap was chosen after the first runs: untaught, 78% of Nemotron's spend was answers that hit the 8,192-token limit with no code, and no working app used more than 1,800 tokens. The sections below are the full write-up of the baseline study.

## The problem

Models are now good at writing a web backend that runs. Running is not the same as safe. In the BaxBench paper (Vero et al., 2025, arXiv:2502.11844), the best model wrote correct code only 62% of the time, and on average about half of the correct programs from each model could be exploited by a known attack: SQL injection, path traversal, cross-site scripting, missing access checks. A demo that works is easy to ship and easy to exploit.

We asked a narrow question. Can a small, cheap open model write backends that both work and survive real attacks, if it gets told what failed and which attacks worked? And how does it compare on cost with a bigger model that does the same?

## What we built

A harness that gives a model a backend spec: an API to build in Python with Flask. BaxBench starts the app in Docker, runs its functional tests, then runs its expert-written exploits against it. An app counts only if every test passes and no exploit succeeds. We call that a secure pass.

We compare four setups on 12 held-out scenarios, plus two prompt-only baselines. Every model runs serverless on Fireworks. The Nemotron arms ran twice per scenario (n = 24), the DeepSeek arms once (n = 12).

| Arm | Model | Loop | Secure pass | Cost per secure app |
|---|---|---|---|---|
| A1 | DeepSeek V4.1 Flash | one-shot | 66.7% | $0.0027 |
| A6 | DeepSeek V4.1 Flash | repair loop | 75.0% | $0.0055 |
| A2 | Nemotron Lightning 3.5 30B A3B | one-shot | 12.5% | $0.0065 |
| A3 | Nemotron Lightning 3.5 30B A3B | repair loop | 25.0% | $0.0121 |
| B1 | DeepSeek V4.1 Flash | one-shot, security reminder | 58.3% | $0.0040 |
| B2 | Nemotron Lightning 3.5 30B A3B | one-shot, security reminder | 0.0% | n/a |

B1 and B2 use BaxBench's own "specific" safety prompt, which names the CWEs the scenario is tested for.

## The repair loop

When an app fails, the model gets back the names of the failing tests and the CWE number and name of each exploit that worked. It never sees the test or exploit code. It tries again, up to 3 times. Round 0 is the first try, so the loop makes at most 4 model calls. Every call counts toward cost and latency.

## Fine-tuning: three examples won

We also built a training set filtered by real exploits. DeepSeek wrote apps for training scenarios that never overlap the test set, and `scripts/check_split.py` checks that. We kept only the apps that passed every test and survived every exploit: 24 apps, written out as 120 examples with five system-prompt wordings each. Dataset uploads were disabled during the event; once Fireworks enabled them, we trained a LoRA adapter on Nemotron Nano 3 (3 epochs, rank 16, 8 minutes, $1.51) and ran it on the same 12 test scenarios, three times each.

| Arm | Model | Loop | Secure pass | Cost per secure app |
|---|---|---|---|---|
| A4 | Nemotron Nano 3 + LoRA | one-shot | 16.7% | $0.157 |
| A5 | Nemotron Nano 3 + LoRA | repair loop | 22.2% | $0.589 |
| C3 | Nemotron Lightning 3.5, 3 verified examples | one-shot | 33.3% | $0.0014 |

Showing three of the verified apps in the prompt beat training on all 24. The tuned model needs a dedicated GPU (Nano 3 has no serverless endpoint), so its cost is the B200 time actually billed, split across runs by tokens; on a busier deployment it would be lower, but not by 100×. Nano 3 is the tunable sibling of Lightning, which Fireworks cannot fine-tune, so A4 is not a strict before-and-after of A2.

## What we found

- **Cheaper per token is not cheaper per secure app.** Nemotron Lightning costs about 6× less per token than DeepSeek. With the repair loop, a secure app cost $0.0121: 4.5× DeepSeek one-shot ($0.0027) and 2.2× DeepSeek with repair ($0.0055), because so few of its apps survive. Even one-shot, Nemotron's $0.0065 per secure app is 2.4× DeepSeek's $0.0027.
- **The repair loop helps, mostly by fixing broken apps.** It moved Nemotron from 12.5% to 25.0% secure, at $0.30 per 100 tasks against $0.08 one-shot, and DeepSeek from 66.7% to 75.0%, at $0.41 against $0.18. Every app it turned secure had failed a functional test on the first try. In the two repair runs where an exploit worked on the first try, retries did not close it: Recipes kept CWE-20 (improper input validation), and SecretStorage dropped CWE-522 (weak credential storage) but then broke a test.
- **A security reminder in the prompt does not help.** Naming the CWEs up front lowered DeepSeek from 66.7% to 58.3% and Nemotron produced no secure app at all.
- **Nemotron's failures are mostly not attacks.** Most of its apps fail functional tests or never return code: it sometimes runs to the 8,192-token limit without writing a file. That also makes its repair runs slow, 63 s median against 7 s for DeepSeek.
- **The exploits that got through most often** in the four main arms were CWE-400 (resource exhaustion) and CWE-522 (weak credential storage), then CWE-20 (improper input validation).

## Limits

12 scenarios is a small sample: one app moves a DeepSeek rate by about 8 points and a Nemotron rate by about 4. A secure pass means no BaxBench exploit worked, not that the app is safe against every attack. Results cover Python with Flask only.
