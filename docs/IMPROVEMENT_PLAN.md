# Improving negotiation performance

Update after the offer-history experiment: the combined input removed duplicate-card drops, but P01 and the first P02 pair scored worse; P03 improved only slightly. Keep the original input as default. P02 particularly showed that EUR 369.15 with 14-day payment can cost more than EUR 370.27 with 45-day payment. See [ten-run cross-case report](INPUT_MEMORY_RESULTS.md). The latest local-only code now prices all latest-reply supplier alternatives and separates unused-card filtering, buyer history and reply-aware adaptation into optional controls. Those changes have no hosted score. Inspect the [28-run index](SAVED_RUN_REVIEW.md) before proposing another experiment.

## What the scores mean

P01 adaptive previously averaged 61.78/100 over two runs; P03 scored 85.15 in one run. These are normalized savings against each case's hidden best package, not deal success rates. All three closed valid deals. Near 100 requires extracting almost all available total-cost improvement; a bigger context window or a stronger-sounding prompt does not establish that the supplier will accept the requested package. The hidden benchmark is for post-run evaluation, never a live input.

## Findings from our code and saved runs

The review of saved discussions found directly actionable input issues: model-selected citations were silently dropped when repeated, and a P01 supplier expressly objected when an unchanged buyer package became cheaper. P03 notes and actual replies disclosed a price freeze, yet the economics policy kept proposing lower prices. See the [28-transcript index](SAVED_RUN_REVIEW.md). The combined offer-history version has already been tested and was not promoted; separate ablations remain untested against hosted suppliers.

1. **Counteroffers lacked calculated comparisons.** The original LiveAgent supplies costs for the standing offer, but asks the model to invent its own packages. A P01 reciprocal-trades run accepted EUR 137.50 with 14-day payment and incurred EUR 11,455.28 in buyer financing cost. The concession did not compensate for the payment trade.
2. **True evidence can support the seller.** Adaptive cited an increasing PPI-C241 index; the supplier explicitly replied that it confirmed its cost case. All claims being verified is a reliability metric, not proof of persuasion.
3. **Retrieval can omit the useful comparison window.** Dossiers are capped at 40,000 JSON characters in live runs. P01 omitted 634 records; P03 omitted 536. Recent recorded model inputs were about 14,500–15,700 tokens, without evidence of overflow. The P01 index card used July–August 2026, even though the full public data includes a twelve-month energy decline: PPI-D351 137.0 in August 2025 to 131.9 in August 2026 (-3.72%). The supplier's labor and material indices increased over their respective twelve-month windows. Any argument must state its own window and cost share; an energy decline does not prove total costs declined.
4. **Supplier-specific notes are already available but weakly operationalized.** P01 notes describe outdated cost spreadsheets, a preference for faster payment and remembered help during 2022. P03 notes describe pricing-committee approval above 2%, a price freeze and flexibility on other terms. These are contextual clues, not exact hidden reservation prices or guarantees of concessions.
5. **Supplier-health estimates are uncertain.** We currently assume 12% supplier financing and a central should-cost estimate. The +/-5% scenarios can change package rankings. Optimizing that estimate too confidently may optimize the wrong objective; a disclosed cost breakdown could improve it.
6. **Communication is deliberately restricted.** The model chooses tone, intent, fact cards and terms; code writes the message. This prevents invented numeric claims but cannot yet express all relationship acknowledgments or nuanced conditional trades. Expanding safe message choices is a separate experiment.

## Implemented experimental improvement

`nighthunter/economics.py` enumerates up to 512 permitted non-price combinations and a price grid from 90% to 100% of the standing price in 0.25% increments. It reuses upstream total-cost arithmetic, respects must-haves, calculates financing/coverage/quality/estimated relationship effects, and returns at most eight distinct payment/date/security packages. Each candidate includes estimated total cost, cost components, cost at the current unit price and uncertainty scenarios. This is a bounded request menu, not a global optimizer or acceptance forecast.

The advisor also rebuilds a within-session memory from supplier offers: concessions in estimated total cost, stagnation, status and messages left. It excludes buyer anchors from observed supplier concessions. It reads only the supplied dossier and the current thread, not practice results, hidden floors or final endpoints.

