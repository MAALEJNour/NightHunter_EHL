# NightHunter_EHL

Our entry for the **Tacto Negotiation Arena**: an autonomous procurement agent for the fictional pump manufacturer Hollerau Pumpenwerke.

The objective is to negotiate the best **total-cost deal** that satisfies the case's must-haves, or choose the available alternative. Unit price is only one component of the score.

## Run the agent (Live Final)

**Setup** (Python 3.12 and `uv`), from this repository's root:

```bash
uv sync --project vendor/negotiation-arena-kit/starter-kit --python 3.12 --frozen --all-extras
uv run --project vendor/negotiation-arena-kit/starter-kit arena data --out data   # Sunday release -> data/release-sunday
uv run --project vendor/negotiation-arena-kit/starter-kit arena me                # the key works
```

**Environment** (root `.env`, never committed; names only): `ARENA_URL`, `ARENA_API_KEY`, `ARENA_DATA`,
`LLM_PROVIDER=openai`, `LLM_MODEL=gpt-5.6-luna`, `LLM_API_KEY`, `LLM_BASE_URL=https://api.openai.com/v1`.

**Start before 12:00 and leave it running:**

```bash
./scripts/start_final.sh        # = python scripts/final_runner.py --final, logged, Mac kept awake
python3 scripts/progress.py     # live progress per case
```

`scripts/final_runner.py --final` polls `GET /v1/cases?set=final`. It plays every case of a wave in parallel
(≤ 10 sessions), closes 75 s before the 8-minute cap, resumes running sessions instead of reopening them,
and reads only cases, sessions and threads (never events, screen, leaderboard or results).

**Approach in one paragraph.** Code decides, the model writes. For each case the agent:
1. builds a source-linked dossier from the data package and the Sunday release;
2. reads the supplier's situation from its documents (approval thresholds, price freezes, cash needs,
   contract notice, quality record) and from what the supplier says in the thread;
3. values every term in euros with the published cost function;
4. sends 2–3 equal-cost term-sheet options (most attractive to the supplier at the same cost to us),
   with a goal-based opening ask and measured, reciprocal concessions;
5. cites one checked fact per argument, and answers the supplier's questions with binding figures.

It accepts only the latest primary sheet that meets every must-have and beats the alternative, and takes
a good final offer rather than countering it. RFQs run one worker per bidder and cite the best rival
bid. Evidence for every rule is in [docs/LESSONS.md](docs/LESSONS.md); results are in
[docs/MILESTONES.md](docs/MILESTONES.md) and [docs/OVERNIGHT_REPORT.md](docs/OVERNIGHT_REPORT.md).

## Project status

### Current status (11 October 2026)

**Best measured configuration:** `--policy packages --adaptation expert_prose` on `gpt-5.6-luna`
(low effort). Code designs every offer (equal-cost term-sheet menus, goal-based anchor, measured
concession schedule, supplier-health estimate); the model writes only filtered framing paragraphs.
Batch **S5** averaged **75.1** over the nine single-supplier practice cases (original agent 46.7);
the P05 RFQ runner scored **92.4** and 79.2. `gpt-6-sol` (S6) was never better at ≈ 9× cost, so
luna stays the default. The Live Final runner (`scripts/final_runner.py`) passed local and hosted
sandbox rehearsals (D01 82.4 / D02 71.9 in parallel under the 8-minute cap). The 11 October full final-runner rehearsal closed 10/10 cases with no runner errors; its scores remain rehearsal results, not guarantees. The fail-closed launch guard and full local suite pass (214 tests).

- Latest: [overnight report](docs/OVERNIGHT_REPORT.md). The [Live Final runbook](docs/LIVE_FINAL_RUNBOOK.md) covers launch, budget checks and recovery.
- Start here: [teammate handoff](docs/HANDOFF_FOR_TEAMMATE.md), [milestones and results](docs/MILESTONES.md),
  [lessons with evidence](docs/LESSONS.md).
