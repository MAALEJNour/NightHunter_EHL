"""Opt-in Codex flags (all OFF by default): need-aligned lead time, retained quality trade, fixed-term answer."""

import json

from arena_kit.cost import total_cost

import nighthunter.live as live
import nighthunter.packages as pk
from nighthunter.context import ROOT
from nighthunter.live import LiveAgent
from nighthunter.validation import validate_sheets

FIXTURES = json.loads((ROOT / "tests/fixtures/hosted_practice_cases.json").read_text())
RFQ = json.loads((ROOT / "tests/fixtures/rfq_p05.json").read_text())


def opening(sheet):
    return [{"from": "sales", "status": "open", "term_sheets": [sheet]}]


def menus(case, std, events, monkeypatch, flag, value):
    out = {}
    for on in (False, True):
        monkeypatch.setattr(pk, flag, on)
        out[on] = pk.plan_packages(case, std, events)
    monkeypatch.setattr(pk, flag, value)
    return out


def test_flags_default_off():
    assert pk.NEED_ALIGNED_LEAD is False and pk.RETAINED_QUALITY_TRADE is False
    assert live.FIXED_TERM_ANSWER is True  # turned on after the live P11 check (11 Oct)


def test_need_aligned_lead_p05_offers_35_days_at_equal_cost(monkeypatch):
    case = RFQ["case"]
    for sid, bidder in RFQ["bidders"].items():
        std, events = bidder["standard_terms"], opening(bidder["opening_offer"])
        plans = menus(case, std, events, monkeypatch, "NEED_ALIGNED_LEAD", False)
        off, on = plans[False]["packages"], plans[True]["packages"]
        assert plans[False]["target_cost"] == plans[True]["target_cost"]
        assert {p["terms"]["lead_time_days"] for p in off} == {28}, sid
        assert {p["terms"]["lead_time_days"] for p in on} == {35}, sid
        validate_sheets(case, [p["terms"] for p in on], std)
        # Same prices and the same cost to us; only the (free to us) lead time changes.
        for a, b in zip(off, on, strict=True):
            assert a["terms"]["unit_price"] == b["terms"]["unit_price"]
            assert abs(total_cost(case, a["terms"], std) - total_cost(case, b["terms"], std)) < 0.01


def test_need_aligned_lead_p10_keeps_priced_56_day_trade(monkeypatch):
    fx = FIXTURES["case:P10"]
    plans = menus(fx["case"], fx["standard_terms"], opening(fx["opening_offer"]), monkeypatch,
                  "NEED_ALIGNED_LEAD", False)
    off = [p["terms"]["lead_time_days"] for p in plans[False]["packages"]]
    on = [p["terms"]["lead_time_days"] for p in plans[True]["packages"]]
    assert 35 in off and 42 not in off
    assert 42 in on and 35 not in on and 56 in on  # need is 42; the discounted 56-day option stays
    assert [p["terms"]["unit_price"] for p in plans[False]["packages"]] == \
        [p["terms"]["unit_price"] for p in plans[True]["packages"]]


def test_need_aligned_lead_changes_nothing_without_a_free_lead_tie(monkeypatch):
    for case_id, fx in FIXTURES.items():
        if case_id == "case:P10":
            continue
        plans = menus(fx["case"], fx["standard_terms"], opening(fx["opening_offer"]), monkeypatch,
                      "NEED_ALIGNED_LEAD", False)
        assert plans[False]["packages"] == plans[True]["packages"], case_id


def test_need_aligned_lead_is_sticky_only_when_the_opening_used_it(monkeypatch):
    case = RFQ["case"]
    bidder = RFQ["bidders"]["sup:70250"]
    std = bidder["standard_terms"]
    monkeypatch.setattr(pk, "NEED_ALIGNED_LEAD", True)
    events = opening(bidder["opening_offer"])
    first = pk.plan_packages(case, std, events)
    events += [{"from": "buyer", "term_sheets": [{"terms": p["terms"]} for p in first["packages"]]},
               {"from": "sales", "status": "open",
                "term_sheets": [{"term_sheet_id": "offer:x-2", "terms": {"unit_price": 37.0}}]}]
    second = pk.plan_packages(case, std, events)
    assert {p["terms"]["lead_time_days"] for p in second["packages"]} == {35}
    # An opening sent without the flag (28 days) is not switched to 35 later.
    monkeypatch.setattr(pk, "NEED_ALIGNED_LEAD", False)
    plain = opening(bidder["opening_offer"])
    sent = pk.plan_packages(case, std, plain)
    plain += [{"from": "buyer", "term_sheets": [{"terms": p["terms"]} for p in sent["packages"]]},
              {"from": "sales", "status": "open",
               "term_sheets": [{"term_sheet_id": "offer:x-2", "terms": {"unit_price": 37.0}}]}]
    monkeypatch.setattr(pk, "NEED_ALIGNED_LEAD", True)
    assert {p["terms"]["lead_time_days"] for p in pk.plan_packages(case, std, plain)["packages"]} == {28}


