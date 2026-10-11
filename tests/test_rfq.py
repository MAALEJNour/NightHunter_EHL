"""RFQ decisions on the hosted P05 case (three bidders), built from public case data only."""

import json

from arena_kit.cost import total_cost

from nighthunter.context import ROOT
from nighthunter.rfq import acceptable_offers, close_decision, plan_rfq, rank_bidders, rival_benchmark, rival_claims
from nighthunter.supplier_profile import build_profile
from nighthunter.validation import validate_sheets

FX = json.loads((ROOT / "tests/fixtures/rfq_p05.json").read_text())
CASE = FX["case"]
STD = {sid: b["standard_terms"] for sid, b in FX["bidders"].items()}
DOSSIER = {"evidence": FX["evidence"]}
PROFILES = {sid: build_profile(CASE, DOSSIER, sid) for sid in CASE["suppliers"]}


def opening():
    return {sid: [{"from": "sales", "status": "open", "term_sheets": [b["opening_offer"]]}]
            for sid, b in FX["bidders"].items()}


def reply(threads, sid, offer_id, status="open", **terms):
    threads[sid].append({"from": "buyer", "term_sheets": []})
    threads[sid].append({"from": "sales", "status": status,
                         "term_sheets": [{"term_sheet_id": offer_id, "terms": terms}]})


def test_only_compliant_primary_offers_are_acceptable():
    offers = acceptable_offers(CASE, opening(), STD)
    # 70240 quotes 31.50 but 52-day lead time breaks the <= 42 must-have.
    assert [o[1] for o in offers] == ["sup:70210", "sup:70250"]


def test_rival_claims_cite_only_lower_prices():
    threads = opening()
    claims_70250 = rival_claims(CASE, threads, STD, "sup:70250")
    assert [c["supplier_id"] for c in claims_70250] == ["sup:70240", "sup:70210"]
    assert claims_70250[0]["unit_price"] == 31.5 and not claims_70250[0]["compliant"]
    assert rival_claims(CASE, threads, STD, "sup:70240") == []  # cheapest bidder: nothing lower to cite


def test_motivation_ranking_from_dossier_signals():
    ranking = rank_bidders(CASE, DOSSIER, PROFILES)
    assert ranking[0]["supplier_id"] == "sup:70250"  # free capacity + cash request + reference customer
    assert ranking[-1]["supplier_id"] == "sup:70240"  # fully booked, commitment condition
    top = ranking[0]
    assert {"deepest_ask", "price_early_payment"} <= set(top["tactics"])
    assert "price_reference_only" in ranking[-1]["tactics"]
    assert all(s["ref"] for r in ranking for s in r["signals"])


def test_round0_plans_are_valid_for_every_bidder():
    plans = plan_rfq(CASE, opening(), STD, PROFILES)
    assert set(plans) == set(CASE["suppliers"])
    for sid, plan in plans.items():
        assert plan["packages"], sid
        validate_sheets(CASE, [p["terms"] for p in plan["packages"]], STD[sid])  # incl. lead <= 42


def test_concessions_never_exceed_best_rival_bid():
    threads = opening()
    # 70210 drops to 30.00 at 35 days lead; 70250 still at its opening.
    reply(threads, "sup:70210", "offer:70210-1", unit_price=30.0, payment_days=30, lead_time_days=35)
    cap = rival_benchmark(CASE, threads, STD, "sup:70250")
    assert cap == total_cost(CASE, {"unit_price": 30.0, "payment_days": 30, "lead_time_days": 35}, STD["sup:70210"])
    plan = plan_rfq(CASE, threads, STD, PROFILES)["sup:70250"]
    assert all(p["estimated_total_cost"] < cap for p in plan["packages"])


def test_close_waits_while_bidders_are_open_then_takes_cheapest_primary():
    threads = opening()
    plans = plan_rfq(CASE, threads, STD, PROFILES)
    assert close_decision(CASE, threads, STD, plans) is None
    reply(threads, "sup:70210", "offer:70210-3", status="final_offer", unit_price=29.0, payment_days=30,
          lead_time_days=35)
    reply(threads, "sup:70250", "offer:70250-3", status="final_offer", unit_price=29.5, payment_days=30,
          lead_time_days=28)
    reply(threads, "sup:70240", "offer:70240-3", status="final_offer", unit_price=27.0, payment_days=45,
          lead_time_days=52)  # cheapest, but breaks the must-have: never accepted
    decision = close_decision(CASE, threads, STD, plan_rfq(CASE, threads, STD, PROFILES))
    assert decision["message"]["action"] == {"type": "accept", "term_sheet_id": "offer:70210-3"}


def test_walkaways_are_excluded():
    threads = opening()
    threads["sup:70210"].append({"from": "sales", "status": "walked_away", "term_sheets": []})
    assert "sup:70210" not in plan_rfq(CASE, threads, STD, PROFILES)
    assert [o[1] for o in acceptable_offers(CASE, threads, STD)] == ["sup:70250"]