- LLM ledger: $5.893528 accounted. Practice/live remains capped at $7; the owner approved a separate $15 cumulative cap for the final only, leaving $9.106472 under that cap. The final runner also has a $2 maximum per launch. These code limits are separate from the actual OpenAI API billing balance. Practice quota is shared with the teammate.
- Launch readiness: the reviewed launcher changes are committed and pushed; the read-only preflight verified the active NightHunter team, source, data and budget. Still submit the exact hash printed by `./scripts/start_final.sh --check` plus the slides on ehl.gg, and verify API billing for `LLM_API_KEY`. The Sunday release is present and the 10-case final-runner rehearsal completed on 11 October (10/10 deals, zero errors/timeouts; slowest case 223 s).

For a no-session preflight, run `./scripts/start_final.sh --check`. To start the autonomous final runner after freeze, run `./scripts/start_final.sh`; it verifies the active NightHunter key, clean pushed source, data and budget before launching. Codex usage credits are not API credits for the runner's `LLM_API_KEY`; check the API billing balance separately.

The paragraphs below are the earlier (Codex-era, Batch A–A3) history; the CLI defaults
(`--policy current`, `--adaptation current`) remain the control.

The full upstream snapshot (323 files), Python 3.12.15, uv 0.13.0 and all 47 locked packages are installed. The naive buyer passes all three simulator cases. Hosted practice has now covered P01, P02, P03, P04, P07, P08, P10, P11 and P18 in Batch A2. The live runner still supports single-supplier cases; RFQ scheduling and final-wave readiness remain under development.

The **opt-in** `--policy packages` uses a source-linked supplier profile and deterministic package planner. The model selects only tone, intent and checked claim IDs; code sends the planner's exact validated terms. A model failure sends a neutral message with those same packages, while final offers, the last buyer round and planner acceptance recommendations use the existing close check. Plans and profiles are saved in decision and comparison diagnostics. The planner uses the cheapest must-have-compliant current sheet as its baseline and estimates relationship costs from public should-cost data in relationship-sensitive categories; the estimate is uncertain. Hosted A2 exposed an acceptance bug: alternative IDs in a supplier reply can be rejected by the API as non-standing. [Review and coordination notes](docs/HANDOFF.md).

**Batch A stopped under its error rule** after four completed sessions and two pre-session P03 errors. On one matched run each, P01 scored 62.80 current versus 67.77 packages; P02 scored 34.57 current versus 22.47 packages. All four deals met must-haves, with zero fallbacks. P02 packages incurred a large supplier-health charge despite better price/payment terms. Spend was $0.05022210 and four practice sessions. The P03 null-notice crash was fixed locally **after** Batch A stopped; none of its sessions used that fix. See [full Batch A results, cost parts and conversations](docs/BATCH_A_RESULTS.md). One run per condition is diagnostic, not proof of a better policy. Defaults remain `--policy current`, `--input-version current` and `--adaptation current`.

**Batch A2** used the later frozen code across all nine supported single-supplier practice cases. Of 18 attempted conditions, 15 completed must-have-compliant deals; P02 packages and both P18 attempts failed when the hosted API rejected an alternative offer ID with HTTP 422. P11 packages had one model fallback. On the seven complete pairs, current mean/worst was **58.75/22.61** versus packages **67.64/48.76**; these exclude the failures. A zero-filled nine-case failure-inclusive view was 50.35 versus 52.61 mean, with worst case zero for both; those zeros are not official scores. Batch spend was **$0.23153115**, lifetime ledger **$0.67388700/$5**. The observed quota moved 468→432 while 18 sessions opened; the additional decrease is unexplained. [Full A2 results, costs, flags and conversations](docs/BATCH_A2_RESULTS.md). One run per condition is diagnostic. Defaults remain `--policy current`, `--input-version current` and `--adaptation current`.

