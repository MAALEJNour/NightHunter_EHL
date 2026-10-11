# Codex findings — offline research, 11 October 2026

**Test forecast evidence first, then port the binding-volume answer into RFQs.** There are also narrow menu experiments worth screening. I found no evidence that promises the required +2.9 in the ten-case **best-score mean**. Recovering a previously achieved score improves repeatability, not that mean. The estimates below deliberately distinguish these outcomes.

No hosted sessions, LLM calls, credentials, commits or pushes were used. No agent source or prompts were edited. Analysis scripts and intermediate outputs are in `/tmp/codex_analysis/`; this report is the only repository file written. Claude owns implementation and live testing; introduce each change in a separately identified frozen batch.

## Evidence scope and ranking

A deduplicated snapshot from `twin.dataset.sessions()` contains **322 sessions: 218 ours, 104 teammate; 1,234 post-opening supplier trace entries across ten practice cases**. Case counts: P01 50, P02 37, P03 32, P04 24, P05 24, P07 30, P08 39, P10 27, P11 30, P18 29. Counts include failures and repeated suppliers, not independent statistical samples. The snapshot is `/tmp/codex_analysis/sessions.json`; new sessions arriving during research are excluded. Two additional P05 RFQ conversations/summary files were inspected separately because the trace loader does not include runs lacking `state.json`.

Sources read: pinned brief/API/cost implementation, required project documentation and lessons, planner, live adapter, validation, profiles, prose, RFQ decisions/runner and final runner. All trace reasons and score denominators below are **offline evidence only**. Runtime proposals use public case/dossier facts and the current session, with no case/supplier IDs in decision logic.

Ranking uses a rough decision prior, **not a fitted treatment effect**. “Upside” is a conditional scenario; zero gain or harm remains possible. Priority weights are subjective confidence discounts applied to a midpoint of the indicated best-mean upside, useful only for deciding which session to spend first. Do not add the rows: effects overlap.

| Rank | Proposed opt-in | Conditional best-mean upside /100 | Confidence weight; priority value | Main limitation |
|---|---|---:|---:|---|
| 1 | `forecast_reply` | 0–1.0 | 0.6; 0.30 | Positive supplier reaction is not causal score evidence |
| 2 | `rfq_volume_answer` | 0–0.36 to reach the stated P05 target | 0.6; 0.11 | Best P05 already 92.38; larger gains would mostly restore repeatability |
| 3 | `need_aligned_lead` | 0–0.4 across P05/P10 | 0.4; 0.08 | Free to us is proven; supplier price response is untested |
| 4 | `payment_date_diversity` | 0–0.4 on P01 | 0.3; 0.06 | Existing hypothesis narrowed, not a newly proven strategy |
| 5 | `retained_quality_trade` | No demonstrated best-score increment | 0.25; 0 | Potentially restores +8.36 P11 / +0.84 mean; strong reverse-causality concern |

The numerical upside ranges are planning assumptions, not confidence intervals. In particular, the data do **not** identify a positive expected gain for any untested variant. Rank 1 assumes a modest extra concession on two or three responsive cases; ranks 3–4 assume a few case points from exposing a currently omitted trade. Rank 5 is a reliability experiment, not a supported path beyond 79.4 on P11.

## 1. Actually select the checked forecast when asked for volume evidence

**Finding.** Forecast cards already exist but `claim_cards()` labels them `neutral_unknown`. `LiveAgent.forced_claims()` lists `forecast:` in its priority order yet only auto-selects `buyer_leverage` cards. Thus adding the prefix to the priority list alone will do nothing. All nine single-supplier cases' latest saved rehearsal dossiers have forecast cards; none of those nine corresponding traces uses a `volume_change` claim. Eight dossiers are from `artifacts/final_runs/20261011T073532Z/`; P07's latest available snapshot is `20261011T073038Z/case_P07/`.

The historical claim/reaction audit is more encouraging than the index audit:

| Case | Forecast claim uses | Explicit “took it into account” | Explicit “does not change our calculation” |
|---|---:|---:|---:|
| P01 | 8 | 7 | 0 |
| P02 | 10 | 10 | 0 |
| P03 | 10 | 9 | 0 |
| P04 | 2 | 0 | 2 |
| P07 | 1 | 1 | 0 |
| P10 | 4 | 0 | 3 |
| P11 | 2 | 2 | 0 |
| P18 | 1 | 1 | 0 |
| **Total** | **38** | **30** | **5** |

