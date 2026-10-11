# Batch A3 — stopped after code changed

10 October 2026. Approved design: one `adaptive/current` control and two `adaptive/packages` repeats per case for P01, P02, P03, P04, P07, P08, P10, P11 and P18, sequentially, with one frozen dossier per case, alternating order, unchanged `--input-version current` and `--adaptation current`, model `gpt-5.6-luna` (low reasoning, 2,048 maximum completion tokens), and a $0.60 batch reservation ceiling. P05 RFQ remained excluded. Full local suite **125 passed**, Ruff, compileall and offline real-dossier round-0 preflight for all nine passed before the first session.

The [frozen manifest](../artifacts/batch_a3/20261010T175741Z/manifest.json) records code/prompts SHA-256 `3cdaa947c81754f8b2b3b32f852c4d7a9b5355c9b31ab7acf3ebddd2549fb9cb`, runner SHA-256 `c9800d8a9ba0a06ac0686468e32ab58c47da462881412554138b376a77fe0164` and each dossier hash. The fingerprint later became `09b56afccd9fdb580e35479c179ca19fad778fac6478152c5bfd513b153a3d63` because `nighthunter/rfq.py` appeared in the shared worktree while A3 was running. The runner correctly stopped **before run 6** with `stopped_code_changed`; **5 of 27** conditions were attempted. No subsequent session was opened under the changed fingerprint. The new RFQ file was not part of the five frozen runs and was not edited by Codex. Batch A and A2 remain separate historical batches.

| Case | Policy / repeat | A3 score /100 | A2 score /100 | Δ vs A2, points | Outcome |
|---|---|---:|---:|---:|---|
| P01 | current | 55.66 | 59.95 | -4.29 | valid deal; 0 fallbacks |
| P01 | packages_1 | 73.89 | 84.12 | -10.23 | valid deal; 0 fallbacks |
| P01 | packages_2 | 73.89 | 84.12 | -10.23 | valid deal; 0 fallbacks |
| P02 | current | 50.03 | 41.90 | +8.13 | valid deal; 0 fallbacks |
| P02 | packages_1 | 42.95 | error | — (A2 error) | valid deal; 0 fallbacks |
| P02 | packages_2 | — | error | — | Not attempted after fingerprint stop |
| P03 | current | — | 89.98 | — | Not attempted after fingerprint stop |
| P03 | packages_1 | — | 86.21 | — | Not attempted after fingerprint stop |
| P03 | packages_2 | — | 86.21 | — | Not attempted after fingerprint stop |
| P04 | current | — | 80.98 | — | Not attempted after fingerprint stop |
| P04 | packages_1 | — | 59.23 | — | Not attempted after fingerprint stop |
| P04 | packages_2 | — | 59.23 | — | Not attempted after fingerprint stop |
| P07 | current | — | 52.14 | — | Not attempted after fingerprint stop |
| P07 | packages_1 | — | 59.45 | — | Not attempted after fingerprint stop |
| P07 | packages_2 | — | 59.45 | — | Not attempted after fingerprint stop |
| P08 | current | — | 22.61 | — | Not attempted after fingerprint stop |
| P08 | packages_1 | — | 48.76 | — | Not attempted after fingerprint stop |
| P08 | packages_2 | — | 48.76 | — | Not attempted after fingerprint stop |
| P10 | current | — | 57.03 | — | Not attempted after fingerprint stop |
| P10 | packages_1 | — | 64.73 | — | Not attempted after fingerprint stop |
| P10 | packages_2 | — | 64.73 | — | Not attempted after fingerprint stop |
| P11 | current | — | 48.58 | — | Not attempted after fingerprint stop |
| P11 | packages_1 | — | 70.99 | — | Not attempted after fingerprint stop |
| P11 | packages_2 | — | 70.99 | — | Not attempted after fingerprint stop |
| P18 | current | — | error | — | Not attempted after fingerprint stop |
| P18 | packages_1 | — | error | — | Not attempted after fingerprint stop |
| P18 | packages_2 | — | error | — | Not attempted after fingerprint stop |

**Required decline flags:** Both P01 packages repeats scored **10.23 points below** their A2 packages score (84.12 → 73.89). P02 packages repeat 1 scored **7.08 points below A3 current** (42.95 versus 50.03); A2 packages had no score because of HTTP 422. No other packages runs were attempted, so they cannot be screened for a decline.

Completed-only current (2 runs): mean **52.85**, worst **50.03**. These are partial-batch diagnostics, not a nine-case comparison.
Completed-only packages (3 runs): mean **63.58**, worst **42.95**. These are partial-batch diagnostics, not a nine-case comparison.