**Batch A3 stopped after 5 of 27 planned conditions** when a new file in the shared `nighthunter/` worktree changed the frozen code fingerprint. The runner opened no further session under that fingerprint. P01 scored 55.66 current and 73.89/73.89 packages; P02 scored 50.03 current and 42.95 on its first packages repeat. All five deals met must-haves, with zero model fallbacks and no HTTP 422. Both P01 packages repeats were 10.23 points below A2 packages; P02 packages was 7.08 below A3 current. Spend was **$0.08272970**; lifetime ledger **$0.75661670/$5**; quota observed 422→417. The [partial A3 report](docs/BATCH_A3_RESULTS.md) includes every term, cost component, A2 delta and conversation. The remaining 22 conditions need a new frozen batch; these partial scores do not establish policy quality. Defaults remain `--policy current`, `--input-version current` and `--adaptation current`.

- [Discovery and implementation plan](docs/PLAN.md): rules, data, architecture, tools, milestones, validation and open questions.
- [Presentation notes](docs/PRESENTATION_NOTES.md): your notes, with differences from the written rules recorded explicitly.
- [Agent instructions](AGENTS.md): how future coding agents should work on this project and maintain its documentation.
- [Local testing guide](docs/LOCAL_TESTING.md): environment, naive buyer, tests and optional Docker instructions.
- [Gradual experiments](docs/EXPERIMENTS.md): context builder, four prompt approaches, budget and a short timeline.
- [Live prompt comparison](docs/PROMPT_COMPARISON.md): eight autonomous P01 deals; scores, costs and replay links.
- [Improvement plan](docs/IMPROVEMENT_PLAN.md): measured weaknesses, useful upstream examples, economic package search and the learning loop.
- [Saved-run review](docs/SAVED_RUN_REVIEW.md): all 28 saved transcript links, including failures and the later P01/P03/P02 batches.
- [Offer-history comparison and first P02 results](docs/INPUT_MEMORY_RESULTS.md): ten matched hosted attempts across P01/P03/P02 and why the new input was not promoted.

## Context and prompt preparation

`nighthunter/context.py` builds a source-linked dossier from a case JSON and the bundled buyer data. It preserves the exact case and essential contracts, reports missing/omitted evidence, and bounds optional history. `nighthunter/experiment.py` prepares four prompt variants with identical dossier context; this does not call a model or generate negotiation scores. Instructions live in `prompts/`, and context tests in `tests/`.

The initial USD 5 LLM testing budget is recorded. The live pilot uses the configured gpt-5.6-luna model with dossier context and budget accounting. See [experiment commands and timeline](docs/EXPERIMENTS.md). The separate naive baseline does not use dossiers.

## Start a real discussion and see its score

First hosted result: **68.45/100 on P01**, with assistant recovery after a runner error. Read [the result and limitations](docs/FIRST_LIVE_RESULT.md).

With the arena and OpenAI keys configured in the root `.env`, run from this directory:

```bash
uv run --project vendor/negotiation-arena-kit/starter-kit --frozen --all-extras python -m nighthunter.live --case case:P01 --variant evidence_first
```

This makes paid calls to the configured `gpt-5.6-luna` model and opens one Tacto practice session after model preflight succeeds. It prints both sides of the discussion and the final result. Each run saves `conversation.md`, `conversation.json`, `decisions.json`, `summary.json` and the arena state under the printed `artifacts/live/<timestamp>/` directory. The summary includes score, total cost, terms, replay URL, fallback count and conservative model spending. A failed preflight saves an error and opens no practice session.

The persistent ledger in `artifacts/llm-budget.json` enforces a USD 5 cumulative allowance for this runner and USD 0.75 per run; do not delete it to repeat tests. It does not track calls from other programs. This pilot supports one supplier and a bounded set of checked factual claims. Results are experiments, not production-ready negotiation guarantees.

Validation update: the live buyer now selects checked claim cards and exact packages; code renders factual sentences and rejects invalid term values. Free-form model prose is not transmitted. After correcting an overly pessimistic acceptance check, an unassisted P01 run closed a valid deal at 49.70/100 with zero fallbacks. This proves autonomous completion; it does not establish the best prompt. See [the experiment plan](docs/EXPERIMENTS.md) for controlled comparisons.

