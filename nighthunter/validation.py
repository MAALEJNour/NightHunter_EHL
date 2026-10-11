"""Auditable claim cards and exact offer validation for controlled prompt comparisons.

The LLM selects verified cards and commercial packages; code renders their factual sentences.
This deliberately avoids claiming to validate arbitrary natural-language arithmetic.
"""

import math
import re
from datetime import date

from arena_kit.cost import must_haves_ok

GREETINGS = {
    "polite": "Thank you for reviewing our proposal.",
    "partnership": "We value our partnership and would like to reach a workable agreement.",
    "firm": "We would like to resolve the remaining commercial points.",
}
REQUESTS = {
    "counteroffer": "Please consider the following alternative packages and confirm your preferred option.",
    "cost_breakdown": "Could you share a cost breakdown to help us understand the proposed adjustment?",
    "approval": "Could you ask the person responsible for approving these terms to review the proposal?",
    "clarify": "Which of these terms offers the most scope for a mutually beneficial adjustment?",
}

# Supplier correspondence patterns (any supplier): material cost hedged until a date; owner's open-book offer.
HEDGE = re.compile(r"our ([\w ,&-]{3,40}?) requirements? (?:is|are) covered at fixed prices until ([A-Z][a-z]+ \d{4})")
OPEN_BOOK = re.compile(r"offered to walk us through (?:their|his|her|our) calculation \(([^)]{3,80})\)")


def month_number(value):
    year, month = map(int, value.split("-")[:2])
    return year * 12 + month


