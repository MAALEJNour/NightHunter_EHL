# Codex findings 2: three opt-in flags (11 October 2026)

**All three flags are implemented, unit-tested and default OFF. None has been tested live.** Patch: `/tmp/codex_work/codex_patch.diff`. It covers `nighthunter/packages.py`, `nighthunter/live.py`, `scripts/rfq_live.py` and a new file, `tests/test_codex_flags.py`.

The patch passes `git apply --check` against the real repository at the copy's state. `nighthunter/`, `tests/` and `scripts/` are untracked, so `git diff` is empty. The patch is therefore a `diff -ruN` against a baseline copy, with `a/` and `b/` path prefixes. **pytest: 198 passed** (190 existing plus 8 new). **ruff (E4, E7, E9, F): all checks passed.** No hosted sessions, API or LLM calls, network access, commits or `.env` access. Scratch analysis is in `/tmp/codex_work/.scratch/`.

## 1. `packages.NEED_ALIGNED_LEAD = False`
- **What it does.** Applies in `plan_packages` → `build()` through the new helpers `aligned_lead()` and `prefer_need_lead()`. Some candidate mixes are identical except for lead time, with the same price, the same seller value and the same cost to us. Within such a group, the slowest allowed lead time that does not exceed `need_lead_time_days` now comes first, so the duplicate removal keeps it. The target, prices and every other field are unchanged. Must-haves are checked as before.
- **Deviation from "opening only".** The preference also applies in later rounds, but only if our opening contained that lead time. Otherwise round 2 would switch from 35 back to 28 days, which reads as a new demand for faster delivery. Openings sent without the flag are never switched.
- **Tests.** P05, all three bidders: 28 → 35 days at identical prices and costs. P10: 35 → 42 days, and the priced 56-day trade is kept. The other eight fixtures are byte-identical. A further test covers the sticky and non-sticky cases.
- **Where it fires.** Fixture replay: only P05 and P10. Saved traces (ours plus teammate): our opening asked faster than the need-aligned lead in P05 **7/28** sessions and P10 **19/30**.

## 2. `packages.RETAINED_QUALITY_TRADE = False`
- **What it does.** Applies in `plan_packages` and `build()` through the new helper `retained_quality_mix()`. It fires when all of the following hold:
  - PPM is negotiable;
  - the supplier quoted a compliant, relaxed-quality mix earlier in the session and dropped it from its latest reply;
  - that mix has no higher chargeback than the standing offer;
  - we have not re-offered it since the drop.

  When it fires, that quality mix is re-admitted past the per-field ratchet and repriced at the same target cost. It takes the last menu slot, after the stricter options. The anchor, schedule and target are computed without it. Per-mix price monotonicity still holds, and non-quality granted terms still pass the ratchet.
- **Safety properties.** Nothing changes at acceptance: it never accepts, never uses a stale ID, and never counters a `final_offer`, because `decide_packages` closes first.
- **Tests.** A P11-like history: 800 ppm quoted in round 1, dropped in round 2. With the flag on, the menu gains 800 ppm / EUR 0 chargeback at EUR 44.01, at equal cost and below the standing EUR 45.50. It is not repeated in the next round. All nine fixture openings are unchanged.
- **Where it fires.** Only P11 among practice cases: **46 of 163** open supplier replies in **18** sessions.
- **Caveat.** The 2/2 versus 0/8 result is confounded: the supplier may have dropped 800 ppm because it had reached its floor.

## 3. `live.FIXED_TERM_ANSWER = False`
- **What it does.** `LiveAgent.fixed_term_answer()` uses the new `FIXED_TERM_REQUEST` patterns for payment, contract length, lead time, effective date and incoterm. When the supplier's latest e-mail asks to change one of these fields and the case fixes it, a code-rendered sentence is added, for example "Payment terms are fixed at 60 days net in this agreement." It is a statement, never a promise.
- **Where it is wired in.** The `expert_prose` path of `decide_packages`, which records `fixed_term_answer` in the decision log, and the RFQ worker.
- **Tests.** Off by default. It fires on the P11 "faster payment" wording. It does not fire when payment is negotiable (P03), when the e-mail makes no request, or on P05's "can't finance longer terms".
- **Where it fires.** Only P11: **133** supplier replies in **33** sessions. No other saved case had a matching request for a fixed field.

## Risk to the final and recommendation
| Flag | Final risk | Recommendation |
|---|---|---|
| NEED_ALIGNED_LEAD | Low. The cost to us is identical by construction. A supplier may still not price slower lead times lower, so the gain may be 0. | **Keep OFF** unless 1 P10 session and 2 P05 sessions confirm it. If there is no time to test, leaving it OFF loses nothing measured. |
| RETAINED_QUALITY_TRADE | Medium. It changes the P11 menu on about 2 in 7 replies, could reveal flexibility on quality, and the evidence is correlational. | **Keep OFF.** At best it restores the 79.4 best score; it is not expected to exceed it. |
| FIXED_TERM_ANSWER | Low for honesty. Outcome effect unknown: it may end the supplier's "faster payment" hope earlier, which could cut either way. | **Keep OFF for the freeze** unless a P11 session can be spared. It is the most defensible to turn on, because it corrects misleading framing. |

Limitation: the trace counts mix our runs with teammate runs, and a "fires" count measures exposure, not effect. No flag has a measured score gain.