The other three lack either explicit reaction. Multiple claims can occur in the same message; these words do not isolate the forecast's price effect. P08 has **zero** observed forecast uses. Counts are from interpreted claim types and supplier reasons, not keyword searches of buyer prose. Every relevant reply has at least one verified claim; that is not a claim-by-claim validation statistic.

Exact examples:

- `artifacts/strategies/S1_20261010T181746Z/P03/packages_1/state.json`, supplier r2: **“Nevertheless, we have factored in your verified demand forecast change to adjust our offer.”** The accompanying check says it holds and was taken into account; terms €432.90 / 90 days / 36 months / 4580 annually.
- Same batch, `P18/current_1/state.json`, r1: **“We checked the volume change data you cited; it holds and we took it into account.”** Claim `fc:370010@2026-09`, +1.9%; offer €5.60 / 60 days / 24 months / indexed db0. This is an old, lower-scoring strategy, not evidence it beats today's planner.
- Same batch, `P07/current_1/state.json`, r1: the same positive check for **+15.3%, `fc:360011@2026-09`**. This is one component's demand, not 15.3% growth of the whole bundle.
- `artifacts/final_runs/20261011T073532Z/case_P03/state.json`, r2: **“Which figures is that based on? Please send us the data.”** Its dossier contains the unused +10.3% forecast card.

**Mechanism.** Supply the checked evidence behind planning/volume language, instead of repeating “planning certainty.” A forecast is evidence of demand, **not a new binding order**. Pair it with an accurately rendered statement of the existing term-sheet/fixed volume only when needed.

**Exact change.** In `nighthunter/live.py`, `forced_claims()`/`decide_packages()`, add off-by-default `forecast_reply`: on a current request for forecasts, volume support or the basis of a preceding volume statement, reserve one of the three claim slots for a fresh, relevant positive forecast card even if neutral. Do not globally relabel every positive forecast as leverage. Preserve notice and quality priority. For a generic “which figures?” question, require a preceding volume/planning statement before classifying it as a forecast request. Use the latest included forecast and existing checked percentage text; identify the component explicitly for bundles. After a supplier says the fact does not matter, do not spend more slots on older snapshots of the same argument.

**Gain/test.** Screening assumptions: P07 +0–3, P18 +0–4, P11 +0–3; P03 is a useful transfer check but only has ~7 points to the supplied target. These are hoped-for extra-step magnitudes, not measurements. First run one variant each on P07/P18/P11, then P03 if it helps. Keep the planner unchanged. Require verified evidence, no contradictions, and either an additional comparable-term concession or a better final total cost; friendly acknowledgment alone is not success. P02's 10 positive reactions do not remove its indexed health/risk ceiling; do not prioritize it. P04/P10's negative evidence argues against forcing forecasts universally.

**Hidden cases/guards.** Generalizes by a supplier's request and current public forecast. No forecasts outside the case's parts, no inference of a binding increase, no new purchases, no extra model call. Keep the three-check cap and existing final-offer close.

## 2. Port the binding-volume response into RFQ workers; state fixed scope before it becomes a dispute

**Finding.** `RfqNegotiator.worker()` passes only the rival-price sentence to `compose()`. It never invokes `LiveAgent.volume_answer()` or an equivalent. Since P05 volume and contract length are fixed rather than negotiable, `describe_terms()` omits both. The prose then tells the supplier to look at volume “in our options,” which is absent from the visible options.

Evidence includes **83 exact “Which volume can you commit to?” reasons in 15 of 24 P05 trace sessions**. Those counts include teammate runs; the code defect is independently visible in our two RFQ conversations:

- `artifacts/rfq/P05_20261010T203454Z/conversation.json`, bidder `sup:70250`, first reply (`offer:70250-2`): **“How many pieces are we talking about?”** Our second buyer message answers **“please consider the volume and terms in our options”**, followed only by price/payment/lead time. Its second reply/final (`offer:70250-3`, €27.00) says **“But you still didn't tell me the volume, how many pieces are we actually talking about?”** This is the **92.38** run, so even the best leaves this question unresolved.
- `artifacts/final_runs/20261011T072128Z/case_P05/state.json`, same bidder r3: **“Send over the volume figures so we can get the machines running.”** At r4: **“I am holding my offer at €… for … days payment and … days lead time until you send the volume figures.”** Final deal €28.00, score **82.05**.

