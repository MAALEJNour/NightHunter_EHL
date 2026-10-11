import json
from copy import deepcopy

import pytest

from nighthunter.context import ROOT
from nighthunter.economics import advise, supplier_estimate, trajectory
from nighthunter.validation import validate_sheets


@pytest.fixture
def case():
    return json.loads((ROOT / "vendor/negotiation-arena-kit/starter-kit/arena_kit/sim_cases/S01.json").read_text())


def thread(prices):
    events = []
    for i, price in enumerate(prices):
        if i:
            events.append({"from": "buyer", "term_sheets": [{"terms": {"unit_price": 1}}]})
        events.append({"from": "sales", "status": "open", "term_sheets": [
            {"term_sheet_id": f"offer:{i}", "terms": {"unit_price": price, "payment_days": 60}}]})
    return events


def test_payment_trade_has_explicit_financing_cost(case):
    advice = advise(case, {"evidence": []}, "sup:70270", {"unit_price": 20}, {}, thread([20]))
    rows = {r["terms"]["payment_days"]: r for r in advice["candidates"]}
    assert rows[14]["cost_at_standing_unit_price"] > rows[60]["cost_at_standing_unit_price"]
    assert rows[90]["estimated_cost"] < rows[60]["estimated_cost"]
    for row in rows.values():
        validate_sheets(case, [row["terms"]], {})


def test_estimate_never_uses_wrong_supplier_or_part(case):
    row = {"supplier_id": "sup:70270", "part_id": "part:unrelated", "unit_cost": 123}
    dossier = {"evidence": [{"table": "should_cost", "row": row}]}
    assert supplier_estimate(case, dossier, "sup:70270", {}) is None
    row["part_id"] = case["parts"][0]
    assert supplier_estimate(case, dossier, "sup:other", {}) is None
    assert supplier_estimate(case, dossier, "sup:70270", {})["full_cost"] == 123


def test_trajectory_uses_supplier_offers_not_buyer_anchors(case):
    memory = trajectory(case, thread([20, 19, 19]), None)
    assert len(memory["supplier_offers"]) == 3
    assert memory["cost_improvements_between_replies"] == [6650, 0]
    assert memory["consecutive_no_improvement"] == 1
    assert memory["messages_left"] == 8


def test_search_honors_must_haves_and_bounds(case):
    case["buyer"]["must_haves"] = [{"field": "payment_days", "op": ">=", "value": 60}]
    advice = advise(case, {"evidence": []}, "sup:70270", {"unit_price": 20}, {}, thread([20]))
    assert advice["candidates"]
    assert all(r["terms"]["payment_days"] >= 60 for r in advice["candidates"])
    case["term_options"]["payment_days"] = list(range(600))
    assert not advise(case, {"evidence": []}, "sup:70270", {"unit_price": 20}, {}, thread([20]))["candidates"]


def test_relationship_penalty_can_make_higher_price_better(case):
    case["buyer"].update(category_goal="stabilise", sustainable_margin_pct=8, relationship_eur_per_point=100000)
    dossier = {"evidence": [{"table": "should_cost", "row": {
        "supplier_id": "sup:70270", "part_id": case["parts"][0], "unit_cost": 18.3}}]}
    advice = advise(case, dossier, "sup:70270", {"unit_price": 20}, {}, thread([20]))
    assert all(r["terms"]["unit_price"] > 18 for r in advice["candidates"])


def test_advice_does_not_depend_on_hidden_results(case):
    clean = advise(case, {"evidence": []}, "sup:70270", {"unit_price": 20}, {}, thread([20]))
    poisoned = deepcopy(case)
    poisoned.update(c_best=1, score=1, hidden_floor=0.01)
    assert advise(poisoned, {"evidence": []}, "sup:70270", {"unit_price": 20}, {}, thread([20])) == clean


def test_agent_economics_policy_supplies_advice_and_keeps_guard(tmp_path, case):
    from types import SimpleNamespace

    from nighthunter.live import LiveAgent

    captured = []

    def complete(system, user):
        captured.append(user)
        return json.dumps({"supplier_id": "sup:70270", "action": "accept"})

    agent = LiveAgent(SimpleNamespace(complete=complete), SimpleNamespace(facts={}),
                      {"case": case, "evidence": []}, "adaptive", tmp_path, policy="economics")
    result = agent.decide(case, {"sup:70270": thread([20])})
    assert "economic_advice" in captured[0]
    assert not agent.decisions[0]["fallback"]
    assert result["message"]["action"]["term_sheet_id"] == "offer:0"
