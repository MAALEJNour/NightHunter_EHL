import json

import httpx
import pytest

from nighthunter.live import BudgetedModel, LiveAgent


@pytest.fixture
def model(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "gpt-5.6-luna")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("LLM_API_KEY", "test-only-key")
    instance = BudgetedModel(tmp_path / "ledger.json")
    instance.http.close()
    yield instance
    instance.close()


def test_real_usage_replaces_reservation(model):
    def respond(request):
        body = json.loads(request.content)
        assert body["max_completion_tokens"] == 128
        assert model.path.exists()  # reserve before request
        return httpx.Response(200, json={
            "usage": {"prompt_tokens": 20, "completion_tokens": 10},
            "choices": [{"message": {"content": '{"ready":true}'}}],
        })
    model.http = httpx.Client(transport=httpx.MockTransport(respond))
    assert json.loads(model.complete("system", "user", 128))["ready"]
    assert model.records[0]["accounted_usd"] == pytest.approx(0.000017)


def test_failed_request_retains_reservation(model):
    model.http = httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(404, json={"error": {"code": "model_not_found"}})))
    with pytest.raises(RuntimeError, match="model_not_found"):
        model.complete("system", "user", 128)
    assert model.records[0]["accounted_usd"] > 0
    assert model.records[0]["state"] == "failed_reservation_retained"


def test_budget_rejects_before_network(model):
    model.records = [{"accounted_usd": 5.0}]
    with pytest.raises(ValueError, match="Budget exhausted"):
        model.complete("system", "user", 128)
    assert len(model.records) == 1


def test_batch_budget_rejects_next_reservation_before_network(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "gpt-5.6-luna")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("LLM_API_KEY", "test-only-key")
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps([{"accounted_usd": 0.4}]))
    instance = BudgetedModel(ledger, batch_start_index=1, batch_limit_usd=0.0001)
    instance.http.close()
    instance.http = httpx.Client(transport=httpx.MockTransport(
        lambda request: pytest.fail("Network transport must not be invoked")))
    try:
        with pytest.raises(ValueError, match="Batch budget exhausted"):
            instance.complete("system", "user", 128)
        assert len(instance.records) == 1  # historical ledger preserved
    finally:
        instance.close()


def test_relationship_estimate_handles_missing_quote_defaults():
    from nighthunter.context import ROOT

    case = json.loads((ROOT / "vendor/negotiation-arena-kit/starter-kit/arena_kit/sim_cases/S01.json").read_text())
    case["buyer"].update(category_goal="stabilise", sustainable_margin_pct=3, relationship_eur_per_point=100)
    agent = LiveAgent.__new__(LiveAgent)
    agent.dossier = {"evidence": [{"table": "should_cost", "row": {
        "supplier_id": "sup:70270", "part_id": case["parts"][0], "unit_cost": 14}}]}
    costs = agent.costs(case, "sup:70270", {"unit_price": 16.59, "payment_days": 60}, {})
    assert len(costs) == 4
    assert all(cost >= 0 for cost in costs)


def test_live_agent_uses_rendered_checked_message(tmp_path):
    from types import SimpleNamespace

    from nighthunter.context import DEFAULT_DATA, ROOT, CaseContextBuilder

    case = json.loads((ROOT / "vendor/negotiation-arena-kit/starter-kit/arena_kit/sim_cases/S01.json").read_text())
    facts = json.loads((DEFAULT_DATA / "facts.json").read_text())
    package = SimpleNamespace(facts=facts, lookup=lambda ref: facts.get(ref))
    model = SimpleNamespace(complete=lambda *args: json.dumps({
        "supplier_id": "sup:70270", "action": "send", "body": "Bogus claim: 99% reduction.",
        "tone": "polite", "intent": "counteroffer", "claim_ids": [],
        "term_sheets": [{"unit_price": 16.5, "payment_days": 60}],
    }))
    agent = LiveAgent(model, package, CaseContextBuilder().build(case), "baseline", tmp_path)
    threads = {"sup:70270": [{"from": "sales@supplier", "status": "open",
                              "term_sheets": [{"term_sheet_id": "offer:current", "terms": {"unit_price": 17}}]}]}
    decision = agent.decide(case, threads)
    assert not agent.decisions[0]["fallback"]
    assert "99%" not in decision["message"]["body"]
    assert decision["message"]["term_sheets"][0]["terms"] == {"unit_price": 16.5, "payment_days": 60}


