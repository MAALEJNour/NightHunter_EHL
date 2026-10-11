# Live Final runbook: NightHunter

Everything is run from the repository root on this laptop: `cd ~/NightHunter_EHL`.

## Before 11:55

1. **Machine:** plugged in, sleep disabled (the launcher also runs `caffeinate`), stable network. Close
   other heavy programs.
2. **Key works:**
   `uv run --project vendor/negotiation-arena-kit/starter-kit arena me` shows team NightHunter.
3. **Sunday release present:** `ls data/release-sunday/facts.json`. If it's missing, run
   `uv run --project vendor/negotiation-arena-kit/starter-kit arena data --out data`.
4. **LLM budget:** the code caps total spend at `TOTAL_LIMIT_USD = 7` in `nighthunter/live.py`. The final needs
   about $1. Check the spend so far:
   `python3 -c "import json;print(sum(r['accounted_usd'] for r in json.load(open('artifacts/llm-budget.json'))))"`.
   Keep at least $1.20 of the approved $7 cap available for the final, so prior spend should be at most $5.80.
   Last checked 11 October: the ledger was $5.893528, leaving $1.106472—about $0.09 below that reserve.
   Recheck before launch. Do not raise the $7 cap without the budget owner's approval; if remaining funds
   are insufficient, do not start the final until its budget is resolved.
5. **Stop every practice loop by 11:55.** Practice sessions count against our 10 open sessions and can block
   wave 1. Check that nothing is running: `pgrep -fl final_runner`. Only ONE agent may use the team key
   (your teammate must not run).
6. **Freeze on ehl.gg at 12:00:** repo link + commit hash + short description + slides
   (`docs/slides/NightHunter_pitch.pptx`).

## Start (before 12:00)

```bash
./scripts/start_final.sh
```

This prints the log file name (`artifacts/final_live_<time>.log`) and the runner's process ID. The runner:
- waits while the final list answers 403 (before wave 1);
- plays every case of each wave in parallel (at most 10);
- stops RFQ negotiations 120 seconds before the 8-minute cap; single-supplier cases switch to a safe close
  90 seconds before the cap, or earlier if their slowest round needs more time;
- resumes running sessions after a crash;
- never reads the leaderboard, the screen, the event feed or results.

## During the final: hands off

- Watch only:
  - `python3 scripts/progress.py` (per-case status);
  - `tail -f artifacts/final_live_*.log`.
- If the runner crashes, restart it with `./scripts/start_final.sh`. It picks up its running sessions (a 409
  names the running session). That is allowed; picking cases or writing messages by hand is not.
- Do not edit code after 12:00 (freeze; the top 10 are checked for pushes).

## After the last wave

- The runner exits after the fifth wave has closed. Results: `artifacts/final_runs/<time>/summary.json`.
- Replays and supplier reasons appear on arena.tacto.ai/results after the final. Pick one negotiation for the
  pitch (suggested: a price-increase case where the notice-period citation earned "a fair point").
