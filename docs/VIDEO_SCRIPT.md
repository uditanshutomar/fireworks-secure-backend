# Secure Backend: 2-minute video script

Six beats, about 290 spoken words. Every number is from `results/results.json`. Read at an easy pace; each beat has a few seconds of slack.

## 1. The problem (0:00 to 0:20)

**On screen:** title card, then the BaxBench paper abstract with the 62% line and the "about half exploitable" line highlighted.

> Models can write a web backend that runs. But running is not the same as safe. The BaxBench benchmark found that even the best model wrote correct code only 62% of the time. And about half of the correct apps could be broken by a known attack. SQL injection. Path traversal. Missing access checks. For a clinic's patient portal, that is a records leak.

## 2. What we built (0:20 to 0:45)

**On screen:** a simple diagram: spec, model on Fireworks, app in Docker, tests and exploits, feedback arrow back to the model.

> We built a harness around BaxBench. A model gets an API spec and writes a Flask app. BaxBench runs it in Docker, runs the functional tests, then runs real exploits against it. An app only counts if every test passes and no exploit works. When an app fails, our repair loop tells the model which tests failed and which kinds of attack got through. Never the exploit code. It gets up to 3 more tries.

## 3. The results (0:45 to 1:10)

**On screen:** the dashboard headline tiles, then the "Where 100 apps end up" panel.

> We ran 12 held-out scenarios, all serverless on Fireworks. NVIDIA's small Nemotron Lightning, one try: 13 safe apps out of 100. With the repair loop: 25. DeepSeek V4.1 Flash, one try: 67. With repair: 75. And telling the model up front which attacks to avoid made things worse: DeepSeek dropped to 58, Nemotron to zero.

## 4. One app, fixed (1:10 to 1:30)

**On screen:** the dashboard's "One app, first try vs retry" panel on Small + retries, Login. Or `scripts/replay_run.py` on the same run.

> Here is one run. Nemotron's first login service failed a functional test. The model got back one line: the name of the test that failed. On the next try every test passed, and no exploit worked. That is the honest pattern in our data: retries rescue broken apps. When an exploit got through, retries did not close it yet.

## 5. Cost per safe app (1:30 to 1:45)

**On screen:** the cost tile and the "All setups" table.

> Nemotron is about six times cheaper per token. But a safe app cost 1.2 cents with Nemotron and retries, 4.5 times DeepSeek's one-try cost. Cheap tokens are not cheap safe apps.

## 6. What is next (1:45 to 2:00)

**On screen:** the fine-tuning slide: 24 exploit-verified examples, split-checked, upload blocked. Then the repo link.

> We also built a training set of 24 apps that survived every exploit. Fine-tuning was blocked on the platform today. Next, we train on that set, add more scenarios and runs, and teach the loop to close the holes, not just fix the bugs. The code is open. Thanks for watching.
