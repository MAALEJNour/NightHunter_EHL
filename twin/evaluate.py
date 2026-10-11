"""Play the deterministic planner against supplier twins and score deals with the official cost.

    python -m twin.evaluate                       # current planner settings, 9 cases x 40 personas
    python -m twin.evaluate --sweep               # compare planner settings (robust mean / worst)

Offline evaluation only (uses practice C_best to place twin floors). Mirrors the live packages
policy's close rules: accept on recommend_accept, exhausted plan, agreed, final_offer or last move.
"""

import argparse
import contextlib
import glob
import json
import random
import statistics

from arena_kit.cost import must_haves_ok, total_cost

import nighthunter.packages as P
from nighthunter.supplier_profile import build_profile
from twin.calibrate import FIXTURES
from twin.supplier import Persona, SupplierTwin

TEAM = "/Users/nourmaalej/Downloads/replays"


def benchmarks():
    out = {}
    for f in glob.glob(TEAM + "/*/manifest.json"):
        for c in json.load(open(f))["cases"]:
            r = c["result"]
            out[c["case_id"]] = (r["c_open"], r["c_best"], r.get("c_alt"))
    return out


def score(c_open, c_best, cost):
    return max(0.0, min(1.0, (c_open - cost) / (c_open - c_best)))


CARD_KIND = (("notice", "notice"), ("estimate:", "should_cost"), ("quality", "quality"),
             ("delivery", "delivery"), ("index:", "index"), ("forecast:", "volume"), ("orders", "price_history"))
EVIDENCE = "fresh"  # "s5": model picks up to 3 cards in round 1 only; "fresh": + one new leverage fact per round


def kind(key):
    return next((k for prefix, k in CARD_KIND if key.startswith(prefix)), None)


def citations(case, fx, profile, events, used):
    """The claim types our agent would cite in this message (approximates the model's own picks)."""
    from nighthunter.live import LiveAgent
    from nighthunter.validation import available_claim_cards, claim_cards
    facts = {e["row"]["id"]: e["citable_fact"] for e in fx["evidence"]
             if e.get("citable_fact") and (e.get("row") or {}).get("id")}
    cards = available_claim_cards(claim_cards(case, {"evidence": fx["evidence"]}, facts, case["suppliers"][0]))
    first = not any(e.get("from") == "buyer" for e in events)
    model = [k for k in cards if cards[k]["stance"] != "supplier_supporting"][:2] if first else []
    fresh = {k: v for k, v in cards.items() if not set(v["refs"]) & used} if EVIDENCE == "fresh" else None
    chosen = LiveAgent.forced_claims(events, cards, profile, model, fresh)
    new = [k for k in chosen if k in cards and not set(cards[k]["refs"]) & used]
    for k in new:
        used.update(cards[k]["refs"])
    return [kind(k) for k in new if kind(k)]


def play(cid, persona, rng, bench):
    fx = FIXTURES[cid]
    case, std = fx["case"], fx["standard_terms"]
    c_open, c_best, c_alt = bench[cid]
    opening = P.complete(case, std, fx["opening_offer"]["terms"])
    profile = build_profile(case, {"evidence": fx["evidence"]}, case["suppliers"][0])
    sc = [e["row"] for e in fx["evidence"] if e.get("table") == "scorecards"]
    real_ppm = max(sc, key=lambda r: r["quarter"])["ppm"] if sc else None
    twin = SupplierTwin(case, std, opening, c_best, persona, rng, real_ppm=real_ppm)
    truth = P.health_estimate(case, std, profile)
    events = [twin.opening_message()]
    used = set()
    alt_score = score(c_open, c_best, c_alt) if c_alt else 0.0
    for _ in range(case.get("round_limit", 10)):
        status = events[-1]["status"]
        if status == "walked_away":
            return alt_score, "walked", len(events) // 2
        plan = P.plan_packages(case, std, events, profile)
        moves_left = case.get("round_limit", 10) - sum(e.get("from") == "buyer" for e in events)
        if plan["recommend_accept"] or plan["exhausted"] or status in {"agreed", "final_offer"} or moves_left <= 1:
            terms = events[-1]["term_sheets"][0]["terms"]
            cost = total_cost(case, terms, std, truth)
            if must_haves_ok(case, terms, std) and (c_alt is None or cost < c_alt):
                return score(c_open, c_best, cost), status, len(events) // 2
            return alt_score, "no_deal", len(events) // 2
        sheets = [p["terms"] for p in plan["packages"]]
        claims = citations(case, fx, profile, events, used)
        events.append({"from": "buyer", "term_sheets": [{"terms": t} for t in sheets]})
        events.append(twin.respond(sheets, claims))
    return alt_score, "round_limit", len(events) // 2


