"""Deterministic package planning: what each term is worth to us, and equal-cost offer menus.

Code chooses every number; a model may choose wording and which menu to send. Each round offers
up to three complete term sheets with the SAME estimated total cost to us but different term mixes,
so the supplier's choice reveals what it values (multiple equivalent simultaneous offers). The
target cost concedes slowly from an ambitious anchor towards the standing offer, never reverts to
an earlier, lower ask, and holds when the supplier did not move.

Inputs are public case data, the quote standard terms, the current thread and an optional
supplier profile. Never pass post-session scores, c_best or replay data. The target schedule and
opening cut are negotiation requests, not predictions of what a supplier will accept.
In stabilise/secure_supply cases a supplier-health estimate from the profile's should-cost is included,
so the planner never asks for a cut whose health charge outweighs the saving.
"""

import itertools
import math

from arena_kit.cost import (
    RELATIONSHIP_GOALS,
    closing_terms,
    cost_breakdown,
    must_haves_ok,
    snap,
    supplier_value,
    total_cost,
)

from .supplier_profile import session_signals
from .validation import validate_sheets

MAX_COMPOSITIONS = 512
# Assumed seller cost of money: neutral (our own 8%) unless the profile reports cash pressure.
# An assumption for sizing asks, never a claim about the supplier's finances.
SELLER_RATE, SELLER_RATE_CASH_PRESSED = 0.08, 0.15
FULL_COST_RATIO = 0.985  # offline fit of hosted health charges vs dossier should-cost (see health_estimate)
# Opening ask as a share of the seller's cash value, by the case's public category goal. Offline
# calibration (2026-10-10, 10 practice cases, 30 teammate replays): stabilise optima lay 0.3-2 %
# below the opening price once terms were used; leverage/RFQ optima 15-30 % below, and those
# suppliers kept conceding until a final_offer around round 4-5. Hypothesis, not a live input;
# re-check on unseen cases before trusting it.
# Concession pace by goal: (planned rounds, exponent). Leverage suppliers issued final_offer at
# round 3-4 in every replay (fast, linear); stabilise/routine suppliers were patient (P01 ran 8
# rounds) and the faster pace cost P01 ~10 points twice in Batch A3 (slow, Boulware).
GOAL_PACE = {"leverage": (4, 1.0)}
DEFAULT_PACE = (5, 1.5)
# Concession per round after the opening, as a share of the remaining cost gap to the supplier's
# standing offer. Measured on 79 hosted negotiations (S1 review): steps of 15-30 % of the gap won a
# median 16 % of the gap after the first counter; steps <= 5 % froze the supplier ("one cent is not
# a real move", P11) and steps > 30 % simply conceded. Diminishing, as the negotiation literature
# recommends (signals approach to our limit).
# Hosted S3 vs S2 (same e-mails): the larger 0.30..0.15 schedule the twin preferred cost 7 points on
# P02, P08 and P18 - suppliers agree once our ask crosses a hidden line, so bigger steps overshoot it.
# Back to the S2 schedule that produced our best P02/P08/P18 deals.
GAP_STEPS = (0.25, 0.22, 0.18, 0.15, 0.12, 0.10)
MIN_STEP = 0.10
# Upper bound on one concession: steps > 30 % of the gap simply conceded (79-run review); S2 P01
# mirrored a supplier date+price move with a 49 % step under the earlier 50 % cap.
HEALTH_MARGIN = 0.10  # share of the remaining gap a health-limited mix may exceed the target by
MAX_STEP = 0.50  # S2 value (mirroring a large supplier move); never more than half the gap
STONEWALL_SHARE, REANCHOR_STEP = 0.15, 0.0
OUR_TERMS_OPTION = False  # twin-only evidence so far (LESSONS L23); off until a hosted test supports it  # adaptive re-anchor (off by default; see twin sweep)
# L33: stop offering fixed prices at lengths where the supplier refused one. Off: S7 hosted check
# (P08 62.6 vs S5 67.9, P18 57.5 vs 58.7) showed no gain; kept for later tests.
INDEX_REFUSAL = False
# Reciprocate only supplier price movement below the price we pay today (current_unit_price).
RETREAT_NOT_CONCESSION = False  # S9: P08 47.3 twice (S5 67.9); the bot raised its price after our smaller step
GOAL_MAX_CUT = {"stabilise": 0.06, "quality_first": 0.08, "routine": 0.10,
                "secure_supply": 0.10, "leverage": 0.22}
