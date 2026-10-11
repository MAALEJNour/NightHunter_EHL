"""Path to target: for every package structure, the price that beats the leaderboard target vs the
lowest price that supplier has ever actually put on the table for that structure (any saved run).

    python -m twin.targets

Uses the published cost function (matches hosted c_deal exactly except a few points of supplier-health
estimate in stabilise cases) and post-session C_open / C_best. Offline evaluation only.
"""

import json
from collections import defaultdict

from arena_kit.cost import total_cost

from nighthunter.context import ROOT
from nighthunter.packages import complete, compositions, health_estimate, price_for_cost
from nighthunter.supplier_profile import build_profile
from twin.dataset import sessions

TARGET = {"P01": 100, "P02": 88, "P03": 99, "P04": 87, "P07": 82, "P08": 92, "P10": 74, "P11": 89, "P18": 73}
FIXTURES = json.loads((ROOT / "tests/fixtures/hosted_practice_cases.json").read_text())


def norm(v):
    if isinstance(v, dict):
        return {k: norm(x) for k, x in v.items()}
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v


def key(case, std, terms):
    t = complete(case, std, terms)
    return json.dumps(norm({k: v for k, v in t.items() if k != "unit_price"}), sort_keys=True)


def label(comp):
    c = json.loads(comp)
    out = []
    for k, v in sorted(c.items()):
        if k == "index_clause":
            out.append("fixed" if not v else f"index db{v.get('deadband_pct'):g}")
        elif k in ("payment_days", "contract_months", "lead_time_days", "volume_per_year", "ppm_commitment",
                   "chargeback_eur_per_complaint", "effective_date"):
            out.append(f"{k.split('_')[0][:4]}={v}")
    return " ".join(out)


def main():
    seen = defaultdict(lambda: defaultdict(lambda: (float("inf"), None)))  # case -> comp -> (price, how)
    bench, best = {}, defaultdict(float)
    for source, cid, case, result, path in sessions():
        c = (cid or "")[-3:]
        if cid not in FIXTURES:
            continue
        fx = FIXTURES[cid]
        if result.get("c_best"):
            bench[c] = (result["c_open"], result["c_best"])
            best[c] = max(best[c], (result.get("score") or 0) * 100)
        for step in result.get("trace") or []:
            mv = step["move"]
            if step["actor"] == "buyer":
                continue
            offers = ([mv["terms"]] if mv.get("terms") else []) + [a.get("terms") for a in mv.get("alternatives") or []]
            for t in offers:
                if t and isinstance(t.get("unit_price"), (int, float)):
                    k = key(fx["case"], fx["standard_terms"], t)
                    if t["unit_price"] < seen[c][k][0]:
                        seen[c][k] = (t["unit_price"], f"{source} r{step['round']} {mv.get('status')}")
    for c in sorted(TARGET):
        fx = FIXTURES[f"case:{c}"]
        case, std = fx["case"], fx["standard_terms"]
        profile = build_profile(case, {"evidence": fx["evidence"]}, case["suppliers"][0])
        supplier = health_estimate(case, std, profile)
        c_open, c_best = bench[c]
        c_target = c_open - TARGET[c] / 100 * (c_open - c_best)
        rows = []
        for comp in compositions(case, std):
            k = json.dumps(norm(comp), sort_keys=True)
            needed = price_for_cost(case, std, comp, c_target + 0.002 * (c_open - c_best), supplier)
            low, how = seen[c].get(k, (float("inf"), None))
            if low < float("inf"):
                low_score = 100 * (c_open - total_cost(case, {**comp, "unit_price": low}, std, supplier)) / (c_open - c_best)
            else:
                low_score = None
            rows.append((label(k), needed, low, how, low_score))
        rows = [r for r in rows if r[2] < float("inf")]
        rows.sort(key=lambda r: -(r[4] or -1e9))
        print(f"\n=== {c}  target {TARGET[c]}  our best {best[c]:.1f}")
        print(f"  {'structure':44} {'price for target':>16} {'lowest offered':>15} {'score at that':>13}  where")
        for lab, needed, low, how, sc in rows[:6]:
            flag = "  <-- target reachable at a price this supplier already offered" if needed and low <= needed else ""
            print(f"  {lab:44} {needed if needed else '-':>16} {low:>15} {sc:>13.1f}  {how}{flag}")


if __name__ == "__main__":
    main()
