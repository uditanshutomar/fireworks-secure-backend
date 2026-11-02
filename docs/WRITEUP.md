# Secure Backend: write-up draft

Numbers in `{{...}}` are filled in from `results/results.json` at the end of the build.

## The problem

Models are now good at writing a web backend that runs. Running is not the same as safe. In the BaxBench paper (Vero et al., 2025, arXiv:2502.11844), the best model wrote correct code only 62% of the time, and on average about half of the correct programs from each model could be exploited by a known attack: SQL injection, path traversal, cross-site scripting, missing access checks. A demo that works is easy to ship and easy to exploit.

We asked a narrow question. Can a small, cheap open model write backends that both work and survive real attacks, if it gets told which attacks worked? And how does it compare on cost with a bigger model that does the same?

## What we built

A harness that gives a model a backend spec: an API to build in Python with Flask. BaxBench starts the app in Docker, runs its functional tests, then runs its expert-written exploits against it. An app counts only if every test passes and no exploit succeeds. We call that a secure pass.

We compare four setups on 12 held-out scenarios, 1 run each. Every model runs serverless on Fireworks.

| Arm | Model | Loop | Secure pass | Cost per secure app |
|---|---|---|---|---|
| A1 | DeepSeek V4.1 Flash | one-shot | {{A1_SECURE}} | {{A1_COST_SECURE}} |
| A6 | DeepSeek V4.1 Flash | repair loop | {{A6_SECURE}} | {{A6_COST_SECURE}} |
| A2 | Nemotron Lightning 3.5 30B A3B | one-shot | {{A2_SECURE}} | {{A2_COST_SECURE}} |
| A3 | Nemotron Lightning 3.5 30B A3B | repair loop | {{A3_SECURE}} | {{A3_COST_SECURE}} |

## The repair loop

When an app fails, the model gets back the names of the failing tests and the CWE number and name of each exploit that worked. It never sees the test or exploit code. It tries again, up to 3 times. Round 0 is the first try, so the loop makes at most 4 model calls. Every call counts toward cost and latency.

## Fine-tuning: attempted, blocked

We also built a training set filtered by real exploits. DeepSeek wrote apps for training scenarios that never overlap the test set, and `scripts/check_split.py` checks that. We kept only the apps that passed every test and survived every exploit: 24 examples. The plan was a LoRA adapter on Nemotron Nano 3 with Fireworks fine-tuning. Dataset uploads were disabled on our account during the event, so the tuned arms did not run.

## What we found

- The repair loop moved Nemotron Lightning from {{A2_SECURE}} to {{A3_SECURE}} secure pass, at {{A3_COST_100}} per 100 tasks against {{A2_COST_100}} one-shot.
- It moved DeepSeek from {{A1_SECURE}} to {{A6_SECURE}}, at {{A6_COST_100}} per 100 tasks against {{A1_COST_100}} one-shot.
- Cost per secure app: {{A3_COST_SECURE}} for Nemotron with repair, {{A6_COST_SECURE}} for DeepSeek with repair.
- The CWEs that still got through most often: {{TOP_CWES}}.

<!-- The bullets above assume repair helps. If a number says otherwise, say so plainly. -->

## Limits

12 scenarios and 1 run per arm is a small sample, so one app more or less moves a rate by about 8 points. A secure pass means no BaxBench exploit worked, not that the app is safe against every attack. Results cover Python with Flask only.
