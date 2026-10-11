"""Prepare reproducible prompt candidates without making model calls."""

import argparse
import hashlib
import json
from pathlib import Path

from .context import ROOT, CaseContextBuilder, encoded

VARIANTS = ("baseline", "evidence_first", "reciprocal_trades", "adaptive")


def prepare(case, builder, max_chars=60000):
    dossier = builder.build(case, max_chars)
    context = encoded(dossier)
    common = (ROOT / "prompts/common.md").read_text()
    output = []
    for variant in VARIANTS:
        system = common + "\n" + (ROOT / f"prompts/{variant}.md").read_text()
        output.append({
            "variant": variant, "case_id": case["case_id"], "system": system, "user": context,
            "prompt_sha256": hashlib.sha256(system.encode()).hexdigest(),
            "context_sha256": hashlib.sha256(context.encode()).hexdigest(),
            "input_characters": len(system) + len(context),
            "stage": "offline prompt preparation, not a scored negotiation",
        })
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--max-chars", default=60000, type=int)
    args = parser.parse_args()
    case = json.loads(args.case.read_text())
    rows = prepare(case, CaseContextBuilder(), args.max_chars)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(encoded(row) for row in rows) + "\n")
    print(f"Prepared {len(rows)} variants with identical case context. No model calls or scores generated.")


if __name__ == "__main__":
    main()
