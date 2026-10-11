# Offer-history input comparison and first P02 test

Historical hosted measurement only. Subsequent local-only implementation added complete current-offer selection, claim classification and separately selectable input/adaptation modes. No hosted supplier has tested that later code, and the scores below are unchanged.

10 October 2026. We tested a separate `--input-version offer_history` condition against the unchanged `--input-version current` control. Both used `adaptive`, `--policy economics`, gpt-5.6-luna at low reasoning, the same case dossier per case, the same cost adviser, claim renderer, guards and model-call budgets. The new condition removes cards whose references were already cited from the model's available-card list, adds exact prior buyer packages and the next supplier status to live state, and adds [a short instruction](../prompts/offer_history.md) about not lowering price on identical non-price terms. This is a combined input-and-instruction change; the effects cannot be attributed separately.

| Hosted case | Control scores / mean | Offer-history scores / mean | Difference in mean |
|---|---:|---:|---:|
| P01 price increase | 78.27, 64.50 / **71.38** | 76.59, 37.04 / **56.81** | **-14.57 points** |
| P03 renewal | 84.67, 83.39 / **84.03** | 86.78, 83.39 / **85.08** | **+1.05 points** |
| P02 copper pass-through, first hosted test | 24.87 / **24.87** | 6.57 / **6.57** | **-18.29 points** |

All ten attempts closed valid deals autonomously, with zero fallbacks; all 24 arena-evaluated claims were verified. The runs spent USD **0.18941835** in the conservative model ledger; lifetime total is **USD 0.39213375 / 5**. These are small samples, particularly the single P02 pair. Case scores are normalized within each case and should not be treated as interchangeable economic outcomes.

The feature achieved its narrow citation goal: P01 control dropped three duplicate model-selected cards in each repeat, while the new input dropped none. But on P01, the new input accepted 14-day payment twice. Its second deal cost EUR 1,132,683.02 at EUR 135.50 per unit, versus its paired control's EUR 1,117,039.72 at EUR 133.60 per unit, also with 14-day payment. The supplier had rejected a lower offer after the buyer cited a rising material index, which strengthened the supplier's cost argument.

P02 exposed a more serious transfer problem. The opening cited a notice comparison where the supplier's 109 days exceeded the contractual 90 days, and a 273 PPM scorecard; the supplier said neither changed its calculation. The new-input buyer later cited the internal should-cost estimate of EUR 374.95 while asking for EUR 359.50–365.00; the supplier said those asks were below the verified estimate. It eventually accepted EUR 369.15 with 14-day payment. Although this unit price was lower than the control's EUR 370.27, the new deal cost **EUR 2,279,754.24** versus **EUR 2,271,091.17** for the control's 45-day payment. Its payment-term component alone was EUR 23,056.29. This is a concrete example of lower price producing a worse score. Neither run exploited an index-clause trade effectively. The first P02 sample is diagnostic, not a reliable estimate of average case performance.

**Decision:** keep `current` as the default input. Preserve `offer_history` for further controlled experiments, but do not promote the combined change. Next, separate the two mechanisms: test unused-card filtering alone and structured offer history alone. More urgently, make the agent compare the complete cost of *actual supplier alternatives* before accepting and avoid evidence that supports the seller. The current closing path chiefly considers the first standing supplier sheet; any change to that path needs its own local validation and matched hosted test. Extend the evaluation matrix beyond single-supplier price increases and renewals before claiming broad readiness.

All original transcripts, decisions and scores are local Git-ignored artifacts:

- [P01 manifest and four discussions](../artifacts/comparisons/20261010T143455Z/manifest.json)
- [P03 manifest and four discussions](../artifacts/comparisons/20261010T144112Z/manifest.json)
- [P02 manifest and two discussions](../artifacts/comparisons/20261010T144803Z/manifest.json)

Each manifest links its run directories, which contain `conversation.md`, `conversation.json`, `decisions.json`, `summary.json`, `state.json` and the frozen dossier. Run order was control/new then new/control for the two-repeat cases. The P02 dossier was built offline from the saved public hosted case snapshot; the runner confirmed exact equality with the current hosted case before opening each session. Code and prompts were frozen throughout each comparison.
