# Batch A2 — single-supplier practice comparison

10 October 2026. This is a **new frozen batch**, separate from [Batch A](BATCH_A_RESULTS.md). Nine single-supplier practice cases (P01, P02, P03, P04, P07, P08, P10, P11, P18) were each attempted once with `adaptive/current` and once with `adaptive/packages`; order alternated by case. P05 is an unsupported RFQ and was excluded. One dossier per case was built before the first session and reused by its pair. Runs were strictly sequential. Model `gpt-5.6-luna` used low reasoning effort and 2,048 maximum completion tokens, with `--input-version current` and `--adaptation current`. The same prompt and code fingerprint was enforced on each run. The persistent $5 lifetime limit, $0.75 per-run limit and $0.75 batch reservation ceiling remained active.

[Frozen manifest, dossier hashes and order](../artifacts/batch_a2/20261010T172044Z/manifest.json). Code/prompts SHA-256 `c1347a940b0c622e5f0cfafcfca9d53d28c6898dd35a14e780b114a3fc03bf59`; runner SHA-256 `b056446a0e1e5c2fec041ae38527a701faa62ff1c1b4ed3d399a266d2473fbe0`. Before sessions, the full local suite passed **91 tests**, Ruff and syntax checks passed, and all nine real-dossier round-0 profiles/plans produced valid must-have-compliant packages with no claim-card construction error. The model rate was checked against the [official model page](https://developers.openai.com/api/docs/models/gpt-5.6-luna) ($0.20/M input, $1.20/M output tokens).

All **18 scheduled conditions were attempted**. Fifteen completed valid deals and three ended in HTTP 422 acceptance errors. The final two attempts (both P18) were consecutive errors, so the batch ended with `stopped_two_consecutive_errors_or_fallbacks` status. No score or total deal cost was returned for failed attempts. All completed deals met must-haves; P11 packages had one model fallback and other completed runs had zero.

| Case | Current score /100 | Packages score /100 | Outcome |
|---|---:|---:|---|
| P01 | 59.95 | 84.12 | Both valid; 0 fallbacks |
| P02 | 41.90 | error | Packages: HTTP 422 on alternative-sheet accept; current valid |
| P03 | 89.98 | 86.21 | Both valid; 0 fallbacks |
| P04 | 80.98 | 59.23 | Both valid; 0 fallbacks |
| P07 | 52.14 | 59.45 | Both valid; 0 fallbacks |
| P08 | 22.61 | 48.76 | Both valid; 0 fallbacks |
| P10 | 57.03 | 64.73 | Both valid; 0 fallbacks |
| P11 | 48.58 | 70.99 | Both valid; packages 1 model fallback |
| P18 | error | error | Both: HTTP 422 on alternative-sheet accept; no scores |

On the **seven complete pairs** (P01, P03, P04, P07, P08, P10, P11), the observed mean/worst scores were **current 58.75/22.61** and **packages 67.64/48.76**. This paired-completer mean excludes the failed P02 packages and both P18 attempts. Across all nine scheduled cases, assigning failed attempts a score of zero solely for a conservative failure-inclusive summary gives **current 50.35 mean / 0 worst** and **packages 52.61 mean / 0 worst**.

The zero-filled calculation is **not an official arena score** for failed sessions. One run per condition and three endpoint failures make this a diagnostic comparison, not proof that either policy is generally better. Teammate replays use a different agent and are context, not controls.

| Case / policy | Unit EUR | Pay d | Lead d | Effective | Months | Volume/y | Index | Incoterm | PPM | Chargeback EUR | Tooling EUR | Rounds | Fallbacks | Deal cost EUR | Scoreboard flags |
|---|---:|---:|---:|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---|
| P01 current | 136.50 | 45 | 42 | 2027-01-01 | 12 | 8150 | none | FCA | 900 | 0.00 | 0.00 | 3 | 0 | 1,119,627.66 | repeated_buyer_package, short_payment |
| P01 packages | 135.90 | 14 | 42 | 2027-04-01 | 12 | 8150 | none | FCA | 900 | 0.00 | 0.00 | 8 | 0 | 1,105,862.30 | relationship_cost, short_payment |
| P02 current | 363.00 | 60 | 35 | 2027-01-01 | 12 | 6110 | CU-NOTATION 3.0% db; share 0.2; base 2026-08 | DAP | 250 | 0.00 | 0.00 | 2 | 0 | 2,263,025.04 | index_cost, relationship_cost |
| P02 packages | — | — | — | — | — | — | — | — | — | — | — | — | — | — | HTTP 422; no deal result |
| P03 current | 433.08 | 90 | 49 | 2027-01-01 | 36 | 4580 | none | DAP | 350 | 0.00 | 0.00 | 3 | 0 | 3,942,826.22 | — |
| P03 packages | 431.61 | 60 | 49 | 2027-01-01 | 36 | 4580 | none | DAP | 350 | 0.00 | 0.00 | 5 | 0 | 3,955,565.46 | — |
| P04 current | 4.91 | 60 | 7 | 2027-01-01 | 24 | 20000 | none | DAP | 150 | 0.00 | 0.00 | 3 | 0 | 196,970.00 | — |
| P04 packages | 4.89 | 30 | 7 | 2027-01-01 | 36 | 20000 | none | DAP | 150 | 0.00 | 0.00 | 3 | 0 | 197,474.00 | short_payment |
| P07 current | 5.70 | 45 | 5 | 2027-01-01 | 36 | 30000 | none | DAP | 80 | 0.00 | 0.00 | 2 | 0 | 343,168.80 | short_payment |
| P07 packages | 5.57 | 30 | 5 | 2027-01-01 | 36 | 30000 | none | DAP | 80 | 0.00 | 0.00 | 4 | 0 | 336,456.80 | short_payment |
| P08 current | 5.73 | 60 | 10 | 2027-01-01 | 24 | 94800 | AS-14404 5.0% db; share 0.45; base 2026-08 | DAP | 50 | 0.00 | 0.00 | 2 | 0 | 1,096,185.67 | index_cost |
| P08 packages | 5.49 | 60 | 10 | 2027-01-01 | 36 | 94800 | AS-14404 5.0% db; share 0.45; base 2026-08 | DAP | 50 | 0.00 | 0.00 | 4 | 0 | 1,050,272.14 | index_cost |
| P10 current | 33.60 | 30 | 42 | 2027-01-01 | 24 | 23400 | none | DAP | 300 | 0.00 | 0.00 | 3 | 0 | 1,588,298.40 | short_payment |
| P10 packages | 31.90 | 30 | 56 | 2027-01-01 | 36 | 23400 | none | DAP | 300 | 0.00 | 0.00 | 3 | 0 | 1,541,808.00 | late_delivery, short_payment |
| P11 current | 46.75 | 60 | 56 | 2027-01-01 | 12 | 15900 | none | FCA | 1500 | 300.00 | 0.00 | 4 | 0 | 771,388.50 | — |
| P11 packages | 45.50 | 60 | 56 | 2027-01-01 | 12 | 15900 | none | FCA | 300 | 0.00 | 0.00 | 5 | 1 | 750,082.50 | — |
| P18 current | — | — | — | — | — | — | — | — | — | — | — | — | — | — | HTTP 422; no deal result |
| P18 packages | — | — | — | — | — | — | — | — | — | — | — | — | — | — | HTTP 422; no deal result |

All completed results report `must_haves_ok=true`. P10 met its volume minimum (both 23,400/y ≥ 22,230/y); P11 met its ppm maximum (current 1,500; packages 300). P10 has no available alternative in the result. Full accepted terms and alternatives are in the linked `summary.json` files beside the conversations.

### Full evaluated cost components (EUR)

Uncovered-need, fallback-risk and tooling components are zero in every completed run. Negative payment components are savings. A failed run has no evaluator cost breakdown.

| Case / policy | Price | Uncovered | Fallback risk | Payment | Freight | Late delivery | Quality | Tooling | Index clause | Index risk | Relationship | **Total** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| P01 current | 1,098,895.31 | 0.00 | 0.00 | 3,662.98 | 15,485.00 | 0.00 | 1,584.36 | 0.00 | 0.00 | 0.00 | 0.00 | **1,119,627.66** |
| P01 packages | 1,075,992.70 | 0.00 | 0.00 | 10,999.04 | 15,485.00 | 0.00 | 1,584.36 | 0.00 | 0.00 | 0.00 | 1,801.21 | **1,105,862.30** |
| P02 current | 2,217,930.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 1,191.45 | 0.00 | 8,871.72 | 17,743.44 | 17,288.43 | **2,263,025.04** |
| P03 current | 3,967,012.80 | 0.00 | 0.00 | -26,446.75 | 0.00 | 0.00 | 2,000.54 | 0.00 | 0.00 | 0.00 | 259.63 | **3,942,826.22** |
| P03 packages | 3,953,547.60 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 2,000.54 | 0.00 | 0.00 | 0.00 | 17.32 | **3,955,565.46** |
| P04 current | 196,400.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 570.00 | 0.00 | 0.00 | 0.00 | 0.00 | **196,970.00** |
| P04 packages | 195,600.00 | 0.00 | 0.00 | 1,304.00 | 0.00 | 0.00 | 570.00 | 0.00 | 0.00 | 0.00 | 0.00 | **197,474.00** |
| P07 current | 342,000.00 | 0.00 | 0.00 | 1,140.00 | 0.00 | 0.00 | 28.80 | 0.00 | 0.00 | 0.00 | 0.00 | **343,168.80** |
| P07 packages | 334,200.00 | 0.00 | 0.00 | 2,228.00 | 0.00 | 0.00 | 28.80 | 0.00 | 0.00 | 0.00 | 0.00 | **336,456.80** |
| P08 current | 1,086,408.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 4,888.84 | 4,888.84 | 0.00 | **1,096,185.67** |
| P08 packages | 1,040,904.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 4,684.07 | 4,684.07 | 0.00 | **1,050,272.14** |
| P10 current | 1,572,480.00 | 0.00 | 0.00 | 10,483.20 | 0.00 | 0.00 | 5,335.20 | 0.00 | 0.00 | 0.00 | 0.00 | **1,588,298.40** |
| P10 packages | 1,492,920.00 | 0.00 | 0.00 | 9,952.80 | 0.00 | 33,600.00 | 5,335.20 | 0.00 | 0.00 | 0.00 | 0.00 | **1,541,808.00** |
| P11 current | 743,325.00 | 0.00 | 0.00 | 0.00 | 24,486.00 | 0.00 | 3,577.50 | 0.00 | 0.00 | 0.00 | 0.00 | **771,388.50** |
| P11 packages | 723,450.00 | 0.00 | 0.00 | 0.00 | 24,486.00 | 0.00 | 2,146.50 | 0.00 | 0.00 | 0.00 | 0.00 | **750,082.50** |

### Failures, flags and conversations

The hosted endpoint rejected non-primary alternative IDs despite their appearance in the latest supplier message. P02 packages attempted `offer:70510-4-a`; both P18 attempts also chose `-a` alternatives. Each returned `HTTP 422: not a standing offer in this session`. This is an observed API mismatch with the local assumption that every latest-reply sheet can be accepted. It suggests only a subset of returned IDs is accept-ready; the exact rule remains unverified. No fallback retry was attempted after the error. Do not treat these as valid zero-cost deals. The historical Batch A results remain unchanged.

All packages-run scoreboard flags and every conversation path are listed below. The offline scoreboard only loads completed runs with `summary.json`; failed-run errors are listed explicitly and are absent from its aggregate table. [Full ignored offline scoreboard](../artifacts/scoreboard.md).

- [P01 current conversation](../artifacts/batch_a2/20261010T172044Z/P01/current/conversation.json): score 59.95; flags `repeated_buyer_package`, `short_payment`.
- [P01 packages conversation](../artifacts/batch_a2/20261010T172044Z/P01/packages/conversation.json): score 84.12; flags `relationship_cost`, `short_payment`.
- [P02 current conversation](../artifacts/batch_a2/20261010T172044Z/P02/current/conversation.json): score 41.90; flags `index_cost`, `relationship_cost`.
- [P02 packages conversation](../artifacts/batch_a2/20261010T172044Z/P02/packages/conversation.json) and [error](../artifacts/batch_a2/20261010T172044Z/P02/packages/error.json): HTTP 422; no score.
- [P03 current conversation](../artifacts/batch_a2/20261010T172044Z/P03/current/conversation.json): score 89.98; flags none.
- [P03 packages conversation](../artifacts/batch_a2/20261010T172044Z/P03/packages/conversation.json): score 86.21; flags none.
- [P04 current conversation](../artifacts/batch_a2/20261010T172044Z/P04/current/conversation.json): score 80.98; flags none.
- [P04 packages conversation](../artifacts/batch_a2/20261010T172044Z/P04/packages/conversation.json): score 59.23; flags `short_payment`.
- [P07 current conversation](../artifacts/batch_a2/20261010T172044Z/P07/current/conversation.json): score 52.14; flags `short_payment`.
- [P07 packages conversation](../artifacts/batch_a2/20261010T172044Z/P07/packages/conversation.json): score 59.45; flags `short_payment`.
- [P08 current conversation](../artifacts/batch_a2/20261010T172044Z/P08/current/conversation.json): score 22.61; flags `index_cost`.
- [P08 packages conversation](../artifacts/batch_a2/20261010T172044Z/P08/packages/conversation.json): score 48.76; flags `index_cost`.
- [P10 current conversation](../artifacts/batch_a2/20261010T172044Z/P10/current/conversation.json): score 57.03; flags `short_payment`.
- [P10 packages conversation](../artifacts/batch_a2/20261010T172044Z/P10/packages/conversation.json): score 64.73; flags `late_delivery`, `short_payment`.
- [P11 current conversation](../artifacts/batch_a2/20261010T172044Z/P11/current/conversation.json): score 48.58; flags none.
- [P11 packages conversation](../artifacts/batch_a2/20261010T172044Z/P11/packages/conversation.json): score 70.99; flags none.
- [P18 current conversation](../artifacts/batch_a2/20261010T172044Z/P18/current/conversation.json) and [error](../artifacts/batch_a2/20261010T172044Z/P18/current/error.json): HTTP 422; no score.
- [P18 packages conversation](../artifacts/batch_a2/20261010T172044Z/P18/packages/conversation.json) and [error](../artifacts/batch_a2/20261010T172044Z/P18/packages/error.json): HTTP 422; no score.

The scoreboard was run offline with `python -m nighthunter.scoreboard --replays ~/Downloads/saved-negotiation-conversations-2026-10-10/replays`. No full transcript or credential was copied into this tracked report.

### Accounting and next check

The model ledger added **$0.23153115** of the $0.75 batch ceiling; lifetime accounting is **$0.67388700/$5**. GET `/v1/me` showed quota **468 → 432** during the batch, a decrease of 36 while 18 sessions were opened by this runner. The observed quota change exceeds the runner’s session count; this report does not attribute the unexplained difference to these negotiations. The next step is a local-only regression and contract check for acceptance of non-primary alternatives, including P02/P18, then a separately approved frozen batch if hosted confirmation is needed. Do not change `--policy current`, `--input-version current` or `--adaptation current` defaults based on this single-repeat batch.
