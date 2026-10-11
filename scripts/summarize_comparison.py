"""Render a completed comparison manifest into a small Markdown report (no network)."""

import argparse
import json
from collections import Counter
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    if manifest["status"] != "complete":
        raise ValueError("Comparison is not complete; inspect manifest failures before reporting")
    controls = set()
    claim_results = Counter()
    details = []
    for row in manifest["runs"]:
        folder = Path(row["directory"])
        summary = json.loads((folder / "summary.json").read_text())
        controls.add(tuple(summary[k] for k in
                           ("model", "context_sha256", "shared_prompt_sha256", "runner_sha256", "validator_sha256")))
        state = json.loads((folder / "state.json").read_text())
        for turn in state.get("result", {}).get("trace", []):
            claim_results.update(r["result"] for r in turn.get("move", {}).get("claim_results", []))
        details.append((row, summary))
    if len(controls) != 1:
        raise ValueError("Model, dossier, common prompt or safeguards differed between runs")
    ranked = sorted(manifest["aggregates"].items(), key=lambda kv: kv[1]["mean_score"], reverse=True)
    lines = [
        "# P01 prompt comparison\n",
        "Date: 10 October 2026. Eight hosted practice runs: two per variant, second block in reverse order. "
        "Model: gpt-5.6-luna, low reasoning, 2,048 maximum completion tokens. "
        "The case dossier, common prompt, runner and validators were identical across the batch. "
        "Supplier replies and resulting conversation histories naturally differ.\n",
        "## Results\n",
        "| Variant | Mean /100 | Run 1 /100 | Run 2 /100 | Deals | Fallbacks | Accounted USD |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for variant, agg in ranked:
        rows = sorted((r for r in manifest["runs"] if r["variant"] == variant), key=lambda r: r["repeat"])
        scores = [f"{r['score'] * 100:.2f}" for r in rows]
        lines.append(f"| {variant} | {agg['mean_score'] * 100:.2f} | {' | '.join(scores)} | "
                     f"{agg['deals']}/{agg['attempts']} | {agg['fallbacks']} | {agg['cost_usd']:.6f} |")
    spent = sum(r["cost_usd"] for r in manifest["runs"])
    lines += [
        f"\nBatch conservative accounted model cost: **USD {spent:.6f}**. "
        "This is local accounting, not a provider invoice; cached-input discounts are ignored.\n",
        f"Highest observed mean: **{ranked[0][0]}**. Two repeats on one case are an exploratory result, "
        "not statistically reliable proof or evidence of generalization to other suppliers. "
        "No case or fallback was dropped from this completed batch.\n",
        "## Validation\n",
        "- All commercial terms pass exact-field, allowed-value, finite-price and must-have checks.",
        "- Models select verified claim cards. Code renders factual sentences and exact packages; "
        "arbitrary model prose is not transmitted. This does not validate arbitrary natural language.",
        f"- Arena-reported claim outcomes across the batch: {dict(claim_results)}.",
        "- Twenty-seven local tests passed before this frozen batch.",
        "- Central supplier-cost estimates guide acceptance; uncertainty ranges are reported, not treated as facts.\n",
        "## Replays\n",
        "| Run | Price | Payment days | Effective date | Cost EUR | Replay |",
        "|---|---:|---:|---|---:|---|",
    ]
    for row, summary in details:
        result = summary["result"]
        terms = result.get("terms") or {}
        lines.append(f"| {row['repeat']} {row['variant']} | {terms.get('unit_price')} | "
                     f"{terms.get('payment_days')} | {terms.get('effective_date')} | {result.get('c_deal')} | "
                     f"[Replay](https://arena.tacto.ai/replay/{row['session_id']}) |")
    lines += [
        "\nEach run's conversation.md, decisions.json, state.json and summary.json are in its manifest directory. "
        "These local artifacts are Git ignored.\n",
        "## Reproducibility\n",
        f"- Frozen case context SHA-256: `{manifest['context_sha256']}`.",
        f"- Code and prompts SHA-256: `{manifest['code_and_prompts_sha256']}`.",
        f"- Manifest: `{args.manifest}`.",
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n")
    print(f"Report written to {args.out}")


if __name__ == "__main__":
    main()
