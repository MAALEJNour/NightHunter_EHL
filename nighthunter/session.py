"""Bounded observations from the current supplier thread, never from past results."""

import re

from arena_kit.play import moves_left

PRICE_FREEZE = re.compile(
    r"\b(?:froz(?:en|e)(?:\s+\w+){0,4}\s+price\s+reduct|"
    r"price\s+reduct\w*\s+(?:are|is)\s+frozen|price\s+freeze|"
    r"pricing\s+(?:is\s+)?frozen|no\s+(?:further\s+)?price\s+reduct)", re.I)
APPROVAL = re.compile(r"\b(?:pricing committee|approval|approver|decision maker)\b", re.I)
DISMISSAL = re.compile(
    r"\b(?:(?:does|do|did) not change (?:our|the) calculation|"
    r"figures confirm our case|does not affect our price)\b", re.I)
FLEXIBILITY = re.compile(r"\b(?:can talk about|open to|flexib\w*\s+(?:on|about|with))\b", re.I)


def thread_observations(case, events, prior_decisions, supplier_id):
    """Supplier statements are observations, not verified costs or binding promises."""
    replies = [event for event in events if event.get("from") != "buyer"]
    current = replies[-1] if replies else {}
    body = current.get("body") or ""
    flexibility = FLEXIBILITY.search(body)
    if flexibility and re.search(r"\b(?:not|cannot|can't)\s+$", body[max(0, flexibility.start() - 16):
                                                         flexibility.start()], re.I):
        flexibility = None
    excerpt = body[flexibility.start():flexibility.start() + 180] if flexibility else ""
    fields = []
    for term, names in (("payment", ("payment_days",)),
                        ("volume", ("volume_per_year",)),
                        ("contract length", ("contract_months",)),
                        ("duration", ("contract_months",))):
        for match in re.finditer(re.escape(term), excerpt, re.I):
            prefix = excerpt[max(0, match.start() - 12):match.start()]
            if not re.search(r"\b(?:not|no)\s+$", prefix, re.I):
                fields.extend(name for name in names if name in case["negotiable"] and name not in fields)
    last_decision = next((d for d in reversed(prior_decisions)
                          if d.get("executed", {}).get("supplier_id") == supplier_id
                          and d.get("validation")), None)
    sent_cards = (last_decision or {}).get("validation", {}).get("selected_claims", [])
    results = []
    for item in current.get("claim_results") or []:
        index = item.get("index")
        results.append({"claim_id": sent_cards[index] if isinstance(index, int) and 0 <= index < len(sent_cards)
                        else None, "result": item.get("result")})
    recent = []
    for message in replies[-2:]:
        sheets = message.get("term_sheets") or []
        if sheets:
            recent.append({"term_sheet_id": sheets[0].get("term_sheet_id"),
                           "terms": sheets[0].get("terms"), "status": message.get("status"),
                           "currently_active": message is current})
    return {"supplier_message_id": current.get("message_id"),
            "price_freeze_reported": bool(PRICE_FREEZE.search(body)),
            "approval_reported": bool(APPROVAL.search(body)),
            "flexible_fields_reported": fields,
            "recent_claim_results": results,
            "recent_claims_dismissed_in_prose": sent_cards if DISMISSAL.search(body) else [],
            "recent_primary_offers": recent,
            "buyer_messages_left": moves_left(case, events),
            "interpretation": "Current-thread supplier statements only. A verified claim can still fail to persuade. "
                              "A stated freeze or dismissal is not a known supplier floor."}


def is_price_only_cut(case, standing_terms, requested):
    """A pure lower-price repeat changes no other negotiated field."""
    terms = requested.get("terms", requested) if isinstance(requested, dict) else None
    return bool(isinstance(terms, dict)
                and isinstance(terms.get("unit_price"), (int, float))
                and not isinstance(terms["unit_price"], bool)
                and terms["unit_price"] < standing_terms["unit_price"]
                and all(terms.get(field) == standing_terms.get(field)
                        for field in case["negotiable"] if field != "unit_price"))