def evaluate(n=40, seed=7, settings=None):
    bench = benchmarks()
    results = {}
    with patched(settings or {}):
        for cid in sorted(FIXTURES):
            rng = random.Random(f"{seed}-{cid}")
            goal = FIXTURES[cid]["case"]["buyer"]["category_goal"]
            runs = [play(cid, Persona.sample(goal, rng), rng, bench) for _ in range(n)]
            results[cid] = runs
    return results


@contextlib.contextmanager
def patched(settings):
    saved = {k: getattr(P, k) for k in settings}
    try:
        for k, v in settings.items():
            setattr(P, k, v)
        yield
    finally:
        for k, v in saved.items():
            setattr(P, k, v)


def summarise(results):
    per_case = {cid: statistics.mean(r[0] for r in runs) for cid, runs in results.items()}
    worst = {cid: sorted(r[0] for r in runs)[len(runs) // 10] for cid, runs in results.items()}  # 10th pct
    return per_case, worst


def report(results, label="current"):
    per_case, worst = summarise(results)
    print(f"\n{label}: mean {100 * statistics.mean(per_case.values()):.1f}  "
          f"(mean of per-case 10th percentiles {100 * statistics.mean(worst.values()):.1f})")
    for cid, runs in results.items():
        ends = {}
        for r in runs:
            ends[r[1]] = ends.get(r[1], 0) + 1
        print(f"  {cid}  mean {100 * per_case[cid]:5.1f}  p10 {100 * worst[cid]:5.1f}  "
              f"rounds {statistics.mean(r[2] for r in runs):.1f}  ends {ends}")


SWEEP_ANCHOR = {
    "current": {},
    "our-terms option off": {"OUR_TERMS_OPTION": False},
    "our-terms off + anchor x1.5 + re-anchor": {"OUR_TERMS_OPTION": False, "GOAL_MAX_CUT": 1.5, "REANCHOR_STEP": 0.50},
    "re-anchor 0.45": {"REANCHOR_STEP": 0.45},
    "anchor x1.3": {"GOAL_MAX_CUT": 1.3},
    "anchor x1.3 + re-anchor 0.45": {"GOAL_MAX_CUT": 1.3, "REANCHOR_STEP": 0.45},
    "anchor x1.5 + re-anchor 0.50": {"GOAL_MAX_CUT": 1.5, "REANCHOR_STEP": 0.50},
}

SWEEP = {
    "current": {},
    "anchor x0.7": {"GOAL_MAX_CUT": None},
    "anchor x1.3": {"GOAL_MAX_CUT": None},
    "steps small (0.15..0.08)": {"GAP_STEPS": (0.15, 0.13, 0.11, 0.10, 0.09, 0.08)},
    "steps large (0.35..0.20)": {"GAP_STEPS": (0.35, 0.30, 0.27, 0.24, 0.22, 0.20), "MAX_STEP": 0.40},
    "min step 0.05": {"MIN_STEP": 0.05},
    "min step 0.20": {"MIN_STEP": 0.20},
    "max step 0.50": {"MAX_STEP": 0.50},
    "max step 0.40": {"MAX_STEP": 0.40},
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sweep", action="store_true")
    parser.add_argument("--anchor", action="store_true", help="sweep anchor / re-anchor settings")
    parser.add_argument("-n", type=int, default=40)
    args = parser.parse_args()
    if not (args.sweep or args.anchor):
        report(evaluate(args.n))
        return
    base = dict(P.GOAL_MAX_CUT)
    rows = []
    for label, settings in (SWEEP_ANCHOR if args.anchor else SWEEP).items():
        if isinstance(settings.get("GOAL_MAX_CUT"), float):
            settings = {**settings, "GOAL_MAX_CUT": {k: v * settings["GOAL_MAX_CUT"] for k, v in base.items()}}
        elif "GOAL_MAX_CUT" in settings:
            factor = 0.7 if "0.7" in label else 1.3
            settings = {**settings, "GOAL_MAX_CUT": {k: v * factor for k, v in base.items()}}
        per_case, worst = summarise(evaluate(args.n, settings=settings))
        rows.append((label, statistics.mean(per_case.values()), statistics.mean(worst.values()), per_case))
    print(f"{'setting':28} {'mean':>6} {'p10':>6}  " + " ".join(c[-3:] for c in sorted(FIXTURES)))
    for label, mean, p10, per_case in rows:
        print(f"{label:28} {100 * mean:6.1f} {100 * p10:6.1f}  " +
              " ".join(f"{100 * per_case[c]:3.0f}" for c in sorted(per_case)))


if __name__ == "__main__":
    main()
