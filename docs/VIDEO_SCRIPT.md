# Teach'O'tron: demo video (YC style, about 90 seconds)

One speaker, voice over screen recording. Plain words, short sentences, one idea per shot. Every number is from `results/results.json`.

**Record:** QuickTime > New Screen Recording, built-in mic, quiet room. Browser full screen at 100% zoom on `ui/index.html` from `main`. Terminal: large font, dark theme. Read the voice lines slowly; pause one beat between shots. Do one take per shot, then cut them together (iMovie is fine). Export 1080p MP4.

## Shot 1. The hook (0:00 to 0:10)

**Screen:** title card: "Teach'O'tron. AI writes the backend. Who attacks it?"

> AI can write your backend in seconds. But nobody checks whether it can be hacked. Teach'O'tron does, and then it uses what it learns to teach a cheap model to write safer code.

## Shot 2. The sandbox loop (0:10 to 0:35)

**Screen:** terminal, run `python3 scripts/replay_run.py results/runs/A3/Login__Python-Flask__r1.json --delay 1.0`. Let it play.

> Here is how it works. A model writes an app, say a login service. We drop it into a sealed Docker sandbox and attack it: real SQL injection, real password theft, real file escapes. Plus the tests a user would run. If it fails, the model gets one line back: what broke. Never the attack code. It tries again. Only an app that works and survives every attack counts as safe.

## Shot 3. The surprise (0:35 to 0:55)

**Screen:** dashboard, headline tiles, then the "All setups" table. Point at the small-model rows.

> We tested a big model, DeepSeek, and a small one, NVIDIA Nemotron, which is six times cheaper per token. Surprise: for every dollar, the small model gave us 154 safe apps. The big one gave 372. Cheap tokens are not cheap safe code. Even retrying in the sandbox made the small model a worse deal.

## Shot 4. Teach'O'tron (0:55 to 1:15)

**Screen:** README hero table on GitHub (three rows), or the live dashboard. Point at Nemotron as is, then Teach'O'tron, then DeepSeek.

> So we turned the sandbox into a teacher. We kept only the big model's apps that survived every attack, and showed three of them to the small model. No training. We also cut it off before it rambles. Same Nemotron: safe apps went from 12 in 100 to 33. And for every dollar, 722 safe apps. That's almost twice the big model, at less than half the wait.

## Shot 5. The close (1:15 to 1:30)

**Screen:** live dashboard URL, then the repo link on a plain card.

> Attack every app in a sandbox. Keep what survives. Teach the cheap model with it. That's Teach'O'tron, built on Fireworks with NVIDIA Nemotron, and it's open source. Thanks.

## If a judge asks

- **Why not fine-tune?** We built the training set (24 apps that survived every attack), but dataset uploads were disabled on Fireworks during the event. Teaching in the prompt got there without it.
- **Is the small model safer than DeepSeek?** Per try, no: 33% against 67%. Per dollar, yes: 722 safe apps against 372. Teach'O'tron is for generating many apps and keeping the ones the sandbox passes.
- **Was the 4k cap tuned on the test set?** We picked it after the first runs. No working app used more than 1,800 tokens, so the cap only cut answers that never had code.
- **Did retries fix security holes?** Not yet. Every app the sandbox loop rescued had a broken feature, not an open hole. That is our next problem.
- **Sample size?** 12 held-out scenarios, 24 runs for most Nemotron setups. Small, and we say so.
