"""Does the supplier's first concession scale with our first ask (anchoring), and when does it backfire?"""
import statistics
from collections import defaultdict

from nighthunter.scoreboard import load_ours, load_replays
from twin.calibrate import FIXTURES, TEAM, floor_value, value


def main():
    rows = defaultdict(list)
    for run in load_ours() + load_replays(TEAM):
        case = run["case"]
        cid = case["case_id"]
        if cid not in FIXTURES or len(case["suppliers"]) > 1 or run["result"].get("c_best") is None:
            continue
        std = FIXTURES[cid]["standard_terms"]
        vf = floor_value(case, std, run["result"]["c_best"])
        ev = run["events"]
        s_idx = [i for i, e in enumerate(ev) if e["actor"] == "supplier"]
        if len(s_idx) < 2:
            continue
        b = next((e for e in ev[s_idx[0]:s_idx[1]] if e["actor"] == "buyer" and e["sheets"]), None)
        v0 = min([v for v in (value(case, std, o) for o in ev[s_idx[0]]["offers"]) if v] or [0])
        v1 = min([v for v in (value(case, std, o) for o in ev[s_idx[1]]["offers"] if o.get("unit_price")) if v] or [0])
        if not b or not v0 or not v1 or not vf or v0 <= vf:
            continue
        va = max(v for v in (value(case, std, s) for s in b["sheets"]) if v)
        depth = (v0 - va) / (v0 - vf)          # our ask as a share of the supplier's room (1 = at its floor)
        conc = (v0 - v1) / (v0 - va) if v0 > va else None   # its concession as a share of the gap we opened
        rows[case["buyer"]["category_goal"]].append((depth, (v0 - v1) / (v0 - vf), conc, run["result"].get("score") or 0))
    for goal, r in sorted(rows.items()):
        print(f"\n{goal}")
        for lo, hi in ((-9, .5), (.5, 1.0), (1.0, 1.5), (1.5, 2.5), (2.5, 99)):
            g = [x for x in r if lo <= x[0] < hi]
            if g:
                print(f"  ask depth {lo:>4}-{hi:<4} n={len(g):2}  first move (share of room) {statistics.median([x[1] for x in g]):5.2f}"
                      f"  share of our gap {statistics.median([x[2] for x in g if x[2] is not None]):5.2f}"
                      f"  final score {100*statistics.median([x[3] for x in g]):5.1f}")


if __name__ == "__main__":
    main()