def test_high_opener_is_held_to_the_market_target():
    plans = plan_rfq(CASE, opening(), STD, PROFILES)
    targets = {sid: p["target_cost"] for sid, p in plans.items()}
    # 70250 opened at 38.50: it must not get a softer ask than the bidder that opened at 31.50.
    assert targets["sup:70250"] <= targets["sup:70240"] + 0.01
    assert max(p["terms"]["unit_price"] for p in plans["sup:70250"]["packages"]) < 31.5


def test_off_option_lead_time_is_never_snapped_into_compliance():
    # Codex review: a quoted 43 days must not become 42 and pass lead_time_days <= 42.
    threads = opening()
    reply(threads, "sup:70210", "offer:probe", status="final_offer", unit_price=20.0, payment_days=30,
          lead_time_days=43)
    assert "sup:70210" not in [o[1] for o in acceptable_offers(CASE, threads, STD)]
    reply(threads, "sup:70250", "offer:70250-9", status="final_offer", unit_price=33.0, payment_days=30,
          lead_time_days=28)
    reply(threads, "sup:70240", "offer:70240-9", status="final_offer", unit_price=19.0, payment_days=45,
          lead_time_days=52)
    decision = close_decision(CASE, threads, STD, plan_rfq(CASE, threads, STD, PROFILES))
    assert decision["message"]["action"]["term_sheet_id"] == "offer:70250-9"


def test_missing_field_without_quote_default_is_not_acceptable():
    # 70240's quote has no lead-time default: a primary omitting lead time cannot be completed.
    assert "lead_time_days" not in STD["sup:70240"]
    threads = opening()
    reply(threads, "sup:70240", "offer:70240-2", status="final_offer", unit_price=18.0, payment_days=45)
    assert "sup:70240" not in [o[1] for o in acceptable_offers(CASE, threads, STD)]
    for sid in ("sup:70210", "sup:70250"):
        threads[sid].append({"from": "sales", "status": "walked_away", "term_sheets": []})
    decision = close_decision(CASE, threads, STD, {})
    assert decision["message"]["action"]["type"] == "walk_away"


def test_quote_defaults_fill_missing_fields_exactly():
    threads = opening()  # 70210 opening quotes only a price; payment 30 / lead 28 come from its quote
    offer = next(o for o in acceptable_offers(CASE, threads, STD) if o[1] == "sup:70210")
    assert offer[3] == {"unit_price": 36.0, "payment_days": 30, "lead_time_days": 28}


def test_market_target_applies_only_to_a_bidders_first_message():
    threads = opening()
    first = plan_rfq(CASE, threads, STD, PROFILES)
    # 70250 replies after our first message: its next ask follows its own path, not the market minimum.
    threads["sup:70250"].append({"from": "buyer", "term_sheets": [{"terms": p["terms"]}
                                                                for p in first["sup:70250"]["packages"]]})
    threads["sup:70250"].append({"from": "sales", "status": "open", "term_sheets": [
        {"term_sheet_id": "offer:70250-1", "terms": {"unit_price": 35.0, "payment_days": 30, "lead_time_days": 28}}]})
    second = plan_rfq(CASE, threads, STD, PROFILES)
    assert second["sup:70250"]["target_cost"] > first["sup:70250"]["target_cost"]


def test_best_bidder_final_offer_is_taken_at_once_while_others_are_open():
    # Practice P05 (11 Oct): 70250's final offer was the best acceptable one, but we waited for a slower
    # bidder; its 60 s ran out, it walked away and our late accept failed (no deal, score 0).
    threads = opening()
    reply(threads, "sup:70250", "offer:70250-4", status="final_offer", unit_price=28.0, payment_days=30,
          lead_time_days=28)
    reply(threads, "sup:70240", "offer:70240-3", status="open", unit_price=33.5, payment_days=30,
          lead_time_days=42)
    decision = close_decision(CASE, threads, STD, plan_rfq(CASE, threads, STD, PROFILES))
    assert decision["message"]["action"] == {"type": "accept", "term_sheet_id": "offer:70250-4"}


def test_rfq_send_retries_busy_session(tmp_path, monkeypatch):
    # The arena runs one call per session at a time; "409 busy ... retry" must be retried, not fatal.
    import sys
    import time as _time
    sys.path.insert(0, str(ROOT / "scripts"))
    from arena_kit.client import ArenaError
    from rfq_live import RfqNegotiator
    monkeypatch.setattr(_time, "sleep", lambda s: None)
    calls = []

    class Client:
        def send_message(self, session_id, sid, message):
            calls.append(sid)
            if len(calls) < 3:
                raise ArenaError(409, "busy: another call on this session is still running; retry")
            return {"status": "open"}

    rfq = RfqNegotiator(Client(), "case:P05", tmp_path)
    rfq.session_id, rfq.deadline = "s", _time.time() + 100
    assert rfq.send("sup:70250", {"body": "x"}) == {"status": "open"} and len(calls) == 3
