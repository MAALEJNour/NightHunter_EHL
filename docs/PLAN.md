# Discovery and implementation plan

**Latest status (10 October 2026, late):** milestones, measured results and next steps now live in
[MILESTONES.md](MILESTONES.md) (S1–S6, M3 RFQ, M4 final runner) and [LESSONS.md](LESSONS.md); the
full current picture for a new teammate is in [HANDOFF_FOR_TEAMMATE.md](HANDOFF_FOR_TEAMMATE.md).
Best measured configuration: `--policy packages --adaptation expert_prose`, `gpt-5.6-luna`, S5 mean
75.1 on nine single-supplier cases; RFQ P05 92.4 / 79.2. The sections below are the original
discovery plan and the Batch A3 record.

Original status: local naive baseline implemented and exercised, 10 October 2026. All advanced architecture and milestones below are proposed unless explicitly marked verified. Upstream commit: `1b5516bb95ef28e37f69aa446dc62168864bca53`.

Batch A3 measured update (10 October 2026): Codex reviewed Claude's A2 planner changes,
then fixed the close path so only the latest supplier reply's **primary** ID is accepted.
When a non-primary sheet is the best acceptable package and a buyer message remains,
the adapter sends its complete terms as one validated package and accepts a valid
primary on the next reply. At zero rounds, it accepts only a primary that beats the
buyer alternative. Approval intent now requires a source-linked profile threshold.
P11's A2 fallback came from an empty late-round plan without an accept recommendation;
the adapter now records deterministic `planner_exhausted` closure. Minimal P02/P18 422
regressions, **125 full-suite tests**, Ruff, syntax and offline real-dossier preflight
for all nine cases passed before A3.

A3 planned 27 sequential conditions (one current and two packages per supported
single-supplier case) with frozen dossiers/code and a $0.60 batch ceiling. It
**stopped after 5 runs** because `nighthunter/rfq.py` appeared in the shared worktree,
changing the code fingerprint before run 6. P01 current scored 55.66; packages
73.89 and 73.89, both 10.23 points below A2 packages. P02 current scored 50.03;
its first packages repeat scored 42.95, 7.08 below current. All five were valid deals,
zero fallbacks, no HTTP 422. The other 22 conditions were not attempted, so this is
not a complete policy comparison. Spend $0.08272970; lifetime ledger $0.75661670/$5;
observed practice quota 422→417. See [partial A3 results](BATCH_A3_RESULTS.md) and
[handoff](HANDOFF.md). The next hosted comparison requires a newly frozen batch and
shared-worktree coordination. Defaults remain `--policy current`, `--input-version current`,
`--adaptation current`. RFQ still lacks a validated hosted runner; Claude's pure RFQ
analysis module is not a completed integration.

Batch A2 measured update (10 October 2026): the later frozen code, including the P03
null-notice fix and Claude's internal should-cost planner estimate, was tested on all nine
supported single-supplier practice cases. Before hosted work, **91 local tests**, Ruff,
syntax checks and real-dossier/claim-card/round-0-plan checks for all nine passed.
Eighteen conditions ran sequentially with one frozen dossier per pair, alternating order,
`adaptive/current` versus `adaptive/packages`, unchanged model/settings and a $0.75 batch cap.
Fifteen ended in must-have-compliant deals; P02 packages and both P18 attempts failed with
`HTTP 422: not a standing offer in this session` when accepting a non-primary alternative ID.
P11 packages had one model fallback. The final two P18 errors triggered the stop rule.
On the seven fully completed pairs, current mean/worst was **58.75/22.61**, packages
**67.64/48.76**; the three failures are excluded there. A zero-filled nine-case view gives
50.35 versus 52.61 mean, worst zero for both; the zeros are not official arena scores.
Batch model spend was **$0.23153115**; lifetime ledger **$0.67388700/$5**. The observed
practice quota changed 468→432 while 18 sessions opened; the excess change is unexplained.
See [full A2 results](BATCH_A2_RESULTS.md), [handoff](HANDOFF.md), and ignored conversations.
One run per condition is diagnostic, not grounds for promoting packages. First repair and
locally test hosted standing-offer selection before any further paid experiment. Defaults
remain `--policy current`, `--input-version current`, `--adaptation current`; P05 RFQ
and parallel multi-supplier scheduling are still unsupported.