All five completed deals met must-haves and beat their alternatives; no model fallback or HTTP error occurred. P02 packages accepted the primary `offer:70510-4`; its run did **not** exercise the alternative-echo branch, so hosted success of that branch remains unverified. One run per current case and only one P02 packages repeat completed. Teammate replays are context from a different agent, not controls.

| Case / policy | Unit EUR | Pay d | Lead d | Effective | Months | Volume/y | Index | Incoterm | PPM | Chargeback EUR | Tooling EUR | Rounds | Fallbacks | Deal cost EUR | Scoreboard flags |
|---|---:|---:|---:|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---|
| P01 current | 137.40 | 60 | 42 | 2027-01-01 | 12 | 8150 | none | FCA | 900 | 0.00 | 0.00 | 3 | 0 | 1,122,073.82 | — |
| P01 packages_1 | 138.20 | 30 | 42 | 2027-04-01 | 12 | 8150 | none | FCA | 900 | 0.00 | 0.00 | 6 | 0 | 1,111,688.10 | short_payment |
| P01 packages_2 | 138.20 | 30 | 42 | 2027-04-01 | 12 | 8150 | none | FCA | 900 | 0.00 | 0.00 | 6 | 0 | 1,111,688.10 | short_payment |
| P02 packages_1 | 372.55 | 90 | 35 | 2027-01-01 | 12 | 6110 | none | DAP | 250 | 0.00 | 0.00 | 5 | 0 | 2,262,527.34 | — |
| P02 current | 365.00 | 60 | 35 | 2027-01-01 | 12 | 6110 | CU-NOTATION 5.0% db, share 0.2, base 2026-08 | DAP | 250 | 0.00 | 0.00 | 2 | 0 | 2,259,175.07 | index_cost, relationship_cost |

Full terms, alternatives and scores are in each run’s `summary.json` beside the conversation. No P03/P04/P07/P08/P10/P11/P18 A3 outcome exists.

### Full evaluated cost components (EUR)

| Case / policy | Price | Uncovered | Fallback risk | Payment | Freight | Late delivery | Quality | Tooling | Index clause | Index risk | Relationship | **Total** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| P01 current | 1,105,004.46 | 0.00 | 0.00 | 0.00 | 15,485.00 | 0.00 | 1,584.36 | 0.00 | 0.00 | 0.00 | 0.00 | **1,122,073.82** |
| P01 packages_1 | 1,086,982.92 | 0.00 | 0.00 | 7,246.55 | 15,485.00 | 0.00 | 1,584.36 | 0.00 | 0.00 | 0.00 | 389.27 | **1,111,688.10** |
| P01 packages_2 | 1,086,982.92 | 0.00 | 0.00 | 7,246.55 | 15,485.00 | 0.00 | 1,584.36 | 0.00 | 0.00 | 0.00 | 389.27 | **1,111,688.10** |
| P02 packages_1 | 2,276,280.50 | 0.00 | 0.00 | -15,175.20 | 0.00 | 0.00 | 1,191.45 | 0.00 | 0.00 | 0.00 | 230.59 | **2,262,527.34** |
| P02 current | 2,230,150.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 1,191.45 | 0.00 | 0.00 | 17,841.20 | 9,992.42 | **2,259,175.07** |

### Conversation paths and offline flags

The offline scoreboard command was `python -m nighthunter.scoreboard --replays ~/Downloads/saved-negotiation-conversations-2026-10-10/replays`; [ignored full scoreboard](../artifacts/scoreboard.md). Every packages-run flag is listed here. No full transcript or credential is copied into this tracked report.

- [P01 current conversation](../artifacts/batch_a3/20261010T175741Z/P01/current/conversation.json): none.
- [P01 packages_1 conversation](../artifacts/batch_a3/20261010T175741Z/P01/packages_1/conversation.json): `short_payment`.
- [P01 packages_2 conversation](../artifacts/batch_a3/20261010T175741Z/P01/packages_2/conversation.json): `short_payment`.
- [P02 packages_1 conversation](../artifacts/batch_a3/20261010T175741Z/P02/packages_1/conversation.json): none.
- [P02 current conversation](../artifacts/batch_a3/20261010T175741Z/P02/current/conversation.json): `index_cost`, `relationship_cost`.

### Accounting and next step

Five sessions opened; observed practice quota **422 → 417**. Model ledger added **$0.08272970** of the $0.60 batch ceiling; lifetime accounted spend is **$0.75661670/$5**. The quota had already changed from A2’s observed 432 to 422 before A3 began; this report does not attribute that earlier change. The next experiment needs a **new frozen batch** after coordinating shared code edits; these five runs cannot be extended under the new fingerprint. Defaults remain `--policy current`, `--input-version current`, `--adaptation current`. No commit or push was made.