def test_offer_history_input_filters_used_cards_and_preserves_prior_packages(tmp_path):
    from types import SimpleNamespace

    from nighthunter.context import ROOT

    case = json.loads((ROOT / "vendor/negotiation-arena-kit/starter-kit/arena_kit/sim_cases/S01.json").read_text())
    captured = []

    def complete(system, user):
        captured.append(json.loads(user.split("\nLIVE STATE (estimated supplier financing 12%, cost +/-5%):\n", 1)[1]))
        return json.dumps({"supplier_id": "sup:70270", "action": "accept"})

    agent = LiveAgent(SimpleNamespace(complete=complete), SimpleNamespace(facts={}),
                      {"case": case, "evidence": []}, "adaptive", tmp_path,
                      policy="economics", input_version="offer_history")
    agent.cards["sup:70270"] = {
        "used": {"text": "Prior claim", "refs": ["fact:used"]},
        "fresh": {"text": "New claim", "refs": ["fact:fresh"]},
    }
    agent.used_refs.add("fact:used")
    terms = {"unit_price": 17, "payment_days": 60}
    threads = {"sup:70270": [
        {"from": "sales", "status": "open", "term_sheets": [{"term_sheet_id": "offer:0", "terms": terms}]},
        {"from": "buyer", "term_sheets": [{"terms": {"unit_price": 16.5, "payment_days": 60}}]},
        {"from": "sales", "status": "open", "term_sheets": [{"term_sheet_id": "offer:1", "terms": terms}]},
    ]}
    agent.decide(case, threads)
    state = captured[0]["sup:70270"]
    assert list(state["available_claim_cards"]) == ["fresh"]
    assert state["previously_used_refs"] == ["fact:used"]
    assert state["buyer_offer_history"] == [{
        "buyer_round": 1, "packages": [{"unit_price": 16.5, "payment_days": 60}],
        "next_supplier_status": "open",
    }]


FIXTURES = json.load(open("tests/fixtures/hosted_practice_cases.json"))


@pytest.mark.parametrize("case_id,expected", [("case:P08", {"hedge", "open_book"}),
                                              ("case:P18", {"open_book"}), ("case:P04", {"open_book"}),
                                              ("case:P02", set())])
def test_supplier_document_cards_are_built_but_not_forced(case_id, expected):
    # S8: forcing them did not help (P08 hedge backfired, open-book a no-op); the hedge card is
    # supplier-supporting (never sent), open-book stays available for the model to choose.
    from nighthunter.validation import available_claim_cards, claim_cards
    fx = FIXTURES[case_id]
    case = fx["case"]
    cards = claim_cards(case, {"evidence": fx["evidence"]}, {}, case["suppliers"][0])
    assert {"hedge", "open_book"} & set(cards) == expected
    shareable = available_claim_cards(cards)
    assert "hedge" not in shareable and ("open_book" in shareable) == ("open_book" in expected)
    assert all(shareable[k]["stance"] != "buyer_leverage" for k in ("open_book",) if k in shareable)
    assert LiveAgent.forced_claims([], shareable, {"tactics": []}, ["x"]) == ["x"]


def test_one_fresh_checked_fact_every_round():
    # S5: no case cited anything after round 1. Later rounds now add the strongest unused leverage fact.
    from nighthunter.validation import available_claim_cards, claim_cards
    fx = FIXTURES["case:P10"]
    case = fx["case"]
    facts = {e["row"]["id"]: e["citable_fact"] for e in fx["evidence"]
             if e.get("citable_fact") and e.get("row", {}).get("id")}
    cards = claim_cards(case, {"evidence": fx["evidence"]}, facts, case["suppliers"][0])
    fresh = available_claim_cards(cards, (), filter_used=True)
    later = [{"from": "buyer"}]
    picked = LiveAgent.forced_claims(later, cards, {"tactics": []}, [], fresh)
    assert len(picked) == 1 and cards[picked[0]]["stance"] == "buyer_leverage"
    used = cards[picked[0]]["refs"]
    fresh2 = available_claim_cards(cards, used, filter_used=True)
    nxt = LiveAgent.forced_claims(later, cards, {"tactics": []}, [], fresh2)
    assert nxt != picked
    assert LiveAgent.forced_claims(later, cards, {"tactics": []}, [picked[0]], fresh2)[-1] != picked[0] or not nxt


