# Batch A — single-supplier practice comparison (stopped)

10 October 2026. The approved batch planned one `adaptive/current` control and one
`adaptive/packages` candidate on each of P01, P02, P03, P04, P07, P08, P10, P11 and P18,
with one frozen dossier per case and alternating order. Model `gpt-5.6-luna`, low reasoning,
2,048 maximum completion tokens, `--input-version current`, `--adaptation current`. The model
price was checked against the [official model page](https://developers.openai.com/api/docs/models/gpt-5.6-luna):
$0.20/M input and $1.20/M output tokens. The persistent ledger enforced the existing $5 total,
$0.75 per-run and a new **$0.75 batch cap** on each model reservation. Runs were strictly sequential.

The batch stopped at **6 attempted conditions**, under the rule requiring a stop after two
consecutive errors. Four sessions completed; both P03 attempts failed before a session opened.
P04, P07, P08, P10, P11 and P18 were not attempted. No score is imputed for the failed or
unattempted cases. [Frozen manifest and dossier hashes](../artifacts/batch_a/20261010T170640Z/manifest.json).

| Case | Control score /100 | Packages score /100 | Outcome |
|---|---:|---:|---|
| P01 | 62.80 | 67.77 | Both valid deals; 0 fallbacks |
| P02 | 34.57 | 22.47 | Both valid deals; 0 fallbacks |
| P03 | — | — | Both failed before session: null notice-day `TypeError` |
| P04, P07, P08, P10, P11, P18 | — | — | Not attempted after stop rule |

Across the **two completed cases only**, control mean/worst was **48.69/34.57**; packages
mean/worst was **45.12/22.47**. These incomplete, one-run-per-condition comparisons are
diagnostic, not evidence that either policy is generally better. Teammate replays use a
different agent and are context, not controls.

| Case / policy | Unit EUR | Payment d | Effective | Months | Volume/y | Index | Rounds | Fallbacks | Deal cost EUR | Flags |
|---|---:|---:|---|---:|---:|---|---:|---:|---:|---|
| P01 current | 136.80 | 60 | 2027-01-01 | 12 | 8,150 | none | 3 | 0 | 1,118,003.87 | closed_while_supplier_moving* |
| P01 packages | 138.20 | 14 | 2027-04-01 | 12 | 8,150 | none | 5 | 0 | 1,115,175.47 | short_payment |
| P02 current | 363.00 | 45 | 2027-01-01 | 12 | 6,110 | CU-NOTATION 3% deadband | 2 | 0 | 2,266,497.94 | index_cost, relationship_cost, short_payment |
| P02 packages | 351.21 | 90 | 2027-01-01 | 12 | 6,110 | CU-NOTATION 5% deadband | 4 | 0 | 2,272,226.89 | closed_while_supplier_moving*, index_cost, relationship_cost |

All four deals met their must-haves and beat the relevant alternative. P01 and P02 fixed
lead time, freight, quality and tooling terms remained case/quote governed; the full accepted
terms are in each `summary.json`. `closed_while_supplier_moving` is a unit-price-only review
cue and does not establish that buyer total cost would have improved by continuing.

| Cost component, EUR | P01 current | P01 packages | P02 current | P02 packages |
|---|---:|---:|---:|---:|
| Price | 1,100,931.70 | 1,086,982.92 | 2,217,930.00 | 2,145,893.10 |
| Uncovered need | 0 | 0 | 0 | 0 |
| Fallback risk | 0 | 0 | 0 | 0 |
| Payment terms | 0 | 11,111.38 | 7,393.10 | −14,305.95 |
| Freight | 15,485.00 | 15,485.00 | 0 | 0 |
| Late delivery | 0 | 0 | 0 | 0 |
| Quality | 1,584.36 | 1,584.36 | 1,191.45 | 1,191.45 |
| Tooling | 0 | 0 | 0 | 0 |
| Index clause | 0 | 0 | 8,871.72 | 0 |
| Index risk | 0 | 0 | 17,743.44 | 17,167.14 |
| Supplier relationship | 2.81 | 11.81 | 13,368.23 | **122,281.15** |
| **Total** | **1,118,003.87** | **1,115,175.47** | **2,266,497.94** | **2,272,226.89** |

P01 packages obtained a later effective date but paid in 14 rather than 60 days. P02 packages
obtained a lower unit price and 90-day payment, yet the evaluator's supplier-health charge rose
by about €108,913 and outweighed those gains. The planner intentionally excluded uncertain
supplier-health costs; this case shows that omission can hurt the hosted score. Its estimates
are not a disclosed supplier cost or hidden floor.

Conversations and offline scoreboard flags:

- [P01 current conversation](../artifacts/batch_a/20261010T170640Z/P01/current/conversation.json): `closed_while_supplier_moving`*.
- [P01 packages conversation](../artifacts/batch_a/20261010T170640Z/P01/packages/conversation.json): `short_payment`.
- [P02 packages conversation](../artifacts/batch_a/20261010T170640Z/P02/packages/conversation.json): `closed_while_supplier_moving`*, `index_cost`, `relationship_cost`.
- [P02 current conversation](../artifacts/batch_a/20261010T170640Z/P02/current/conversation.json): `index_cost`, `relationship_cost`, `short_payment`.

The scoreboard was run with
`python -m nighthunter.scoreboard --replays ~/Downloads/saved-negotiation-conversations-2026-10-10/replays`
and wrote [the full ignored local report](../artifacts/scoreboard.md). All listed packages-run
flags are included above. No transcript or teammate replay was copied into a tracked document.

Both [P03 current error](../artifacts/batch_a/20261010T170640Z/P03/current/error.json) and
[P03 packages error](../artifacts/batch_a/20261010T170640Z/P03/packages/error.json) were
`TypeError: '<' not supported between instances of 'NoneType' and 'int'` while `LiveAgent`
built notice claim cards. The trigger fact had `days: null`; `validation.py` had tested only
whether the key existed. The guard was fixed and locally regression-tested **after this batch
stopped**. That fix changes the code fingerprint; no further hosted sessions were attempted.

Practice quota moved **474 → 470** (four sessions). Batch model accounting was
**$0.05022210**, well under the $0.75 cap; the lifetime ledger moved from $0.39213375 to
**$0.44235585**. The two P03 errors consumed no model reservation or practice session.
The next experiment needs a new frozen batch and approval after offline P03 construction and
the supplier-health omission are reviewed; it cannot be spliced into this stopped batch.