Batch A measured update (10 October 2026): the nine-case, 18-session sequential comparison
stopped after **four completed sessions and two P03 pre-session errors**, per the two-consecutive-
errors rule. One matched run on P01 scored current 62.80 versus packages 67.77; P02 scored current
34.57 versus packages 22.47. All four deals met must-haves with zero fallbacks. P02 packages'
lower price and longer payment were offset by €122,281.15 of evaluated supplier-health cost,
compared with €13,368.23 for current. Quota used: four sessions; model spend $0.05022210 of the
$0.75 batch cap (lifetime $0.44235585/$5). The P03 crash came from null notice days in a
Codex-owned claim-card check; fixed and locally validated **after** the stopped batch, with no
further hosted run within Batch A. That batch's final local suite had **89 passing tests**; touched-file Ruff
passes. See [Batch A results](BATCH_A_RESULTS.md), [handoff](HANDOFF.md) and ignored transcripts.
No policy promotion follows from one run per condition and an incomplete case set. Defaults stay
`--policy current`, `--input-version current`, `--adaptation current`; P05 RFQ remains unsupported.

10 October 2026 local-only update: `--policy packages` is wired as a separate, opt-in experiment. At startup it builds one source-linked supplier profile per supplier; at each decision it validates the current primary offer, computes the deterministic package plan, and sends the plan's exact validated terms. The model can select only rendered tone, intent and available checked claims. Model failure uses neutral rendering with the same planned packages; a final offer, last buyer round or planner acceptance recommendation invokes the existing safe close over all valid current sheets. Plans/profiles are logged in decisions and comparison manifests. Eight focused fake-model tests and the 79-test full local suite passed; touched-file Ruff (`E4,E7,E9,F`) and syntax checks passed. No hosted score exists. Defaults remain `--policy current`, `--input-version current`, `--adaptation current`. The planner's target is a request, not a supplier acceptance forecast; its first-sheet movement analysis, quote-default completion and approximate equal-cost menus need improvement or controlled hosted validation. See [the review and proposed matched batch](HANDOFF.md). RFQ and parallel wave support remain design only.

Latest local-only implementation: the live agent now evaluates all valid sheets in each active supplier's **latest** reply, prices completed terms using quote defaults and the published cost helper, enforces must-haves, and chooses the exact ID of the lowest central-estimated-cost current offer only when it beats the alternative. Older offer IDs are not reused. Claim cards now classify buyer leverage, seller support and uncertainty; should-cost stays internal. `unused_claims` and `buyer_history` are separately selectable inputs, while `reply_aware` is an independent optional adaptation mode driven only by current-thread supplier feedback. The existing defaults remain `--policy current`, `--input-version current`, `--adaptation current`; `economics` and `offer_history` remain experimental. Focused tests and the full local project suite passed (**49 tests**); S01–S03 naive simulator checks closed valid scripted deals with zero LLM calls. No OpenAI or Tacto calls, hosted sessions or new score measurements were made for this implementation. See [saved 28-run audit](SAVED_RUN_REVIEW.md), [local tests](LOCAL_TESTING.md) and [input comparison](INPUT_MEMORY_RESULTS.md). Multi-supplier RFQ scheduling, exact hosted acceptance of alternative IDs, deadlines/recovery and broader case coverage remain open.

Latest cross-case milestone: an optional offer-history input filtered previously used evidence and included prior buyer packages. Ten frozen hosted tests across P01, P03 and the first P02 pair all closed valid autonomous deals with no fallbacks. It eliminated duplicate-card drops but reduced P01 mean from 71.38 to 56.81 and P02's single score from 24.87 to 6.57; P03 rose slightly from 84.03 to 85.08. Keep the original input default. The low P02 scores and 14-day payment trade reveal a generalization gap. New spend USD 0.18941835; cumulative USD 0.39213375 / 5. See [INPUT_MEMORY_RESULTS.md](INPUT_MEMORY_RESULTS.md). The older budget totals below are historical checkpoints.