def test_late_reply_rechecks_thread_instead_of_countering_unseen_final_offer(tmp_path):
    # S10 P08: a late third e-mail countered the timeout final offer we never saw; supplier walked.
    import time

    from arena_kit.client import ArenaError

    from nighthunter.live import RecordingTable

    class Client:
        sent = []

        def thread(self, session_id, sid):
            return {"messages": [1, 2, 3, 4, 5, 6, 7], "status": "final_offer", "closed": False,
                    "offer_id": "offer:x-3", "timeouts": [{"terms": {"unit_price": 5.43}}]}

        def session(self, session_id):
            return {"status": "running"}

        def send_message(self, *args):
            self.sent.append(args)
            return {"status": "open", "term_sheets": []}

    client = Client()
    table = RecordingTable(client, tmp_path)
    table.session_id = "s"
    table.replied_at["sup"], table.seen["sup"] = time.monotonic() - 50, 6
    with pytest.raises(ArenaError):
        table.send("sup", {"body": "late counter"})
    assert client.sent == []
    reply = table.missed("sup", ArenaError(409, "late"))
    assert reply["status"] == "final_offer" and reply["term_sheets"][0]["term_sheet_id"] == "offer:x-3"
    table.send("sup", {"body": "on time"})  # just answered: no check, sent normally
    assert len(client.sent) == 1


def test_breakdown_requested_once_from_open_book_suppliers(monkeypatch):
    monkeypatch.setattr(LiveAgent, "ASK_BREAKDOWN", True)
    from nighthunter.validation import REQUESTS
    assert "breakdown" in REQUESTS["cost_breakdown"].lower()
    assert LiveAgent.asks_breakdown([], {"open_book": {}})
    assert not LiveAgent.asks_breakdown([{"from": "buyer"}], {"open_book": {}})
    assert not LiveAgent.asks_breakdown([], {"quality": {}})


def test_volume_question_answered_with_binding_sheet_volume():
    fx = FIXTURES["case:P02"]
    case = fx["case"]
    asked = [{"from": "sales", "body": "Please provide the specific volume figures. Which volume can you commit to?"}]
    terms = [{"unit_price": 360.0, "payment_days": 90, "index_clause": None}]
    answer = LiveAgent.volume_answer(case, asked, terms)
    assert answer == ["To answer your question on volume: each option commits to 6110 units per year for 12 months "
                      "(6110 units in total), our full requirement for this part."]
    assert LiveAgent.volume_answer(case, [{"from": "sales", "body": "Our price stands."}], terms) == []


def test_sheet_missing_a_negotiable_field_is_still_negotiated(tmp_path, monkeypatch):
    # Local P12: opening sheet {"unit_price"} only, quote without ppm -> the agent used to give up at once.
    from types import SimpleNamespace
    case = json.loads(json.dumps(FIXTURES["case:P11"]["case"]))
    std = {k: v for k, v in FIXTURES["case:P11"]["standard_terms"].items() if k != "ppm_commitment"}
    monkeypatch.setattr("nighthunter.live.standard_terms", lambda events: std)
    model = SimpleNamespace(complete=lambda *a, **k: "{}", reasoning_effort="low", name="offline")
    agent = LiveAgent(model, type("P", (), {"facts": {}})(), {"case": case, "evidence": []}, "adaptive",
                      tmp_path, policy="packages", adaptation="expert_prose")
    sid = case["suppliers"][0]
    opening = [{"from": "sales", "status": "open", "body": "",
                "term_sheets": [{"term_sheet_id": "offer:x-0", "terms": {"unit_price": 47.0}}]}]
    decision = agent.decide(case, {sid: opening})
    assert decision["message"].get("term_sheets"), decision


def test_data_question_answered_with_rising_forecast_and_rfq_volume_stated():
    # Codex audit: forecast facts drew "took it into account" 30/38; P05 bidders asked for volume 83x.
    cards = {"forecast:part:1": {"text": "The recorded demand forecast change is +10.3% (fc:1@2026-09).",
                                 "refs": ["fc:1@2026-09"], "stance": "neutral_unknown"},
             "forecast:part:2": {"text": "The recorded demand forecast change is -4.0% (fc:2@2026-09).",
                                 "refs": ["fc:2@2026-09"], "stance": "neutral_unknown"}}
    asked = [{"from": "sales"}, {"from": "buyer"}, {"from": "sales", "body": "Which figures is that based on?"}]
    assert LiveAgent.forced_claims(asked, cards, {"tactics": []}, [], dict(cards)) == ["forecast:part:1"]
    quiet = [{"from": "sales"}, {"from": "buyer"}, {"from": "sales", "body": "Our price stands."}]
    assert LiveAgent.forced_claims(quiet, cards, {"tactics": []}, [], dict(cards)) == []
    rfq = json.load(open("tests/fixtures/rfq_p05.json"))["case"]
    first = LiveAgent.volume_answer(rfq, [{"from": "sales", "body": ""}], [{"unit_price": 28.0}], proactive=True)
    assert first and "4200 units per year for 24 months" in first[0]