# Codex rank 3 (default OFF, untested live): among mixes equal in price, seller value and our cost
# that differ only in lead time, offer the slowest lead time within our need instead of the first
# enumerated (P05 28 = 35 days, P10 35 = 42 days at equal cost; suppliers price overtime for speed).
# Opening menus; later rounds keep the preference only if the opening used it (no lead-time flip).
NEED_ALIGNED_LEAD = False
# Codex rank 5 (default OFF, untested live): if the supplier quoted a compliant relaxed-quality mix
# earlier in this session and dropped it from its latest reply, re-offer that quality mix once at the
# same cost target, despite the per-field ratchet. P11: 2/2 such menus won the next step, 0/8 without.
RETAINED_QUALITY_TRADE = False
QUALITY_FIELDS = ("ppm_commitment", "chargeback_eur_per_complaint")


def health_estimate(case, standard, profile):
    """Supplier-health estimate for strategic/bottleneck goals from the dossier should-cost.

    Offline check (2026-10-10, hosted P01/P02/P03 results incl. a EUR 122k charge): a full cost of
    98-98.6 % of the dossier should-cost reproduced every hosted health charge, despite its stated
    5 % confidence. An estimate for sizing asks, never disclosed and never a known supplier floor."""
    estimate = profile.get("should_cost") or {}
    cost = estimate.get("unit_cost")
    if case["buyer"].get("category_goal") not in RELATIONSHIP_GOALS or not cost or cost <= 0:
        return None
    return {"standard": closing_terms(case, {}, standard), "interest_rate": SELLER_RATE,
            "full_cost": cost * FULL_COST_RATIO}


def complete(case, standard, terms):
    """All negotiable fields: given terms, then quote defaults, then the closest allowed option."""
    out = {}
    for field in case["negotiable"]:
        value = terms.get(field, standard.get(field))
        if field != "unit_price" and value is None and None not in case.get("term_options", {}).get(field, [None]):
            value = case["term_options"][field][0]
        out[field] = snap(case, field, value) if field != "unit_price" else value
    return out


def _cost(case, standard, terms, supplier=None):
    return total_cost(case, terms, standard, supplier)


def _options(case, standard):
    fields = [f for f in case["negotiable"] if f != "unit_price"]
    values = []
    for field in fields:
        allowed = list(case.get("term_options", {}).get(field, []))
        if field in standard and standard[field] not in allowed:
            allowed.append(standard[field])
        values.append(allowed or [standard.get(field)])
    return fields, values


def compositions(case, standard):
    """Every allowed combination of the non-price negotiable fields (bounded)."""
    fields, values = _options(case, standard)
    if math.prod(len(v) for v in values) > MAX_COMPOSITIONS:
        raise ValueError("Too many non-price combinations for exhaustive planning")
    return [dict(zip(fields, combo, strict=True)) for combo in itertools.product(*values)]


def lever_values(case, standard, base_terms, supplier=None):
    """EUR change in our total cost for each single-field option, relative to base_terms.

    price_equivalent is the change expressed in EUR per unit of price, so a payment or date
    option can be compared directly with a price concession."""
    base = complete(case, standard, base_terms)
    price = base["unit_price"]
    c0 = _cost(case, standard, base, supplier)
    per_unit = _cost(case, standard, {**base, "unit_price": price + 1}, supplier) - c0
    fields, values = _options(case, standard)
    out = {"base_terms": base, "base_cost": c0, "eur_per_unit_price": round(per_unit, 2), "fields": {}}
    for field, allowed in zip(fields, values, strict=True):
        rows = []
        for value in allowed:
            delta = _cost(case, standard, {**base, field: value}, supplier) - c0
            rows.append({"value": value, "delta_eur": round(delta, 2),
                         "price_equivalent": round(delta / per_unit, 2) if per_unit else None})
        out["fields"][field] = rows
    return out


def cheapest_price(case, standard, composition, supplier, high):
    """Price in (0, high] with the lowest total cost. Without a supplier-health estimate cost only
    rises with price; with one, cutting below the supplier's sustainable margin costs more than it saves."""
    if not supplier:
        return 0.01
    def cost(p):
        return _cost(case, standard, {**composition, "unit_price": p}, supplier)
    lo, hi = 0.01, high
    for _ in range(100):  # ternary search: linear price cost plus a convex health charge
        a, b = lo + (hi - lo) / 3, hi - (hi - lo) / 3
        lo, hi = (lo, b) if cost(a) <= cost(b) else (a, hi)
    return math.ceil(lo * 100) / 100


