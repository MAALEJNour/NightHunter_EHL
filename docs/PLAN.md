# Discovery and implementation plan

Status: planning plus authorized source import/environment template, 10 October 2026. All architecture and milestones below are proposed unless explicitly marked verified. Upstream commit: `1b5516bb95ef28e37f69aa446dc62168864bca53`.

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
| Python 3.12 + uv | Required by kit (>=3.12,<3.13). Current default python3 is 3.14.0; uv was not found on PATH. Install a compatible environment during implementation. |
| arena-kit pinned to inspected revision | Full snapshot now vendored under vendor/negotiation-arena-kit; includes its uv.lock. API contract, baseline, simulation, document and cost utilities. |
| SQLite + standard Python | Structured data, deterministic arithmetic and retrieval. |
| httpx, pypdf, openpyxl | Already declared by upstream for HTTP and supplier documents. |
| pytest + Ruff | Contract/decision tests and lint. No tests run yet; only source and data inspection. |
| LLM access | Provider/model and budget pending; benchmark latency and structured output before choosing. No paid calls made. |
| Arena team key | User confirms possession; enter it privately in root .env. Authentication has not yet been tested. |
| Optional data MCP | Six read-only tools: list_tables, query, lookup, list_ids, read_document, get_case. Useful for exploration; direct Python is simpler for runtime. Hosted cases still come from API. |
| Git + Entire | Development provenance; separate from competition scoring. Previously verified commit/checkpoint upload. |

Baseline commands below belong in upstream starter-kit after environment/key setup; they have not been executed for this planning task:

```bash
uv sync --all-extras
uv run arena me
uv run arena cases --set practice
uv run arena data
uv run pytest
uv run ruff check .
```

Verify CLI help before executing commands. Point ARENA_DATA at the actual extracted package. Upstream's `arena play case:P01` opens a quota-consuming session; do not run casually during discovery. Model selection remains open; the example environment's model name is not a recommendation or verified available model.

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

- Team key authentication, chosen LLM access, credits/rate limits and intended final machine/network.
- Actual hosted case files, live service behavior and quota: not queried without team configuration.
- Official clarification of presentation's price-only/single-supplier claims if intended as a rule change.
- Jury weighting remains a placeholder in upstream; ask the organizers when relevant.
- Per-thread timing during other suppliers' in-flight replies needs contract testing and possibly organizer clarification.
- Final upstream/data changes: review diffs deliberately; pin the implementation used at freeze.

Next step after the user's instruction to implement: establish Python 3.12/uv using the vendored kit and lockfile, and build the local simulator baseline plus evidence layer. No negotiated outcome or model performance is claimed yet.
