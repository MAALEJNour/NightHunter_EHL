# P01 prompt comparison

Date: 10 October 2026. Eight hosted practice runs: two per variant, second block in reverse order. Model: gpt-5.6-luna, low reasoning, 2,048 maximum completion tokens. The case dossier, common prompt, runner and validators were identical across the batch. Supplier replies and resulting conversation histories naturally differ.

## Results

| Variant | Mean /100 | Run 1 /100 | Run 2 /100 | Deals | Fallbacks | Accounted USD |
|---|---:|---:|---:|---:|---:|---:|
| adaptive | 61.78 | 58.04 | 65.51 | 2/2 | 0 | 0.024818 |
| evidence_first | 59.23 | 55.66 | 62.80 | 2/2 | 0 | 0.024768 |
| baseline | 57.59 | 55.66 | 59.52 | 2/2 | 0 | 0.019852 |
| reciprocal_trades | 26.63 | 8.13 | 45.13 | 2/2 | 0 | 0.016591 |

Batch conservative accounted model cost: **USD 0.086029**. This is local accounting, not a provider invoice; cached-input discounts are ignored.

Highest observed mean: **adaptive**. Two repeats on one case are an exploratory result, not statistically reliable proof or evidence of generalization to other suppliers. No case or fallback was dropped from this completed batch.

## Validation

- All commercial terms pass exact-field, allowed-value, finite-price and must-have checks.
- Models select verified claim cards. Code renders factual sentences and exact packages; arbitrary model prose is not transmitted. This does not validate arbitrary natural language.
- Arena-reported claim outcomes across the batch: {'verified': 18}.
- Twenty-seven local tests passed before this frozen batch.
- Central supplier-cost estimates guide acceptance; uncertainty ranges are reported, not treated as facts.

## Replays

| Run | Price | Payment days | Effective date | Cost EUR | Replay |
|---|---:|---:|---|---:|---|
| 1 baseline | 137.4 | 60 | 2027-01-01 | 1122073.82 | [Replay](https://arena.tacto.ai/replay/3e80bfa8bea13dc4) |
| 1 evidence_first | 137.4 | 60 | 2027-01-01 | 1122073.82 | [Replay](https://arena.tacto.ai/replay/88cbc7183c653f40) |
| 1 reciprocal_trades | 137.5 | 14 | 2026-11-01 | 1149149.64 | [Replay](https://arena.tacto.ai/replay/e3867de97dad47e6) |
| 1 adaptive | 137.2 | 60 | 2027-01-01 | 1120716.24 | [Replay](https://arena.tacto.ai/replay/ccb5ba3926636b27) |
| 2 adaptive | 135.5 | 30 | 2027-01-01 | 1116460.46 | [Replay](https://arena.tacto.ai/replay/4f7d6fd799add248) |
| 2 reciprocal_trades | 137.2 | 30 | 2027-01-01 | 1128073.88 | [Replay](https://arena.tacto.ai/replay/cb27eb7043ffbcaf) |
| 2 evidence_first | 136.8 | 60 | 2027-01-01 | 1118003.87 | [Replay](https://arena.tacto.ai/replay/53c3b2f38ee20b2a) |
| 2 baseline | 136.0 | 30 | 2027-01-01 | 1119874.04 | [Replay](https://arena.tacto.ai/replay/58d97b5999e6c42f) |

Each run's conversation.md, decisions.json, state.json and summary.json are in its manifest directory. These local artifacts are Git ignored.

## Interpretation and next candidate

Adaptive is the candidate for the next evaluation batch, not an automatically promoted universal default. It averaged 4.19 points above baseline in this small P01 sample. Evidence-first's results varied from 55.66 to 62.80, illustrating why a single run is insufficient.

Reciprocal trades' first run accepted 14-day payment at EUR 137.50, which added EUR 11,455.28 of buyer financing cost. Its price concession did not compensate for the payment trade. Next work should calculate the cost of proposed packages before presenting them, then test adaptive and evidence-first across other case types. Avoid further wording changes based only on these two repeats.

Before this matched batch, the fixed runner's first autonomy check walked away for zero because it treated the pessimistic supplier-cost scenario as a hard rejection threshold. That was corrected; a second check closed a valid deal autonomously at 49.70 with no fallbacks. Those two diagnostic runs used different safeguards from this batch and are reported separately, not discarded from the project history or mixed into the controlled means.

All eight matched runs were autonomous, satisfied must-haves and had zero fallbacks. All 18 arena-evaluated claims were verified. Longest measured model decision was 6.142 seconds. Total cumulative conservative ledger accounting, including the original assisted pilot and both diagnostic runs, is USD 0.1146784 against the USD 5 allowance. No provider invoice reconciliation or evidence of cross-case generalization is claimed.

## Frozen inputs

- Frozen case context SHA-256: `a640ad180c41c9d0af10db4c8b6b490f31f5461acc90c87bf44a5ac403d6ad1b`.
- Code and prompts SHA-256: `b8851df814a0c8af2fb60d1022547c6c2ebd246d3e69017fd418bb721659bfbe`.
- Manifest: `artifacts/comparisons/20261010T134738Z/manifest.json`.
