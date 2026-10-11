# Gradual improvement and prompt experiments

## Current checkpoint

New local-only validation: 28 saved conversations and six comparison manifests were reconciled; no new hosted run was made. All 49 local project tests pass after deterministic latest-reply offer selection, conservative claim labels/internal should-cost handling, separately selectable `unused_claims`/`buyer_history`, and optional `reply_aware` behavior. S01–S03 naive simulator runs remain scripted integration checks. Keep `--policy current`, `--input-version current`, and `--adaptation current` as defaults. Later matched hosted evaluation should vary **one** optional flag at a time on identical dossiers/model/guards, alternate order, and report every case's mean and worst score, cost components, deal/must-have/fallback/timeout counts and failures. The existing hosted scores below predate this code and cannot validate it.

Latest historical input comparison: optional `--input-version offer_history` was paired with `current` under fixed adaptive/economics/model/dossier/guards. P01 means 56.81 versus 71.38 (two each), P03 85.08 versus 84.03 (two each), and first P02 hosted scores 6.57 versus 24.87 (one each). Ten valid autonomous deals, zero fallbacks, 24 verified claims. The new condition removed duplicate claim-card drops but was not promoted. New spend USD 0.18941835; lifetime USD 0.39213375 / 5. See [full report](INPUT_MEMORY_RESULTS.md). At that checkpoint, separate input mechanisms and complete-cost evaluation were next steps; they now have local code and tests, but no hosted measurement. Older totals below remain historical.

Economic-policy experiment completed: six matched runs, P01 two per condition and P03 one per condition. Economics scored 71.90 mean on P01 versus 49.05 current; P03 88.27 versus 73.07 current. All autonomous valid deals, zero fallbacks, 11 verified claims. New spend USD 0.07994095; lifetime USD 0.2027154. [Detailed results](ECONOMIC_POLICY_RESULTS.md), [findings and next experiments](IMPROVEMENT_PLAN.md). This compares an advisory feature plus policy instructions, not a pure prompt-variant test. Thirty-four local tests pass. The experimental policy remains opt-in pending broader evaluation.

Cross-case extension: one P03 renewal using unchanged adaptive/model/safeguards scored **85.15/100**, closed a valid deal autonomously with zero fallbacks, and had its one checked claim verified. Cost USD 0.00809605; cumulative ledger now USD 0.12277445. See [P03 result and replay](ADAPTIVE_P03_RESULT.md). No other prompt was run on P03, so do not interpret this as a prompt comparison or a gain relative to P01. Next candidate evaluation: matched adaptive versus evidence_first repeats on P03 before further prompt tuning. Earlier budget totals below describe their respective checkpoints.

Completed comparison: eight P01 runs, two per variant, all autonomous valid deals with zero fallbacks. Mean scores /100: adaptive 61.78, evidence_first 59.23, baseline 57.59, reciprocal_trades 26.63. All 18 checked claims were verified by the arena. Batch accounted USD 0.086029; lifetime ledger USD 0.1146784. See [full comparison and replays](PROMPT_COMPARISON.md). Adaptive is a provisional candidate; this is not proof of generalization beyond P01.

Autonomy/validation update: the first fixed-runner retry closed without intervention but walked away for 0 because the maximum of uncertain supplier-cost scenarios was treated as a hard rejection threshold. Using the central estimate for decisions and retaining the range as diagnostic information then produced an autonomous P01 deal, score 0.497015, no fallbacks (session 5ee1aa8b720a37b0). This fixes completion behavior, not necessarily negotiation quality.

The next comparison uses nighthunter/validation.py for deterministic claim cards and exact package checks. The LLM selects a tone, intent, approved claim IDs and commercial terms. Code composes the transmitted e-mail; arbitrary model prose is not transmitted. Cards validate quote part/supplier/case applicability, contract notice dates, recorded forecast changes, scorecard values and calculated index changes. Unknown cards and out-of-option or incomplete packages are rejected. Previously cited references are omitted. This is a restricted, auditable message format, not a general natural-language fact checker. Twenty-seven local tests pass before comparison.

