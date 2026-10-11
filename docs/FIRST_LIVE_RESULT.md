# First hosted LLM experiment — P01

Date: 10 October 2026. Model: gpt-5.6-luna, low reasoning. Prompt: evidence_first. One hosted practice case, dossier prepared before opening.

- Score: 0.684485 (68.45/100).
- Previously reported team best: 0.582831 (58.28/100). This is a historical comparison, not a paired prompt experiment.
- Opening unit price EUR 138.55; accepted EUR 136.30, 60 days net, effective 2027-01-01.
- Opening total cost EUR 1,153,779.74; accepted total cost EUR 1,114,788.78; saving EUR 38,990.96 across the case horizon.
- Must-haves passed. Exact supplier-health cost in arena result: EUR 181.70.
- Three model calls: readiness check and two buyer messages. Conservative accounted model cost USD 0.008149; provider invoice may differ. No cached-input discount assumed.
- [Hosted replay](https://arena.tacto.ai/replay/7e04a0abce3fa8e7). Full local discussion and result: artifacts/live/20261010T133318571681Z/conversation.md and summary.json (Git ignored).

## What happened

The supplier opened at EUR 138.55 from November. The buyer offered three price/payment/date packages and cited contract notice. The supplier acknowledged notice and revised its offer to EUR 137.50 from January. The second buyer message cited forecast demand and offered EUR 135 at 90 days or EUR 136 at 60 days. The supplier made a final EUR 136.30 offer at 60 days from January.

The runner then failed with KeyError payment_days when supplier standard defaults no longer contained that field. The assistant recovered the same session and accepted its current final offer after must-have and alternative-cost checks. **This result is assisted recovery, not a fully autonomous run.** Missing defaults are now completed for the supplier estimate, with a regression test. A second paid run has not been made to claim end-to-end recovery-free success.

## Next improvements

The notice and forecast arguments were verified and influenced the supplier. Historical quote citation quote:7300001 was classified irrelevant. The first message contained a confusing comparison between EUR 138.55 and EUR 143.22. ID existence checks are insufficient: add numerical and applicability validation before promoting this approach. Supplier financing/full-cost scenarios remain estimates. Validate autonomous closure offline and then compare prompt variants in matched repeated runs; one better historical score is not proof of prompt superiority.
