import json
from copy import deepcopy

import pytest

from nighthunter.context import DEFAULT_DATA, ROOT, CaseContextBuilder
from nighthunter.validation import available_claim_cards, claim_cards, render_message, validate_sheets


@pytest.fixture
def inputs():
    # Minimal case contract derived from the public P01 trigger, not a hosted result.
    case = {
        "case_id": "test:P01", "title": "Price increase", "suppliers": ["sup:70110"],
        "parts": ["part:310010"], "trigger_doc": "doc:20260911-70110-P01",
        "refs": ["doc:20260911-70110-P01", "ctr:4600070110", "quote:7200001", "sc:70110@2026Q3"],
        "negotiable": ["unit_price", "effective_date", "payment_days"],
        "term_options": {"effective_date": ["2026-11-01", "2027-01-01"], "payment_days": [30, 60, 90]},
        "fixed_terms": {"volume_per_year": 8150, "contract_months": 12, "lead_time_days": 42, "incoterm": "FCA"},
        "buyer": {"need_per_year": 8150, "horizon_years": 1, "reference_payment_days": 60,
                  "need_lead_time_days": 45, "freight_eur_per_unit": {"FCA": 1.9}, "must_haves": []},
    }
    dossier = CaseContextBuilder().build(case, 40000)
    facts = json.loads((DEFAULT_DATA / "facts.json").read_text())
    return case, dossier, facts


def test_historical_quote_not_usable_as_rival(inputs):
    case, dossier, facts = inputs
    cards = claim_cards(case, dossier, facts, "sup:70110")
    assert "quote:quote:7200001" in cards
    assert cards["quote:quote:7200001"]["disclosure"] == "internal_only"
    assert all("quote:7300001" not in card["refs"] for card in cards.values())
    assert "51 days" in cards["notice"]["text"] and "90 days" in cards["notice"]["text"]
    assert "+10.1%" in cards["forecast:part:310010"]["text"]
    assert cards["notice"]["stance"] == "buyer_leverage"


def test_irrelevant_part_and_expired_contract_excluded(inputs):
    case, dossier, facts = inputs
    facts = deepcopy(facts)
    facts["quote:7200001"]["part"] = "part:unrelated"
    facts["ctr:4600070110"]["valid_to"] = "2020-01-01"
    cards = claim_cards(case, dossier, facts, "sup:70110")
    assert "quote:quote:7200001" not in cards and "notice" not in cards


def test_null_notice_days_do_not_crash_live_card_building(inputs):
    case, dossier, facts = inputs
    facts = deepcopy(facts)
    facts[case["trigger_doc"]]["days"] = None
    assert "notice" not in claim_cards(case, dossier, facts, case["suppliers"][0])


def test_index_values_are_computed_not_model_assertions(inputs):
    case, dossier, facts = inputs
    cards = claim_cards(case, dossier, facts, "sup:70110")
    index_cards = [v for k, v in cards.items() if k.startswith("index:")]
    assert index_cards
    for card in index_cards:
        a, b = [facts[r] for r in card["refs"]]
        expected = (b["value"] / a["value"] - 1) * 100
        assert f"{expected:+.1f}%" in card["text"]
        assert a["series"] == b["series"]


def test_prose_cannot_smuggle_false_claims_and_duplicates_are_omitted(inputs):
    case, dossier, facts = inputs
    cards = claim_cards(case, dossier, facts, "sup:70110")
    proposal = {"body": "138 is above 143 (quote:7300001). Prices fell 99%.", "tone": "polite",
                "claim_ids": ["notice", "forecast:part:310010"],
                "term_sheets": [{"unit_price": 134, "effective_date": "2027-01-01", "payment_days": 60}]}
    msg, report = render_message(proposal, cards, {"doc:20260911-70110-P01"}, case, {})
    assert "99%" not in msg["body"] and "7300001" not in msg["body"]
    assert report["duplicate_claims_omitted"] == ["notice"]
    assert report["model_prose_discarded"]
    assert "unit_price=134" in msg["body"]
    assert msg["refs"] == ["fc:310010@2026-09"]


