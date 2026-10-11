# Adaptive on P03: contract renewal

10 October 2026. One hosted practice run on a different case from the P01 prompt comparison. P03 renews the 7.5 kW frequency-converter agreement with Selvbrunn Drive Systems GmbH, a strategic supplier. The category goal includes supplier sustainability as well as buyer total cost.

**Result: 85.15/100, valid deal, autonomous completion, zero fallbacks.** No code or prompt changes were made for this run. Saved metadata confirms the same adaptive prompt, common instructions, runner, validator, model (gpt-5.6-luna) and settings as the P01 comparison. The case and dossier differ by design.

## Discussion and agreed terms

The supplier opened at EUR 438.21 per unit, 30-day payment, 12 months and 4,580 units annually. Adaptive cited the recorded +10.3% demand forecast and proposed EUR 432, 60-day payment, 36 months and the same annual quantity. The arena verified the forecast claim. The supplier offered that package, and the agent explicitly accepted its structured offer `offer:70530-1`.

| Measure | Result |
|---|---:|
| Unit price | EUR 432.00 |
| Payment | 60 days |
| Contract | 36 months |
| Annual volume | 4,580 units |
| Effective date | 2027-01-01 |
| Arena opening total cost | EUR 4,246,314.02 |
| Arena deal total cost | EUR 3,959,120.54 |
| Total-cost reduction versus opening | EUR 287,193.48 |
| Arena alternative total cost | EUR 4,332,545.92 |
| Arena normalized score | 0.8515216195 |
| Relationship charge | EUR 0 |
| Must-haves check | Passed (case has no explicit must-haves) |
| Buyer decisions / fallbacks | 2 / 0 |
| Negotiation elapsed time | 67.170 seconds |
| Longest model decision | 5.201 seconds |
| LLM calls, including preflight | 3 |
| Conservative accounted model cost | USD 0.00809605 |

The arena evaluates the fixed two-year need horizon even though the agreement is for 36 months. The total-cost reduction includes changes beyond unit price; it is not a price-only saving or a real purchasing transaction. Lifetime local model accounting is now USD 0.12277445 of the USD 5 allowance, excluding calls from other programs and without invoice reconciliation.

## Replay and local artifacts

- [Watch the arena replay](https://arena.tacto.ai/replay/18e1fd3969a6c0f8).
- [Read the full conversation](../artifacts/live/20261010T135954827239Z/conversation.md).
- [Structured result and cost breakdown](../artifacts/live/20261010T135954827239Z/summary.json).
- [Model decisions and executed actions](../artifacts/live/20261010T135954827239Z/decisions.json).

Artifacts are local and Git ignored. To run another paid P03 attempt from the repository root:

```bash
uv run --project vendor/negotiation-arena-kit/starter-kit --frozen --all-extras python -m nighthunter.live --case case:P03 --variant adaptive
```

This is encouraging evidence that the current agent can complete another case type. One P03 run cannot establish prompt superiority, repeatability or an improvement over P01: those cases have different score benchmarks. Next, compare adaptive with evidence_first on the same P03 dossier and unchanged safeguards in paired repeats before changing wording based on this result.
