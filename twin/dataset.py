"""Supervised dataset of supplier reactions from every saved post-session trace (ours + teammate).

One row per supplier reply (round >= 1): what our preceding e-mail did (ask depth, step, evidence
types and their check results, answered volume, questions) and what the supplier did next (price move
as a share of its opening price, status). Offline evaluation material only - never a live input.

    python -m twin.dataset            # writes artifacts/twin_dataset.json and prints a summary
"""

import glob
import json
import os
import re
from collections import Counter

from nighthunter.context import ROOT

TEAM_DIRS = [os.path.expanduser("~/Downloads/replays"),
             os.path.expanduser("~/Downloads/saved-negotiation-conversations-2026-10-10/replays")]
CLAIM_TYPES = ("notice_period", "rival_quote", "should_cost", "delivery_record", "quality_record",
               "index_change", "price_history", "volume_change")
VERDICTS = {"fair": r"did not know that", "took": r"took it into account|adjusted our calculation",
            "nochange": r"does not change our (?:calculation|position)", "notreal": r"not our reality",
            "ignored": r"ignor"}


def sessions():
    """(source, case definition or None, result) for every distinct session with a trace."""
    seen = set()
    for path in glob.glob(str(ROOT / "artifacts/**/state.json"), recursive=True):
        try:
            state = json.load(open(path))
        except (OSError, ValueError):
            continue
        result = state.get("result") or {}
        if result.get("trace") and state.get("session_id") not in seen:
            seen.add(state.get("session_id"))
            dossier = os.path.join(os.path.dirname(path), "dossier.json")
            case = json.load(open(dossier))["case"] if os.path.exists(dossier) else None
            yield "ours", state.get("case_id"), case, result, path
    for folder in TEAM_DIRS:
        for path in glob.glob(folder + "/practice-*/case_P*.json"):
            if path.endswith(("__threads.json", "__backoffice.json")):
                continue
            try:
                session = json.load(open(path))
            except (OSError, ValueError):
                continue
            result = session.get("result") or {}
            if not isinstance(session, dict) or not result.get("trace") or session.get("session_id") in seen:
                continue
            seen.add(session.get("session_id"))
            defs_path = os.path.join(os.path.dirname(path), "case-definitions.json")
            case = json.load(open(defs_path)).get(session["case_id"]) if os.path.exists(defs_path) else None
            yield "teammate", session["case_id"], case, result, path


def best_ask(move):
    prices = [(t.get("terms") or {}).get("unit_price") for t in move.get("term_sheets") or []]
    prices = [p for p in prices if isinstance(p, (int, float))]
    return min(prices) if prices else None


def rows():
    out = []
    for source, case_id, case, result, path in sessions():
        trace = result["trace"]
        goal = ((case or {}).get("buyer") or {}).get("category_goal")
        sup_steps = [s for s in trace if s["actor"] != "buyer"]
        if len({s["actor"] for s in sup_steps}) != 1:  # single-supplier threads only
            continue
        opening = next(((s["move"].get("terms") or {}).get("unit_price") for s in sup_steps if s["round"] == 0), None)
        if not opening:
            continue
        sup_price, prev_sup_move, our_prev_ask, first_depth = opening, 0.0, None, None
        cited_before = set()
        for i, step in enumerate(trace):
            if step["actor"] == "buyer" or step["round"] < 1:
                continue
            buyer = trace[i - 1] if i and trace[i - 1]["actor"] == "buyer" else None
            move = step["move"]
            price = (move.get("terms") or {}).get("unit_price")
            if buyer is None or buyer["move"].get("type") != "message" or not isinstance(price, (int, float)):
                if isinstance(price, (int, float)):
                    sup_price = price
                continue
            bm = buyer["move"]
            ask = best_ask(bm)
            if ask is None:
                continue
            body = bm.get("body") or ""
            claims = (bm.get("interpreted") or {}).get("claims") or []
            types = Counter(c.get("type") for c in claims)
            results = [c.get("result") for c in move.get("claim_results") or []]
            reasons = " ".join(step.get("reasons") or [])
            if step["round"] == 1:
                first_depth = (opening - ask) / opening
            our_move = 0.0 if our_prev_ask is None else (ask - our_prev_ask) / opening
            row = {
                "source": source, "case": case_id, "goal": goal, "round": step["round"], "path": path,
                "gap_before": (sup_price - ask) / opening,               # distance our ask leaves
                "sup_from_open": (opening - sup_price) / opening,          # how far it has come already
                "our_move": our_move,                                      # our concession this round
                "prev_sup_move": prev_sup_move,                            # its last concession
                "first_depth": first_depth or 0.0,
                "n_sheets": len(bm.get("term_sheets") or []),
                "n_claims": len(claims), "n_verified": results.count("verified"),
                "n_contradicted": results.count("contradicted"),
                "new_claims": sum(1 for c in claims if tuple(c.get("refs") or []) not in cited_before),
                "volume_answer": int(bool(re.search(r"\d{3,} units per year|units in total", body))),
                "body_len": len(body), "questions": body.count("?"),
                **{f"c_{t}": types.get(t, 0) for t in CLAIM_TYPES},
                **{f"v_{k}": int(bool(re.search(rx, reasons, re.I))) for k, rx in VERDICTS.items()},
                "y_move": (sup_price - price) / opening,
                "y_status": move.get("status"),
            }
            out.append(row)
            cited_before |= {tuple(c.get("refs") or []) for c in claims}
            prev_sup_move, sup_price, our_prev_ask = row["y_move"], price, ask
    return out


def main():
    data = rows()
    (ROOT / "artifacts/twin_dataset.json").write_text(json.dumps(data, indent=1))
    print(len(data), "supplier replies;", Counter(r["source"] for r in data))
    print("by case:", dict(sorted(Counter(r["case"] for r in data).items())))
    print("status:", Counter(r["y_status"] for r in data))


if __name__ == "__main__":
    main()
