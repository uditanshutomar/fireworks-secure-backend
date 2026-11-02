# Tasks and how we talk

Every task is a GitHub issue. Talk in the issue's comments, not in chat, so everyone sees the same thing.

- Start every comment with who you are: `[Sukriti]`, `[Uditanshu]`, `[P1]`, `[P2]`, `[P3]`.
- Starting a task: comment `taking it`. Done: comment `done` with the branch or commit, then the P1 seat reviews and merges.
- Blocked: comment `blocked:` and what you need. Anything for everyone goes in the **Standup** issue.
- Work on a branch named after the issue (`12-repair-loop`), open a PR that says `Closes #12`.
- Never paste keys, `.env` contents or the locked test list anywhere in the repo, issues or PRs.

## Schedule (Pacific, Nov 2)

| Time | Milestone |
|---|---|
| 11:50 | Repo, contracts and fake data up |
| 12:00 | BaxBench smoke run on P1, fine-tune go/no-go |
| 12:00 to 12:40 | Training data generated on P1 |
| 12:30 | P2 and P3 modules merged |
| 12:40 | LoRA training started |
| 12:40 to 1:30 | Arms A1 to A3 run |
| 1:30 to 2:00 | Tuned model deployed, A4 and A5 run |
| 2:00 to 2:15 | Real results in the dashboard and README |
| 2:15 to 2:30 | Backup video take |
| 2:30 to 2:50 | Final video and form |
| 3:00 | Submitted |

## Fallbacks

- Nemotron Nano 3 not tunable at 12:00: tune Qwen 3.8 27B instead, Nemotron stays as A2 and A3.
- Training not finished by 1:45: run A4 and A5 at 1 run per scenario.
- Docker too slow: 2 runs per scenario for every arm.