def price_for_cost(case, standard, composition, target, supplier=None, high=None):
    """Highest two-decimal price whose total cost with this composition is at most target,
    searched only above the cost-minimising price (never a deeper, costlier cut)."""
    def cost(p):
        return _cost(case, standard, {**composition, "unit_price": p}, supplier)
    hi = 1.0
    while cost(hi) <= target or (supplier and hi < (high or 0)):
        hi *= 2
        if hi > 1e9:
            return None
    lo = cheapest_price(case, standard, composition, supplier, hi)
    if cost(lo) > target:
        return None
    for _ in range(80):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if cost(mid) <= target else (lo, mid)
    price = math.floor(lo * 100) / 100
    while price > 0.01 and cost(price) > target:
        price = round(price - 0.01, 2)
    return price


def seller_neutral_price(case, composition, standing, seller, share):
    """Price at which this mix gives the seller `share` of its cash value from the standing offer.

    supplier_value is affine in price; contract length and index clauses are security, not cash,
    so a longer contract alone does not count as a concession by the seller."""
    goal = share * supplier_value(case, standing, seller)
    v1 = supplier_value(case, {**composition, "unit_price": 1.0}, seller)
    v2 = supplier_value(case, {**composition, "unit_price": 2.0}, seller)
    if v2 - v1 <= 0:
        return None
    return math.floor((1.0 + (goal - v1) / (v2 - v1)) * 100) / 100


def _thread(events, case, standard):
    """Our sent packages and the supplier's primary standing offers, in order."""
    sent, standing = [], []
    for event in events:
        sheets = event.get("term_sheets") or []
        if event.get("from") == "buyer":
            if sheets:
                sent.append([complete(case, standard, s.get("terms", s)) for s in sheets])
        else:
            # The cheapest priced sheet of each reply (primary or alternative) is its standing offer.
            priced = [complete(case, standard, s.get("terms", {})) for s in sheets
                      if s.get("terms", {}).get("unit_price")]
            # Prefer sheets we could accept; an all-non-compliant reply (e.g. an opening below a
            # volume must-have) still serves as the baseline to counter from.
            compliant = [t for t in priced if must_haves_ok(case, t, standard)]
            if priced:
                standing.append(min(compliant or priced, key=lambda t: _cost(case, standard, t)))
    return sent, standing


def index_required(case, standard, events):
    """Contract lengths at which the supplier answered our fixed-price ask with indexed sheets only.

    L33 (P08 S5/S6/astra, P18 S5): "for a contract of this length we cannot offer a fixed price";
    we kept offering fixed 36-month options and the supplier set the index terms itself (0 % deadband).
    Judged from term sheets, not wording, so it holds for any supplier language. After a refusal, every
    length longer than the longest the supplier itself quoted at a fixed price is treated the same
    (replays: moving the fixed ask from 36 to 24 months just invites the same refusal)."""
    if "index_clause" not in case["negotiable"]:
        return set()
    refused, asked_fixed, quoted_fixed = set(), set(), set()
    for event in events:
        sheets = [complete(case, standard, s.get("terms", s)) for s in event.get("term_sheets") or []]
        if event.get("from") == "buyer":
            asked_fixed = {t.get("contract_months") for t in sheets if not t.get("index_clause")}
            continue
        priced = [t for t in sheets if t.get("unit_price")]
        quoted_fixed |= {t.get("contract_months") for t in priced if not t.get("index_clause")}
        for months in asked_fixed:
            at = [t for t in priced if t.get("contract_months") == months]
            if at and all(t.get("index_clause") for t in at):
                refused.add(months)
        asked_fixed = set()
    lengths = [m for m in case.get("term_options", {}).get("contract_months") or [] if m is not None]
    known = [m for m in quoted_fixed if m is not None]
    if refused and lengths and known:
        refused |= {m for m in lengths if m > max(known)}
    return refused - quoted_fixed


def _distance(a, b, fields):
    return sum(a.get(f) != b.get(f) for f in fields)


