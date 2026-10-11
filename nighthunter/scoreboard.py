"""Offline scoreboard of saved negotiations: every run, its terms, cost parts, timeline and flaws.

Reads our runs (artifacts/live, artifacts/comparisons) and optional teammate replay folders
(practice-*/manifest.json + case_*.json). Post-session material for evaluation only: never feed
its scores, c_best or traces into a live decision.

    python -m nighthunter.scoreboard [--replays DIR ...] [--out artifacts/scoreboard.md]
"""

import argparse
import glob
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from .context import ROOT

FLAG_HELP = {
    "no_deal": "ended without a deal",
    "short_payment": "accepted payment earlier than the reference: financing cost paid",
    "index_cost": "accepted an index clause that adds cost/risk on the case's index path",
    "late_delivery": "accepted lead time beyond the need: late-delivery cost",
    "uncovered_need": "deal leaves need uncovered (fallback price + risk)",
    "relationship_cost": "supplier-health charge above EUR 1,000 (price pushed below its sustainable margin)",
    "countered_final_offer": "sent a counter after a final_offer",
    "closed_while_supplier_moving": "accepted while the supplier's last two offers were still improving",
    "contradicted_claims": "cited facts marked contradicted (costs trust)",
    "repeated_buyer_package": "sent an identical package twice",
}


def _event(actor, sid, status=None, offers=(), sheets=(), action=None, claims=()):
    return {"actor": actor, "sid": sid, "status": status, "offers": list(offers),
            "sheets": list(sheets), "action": action, "claims": list(claims)}


def load_ours(root=ROOT):
    runs = []
    for summary_path in sorted(glob.glob(str(root / "artifacts/**/summary.json"), recursive=True)):
        folder = Path(summary_path).parent
        summary = json.loads(Path(summary_path).read_text())
        conv_path, dossier_path = folder / "conversation.json", folder / "dossier.json"
        if not conv_path.exists() or not dossier_path.exists():
            continue
        events = []
        for entry in json.loads(conv_path.read_text()):
            msg, sid = entry["message"], entry.get("supplier_id")
            if entry["who"] == "Supplier":
                events.append(_event("supplier", sid, msg.get("status"),
                                     [s.get("terms", {}) for s in msg.get("term_sheets") or []],
                                     claims=[c.get("result") for c in msg.get("claim_results") or []]))
            elif entry["who"].startswith("Buyer"):
                action = (msg.get("action") or {}).get("type") if isinstance(msg.get("action"), dict) else None
                events.append(_event("buyer", sid, sheets=[s.get("terms", s) for s in msg.get("term_sheets") or []],
                                     action=action or "send"))
        label = "/".join(str(summary.get(k)) for k in ("variant", "policy", "input_version", "adaptation")
                         if summary.get(k) not in (None, "current"))
        runs.append({"source": "ours", "run": str(folder.relative_to(root / "artifacts")),
                     "case": json.loads(dossier_path.read_text())["case"], "label": label or "current",
                     "result": summary.get("result") or {}, "events": events,
                     "fallbacks": summary.get("fallbacks")})
    return runs


def load_replays(folder):
    runs = []
    for batch in sorted(glob.glob(str(Path(folder) / "practice-*"))):
        defs = json.loads((Path(batch) / "case-definitions.json").read_text())
        for path in sorted(glob.glob(batch + "/case_P*.json")):
            if path.endswith(("__threads.json", "__backoffice.json")):
                continue
            session = json.loads(Path(path).read_text())
            result = session.get("result") or {}
            events = []
            for step in result.get("trace") or []:
                move = step.get("move") or {}
                if step["actor"] == "buyer":
                    action = move.get("action")
                    action = action.get("type") if isinstance(action, dict) else (action or move.get("type"))
                    events.append(_event("buyer", move.get("supplier_id"),
                                         sheets=[s.get("terms", s) for s in move.get("term_sheets") or []],
                                         action="send" if action == "message" else action))
                else:
                    offers = ([move["terms"]] if move.get("terms") else []) + \
                             [a.get("terms", {}) for a in move.get("alternatives") or []]
                    events.append(_event("supplier", step["actor"], move.get("status"), offers,
                                         claims=[c.get("result") for c in move.get("claim_results") or []]))
            runs.append({"source": "teammate", "run": f"{Path(batch).name}/{session['session_id']}",
                         "case": defs[session["case_id"]], "label": "teammate-llm", "result": result,
                         "events": events, "fallbacks": None})
    return runs


