"""Bounded, advisory package search using public case data and current-thread offers.

Never reads post-session results, hidden floors or previous practice outcomes. Candidate
prices are requests, not predictions of acceptance. The existing validator still closes deals.
"""

import itertools
import math

from arena_kit.cost import closing_terms, cost_breakdown, must_haves_ok, total_cost
from arena_kit.docs import standard_terms
from arena_kit.play import latest, moves_left

from .context import encoded
from .validation import validate_sheets


def supplier_estimate(case, dossier, sid, standard):
    """Use only an unambiguous estimate for this supplier AND this case's single part."""
    if len(case["parts"]) != 1:
        return None
    rows = [e["row"] for e in dossier["evidence"] if e["table"] == "should_cost"
            and e["row"].get("supplier_id") == sid
            and e["row"].get("part_id") == case["parts"][0]]
    if not rows:
        return None
    row = max(rows, key=lambda r: r.get("estimate_date", ""))
    cost = float(row["unit_cost"])
    if not math.isfinite(cost) or cost <= 0:
        return None
    return {"full_cost": cost, "interest_rate": 0.12,
            "standard": closing_terms(case, {}, standard)}


def central_cost(case, terms, standard, supplier):
    return total_cost(case, terms, standard, supplier)


def trajectory(case, events, supplier):
    """Recompute observations from this thread only; never infer a hidden reservation price."""
    offers = []
    for i, event in enumerate(events):
        if event.get("from") == "buyer":
            continue
        std = standard_terms(events[:i + 1])
        for sheet in (event.get("term_sheets") or [])[:1]:
            terms = sheet["terms"]
            if terms.get("unit_price"):
                offers.append({"terms": terms, "status": event.get("status"),
                               "estimated_cost": central_cost(case, terms, std, supplier)})
    gains = [round(a["estimated_cost"] - b["estimated_cost"], 2)
             for a, b in itertools.pairwise(offers)]
    return {"supplier_offers": offers, "cost_improvements_between_replies": gains,
            "consecutive_no_improvement": next((i for i, g in enumerate(reversed(gains)) if g > 0), len(gains)),
            "messages_left": moves_left(case, events), "status": latest(events).get("status"),
            "interpretation": "Observed responses, not a learned floor; costs include uncertain estimates."}


def advise(case, dossier, sid, terms, standard, events):
    supplier = supplier_estimate(case, dossier, sid, standard)
    current = closing_terms(case, terms, standard)
    memory = trajectory(case, events, supplier)
    price = current.get("unit_price")
    if not isinstance(price, (int, float)) or not math.isfinite(price) or price <= 0:
        return {"trajectory": memory, "candidates": [], "limitation": "No priced standing offer"}
    current_cost = central_cost(case, current, standard, supplier)
    fields = [f for f in case["negotiable"] if f != "unit_price"]
    options = []
    for field in fields:
        values = list(case.get("term_options", {}).get(field, []))
        if field in standard and standard[field] not in values:
            values.append(standard[field])
        if not values:
            return {"trajectory": memory, "candidates": [], "limitation": f"No allowed options for {field}"}
        options.append(values)
    combinations = math.prod(len(v) for v in options)
    if combinations > 512:
        return {"trajectory": memory, "candidates": [], "limitation": "More than 512 discrete packages; search skipped"}
    # Fixed exploration grid, not a claim that a supplier will accept a ten-percent cut.
    prices = sorted({round(price * (1 - i / 400), 2) for i in range(41)} | {round(price, 2)})
    rows = []
    for values in itertools.product(*options):
        template = dict(zip(fields, values))
        valid = []
        for requested_price in prices:
            candidate = {**template, "unit_price": requested_price}
            try:
                validate_sheets(case, [candidate], standard)
            except ValueError:
                continue
            cost = central_cost(case, candidate, standard, supplier)
            if math.isfinite(cost):
                valid.append((cost, -requested_price, candidate))
        if not valid:
            continue
        cost, _, candidate = min(valid, key=lambda x: (x[0], x[1]))
        at_current_price = {**template, "unit_price": price}
        scenarios = [cost]
        if supplier:
            scenarios += [central_cost(case, candidate, standard,
                          {**supplier, "full_cost": supplier["full_cost"] * factor}) for factor in (0.95, 1.05)]
        rows.append({"terms": candidate, "estimated_cost": cost,
                     "estimated_saving_vs_standing": round(current_cost - cost, 2),
                     "cost_at_standing_unit_price": central_cost(case, at_current_price, standard, supplier),
                     "estimated_cost_range": [min(scenarios), max(scenarios)],
                     "cost_components": {k: round(v, 2) for k, v in
                                         cost_breakdown(case, candidate, standard, supplier).items() if v}})
    rows.sort(key=lambda r: (r["estimated_cost"], -r["terms"].get("contract_months", 0), encoded(r["terms"])))
    # Show distinct payment/date/security choices, not many near-identical prices.
    selected = []
    for field in fields:
        seen = set()
        for row in rows:
            key = encoded(row["terms"].get(field))
            if key not in seen:
                if row not in selected:
                    selected.append(row)
                seen.add(key)
    for row in rows:
        if all(row["terms"].get(f) == current.get(f) for f in fields) and row not in selected:
            selected.append(row)
            break
    selected = selected[:8]
    alt = case["buyer"].get("alternative") or {}
    alternative_cost = total_cost(case, alt["terms"]) if alt.get("terms", {}).get("unit_price") else None
    return {"standing_cost_estimate": current_cost,
            "standing_must_haves_ok": must_haves_ok(case, current, standard),
            "alternative_cost": alternative_cost,
            "supplier_estimate": {k: v for k, v in (supplier or {}).items() if k != "standard"},
            "trajectory": memory, "discrete_packages_evaluated": len(rows), "candidates": selected,
            "limitations": "Request prices searched from 90% to 100% of standing price in 0.25% steps. "
                           "Not an acceptance forecast or exact optimum. Financing 12% assumed; cost range +/-5%. "
                           "No hidden result/floor supplied. Missing supplier cost means health charge is unestimated."}
