"""RFQ decisions across parallel supplier threads: competition, bidder motivation, one close.

Pure functions over the case, each thread's events and the dossier; the live runner (Codex-owned)
owns concurrency, deadlines and the single terminal action. Inputs are public case/dossier data and
this session's messages only. A rival's offer is buyer-private: citing it reveals it to the bidder,
so only a LOWER rival price is ever proposed for citation (a higher one strengthens the bidder).

Only the latest PRIMARY sheet of a reply is acceptable (hosted API, Batch A2 HTTP 422 on `-a`).
"""

import math
import re

from arena_kit.cost import must_haves_ok, total_cost

from .packages import plan_packages, price_for_cost

ENDED = {"walked_away", "no_bid"}
# Evidence of how much a bidder wants this business. Weights are a transparent ordering heuristic,
# not a probability; every signal carries its source reference.
MOTIVATION = {"free_capacity": 2, "cash_pressure": 1, "reference_customer": 1,
              "full_order_book": -2, "commitment_condition": -1}
REFERENCE = re.compile(r"important reference customer", re.I)
COMMITMENT = re.compile(r"only against a binding [\w-]+ commitment", re.I)


def _latest(events):
    return next((m for m in reversed(events) if m.get("from") != "buyer"), {})


def live(threads):
    return [sid for sid, events in threads.items() if _latest(events).get("status") not in ENDED]


def exact_terms(case, terms, standard):
    """A supplier's offer exactly as quoted: every negotiable field from the sheet, else from its
    quote standard terms. Never snapped or guessed (Codex review: a quoted 43-day lead time must not
    become 42). Returns None if a field is unresolved or a value is neither an allowed option nor
    the supplier's own quote default."""
    out = {}
    for field in case["negotiable"]:
        if field in terms:
            value = terms[field]
        elif field in standard:
            value = standard[field]
        else:
            return None
        if field == "unit_price":
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not value > 0:
                return None
        elif value not in case.get("term_options", {}).get(field, [value]) and value != standard.get(field):
            return None
        out[field] = value
    return out


def primary(case, events, standard):
    """(term_sheet_id, exact terms) of the latest reply's primary sheet, or (None, None)."""
    sheets = _latest(events).get("term_sheets") or []
    if not sheets or not isinstance(sheets[0].get("term_sheet_id"), str):
        return None, None
    terms = exact_terms(case, sheets[0].get("terms") or {}, standard)
    return (sheets[0]["term_sheet_id"], terms) if terms else (None, None)


def _quoted_price(events):
    """The latest primary sheet's quoted unit price, exactly as sent, or None."""
    sheet = (_latest(events).get("term_sheets") or [{}])[0]
    price = (sheet.get("terms") or {}).get("unit_price")
    return price if isinstance(price, (int, float)) and not isinstance(price, bool) and price > 0 else None


def acceptable_offers(case, threads, standards):
    """Compliant primary offers of live threads, cheapest first: (cost, sid, offer_id, terms)."""
    out = []
    for sid in live(threads):
        offer_id, terms = primary(case, threads[sid], standards[sid])
        if offer_id and must_haves_ok(case, terms, standards[sid]):
            cost = total_cost(case, terms, standards[sid])
            if math.isfinite(cost):
                out.append((cost, sid, offer_id, terms))
    return sorted(out, key=lambda x: (x[0], x[1]))


def rival_benchmark(case, threads, standards, sid):
    """Cheapest acceptable rival offer cost (EUR), or None: a ceiling for this thread's concessions."""
    rivals = [o for o in acceptable_offers(case, threads, standards) if o[1] != sid]
    return rivals[0][0] if rivals else None


def rival_claims(case, threads, standards, sid):
    """Rival primary offers this bidder may be told about: same part, lower unit price only.

    The arena checks `offer:` citations against the rival's price in EUR. A rival that breaks a
    must-have is still a true price, but the wording must not imply we could accept it."""
    own = _quoted_price(threads[sid])
    if own is None:
        return []
    claims = []
    for rival in live(threads):
        if rival == sid:
            continue
        sheet = (_latest(threads[rival]).get("term_sheets") or [{}])[0]
        offer_id, price = sheet.get("term_sheet_id"), _quoted_price(threads[rival])
        if isinstance(offer_id, str) and price is not None and price < own:
            # Only the quoted price is cited; acceptability uses exact, complete terms.
            terms = exact_terms(case, sheet.get("terms") or {}, standards[rival])
            claims.append({"ref": offer_id, "supplier_id": rival, "unit_price": price,
                           "compliant": bool(terms) and must_haves_ok(case, terms, standards[rival]),
                           "sentence": f"Another bid in this RFQ ({offer_id}) quotes EUR "
                                       f"{price:.2f} per unit."})
    return sorted(claims, key=lambda c: c["unit_price"])


def _ref(item):
    source = item.get("source") or ""
    return source.split(":", 1)[1] if ":" in source else source


def market_signals(dossier, sid):
    """Capacity and commitment signals for one bidder (news topics, notes), each with its ref."""
    number = sid.split(":", 1)[-1]
    out = []
    for item in dossier.get("evidence", []):
        row, text = item.get("row") or {}, item.get("document") or ""
        mine = row.get("supplier_id") == sid or re.search(rf"(?<!\d){number}(?!\d)", _ref(item))
        if not mine:
            continue
        if item.get("table") == "news" and row.get("topic") in {"free_capacity", "full_order_book"}:
            out.append({"kind": row["topic"], "ref": _ref(item), "detail": row.get("headline")})
        if REFERENCE.search(text):
            out.append({"kind": "reference_customer", "ref": _ref(item), "detail": REFERENCE.search(text).group(0)})
        if COMMITMENT.search(text):
            out.append({"kind": "commitment_condition", "ref": _ref(item), "detail": COMMITMENT.search(text).group(0)})
    return out


