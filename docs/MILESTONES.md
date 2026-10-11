# Milestones (from 2026-10-10 evening)

Goal: maximise money saved per deal (score = (C_open − C_deal) / (C_open − C_best)) on the **hidden**
final cases, using the practice cases to learn general rules, not to memorise practice suppliers.

## Where we are (measured)

| Strategy | Batch | Mean (9 single-supplier cases) | Worst |
|---|---|---:|---:|
| original agent (`current`) | S1 | 46.7 | 0.0 |
| code-designed offers (`packages`) | S1 | 67.3 | 40.6 |
| packages v2 / + persuasive e-mails | S2 | prose ahead on 5 of 8 paired; P11 broken by chargeback valuation | — |
| **packages + expert prose, all fixes (luna)** | **S5** | **75.1** | 58.7 (P18) |
| same, `gpt-6-sol` (5 cases) | S6 | never better; P01 −22 | — |
| top team per case (leaderboard, 10 Oct late, 10 cases) | — | 86.8 | 70 (P10) |

Targets to beat (top team per case, leaderboard 2026-10-11 night) vs our team best (`arena me`):

| | P01 | P02 | P03 | P04 | P05 | P07 | P08 | P10 | P11 | P18 |
|---|---|---|---|---|---|---|---|---|---|---|
| **target** | 100 | 88 | 99 | 87 | 96 | 82 | 92 | 74 | 89 | 73 |
| ours | 91.0 | 73.5 | 92.0 | 87.4 | 92.4 | 72.7 | 72.5 | 69.4 | 79.4 | 58.7 |

Lessons with evidence: [LESSONS.md](LESSONS.md).

## Practice quota (550 sessions / rolling 24 h, SHARED with the teammate's agent; 257 left at 10 Oct late)

The team key is shared: earlier "unexplained" quota drops were the teammate's sessions. Agree the split
before large batches. Sandbox (`case:D01`, `case:D02`) and final sessions do not count.

| Use | Sessions |
|---|---:|
| M2 hosted confirmation (2 configs × 9 cases × 2 runs) | 36 |
| M3 RFQ P05 (after free sandbox D02 runs) | 6 |
| M4 final rehearsal (all 10 cases in parallel, final runner) | 10 |
| Targeted re-tests of any case that drops > 10 points | ≈ 20 |
| Reserve for the teammate and after the Sunday data release | ≈ 50+ |

## M1 — Improve locally first (no quota)

1. **Supplier digital twin** calibrated on all saved hosted transcripts (ours + teammate, ≈ 110):
   first-reply concession, mirroring of our steps, freeze on token steps, patience until
   `final_offer`, walk-away, "agreed" when our package meets its position, and the supplier-health
   behaviour. Its hidden floor per case is derived offline from `C_best` (allowed: the twin is an
   evaluation tool; the agent never sees it).
2. **Offline tuning of planner parameters** (anchor `GOAL_MAX_CUT`, `GAP_STEPS`, `MAX_STEP`,
   `MIN_STEP`, pace) against the twin **across a range of twin behaviours** (robustness), choosing
   settings that maximise mean AND worst case, never one twin setting.
3. **Replay gate**: every change replays all saved supplier replies (no empty plans, premature accepts,
   price drops on identical terms, errors) plus unit tests.
4. Port the teammate's still-missing lessons: P04 longer-contract-for-discount answer to a firm-release
   request; numbers in cited claims without thousands separators; P10 full volume paired with a long
   commitment and feasible lead time.

### M1 progress (2026-10-10 night)

- `twin/` built: calibration on 110+ hosted transcripts (`twin.calibrate`, `twin.anchor`), behavioural
  supplier (`twin.supplier`: anchoring sweet spot + stonewall, mirroring, token-step freeze, patience,
  walk-away, term weight, real-PPM chargeback cost), evaluator (`twin.evaluate`, paired seeds).
- Twin vs hosted S2 (same planner): within ~5–10 points per case after adding `term_weight`.
- Twin sweeps: larger diminishing steps (0.30 → 0.15) beat 0.25 → 0.10; anchor ×1.5 + adaptive re-anchor
  best on mean (75.7) and worst decile (58.4) vs 72.8 / 58.2. Deep leverage asks are extrapolation:
  confirm on hosted (M2).
- Fixes from S2 transcripts: per-mix price never falls; steps capped; chargeback at real PPM; authority
  claim stops approval requests; RFQ market target only on a bidder's first message.