@pytest.mark.parametrize("bad", [
    {"unit_price": 134},
    {"unit_price": -1, "effective_date": "2027-01-01", "payment_days": 60},
    {"unit_price": float("nan"), "effective_date": "2027-01-01", "payment_days": 60},
    {"unit_price": 134, "effective_date": "2027-01-01", "payment_days": 75},
    {"unit_price": 134.123, "effective_date": "2027-01-01", "payment_days": 60},
    {"unit_price": 134, "effective_date": "2027-01-01", "payment_days": True},
])
def test_invalid_packages_rejected_without_silent_snapping(inputs, bad):
    with pytest.raises(ValueError):
        validate_sheets(inputs[0], [bad], {})


def test_unknown_card_and_must_have_rejected(inputs):
    case, dossier, facts = inputs
    cards = claim_cards(case, dossier, facts, "sup:70110")
    with pytest.raises(ValueError, match="Unknown claim"):
        render_message({"claim_ids": ["made-up"]}, cards, set(), case, {})
    case["buyer"]["must_haves"] = [{"field": "payment_days", "op": ">=", "value": 60}]
    with pytest.raises(ValueError, match="must-haves"):
        validate_sheets(case, [{"unit_price": 134, "effective_date": "2027-01-01", "payment_days": 30}], {})


def test_central_estimate_does_not_treat_upper_bound_as_certainty():
    from nighthunter.live import LiveAgent

    case = json.loads((ROOT / "vendor/negotiation-arena-kit/starter-kit/arena_kit/sim_cases/S01.json").read_text())
    case["buyer"]["alternative"] = {"terms": {"unit_price": 20}, "kind": "quote"}
    agent = LiveAgent.__new__(LiveAgent)
    agent.dossier = {"evidence": []}
    agent.costs = lambda *args: [100, 110, 120, 1e9]
    threads = {"sup:70270": [{"from": "sales@supplier", "status": "open",
                              "term_sheets": [{"term_sheet_id": "offer:current", "terms": {
                                  "unit_price": 17, "payment_days": 60}}]}]}
    assert agent.safe_close(case, threads)["message"]["action"]["type"] == "accept"


def test_compliant_notice_is_not_breach_and_estimate_stays_internal():
    case = {"parts": ["part:350011"], "suppliers": ["sup:70510"],
            "trigger_doc": "doc:test", "refs": ["ctr:test"],
            "buyer": {"alternative": {}}}
    dossier = {"evidence": [{"table": "should_cost", "source": "cost:test",
                             "row": {"id": "cost:test"}}]}
    facts = {"doc:test": {"supplier": "sup:70510", "date": "2026-09-14", "days": 109},
             "ctr:test": {"supplier": "sup:70510", "valid_from": "2026-01-01",
                          "valid_to": "2026-12-31", "days": 90},
             "cost:test": {"part": "part:350011", "unit_cost": 374.95}}
    cards = claim_cards(case, dossier, facts, "sup:70510")
    assert cards["notice"]["stance"] == "neutral_unknown"
    assert "no breach" in cards["notice"]["reason"]
    assert cards["estimate:cost:test"]["disclosure"] == "internal_only"
    assert "estimate:cost:test" not in available_claim_cards(cards)
    facts["doc:test"]["days"] = 51
    assert claim_cards(case, dossier, facts, "sup:70510")["notice"]["stance"] == "buyer_leverage"


def test_rising_index_is_supplier_supporting_and_not_selectable(inputs):
    case, dossier, facts = inputs
    cards = claim_cards(case, dossier, facts, "sup:70110")
    rising = [k for k, c in cards.items() if k.startswith("index:") and c["stance"] == "supplier_supporting"]
    assert rising
    assert all(k not in available_claim_cards(cards) for k in rising)
    with pytest.raises(ValueError, match="not available"):
        render_message({"claim_ids": [rising[0]]}, cards, set(), case, {})