Latest performance milestone: implemented opt-in package search and within-session concession memory (`--policy economics`), with 34 passing local tests. Six frozen live tests: P01 economics mean 71.90 versus current 49.05 (two each); P03 economics 88.27 versus current 73.07 (one each). All valid autonomous deals, zero fallbacks, all 11 checked claims verified. Experiment USD 0.07994095; current cumulative ledger USD 0.2027154 of USD 5. See [ECONOMIC_POLICY_RESULTS.md](ECONOMIC_POLICY_RESULTS.md) and [IMPROVEMENT_PLAN.md](IMPROVEMENT_PLAN.md). Small-sample evidence only; default policy unchanged. Next: equivalent-value package menus, evidence-window retrieval, supplier-cost calibration and held-out case testing. No automatic cross-run training or model weight updates are implemented.

Latest cross-case check: unchanged adaptive completed one P03 renewal autonomously at 0.8515216195 (85.15/100), with a valid deal, zero fallbacks and one arena-verified forecast claim. Two buyer decisions, 67.170 seconds, conservative model cost USD 0.00809605. Current cumulative ledger: USD 0.12277445 of USD 5. See [ADAPTIVE_P03_RESULT.md](ADAPTIVE_P03_RESULT.md) for agreed terms, discussion, replay and limitations. P03 has not yet had a matched prompt comparison; this single run does not establish superiority. Earlier updates below retain their historical results and budget totals.

Completed milestones: autonomous P01 deal closure, structured evidence/term validation (27 local tests), and eight matched live prompt runs. All eight comparison runs closed valid deals without intervention/fallback; adaptive had the highest observed mean, 61.78/100, across two repeats. All 18 arena-evaluated claims were verified. See PROMPT_COMPARISON.md for all results, failures from preceding diagnostic runs, limitations and replay links. Initial USD 5 allowance has USD 0.1146784 conservatively accounted across all runs so far. Next: pre-score proposed packages and validate candidates across different case types; do not claim a general best prompt from P01 alone.

Live pilot update: nighthunter.live now connects dossier context and prompt variants to real OpenAI/Tacto practice calls, with a persistent conservative budget ledger and saved discussion/replay. First P01 score 0.684485, assisted recovery after a closing-cost default error, accounted USD 0.008149. The error is fixed and regression-tested; autonomous completion after the fix is not yet demonstrated on a second paid run. See FIRST_LIVE_RESULT.md. Full numerical claim validation, RFQ scheduling and paired prompt evaluation remain pending.

Context milestone: nighthunter/context.py now produces bounded dossiers with exact essentials, citable facts, contract/correspondence text, supplier alias handling and explicit coverage. Ten tests cover budget pressure, missing refs/identities, case fact precedence, units and supplemental evidence. Four prompt variants share common rules and identical context, with hashes for reproducibility. This is offline preparation, not measured LLM negotiation improvement. See EXPERIMENTS.md for commands, limitations, staged timeline and evaluation design. User approved USD 5 total initial LLM spend, with model confirmation before paid calls.

Baseline update: installed uv 0.13.0 and CPython 3.12.15; synced all 47 packages with --frozen --all-extras. scripts/test_naive.py runs the original NaiveAgent against a temporary localhost simulator and does not read .env. All three cases closed valid deals: S01 0.520602, S02 0.513154, S03 0.677574. These are scripted-simulator scores, not hosted performance. See LOCAL_TESTING.md for reproducible commands and verification. No changes to upstream files were needed.

Setup update: all 323 upstream tracked files are now in vendor/negotiation-arena-kit, with licenses retained and no upstream modifications. The root .env has blank credential fields and is ignored; the user confirms they have the team key and can enter it there. .env.example is safe to share. See docs/UPSTREAM.md and the root README for commands. Importing the source does not install dependencies or implement our agent.

## 1. Mission and success criteria

Build an autonomous buyer for Hollerau Pumpenwerke. Prepare from company records, negotiate structured packages by e-mail with hosted supplier bots, and explicitly accept a standing offer or walk away. Support price increases, renewals, RFQs, bundling, raw material, capacity and quality cases.

Verified scoring: `clip((C_open - C_deal) / (C_open - C_best), 0, 1)`. The API documents the near-zero-denominator special case. C_best is hidden until the result; do not depend on knowing it during play. A broken must-have scores zero. Walking away scores the case's alternative, or zero without one. A deal can be worse than walking away.

