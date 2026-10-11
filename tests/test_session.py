"""Offline feedback and price-freeze adaptation checks; no hosted clients."""

import json
from types import SimpleNamespace

from nighthunter.context import ROOT
from nighthunter.live import LiveAgent
from nighthunter.session import is_price_only_cut, thread_observations


def case():
    return json.loads((ROOT / "vendor/negotiation-arena-kit/starter-kit/arena_kit/sim_cases/S01.json").read_text())


def test_observations_keep_supplier_claim_feedback_and_rounds_separate():
    example = case()
    example["c_best"] = 0  # A post-run-looking field must not appear in observations.
    decisions = [{"validation": {"selected_claims": ["quality"]},
                  "executed": {"supplier_id": "sup:70270"}}]
    events = [
        {"from": "sales", "status": "open", "term_sheets": [{
            "term_sheet_id": "offer:old", "terms": {"unit_price": 20, "payment_days": 30}}]},
        {"from": "buyer", "term_sheets": []},
        {"from": "sales", "message_id": "msg:latest", "status": "open",
         "body": "Management has frozen all price reductions. We can talk about the terms instead - "
                 "payment or contract length. Your figures hold but do not change our calculation. "
                 "Pricing committee approval would be needed.",
         "term_sheets": [{"term_sheet_id": "offer:new", "terms": {
             "unit_price": 19, "payment_days": 30}}],
         "claim_results": [{"index": 0, "result": "verified"}]},
    ]
    state = thread_observations(example, events, decisions, "sup:70270")
    assert state["price_freeze_reported"] and state["approval_reported"]
    assert state["flexible_fields_reported"] == ["payment_days"]
    assert state["recent_claim_results"] == [{"claim_id": "quality", "result": "verified"}]
    assert state["recent_claims_dismissed_in_prose"] == ["quality"]
    assert state["recent_primary_offers"][0]["currently_active"] is False
    assert state["recent_primary_offers"][1]["currently_active"] is True
    assert state["buyer_messages_left"] == example.get("round_limit", 10) - 1
    assert "c_best" not in json.dumps(state)


def test_price_only_cut_recognizes_unchanged_other_terms():
    example = case()
    standing = {"unit_price": 20, "payment_days": 30}
    assert is_price_only_cut(example, standing, {"unit_price": 19, "payment_days": 30})
    assert not is_price_only_cut(example, standing, {"unit_price": 19, "payment_days": 60})
    assert not is_price_only_cut(example, standing, {"unit_price": 20, "payment_days": 30})


def test_negated_flexibility_does_not_become_a_supplier_priority():
    example = case()
    events = [{"from": "sales", "status": "open",
               "body": "We are not flexible on payment terms. No price reduction is available.",
               "term_sheets": []}]
    assert thread_observations(example, events, [], "sup:70270")["flexible_fields_reported"] == []


def test_reply_aware_replaces_frozen_price_only_repeat_with_nonprice_trade(tmp_path):
    example = case()
    model = SimpleNamespace(complete=lambda *_: json.dumps({
        "supplier_id": "sup:70270", "action": "send", "tone": "polite",
        "intent": "counteroffer", "claim_ids": [],
        "term_sheets": [{"unit_price": 19, "payment_days": 30}]}))
    package = SimpleNamespace(facts={}, lookup=lambda _ref: None)
    agent = LiveAgent(model, package, {"case": example, "evidence": []},
                      "adaptive", tmp_path, adaptation="reply_aware")
    events = [{"from": "sales", "status": "open",
               "body": "Management has frozen all price reductions. We can talk about payment terms.",
               "term_sheets": [{"term_sheet_id": "offer:current", "terms": {
                   "unit_price": 20, "payment_days": 30}}]}]
    decision = agent.decide(example, {"sup:70270": events})
    assert not agent.decisions[0]["fallback"]
    assert agent.decisions[0]["frozen_price_only_sheets_removed"] == 1
    sheets = decision["message"]["term_sheets"]
    assert sheets and all(s["terms"]["unit_price"] == 20 for s in sheets)
    assert all(s["terms"]["payment_days"] > 30 for s in sheets)
    assert "Package" in decision["message"]["body"]