The completed matched comparison produced eight valid autonomous deals with no fallbacks. Adaptive led the two-repeat P01 sample at **61.78/100 mean**, followed by evidence-first at 59.23, baseline at 57.59 and reciprocal trades at 26.63. Use `--variant adaptive` to try that candidate; broader case testing is still needed. Full conversations and replay links are indexed in [the comparison report](docs/PROMPT_COMPARISON.md).

Cross-case check: unchanged adaptive completed **P03 (contract renewal) at 85.15/100**, autonomously with zero fallbacks, for about USD 0.0081. Agreed terms: EUR 432/unit, 60-day payment, 36 months and 4,580 units/year. [Result, discussion and replay](docs/ADAPTIVE_P03_RESULT.md). This is one exploratory run, not a paired prompt comparison. Cumulative accounted model spending is USD 0.12277445 of the USD 5 allowance.

Latest experiment: calculated package choices and within-session concession history raised the observed **P01 mean to 71.90** versus 49.05 for two fresh controls; **P03 scored 88.27** versus 73.07 for one fresh control. All six closed valid deals autonomously with zero fallbacks. This is a small exploratory comparison. Enable the candidate with `--variant adaptive --policy economics`; the original policy stays the default. [Results, costs and replays](docs/ECONOMIC_POLICY_RESULTS.md). Current cumulative accounting: **USD 0.2027154 of USD 5**. The earlier totals above are historical checkpoints.

New cross-case input check: filtering used evidence and showing the model its prior offers eliminated duplicate-card drops, but **did not improve overall scores**. P01 averaged 56.81 versus 71.38 for the control; P03 averaged 85.08 versus 84.03; the first P02 hosted pair scored 6.57 versus 24.87. All ten attempts closed autonomously with no fallback. Keep `--input-version current` (the default); `--input-version offer_history` remains experimental. See [the results and transcripts](docs/INPUT_MEMORY_RESULTS.md). Current cumulative model accounting: **USD 0.39213375 of USD 5**. The prior total above is a historical checkpoint.

Earlier implementation: closing prices valid term sheets in the latest supplier reply, completes missing terms from quote defaults, checks must-haves and the alternative, and chooses the lowest estimated total-cost offer by exact ID. A2 showed that a non-primary alternative ID can fail hosted acceptance with HTTP 422, so this path needs a contract fix before further hosted use. Checked claim cards label potential buyer leverage, seller support or uncertainty; internal should-cost estimates and unit-only competing quotes cannot be selected for supplier messages. Optional `--input-version unused_claims` and `buyer_history` isolate the two parts of the earlier combined experiment. Optional `--adaptation reply_aware` uses current-thread feedback; these optional input/adaptation modes were not tested in A2. The controls remain `--policy current`, `--input-version current`, and `--adaptation current`.

Local verification from the repository root (the test suite uses mock HTTP responses; the simulator uses only `127.0.0.1` and disposable credentials):

```bash
vendor/negotiation-arena-kit/starter-kit/.venv/bin/python -m pytest tests -q
vendor/negotiation-arena-kit/starter-kit/.venv/bin/python scripts/test_naive.py --case all
vendor/negotiation-arena-kit/starter-kit/.venv/bin/ruff check --select E4,E7,E9,F nighthunter tests
```

Previous local result: **49 tests passed**; S01/S02/S03 scripted deals closed with their historical baseline scores 52.06/51.32/67.76. The simulator checks integration, not hosted persuasion. A controlled input experiment should isolate unused-card filtering from buyer history on the same frozen dossiers and compare complete cost, worst-case score, deal/must-have/fallback outcomes and failures. Do not promote any optional mode from local scores alone.