**Mechanism/change.** Add `rfq_volume_answer=False` in `scripts/rfq_live.py`, `worker()`, backed by a shared deterministic formatter in `nighthunter/prose.py`. Render the actual fixed or per-option annual volume, units and duration. For P05 that is **4200 per year, 24 months**; derive it from the case, never an ID rule. State it once in the opening RFQ and again if asked. Expand the request detector to cover “how many pieces,” “call-off figures” and “underlying forecasts.” Keep forecast evidence separate from commitment wording. For raw materials use case/dossier units rather than blindly saying pieces. Do not say “full requirement” unless coverage actually matches the fixed need; do not fabricate a delivery schedule.

**Gain/test.** The supplied target 96 versus 92.38 leaves **3.62 case points / 0.362 ten-case mean** to target. Reproducing €27 instead of €28 would recover **10.33 P05 points** at the saved final terms, but would not raise the best. Run two P05 sessions because prose/asynchronous paths vary. Success: no repeated unanswered volume question, all bidder deadlines met, and price below €27 at equivalent total-cost terms for a best-score improvement; separately record repeatability gains. Do not keep negotiating a final offer to obtain an answer.

**Hidden cases/guards.** This uses binding case terms for any RFQ and adds no model latency or endpoint access. Port the same exact-scope sentence into single-supplier opening messages only as a separate variant; S13 already tested reactive volume answers there, so that is not itself a new discovery.

## 3. Stop asking for unpriced delivery acceleration when selecting tied menus

**Finding.** `supplier_value()` has no lead-time/overtime charge. In `plan_packages.build()`, options are deduplicated by `(price, seller_value)`; tied lead times can collapse to the first enumerated option. For P05, **28 and 35 days have identical buyer cost** because need is 35. For P10, **35 and 42 are identical** because need is 42. This equality was checked with the published cost function on saved complete deals. No health term changes when only lead time changes under the current estimate.

- Both `artifacts/rfq/P05_20261010T203454Z/conversation.json` and `P05_20261010T203823Z/conversation.json` open to `sup:70250` with 28-day packages plus a 42-day trade, but no 35-day package. Both finish at 28 days.
- `artifacts/strategies/S5_20261010T204627Z/P10/luna_1/decisions.json`, first plan, similarly offers 35 and 56 days, omitting the equally cheap 42-day service level.
- **32 supplier trace turns in 17 P05 sessions** mention overtime. `~/Downloads/replays/practice-20261010T152823Z/case_P05__fa7f23eed69e341e.json`, r3: **“To squeeze the Lieferzeit down to … days, we have to run weekend shifts and overtime, which costs extra.”** These reasons concern multiple bidders; they do not prove that the eventual winning bidder prices 28 versus 35 differently.

**Mechanism/change.** Add `need_aligned_lead=False` in `nighthunter/packages.py`, `plan_packages()`/`build()`: within truly equal buyer-cost/seller-value groups that differ only in lead time, prefer the **largest allowed lead time no greater than `buyer.need_lead_time_days`** and satisfying must-haves. Apply this before duplicate elimination. Preserve all other ranking keys and price/concession logic. Start with opening menus only so it cannot reverse a later granted term or disturb per-mix monotonicity. This is a narrow tie-break, not an invented monetary overtime estimate.

**Gain/test.** Planning hypothesis: P05 +0–3, P10 +0–1 points (0–0.4 mean combined); possibly zero because price may dominate. One P10 and two P05 sessions, separate from the volume variant. Require identical opening cost targets, correct new lead options, and lower final cost. In particular, P10's 56-day discount can still be worthwhile; do not remove that priced trade.

**Hidden cases/guards.** Applies when a faster-than-needed term has no scored benefit. Recheck exact costs and must-haves, including case-specific delivery constraints. Never lengthen beyond buyer need under this flag. No model/clock overhead of consequence.

## 4. Narrow the existing “our terms” option to payment/date diversity

**Finding.** This builds on L23 rather than claiming its twin result as new evidence. Replaying current planner logic over **nine S5 histories** shows why a global `OUR_TERMS_OPTION=True` is unsuitable: it changes substantive menu membership in P01, P07 and P11, while several other differences are just order changes. On P11 it introduces EUR500 chargebacks, contrary to the measured L19 risk. On P01 it exposes a useful omitted trade.

