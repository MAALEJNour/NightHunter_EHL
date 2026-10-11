"""Package planner on the hosted P01-P03 case definitions (public case data, no transcripts/scores)."""

import itertools
import json

import pytest
from arena_kit.cost import total_cost

from nighthunter.context import ROOT
from nighthunter.packages import lever_values, plan_packages, price_for_cost
from nighthunter.validation import validate_sheets

FIXTURES = json.loads((ROOT / "tests/fixtures/hosted_practice_cases.json").read_text())


def setup(case_id):
    fx = FIXTURES[case_id]
    events = [{"from": "sales", "status": "open", "term_sheets": [fx["opening_offer"]]}]
    return fx["case"], fx["standard_terms"], events


def reply(events, plan, price_factor=0.996):
    """Buyer sends the plan; supplier lowers its own standing price slightly."""
    last = [e for e in events if e["from"] != "buyer"][-1]["term_sheets"][0]["terms"]
    events.append({"from": "buyer", "term_sheets": [{"terms": p["terms"]} for p in plan["packages"]]})
    events.append({"from": "sales", "status": "open", "term_sheets": [
        {"term_sheet_id": f"offer:x-{len(events)}",
         "terms": {**last, "unit_price": round(last["unit_price"] * price_factor, 2)}}]})


@pytest.mark.parametrize("case_id", sorted(FIXTURES))
def test_packages_are_valid_complete_and_equal_cost(case_id):
    case, std, events = setup(case_id)
    plan = plan_packages(case, std, events)
    assert 1 <= len(plan["packages"]) <= 3
    validate_sheets(case, [p["terms"] for p in plan["packages"]], std)
    for p in plan["packages"]:
        cost = total_cost(case, p["terms"], std)
        assert cost <= plan["target_cost"] + 0.01
        assert cost >= plan["target_cost"] - 0.002 * plan["target_cost"]  # equal cost, cent rounding
        assert cost < plan["standing_cost"]


def test_p01_opening_uses_date_and_payment_levers():
    case, std, events = setup("case:P01")
    plan = plan_packages(case, std, events)
    first = plan["packages"][0]["terms"]
    assert first["effective_date"] == "2027-04-01" and first["payment_days"] == 90
    # The anchor keeps most of the price: value comes from terms, not an aggressive price cut.
    assert first["unit_price"] > 0.97 * events[0]["term_sheets"][0]["terms"]["unit_price"]


def test_p02_never_trades_payment_down_without_compensating_price():
    case, std, events = setup("case:P02")
    plan = plan_packages(case, std, events)
    by_days = {p["terms"]["payment_days"]: p["terms"]["unit_price"] for p in plan["packages"]}
    assert max(by_days) == 90
    # Equal cost: every shorter payment carries a correspondingly lower price.
    days = sorted(by_days)
    assert all(by_days[a] < by_days[b] for a, b in itertools.pairwise(days))


def test_price_increase_anchor_never_below_old_price():
    for case_id in ("case:P01", "case:P02"):
        case, std, events = setup(case_id)
        old = case["buyer"]["current_unit_price"]
        assert all(p["terms"]["unit_price"] >= old for p in plan_packages(case, std, events)["packages"])


def test_p03_uses_full_horizon_and_no_overbuy():
    case, std, events = setup("case:P03")
    for p in plan_packages(case, std, events)["packages"]:
        assert p["terms"]["contract_months"] >= 24
        assert p["terms"]["volume_per_year"] == case["buyer"]["need_per_year"]


def test_price_freeze_profile_shrinks_the_ask():
    case, std, events = setup("case:P03")
    loose = plan_packages(case, std, events)
    frozen = plan_packages(case, std, events, profile={"price_freeze": True})
    assert frozen["target_cost"] > loose["target_cost"]


def test_cash_pressure_adds_priced_early_payment_option():
    case, std, events = setup("case:P01")
    plan = plan_packages(case, std, events, profile={"cash_pressure": True})
    early = [p for p in plan["packages"] if p["terms"]["payment_days"] == 14]
    assert early and early[0]["estimated_total_cost"] <= plan["target_cost"] + 0.01