C includes committed purchase cost, uncovered need and fallback risk, payment timing, freight, late delivery, quality net of chargebacks, tooling, index movement/risk, and supplier-health charges for stabilise/secure_supply. Underbuying or shortening the contract does not erase the fixed need. Overbuying costs money. Only structured terms bind.

Final scoring: five waves, each mean case score times 100; sum up to 500. Ties use deals then rounds. Euros saved are a side metric. Practice uses best score per hosted case. The kit describes 19 practice case files but only 10 hosted practice cases; discover hosted status via the API.

## 2. Verified operational contract

| Constraint | Consequence |
|---|---|
| One team key; bring our own LLM | Arena credentials and model credentials are separate prerequisites. |
| 200 practice sessions per rolling 24 hours | Reserve quota for comparisons and final-machine rehearsal; check /v1/me. Sandbox/final do not consume practice quota. |
| 10 open sessions, 10 calls/second per key | Share the rate limiter across all case and supplier workers. Kit defaults to 9 calls/second. |
| 60 seconds after each supplier reply | Research before opening; bound inference, parsing and send time. Supplier reply time is excluded for that thread. |
| Default 10 buyer messages/thread | Read each case's actual round_limit. Questions consume limited interaction budget. |
| Supplier responses can take roughly a minute | Use the kit's 180-second HTTP timeout; schedule other RFQ threads independently. |
| Five final waves, eight minutes each unless extended | Read seconds_left. Reserve closing time, accounting for observed slow responses. |
| Up to three alternative term sheets/message | Each contains exactly all negotiable fields with permitted values; incorporate fixed and standard terms in evaluation. |
| At most three checked arguments/message | Choose relevant evidence rather than flood IDs; maximum 20 refs, 8,000 body characters, 64 KB request. |
| Only explicit acceptance closes a deal | Validate the current offer ID, including after retries or a supplier counteroffer. |

Use fresh X-Move-Id per logical POST and reuse it on retries. Handle 422 without consuming a round; distinguish 429 rate limits from exhausted quota and session limits. On 409, recover state rather than assume success or blindly replay a different move. Final retries must resume the existing session.

The final agent must not read event feeds, screen, leaderboard or results endpoints, including JSON/stream variants. Use case and own-session endpoints for state and deadlines. Replays/backoffice for final cases are available after the final, not as live strategy input.

## 3. Data inventory and evidence

Verified locally: 24 SQLite tables, 32,997 rows, 10,356 facts.json entries, 46 contract documents and 208 correspondence documents. The master contains 447 supplier records, including spend-only suppliers; detailed company material describes 46 suppliers and 60 parts.

Use SQLite for joins/aggregations, facts.json for checked values, and document text for commercial context. Relevant groups:

- Supplier strength: supplier_intel, spend, news, sourcing alternatives, supplier notes.
- Economics: should_cost, cost_drivers, index_series/index_values, price conditions, invoices and payment behavior.
- Negotiating history: negotiation_history, contracts/clauses, correspondence, RFQs and quotes.
- Operations: scorecards, quality_notifications, orders, receipts and forecasts.

Concrete example: P01's Brandlhuber letter requests +9.5%; a September owner visit records that the supplier held prices during 2022 and expects reciprocity. A generic cost challenge misses that relationship context. Test a specific exchange of economic value rather than assume appreciation alone earns a discount.

Data pitfalls: price_unit can be 1/100/1000; vendor 71999 aliases 70210; requested-date and confirmed-date OTD differ; partial receipts affect metrics; stale conditions and late payments exist; recent orders can be unreceived; indices have different publication lags. Should-cost is an estimate, not the hidden floor. Supplier-specific strategic estimates have about 5% error; generic estimates about 5–15%. Respect facts.json's claim values instead of citing an incompatible calculation.

Evidence records should contain ID, source, supplier/part, date/window, measured value, unit, applicability and whether already cited. Numerically verify statements in code. An index claim needs two months of the same series, at most 12 months apart and ending within the data's last 12 months. Track verified/contradicted/irrelevant/duplicate responses. Rival offers are usable evidence but disclose private competitive information.

