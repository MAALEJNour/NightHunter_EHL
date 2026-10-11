"""Expert negotiation e-mails: code renders every figure, the model writes checked framing.

Numbers, IDs, terms and factual sentences come only from code (planned packages, checked claim
cards, our own previous asks). The model contributes three short framing paragraphs - respond to
the supplier, explain the give-and-take, ask one question - that may contain NO digits, IDs,
currency or percentages, and none of the banned content below. A paragraph that fails the check is
dropped (and logged), never repaired. This is a content filter, not semantic validation of prose.

Grounding: multiple equivalent simultaneous offers (Harvard PON), labelled concessions and an
explicit "near our limit" signal (HBS/PON), plus Batch A-A3 replays: answer the supplier's question,
acknowledge its argument, do not escalate to a self-declared decision maker, do not lower an ask on
comparable terms, avoid robotic field dumps.
"""

import re
from datetime import date

MAX_FIELD = 380
BANNED = [
    (re.compile(r"\d"), "digits"),
    (re.compile(r"[€%$£]|\beur\b|\beuros?\b|percent|per cent", re.I), "money_or_percent"),
    (re.compile(r"\b[a-z]{2,8}:[\w-]", re.I), "data_id"),
    (re.compile(r"competit|other (?:supplier|bidder|bid|quote|offer)s?\b|another (?:supplier|bid|quote)|"
                r"second source|alternative (?:supplier|source)|cheaper (?:offer|quote)|market price", re.I),
     "competition_claim"),
    (re.compile(r"budget|urgen|deadline|no (?:other )?alternative|only option|desperate", re.I), "leakage"),
    (re.compile(r"walk away|terminat|switch(?:ing)? supplier|legal action|lawyer|penalt", re.I), "threat"),
    (re.compile(r"(?:additional|more|higher|future|further) (?:volume|business|orders|projects)|"
                r"new projects|future orders", re.I), "future_commitment"),
    (re.compile(r"your (?:costs? (?:are|is)|margin)|should[- ]cost|our (?:estimate|analysis) of your", re.I),
     "supplier_cost_claim"),
    (re.compile(r"ignore (?:previous|all)|system prompt|instruction", re.I), "injection"),
]
ESCALATION = re.compile(r"escalat|your (?:manager|boss|superior|management)|committee|approv", re.I)
SIGN_OFF = re.compile(r"(?:mit freundlichen grüßen|viele grüße|freundliche grüße|kind regards|best regards|"
                      r"regards|sincerely)[^\n]*\n+([^\n]+)", re.I)
NAME = re.compile(r"^[A-ZÄÖÜ][a-zäöüß'-]+(?: [A-ZÄÖÜ][a-zäöüß'-]+){1,2}$")


def check_text(text, allow_escalation=False):
    """(clean text or None, reason). Rejects rather than edits."""
    if not isinstance(text, str) or not text.strip():
        return None, "empty"
    text = " ".join(text.split())
    if len(text) > MAX_FIELD:
        return None, "too_long"
    for pattern, reason in BANNED:
        if pattern.search(text):
            return None, reason
    if not allow_escalation and ESCALATION.search(text):
        return None, "escalation"
    return text, None


def _date(value):
    d = date.fromisoformat(value)
    return f"{d.day} {d.strftime('%B')} {d.year}"