@pytest.mark.parametrize("case_id", sorted(FIXTURES))
def test_concessions_are_monotonic_and_never_repeat(case_id):
    """Our most generous offer never shrinks, unless we are matching the supplier's own lower price."""
    case, std, events = setup(case_id)
    best_offered, sent = None, set()
    for _ in range(5):
        plan = plan_packages(case, std, events)
        if plan["recommend_accept"] or plan["exhausted"]:
            break
        supplier_price = [e for e in events if e["from"] != "buyer"][-1]["term_sheets"][0]["terms"]["unit_price"]
        offered = max(p["estimated_total_cost"] for p in plan["packages"])
        matching = all(p["terms"]["unit_price"] >= supplier_price for p in plan["packages"])
        assert best_offered is None or offered >= best_offered - 1.0 or matching
        best_offered = max(best_offered or offered, offered)
        for p in plan["packages"]:
            key = json.dumps(p["terms"], sort_keys=True)
            assert key not in sent
            sent.add(key)
        reply(events, plan)


def test_stalled_supplier_gets_a_small_real_step_not_a_token_or_none():
    # S1 P11: +0.01 steps drew "one cent is not a real move" and a final offer at the supplier's price.
    case, std, events = setup("case:P02")
    plan = plan_packages(case, std, events)
    reply(events, plan, price_factor=1.0)
    held = plan_packages(case, std, events)
    gap = held["standing_cost"] - plan["target_cost"]
    assert not held["supplier_moved"]
    assert 0.05 * gap < held["target_cost"] - plan["target_cost"] <= 0.12 * gap


def test_recommends_accept_when_supplier_reaches_schedule():
    case, std, events = setup("case:P02")
    plan = plan_packages(case, std, events)
    reply(events, plan, price_factor=0.94)  # supplier meets the anchor
    assert plan_packages(case, std, events)["recommend_accept"]


def test_lever_values_match_published_cost_function():
    case, std, events = setup("case:P02")
    base = events[0]["term_sheets"][0]["terms"]
    levers = lever_values(case, std, base)
    row = next(r for r in levers["fields"]["payment_days"] if r["value"] == 90)
    expected = total_cost(case, {**base, "payment_days": 90}, std) - total_cost(case, base, std)
    assert row["delta_eur"] == pytest.approx(expected, abs=0.01)
    assert row["delta_eur"] < 0 and row["price_equivalent"] < 0


def test_price_for_cost_is_tight():
    case, std, events = setup("case:P01")
    comp = {"effective_date": "2027-01-01", "payment_days": 60}
    target = 1_110_000
    price = price_for_cost(case, std, comp, target)
    assert total_cost(case, {**comp, "unit_price": price}, std) <= target
    assert total_cost(case, {**comp, "unit_price": round(price + 0.01, 2)}, std) > target


def test_ambition_follows_public_category_goal():
    case, std, events = setup("case:P02")
    stabilise = plan_packages(case, std, events)
    leverage = plan_packages({**case, "buyer": {**case["buyer"], "category_goal": "leverage"}}, std, events)
    assert leverage["anchor_cost"] < stabilise["anchor_cost"]
    assert plan_packages(case, std, events, max_cut=0.06)["anchor_cost"] == stabilise["anchor_cost"]


def test_standing_offer_is_cheapest_sheet_of_latest_reply():
    case, std, events = setup("case:P02")
    primary = events[0]["term_sheets"][0]
    cheaper = {"term_sheet_id": "offer:alt", "terms": {**primary["terms"], "payment_days": 90}}
    with_alt = [{**events[0], "term_sheets": [primary, cheaper]}]
    assert plan_packages(case, std, with_alt)["standing_cost"] < plan_packages(case, std, events)["standing_cost"]


def test_standing_prefers_compliant_sheet_but_counters_non_compliant_opening():
    case, std, events = setup("case:P02")
    case = {**case, "buyer": {**case["buyer"], "must_haves": [{"field": "payment_days", "op": ">=", "value": 45}]}}
    primary = events[0]["term_sheets"][0]  # 30 days: breaks the must-have
    compliant = {"term_sheet_id": "offer:alt", "terms": {**primary["terms"], "payment_days": 60,
                                                          "unit_price": primary["terms"]["unit_price"] + 5}}
    with_alt = [{**events[0], "term_sheets": [primary, compliant]}]
    assert plan_packages(case, std, with_alt)["standing_cost"] == total_cost(case, compliant["terms"], std)
    only_bad = plan_packages(case, std, events)  # non-compliant opening: still plans compliant counters
    assert only_bad["packages"] and all(p["terms"]["payment_days"] >= 45 for p in only_bad["packages"])


