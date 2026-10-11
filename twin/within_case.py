"""Within-case learning: which of OUR choices go with better scores when the supplier is held fixed.

Hosted suppliers are nearly deterministic for identical inputs (S13: P02 73.5 and P18 58.7 again), so
comparing runs of the SAME case isolates our choices. A rule is kept only if its direction agrees on
the training cases AND is confirmed on the validation and test cases (split as in twin.learn).

    python -m twin.within_case        # needs numpy (scratch env)
"""

import json
import statistics
from collections import defaultdict

import numpy as np

from twin.dataset import sessions
from twin.learn import TEST, TRAIN, VALID


def run_features(result):
    trace = result["trace"]
    sup = [s for s in trace if s["actor"] != "buyer"]
    if len({s["actor"] for s in sup}) != 1:
        return None
    opening = next(((s["move"].get("terms") or {}).get("unit_price") for s in sup if s["round"] == 0), None)
    buyer = [s for s in trace if s["actor"] == "buyer" and s["move"].get("type") == "message"]
    if not opening or not buyer:
        return None
    asks = [min([(t.get("terms") or {}).get("unit_price") or 1e12 for t in b["move"].get("term_sheets") or [{}]])
            for b in buyer]
    sup_prices = [(s["move"].get("terms") or {}).get("unit_price") for s in sup]
    sup_prices = [p for p in sup_prices if isinstance(p, (int, float))]
    claims1 = (buyer[0]["move"].get("interpreted") or {}).get("claims") or []
    types1 = {c.get("type") for c in claims1}
    step2 = None
    if len(asks) > 1 and len(sup_prices) > 1 and sup_prices[1] > asks[0]:
        step2 = (asks[1] - asks[0]) / (sup_prices[1] - asks[0])
    later_claims = sum(len((b["move"].get("interpreted") or {}).get("claims") or []) for b in buyer[1:])
    statuses = [s["move"].get("status") for s in sup]
    return {
        "first_depth": (opening - asks[0]) / opening,
        "step2_share": step2,
        "n_msgs": len(buyer),
        "first_reply_move": (opening - sup_prices[1]) / opening if len(sup_prices) > 1 else None,
        "n_claims_r1": len(claims1),
        "later_claims": later_claims,
        "notice_r1": int("notice_period" in types1),
        "index_r1": int("index_change" in types1),
        "scorecard_r1": int(bool(types1 & {"delivery_record", "quality_record"})),
        "should_cost_r1": int("should_cost" in types1),
        "timeouts": sum(1 for b in trace if b["actor"] == "buyer" and b["move"].get("type") == "timeout"),
        "ended_agreed": int("agreed" in statuses),
        "ended_final": int("final_offer" in statuses),
    }


def collect():
    runs = defaultdict(list)
    for source, case_id, case, result, path in sessions():
        if result.get("score") is None or not case_id:
            continue
        f = run_features(result)
        if f:
            runs[case_id[-3:]].append({**f, "score": result["score"] * 100, "source": source, "path": path})
    return runs


def within_slope(rows, key):
    """Standardised within-case association (Spearman-like rank correlation) of a choice with the score."""
    pts = [(r[key], r["score"]) for r in rows if r.get(key) is not None]
    if len(pts) < 5 or len({p[0] for p in pts}) < 2:
        return None
    xs, ys = np.array([p[0] for p in pts], float), np.array([p[1] for p in pts], float)
    rx, ry = xs.argsort().argsort().astype(float), ys.argsort().argsort().astype(float)
    if rx.std() == 0 or ry.std() == 0:
        return None
    return float(np.corrcoef(rx, ry)[0, 1])


def main():
    runs = collect()
    keys = ["first_depth", "step2_share", "n_msgs", "n_claims_r1", "later_claims", "notice_r1", "index_r1",
            "scorecard_r1", "should_cost_r1", "timeouts"]
    print("runs per case:", {c: len(v) for c, v in sorted(runs.items())})
    print("\nWithin-case rank correlation of our choice with the final score (+ = more of it, better score)")
    print(f"{'choice':16} " + " ".join(f"{c:>6}" for c in sorted(runs)) + "   train  valid  test   verdict")
    for key in keys:
        corr = {c: within_slope(runs[c], key) for c in sorted(runs)}

        def agree(group):
            vals = [corr[c] for c in group if c in corr and corr[c] is not None]
            return statistics.mean(vals) if vals else None

        tr, va, te = agree(TRAIN), agree(VALID), agree(TEST)
        signs = [v for v in (tr, va, te) if v is not None]
        verdict = "consistent +" if signs and all(v > 0.1 for v in signs) and len(signs) == 3 else \
            "consistent -" if signs and all(v < -0.1 for v in signs) and len(signs) == 3 else "not robust"
        fmt = lambda v: f"{v:+.2f}" if v is not None else "   - "  # noqa: E731
        print(f"{key:16} " + " ".join(f"{fmt(corr[c]):>6}" for c in sorted(runs)) +
              f"   {fmt(tr)}  {fmt(va)}  {fmt(te)}   {verdict}")
    print("\nBest observed run per case (our or teammate) and what it did:")
    for c in sorted(runs):
        best = max(runs[c], key=lambda r: r["score"])
        med = statistics.median(r["score"] for r in runs[c])
        print(f"  {c}: best {best['score']:.1f} (median {med:.1f}, {best['source']}) depth {best['first_depth']:.3f} "
              f"step2 {best['step2_share'] if best['step2_share'] is None else round(best['step2_share'], 2)} "
              f"msgs {best['n_msgs']} claims_r1 {best['n_claims_r1']} later {best['later_claims']}")
    json.dump({c: v for c, v in runs.items()}, open("artifacts/twin_runs.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