def p11_history():
    """P11-like: the supplier quotes 800 ppm as an alternative in r1, then drops it in r2."""
    fx = FIXTURES["case:P11"]
    case, std = fx["case"], fx["standard_terms"]
    events = opening(fx["opening_offer"])
    events.append({"from": "buyer", "term_sheets": [
        {"terms": p["terms"]} for p in pk.plan_packages(case, std, events)["packages"]]})
    events.append({"from": "sales", "status": "open", "term_sheets": [
        {"term_sheet_id": "offer:x-1", "terms": {"unit_price": 46.5, "ppm_commitment": 300,
                                                 "chargeback_eur_per_complaint": 0.0}},
        {"term_sheet_id": "offer:x-1-a", "terms": {"unit_price": 46.0, "ppm_commitment": 800,
                                                   "chargeback_eur_per_complaint": 0.0}}]})
    events.append({"from": "buyer", "term_sheets": [
        {"terms": p["terms"]} for p in pk.plan_packages(case, std, events)["packages"]]})
    events.append({"from": "sales", "status": "open", "term_sheets": [
        {"term_sheet_id": "offer:x-2", "terms": {"unit_price": 45.5, "ppm_commitment": 300,
                                                 "chargeback_eur_per_complaint": 0.0}}]})
    return case, std, events


def test_retained_quality_trade_reoffers_dropped_mix_once_at_equal_cost(monkeypatch):
    case, std, events = p11_history()
    plans = menus(case, std, events, monkeypatch, "RETAINED_QUALITY_TRADE", False)
    off, on = plans[False], plans[True]
    assert off["target_cost"] == on["target_cost"]
    assert all(p["terms"]["ppm_commitment"] == 300 for p in off["packages"])
    retained = [p for p in on["packages"] if p["terms"]["ppm_commitment"] == 800]
    assert len(retained) == 1 and on["packages"][-1] is retained[0]
    terms = retained[0]["terms"]
    assert terms["chargeback_eur_per_complaint"] == 0  # never a higher chargeback than standing
    assert terms["unit_price"] < 45.5  # a real counter below the standing price, not a stale quote
    assert total_cost(case, terms, std) <= on["target_cost"] + 0.01
    assert on["packages"][0] == off["packages"][0]  # the stricter-quality lead option stays
    validate_sheets(case, [p["terms"] for p in on["packages"]], std)
    # Price monotone on that mix: never below what we asked for 800 ppm / 0 earlier.
    earlier = [s["terms"]["unit_price"] for e in events if e["from"] == "buyer" for s in e["term_sheets"]
               if s["terms"]["ppm_commitment"] == 800 and s["terms"]["chargeback_eur_per_complaint"] == 0]
    assert all(terms["unit_price"] >= p for p in earlier)

    # One counter only: after we re-offered it and the supplier still quotes 300 ppm, it is not repeated.
    monkeypatch.setattr(pk, "RETAINED_QUALITY_TRADE", True)
    events += [{"from": "buyer", "term_sheets": [{"terms": p["terms"]} for p in on["packages"]]},
               {"from": "sales", "status": "open", "term_sheets": [
                   {"term_sheet_id": "offer:x-3", "terms": {"unit_price": 45.4, "ppm_commitment": 300,
                                                            "chargeback_eur_per_complaint": 0.0}}]}]
    assert all(p["terms"]["ppm_commitment"] == 300 for p in pk.plan_packages(case, std, events)["packages"])


def test_retained_quality_trade_inert_without_a_dropped_quote(monkeypatch):
    for case_id, fx in FIXTURES.items():
        plans = menus(fx["case"], fx["standard_terms"], opening(fx["opening_offer"]), monkeypatch,
                      "RETAINED_QUALITY_TRADE", False)
        assert plans[False]["packages"] == plans[True]["packages"], case_id


def asked(body):
    return [{"from": "sales", "status": "open", "term_sheets": [], "body": "Hello"},
            {"from": "buyer", "term_sheets": []},
            {"from": "sales", "status": "open", "term_sheets": [], "body": body}]


def test_fixed_term_answer_only_on_request_for_a_fixed_field(monkeypatch):
    p11 = FIXTURES["case:P11"]["case"]
    p03 = FIXTURES["case:P03"]["case"]  # payment negotiable there
    request = "We can't go any lower, especially since you won't help us out with faster payment."
    monkeypatch.setattr(live, "FIXED_TERM_ANSWER", False)
    assert LiveAgent.fixed_term_answer(p11, asked(request)) == []  # flag off
    monkeypatch.setattr(live, "FIXED_TERM_ANSWER", True)
    assert LiveAgent.fixed_term_answer(p11, asked(request)) == [
        "Payment terms are fixed at 60 days net in this agreement."]
    assert LiveAgent.fixed_term_answer(p03, asked(request)) == []
    assert LiveAgent.fixed_term_answer(p11, asked("Our price is EUR 46.00 for 300 ppm.")) == []
    # P05 trace: "can't finance longer terms" is about payment, not the fixed contract length.
    rfq = RFQ["case"]
    assert LiveAgent.fixed_term_answer(rfq, asked("cash is tight and I can't finance longer terms")) == []