## M2 — Hosted confirmation (≈ 36 sessions)

Best two M1 configurations, 9 cases × 2 runs, sequential, ledger-capped. Promote only if no case drops
> 10 points versus its previous configuration without a second run confirming it.

### M2 results (S3, S4; 2026-10-10 night)

- S3 (fixes vs ambitious anchor, 9 cases): ambitious anchor rejected (P18 −10, P03 −7, P02 −3; won
  P01 +2.6, P04 +1.4). Chargeback fix confirmed: P11 71.0 (S2: 23.1). Larger steps from the twin cost
  P02/P08/P18 ≈ −7 → S2 step schedule restored.
- S4 (low vs medium reasoning effort, 4 cases): no clear winner (P08 +10.9 medium, P11 +8.4 low; P02
  decided by a planner knife-edge, fixed; P07 low had a fallback bug, fixed). Same cost/latency
  (≈ $0.018/run, 3–8 s per e-mail). Default stays low; `--reasoning-effort medium` available.
- Fixes merged after S4: health-limited options offered at their healthy floor (P02 index timing),
  empty model reply retried (no session-long fallback), duplicate-looking options removed, English-only
  framing.

## M3 — RFQ (P05)

**Done (2 of max 3 approved runs):** P05 hosted **92.4** and **79.2** (mean 85.8; top team 83,
teammate best 56.2). Both deals with the most motivated bidder (free capacity + cash request) at
€27.00 / €28.28 with 14-day payment, 28-day lead; all rival citations verified; replies 2.5–10 s after
each supplier message; no timeouts. Hypothesis from run 2: cap mirroring of a large first concession
when competition already supplies pressure (step 24.48 → 27.49 raised the landing price ≈ €1).
 Queued fixes (market target on the first message only, authority signal, call limit) were merged before
these runs. Hidden final cases include RFQs.

### S5 / S6 (2026-10-10 late)

- **S5 (luna, all fixes, 9 cases): mean 75.1** — best batch so far (S1 packages 67.3; original 46.7).
  P01 79.7, P02 73.5, P03 90.0, P04 86.0, P07 71.0, P08 67.9, P10 69.4 (record 70), P11 79.4, P18 58.7.
- **S6 (gpt-6-sol, 5 biggest-gap cases): never better** — P01 57.3 (−22.4), P02/P07 tie, P18 −6.7,
  P08 −7.6; $0.86 for 5 runs (≈ 9× luna). Rolled back to gpt-5.6-luna. `--llm-model` switch and
  verified price table (`nighthunter.live.PRICES`) remain for future tests.
- P01 sol loss traced to evidence choice (no contract-notice citation → supplier kept 1 November).
  Fix: code cites the notice card in the first message whenever the profile's `defer_effective_date`
  tactic applies (saved P01 runs: cited + later date asked → January/April in 27 of 29).

## M4 — Final readiness

**Built and rehearsed:** `scripts/final_runner.py` (`--final` polls waves; `--rehearse` plays a list).
Single-supplier cases via the kit's deadline-aware `play` + our LiveAgent (packages + expert prose);
RFQs via the concurrent `RfqNegotiator`; one shared thread-safe budgeted model (reservations under a
lock, API calls in parallel); sessions resumed on 409, never reopened; reads only cases/sessions.
Local S01–S03 parallel: all deals; 5-second cap: every case closed safely. **Full practice rehearsal (2026-10-11 07:21 UTC, 10 cases in parallel, 480 s cap): 10/10 deals, 0 errors,
0 timeouts, slowest case 223 s (P05 RFQ); scores P01 88.0, P02 73.5, P03 91.9, P04 86.0, P05 82.0, P07 70.4,
P08 60.5, P10 67.9, P11 71.0, P18 58.7 (mean 75.0; ledger $4.66).** **Hosted sandbox D01 + D02
in parallel under a 480 s cap: 82.4 and 71.9, done in 125 s / 202 s.** Remaining: Sunday data release,
a full 10-case practice rehearsal from the final machine (10 sessions), frozen commit, and an approved
budget cap for the final (the code enforces $5 total; ledger $3.24; the owner wants ≈ $8 kept for the
final, which needs an explicit cap change).

## Open (10 Oct late)