def test_health_estimate_stops_deep_cuts_in_stabilise_cases():
    from nighthunter.supplier_profile import build_profile
    fx = FIXTURES["case:P02"]
    case, std, events = setup("case:P02")
    profile = build_profile(case, {"evidence": fx["evidence"]}, case["suppliers"][0])
    assert profile["should_cost"]["unit_cost"] > 0
    blind = min(p["terms"]["unit_price"] for p in plan_packages(case, std, events)["packages"])
    aware = plan_packages(case, std, events, profile=profile)
    # Batch A: 351.21 drew a EUR 122k health charge; the aware planner asks well above that.
    assert min(p["terms"]["unit_price"] for p in aware["packages"]) > max(blind, 355)


def test_no_health_estimate_for_leverage_goal():
    from nighthunter.packages import health_estimate
    case, std, _ = setup("case:P02")
    leverage = {**case, "buyer": {**case["buyer"], "category_goal": "leverage"}}
    assert health_estimate(leverage, std, {"should_cost": {"unit_cost": 300}}) is None
    assert health_estimate(case, std, {"should_cost": {"unit_cost": 300}})["full_cost"] < 300


# --- Batch A2 regressions: real supplier offers from hosted practice replies -------------------

def _sheet(offer_id, **terms):
    return {"term_sheet_id": offer_id, "terms": terms}


def test_a2_p04_never_gives_back_granted_payment_days():
    case, std, events = setup("case:P04")
    first = plan_packages(case, std, events)
    events.append({"from": "buyer", "term_sheets": [{"terms": p["terms"]} for p in first["packages"]]})
    # Supplier granted 90 days / 36 months at 4.94 (alternative 4.90 at 45 days).
    events.append({"from": "sales", "status": "open", "term_sheets": [
        _sheet("offer:70620-1", unit_price=4.94, payment_days=90, contract_months=36),
        _sheet("offer:70620-1-a", unit_price=4.90, payment_days=45, contract_months=36)]})
    plan = plan_packages(case, std, events)
    assert plan["packages"] and all(p["terms"]["payment_days"] == 90 for p in plan["packages"])


def test_a2_p08_price_per_mix_never_decreases_and_reciprocates():
    case, std, events = setup("case:P08")
    first = plan_packages(case, std, events)
    events.append({"from": "buyer", "term_sheets": [{"terms": p["terms"]} for p in first["packages"]]})
    events.append({"from": "sales", "status": "open", "term_sheets": [
        _sheet("offer:70710-1", unit_price=5.53, payment_days=90, contract_months=36,
               index_clause={"series": "AS-14404", "material_share": 0.45, "deadband_pct": 5.0,
                             "base_month": "2026-08"})]})
    second = plan_packages(case, std, events)
    assert second["target_cost"] > first["target_cost"]  # visible concession after a supplier move
    sent = {json.dumps({k: v for k, v in p["terms"].items() if k != "unit_price"}, sort_keys=True):
            p["terms"]["unit_price"] for p in first["packages"]}
    for p in second["packages"]:
        mix = json.dumps({k: v for k, v in p["terms"].items() if k != "unit_price"}, sort_keys=True)
        assert p["terms"]["unit_price"] >= sent.get(mix, 0)


AS_INDEX = {"series": "AS-14404", "material_share": 0.45, "base_month": "2026-08"}


@pytest.mark.parametrize("case_id", ["case:P08", "case:P18"])
def test_l33_refused_fixed_price_length_is_offered_indexed(case_id, monkeypatch):
    monkeypatch.setattr("nighthunter.packages.INDEX_REFUSAL", True)
    # Astra P08: after "for a contract of this length we cannot offer a fixed price" (indexed sheets
    # only at 36 months), round 3 went back to fixed 36-month asks; the supplier set a 0 % deadband.
    case, std, events = setup(case_id)
    first = plan_packages(case, std, events)
    assert any(not p["terms"]["index_clause"] and p["terms"]["contract_months"] == 36 for p in first["packages"])
    events.append({"from": "buyer", "term_sheets": [{"terms": p["terms"]} for p in first["packages"]]})
    events.append({"from": "sales", "status": "open", "term_sheets": [
        _sheet("offer:x-1", unit_price=5.52, payment_days=90, contract_months=36,
               index_clause={**AS_INDEX, "deadband_pct": 0.0}),
        _sheet("offer:x-1-a", unit_price=5.46, payment_days=30, contract_months=36,
               index_clause={**AS_INDEX, "deadband_pct": 0.0})]})
    second = plan_packages(case, std, events)
    # 36 refused; 24 is also longer than the supplier's own fixed-price quote (12 months).
    assert second["index_required_months"] == [24, 36]
    assert second["packages"]
    for p in second["packages"]:
        assert p["terms"]["index_clause"] or p["terms"]["contract_months"] == 12