The package-policy update adds offline fake-model regression coverage for exact outgoing terms, ignored model terms, safe closing and neutral fallback. Run it with `vendor/negotiation-arena-kit/starter-kit/.venv/bin/python -m pytest tests/test_packages_policy.py -q`. Validation: **8 focused tests and 79 full-suite tests passed**; Ruff (`E4,E7,E9,F`) passed on the touched Python files. No hosted negotiation was run for this update.

## Try the naive negotiator

From this repository's root:

```bash
uv run --project vendor/negotiation-arena-kit/starter-kit --frozen --all-extras python scripts/test_naive.py
```

Add `--case all` to run all three bundled cases, or `--case case:S02` for the RFQ. The script starts and stops its own local simulator, prints the deal and score, and needs no API keys or model credits. It uses the upstream `NaiveAgent`: open 10% below the supplier price, split the gap on subsequent offers, and accept early. This is a baseline to improve, not the final strategy.

## Source material

Upstream: [tacto-ai/negotiation-arena-kit](https://github.com/tacto-ai/negotiation-arena-kit), inspected at commit `1b5516bb95ef28e37f69aa446dc62168864bca53`.

The source was first inspected separately, then imported at your request into [vendor/negotiation-arena-kit](vendor/negotiation-arena-kit/README.md). All tracked upstream files are included, without its Git history. See [provenance and licenses](docs/UPSTREAM.md).

Start with upstream's [brief](https://github.com/tacto-ai/negotiation-arena-kit/blob/1b5516bb95ef28e37f69aa446dc62168864bca53/brief/brief.md), [API contract](https://github.com/tacto-ai/negotiation-arena-kit/blob/1b5516bb95ef28e37f69aa446dc62168864bca53/brief/api.md), [starter kit](https://github.com/tacto-ai/negotiation-arena-kit/blob/1b5516bb95ef28e37f69aa446dc62168864bca53/starter-kit/README.md), and [submission requirements](https://github.com/tacto-ai/negotiation-arena-kit/blob/1b5516bb95ef28e37f69aa446dc62168864bca53/brief/submission.md).

## Proposed pipeline

Read case and supplier history → build a dossier with source IDs → calculate candidate packages → negotiate and update the dossier → validate and accept the best standing offer, or walk away → evaluate the replay.

Use an LLM for interpretation and business communication; use deterministic code for money, evidence checks, legal API values, deadlines and closing decisions. Logical specialist roles can share one orchestrator; multiple model calls are an experiment, not a prerequisite.

## Setup prerequisites

The supplied kit requires **Python 3.12** and `uv` (installed locally). The local naive test requires no credentials. Hosted play needs one team arena key; an LLM buyer additionally needs our own model access. Keep credentials in an untracked environment file or environment variables; never paste them into documentation or commits.

Open the root `.env` and fill in `ARENA_API_KEY=your_team_key`. The file is ignored by Git; [.env.example](.env.example) is the shareable template with blank credentials. LLM settings can remain blank until we choose a model.

After Python 3.12 and `uv` are installed, run these from **this repository's root**:

```bash
uv sync --project vendor/negotiation-arena-kit/starter-kit --python 3.12 --frozen --all-extras
uv run --project vendor/negotiation-arena-kit/starter-kit arena me
uv run --project vendor/negotiation-arena-kit/starter-kit arena cases --set practice
```

Keep the working directory here: the kit reads `.env` from the current directory, and `ARENA_DATA` points to the bundled data. Dependencies, team authentication, case discovery and live model access have been exercised. `arena me` verifies the team account; listing cases does not start a negotiation.

## Feasibility

Building a functioning autonomous buyer is feasible with this kit. Competitive performance needs measured experiments; a winning score cannot be promised. The repository supplies the public data and simulator, but the real supplier bots and hidden final cases remain hosted by Tacto. LLM access and final-machine testing are still required.

## Development workflow with Entire

1. Work with the coding agent to make and review a change.
2. Commit the change with a descriptive message.
3. Push the commit and check the terminal output for Entire's checkpoint upload confirmation.

With Entire enabled and its agent hooks approved, session checkpoints can accompany your normal Git workflow.