Case files are served by the authenticated API; the repository does not contain the hosted practice case JSON. S01–S03 are local simulator fixtures. Sunday's supplemental data has new IDs and separate files; merge it into retrieval, not just the old SQLite query path. Hidden case facts must also be available to the evidence layer.

## 4. Proposed architecture

Start with a small Python application around the kit, with specialist responsibilities rather than an expensive multi-agent framework.

1. **Preparation:** load case and related records; build a compact dossier per supplier, including constraints, history, likely priorities, alternative and confidence-tagged hypotheses. Precompute reusable company research before final waves; case-specific work waits for case release.
2. **Economics:** calculate complete packages with upstream cost helpers; filter must-haves and invalid options; search bounded combinations and candidate prices. Estimate supplier economics with uncertainty for relationship-sensitive cases. Compare low/base/high estimates instead of treating unobserved costs as zero.
3. **Negotiator:** one bounded LLM decision per move by default. Choose a question, justified offer/trade or closing recommendation. Adapt to status, claims, documents and prior concessions. Use two or three meaningfully different packages when useful to learn supplier preferences.
4. **Validator:** check schema, units, numeric claims, allowed values, complete fields, available thread, current standing offer and alternative. Select a deterministic safe move when inference fails; do not inherit a blind aggressive fallback.
5. **Scheduler:** manage per-thread clocks and case/wave caps, parallel supplier requests when needed, shared rate limits, durable session/move state and one atomic terminal action per case. Read actual remaining wave time, including extensions.
6. **Evaluator:** save sanitized decisions, sources, terms, cost components, latencies and results; inspect practice replays; compare strategy versions and ablations.

Potential later specialist model calls: dossier researcher and strategy critic. Add only if measured gains justify latency/cost. Research can be parallelized outside the decision clock; sequential live debates are a poor default under 60 seconds. No agent framework or vector database is currently necessary: indexed SQL plus targeted document search is the first approach.

Example trades to test: faster payment for a cash-constrained supplier in exchange for price; duration/credible volume for an underutilized supplier; evidence-backed index clauses instead of blanket increases; quality commitments/chargebacks for quality cases; authorized competing quotes for RFQs. Never assume one tactic fits all category goals.

## 5. Reuse and implementation gaps

Reuse ArenaClient (HTTP, pacing, idempotent retries), DataPackage, PDF/XLSX readers, total_cost/must_haves_ok, the simulator and wave-runner behavior.

Verified source limitations to address or test:

- LLMAgent prepares mostly case-referenced facts, truncates documents/history and checks ID existence rather than claim truth.
- Its prepare() runs on first decide(), after session opening; heavy research needs an earlier explicit phase.
- Stock accept/closing_move cost calls omit supplier estimates and thus the relationship charge. All decision paths, including deadline fallback, need consistent estimated economics.
- Stock play() is synchronous per case; waiting on one RFQ supplier may expose another thread to timeout. Measure with delayed-response fixtures and implement coordinated scheduling if confirmed.
- The CLI accepts only naive/llm agent names. Our agent needs our own entry point or an explicit upstream integration change, not a fictional custom --agent flag.
- DataPackage includes Sunday facts and document lookup, but its SQLite database remains the base package. Supplemental retrieval needs explicit coverage.

## 6. Tools and environment

| Tool | Purpose / status |
|---|---|
| Python 3.12 + uv | Installed uv 0.13.0 and managed Python 3.12.15. The separate kit .venv meets >=3.12,<3.13 without changing default Python. |
| arena-kit pinned to inspected revision | Full snapshot now vendored under vendor/negotiation-arena-kit; includes its uv.lock. API contract, baseline, simulation, document and cost utilities. |
| SQLite + standard Python | Structured data, deterministic arithmetic and retrieval. |
| httpx, pypdf, openpyxl | Already declared by upstream for HTTP and supplier documents. |
| pytest + Ruff | Installed; local baseline and upstream checks exercised. Results recorded in LOCAL_TESTING.md. |
| LLM access | gpt-5.6-luna and the USD 5 cumulative ledger were used through partial Batch A3; latest accounted total is USD 0.75661670. See A3 above for the measured partial batch. |
| Arena team key | Authenticated practice runs covered the nine supported single-supplier cases in Batch A2. The private key stays in ignored `.env`. |
| Optional data MCP | Six read-only tools: list_tables, query, lookup, list_ids, read_document, get_case. Useful for exploration; direct Python is simpler for runtime. Hosted cases still come from API. |
| Git + Entire | Development provenance; separate from competition scoring. Previously verified commit/checkpoint upload. |

