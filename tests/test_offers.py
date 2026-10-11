"""Local closing checks derived from the saved P02 payment trade, with no API access."""

from copy import deepcopy
from types import SimpleNamespace
import json

import pytest

from arena_kit.cost import total_cost
from nighthunter.live import LiveAgent


@pytest.fixture
def case():
    # Public P02 economics needed to reproduce the buyer's payment-cost trade.
    return {
        "case_id": "fixture:P02", "suppliers": ["sup:70510"], "parts": ["part:350011"],
        "negotiable": ["unit_price", "payment_days", "index_clause"],
        "term_options": {"payment_days": [14, 30, 45, 60, 90], "index_clause": [None]},
        "fixed_terms": {"lead_time_days": 35, "volume_per_year": 6110, "contract_months": 12,
                        "effective_date": "2027-01-01", "incoterm": "DAP", "tooling_eur": 0},
        "buyer": {"need_per_year": 6110, "horizon_years": 1.0, "current_unit_price": 348.32,
                  "fallback_unit_price": 376.19, "interest_rate": 0.08,
                  "reference_payment_days": 60, "need_lead_time_days": 36,
                  "category_goal": "stabilise", "fallback_risk_pct": 10,
                  "index_risk_pct": 4, "late_cost_per_day": 720,
                  "cost_per_defect": 780, "sustainable_margin_pct": 0.5,
                  "relationship_eur_per_point": 31920,
                  "freight_eur_per_unit": {"EXW": 2.99, "FCA": 2.6, "DAP": 0.0},
                  "index_paths": {}, "must_haves": [],
                  "alternative": {"kind": "quote", "terms": {
                      "unit_price": 421.06, "payment_days": 30, "lead_time_days": 56,
                      "volume_per_year": 6110, "contract_months": 12,
                      "effective_date": "2027-01-01", "index_clause": None,
                      "incoterm": "DAP", "tooling_eur": 0, "ppm_commitment": 0}}},
    }


@pytest.fixture
def agent():
    buyer = LiveAgent.__new__(LiveAgent)
    buyer.dossier = {"evidence": []}
    return buyer


def reply(*sheets, status="open", standard_days=45):
    standard = ("Our standard terms (apply to everything not stated above)\n"
                f"Payment terms (days net) {standard_days}\n"
                "Quality commitment (ppm) 250\n"
                "Chargeback per complaint (EUR) 0.00\n"
                "Index clause none\n")
    return {"from": "sales@70510", "status": status,
            "attachments": [{"name": "quote-offer.pdf", "text": standard}],
            "term_sheets": [{"term_sheet_id": offer_id, "terms": terms} for offer_id, terms in sheets]}


def action(decision):
    return decision["message"]["action"]


def test_p02_saved_payment_trade_prefers_complete_cost(case, agent):
    fast = {"unit_price": 369.15, "payment_days": 14, "index_clause": None}
    slower = {"unit_price": 370.27, "payment_days": 45, "index_clause": None}
    std = {"ppm_commitment": 250, "chargeback_eur_per_complaint": 0}
    # Saved hosted outcomes were EUR 2,279,754.24 and EUR 2,271,091.17;
    # the latter includes EUR 8.86 of private supplier-health charge we cannot know live.
    assert total_cost(case, fast, std) == 2_279_754.24
    assert total_cost(case, slower, std) == 2_271_082.32
    assert 2_271_091.17 < 2_279_754.24
    threads = {"sup:70510": [reply(("offer:fast", fast), ("offer:slower", slower))]}
    decision = agent.safe_close(case, threads)
    assert decision["message"]["term_sheets"] == [{"terms": slower}]
    assert "action" not in decision["message"]
    case["round_limit"] = 0
    assert action(agent.safe_close(case, threads)) == {"type": "accept", "term_sheet_id": "offer:fast"}