Enable it with `--variant adaptive --policy economics`. The default remains `--policy current`. The additional instructions are in `prompts/economics_policy.md`; `prompts/common.md` and the four original variant files are unchanged. The new policy encourages calculated trades, relevant evidence, approval requests when appropriate and measured continuation while the supplier remains open. Existing evidence validation, acceptance checks and budget limits remain in force.

This changes both the advisory input and its policy instructions, so the comparison evaluates the combined feature, not wording alone. The same model, case dossier, common rules and safeguards are frozen within a batch. Changes to retrieval, model or message rendering need separate experiments.

Validation before live comparison: 34 local tests passed, including financing trade-offs, supplier/part estimate matching, supplier-only concession history, must-haves, bounded search, supplier-health penalties and independence from injected hidden-result fields. Targeted Python/import lint passes. A broader inherited Ruff ruleset also reports existing style warnings in earlier files; it was not made a new project-wide gate. Candidate construction on saved P01/P03 openings took roughly 6–18 ms locally.

## Examples worth building on

| Source | What to reuse |
|---|---|
| [Starter README: Haggler example](../vendor/negotiation-arena-kit/starter-kit/README.md) | `decide(case, threads)`, cost the counteroffer, ask for a breakdown, explicitly accept. It is a demonstration, not a competitive strategy. |
| [NaiveAgent](../vendor/negotiation-arena-kit/starter-kit/arena_kit/agents/naive.py) | Simple anchor, split the gap, close on final/agreed; regression baseline. |
| [LLMAgent](../vendor/negotiation-arena-kit/starter-kit/arena_kit/agents/llm.py) | Current offers, attached document text, model adapter and closing guard. |
| [Cost helpers](../vendor/negotiation-arena-kit/starter-kit/arena_kit/cost.py) | Total cost, supplier cash value, supplier-health penalty and fixed-horizon coverage. |
| [Document readers](../vendor/negotiation-arena-kit/starter-kit/arena_kit/docs.py) | Quote defaults and PDF/XLSX text. XLSX formulas are returned as text, not evaluated. |
| [API evidence and document rules](../vendor/negotiation-arena-kit/brief/api.md) | Applicable claim windows, verified versus persuasive evidence, approval and breakdown requests. |

There is no winning trained agent or hosted supplier implementation in this snapshot. Local simulator scores test the API contract, not realistic negotiation skill.

## How the agent should learn

**Within a negotiation (initial version implemented):** read replies, preserve exact standing offers and constraints, update concession history, compare packages and adapt the next request. A stalled trajectory is an observation, not proof of a hard floor. Structured memory makes the information easier to use; it does not train model weights.

**Between practice runs (controlled development loop):** save outcomes and traces → identify a repeated failure → write one general hypothesis → change one feature → run paired comparisons → keep or reject the change. Record failures, not only best leaderboard scores. Preserve case families not used for tuning. Do not put previous `c_best`, hidden outcome values or post-session traces into the live negotiator's context. We have not implemented automatic prompt rewriting, weight training or a cross-run learning database.

## Next experiments, in order

1. The first economic-policy comparison is complete: P01 71.90 mean versus 49.05 current, P03 88.27 versus 73.07 current, with six autonomous valid deals and no fallbacks. See [results](ECONOMIC_POLICY_RESULTS.md). Test equivalent-value package alternatives next: P03's outgoing menu included the standing package, which the supplier selected without further improvement. Repeat across more cases before promoting the policy.
2. Improve evidence retrieval: preserve explicitly selected twelve-month index pairs, cost-driver shares and relevant supplier notes before optional transaction history. Generate cards with consistent windows and source IDs. Compare with the original dossier policy separately.
3. Model supplier priorities explicitly: source-linked cash/approval/relationship hypotheses, uncertainty and latest observations. Ask for a breakdown when useful, parse disclosed values deterministically and retain their provenance. Do not infer undisclosed actual cost from an estimate.
4. Test richer validated messages: acknowledgments grounded in notes, conditional payment-for-price trades and approval escalation. Keep numerical statements templated and claims checked.
5. Evaluate adaptive and evidence-first across more case types with repeated paired runs. Add RFQ scheduling and final-wave deadlines before claiming broad readiness. Only then test a different model on difficult decisions as a separate budgeted comparison.

Retain the USD 5 cumulative ledger and preserve practice quota. A failed hypothesis is useful evidence; do not promote it because its architecture sounds stronger. No near-100 result is promised.