def test_l33_fixed_price_reply_keeps_fixed_options(monkeypatch):
    monkeypatch.setattr("nighthunter.packages.INDEX_REFUSAL", True)
    case, std, events = setup("case:P08")
    first = plan_packages(case, std, events)
    events.append({"from": "buyer", "term_sheets": [{"terms": p["terms"]} for p in first["packages"]]})
    events.append({"from": "sales", "status": "open", "term_sheets": [
        _sheet("offer:x-1", unit_price=5.60, payment_days=90, contract_months=36, index_clause=None)]})
    second = plan_packages(case, std, events)
    assert second["index_required_months"] == []


@pytest.mark.parametrize("case_id", sorted(FIXTURES))
def test_all_hosted_cases_plan_compliant_round0_with_profile(case_id):
    from nighthunter.supplier_profile import build_profile
    fx = FIXTURES[case_id]
    case, std, events = setup(case_id)
    profile = build_profile(case, {"evidence": fx["evidence"]}, case["suppliers"][0])
    plan = plan_packages(case, std, events, profile=profile)
    assert plan["packages"]
    validate_sheets(case, [p["terms"] for p in plan["packages"]], std)


def test_a2_p01_granted_term_does_not_trigger_premature_accept():
    case, std, events = setup("case:P01")
    first = plan_packages(case, std, events)
    events.append({"from": "buyer", "term_sheets": [{"terms": p["terms"]} for p in first["packages"]]})
    events.append({"from": "sales", "status": "open", "term_sheets": [
        _sheet("offer:70110-1", unit_price=138.9, payment_days=14, effective_date="2027-04-01")]})
    plan = plan_packages(case, std, events)
    assert not plan["recommend_accept"] and plan["packages"]


def test_a3_p01_granted_date_with_higher_price_is_not_reciprocated():
    case, std, events = setup("case:P01")
    first = plan_packages(case, std, events)
    events.append({"from": "buyer", "term_sheets": [{"terms": p["terms"]} for p in first["packages"]]})
    events.append({"from": "sales", "status": "open", "term_sheets": [
        _sheet("offer:70110-1", unit_price=138.9, payment_days=14, effective_date="2027-04-01")]})
    second = plan_packages(case, std, events)
    # A3 gave up most of the gap in one step (14-day ask 131.81 -> 136.77). Now: a measured share.
    gap = second["standing_cost"] - first["target_cost"]
    assert 0.15 * gap <= second["target_cost"] - first["target_cost"] <= 0.30 * gap
    assert not second["recommend_accept"] and second["packages"]



@pytest.mark.parametrize("case_id", sorted(FIXTURES))
def test_plan_is_never_empty_without_accept_when_supplier_stalls(case_id):
    case, std, events = setup(case_id)
    for _ in range(6):
        plan = plan_packages(case, std, events)
        assert plan["packages"] or plan["recommend_accept"] or plan["exhausted"]
        if plan["recommend_accept"] or plan["exhausted"]:
            break
        reply(events, plan, price_factor=1.0)  # supplier never moves



