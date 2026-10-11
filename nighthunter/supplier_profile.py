"""Supplier read-out before round 1: signals from the dossier, each with its source ID.

Pattern matches on notes, letters, contracts, intel and negotiation history. Each signal is an
observation for choosing a tactic, not a fact about the supplier's costs, floor or authority.
Only public case/dossier data; never post-session results or replays.
"""

import re
import statistics
from datetime import date

APPROVAL = re.compile(r"(?:price )?changes? above (\d+(?:\.\d+)?)\s*%.{0,60}?(?:approval|committee)", re.I | re.S)
FREEZE = re.compile(r"froz\w*\s+(?:all\s+)?price reductions|no room on price|price freeze|"
                    r"(?:no longer grant|ruled out|no) individual price reductions|"
                    r"applies to all customers without exception", re.I)
OPEN_ON = re.compile(r"open (?:on|to) ([^.]+)", re.I)
CASH = re.compile(r"pay (?:our )?invoices within \d+ days|cash discount|skonto|liquidity|cash flow|"
                  r"bank is watching|short-time work|help us most now is cash", re.I)
# Sunday-release news topics about a supplier (news.csv `topic`): what they mean for the negotiation.
NEWS_CASH = {"insolvency", "credit_downgrade"}
NEWS_GROUP_PRICING = re.compile(r"prices? (?:will be|are) set centrally", re.I)
STALE_COSTING = re.compile(r"spreadsheet[^.]*(?:updated|old)|not followed his [^.]*prices", re.I)
PARTNERSHIP = re.compile(r"expects? partnership|kept supplying at the old price", re.I)
FIXED_YEAR = re.compile(r"fixed for each calendar year.*?notice of at least (\d+) days", re.I | re.S)
TERM_WORDS = {"payment": "payment_days", "call-off": "volume_per_year", "volume": "volume_per_year",
              "duration": "contract_months", "contract length": "contract_months"}


def _ref(item):
    source = item.get("source") or ""
    return source.split(":", 1)[1] if ":" in source else source


def _documents(dossier, sid):
    """Only this supplier's documents: RFQ dossiers hold several suppliers' notes."""
    number = sid.split(":", 1)[-1]
    for item in dossier.get("evidence", []):
        text = item.get("document")
        if text and (sid in text or (item.get("row") or {}).get("supplier_id") == sid
                     or re.search(rf"(?<!\d){re.escape(number)}(?!\d)", _ref(item))):
            yield item, text


SESSION_CASH = re.compile(r"faster payment|earlier payment|pay(?:ing)? (?:us )?(?:faster|earlier|sooner)|"
                          r"cash ?flow|liquidity|shorter payment", re.I)


SESSION_AUTHORITY = re.compile(r"(?:fully|full) authori[sz]|hold (?:the )?full authority|authori[sz]ed to (?:decide|"
                               r"negotiate)|my (?:own )?decision|escalation (?:will not|won't|is unnecessary)", re.I)


def session_signals(events):
    """Signals the supplier states in this thread (within-session memory, never across sessions).

    S1 P11: the supplier asked for faster payment five times while we never offered it."""
    bodies = " ".join(e.get("body") or "" for e in events if e.get("from") != "buyer")
    out = {"cash_pressure": True} if SESSION_CASH.search(bodies) else {}
    if SESSION_AUTHORITY.search(bodies):
        out["authority_claimed"] = True  # S1 P07 / A2 P10: we kept asking for approval regardless
    return out