def rank_bidders(case, dossier, profiles):
    """Bidders by evidenced motivation (highest first) with the tactic each signal suggests."""
    rows = []
    for sid in case["suppliers"]:
        signals = market_signals(dossier, sid)
        profile = profiles.get(sid) or {}
        if profile.get("cash_pressure"):
            signals.append({"kind": "cash_pressure", "ref": next(
                (s["ref"] for s in profile.get("signals", []) if s["kind"] in {"cash_request", "credit_worsening"}),
                None), "detail": "cash signal in profile"})
        kinds = {s["kind"] for s in signals}
        tactics = []
        if "free_capacity" in kinds or "cash_pressure" in kinds:
            tactics.append("deepest_ask")
        if "cash_pressure" in kinds and "payment_days" in case["negotiable"]:
            tactics.append("price_early_payment")
        if profile.get("stale_costing"):
            tactics.append("request_cost_breakdown")
        if "full_order_book" in kinds:
            tactics.append("price_reference_only")
        rows.append({"supplier_id": sid, "motivation": sum(MOTIVATION.get(k, 0) for k in kinds),
                     "signals": signals, "tactics": tactics})
    return sorted(rows, key=lambda r: (-r["motivation"], r["supplier_id"]))


def _reprice(case, standard, plan, target):
    """Re-price a plan's packages to a lower total-cost target; drop mixes that cannot reach it."""
    out = []
    for package in plan["packages"]:
        mix = {k: v for k, v in package["terms"].items() if k != "unit_price"}
        price = price_for_cost(case, standard, mix, target, high=2 * package["terms"]["unit_price"])
        if price:
            terms = {**mix, "unit_price": min(price, package["terms"]["unit_price"])}
            out.append({**package, "terms": terms, "estimated_total_cost": total_cost(case, terms, standard)})
    return out


def plan_rfq(case, threads, standards, profiles=None):
    """Per live thread: planner packages held to one case-level market target.

    Each thread's own plan anchors on its own quote, which lets a high opener off lightly. In an RFQ
    every bidder is asked to meet the most ambitious thread target (the market), and no thread ever
    concedes beyond the best acceptable rival bid (EUR 1 margin on total cost)."""
    profiles = profiles or {}
    plans = {}
    for sid in live(threads):
        try:
            plans[sid] = plan_packages(case, standards[sid], threads[sid], profiles.get(sid))
        except ValueError as exc:
            plans[sid] = {"packages": [], "error": str(exc)}
    targets = [p["target_cost"] for p in plans.values() if p.get("packages")]
    market = min(targets) if targets else None
    for sid, plan in plans.items():
        if not plan.get("packages"):
            continue
        cap = rival_benchmark(case, threads, standards, sid)
        plan["rival_benchmark"], plan["market_target"] = cap, market
        # The common market target is for a bidder's FIRST message only (D02: asks to a bidder that
        # kept moving stayed stuck at the most ambitious target). Afterwards each thread follows its
        # own concession path, still never conceding beyond the best real rival bid.
        first = not any(e.get("from") == "buyer" for e in threads[sid])
        goal = min(t for t in (market if first else None, None if cap is None else cap - 1.0) if t is not None) \
            if (first or cap is not None) else plan["target_cost"]
        if goal < plan["target_cost"]:
            repriced = _reprice(case, standards[sid], plan, goal)
            if repriced:
                plan.update(packages=repriced, target_cost=round(goal, 2), recommend_accept=False,
                            held_to_market=True)
    return plans


def close_decision(case, threads, standards, plans, moves_left=None):
    """One case-level decision: accept the cheapest acceptable primary, or None to keep going.

    Accept when that bidder's planner recommends it, when every live thread is at final_offer or out
    of moves, or when no thread has packages left to send. Never accept a deal worse than the case
    alternative; with no acceptable offer and nothing left to send, walk away (no-deal = alternative)."""
    offers = acceptable_offers(case, threads, standards)
    alt = case["buyer"].get("alternative") or {}
    c_alt = total_cost(case, alt["terms"]) if alt.get("terms", {}).get("unit_price") else math.inf
    moves_left = moves_left or {}
    exhausted = all(_latest(threads[s]).get("status") == "final_offer" or moves_left.get(s, 1) <= 0
                    for s in live(threads))
    nothing_to_send = all(not (plans.get(s) or {}).get("packages") for s in live(threads))
    if offers and offers[0][0] < c_alt:
        cost, sid, offer_id, _ = offers[0]
        # The best acceptable offer is that bidder's last word (final_offer / agreed): take it now. Waiting
        # for slower bidders let its 60 s clock run out (practice P05, 11 Oct: timeout -> "can't wait
        # around" -> walked away -> our late accept got HTTP 422 -> no deal, score 0).
        settled = _latest(threads[sid]).get("status") in {"final_offer", "agreed"}
        if (plans.get(sid) or {}).get("recommend_accept") or exhausted or nothing_to_send or settled:
            return {"supplier_id": sid, "message": {"action": {"type": "accept", "term_sheet_id": offer_id}},
                    "estimated_total_cost": cost}
        return None
    if exhausted or nothing_to_send:
        target = live(threads)[0] if live(threads) else case["suppliers"][0]
        return {"supplier_id": target, "message": {"action": {"type": "walk_away"}}}
    return None