def test_s2_p01_price_never_falls_on_identical_terms_and_steps_are_capped():
    case, std, events = setup("case:P01")
    first = plan_packages(case, std, events)
    events.append({"from": "buyer", "term_sheets": [{"terms": p["terms"]} for p in first["packages"]]})
    events.append({"from": "sales", "status": "open", "term_sheets": [
        _sheet("offer:70110-1", unit_price=138.9, payment_days=14, effective_date="2027-04-01"),
        _sheet("offer:70110-1-a", unit_price=135.7, payment_days=14, effective_date="2027-01-01")]})
    second = plan_packages(case, std, events)
    gap = second["standing_cost"] - first["target_cost"]
    assert second["target_cost"] - first["target_cost"] <= 0.30 * gap + 1
    sent = {json.dumps({k: v for k, v in p["terms"].items() if k != "unit_price"}, sort_keys=True):
            p["terms"]["unit_price"] for p in second["packages"]}
    events.append({"from": "buyer", "term_sheets": [{"terms": p["terms"]} for p in second["packages"]]})
    events.append({"from": "sales", "status": "open", "term_sheets": [
        _sheet("offer:70110-2", unit_price=136.3, payment_days=14, effective_date="2027-04-01")]})
    for p in plan_packages(case, std, events)["packages"]:
        mix = json.dumps({k: v for k, v in p["terms"].items() if k != "unit_price"}, sort_keys=True)
        assert p["terms"]["unit_price"] >= sent.get(mix, 0)


def test_one_option_is_always_the_mix_best_for_us(monkeypatch):
    monkeypatch.setattr("nighthunter.packages.OUR_TERMS_OPTION", True)
    # S2 P01: cash-pressure ranking hid April + 90 days, the package nearest the case optimum.
    from nighthunter.supplier_profile import build_profile
    case, std, events = setup("case:P01")
    profile = build_profile(case, {"evidence": FIXTURES["case:P01"]["evidence"]}, case["suppliers"][0])
    plain = plan_packages(case, std, events)["packages"][0]["terms"]
    assert plain["effective_date"] == "2027-04-01" and plain["payment_days"] == 90
    # With the health estimate the opening target is below that mix's healthy price; from the next
    # round on (target moved) it leads the menu.
    first = plan_packages(case, std, events, profile=profile)
    reply(events, first)
    lead = plan_packages(case, std, events, profile=profile)["packages"][0]["terms"]
    assert lead["effective_date"] == "2027-04-01" and lead["payment_days"] == 90


def test_s4_p02_health_limited_index_option_is_offered_on_time():
    # S2 offered the copper-index mix at 361.79 in round 3 and it was agreed at once (73.4); in S4 the
    # target missed its healthy floor by 0.03 %, the mix came a round later at 364.78 (66.7).
    from nighthunter.supplier_profile import build_profile
    case, std, events = setup("case:P02")
    profile = build_profile(case, {"evidence": FIXTURES["case:P02"]["evidence"]}, case["suppliers"][0])
    first = plan_packages(case, std, events, profile=profile)
    events.append({"from": "buyer", "term_sheets": [{"terms": p["terms"]} for p in first["packages"]]})
    events.append({"from": "sales", "status": "open", "term_sheets": [
        _sheet("offer:70510-1", unit_price=374.35, payment_days=90, index_clause=None),
        _sheet("offer:70510-1-a", unit_price=371.25, payment_days=45, index_clause=None)]})
    second = plan_packages(case, std, events, profile=profile)
    events.append({"from": "buyer", "term_sheets": [{"terms": p["terms"]} for p in second["packages"]]})
    events.append({"from": "sales", "status": "open", "term_sheets": [
        _sheet("offer:70510-2", unit_price=373.95, payment_days=90, index_clause=None)]})
    third = plan_packages(case, std, events, profile=profile)
    indexed = [p["terms"] for p in third["packages"] if p["terms"]["index_clause"]]
    assert indexed and indexed[0]["unit_price"] < 363


def test_retreat_from_inflated_opening_is_not_mirrored(monkeypatch):
    monkeypatch.setattr("nighthunter.packages.RETREAT_NOT_CONCESSION", True)
    # S5 P08: 6.05 opening (current price 5.45) -> 5.41; mirroring that "concession" made our second ask a
    # 47 % step of the gap (4.71 -> 5.01). Only movement below today's price is reciprocated.
    case, std, events = setup("case:P08")
    first = plan_packages(case, std, events)
    events.append({"from": "buyer", "term_sheets": [{"terms": p["terms"]} for p in first["packages"]]})
    events.append({"from": "sales", "status": "open", "term_sheets": [
        _sheet("offer:x-1", unit_price=5.41, payment_days=90, contract_months=36,
               index_clause={**AS_INDEX, "deadband_pct": 0.0})]})
    second = plan_packages(case, std, events)
    asks = [p["terms"]["unit_price"] for p in second["packages"]]
    assert asks and min(asks) <= 4.90  # mechanism only; switched off after S9
