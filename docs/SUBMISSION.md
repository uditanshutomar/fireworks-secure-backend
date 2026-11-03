# Teach'O'tron: submission form answers

## Project name

Teach'O'tron

## Tagline (one line)

Same small model, taught by a sandbox: 2.7× more hack-proof backends and more safe code per dollar than a model 6× its price.

## Links

- Repo: https://github.com/uditanshutomar/fireworks-secure-backend
- Live dashboard: https://uditanshutomar.github.io/fireworks-secure-backend/ui/

## The problem

AI writes web backends in seconds, but nobody checks whether they can be hacked. In the BaxBench benchmark, even the best model wrote correct code only 62% of the time, and about half of the correct apps fell to a known attack. Small, cheap models are worse, so teams pay for big ones.

## What we built

Teach'O'tron puts every app a model writes into a sealed Docker sandbox and attacks it with BaxBench's real exploits (SQL injection, password theft, path traversal, zip bombs) plus its functional tests. An app counts as safe only if every test passes and no attack works.

Then the sandbox becomes a teacher. We keep only the big model's apps that survived every attack, and show three of them to the small model, NVIDIA Nemotron Lightning, in its prompt. No fine-tuning. We also cap its answers at 4,096 tokens, because untaught, 78% of its spend went on answers that never produced code.

## Results (12 held-out scenarios, real exploits, Fireworks list prices)

| Setup | Safe apps | Safe apps per $1 | Wait per app |
|---|---:|---:|---:|
| Nemotron Lightning, as is | 12.5% | 154 | 6.3 s |
| Teach'O'tron (same Nemotron) | 33.3% | 722 | 2.5 s |
| DeepSeek V4.1 Flash (about 6× the token price) | 66.7% | 372 | 5.9 s |

Same model: 2.7× the safe apps, 4.7× the safe apps per dollar. Against the bigger model: 1.9× the safe apps per dollar at less than half the wait. DeepSeek still wins per try, so Teach'O'tron is for generating many apps and shipping only what the sandbox passes.

## What we learned

- Teaching beats retrying. A retry loop that tells the model what failed was the worst deal we measured (83 safe apps per $1). Every app it rescued had a broken feature, not an open hole.
- Telling a model to be careful does not help. Naming the vulnerabilities up front lowered DeepSeek's safe rate and Nemotron's to zero.
- The examples work because they show what a finished answer looks like: runaway answers with no code fell from 9 in 24 runs to 0.

## How we built it

Python harness around BaxBench (third-party, MIT) running in Docker on one laptop, with a memory watchdog for exploits that build multi-GB payloads. All models ran serverless on Fireworks. Training and test scenarios never overlap, checked by script. Every run is a JSON record in the repo, and every number on the dashboard is generated from them.

## Challenges

Fireworks dataset uploads were disabled on both our accounts, so the planned LoRA fine-tune of Nemotron Nano 3 could not run. We had already built the training set (24 apps that survived every attack), so we taught in the prompt instead. Debian's security mirror had dropped a package BaxBench needs; we pinned a working version without changing any test or exploit.

## What's next

Fine-tune on the verified set once uploads open, add more scenarios and frameworks, and teach the loop to close security holes, not just fix bugs. We also want an uncensored open model as the attacker, writing new exploits where frontier models refuse.

## Honest limits

12 scenarios is a small sample (one app moves a Nemotron rate by about 4 points). We chose the 4,096-token cap after the first runs; no working app used more than 1,800 tokens, so it only cut answers that had no code. Safe means no BaxBench exploit worked, not that an app is safe against every attack.

## Built with

Fireworks AI (serverless inference), NVIDIA Nemotron Lightning 3.5, DeepSeek V4.1 Flash, BaxBench, Docker, Python.

## Team

Sukriti Sehgal (lead), Uditanshu Tomar
