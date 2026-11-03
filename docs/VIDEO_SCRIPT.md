# Teach'O'tron: demo video (YC style, about 90 seconds)

One speaker, voice over screen recording. Plain words, short sentences, one idea per shot. Every number is from `results/results.json`.

**Record:** QuickTime > New Screen Recording, built-in mic, quiet room. Browser full screen at 100% zoom on `ui/index.html` from `main`. Terminal: large font, dark theme. Read the voice lines slowly; pause one beat between shots. Do one take per shot, then cut them together (iMovie is fine). Export 1080p MP4.

Follows the form's three demo points: the problem, the tech stack, the benchmark.

## 1. The problem (0:00 to 0:15)

**Screen:** title card "Teach'O'tron", then the dashboard top.

> AI can write the code behind a website in seconds. But nobody checks if hackers can break in. Even the best models leave about half their working apps open to known attacks, and cheap models are worse. So teams pay for expensive ones.

## 2. Tech stack, and what it made possible (0:15 to 0:40)

**Screen:** terminal, `python3 scripts/replay_run.py results/runs/A3/Login__Python-Flask__r1.json --delay 1.0` (big font, cleared screen).

> Every app the AI writes goes into a locked Docker box. BaxBench attacks it like a real hacker: database break-ins, password theft, file escapes. Fireworks runs both models serverless, so we could test hundreds of apps on two models in one afternoon without owning a GPU. NVIDIA's Nemotron Lightning is the small, cheap model we set out to improve.

## 3. Benchmark: baseline, techniques, results (0:40 to 1:30)

**Screen:** dashboard "What $1 buys" panel (press Replay), then the headline tiles.

> Baseline: on 12 test apps it had never seen, Nemotron as is wrote 13 safe apps out of 100, and $1 bought 154. The big model got 372.
>
> We tried three techniques. One: letting it retry after failing. That was the worst deal, 83 per dollar. Two: telling it to be careful. That made it worse. Three, which worked: we kept only the big model's apps that survived every attack and showed three to Nemotron as examples. And we cut it off before it rambles.
>
> Same model, no retraining: 33 safe apps out of 100, and 722 for a dollar. That's almost twice the big model, in half the time.
>
> Attack every app. Keep what survives. Teach the cheap model with it. That's Teach'O'tron.

## If a judge asks

- **Why not fine-tune?** We built the training set (24 apps that survived every attack), but dataset uploads were disabled on Fireworks during the event. Teaching in the prompt got there without it.
- **Is the small model safer than DeepSeek?** Per try, no: 33% against 67%. Per dollar, yes: 722 safe apps against 372. Teach'O'tron is for generating many apps and keeping the ones the sandbox passes.
- **Was the 4k cap tuned on the test set?** We picked it after the first runs. No working app used more than 1,800 tokens, so the cap only cut answers that never had code.
- **Did retries fix security holes?** Not yet. Every app the sandbox loop rescued had a broken feature, not an open hole. That is our next problem.
- **Sample size?** 12 held-out scenarios, 24 runs for most Nemotron setups. Small, and we say so.
