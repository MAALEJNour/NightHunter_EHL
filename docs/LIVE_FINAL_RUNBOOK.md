# Live Final runbook: NightHunter

Run everything from the root of the submitted `NightHunter_EHL` checkout. The final uses the exact
code and slides submitted on ehl.gg; do not edit after the freeze.

## Budget and credentials

The general practice/live cap remains **$7**. On 11 October, the owner authorized a separate
**$15 cumulative cap for the Live Final only**. The shared ledger currently contains **$5.893528** of
accounted/reserved spend, leaving **$9.106472** under the final cap. Each final launch is separately
limited to **$2.00** and refuses to start unless at least **$2.00** remains. It never resets or rewrites
old ledger entries.

This ledger measures this repository's model calls, not the provider's invoice. The runner sends
requests to `api.openai.com` using `LLM_API_KEY`; Codex/ChatGPT usage credits do not automatically pay
for those API calls. Check the API billing balance for that key separately before launch. OpenAI
describes Codex credits as distinct from API credits in its [credit FAQ](https://help.openai.com/en/articles/12642688)
and documents separate [ChatGPT and API billing](https://help.openai.com/en/articles/9039756).

Keep the root `.env` private and ignored. It must contain the arena URL/key, `LLM_PROVIDER=openai`,
`LLM_MODEL=gpt-5.6-luna`, `LLM_BASE_URL=https://api.openai.com/v1`, and the OpenAI API key. The
preflight prints whether values are present; it never prints their contents. It confirms the active
NightHunter team with the read-only `GET /v1/me` endpoint. This catches failures that `arena me` can
hide because the upstream command may exit successfully after an HTTP error.

## Prepare and check

Do setup and any upstream kit update well before final day. The project keeps its upstream kit pinned;
review a new kit revision deliberately rather than pulling it during launch preparation.

The announcement's `arena-sim serve --final-rehearsal` flag is not present in the kit revision pinned
here, and this checkout has no `data/package` directory. That exact local command will fail against
this snapshot. The separately announced `arena run --set final` command defaults to the kit's naive
agent; it does not run NightHunter. Do not update the pinned vendor tree during the freeze window.

```bash
uv sync --project vendor/negotiation-arena-kit/starter-kit --python 3.12 --frozen --all-extras
```

Before launch, submit the reviewed code and slides on ehl.gg, then run this safe check from the repo
root:

```bash
./scripts/start_final.sh --check
```

The check validates the clean `main` worktree and local upstream commit, secret presence without
revealing values, expected arena/model endpoints, reviewed model name, pinned data and Sunday release,
ledger headroom, active team identity, Python/runner syntax, a duplicate final-runner PID and the
model-ledger lock. The runner's lock also prevents a second model process from spending concurrently.
It uses no model call, starts no negotiation and does not consume a practice session. It prints the
full commit hash; compare that exact hash with the submission on ehl.gg.

If any check fails, the launcher stops before starting the final runner. Commit and push the approved
changes, correct the reported configuration issue, or stop and resolve the budget/key problem. Do not
work around a failed source, identity, or budget check on final day.

## Start: one command

Stop practice loops by 11:55. Submit and verify the exact code/slides freeze, then start the runner
before 12:00 so it is already waiting when wave 1 begins. Leave it running:

```bash
./scripts/start_final.sh
```

The launcher repeats the full preflight and starts the runner only if every check passes. It uses the
already-synced Python 3.12 environment with frozen dependencies and no package sync, stays alive after
the terminal closes (`nohup`), keeps the Mac awake (`caffeinate`), writes a timestamped log under
`artifacts/`, and waits for the runner to log that it entered final-case polling before printing
success. It refuses duplicate runner copies. A stale PID file from a process that has exited is
cleared automatically. An atomic launcher lock also prevents two simultaneous starts. If the process
lives but never reaches the ready marker, the launcher reports the log path and keeps its PID guard in
place; inspect it before retrying.

The runner waits on 403 until wave 1, plays each case once, uses at most 10 simultaneous sessions,
honors each case's `seconds_left`, and keeps the existing recovery path for already-running sessions.
It closes RFQs 120 seconds before the eight-minute cap and single-supplier negotiations at least 90
seconds before the cap (earlier when a slow round requires it). Its per-launch model cap is $2.00;
the cumulative ledger is hard-capped at $15.

## During and after the final

Hands off after the freeze. You may watch local progress and logs:

```bash
python3 scripts/progress.py
tail -f artifacts/final_live_*.log
```

If the runner crashes, inspect the latest log, then run `./scripts/start_final.sh` again. It refuses a
still-running copy and the runner recovers an existing session rather than opening a replacement. Do
not run practice loops or a second agent on the shared team key. Do not read the leaderboard, event
feed or results during the final, and do not change the submitted code or slides after freeze.

The runner exits when all five waves close. Local summaries are saved under
`artifacts/final_runs/<timestamp>/summary.json`; official scoring remains on the arena.
