# Overnight report (night of 10 → 11 October 2026)

What ran overnight, what was learned, and what to decide in the morning. **No live session was used
after S13** (which you approved; 6 sessions). Everything else was offline.

## Results at a glance

| | P01 | P02 | P03 | P04 | P05 | P07 | P08 | P10 | P11 | P18 |
|---|---|---|---|---|---|---|---|---|---|---|
| **Target (top team)** | 100 | 88 | 99 | 87 | 96 | 82 | 92 | 74 | 89 | 73 |
| **Our team best** (`arena me`) | 91.0 | 73.5 | 92.0 | **87.4** ✅ | 92.4 | 72.7 | 72.5 | 69.4 | 79.4 | 58.7 |

S13 (6 sessions; volume answer, quality fix, breakdown request): P02 73.5, P07 72.3, P10 68.6, P11 71.0,
P08 61.4, P18 58.7. **No new best.** Practice quota: 200 → 194 after S13 (our 6 sessions); `arena me` later showed **180** (the other 14 were not started by this agent: likely the teammate on the shared key). LLM ledger $4.51 / $7.

## What was learned

1. **Suppliers are nearly deterministic.** The same inputs give the same outcome: P02 ends at €361.44
   (73.5) and P18 at €5.20 (58.7) in almost every run. Score differences come from what we send, not
   luck. So **one live session per variant is a clean A/B test** for these cases.

2. **Our cost model matches the arena exactly.** On every saved deal it reproduces the arena's real cost
   to 0.0 score points (P04–P18), and within a few points where the supplier-health charge is estimated
   (P01/P02). The path-to-target numbers below are therefore reliable.

3. **Path to target** (`python -m twin.targets`): the price needed to hit the top score vs the lowest
   price that supplier has ever put on the table for the same structure, in any of ~270 runs.

   | Case | Gap | Diagnosis |
   |---|---|---|
   | P02 | −14.5 | The index route **cannot** beat ≈ 73.6: every index deal pays a fixed €17.7k index-risk charge, and below €361 the health charge rises faster than the price falls. The target needs a **fixed price** around €364–368 (90 or 60 days). This supplier has never quoted a fixed price below €368.65 (and that was at 14-day payment). The open question is how to get a fixed price that low. |
   | P18 | −14.3 | Target ≈ €5.05 with a 5 % deadband (45 days). The supplier **once offered €5.20 db5/p45 (= 63.0)** as an alternative in round 3 (S2); we kept negotiating, and its final offer dropped it (we took db0/p90 at €5.20, 58.7). |
   | P08 | −19.5 | Target ≈ €5.08 (db3, 90 days); the lowest ever seen is €5.26 (our 72.5). A real price gap. |
   | P07 | −9.3 | Target ≈ €5.21–5.30; lowest seen €5.35–5.46. A real price gap. |
   | P11 | −9.6 | Target €44.43 (300 ppm); our best €45.00. The supplier says it holds because "you ignored our request for faster payment", and payment is fixed in this case. |
   | P04 | +0.4 | At target. |

4. **Supervised learning with case-grouped train / validation / test** (`python -m twin.learn`; train
   P01 P02 P03 P04 P07, validation P10 P11, test P08 P18, plus leave-one-case-out). It covers 894
   supplier replies (627 ours, 267 teammate). The learned response model barely beats a naive baseline:
   1.18 vs 1.21 % error, better on 5 of 9 held-out cases. Across suppliers the hidden floor dominates;
   our choices explain little.

5. **Within-case rules, bootstrapped 300×** (`python -m twin.overnight`). A rule counts as robust only
   if its sign holds on the train, validation and test cases in ≥ 80 % of resamples. **None does.** The
   strongest only stay positive, never negative:
   - longer negotiations: 74 %;
   - matching the supplier's first big drop: 53 %;
   - a first-ask depth near the current anchor (middle tercile best in 6 of 9 cases).

   So the general strategy (S5 + lessons) is as good as this data can show. **Further gains need
   case-mechanism ideas (point 3), tested one session at a time**, not generic re-tuning.

6. **Deal endings (weak):** "agreed" endings score lower than final-offer endings in 6 of 8 cases. But
   on checking, 19 of the 50 agreed endings were echoes of the supplier's own alternative (the normal
   way to accept one), and most low-scoring agreed endings come from older agent versions. Treat this
   as era-confounded, not a rule.

7. **The LLM supplier twin fails its fidelity test** (2.4 % vs 1.3 % error for a naive guess). Do not
   tune on it (L40).

## Code changes (all offline-tested; 184 tests, replay gate 508 decisions / 0 errors, local rehearsal OK)

