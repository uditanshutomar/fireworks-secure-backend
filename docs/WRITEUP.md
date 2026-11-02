# Secure Backend: write-up draft

Numbers in `{{...}}` are filled in from `results/results.json` at the end of the build.

## The problem

Models are now good at writing a web backend that runs. Running is not the same as safe. In the BaxBench paper (Vero et al., 2025, arXiv:2502.11844), the best model wrote correct code only 62% of the time, and on average about half of the correct programs from each model could be exploited by a known attack: SQL injection, path traversal, cross-site scripting, missing access checks. A demo that works is easy to ship and easy to exploit.

We asked a narrow question. Can a small open model, fine-tuned on Fireworks, write backends that both work and survive real attacks? And is it cheaper than a bigger model that does the same?

## What we built

A harness that gives a model a backend spec: an API to build in Python with Flask. BaxBench starts the app in Docker, runs its functional tests, then runs its expert-written exploits against it. An app counts only if every test passes and no exploit succeeds. We call that a secure pass.

We compare five setups on 12 held-out scenarios, 3 runs each:

| Arm | Model | Loop | Secure pass | Cost per secure app |
|---|---|---|---|---|
| A1 | DeepSeek V4.1 Flash (reference) | one-shot | {{A1_SECURE}} | {{A1_COST_SECURE}} |
| A2 | Nemotron Nano 3 30B A3B, base | one-shot | {{A2_SECURE}} | {{A2_COST_SECURE}} |
| A3 | Nemotron Nano 3, base | repair loop | {{A3_SECURE}} | {{A3_COST_SECURE}} |
| A4 | Nemotron Nano 3, fine-tuned | one-shot | {{A4_SECURE}} | {{A4_COST_SECURE}} |
| A5 | Nemotron Nano 3, fine-tuned | repair loop | {{A5_SECURE}} | {{A5_COST_SECURE}} |

## Training data filtered by real exploits

DeepSeek wrote candidate apps for training scenarios. None of them overlap the test set, and a script checks that before training.
<!-- Keep the sentence above only if scripts/check_split.py exits 0 on the final data/sft.jsonl before the SFT job starts. Otherwise say the split was checked by hand, or drop it. --> We ran every candidate through the same tests and exploits. We kept only the apps that passed every test and survived every exploit. That left {{SFT_KEPT}} of {{SFT_TOTAL}} candidates. We trained a LoRA adapter on Nemotron Nano 3 with Fireworks supervised fine-tuning on those apps alone.

So the filter is not a style guide or a second model's opinion. It is the attack itself.

## The repair loop

When an app fails, the model gets back the names of the failing tests and the CWE number and name of each exploit that worked. It never sees the test or exploit code. It tries again, up to 3 times. Round 0 is the first try, so the loop makes at most 4 model calls. Every call counts toward cost and latency.

## What we found

- Fine-tuning moved the small model's secure pass rate from {{A2_SECURE}} to {{A4_SECURE}}.
- The repair loop moved it from {{A4_SECURE}} to {{A5_SECURE}}, at {{A5_COST_100}} per 100 tasks against {{A4_COST_100}} one-shot.
- The reference model reached {{A1_SECURE}} at {{A1_COST_100}} per 100 tasks.
- The CWEs that still got through most often: {{TOP_CWES}}.

## Limits

12 scenarios and 3 runs per arm is a small sample. A secure pass means no BaxBench exploit worked, not that the app is safe against every attack. Results cover Python with Flask only.