def build_profile(case, dossier, sid):
    """Tactical signals for one supplier; every entry carries its source reference."""
    profile = {"supplier_id": sid, "signals": [], "tactics": []}

    def signal(kind, ref, detail):
        profile["signals"].append({"kind": kind, "ref": ref, "detail": detail})

    for item, text in _documents(dossier, sid):
        ref = _ref(item)
        if m := APPROVAL.search(text):
            profile["approval_threshold_pct"] = float(m.group(1))
            signal("approval_threshold", ref, m.group(0))
        if FREEZE.search(text):
            profile["price_freeze"] = True
            signal("price_freeze", ref, FREEZE.search(text).group(0))
            if m := OPEN_ON.search(text):
                fields = sorted({f for w, f in TERM_WORDS.items()
                                 if w in m.group(1).lower() and f in case["negotiable"]})
                profile["open_fields"] = sorted(set(profile.get("open_fields", [])) | set(fields))
                signal("open_terms", ref, m.group(0))
        if CASH.search(text):
            profile["cash_pressure"] = True
            signal("cash_request", ref, CASH.search(text).group(0))
        if STALE_COSTING.search(text):
            profile["stale_costing"] = True
            signal("stale_costing", ref, STALE_COSTING.search(text).group(0))
        if PARTNERSHIP.search(text):
            profile["relationship_appeal"] = True
            signal("relationship_appeal", ref, PARTNERSHIP.search(text).group(0))
        if item.get("table") == "contracts" and (m := FIXED_YEAR.search(text)):
            profile["contract_price_fixed_per_year"] = {"ref": ref, "notice_days": int(m.group(1))}

    rows = [i for i in dossier.get("evidence", []) if (i.get("row") or {}).get("supplier_id") == sid]
    for item in rows:
        row = item["row"]
        if item.get("table") == "news":
            if row.get("topic") in NEWS_CASH:
                profile["cash_pressure"] = True
                profile["supply_risk"] = True  # insolvency / no credit cover: secure supply, never prepay
                signal(f"news_{row['topic']}", _ref(item), row.get("headline"))
            if NEWS_GROUP_PRICING.search(row.get("body") or ""):
                profile["price_freeze"] = True
                signal("news_group_pricing", _ref(item), row.get("headline"))
        if item.get("table") == "supplier_intel":
            profile["intel"] = {k: row.get(k) for k in ("owner_type", "credit_index", "credit_index_12m_ago",
                                                       "equity_ratio_pct", "staff", "group_parent")}
            if (row.get("credit_index") or 0) > (row.get("credit_index_12m_ago") or 0) + 15:
                profile["cash_pressure"] = True
                signal("credit_worsening", _ref(item), f"credit index {row['credit_index_12m_ago']}"
                       f" -> {row['credit_index']}")
        if item.get("table") == "should_cost" and row.get("part_id") in case.get("parts", []) \
                and len(case.get("parts", [])) == 1 and isinstance(row.get("unit_cost"), (int, float)):
            profile["should_cost"] = {"unit_cost": float(row["unit_cost"]), "ref": _ref(item),
                                      "confidence_pct": row.get("confidence_pct"),
                                      "use": "internal estimate only; never disclose or cite as the supplier's cost"}
        if item.get("table") == "scorecards" and isinstance(row.get("ppm"), (int, float)):
            if row.get("quarter", "") >= profile.get("observed_ppm", {}).get("quarter", ""):
                # Its real defect rate: what a chargeback actually costs it (S2 P11: a EUR 500
                # chargeback valued at zero made every option carry it; the supplier raised price).
                profile["observed_ppm"] = {"ppm": row["ppm"], "quarter": row.get("quarter"), "ref": _ref(item)}
    history = [i["row"] for i in rows if i.get("table") == "negotiation_history"
               and isinstance(i["row"].get("asked_pct"), (int, float))
               and isinstance(i["row"].get("settled_pct"), (int, float))]
    if history:
        gaps = [h["asked_pct"] - h["settled_pct"] for h in history]
        profile["history"] = {"events": len(history), "median_asked_minus_settled_pp": statistics.median(gaps),
                              "settled_below_ask_every_time": all(g > 0 for g in gaps),
                              "notes": sorted({h["note"] for h in history if h.get("note")})}

    _trigger_checks(case, dossier, profile)
    _tactics(case, profile)
    return profile


def _trigger_checks(case, dossier, profile):
    """Compare a price letter with the contract's calendar-year clause. Compliance is not leverage."""
    clause = profile.get("contract_price_fixed_per_year")
    letter = next((i["citable_fact"] for i in dossier.get("evidence", [])
                   if _ref(i) == case.get("trigger_doc") and i.get("citable_fact")), None)
    if not clause or not letter or not letter.get("effective_date") or not letter.get("date"):
        return
    effective = date.fromisoformat(letter["effective_date"])
    sent = date.fromisoformat(letter["date"])
    year_end = date(sent.year, 12, 31)
    check = {"letter_ref": case["trigger_doc"], "contract_ref": clause["ref"],
             "notice_days_given_to_year_end": (year_end - sent).days,
             "notice_days_required": clause["notice_days"],
             "notice_compliant": (year_end - sent).days >= clause["notice_days"],
             "mid_year_effective_date": (effective.month, effective.day) != (1, 1)}
    if letter.get("asked_pct") is not None:
        check["asked_pct"] = letter["asked_pct"]
    profile["trigger_check"] = check


def _tactics(case, profile):
    tactics = profile["tactics"]
    check = profile.get("trigger_check", {})
    if check.get("mid_year_effective_date") and "effective_date" in case["negotiable"]:
        tactics.append({"tactic": "defer_effective_date", "refs": [check["contract_ref"], check["letter_ref"]],
                        "why": "Contract fixes prices per calendar year; the letter moves price mid-year."})
    if profile.get("approval_threshold_pct") is not None:
        tactics.append({"tactic": "request_approval", "threshold_pct": profile["approval_threshold_pct"],
                        "why": "Moves beyond the stated threshold need the approver: ask for escalation "
                               "rather than repeating requests the rep cannot grant."})
    if profile.get("price_freeze"):
        tactics.append({"tactic": "trade_non_price_terms", "fields": profile.get("open_fields", []),
                        "why": "Stated price freeze; seek value through the terms it reported as open."})
    if profile.get("cash_pressure") and "payment_days" in case["negotiable"]:
        tactics.append({"tactic": "price_early_payment", "why": "Cash signal: offer earlier payment only "
                        "where the price cut exceeds our financing cost (equal-cost menu)."})
    elif "payment_days" in case["negotiable"]:
        tactics.append({"tactic": "ask_longer_payment", "why": "No cash-pressure signal: longer payment "
                        "is likely cheaper for the seller than for us to forgo."})
    if profile.get("stale_costing"):
        tactics.append({"tactic": "request_cost_breakdown", "why": "Owner reported outdated costing: ask "
                        "for the cost breakdown and compare with current verified index values."})
    if profile.get("relationship_appeal"):
        tactics.append({"tactic": "acknowledge_partnership", "why": "Supplier values reciprocity; "
                        "acknowledge it explicitly while trading terms."})