`artifacts/strategies/S5_20261010T204627Z/P01/luna_1/decisions.json`, r1, has three **14-day** options at different effective dates. The scratch reconstruction adds an April/90-day option at €135.59 at the same target, alongside April/14 at €131.81. After the first saved reply it would expose April/90 at €138.70, whereas the normal menu offers April with 14/30/45 days. These are counterfactual **asks**, not supplier offers or predicted deals.

The same S5 run actually closes April/**14 days** at €136.60; there are **no accepted 90-day P01 deals among the 50 snapshot sessions**. Longer-payment acceptance is therefore unproven. There is narrower evidence that payment is tradable: `artifacts/strategies/S2_20261010T185440Z/P01/packages_1/state.json`, r3, offers April/30 days at €137.10 as an alternative, with **“Alternatively, with Zahlungsziel … days net: €… per unit.”** Start by exposing a genuine payment trade; do not assume 90 days is obtainable.

**Mechanism/change.** Add `payment_date_diversity=False` in `packages.plan_packages.build()`. Preserve two seller-ranked packages and reserve only the third for a cost-valid payment/effective-date alternative when these are negotiable and the menu lacks it. Hold other fields, especially quality/chargebacks, constant. Do not turn on the existing global flag. Recheck actual cost after price cap/rounding/per-mix floors; do not let the reserved package exceed the target except the existing separately logged health margin.

**Gain/test.** P01 +0–4 points is a planning hypothesis, ~0–0.4 mean; no hosted evidence yet beyond L23. One P01 screening run and a repeat if it improves, with P02 as a health-sensitive transfer check only after a gain. Compare against current paired behavior and **91.6 team best** separately. Earlier access to long payment might instead anchor a higher sticky price. Success requires improved final total cost, not merely a longer payment term.

**Hidden cases/guards.** Gate by negotiable fields/menu coverage, not cash-pressure supplier identity. Preserve health estimates, final-offer closure and all quality safeguards. The inspected S5 replay produced no large target overshoot outside the configured threshold; an overshoot bug is not established by this audit.

## 5. Low-confidence P11 experiment: retain a previously quoted quality trade as a new counter

**Finding.** In ten recent P11 sessions (S3 onward and rehearsal traces) with a first follow-up after the supplier reached €45.50/300PPM/zero chargeback:

- **2/2** with an 800PPM/zero-chargeback buyer option obtained €45.00 next: S4 `low_1` and S5 `luna_1`, r4.
- **0/8** without that option moved below €45.50 next: S3 `fixes_1`, `ambitious_1`; S4 `medium_1`; S11/S13 `luna_1`; three saved rehearsals.

Paths share `artifacts/strategies/` with batch folders `S3_20261010T194644Z`, `S4_20261010T201615Z`, `S5_20261010T204627Z`, `S11_20261010T221955Z`, `S13_20261010T225236Z`; rehearsals are `artifacts/final_runs/{20261011T072128Z,20261011T073038Z,20261011T073532Z}/case_P11/state.json`.

**Critical confound:** the successful suppliers already repeated an 800PPM alternative in r3; S13 dropped it. `_thread()` therefore chose 800 in the successful histories but 300 in S13, and the per-field ratchet prevented re-offering 800. The supplier's omitted alternative may simply signal that it has already reached its floor. This is not 2/2 causal evidence for a buyer change.

S5 r4 reason: **“Since you want to stick to the standard payment terms, I can offer €… for … ppm and €… chargeback.”** S13 r4: **“You said you reflected cash timing in your options, but without an actual agreement on faster payment, we just can't drop the price anymore.”** Payment is fixed at 60 days, so promising faster payment is not a valid remedy.

**Mechanism/change.** Off-by-default `retained_quality_trade` in `packages.plan_packages()`: when quality is negotiable and the supplier previously quoted a compliant relaxed-quality/low-chargeback mix in this session, allow one newly repriced counter on that mix despite its absence from the latest reply. Keep the stricter-quality option and the same total-cost target; retain price monotonicity. This explicitly relaxes the per-field quality ratchet only for a compensated menu trade. Never accept a stale ID. Do not relax other terms or raise chargebacks. As a separate correctness fix, code-render fixed payment when asked and suppress framing that implies payment has improved; this prevents a misleading answer but is not demonstrated to unlock price.

**Gain/test.** First test one P11 run, with a control if code has changed since the saved runs. Success is a valid equal-cost relaxed option surviving the missing-alternative branch and a final score above the paired control without larger buyer concessions. Restoring €45.00 instead of €45.50 is **+8.36 case / +0.84 mean**, but is **zero improvement over the existing 79.35 best**. Going below €45.00 would be new evidence. Do not tune the whole concession schedule from this correlation.

**Hidden cases/guards.** Generalizes through permitted quality options and within-session quotes; must-haves still bind. Supplier production/inspection burdens are not fully represented in `supplier_value()`, so compensated quality flexibility is plausible. A strict quality commitment can be valuable; keep that choice in the menu and evaluate actual offered total costs. Never counter `final_offer`.

## Checks that do not justify another broad strategy test

- **Single-supplier rival citations:** 23 interpreted uses across six single-supplier cases, **zero explicit positive “took it into account” reactions**. Reasons include 17 irrelevant responses and four verified-but-no-change responses. Public alternative prices in all seven quote-bearing single-supplier fixture cases are above current prices; blindly exposing them can strengthen the seller. Do not simply make every suppressed quote shareable. This does not weaken the separate RFQ evidence: **37 positive reactions among 107 interpreted P05 rival uses**.
- **Past order prices:** confirmed **0 positive / 8 no-change** across eight cases. Keep internal.
- **Forecast spam:** P04 **0/2** and P10 **0/4** explicit positives; do not generalize the forecast mechanism to every supplier. One P10 news claim also produced no-change; no evidence supports forcing news universally.
- **Global `OUR_TERMS_OPTION`:** the nine-history scratch audit exposes the P11 EUR500-chargeback issue. Do not promote it on a twin gain or reorder-only changes in raw-material menus.
- **Generic faster payment on P11:** fixed term. Ordinary acknowledgment has already failed; `20261011T073038Z/case_P11`, r4 says **“Thanks for the update on the payment terms, but since you can't do faster payment, I really can't go any lower on the price.”** No unsupported promise or hidden payment field should be added.
- **Early alternative locking / agreed-ending step caps:** existing L46/L45 findings remain the evidence: 85% of 87 final deals beat the earlier better alternative; 19/50 agreed endings were echoes, with era confounding. Not independently recomputed here; no new recommendation to reverse them.
- **Index-refusal rule / anchor and pace retuning:** existing S7 gives 62.6 P08 and 57.5 P18; S9's reciprocity change gives 47.3 twice on P08 and 45.3 on P18. Those documented failures are not new experiments in this audit. Keep their switches off.
- **Price-only recovery claims:** nominal sensitivities at S5 final structures are ~3.27 points per €0.05 on P07, 5.41 on P08, 3.35 on P18, and 8.36 per €0.50 on P11. These translate a real concession into score; they do not predict one. P01/P02 require additional health-cost checks.

## Reproduction and handoff

Scripts: `mine.py` freezes the session inventory and reason counts; `claims.py` audits typed claims and current dossier cards; `summary_stats.py` produces per-case forecast counts, the ten-session P11 comparison and price sensitivities; `menus.py` compares current planner menus with the existing flag over saved S5 histories; `checks.py` verifies equal-cost lead times and records inspected code hashes. Use the existing venv directly, without an environment loader:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:vendor/negotiation-arena-kit/starter-kit \
  vendor/negotiation-arena-kit/starter-kit/.venv/bin/python /tmp/codex_analysis/checks.py
```

These are offline analyses, not simulator or hosted performance tests. `menus.py` changes a module flag only inside its own analysis process; it does not edit source. Snapshot/hash outputs are in `/tmp/codex_analysis/`. Some exploratory output in `audit.txt` used a synthetic current-price opening; **do not use its OPEN PLAN rows**—the report's menu examples come from `menus.py` over actual saved supplier openings.

Suggested sequence: forecast on P07/P18/P11; RFQ volume separately on P05; then the lead-time tie-break. Only spend sessions on the lower-ranked variants if those screens leave time. For variable P05/P01, repeat; for deterministic cases, one initial screen per variant is adequate to reject obvious regressions, not to establish broad superiority. Record failed deals and timing regressions, preserve the control, and do not mix old-run scores into measurements of changed code.