- **Late-reply guard (L38):** re-check the thread before a late send, so we never counter an unseen
  final offer. This caused S10 P08's 0. Message timestamps are now recorded.
- **One scorecard fact per ID (L39):** quality when PPM ≥ 1000, else delivery. Code ranks the first
  e-mail's three checked facts (notice, should-cost, quality, index, delivery).
- **Volume answer (L41):** a code-rendered sentence with our binding term-sheet volume, sent only when
  the supplier asks. In S13 P07 it was welcomed ("thank you for confirming the binding volume… we
  improve our offer").
- **Cost-breakdown request (L42):** built, **off**. P18 asked and got no spreadsheet and no reaction. A
  bug that dropped the request when the model wrote its own closing is fixed (P08 never asked).
- Unchanged: S5 planner (anchor, steps, reciprocity), luna, $7 cap.

Current fingerprint `0366a02e2220059efb553e8d0777dafd4face86747473a2f5c689195524f26ca`; **nothing is
committed yet** (needs your OK).

## Decisions for the morning

1. **Commit** the current version (without `.env` / `artifacts/`).
2. **Targeted one-session tests**, each a clean A/B on a deterministic supplier (your go needed):
   - **P02, fixed-price route:** offer fixed price at 60/90 days around €366–368 alongside the index
     option. Shows whether this supplier ever goes fixed below €368. Upside up to +15. **1 session.**
   - **P18, lock a better alternative:** when the supplier's own alternative is the best package seen so
     far, echo it at once instead of countering. Saved data: 19 of 19 echoes were agreed. Upside about
     +4. **1 session.**
   - (Dropped after checking: an end-game step cap. The "agreed = overpaid" signal was era-confounded.)
3. **The 10-case final-runner rehearsal** (10 sessions) before the final.

## How to re-run the overnight learning

Use the scratch environment with numpy + scikit-learn (the kit's venv has neither):

```bash
S=<scratchpad>; KIT=vendor/negotiation-arena-kit/starter-kit/.venv/lib/python3.12/site-packages
PYTHONPATH=.:vendor/negotiation-arena-kit/starter-kit:$KIT $S/mlenv/bin/python -m twin.overnight --boot 300
PYTHONPATH=.:vendor/negotiation-arena-kit/starter-kit:$KIT $S/mlenv/bin/python -m twin.learn
PYTHONPATH=.:vendor/negotiation-arena-kit/starter-kit:$KIT $S/mlenv/bin/python -m twin.targets
```

## Morning update (11 October)

- **Sunday release downloaded** to `data/release-sunday/` (outside vendor/); merged into **final** dossiers only
  (L47). It contains 4 supplier letters (Nordmark and Mairhofer group price lists, Fuchsreiter cash request,
  Rupprecht-Kessel steel bought forward), 6 news items (Kalwisz insolvency, Weißacher credit cover withdrawn,
  Konvertek supply normal, Strelvo acquires Mairhofer, stable pump order intake, Leitner logistics) and a
  purchasing memo. The profile reads the new signals (tests added; 186 pass).
- **Both one-session ideas rejected offline, saving 2 sessions:** P02 never quoted fixed below €371.95 at
  90 days (49.7 < our 73.5); locking a better alternative early loses in 85 % of 87 runs (L46).
- **Full 10-case rehearsal** (10 sessions, 480 s cap, all in parallel): **10/10 deals, 0 errors, 0 timeouts**, slowest
  223 s (P05). Scores 88.0 / 73.5 / 91.9 / 86.0 / 82.0 / 70.4 / 60.5 / 67.9 / 71.0 / 58.7 (P01…P18), mean 75.0.
- **Practice rounds for the 0.82 goal** (11 Oct, 07:21–08:10 UTC): 6 default rounds + anchor variants 0.9×/1.1×/1.2×.
  New team bests: P07 74.0 (1.2×), P18 60.6 (1.1×); mean of bests 79.07 → 79.28. Deterministic cases repeat
  exactly. **Three final-relevant bugs found and fixed:** RFQ under parallel load (L48), 429 open-session limit
  and a missing field in a supplier sheet (L49).
- **Codex findings applied** (forecast reply, RFQ volume answer; docs/CODEX_FINDINGS.md) and the RFQ under-load
  fix (L48) checked live: P05 under load 79.2 (busy/refresh handled). Last 10-case round (08:02 UTC): 10/10 deals,
  0 errors; P01 89.0, P02 73.5, P03 **92.3 (new best)**, P04 86.0, P05 81.4, P07 71.7, P08 60.5, P10 69.4,
  P11 79.4, P18 52.0. Team-best mean **79.31** (quota 220, ledger $5.80).