These are upstream starter-kit commands for a separately authorized run; only the local checks in LOCAL_TESTING.md were executed for the latest changes:

```bash
uv sync --all-extras
uv run arena me
uv run arena cases --set practice
uv run arena data
uv run pytest
uv run ruff check .
```

Verify CLI help before executing commands. Point ARENA_DATA at the actual extracted package. Upstream's `arena play case:P01` opens a quota-consuming session. The previously configured model is not evidence that the latest code performs better; test changes in a future matched batch.

## 7. Milestones and acceptance gates

1. **Environment and baseline:** pin dependencies/data, safe environment template, working simulator and baseline results. Gate: install reproducibly, parse documents and complete all three simulator scenarios without real keys.
2. **Evidence engine:** build dossiers and checked claims with source references. Gate: tests for aliases, price units, scorecard semantics, index windows, Sunday/case-only facts and unsupported claims.
3. **Decision engine:** candidate packages, supplier estimates, negotiation policy and validators. Gate: must-have rejection, complete/defaulted terms, alternative comparison, uncertain relationship cost, stale offers and malformed/time-limited model outputs.
4. **Reliable execution:** per-thread scheduling, durable state, shared rate limiter and closing fallback. Gate: delayed multi-supplier replies, retries, 409/422/429, restart without duplicate moves, single closure and wave extensions. Proposed normal decision target <30 seconds, leaving transmission/fallback margin; measure p95 and worst case.
5. **Hosted experiments:** baseline versus improved agent across case types and supplier styles. Start with one baseline run per hosted case, then targeted paired repeats within remaining quota. Record score, C, deal rate, must-have violations, timeouts, latency, model spend and relationship cost. Test retrieval/optimization/adaptive-trades separately. Preserve quota for rehearsal; do not optimize only the easiest case.
6. **Freeze readiness:** Sunday data refresh, final-machine practice run, five-wave rehearsal, frozen commit, autonomous runner and clean runbook. Gate: no human prompts, no prohibited endpoint calls, sufficient credits and verified recovery.
7. **Submission:** accessible solution repo, exact final commit hash, setup/run README, approach description and slides. Prepare one explainable replay for the five-minute pitch and two-minute questions.

## 8. Schedule, unknowns and next step

Published event schedule: Sunday 08:00 supplemental data, 09:00 preflight, 12:00 code/slides freeze and final start; top-ten pitches from 13:00. API dates place the release on 11 October 2026 at 06:00 UTC (08:00 Berlin). Confirm organizer updates; do not treat placeholders in the brief as settled rules.

Open items:

- Intended final machine/network, remaining hosted practice quota and provider credits at freeze time.
- The hosted API rejected non-primary alternative IDs in P02/P18 with HTTP 422 despite those IDs appearing in the latest supplier message. Determine its standing-offer rule locally and correct closing before further hosted sessions. Multi-supplier RFQ scheduling remains open.
- Official clarification of presentation's price-only/single-supplier claims if intended as a rule change.
- Jury weighting remains a placeholder in upstream; ask the organizers when relevant.
- Per-thread timing during other suppliers' in-flight replies needs contract testing and possibly organizer clarification.
- Final upstream/data changes: review diffs deliberately; pin the implementation used at freeze.

Next step: coordinate a stable shared worktree, review the new RFQ module separately,
and decide whether to approve a fresh 27-condition single-supplier batch for the 22 A3
conditions left unattempted. Do not merge those later measurements into A3's frozen
five-run fingerprint. Future input experiments should isolate `unused_claims` from
`buyer_history` on identical dossiers and model settings, recording complete cost,
failures and fallbacks. Multi-supplier RFQs still need a hosted runner, scheduler,
deadline handling and recovery; the current live runner rejects them.