def describe_terms(case, terms, price=True):
    """One complete package in plain business language (every negotiable field)."""
    parts = []
    for field in case["negotiable"]:
        value = terms.get(field)
        if field == "unit_price":
            if price:
                parts.insert(0, f"EUR {value:.2f} per unit")
        elif field == "payment_days":
            parts.append(f"payment {value} days net")
        elif field == "effective_date":
            parts.append(f"new price effective {_date(value)}" if value else "price effective immediately")
        elif field == "contract_months":
            parts.append(f"{value}-month agreement")
        elif field == "volume_per_year":
            parts.append(f"{value} pcs per year")
        elif field == "lead_time_days":
            parts.append(f"lead time {value} days")
        elif field == "index_clause":
            parts.append("fixed price, no index clause" if not value else
                         f"{value['series']} index clause on {value['material_share'] * 100:g} % material share, "
                         f"{value['deadband_pct']:g} % deadband, base {value['base_month']}")
        elif field == "ppm_commitment":
            parts.append(f"quality commitment {value} ppm")
        elif field == "chargeback_eur_per_complaint":
            parts.append(f"EUR {value:.0f} per supplier-caused complaint")
        elif field == "incoterm":
            parts.append(f"delivery {value}")
        elif field == "tooling_eur":
            parts.append(f"tooling EUR {value:.0f}")
        else:
            parts.append(f"{field.replace('_', ' ')} {value}")
    return ", ".join(parts)


def _mix(terms):
    return tuple(sorted((k, str(v)) for k, v in terms.items() if k != "unit_price"))


def concession_line(case, events, packages):
    """Label our largest price step on an unchanged mix since our previous message (code figures)."""
    previous = {}
    for event in events:
        if event.get("from") == "buyer":
            for sheet in event.get("term_sheets") or []:
                terms = sheet.get("terms", sheet)
                if isinstance(terms.get("unit_price"), (int, float)):
                    previous[_mix(terms)] = terms["unit_price"]
    steps = [(p["unit_price"] - previous[_mix(p)], previous[_mix(p)], p) for p in packages
             if _mix(p) in previous and p["unit_price"] > previous[_mix(p)]]
    if not steps:
        return None
    _, before, terms = max(steps, key=lambda s: s[0])
    return (f"To move this forward we have raised our price on the option with "
            f"{describe_terms(case, terms, price=False)} "
            f"from EUR {before:.2f} to EUR {terms['unit_price']:.2f} per unit - a real step for us.")


def salutation(events):
    """'Dear <full name>,' from the supplier's latest sign-off; no gender is inferred."""
    for event in reversed(events):
        if event.get("from") != "buyer":
            match = SIGN_OFF.search(event.get("body") or "")
            name = match.group(1).strip() if match else ""
            return f"Dear {name}," if NAME.match(name) else "Good day,"
    return "Good day,"


def compose(case, events, packages, card_texts, choice, request_line, *, allow_escalation=False,
            near_limit=False, require_request=False):
    """Full e-mail body plus diagnostics. `packages`: exact planned terms (validated elsewhere)."""
    diagnostics, framing = {}, {}
    for key in ("opening", "rationale", "closing"):
        text, reason = check_text((choice or {}).get(key), allow_escalation)
        framing[key] = text
        if reason and reason != "empty":
            diagnostics[f"{key}_dropped"] = reason
    lines = [salutation(events)]
    if framing["opening"]:
        lines.append(framing["opening"])
    lines += list(card_texts)
    if framing["rationale"]:
        lines.append(framing["rationale"])
    if label := concession_line(case, events, packages):
        lines.append(label)
        diagnostics["concession_labelled"] = True
    if len(packages) == 1:
        lines.append("Our proposal: " + describe_terms(case, packages[0]) + ".")
    else:
        lines.append("We offer the following options; each of them works for us:")
        lines += [f"Option {chr(65 + i)}: {describe_terms(case, t)}." for i, t in enumerate(packages)]
    if near_limit:
        lines.append("We are now close to the limit of what we can approve.")
        diagnostics["near_limit_signal"] = True
    # A code-required request (e.g. the cost breakdown) must survive a model-written closing (S13 P08:
    # the model's own closing question replaced it and the breakdown was never asked).
    lines.append(framing["closing"] or request_line)
    if require_request and framing["closing"] and request_line not in framing["closing"]:
        lines.append(request_line)
        diagnostics["required_request"] = True
    lines.append("Kind regards,\nPurchasing, Hollerau Pumpenwerke GmbH")
    return "\n\n".join(lines), diagnostics