The user authorized continuing these tests without routine confirmation, still within the initial USD 5 budget. Comparison code freezes the dossier and code/prompt fingerprints, runs variants sequentially with reverse order on alternate repeats, and records failures. Do not edit nighthunter/*.py or prompts/*.md during a running comparison. See the latest comparison report for outcomes; no variant is considered a winner before results exist.

Live update: the user authorized actual testing with configured gpt-5.6-luna. One P01 run scored 0.684485 at conservatively accounted USD 0.008149, but required assistant recovery to accept after a missing-default error. See [first live result](FIRST_LIVE_RESULT.md). The USD 5 ledger is artifacts/llm-budget.json; never reset it between comparisons. The prior offline-only status below describes the initial context milestone, not the current execution state.

Implemented a deterministic CaseContextBuilder, offline prompt preparation, and optional JSON baseline recording. No model calls were made. User authorized an initial **USD 5 total LLM testing budget, with model confirmation required before paid runs**. That authorization is not a recurring allowance per experiment. A budget meter and run limits must be implemented before those runs.

The builder preserves the exact case, required references, supplier/part identities, contracts and clauses. It reads base tables through read-only SQLite, links cost drivers to indices and forecasts to lines, resolves the documented supplier alias, merges an explicitly supplied Sunday release, and searches supplier correspondence. Case facts take precedence over package facts. Essential content exceeding the configured limit raises an error.

Optional records are balanced across categories: up to 12 rows per category and 13 recent observations per index series, plus required evidence. Whole documents are included or omitted; no mid-record slicing. The coverage report records found/included/omitted rows by table, missing refs, missing identities/documents and pending opening-quote checks. The default 60,000-character limit is **not a token limit**; measure actual model tokens and leave room for prompts, live state and output before inference. S01 currently fits in 57,535 characters, with 481 omitted evidence records and no unresolved refs or missing-document warnings. Zero unresolved refs does not mean omniscient or complete context.

Limitations: all base tables are scanned locally before filtering; suitable for this 33k-row dataset, but optimize SQL queries if preparation latency grows. Latest-first selection is a first-pass heuristic, not semantic relevance. Historical contracts are retained with dates, not declared automatically applicable. Global news without supplier links needs further retrieval work. Numeric claim validation, document relevance ranking, on-demand retrieval, live quote/state integration and actual model token counting remain to build. The naive buyer still ignores dossiers, so retrieval improvements do not yet imply higher deal scores.

## Reproduce from the repository root

```bash
# Build one dossier; change S01 to S02 or S03 as needed.
uv run --project vendor/negotiation-arena-kit/starter-kit --frozen --all-extras python -m nighthunter.context --case vendor/negotiation-arena-kit/starter-kit/arena_kit/sim_cases/S01.json --out artifacts/context/S01.json

# Prepare four prompts, all receiving identical dossier content. No inference.
uv run --project vendor/negotiation-arena-kit/starter-kit --frozen --all-extras python -m nighthunter.experiment --case vendor/negotiation-arena-kit/starter-kit/arena_kit/sim_cases/S01.json --out artifacts/prompts/S01.jsonl

# Save naive baseline deals, scores and elapsed time.
uv run --project vendor/negotiation-arena-kit/starter-kit --frozen --all-extras python scripts/test_naive.py --case all --out artifacts/baselines/naive.json

# Check context behavior without a server or keys.
uv run --project vendor/negotiation-arena-kit/starter-kit --frozen --all-extras python -m pytest tests -q
```

Artifacts are ignored by Git. Prompt preparation records SHA-256 hashes of both instructions and rendered context. The dossier CLI can also accept downloaded case JSON and --release PATH. Never include hidden outcomes or post-session supplier traces in a live input.

For a matched live comparison (paid model calls and one practice session per run):

```bash
uv run --project vendor/negotiation-arena-kit/starter-kit --frozen --all-extras python -m nighthunter.compare --dossier artifacts/live/20261010T134521779080Z/dossier.json --repeats 2
```

The example dossier is an existing P01 pre-session artifact on this machine. On another machine, first run P01 to generate a dossier and use that run's path. The command prepares a frozen copy under artifacts/comparisons/<timestamp>/ and runs four variants twice (eight sessions). Each run has a log, readable conversation and summary; manifest.json contains hashes, ordering and aggregated scores. The runner stops if code changes, the hosted case changes, or a process fails. Cases with zero scores, walkaways or fallbacks remain in the comparison.

## Prompt approaches to compare

| Variant | Hypothesis |
|---|---|
| baseline | Short, polite bargaining establishes a simple LLM reference. |
| evidence_first | One strong, relevant checked argument earns better concessions than generic requests. |
| reciprocal_trades | Trading payment, duration or other permitted terms improves total cost more than price haggling. |
| adaptive | Updating supplier-priority hypotheses and closing decisions improves varied-case performance. |

All variants share prompts/common.md: total-cost objective, must-haves, supported claims, binding structured terms, output schema and deadline/rule constraints. Change only the variant instruction when testing prompt effects. Later tests can separately vary dossier selection, output length, reasoning effort and scheduling, not all at once.

## Small timeline (working-time estimates, not guarantees)

| Stage | Estimate | Exit check |
|---|---|---|
| 1. Dossier and coverage | Completed initial version this turn | 10 local tests pass; required records survive budget pressure. |
| 2. Safe LLM adapter and live state | 1–2 hours | Valid JSON, exact current offers/default terms, claim checks, deterministic fallback, token/cost meter and timeout tests. Confirm model before any paid calls. |
| 3. First prompt smoke comparison | 30–60 minutes | Run all four prompts on the same small case set; inspect malformed outputs and latency. Use at most USD 1 of the USD 5 budget initially. |
| 4. Hosted paired comparisons | 1–2 hours, depends on supplier latency | Repeated paired runs across price, RFQ and strategic/quality cases; reserve at least USD 1 for confirmation. Hosted quota and access checked first. |
| 5. Best-candidate confirmation | 30–60 minutes | Compare finalists on cases excluded from prompt tuning; only then select a default. |

Stop or reduce scope if time, quota or credits are tighter. Do not consume the whole practice quota searching prompt wording. Model latency/rate limits and final-machine readiness may dominate the schedule.

## How we decide whether a change helps

For local-only comparisons, use the fixed public-case fixture in `tests/test_offers.py` and synthetic thread fixtures in `tests/test_session.py` with a mocked model response. Hold the case, supplier reply, quote defaults and requested action fixed; vary only one `input_version` or `adaptation` switch, and assert the exact outgoing term sheets, accepted ID, complete estimated cost, must-have result and fallback record. Run `vendor/negotiation-arena-kit/starter-kit/.venv/bin/python -m pytest tests/test_offers.py tests/test_session.py tests/test_validation.py -q`. These checks measure deterministic correctness, not supplier persuasion. The local S01–S03 naive simulator does not exercise the revised LiveAgent strategy.

For a later authorized hosted comparison, use one frozen dossier per case and the sequential `nighthunter.compare` runner. Compare `current` versus `unused_claims`, then `current` versus `buyer_history`, then the independent `current` versus `reply_aware` adaptation; keep the other flags fixed in each batch. Alternate order, repeat each condition, and preserve failed runs. The combined `offer_history` result is historical and should not be mixed with a batch using the new closing and evidence safeguards. Do not infer a winner from one P02 run or scripted local scores.

Record case ID, dataset/release revision, code revision/dirty state, model ID/settings, prompt/context hashes, repeat index, score, total cost/breakdown, deal/must-have outcome, rounds, timeouts, latency, actual token usage and USD cost. Include failures in the denominator and distinguish requested model action from executed fallback.

Use the same cases, context policy, model, settings, validators and closing behavior across variants; alternate run order. Start with representative cases, then give the two strongest candidates at least three repeats per case when budget permits. Compare mean paired score differences and per-case wins/losses, not only the single best score. Also report failure/timeout rates and cost. Small samples may be inconclusive; no statistical confidence claims without enough trials.

The local scripted simulator verifies interface and regression behavior, **not persuasion quality**. Hosted supplier repeats can vary. A candidate should improve mean normalized score without increasing broken must-haves or timeouts, and fit the budget/deadlines. Keep the previous working version if that evidence is absent. Hidden final cases must not be used for iterative tuning; final rules remain one attempt per case and frozen code.