- **`gpt-6-astra` single run on P08 (approved one-off caps: $2 per run, $5.5 total): 63.7** (luna S5 67.9,
  sol S6 60.3, team best 70.0). 4 model calls, $0.672; ledger now $3.910. The e-mails were good (claims
  verified, questions answered), but code designs the offers, so the model could not fix the real
  problem (L33): after the supplier twice said a 36-month contract needs an index clause, the planner
  went back to fixed-price options, and the supplier closed with a 0 % deadband. Same pattern in every
  P08/P18 run. **Model verdict: stay on luna.** Next: planner fix for L33, checked on P08 + P18.
  Conversation: `artifacts/live/P08_astra_20261010T212924Z/`.
- Teammate handoff: [HANDOFF_FOR_TEAMMATE.md](HANDOFF_FOR_TEAMMATE.md).
- **S7 (luna, L33 index fix, P08 + P18): no gain.** P08 62.6 (S5 67.9), P18 57.5 (S5 58.7), $0.034.
  Fix kept but switched off (`INDEX_REFUSAL = False`); the default is the S5 behaviour again. Offline, the
  best P08 deal is about €5.05 (5 % deadband) against our €5.28–5.35: the remaining gap is the price endgame.
- **Budget cap raised by the owner from $5 to $7** (`nighthunter.live.TOTAL_LIMIT_USD`; final runner
  uses the same cap). Ledger $3.944; luna costs ≈ $0.018 per negotiation (S5), ≈ $0.90 for 50 final cases.
- **Lever catalogue (offline, 208 supplier documents → ≈ 47 recurring templates).** Used by the agent:
  approval threshold (19 suppliers), cash request (17), partnership (6), stale costing (9), price freeze (4),
  contract notice. Not used: "reviewing small accounts / focus on volume" (16), spare capacity "second shift
  on hold" (11), "Hollerau is an important reference customer" (9; mostly non-practice suppliers, likely
  final), "pay earlier, the bank is watching" (5), multi-year-only discounts (3), material bought forward (6).
- **S8 (luna, supplier-document citations forced, P08/P18/P04): no gain.** P08 57.0 (hedge backfired), P18
  58.7 and P04 86.0 identical to S5. Forcing removed (L34); open-book card stays available to the model.
- **S9 (luna, retreat-not-concession): rejected.** P08 47.3 ×2, P18 45.3: the bot raised its price after
  our smaller second step (L36).
- **S10 (luna, one new verified fact per round + new fact types, 9 cases): mixed, mean 66.9** (S5 75.1):
  P01 89.5, P02 73.5, P03 92.0, P04 86.0, P07 72.3, P08 0 (walk-away), P10 67.1, P11 62.6, P18 58.7.
  Past order prices never moved a supplier (8/8) → internal-only. S11 tests the refined set.
- **S11 (refined evidence, 9 cases): mean 73.5** (S5 75.1): P01 87.7, P03 92.0, P07 72.3 (gains replicated);
  P08 52.8 and P11 71.0 lost because the delivery fact displaced an index fact / the quality fact.
  Fixed (L39) + late-reply guard (L38); S12 checks P08/P11 only (2 sessions).
- **Digital twin upgraded** (evidence reactions by type, unmatched-first-drop penalty, stonewall
  recalibrated): case difficulty correlates 0.83 with hosted S5 and it reproduces the S9 loss, but it
  still over-rewards deeper anchors (L24 stands).
- **S12 (stopped by the user's request):** P08 72.5 (new team best) finished before the stop; P11 was
  started and abandoned. Rule since: no hosted run without the user's explicit go.
- **Offline (2026-10-11 night):** LLM supplier twin fails its fidelity test (L40). Supplier-question mining
  → volume answer (L41, built, additive). Cost-breakdown request for open-book suppliers (L42, built, off).
  Proposed hosted checks (need the user's go): volume answer on P02/P07/P10 (3), breakdown ask on P08/P18
  (2), quality-fact fix on P11 (1).
- **S13 (6 sessions, user's go): no new best** (P02 73.5, P07 72.3, P10 68.6, P11 71.0, P08 61.4, P18 58.7).
  Breakdown request: no spreadsheet (P18); switched off.
- **Overnight offline learning: see [OVERNIGHT_REPORT.md](OVERNIGHT_REPORT.md)** (L43–L45, path-to-target table,
  proposed one-session tests).
- Next idea (not started): opponent modelling from the supplier's counter-offers (ANAC-style
  frequency model) to learn which terms each supplier really values.