def claim_cards(case, dossier, facts, sid):
    """Only applicable, source-backed values; context rows alone are not verified claims."""
    cards = {}
    parts = set(case["parts"])
    refs = set(case.get("refs", []))
    alternative = case["buyer"].get("alternative") or {}
    if alternative.get("ref"):
        refs.add(alternative["ref"])

    def add(key, text, sources, stance="neutral_unknown", reason="No verified buyer advantage",
            disclosure="shareable"):
        cards[key] = {"text": text, "refs": sources, "stance": stance,
                      "reason": reason, "disclosure": disclosure}

    trigger = case.get("trigger_doc")
    notice = facts.get(trigger, {})
    for ref in sorted(refs):
        fact = facts.get(ref, {})
        if ref.startswith("quote:") and fact.get("part") in parts and fact.get("supplier") != sid:
            if isinstance(fact.get("unit_price"), (int, float)):
                add(f"quote:{ref}", f"The alternative supplier quoted EUR {fact['unit_price']:.2f} "
                    f"per price unit for this part ({ref}); its other terms must also be considered.", [ref],
                    reason="A unit price alone cannot rank complete competing packages",
                    disclosure="internal_only")
        if ref.startswith("ctr:") and notice.get("supplier") == sid and fact.get("supplier") == sid:
            if isinstance(notice.get("days"), (int, float)) and isinstance(fact.get("days"), (int, float)):
                notified = notice.get("date")
                if notified and (fact.get("valid_from") or notified) <= notified <= (fact.get("valid_to") or notified):
                    short = notice["days"] < fact["days"]
                    add("notice", f"The letter gives {notice['days']} days of notice ({trigger}), "
                        f"while the agreement requires {fact['days']} days ({ref}).", [trigger, ref],
                        "buyer_leverage" if short else "neutral_unknown",
                        "Notice is shorter than the applicable contract minimum" if short else
                        "Notice meets or exceeds the contract minimum; no breach implied")

    # Candidates must be present in the selected dossier, not arbitrary database knowledge.
    included = {e["row"].get("id", e["source"]): e for e in dossier["evidence"]}
    forecast_by_part = {}
    for ref in included:
        fact = facts.get(ref, {})
        if ref.startswith("fc:") and fact.get("part") in parts and "change_pct" in fact:
            part = fact["part"]
            if ref > forecast_by_part.get(part, ""):
                forecast_by_part[part] = ref
    for part, ref in forecast_by_part.items():
        change = float(facts[ref]["change_pct"])
        add(f"forecast:{part}", f"The recorded demand forecast change is {change:+.1f}% ({ref}).", [ref])

    for ref in sorted(included):
        fact = facts.get(ref, {})
        if ref.startswith("cost:") and fact.get("part") in parts and "unit_cost" in fact:
            # Shareable only below the price we pay today: then it argues against any increase
            # (teammate P01/P10: "we checked the should cost data you cited; it holds and we took it
            # into account"). Above today's price it would support the supplier's case.
            current = case["buyer"].get("current_unit_price")
            below = isinstance(current, (int, float)) and fact["unit_cost"] < current
            add(f"estimate:{ref}", f"Our cost estimate for this part is EUR {fact['unit_cost']:.2f} "
                f"per price unit ({ref}); this is an estimate, not your disclosed actual cost.", [ref],
                "buyer_leverage" if below else "supplier_supporting",
                "Estimate below the price we pay today" if below else
                "Internal uncertain estimate, not a supplier-disclosed cost or floor",
                disclosure="shareable" if below else "internal_only")
        if ref.startswith("sc:") and fact.get("supplier") == sid and ref in refs:
            # A weak record is leverage (contracts set a 95 % on-time target; hundreds of PPM is poor for
            # machined/cast parts); a good one is neutral and never forced.
            # One scorecard ID counts once per case (S11 P11: the delivery fact used it, so the quality
            # fact - the case's key argument - could never be cited). Quality first when it is poor.
            poor_quality = fact.get("ppm") is not None and fact["ppm"] >= 1000
            if "otd_pct" in fact and not poor_quality:
                weak = fact["otd_pct"] < 95
                add("delivery", f"The supplier scorecard records on-time delivery of {fact['otd_pct']:.1f}% "
                    f"against requested dates ({ref}).", [ref], "buyer_leverage" if weak else "neutral_unknown",
                    "On-time delivery below the 95 % target" if weak else "No verified buyer advantage")
            if "ppm" in fact:
                weak = fact["ppm"] >= 1000
                add("quality", f"The supplier scorecard records {fact['ppm']} PPM ({ref}).", [ref],
                    "buyer_leverage" if weak else "neutral_unknown",
                    "Defect rate of 1000 PPM or more" if weak else "No verified buyer advantage")

    # What we actually pay: 2-8 order lines of this part from this supplier at one price (the arena
    # checks "the order prices"; same-part lines are one argument). Never cited in saved runs.
    if len(parts) == 1:
        lines = sorted(((facts[r].get("date") or "", r) for r in included if r.startswith("po:")
                        and facts.get(r, {}).get("part") in parts and facts[r].get("supplier") == sid
                        and isinstance(facts[r].get("unit_price"), (int, float))), reverse=True)
        if lines:
            price = facts[lines[0][1]]["unit_price"]
            same = [r for _, r in lines if facts[r]["unit_price"] == price][:4]
            if len(same) >= 2:
                # S10: "it holds, but it does not change our calculation" in 8 of 8 cases; it only used
                # a claim slot (max 3 checks per message). Kept for the model's context, never sent.
                add("orders", f"Our last {len(same)} orders for this part were placed at EUR {price:.2f} "
                    f"per price unit ({', '.join(same)}).", same, "neutral_unknown",
                    "S10: no effect on any supplier", disclosure="internal_only")

    # The supplier's own words in its correspondence (no one cited these in ~90 saved P08/P18 runs; the
    # supplier only used its hedge letter to rebut OUR index claims): its material cost is fixed until a
    # date, and its owner offered an open-book walk-through of the calculation.
    for e in dossier["evidence"]:
        row, text = e.get("row") or {}, e.get("document") or ""
        if e.get("table") != "documents" or row.get("supplier_id") != sid or not row.get("id"):
            continue
        ref, day = row["id"], row.get("date")
        hedge = HEDGE.search(text)
        if hedge and "hedge" not in cards:
            add("hedge", f"Your letter of {day} ({ref}) states that your {hedge.group(1).strip()} requirement is "
                f"covered at fixed prices until {hedge.group(2)} and that market movements reach your costs "
                f"only after that.", [ref], "supplier_supporting",
                "Two-sided: S8 P08 used it to make an index clause mandatory for long contracts (57.0 vs 67.9)")
        book = OPEN_BOOK.search(text)
        if book and "open_book" not in cards:
            add("open_book", f"In our call on {day} ({ref}) your owner offered to walk us through your "
                f"calculation ({book.group(1).strip()}); we would like to take up that offer.", [ref],
                "neutral_unknown", "Context only (a call-note ID is not checked); S8: no price effect")

    series = {e["row"]["series_id"] for e in dossier["evidence"] if e["table"] == "cost_drivers"}
    latest_data_month = max((month_number(f["month"]) for f in facts.values()
                             if isinstance(f, dict) and f.get("month") and f.get("series")), default=0)
    for name in sorted(series):
        observations = sorted((f["month"], ref, f["value"]) for ref, f in facts.items()
                              if ref in included and ref.startswith("idx:") and f.get("series") == name)
        if len(observations) < 2:
            continue
        end, end_ref, end_value = observations[-1]
        valid = [r for r in observations[:-1] if 0 < month_number(end) - month_number(r[0]) <= 12]
        if not valid or latest_data_month - month_number(end) > 12:
            continue
        start, start_ref, start_value = valid[0]
        if start_value <= 0:
            continue
        delta = (end_value / start_value - 1) * 100
        stance = "supplier_supporting" if delta > 0 else "buyer_leverage" if delta < 0 else "neutral_unknown"
        reason = ("This relevant cost driver rose; it may support the supplier's cost case" if delta > 0
                  else "This driver fell; its weight and other rising costs still matter" if delta < 0
                  else "No change in this driver")
        add(f"index:{name}", f"The {name} index changed {delta:+.1f}% between {start} and {end} "
            f"({start_ref}, {end_ref}).", [start_ref, end_ref], stance, reason)
    return cards


