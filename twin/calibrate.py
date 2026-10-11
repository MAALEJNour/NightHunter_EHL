"""Measure supplier behaviour from saved hosted transcripts, in the supplier's own value terms.

Offline evaluation only: uses post-session C_best to place each supplier's floor. Never imported by
the live agent.

    python -m twin.calibrate
"""

import json
import statistics
from collections import defaultdict

from arena_kit.cost import closing_terms, supplier_value

from nighthunter.context import ROOT
from nighthunter.packages import compositions, price_for_cost
from nighthunter.scoreboard import load_ours, load_replays

FIXTURES = json.loads((ROOT / "tests/fixtures/hosted_practice_cases.json").read_text())
TEAM = "/Users/nourmaalej/Downloads/replays"
SELLER_RATE = 0.08


def seller(case, standard):
    return {"standard": closing_terms(case, {}, standard), "interest_rate": SELLER_RATE}


def complete(case, standard, terms):
    t = {f: terms.get(f, standard.get(f)) for f in case["negotiable"]}
    return t if all(v is not None or f == "index_clause" for f, v in t.items()) else None


def floor_value(case, standard, c_best):
    """Highest seller value among packages costing the buyer exactly C_best: the twin's reservation."""
    s, best = seller(case, standard), None
    for comp in compositions(case, standard):
        price = price_for_cost(case, standard, comp, c_best)
        if price:
            v = supplier_value(case, {**comp, "unit_price": price}, s)
            best = v if best is None else max(best, v)
    return best


def value(case, standard, terms):
    t = complete(case, standard, terms)
    return supplier_value(case, t, seller(case, standard)) if t else None


def measure():
    runs = load_ours() + load_replays(TEAM)
    stats = defaultdict(lambda: defaultdict(list))
    for run in runs:
        case = run["case"]
        cid = case["case_id"]
        if cid not in FIXTURES or len(case["suppliers"]) > 1 or run["result"].get("c_best") is None:
            continue
        std, goal = FIXTURES[cid]["standard_terms"], case["buyer"]["category_goal"]
        vf = floor_value(case, std, run["result"]["c_best"])
        sup, ours = [], []
        for e in run["events"]:
            if e["actor"] == "supplier":
                vals = [value(case, std, o) for o in e["offers"] if o.get("unit_price")]
                vals = [v for v in vals if v]
                sup.append((min(vals) if vals else None, e["status"]))
            elif e["sheets"]:
                vals = [value(case, std, s) for s in e["sheets"]]
                ours.append(max(v for v in vals if v) if any(vals) else None)
        if len(sup) < 2 or not sup[0][0] or not vf or sup[0][0] <= vf:
            continue
        room = sup[0][0] - vf
        if sup[1][0]:
            stats[goal]["first_share"].append((sup[0][0] - sup[1][0]) / room)
        for i in range(1, min(len(ours), len(sup) - 1)):
            if None in (ours[i], ours[i - 1], sup[i][0], sup[i + 1][0]):
                continue
            our_move, their_move = ours[i] - ours[i - 1], sup[i][0] - sup[i + 1][0]
            gap = sup[i][0] - ours[i - 1]
            if gap > 0 and our_move > 0:
                stats[goal]["step_share"].append(our_move / gap)
                stats[goal]["mirror"].append(their_move / our_move)
        final = next((i for i, s in enumerate(sup) if s[1] == "final_offer"), None)
        stats[goal]["final_at"].append(final if final is not None else len(sup))
        stats[goal]["end_share"].append((sup[0][0] - min(s[0] for s in sup if s[0])) / room)
    return stats


def main():
    for goal, s in sorted(measure().items()):
        print(f"\n{goal}  (runs={len(s['final_at'])})")
        for key in ("first_share", "end_share", "mirror", "step_share", "final_at"):
            v = s[key]
            if v:
                q = statistics.quantiles(v, n=4) if len(v) > 3 else [min(v), statistics.median(v), max(v)]
                print(f"  {key:12} n={len(v):3} median={statistics.median(v):6.2f}  IQR=[{q[0]:.2f}, {q[-1]:.2f}]")


if __name__ == "__main__":
    main()
