# NightHunter project handoff

> **Historical snapshot:** the repository state, budget, Sunday release and commands below describe
> an earlier 10 October handoff. For current launch instructions and the 11 October budget, use the
> [README](../README.md) and [Live Final runbook](LIVE_FINAL_RUNBOOK.md). The reviewed launcher changes
> must be committed/pushed and submitted on ehl.gg before its clean-source preflight will pass.

Snapshot: 10 October 2026, late evening, after batches S5/S6 and the final-runner rehearsal. This is a
factual handoff for a teammate (or the teammate's LLM) working in the `NightHunter_EHL` repository. It
is not a request to open Arena sessions. Do not copy credentials from the root `.env` into prompts,
logs, commits or documentation; its values were not read for this document.

## Executive context

Same hackathon, same buyer (Hollerau Pumpenwerke), same score:
`clip((C_open − C_deal) / (C_open − C_best), 0, 1)`, averaged over 50 hidden final cases in five waves
(8-minute cap per wave). The hidden final suppliers are new, so nothing here may depend on a practice
case ID, a practice supplier's score, `C_best`, or a saved replay at run time.

Our agent is a **code-first negotiator with a model as copywriter**:

- **Code decides every number.** For each round, a deterministic planner (`nighthunter/packages.py`)
  builds 2–3 complete term sheets that cost us the same total `C` but are worth different amounts to
  the supplier ("equal-cost menus"). It controls the opening ask, the size of each concession, and
  when to accept.
- **The model writes only the framing paragraphs**: opening, rationale and closing (`--adaptation
  expert_prose`). A filter (`nighthunter/prose.py`) rejects any paragraph containing digits, IDs,
  money, percentages, competitor claims, threats, volume promises, supplier-cost claims or escalation.
  All figures, cited facts and the options themselves are rendered by code from checked claim cards.
- **RFQs** (2–3 bidders) run with one concurrent worker per bidder (`scripts/rfq_live.py`, decisions in
  `nighthunter/rfq.py`), cite a lower rival bid with its `offer:` ID and EUR price, and close exactly once.

This differs from the teammate agent in `negotiation-arena-kit/starter-kit/arena_kit/agents/` (where an
LLM e-mail expert writes around portfolio packages). The two code bases are separate; nothing here
imports the teammate's modules.

**Current status:** best measured configuration is `--policy packages --adaptation expert_prose` on
`gpt-5.6-luna`, low reasoning effort. Batch S5 (one run per case, nine single-supplier cases) averaged
**75.1**; P05 RFQ scored **92.4** and **79.2** in two runs. One small fix (forced contract-notice
citation, lesson L32) was merged after S5; the current source has passed the unit tests, the offline
replay gate and the hosted **sandbox** rehearsal, but **no practice case has run on it yet**.

## Repository and source state

| Item | State at this snapshot |
| --- | --- |
| Repository | `NightHunter_EHL`, branch `main` |
| `HEAD` | `855ae1d` (import of the kit + plan). **Nothing of the agent is committed yet**: `nighthunter/`, `prompts/`, `scripts/`, `tests/`, `twin/` and most `docs/` are untracked. A baseline commit is waiting for the owner's approval. |
| Current code + prompt fingerprint | `0366a02e2220059efb553e8d0777dafd4face86747473a2f5c689195524f26ca` (`nighthunter.compare.fingerprint()`) |
| S5 evaluated fingerprint | `cfdc6a0f90751b52783874374f7d7c515aa4a24892357c44ec65b260bb250890` (`artifacts/strategies/S5_20261010T204627Z/manifest.json`) |
| Tests | `pytest tests` → **184 passed** |
| Model | `gpt-5.6-luna` in `.env` (only the `LLM_MODEL` line was changed, back from `gpt-6-sol`). Other models only via the explicit `--llm-model` flag, and only if priced in `nighthunter.live.PRICES`. |
| LLM budget ledger | `artifacts/llm-budget.json`, cumulative **$4.511** of a **$7** cap (`TOTAL_LIMIT_USD`, raised from $5 by the owner). Never reset it. |
| Practice quota | 257 of 550 left (rolling 24 h, resets 2026-10-11 12:37 UTC), **shared** by both agents on the team key |
| Upstream kit | `vendor/negotiation-arena-kit/` (pinned, do not modify) |
| Sunday release | not downloaded yet |

## Measured results

Score is per case ×100. Team best = `arena me` best over all team runs (both agents).

| Case | Type | S1 original agent | S5 (current config, 1 run) | Team best | Top team (leaderboard, 10 Oct late) |
| --- | --- | ---: | ---: | ---: | ---: |
| P01 | price increase | — | 79.7 | 84.1 | 100 |
| P02 | price increase, copper | — | 73.5 | 73.5 | 85 |
| P03 | renewal | — | 90.0 | 90.4 | 96 |
| P04 | renewal | — | 86.0 | 87.4 | 87 |
| P05 | RFQ, 3 bidders | — | 92.4 / 79.2 (M3) | 92.4 | 96 |
| P07 | bundle | — | 71.0 | 72.7 | 81 |
| P08 | alloy surcharge | — | 67.9 | 70.0 | 92 |
| P10 | capacity | — | 69.4 | 69.4 | 70 |
| P11 | quality | — | 79.4 | 79.4 | 88 |
| P18 | alloy surcharge | — | 58.7 | 58.7 | 73 |
| **Mean (9 single)** | | **46.7** | **75.1** | | |

Batch history (all hosted practice, sequential, frozen code per batch):

| Batch | What changed | Result | Lesson |
| --- | --- | --- | --- |
| A / A2 / A3 (Codex era) | packages planner vs original prompt agent | packages 67.6 vs current 58.8 on complete pairs; HTTP 422 on alternative IDs | accept only the latest **primary** sheet (L11) |
| S1 | 3 strategies × 9 cases | original 46.7, packages 67.3, prose 0/31 paragraphs sent (prompt conflict) | fixed the prompt |
| S2 | packages v2 + persuasive e-mails | prose ahead on 5 of 8 paired cases; P11 broken by a chargeback valued at 0 | L16, L19 |
| S3 | twin-tuned anchor ×1.5 + bigger steps | ambitious anchor lost P18 −10, P03 −7, P02 −3 | L24: the twin over-rewards aggression |
| S4 | low vs medium reasoning effort | wash at the same cost | L29 |
| M3 | P05 RFQ, 2 runs | **92.4** and 79.2 | L27, L28 |
| S5 | all fixes, luna | **75.1 mean**, best batch | — |
| S6 | `gpt-6-sol` on the 5 biggest-gap cases | never better: P01 −22.4, P18 −6.7, P08 −7.6, two ties; ≈ 9× cost | L31, L32 |
| Final-runner rehearsal | sandbox D01 + D02 in parallel, 480 s cap | 82.4 / 71.9, done in 125 s / 202 s | — |

One run per case is a regression screen, not a performance estimate; hosted suppliers vary ±5–10 points
run to run.

## Architecture (files that matter)

| Module | Responsibility |
| --- | --- |
| `nighthunter/context.py` | Builds the case dossier (≤ 40k chars) from the data package: scoped DB rows, contracts, correspondence, should-cost, scorecards, each with source IDs. |
| `nighthunter/supplier_profile.py` | Reads the supplier: approval threshold, price freeze, cash pressure, stale costing, `observed_ppm` (latest scorecard), contract-trigger checks, tactics with source refs. `session_signals(events)` adds what the supplier said in this thread (cash request, "I have authority"). |
| `nighthunter/packages.py` | The planner. Goal-based anchor (`GOAL_MAX_CUT`: stabilise 6 %, quality_first 8 %, routine/secure_supply 10 %, leverage 22 %), concession schedule `GAP_STEPS` (25 → 10 % of the remaining gap), reciprocity (mirror the supplier's move), term ratchet (never give back a granted term), per-mix monotone price, options ranked by **value to the supplier** at equal cost to us, supplier-health estimate (should-cost × 0.985) with `HEALTH_MARGIN`. Returns packages, target and `recommend_accept` / `exhausted`. |
| `nighthunter/prose.py` | `compose()` assembles the e-mail: salutation, model framing (filtered), code-rendered options and claims, one question. `check_text()` is the filter. |
| `nighthunter/live.py` | `LiveAgent` (decide/close loop on top of the kit's `play`), `BudgetedModel` (ledgered OpenAI calls, per-run $0.75, total $7, retry once, disable after two consecutive failures), `forced_claims` (code-forced citations), `RecordingTable` (saves every message). CLI: `python -m nighthunter.live`. |
| `nighthunter/rfq.py` | RFQ decisions: exact terms (never snapped), acceptable offers, rival benchmark and rival claims (lower prices only), bidder ranking by motivation, single close decision. |
| `nighthunter/validation.py` | Outbound term-sheet validation (allowed fields/values, must-haves). |
| `scripts/run_strategies.py` | Sequential hosted batches with frozen dossiers and code fingerprint; stops on code change, budget ceiling, broken must-have or a repeated error. |
| `scripts/rfq_live.py` | RFQ runner (`--local` for the simulator, `--model` for model framing). |
| `scripts/final_runner.py` | **Live Final runner**: polls waves, plays every case of a wave in parallel, shared thread-safe budget, resumes sessions on 409, closes 75 s before the cap. Reads only cases/sessions/threads (no event feed, screen or leaderboard). |
| `scripts/review_run.py` | Round-by-round review of a run: step shares, token steps, ignored questions, countered final offers, contradicted claims. |
| `twin/` | Digital-twin suppliers calibrated on ~200 saved transcripts (ours + teammate's replays). Good for bug-finding; **not** trusted for aggressiveness (L24). |
| `prompts/expert_prose.md` | The only prompt used by the current config. |

## What we learned (full list with evidence: `docs/LESSONS.md`)

The lessons that moved the score most:

1. **Total cost, not unit price** (L1). Every term is valued in EUR before it is traded.
2. **The first supplier reply carries most of the money** (L2), so the opening ask matters, but **only
   slightly beyond the supplier's room**: far deeper asks get stonewalled (L17, L24, S3).
3. **Suppliers mirror concessions.** Steps of 15–30 % of the remaining gap work; one-cent steps freeze
   them and big steps make us cave (L4, L25).
4. **Never give back a granted term, and never lower our price on the same terms** (L5, L6).
5. **Offer what is worth most to the supplier at equal cost to us** (L7, L18). Many suppliers price
   payment days or start dates far below their cash value.
6. **Health cost in stabilise/secure-supply cases**: a deep cut draws a supplier-health charge (L8, L26).
7. **Value a chargeback at the supplier's real PPM**, or the supplier raises its price (L19; P11 went
   from 23 to 79).
8. **Answer the supplier's question** (L9) and never escalate to a manager when it claims authority (L10).
9. **RFQ: read the bidders.** The most motivated one (free capacity plus a cash request) gives the deep
   price. Cite the rival's exact `offer:` ID and price (L13, L27, L28).
10. **A bigger model does not help** (L29, L31). Decisive evidence must be cited by code (L32).

## Remaining gaps and hypotheses (not yet tested)

- **P08 / P18 (alloy surcharge, −22 / −14 vs top)** are now the biggest gaps. Root cause found (L33): the
  supplier says a 36-month contract needs an index clause, but our planner keeps offering fixed-price
  36-month options. A fix (`INDEX_REFUSAL`) was tested hosted (S7) and gave no gain, so it is off. Offline,
  the best P08 deal is about €5.05 against our €5.28–5.35: the gap is the price endgame, not the structure.
- **P01 (−16 vs best team run)**: start-date deferral is the money; the notice citation is now forced.
- **P11 (−9)** and **P07 (−9)**.
- `OUR_TERMS_OPTION` (always offer "your price, our terms"): +6 on the twin, untested hosted (L23).
- RFQ: cap the mirroring of a big first concession when competition already supplies pressure.
- L20 (teammate): answer a firm-release request with a priced longer contract.

## Pending decisions for the owner

1. **Baseline commit** of the current source (without `.env` or `artifacts/`). Not done; needs approval.
2. **Budget cap**: raised by the owner to **$7** total (`TOTAL_LIMIT_USD`, used by `BudgetedModel` and
   `SharedModel`). Ledger $3.94 → ≈ $3.06 left; a luna final costs ≈ $0.90 (≈ $0.018 per negotiation).
3. **`gpt-6-astra` was tested once on P08** (owner-approved one-off caps): **63.7** vs luna 67.9. The model
   is not the bottleneck (L31, L33); stay on luna. The `--run-limit-usd` / `--total-limit-usd` flags in
   `nighthunter.live` default to $0.75 / $7; raising them needs the owner's approval.
4. **Full 10-case rehearsal** from the final machine through `scripts/final_runner.py` (10 practice
   sessions, ≈ $0.20).

## Commands

Run from the repository root (the kit loads the root `.env`). Paid or quota-consuming commands are marked.

```bash
PY="uv run --project vendor/negotiation-arena-kit/starter-kit python"

$PY -m pytest -q tests                                   # 184 tests, free
$PY scripts/final_runner.py --rehearse case:S01 case:S02 case:S03 --local --cap 480   # local sim, free
$PY scripts/final_runner.py --rehearse case:D01 case:D02 --set sandbox --cap 480       # sandbox, model $
$PY -m nighthunter.live --case case:P08 --variant adaptive --policy packages \
    --adaptation expert_prose --out artifacts/live/P08_try                             # 1 quota + model $
$PY scripts/run_strategies.py --name S7 --limit-usd 0.30 --cases P08 P18 \
    --conditions luna=packages/expert_prose                                            # quota + model $
$PY scripts/review_run.py artifacts/strategies/S5_20261010T204627Z --summary            # free
$PY -m twin.evaluate -n 20                                                             # free
$PY scripts/final_runner.py --final                                                    # THE LIVE FINAL
```

Rules that keep runs comparable: hosted batches strictly sequential; never edit `nighthunter/*.py` or
`prompts/*.md` while a batch runs (the fingerprint check stops it); do experimental edits in a scratch
copy; keep `--policy current` as the control.

## Where the conversations are

- `artifacts/strategies/<batch>_<ts>/<case>/<label>_<n>/` contains `conversation.json` (every message,
  diagnostics, model framing, plan per round), `decisions.jsonl`, `summary.json` (score, `c_deal`, cost
  parts, replay URL) and `state.json`.
- `artifacts/rfq/<case>_<ts>/` contains RFQ runs (`conversation.json`, `ranking.json`, `summary.json`).
- `artifacts/final_runs/<ts>/` contains final-runner rehearsals.
- Teammate replays: `~/Downloads/replays` and `~/Downloads/saved-negotiation-conversations-2026-10-10/replays`.

`artifacts/` is git-ignored: copy the folders you need, never commit them.

## Before the final

1. Download the Sunday release (`arena data`) and check that `DataPackage` merges it.
2. Approve the budget cap for the final, then run the full 10-case rehearsal on the final machine.
3. Make the frozen commit and record its fingerprint.
4. Run `scripts/final_runner.py --final` before the first wave: no human intervention, one session per
   case, and no leaderboard or event-feed access.

Latest: [OVERNIGHT_REPORT.md](OVERNIGHT_REPORT.md) (path-to-target per case, what the data can and cannot show).

Suggested reading order: this file → `docs/MILESTONES.md` → `docs/LESSONS.md` → `nighthunter/packages.py`
→ `nighthunter/live.py` (`LiveAgent.decide`) → `scripts/final_runner.py` → one S5 conversation (for
example P08).
