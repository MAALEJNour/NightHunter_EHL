"""Round-by-round review of saved negotiations: did our agent respond well to the supplier?

    python scripts/review_run.py artifacts/strategies/S2_*/P11/prose_1      # one run, full detail
    python scripts/review_run.py artifacts/strategies/S2_* --summary         # every run, one line each

Per round: what the supplier said (status, best price, its question or request), what we sent
(our framing, best ask), our step as a share of the remaining gap, the supplier's next move, flags.
Offline evaluation only; nothing here is a live input.
"""

import argparse
import glob
import json
import re
import statistics
from pathlib import Path

QUESTION = re.compile(r"[^.?!]*\?")
REQUEST = re.compile(r"faster payment|earlier payment|cash ?flow|volume|commit|longer contract|lead time|"
                     r"index|surcharge|approval|committee|authority", re.I)
STOP = {"which", "would", "could", "about", "please", "there", "their", "these", "what", "your", "with"}


def price(sheets):
    prices = [s.get("terms", s).get("unit_price") for s in sheets or []]
    prices = [p for p in prices if isinstance(p, (int, float))]
    return min(prices) if prices else None


def rounds(conv):
    out, pending = [], None
    for entry in conv:
        msg = entry["message"]
        if entry["who"] == "Supplier":
            body = msg.get("body") or ""
            pending = {"status": msg.get("status"), "supplier_price": price(msg.get("term_sheets")),
                       "sheets": [s.get("terms") for s in msg.get("term_sheets") or []],
                       "question": (QUESTION.findall(body) or [""])[-1].strip()[:140],
                       "requests": sorted({m.lower() for m in REQUEST.findall(body)}),
                       "claims": [c.get("result") for c in msg.get("claim_results") or []],
                       "said": " ".join(body.split())[:220]}
            if out and out[-1].get("reply") is None:
                out[-1]["reply"] = pending
            out.append(pending)
        elif entry["who"].startswith("Buyer") and pending is not None:
            if msg.get("action"):
                pending["our_action"] = msg["action"]
                continue
            body = msg.get("body") or ""
            pending["our_ask"] = price(msg.get("term_sheets"))
            pending["our_sheets"] = [sh.get("terms", sh) for sh in msg.get("term_sheets") or []]
            pending["echo"] = [s.get("terms") for s in msg.get("term_sheets") or []] == pending["sheets"][1:2]
            pending["our_options"] = len(msg.get("term_sheets") or [])
            pending["our_text"] = " ".join(body.split())[:260]
            words = [w for w in re.findall(r"[a-z]{5,}", pending["question"].lower()) if w not in STOP]
            pending["answered"] = (not pending["question"]) or any(w in body.lower() for w in words)
            pending["reply"] = None
    return out


def _mix(terms):
    return tuple(sorted((k, json.dumps(v, sort_keys=True)) for k, v in terms.items() if k != "unit_price"))


def analyse(rows):
    """Steps are measured like for like: same non-price terms, earlier vs later price."""
    prev_ask, last_by_mix = None, {}
    for row in rows:
        ask, sp = row.get("our_ask"), row.get("supplier_price")
        flags, steps = [], []
        for terms in row.get("our_sheets", []):
            before = last_by_mix.get(_mix(terms))
            if before is not None:
                steps.append(terms["unit_price"] - before)
                if terms["unit_price"] < before:
                    flags.append("ask_went_down_same_terms")
        if steps and sp and prev_ask is not None and sp > prev_ask:
            row["step_share"] = round(max(steps) / (sp - prev_ask), 2)
            if 0 < row["step_share"] < 0.05:
                flags.append("token_step")
        for terms in row.get("our_sheets", []):
            last_by_mix[_mix(terms)] = terms["unit_price"]
        if row.get("question") and row.get("answered") is False:
            flags.append("question_ignored")
        if row.get("status") == "final_offer" and row.get("our_ask") is not None:
            flags.append("echoed_alternative_to_accept" if row.get("echo") else "countered_final_offer")
        if "contradicted" in row.get("claims", []):
            flags.append("claim_contradicted")
        row["flags"] = flags
        prev_ask = ask if ask is not None else prev_ask
    return rows


def load(run):
    run = Path(run)
    conv = json.loads((run / "conversation.json").read_text())
    summary = json.loads((run / "summary.json").read_text()) if (run / "summary.json").exists() else {}
    return conv, summary.get("result") or ({} if summary else {"score": None, "deal": "in progress"})


def detail(run):
    conv, result = load(run)
    rows = analyse(rounds(conv))
    print(f"\n=== {run}  score={100 * (result.get('score') or 0):.1f}  deal={result.get('deal')}")
    for i, r in enumerate(rows):
        print(f"[{i}] SUPPLIER {r['status']:<11} price={r['supplier_price']}  claims={r['claims'] or '-'}")
        print(f"     said: {r['said']}")
        if r["question"]:
            print(f"     asked: {r['question']}")
        if r.get("our_action"):
            print(f"     WE: {r['our_action']}")
        elif r.get("our_ask") is not None:
            print(f"     WE: best ask {r['our_ask']} in {r['our_options']} option(s); step {r.get('step_share')} of gap;"
                  f" answered={r['answered']}")
            print(f"     wrote: {r['our_text']}")
        if r["flags"]:
            print(f"     FLAGS: {', '.join(r['flags'])}")


def summary(paths):
    print(f"{'run':38} {'score':>6} {'rounds':>6} {'avg step':>8} {'answered':>9}  flags")
    steps_all = []
    for run in paths:
        if not (Path(run) / "conversation.json").exists():
            continue
        conv, result = load(run)
        rows = analyse(rounds(conv))
        steps = [r["step_share"] for r in rows if r.get("step_share") is not None]
        steps_all += steps
        qs = [r for r in rows if r.get("question") and "answered" in r]
        flags = sorted({f for r in rows for f in r["flags"]})
        name = "/".join(Path(run).parts[-2:])
        print(f"{name:38} {100 * (result.get('score') or 0):6.1f} {len(rows):6} "
              f"{(statistics.mean(steps) if steps else 0):8.2f} {sum(r['answered'] for r in qs):>4}/{len(qs):<4}  {', '.join(flags)}")
    if steps_all:
        print(f"\nmedian step share {statistics.median(steps_all):.2f} over {len(steps_all)} concessions")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    runs = []
    for p in args.paths:
        for match in sorted(glob.glob(p)):
            path = Path(match)
            runs += [str(c.parent) for c in sorted(path.rglob("conversation.json"))] if args.summary else [match]
    if args.summary:
        summary(runs)
    else:
        for run in runs:
            detail(run)


if __name__ == "__main__":
    main()