def test_only_latest_supplier_message_ids_are_eligible(case, agent):
    older = reply(("offer:old", {"unit_price": 360, "payment_days": 45, "index_clause": None}))
    latest = reply(("offer:new", {"unit_price": 370, "payment_days": 45, "index_clause": None}))
    threads = {"sup:70510": [older, {"from": "buyer", "term_sheets": []}, latest]}
    assert action(agent.safe_close(case, threads))["term_sheet_id"] == "offer:new"
    assert [o["term_sheet_id"] for o in agent.current_offers(case, threads)] == ["offer:new"]
    latest["term_sheets"] = []
    assert agent.current_offers(case, threads) == []
    assert action(agent.safe_close(case, threads))["type"] == "walk_away"


def test_quote_standard_completes_missing_negotiable_field(case, agent):
    threads = {"sup:70510": [reply(("offer:partial", {"unit_price": 370, "index_clause": None}))]}
    offer = agent.current_offers(case, threads)[0]
    assert offer["terms"]["payment_days"] == 45
    assert action(agent.safe_close(case, threads))["term_sheet_id"] == "offer:partial"
    no_default = deepcopy(threads)
    no_default["sup:70510"][0]["attachments"] = []
    assert agent.current_offers(case, no_default) == []


def test_must_haves_and_alternative_can_block_acceptance(case, agent):
    case["buyer"]["must_haves"] = [{"field": "payment_days", "op": ">=", "value": 30}]
    threads = {"sup:70510": [reply(("offer:fast", {
        "unit_price": 369.15, "payment_days": 14, "index_clause": None}))]}
    assert action(agent.safe_close(case, threads))["type"] == "walk_away"
    case["buyer"]["must_haves"] = []
    case["buyer"]["alternative"]["terms"] = {
        **case["fixed_terms"], "unit_price": 369.15, "payment_days": 14,
        "index_clause": None, "ppm_commitment": 250,
        "chargeback_eur_per_complaint": 0}
    # Equal-cost offers do not beat the alternative.
    assert action(agent.safe_close(case, threads))["type"] == "walk_away"
    case["buyer"]["alternative"]["terms"] = {
        **case["buyer"]["alternative"]["terms"], "unit_price": 300}
    assert action(agent.safe_close(case, threads))["type"] == "walk_away"


def test_invalid_or_absent_current_offers_do_not_get_accepted(case, agent):
    bad = reply(("offer:bad", {"unit_price": -1, "payment_days": 45, "index_clause": None}))
    assert action(agent.safe_close(case, {"sup:70510": [bad]}))["type"] == "walk_away"
    empty = reply()
    assert action(agent.safe_close(case, {"sup:70510": [empty]}))["type"] == "walk_away"


@pytest.mark.parametrize("requested_action", ["accept", "walk_away"])
def test_model_close_echoes_best_nonprimary_terms(case, tmp_path, requested_action):
    model = SimpleNamespace(complete=lambda *_: json.dumps({
        "supplier_id": "sup:70510", "action": requested_action}))
    package = SimpleNamespace(facts={}, lookup=lambda _ref: None)
    buyer = LiveAgent(model, package, {"case": case, "evidence": []}, "baseline", tmp_path)
    threads = {"sup:70510": [reply(
        ("offer:low-price", {"unit_price": 369.15, "payment_days": 14, "index_clause": None}),
        ("offer:low-cost", {"unit_price": 370.27, "payment_days": 45, "index_clause": None}))]}
    result = buyer.decide(case, threads)
    assert result["message"]["term_sheets"] == [{"terms": {
        "unit_price": 370.27, "payment_days": 45, "index_clause": None}}]
    assert "action" not in result["message"]
    assert not buyer.decisions[0]["fallback"], buyer.decisions[0].get("reason")


def test_model_accept_cannot_override_unfavorable_alternative(case, tmp_path):
    case["buyer"]["alternative"]["terms"]["unit_price"] = 300
    model = SimpleNamespace(complete=lambda *_: json.dumps({
        "supplier_id": "sup:70510", "action": "accept"}))
    package = SimpleNamespace(facts={}, lookup=lambda _ref: None)
    buyer = LiveAgent(model, package, {"case": case, "evidence": []}, "baseline", tmp_path)
    threads = {"sup:70510": [reply(("offer:high", {
        "unit_price": 370.27, "payment_days": 45, "index_clause": None}))]}
    assert action(buyer.decide(case, threads))["type"] == "walk_away"
    assert not buyer.decisions[0]["fallback"]