def available_claim_cards(cards, used_refs=(), filter_used=False):
    """Keep internal estimates and seller-supporting claims out of outgoing choices."""
    used = set(used_refs)
    return {key: card for key, card in cards.items()
            if card.get("disclosure", "shareable") == "shareable"
            and card.get("stance", "neutral_unknown") != "supplier_supporting"
            and (not filter_used or not set(card["refs"]) & used)}


def validate_sheets(case, sheets, standard):
    if not isinstance(sheets, list) or len(sheets) > 3:
        raise ValueError("Expected at most three term sheets")
    result = []
    for sheet in sheets:
        terms = sheet.get("terms", sheet) if isinstance(sheet, dict) else None
        if not isinstance(terms, dict) or set(terms) != set(case["negotiable"]):
            raise ValueError("Term sheet must contain exactly all negotiable fields")
        price = terms.get("unit_price")
        if isinstance(price, bool) or not isinstance(price, (int, float)) or not math.isfinite(price) or price <= 0:
            raise ValueError("Invalid unit price")
        if abs(price - round(price, 2)) > 1e-8:
            raise ValueError("Unit price must have at most two decimals")
        for field, value in terms.items():
            if field == "unit_price":
                continue
            if isinstance(value, bool):
                raise ValueError("Boolean is not a commercial term value")
            allowed = case.get("term_options", {}).get(field, [])
            if value not in allowed and (field not in standard or value != standard[field]):
                raise ValueError(f"Unsupported value for {field}")
            if field == "effective_date" and value:
                date.fromisoformat(value)
        if not must_haves_ok(case, terms, standard):
            raise ValueError("Proposed terms violate must-haves")
        if terms not in result:
            result.append(terms)
    return result


def render_message(proposal, cards, used_refs, case, standard):
    """Never send unverified model prose. Render only approved choices and exact terms."""
    sheets = validate_sheets(case, proposal.get("term_sheets", []), standard)
    tone = proposal.get("tone", "polite")
    intent = proposal.get("intent", "counteroffer")
    if tone not in GREETINGS or intent not in REQUESTS:
        raise ValueError("Unknown message tone or intent")
    ids = proposal.get("claim_ids", [])
    if not isinstance(ids, list) or len(ids) > 3 or any(not isinstance(i, str) or i not in cards for i in ids):
        raise ValueError("Unknown claim card or too many claims")
    selected, dropped, refs = [], [], []
    for key in dict.fromkeys(ids):
        card = cards[key]
        if card.get("disclosure", "shareable") != "shareable" or card.get("stance") == "supplier_supporting":
            raise ValueError("Claim card is not available for supplier disclosure")
        if set(card["refs"]) & (set(used_refs) | set(refs)):
            dropped.append(key)
            continue
        selected.append(key)
        refs += card["refs"]
    lines = [GREETINGS[tone], *[cards[key]["text"] for key in selected], REQUESTS[intent]]
    for i, terms in enumerate(sheets, 1):
        entries = [f"{field}={value}" for field, value in terms.items()]
        lines.append(f"Package {i}: " + "; ".join(entries) + ".")
    body = "\n\n".join(lines)
    return {"subject": f"Re: {case['title']}", "body": body, "refs": refs,
            "term_sheets": [{"terms": t} for t in sheets]}, {
                "selected_claims": selected, "duplicate_claims_omitted": dropped,
                "model_prose_discarded": bool(proposal.get("body")),
            }
