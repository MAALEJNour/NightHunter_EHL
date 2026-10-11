# NightHunter: a procurement negotiator that lets code decide and the model write

Team NightHunter · Tacto Negotiation Arena · EHL Grand Finale 2026

---

## 1. The job

- The buyer is Hollerau Pumpenwerke. We negotiate by e-mail with supplier bots: price increases, renewals,
  RFQs, bundles, raw materials, capacity, quality.
- **What counts is total cost, not unit price.** That means price, uncovered need, payment, freight, lead
  time, quality, index risk and the supplier's health.
- Score = share of the possible saving captured: (C_open − C_deal) / (C_open − C_best).

---

## 2. How NightHunter works

1. **Dossier:** source-linked facts from the data package and the Sunday release (contracts, letters, scorecards, quotes, should-cost).
2. **Supplier read:** approval thresholds, price freezes, cash needs, contract notice, quality record, and what it says in the thread.
3. **Planner (code):** every term priced in euros with the official cost function. It sends **2–3 equal-cost
   options**, chosen to be the most attractive to the supplier at the same cost to us. It uses a goal-based
   opening ask and measured, reciprocal concessions.
4. **Arguments (code):** one checked fact per argument (data ID plus figure), one new fact per round, and direct
   answers to the supplier's questions with our binding figures.
5. **E-mail (LLM, gpt-5.6-luna):** writes only the framing. A filter blocks invented numbers, threats and promises.
6. **Close:** accept only the latest primary sheet that meets every must-have and beats the alternative; take a good final offer.

The RFQ runs one worker per bidder and cites the best rival bid. The final runner plays every wave in parallel.

---

## 3. What we learned about suppliers (from 300+ negotiations and the arena's own traces)

| Finding | Evidence |
|---|---|
| The first reply carries most of the money | stabilise: 1.40 % of a 1.69 % total move |
| Match their first big drop; a smaller step makes them **raise** the price | P08 47 vs 68 |
| A **new verified fact** moves them: notice period → "a fair point" | 34 of 38 |
| Index arguments and our past order prices do not ("not our reality") | 23 / 8 replies |
| Unanswered questions block them ("which volume can you commit to?") | 60+ times |
| Countering a single supplier's final offer → walk-away | 2 of 2 |
| A bigger LLM did not help (code decides the money) | gpt-6 variants lost or tied |

---

## 4. How we learned without over-fitting

- Every saved replay was mined for the supplier's **reasons in words**.
- Train / validation / test split **by case**, plus bootstrap: we keep a rule only if it holds on suppliers it has not seen.
- Path-to-target: for each case, the price needed for the best score vs the best price ever offered.
- A digital twin for bug-finding, honestly benchmarked: it did **not** beat a naive predictor, so we did not tune on it.
- No case IDs in the agent: the hidden final has new suppliers.

---

## 5. Results

- Mean per run: **46.7 → 75** (single-supplier practice cases).
- RFQ P05: **92.4** (house agent 56).
- Full 10-case rehearsal under the final's rules: **10/10 deals, 0 timeouts, every case inside the 8-minute cap**.

| P01 | P02 | P03 | P04 | P05 | P07 | P08 | P10 | P11 | P18 |
|---|---|---|---|---|---|---|---|---|---|
| 91.6 | 73.5 | 92.3 | 87.4 | 92.4 | 74.0 | 72.5 | 69.4 | 79.4 | 60.6 |

Robustness fixes found in rehearsal:
- RFQ "busy" sessions and stale offers;
- the open-session limit;
- offers with missing fields;
- late replies.

---

## 6. One negotiation (P01: a family foundry asks +9.5 %)

- **Our first e-mail:** a deferred start date in exchange for faster payment, plus two checked facts: their
  notice period vs the contract, and their on-time delivery of 85 %.
- **Supplier:** "We checked the notice period data you cited; it holds and we took it into account. **We did not
  know that - a fair point.**"
- **Result:** €135.0 from April instead of €138.55 from November. **Score 87–89.**

---

## 7. Honest limits and next steps

- Some suppliers have structural ceilings. For example, an indexed deal in P02 is capped near 74; that case needs a fixed price this supplier never quoted.
- Remaining gaps are price endgames; the next lever is one-session experiments on deterministic suppliers.
- Would it work on a real supplier? The reasoning would (total-cost menus, checked facts, answered
  questions). The numeric calibration was learned on bots and would need re-learning.