def flags(run):
    case, result, events = run["case"], run["result"], run["events"]
    b, parts, terms = case["buyer"], result.get("cost_breakdown") or {}, result.get("terms") or {}
    out = []
    if not result.get("deal"):
        out.append("no_deal")
    early = terms.get("payment_days", 999) < b.get("reference_payment_days", 0)
    if terms and early and parts.get("payment_terms", 0) > 0:
        out.append("short_payment")
    if parts.get("index_clause", 0) + parts.get("index_risk", 0) > 0:
        out.append("index_cost")
    for key, flag in (("late_delivery", "late_delivery"), ("uncovered_need", "uncovered_need")):
        if parts.get(key, 0) > 0:
            out.append(flag)
    if parts.get("relationship", 0) > 1000:
        out.append("relationship_cost")
    last_status = {}
    seen = set()
    for e in events:
        if e["actor"] == "supplier":
            last_status[e["sid"]] = e["status"]
        elif e["sheets"]:
            if last_status.get(e["sid"]) == "final_offer":
                out.append("countered_final_offer")
            for sheet in e["sheets"]:
                key = (e["sid"], json.dumps(sheet, sort_keys=True))
                if key in seen:
                    out.append("repeated_buyer_package")
                seen.add(key)
    if result.get("deal"):
        prices = [min((o.get("unit_price") for o in e["offers"] if o.get("unit_price")), default=None)
                  for e in events if e["actor"] == "supplier" and e["sid"] == result.get("supplier_id")]
        prices = [p for p in prices if p]
        final = [e for e in events if e["actor"] == "supplier" and e["sid"] == result.get("supplier_id")][-1:]
        if len(prices) >= 3 and prices[-1] < prices[-2] < prices[-3] and final and final[0]["status"] != "final_offer":
            out.append("closed_while_supplier_moving")
    if any(c == "contradicted" for e in events for c in e["claims"]):
        out.append("contradicted_claims")
    return sorted(set(out))


def timeline(run):
    parts = []
    for e in run["events"]:
        if e["actor"] == "supplier":
            price = min((o.get("unit_price") for o in e["offers"] if o.get("unit_price")), default=None)
            parts.append(f"S{e['sid'][-5:] if e['sid'] else ''}:{price}/{(e['status'] or '?')[:5]}")
        elif e["sheets"]:
            parts.append("B" + ",".join(str(s.get("unit_price")) for s in e["sheets"]))
        elif e["action"]:
            parts.append(f"B:{e['action']}")
    return " ".join(parts)


def report(runs):
    by_case = defaultdict(list)
    for run in runs:
        by_case[run["case"]["case_id"]].append(run)
    all_flags = Counter()
    lines = ["# Negotiation scoreboard", "",
             "Offline evaluation of saved runs (ours + teammate replays). Scores are post-session results; "
             "never use them as live inputs. Teammate runs use a different agent and are context, not a control.", ""]
    summary = ["| Case | Type / goal | Runs | Mean | Worst | Best | Common flags |",
               "|---|---|---:|---:|---:|---:|---|"]
    detail = []
    for cid in sorted(by_case):
        rows = by_case[cid]
        case = rows[0]["case"]
        scores = [100 * (r["result"].get("score") or 0) for r in rows]
        case_flags = Counter(f for r in rows for f in flags(r))
        all_flags.update(case_flags)
        summary.append(f"| {cid} | {case['type']} / {case['buyer']['category_goal']} | {len(rows)} | "
                       f"{statistics.mean(scores):.1f} | {min(scores):.1f} | {max(scores):.1f} | "
                       f"{', '.join(f'{k} ×{v}' for k, v in case_flags.most_common(3))} |")
        detail += [f"## {cid} — {case['title']}", "",
                   f"Negotiable: {', '.join(case['negotiable'])}. "
                   f"Must-haves: {case['buyer'].get('must_haves') or 'none'}.", "",
                   "| Run | Agent | Score | Deal terms | Extra cost parts (EUR) | Flags |",
                   "|---|---|---:|---|---|---|"]
        for r, score in sorted(zip(rows, scores, strict=True), key=lambda x: -x[1]):
            terms = {k: v for k, v in (r["result"].get("terms") or {}).items() if k in case["negotiable"]}
            terms = {k: (f"idx db{v.get('deadband_pct')}" if isinstance(v, dict) else v) for k, v in terms.items()}
            extra = {k: round(v) for k, v in (r["result"].get("cost_breakdown") or {}).items() if v and k != "price"}
            detail.append(f"| {r['run']} | {r['label']} | {score:.1f} | {terms or '—'} | {extra or '—'} | "
                          f"{', '.join(flags(r)) or '—'} |")
        detail += ["", "Timelines (S = supplier best price/status, B = buyer asks):", ""]
        detail += [f"- `{r['run']}`: {timeline(r)}" for r in rows] + [""]
    flag_lines = ["## Flag totals", "", "| Flag | Runs | Meaning |", "|---|---:|---|"]
    flag_lines += [f"| {k} | {v} | {FLAG_HELP[k]} |" for k, v in all_flags.most_common()]
    return "\n".join(lines + summary + [""] + flag_lines + [""] + detail) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--replays", action="append", default=[], help="Teammate replay folder(s)")
    parser.add_argument("--no-ours", action="store_true")
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts/scoreboard.md")
    args = parser.parse_args()
    runs = ([] if args.no_ours else load_ours()) + [r for d in args.replays for r in load_replays(d)]
    text = report(runs)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text)
    print(text.split("\n## case:")[0])
    print(f"Full report: {args.out}")


if __name__ == "__main__":
    main()