def aligned_lead(case, standard):
    """Slowest allowed lead time within the buyer's need, if a faster allowed option exists."""
    need = case["buyer"].get("need_lead_time_days")
    if "lead_time_days" not in case["negotiable"] or not isinstance(need, (int, float)):
        return None
    fields, values = _options(case, standard)
    allowed = [v for v in values[fields.index("lead_time_days")] if isinstance(v, (int, float))]
    within = [v for v in allowed if v <= need]
    if not within or min(allowed) >= max(within):
        return None
    return max(within)


def prefer_need_lead(case, candidates):
    """Reorder build() candidates (..., value, terms) so that, within each group identical except for
    lead time (same price, seller value and our cost), the slowest lead time within need comes first."""
    need = case["buyer"].get("need_lead_time_days")

    def key(c):
        rest = tuple(sorted((f, str(v)) for f, v in c[-1].items() if f != "lead_time_days"))
        return rest, round(c[3], 4), c[1]

    groups = {}
    for c in candidates:
        groups.setdefault(key(c), []).append(c)
    out, done = [], set()
    for c in candidates:
        k = key(c)
        if k in done:
            continue
        done.add(k)
        members = groups[k]
        within = [m for m in members if isinstance(m[-1].get("lead_time_days"), (int, float))
                  and m[-1]["lead_time_days"] <= need]
        top = max(within, key=lambda m: m[-1]["lead_time_days"]) if within else members[0]
        out += [top] + [m for m in members if m is not top]
    return out


def retained_quality_mix(case, standard, events, standing, supplier=None):
    """Quality fields of a compliant, relaxed-quality mix the supplier quoted earlier in this session
    but dropped from its latest reply, or None. Relaxed: costlier to us than the standing quality at the
    standing price. Never a higher chargeback than standing. Offered in one buyer message only."""
    quality = [f for f in QUALITY_FIELDS if f in case["negotiable"]]
    if "ppm_commitment" not in quality:
        return None
    replies = [i for i, e in enumerate(events) if e.get("from") != "buyer" and e.get("term_sheets")]
    if len(replies) < 2:
        return None

    def mixes(event):
        out = []
        for sheet in event.get("term_sheets") or []:
            terms = complete(case, standard, sheet.get("terms", {}))
            if terms.get("unit_price") and must_haves_ok(case, terms, standard):
                out.append(terms)
        return out

    def key(terms):
        return tuple(terms.get(f) for f in quality)

    latest = {key(t) for t in mixes(events[replies[-1]])}
    base = _cost(case, standard, standing, supplier)
    for i in reversed(replies[:-1]):
        for terms in mixes(events[i]):
            mix = {f: terms.get(f) for f in quality}
            if key(mix) in latest:
                continue
            if (mix.get("chargeback_eur_per_complaint") or 0) > (standing.get("chargeback_eur_per_complaint") or 0):
                continue
            if _cost(case, standard, {**standing, **mix}, supplier) <= base + 0.01:
                continue  # not relaxed: the ratchet already allows it
            # One counter: none of our messages since the supplier first dropped this mix contained it.
            dropped = next(j for j in replies if j > i and key(mix) not in {key(t) for t in mixes(events[j])})
            if any(key(complete(case, standard, s.get("terms", s))) == key(mix)
                   for e in events[dropped + 1:] if e.get("from") == "buyer" for s in e.get("term_sheets") or []):
                return None
            return mix
    return None


