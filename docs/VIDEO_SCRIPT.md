# Secure Backend: 2-minute video script

Six beats, about 280 spoken words. Numbers in `{{...}}` come from `results/results.json`, same names as `docs/WRITEUP.md`. Read at an easy pace; each beat has a few seconds of slack.

## 1. The problem (0:00 to 0:20)

**On screen:** title card, then the BaxBench paper abstract with the 62% line and the "about half exploitable" line highlighted.

> Models can write a web backend that runs. But running is not the same as safe. The BaxBench benchmark found that even the best model wrote correct code only 62% of the time. And about half of the correct apps could be broken by a known attack. SQL injection. Path traversal. Missing access checks.

## 2. What we built (0:20 to 0:45)

**On screen:** a simple diagram: spec, model on Fireworks, app in Docker, tests and exploits, feedback arrow back to the model.

> We built a harness around BaxBench. A model gets an API spec and writes a Flask app. BaxBench runs it in Docker, runs the functional tests, then runs real exploits against it. An app only counts if every test passes and no exploit works. When an app fails, our repair loop tells the model which tests failed and which kinds of attack got through. Never the exploit code. It gets up to 3 more tries.

## 3. The leaderboard (0:45 to 1:05)

**On screen:** the dashboard leaderboard with the four arms. Point at each row as it is named.

> We ran four setups on 12 held-out scenarios, all serverless on Fireworks. DeepSeek V4.1 Flash, and NVIDIA's small Nemotron Lightning 3.5, each one-shot and with repair. One-shot, Nemotron got {{A2_SECURE}} secure. With repair, {{A3_SECURE}}. DeepSeek went from {{A1_SECURE}} to {{A6_SECURE}}.

## 4. One exploit, fixed (1:05 to 1:30)

**On screen:** the run viewer on one demo run from `ui/demo/index.json`. Round 0 with the exploit marked, the feedback the model got, then the passing round.

> Here is one run. On the first try, the {{DEMO_SCENARIO}} app was open to {{DEMO_CWE}}. The model got back one line: which attack worked. On round {{DEMO_ROUND}}, it fixed the code. Every test passed, and no exploit worked.

## 5. Cost per secure app (1:30 to 1:45)

**On screen:** the cost columns: cost per 100 tasks and cost per secure app, for each arm.

> Repair costs extra calls, so we count every one. A secure app cost {{A3_COST_SECURE}} with Nemotron and repair, and {{A6_COST_SECURE}} with DeepSeek and repair.

## 6. What is next (1:45 to 2:00)

**On screen:** the fine-tuning slide: 24 exploit-verified examples, split-checked, upload blocked. Then the repo link.

> We also built a training set of 24 apps that survived every exploit. Fine-tuning was blocked on the platform today. Next, we train on that set, add more scenarios and more runs, and try other frameworks. The code is open. Thanks for watching.

<!-- If repair did not help in the final numbers, change beats 3 and 5 to say what happened. Keep the 62% and "about half" lines tied to the paper. -->
