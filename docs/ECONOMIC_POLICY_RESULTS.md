# Economic-policy experiment

10 October 2026. Six hosted runs with gpt-5.6-luna (low reasoning, 2,048 max completion tokens). Adaptive with its original inputs is compared with adaptive plus calculated package advice, concession history and `prompts/economics_policy.md`.

The model, case dossier, common instructions, evidence renderer, acceptance guards and budgets were identical within each case. The experimental condition adds both advisory input and policy wording; this does not isolate their separate effects. Code and prompts were frozen across all six runs. P01 order: current, economics, economics, current. P03 order: economics, current. No attempt was omitted.

| Case | Current adaptive /100 | Economic policy /100 | Observed difference |
|---|---:|---:|---:|
| P01, two runs each | 49.05 mean (62.80, 35.29) | **71.90 mean (70.99, 72.82)** | +22.86 points |
| P03, one run each | 73.07 | **88.27** | +15.21 points |

These small samples are encouraging, not statistically reliable proof of superiority. Earlier P01 adaptive averaged 61.78 over two other runs; the earlier P03 adaptive run scored 85.15. Those results are retained in their reports, not mixed into this matched comparison. The fresh control variability shows why selecting the best run is misleading.

All six runs closed valid deals autonomously, passed must-have checks and used zero fallbacks. All 11 arena-evaluated claims were verified. Longest model decision: 6.040 seconds. P01 economics took 74.913 and 100.347 seconds overall versus 36.711 and 47.510 for current; it used more negotiation turns and model calls. P03 economics took 50.377 seconds versus 70.953 for current. Supplier latency varies, so these are observed durations rather than timing guarantees.

Model accounting: P01 batch USD 0.05838670; P03 batch USD 0.02155425; this experiment **USD 0.07994095**. Lifetime ledger **USD 0.20271540 of USD 5**. Conservative runner accounting excludes outside clients and is not a provider invoice.

## Deals and discussions

| Run | Unit price EUR | Payment days | Effective date | Months | Score /100 | Replay |
|---|---:|---:|---|---:|---:|---|
| P01 current 1 | 136.80 | 60 | 2027-01-01 | 12 | 62.80 | [Replay](https://arena.tacto.ai/replay/f281c964dc3cfc1e) |
| P01 economics 1 | 133.60 | 30 | 2026-11-01 | 12 | 70.99 | [Replay](https://arena.tacto.ai/replay/e1606746d78c72bf) |
| P01 economics 2 | 133.00 | 14 | 2026-11-01 | 12 | 72.82 | [Replay](https://arena.tacto.ai/replay/988b97314ebd61ce) |
| P01 current 2 | 136.10 | 30 | 2026-11-01 | 12 | 35.29 | [Replay](https://arena.tacto.ai/replay/0870b1d7584f82f3) |
| P03 economics | 430.82 | 60 | 2027-01-01 | 36 | 88.27 | [Replay](https://arena.tacto.ai/replay/e85f4c14e2906bad) |
| P03 current | 435.00 | 45 | 2027-01-01 | 24 | 73.07 | [Replay](https://arena.tacto.ai/replay/b1b614f0af406b69) |

Annual volume remained 8,150 units on P01 and 4,580 on P03. Structured terms, not alternate prices mentioned in e-mail prose, determine the actual deal.

Local artifacts:

- [P01 manifest](../artifacts/comparisons/20261010T140428Z/manifest.json).
- [P01 economic run 2 discussion](../artifacts/comparisons/20261010T140428Z/2_adaptive_economics/conversation.md).
- [P03 manifest](../artifacts/comparisons/20261010T140903Z/manifest.json).
- [P03 economic discussion](../artifacts/comparisons/20261010T140903Z/1_adaptive_economics/conversation.md).

Each run directory also has dossier, decisions (including economic advice), state, metadata and summary JSON. Artifacts are Git ignored. Both manifests record code/prompts SHA-256 `e1fd6486e34d2f2c4cf105c62558b0e6331416b0cdab45e0b550fd9bf81fa735` and their case-specific frozen dossier hashes.

## What we learned and what remains

The original P01 control accepted an OPEN offer after one counteroffer in both new runs. The experimental policy continued with costed requests, then accepted an agreed/final package. That is consistent with the improvement hypothesis, but this combined experiment cannot assign the gain solely to package search, a more ambitious opening, different claims or extra turns.

The better P01 economic deal still cost EUR 15,483.38 more than its post-run benchmark. P03 economics remained EUR 39,553.40 above its benchmark. These values are evaluator diagnostics only; the negotiator never receives them.

P03 also exposed a weakness: the second buyer message offered the existing EUR 430.82/60-day standing package alongside two alternatives seeking lower prices. The supplier selected that unchanged package and the buyer closed. Next test: generate alternatives with similar buyer total cost, omitting an already available fallback from the outgoing menu when further bargaining is justified. Keep the actual standing offer in internal state and respect agreed/final status; no assumption that an old offer stays available after a new reply.

Keep economics opt-in while broadening evaluation. Next priorities are equivalent-value alternative packages, targeted evidence windows and supplier-cost uncertainty, detailed in [the improvement plan](IMPROVEMENT_PLAN.md). No model weights were trained and no automatic cross-run learning system was introduced.

## Reproduce

From the repository root, using existing local dossiers (each command makes paid calls):

```bash
uv run --project vendor/negotiation-arena-kit/starter-kit --frozen --all-extras python -m nighthunter.compare --dossier artifacts/comparisons/20261010T134738Z/dossier.json --variants adaptive --policies current economics --repeats 2
uv run --project vendor/negotiation-arena-kit/starter-kit --frozen --all-extras python -m nighthunter.compare --dossier artifacts/live/20261010T135954827239Z/dossier.json --variants adaptive --policies economics current --repeats 1
```

For one new economic-policy session: `python -m nighthunter.live --case case:P01 --variant adaptive --policy economics` using the same project environment. On another machine, generate a fresh live dossier first; the Git-ignored artifact paths above will not be present.