def plan_packages(case, standard, events, profile=None, supplier=None, *,
                  max_cut=None, max_concession=0.85, planned_rounds=None, reciprocity=0.5):
    """Up to three equal-cost packages for the next buyer message, with diagnostics.

    events: this supplier thread only ({"from", "term_sheets", ...}). profile: optional output of
    supplier_profile.build_profile; it adjusts the anchor and composition choice, never the cost
    arithmetic. Returns packages=[] with recommend_accept=True when the schedule has reached the
    standing offer's cost.
    """
    profile = {**(profile or {}), **session_signals(events)}
    if supplier is None:
        supplier = health_estimate(case, standard, profile)
    if max_cut is None:
        max_cut = GOAL_MAX_CUT.get(case["buyer"].get("category_goal"), 0.06)
    sent, standing_offers = _thread(events, case, standard)
    if not standing_offers:
        raise ValueError("No priced supplier offer in this thread")
    standing = standing_offers[-1]
    ref = standing["unit_price"]
    c_stand = _cost(case, standard, standing, supplier)
    fields = [f for f in case["negotiable"] if f != "unit_price"]

    def rank(comp):
        # Our cost at the standing price; ties prefer longer contracts (security the supplier
        # values that is free to us within the horizon), then fewer changes from its offer.
        return (round(_cost(case, standard, {**comp, "unit_price": ref}, supplier), 2),
                -(comp.get("contract_months") or 0), _distance(comp, standing, fields))

    comps = []
    for comp in compositions(case, standard):
        try:
            validate_sheets(case, [{**comp, "unit_price": ref}], standard)
        except ValueError:
            continue
        comps.append(comp)
    if not comps:
        raise ValueError("No composition satisfies the must-haves")
    # A refused fixed price is not offered again at that length: indexed options (deadband chosen by
    # our cost at equal cost) or a shorter fixed-price contract instead (L33).
    indexed_only = index_required(case, standard, events) if INDEX_REFUSAL else set()
    comps = [c for c in comps if c.get("index_clause") or c.get("contract_months") not in indexed_only] or comps
    # Term ratchet (Batch A2, P04): never offer back a term the supplier GRANTED since its opening
    # (it takes the term and keeps its price). Only changed fields are protected, each judged alone
    # on the standing offer; whole-package comparisons at the supplier's price wrongly blocked longer
    # contracts it never offered (S1 review). Exception: earlier payment for a cash-pressed seller.
    opening_offer = standing_offers[0]
    granted = [f for f in fields if standing.get(f) != opening_offer.get(f)
               and not (f == "payment_days" and profile.get("cash_pressure"))]

    def held(comp):
        base = _cost(case, standard, standing, supplier)
        return all(_cost(case, standard, {**standing, f: comp[f]}, supplier) <= base + 0.01 for f in granted)

    valid = comps
    comps = [c for c in comps if held(c)] or comps
    # Kept out of comps so that the anchor, schedule and target are unchanged; build() adds them.
    retained, retained_mix = [], None
    if RETAINED_QUALITY_TRADE and sent:
        retained_mix = retained_quality_mix(case, standard, events, standing, supplier)
    if retained_mix:
        base = _cost(case, standard, standing, supplier)
        others = [f for f in granted if f not in retained_mix]
        retained = [c for c in valid if c not in comps and all(c.get(f) == v for f, v in retained_mix.items())
                    and all(_cost(case, standard, {**standing, f: c[f]}, supplier) <= base + 0.01 for f in others)]
    lead_pref = aligned_lead(case, standard) if NEED_ALIGNED_LEAD else None
    if lead_pref is not None and sent and not any(p.get("lead_time_days") == lead_pref for p in sent[0]):
        lead_pref = None  # the opening did not use it: do not switch lead times mid-negotiation
    comps.sort(key=rank)
    best = comps[0]

    if profile.get("price_freeze"):
        # Halve, don't zero: hosted P03 runs still won 1.7-2.3 % price cuts despite a stated freeze.
        max_cut /= 2
    current = case["buyer"].get("current_unit_price")
    # Never ask below the pre-increase price, nor implausibly deep below the standing offer.
    floor_price = ref * (1 - 1.5 * max_cut)
    if case.get("type") == "price_increase" and current and current < ref:
        floor_price = max(floor_price, current)
    seller = {"standard": closing_terms(case, {}, standard),
              "interest_rate": SELLER_RATE_CASH_PRESSED if profile.get("cash_pressure") else SELLER_RATE}
    if (profile.get("observed_ppm") or {}).get("ppm") is not None:
        seller["ppm"] = profile["observed_ppm"]["ppm"]  # chargebacks cost it at its real defect rate
    anchors = []
    for comp in comps:
        price = seller_neutral_price(case, comp, standing, seller, 1 - max_cut)
        if price is None:
            continue
        price = min(max(price, floor_price, cheapest_price(case, standard, comp, supplier, 2 * ref)), ref)
        anchors.append(_cost(case, standard, {**comp, "unit_price": price}, supplier))
    c_floor = min(anchors) if anchors else _cost(case, standard, {**best, "unit_price": ref}, supplier)

    k = len(sent)
    # Suppliers issued final_offer around round 3-5 in every replay: concede visibly and early.
    rounds, exponent = GOAL_PACE.get(case["buyer"].get("category_goal"), DEFAULT_PACE)
    rounds = planned_rounds or rounds
    schedule = c_floor + (c_stand - c_floor) * max_concession * min(1.0, k / rounds) ** exponent
    # Highest cost we have ever offered (all messages): our position never slides back, even by
    # cent rounding between differently composed menus.
    previous = max((_cost(case, standard, p, supplier) for msg in sent for p in msg), default=None)
    # Reciprocate only real price movement, valued on the current terms: a term the supplier granted
    # because we asked for it (A3 P01: April date, with a HIGHER price) is not a concession to match.
    gain = 0.0
    if len(standing_offers) > 1:
        prior = standing_offers[-2]["unit_price"]
        current = case["buyer"].get("current_unit_price")
        if RETREAT_NOT_CONCESSION and current:
            # Coming back down from an inflated opening toward the price we pay today is not a gift
            # (S5: mirroring it made 42-58 % steps in P01/P02/P08/P18, our four largest gaps to the top).
            prior = min(prior, max(current, standing["unit_price"]))
        before = {**standing, "unit_price": prior}
        gain = max(0.0, _cost(case, standard, before, supplier) - c_stand)
    # Movement for holding the line is total cost (a granted term counts); the reciprocity bonus
    # above counts price only.
    supplier_moved = len(standing_offers) < 2 or (
        _cost(case, standard, standing_offers[-2], supplier) - c_stand > 0.5)
    if previous is not None:
        # Never revert to a lower ask. After a supplier move: a meaningful, diminishing share of the
        # remaining gap, or half the supplier's own price move if larger (mirroring), capped at half
        # the gap (a granted term we asked for is not a reason to cave: A3 P01). Hold if it did not move.
        gap = max(0.0, c_stand - previous)
        share = GAP_STEPS[min(len(sent) - 1, len(GAP_STEPS) - 1)]
        if len(sent) == 1 and len(standing_offers) >= 2 and REANCHOR_STEP:
            # Adaptive anchor: if the supplier's first reply barely moved toward our opening ask, we
            # overshot its zone (hosted data: asks far beyond its limit drew ~0.15x moves). One larger
            # step re-enters it instead of grinding small steps against a stonewall.
            opened = _cost(case, standard, standing_offers[0], supplier) - previous
            moved = _cost(case, standard, standing_offers[0], supplier) - c_stand
            if opened > 0 and moved < STONEWALL_SHARE * opened:
                share = max(share, REANCHOR_STEP)
        step = min(max(share * gap, reciprocity * gain), max(MAX_STEP, share) * gap)
        # A stalled supplier gets a small but real step: holding while rotating mixes read as a lower
        # price on comparable terms (A2 P08), a token step as "not a real move" (S1 P11).
        target = max(schedule, previous + (step if supplier_moved else MIN_STEP * gap))
    else:
        target = schedule
    target = round(target, 2)
    recommend_accept = target >= c_stand - max(1.0, 1e-4 * c_stand)

    already = {tuple(sorted(map(str, p.items()))) for msg in sent for p in msg}
    # Per-mix price never falls (A2, P08: "decreased for comparable terms" preceded a final offer).
    last_price = {}
    for msg in sent:
        for p in msg:
            key = tuple(sorted(map(str, ((f, p.get(f)) for f in fields))))
            last_price[key] = max(last_price.get(key, 0), p.get("unit_price") or 0)
    standing_mix = {f: standing[f] for f in fields}
    value_standing = supplier_value(case, standing, seller)

    def build(goal):
        """All mixes priced at the same cost to us; offer the three worth most to the seller.

        At equal buyer cost, the seller's cash value (supplier_value, assumed rate; higher with a
        cash signal) decides which options are most likely accepted. Ranking mixes by our cost at the
        SUPPLIER's price instead swapped 36-month for 12-month asks mid-negotiation (S1 review)."""
        candidates = []
        for comp in comps + retained:
            price = price_for_cost(case, standard, comp, goal, supplier, high=2 * ref)
            if price is None and supplier:
                # Health-limited mix just short of the target (S4 vs S2 P02: an index option missed by
                # 0.03 % appeared a round later at +EUR 3/unit; offered on time it was agreed at once):
                # offer it at its healthy floor price when that is within a small margin of the target.
                healthy = cheapest_price(case, standard, comp, supplier, 2 * ref)
                margin = HEALTH_MARGIN * max(0.0, c_stand - goal)
                if _cost(case, standard, {**comp, "unit_price": healthy}, supplier) <= goal + margin:
                    price = healthy
            if price is None or price < floor_price:
                continue  # this mix would need an implausibly deep cut; do not send it
            mix = tuple(sorted(map(str, ((f, comp.get(f)) for f in fields))))
            # Never lower our price on identical terms (S2 P01: a 45-day ask fell 136.83 -> 136.30
            # because it was capped at the supplier's 14-day price). The cap applies to new mixes only.
            price = max(min(price, ref), last_price.get(mix, 0))
            terms = {**comp, "unit_price": price}
            if price >= ref and comp == standing_mix:
                continue  # identical to the supplier's own standing offer: nothing to ask
            if tuple(sorted(map(str, terms.items()))) in already:
                continue
            value = supplier_value(case, terms, seller)
            # Seller value within 0.1 % is a tie (e.g. payment days when both sides' money costs about
            # the same); ties go to the mix best for us at the supplier's price (robust to model error:
            # long payment, no index clause), then longer contracts.
            candidates.append((-round(value / value_standing, 3),
                               round(_cost(case, standard, {**comp, "unit_price": ref}, supplier), 2),
                               -(comp.get("contract_months") or 0), value, terms))
        candidates.sort(key=lambda c: c[:3])
        if lead_pref is not None:
            candidates = prefer_need_lead(case, candidates)
        if candidates and OUR_TERMS_OPTION:
            # Always include the mix best for US at the supplier's price ("your price, our terms"):
            # suppliers often give non-price terms away cheaply (L18). S2 P01 never offered April +
            # 90 days, the package nearest the case optimum, because cash-pressure ranking hid it.
            ours = min(candidates, key=lambda c: (c[1], c[2]))
            candidates = [ours] + [c for c in candidates if c is not ours]
        def is_retained(terms):
            return bool(retained_mix) and all(terms.get(f) == v for f, v in retained_mix.items())

        picked, seen = [], set()
        for c in candidates:
            # Options with the same price and the same value to the seller are duplicates to it (D02:
            # three options differing only in lead time; 24 vs 36 months beyond the horizon). Keep the
            # first (best ranked) so the menu shows genuinely different trades.
            key = (c[-1]["unit_price"], round(c[3], 4))
            if key in seen or (is_retained(c[-1]) and any(is_retained(p[-1]) for p in picked)):
                continue
            seen.add(key)
            picked.append(c)
        if retained_mix and not any(is_retained(p[-1]) for p in picked[:3]):
            # One retained relaxed-quality counter, in the last slot after the stricter options.
            extra = next((p for p in picked if is_retained(p[-1])), None)
            if extra is not None:
                picked = [p for p in picked if p is not extra][:2] + [extra]
        out = []
        for _, _, _, value, terms in picked:
            cost = _cost(case, standard, terms, supplier)
            ask = 1 - value / supplier_value(case, standing, seller)
            out.append({"terms": terms, "estimated_total_cost": cost,
                        "saving_vs_standing": round(c_stand - cost, 2),
                        "estimated_seller_concession_pct": round(100 * ask, 2),
                        "cost_components": {k2: round(v, 2) for k2, v in
                                            cost_breakdown(case, terms, standard, supplier).items() if v}})
            if len(out) == 3:
                break
        return out

    packages = build(target)
    # Nothing new to ask (every mix already at the supplier's price or sent): say so; the caller
    # closes on the best acceptable current offer instead of sending a token or repeated package.
    exhausted = not packages and not recommend_accept
    if recommend_accept:
        packages = []
    return {"packages": packages, "target_cost": target, "standing_cost": c_stand,
            "anchor_cost": round(c_floor, 2), "buyer_messages_sent": k,
            "supplier_moved": supplier_moved, "recommend_accept": recommend_accept, "exhausted": exhausted,
            "index_required_months": sorted(indexed_only, key=str),
            "levers": lever_values(case, standard, standing, supplier),
            "limitations": "Equal-cost menus from the published cost function; supplier-health cost "
                           "estimated from dossier should-cost in strategic goals (calibrated offline). "
                           "Anchor and schedule are requests, not acceptance forecasts."}
