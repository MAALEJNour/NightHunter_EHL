"""Expert e-mail composition: code-rendered figures, filtered model framing; fake model, no HTTP."""

import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from nighthunter.context import ROOT
from nighthunter.live import LiveAgent
from nighthunter.prose import check_text, compose, concession_line, describe_terms, salutation

FIXTURES = json.loads((ROOT / "tests/fixtures/hosted_practice_cases.json").read_text())
P02 = FIXTURES["case:P02"]["case"]
SUPPLIER_MAIL = ("Dear Sir or Madam,\n\nOur offer stands. Which volume can you commit to?\n\n"
                 "Mit freundlichen Grüßen\nPetra Lechner\nKey Account Manager, Antriebstechnik Nordmark AG")


@pytest.mark.parametrize("text,reason", [
    ("We can pay in 14 days.", "digits"),
    ("Our target is a lower euro price.", "money_or_percent"),
    ("As shown in doc:visit-note your delivery slipped.", "data_id"),
    ("A competitor has offered better terms.", "competition_claim"),
    ("Another supplier is ready to start.", "competition_claim"),
    ("Our budget is tight this year.", "leakage"),
    ("Otherwise we will walk away.", "threat"),
    ("We can promise additional volume next year.", "future_commitment"),
    ("We know your margin can absorb this.", "supplier_cost_claim"),
    ("Please escalate this to your manager.", "escalation"),
])
def test_banned_framing_is_rejected(text, reason):
    assert check_text(text) == (None, reason)


def test_clean_framing_passes_and_escalation_only_when_allowed():
    assert check_text("Thank you for explaining the copper situation so clearly.")[0]
    assert check_text("Could your pricing committee review option A?", allow_escalation=True)[0]


def test_describe_terms_is_plain_language_for_every_field():
    text = describe_terms(P02, {"unit_price": 361.53, "payment_days": 90, "index_clause": None})
    assert text == "EUR 361.53 per unit, payment 90 days net, fixed price, no index clause"
    assert "=" not in text and "{" not in text


def test_salutation_uses_full_signed_name_without_gender():
    assert salutation([{"from": "sales", "body": SUPPLIER_MAIL}]) == "Dear Petra Lechner,"
    assert salutation([{"from": "sales", "body": "no signature"}]) == "Good day,"


def test_concession_is_labelled_with_code_figures():
    events = [{"from": "buyer", "term_sheets": [{"terms": {"unit_price": 356.0, "payment_days": 90,
                                                           "index_clause": None}}]}]
    line = concession_line(P02, events, [{"unit_price": 358.5, "payment_days": 90, "index_clause": None}])
    assert "from EUR 356.00 to EUR 358.50" in line


def test_compose_drops_bad_paragraphs_and_keeps_exact_options():
    events = [{"from": "sales", "body": SUPPLIER_MAIL}]
    packages = [{"unit_price": 361.53, "payment_days": 90, "index_clause": None},
                {"unit_price": 356.74, "payment_days": 30, "index_clause": None}]
    choice = {"opening": "Thank you, Ms Lechner; the volume in our options is our full annual need.",
              "rationale": "A competitor quoted less.", "closing": "Which option suits you best?"}
    body, diag = compose(P02, events, packages, ["Checked fact sentence."], choice, "fallback request")
    assert body.startswith("Dear Petra Lechner,")
    assert "competitor" not in body and diag["rationale_dropped"] == "competition_claim"
    assert "Option A: EUR 361.53 per unit, payment 90 days net" in body
    assert "Option B: EUR 356.74 per unit, payment 30 days net" in body
    assert "Checked fact sentence." in body and body.rstrip().endswith("Hollerau Pumpenwerke GmbH")


def test_live_expert_prose_sends_planned_terms_with_filtered_framing(tmp_path, monkeypatch):
    fx = deepcopy(FIXTURES["case:P02"])
    case, standard = fx["case"], fx["standard_terms"]
    monkeypatch.setattr("nighthunter.live.standard_terms", lambda events: standard)
    answer = {"tone": "partnership", "intent": "counteroffer", "claim_ids": [],
              "opening": "Thank you for the clear explanation of the copper development.",
              "rationale": "Longer payment costs you little and gives us room; we can pay in 90 days.",
              "closing": "Which of the options would you prefer?",
              "term_sheets": [{"unit_price": 1.0}]}
    agent = LiveAgent(SimpleNamespace(complete=lambda s, u: json.dumps(answer)), SimpleNamespace(facts={}),
                      {"case": case, "evidence": fx["evidence"]}, "adaptive", tmp_path,
                      policy="packages", adaptation="expert_prose")
    sid = case["suppliers"][0]
    threads = {sid: [{"from": "sales", "status": "open", "term_sheets": [fx["opening_offer"]],
                      "body": SUPPLIER_MAIL}]}
    decision = agent.decide(case, threads)
    record = agent.decisions[0]
    body = decision["message"]["body"]
    assert not record["fallback"]
    assert decision["message"]["term_sheets"] == [{"terms": r["terms"]} for r in record["plan"]["packages"]]
    assert "copper development" in body and "Which of the options" in body
    assert record["prose"]["rationale_dropped"] == "digits"
    assert "=" not in body


def test_expert_prose_requires_packages_policy(tmp_path):
    fx = FIXTURES["case:P02"]
    with pytest.raises(ValueError):
        LiveAgent(SimpleNamespace(complete=None), SimpleNamespace(facts={}),
                  {"case": fx["case"], "evidence": fx["evidence"]}, "adaptive", tmp_path,
                  policy="current", adaptation="expert_prose")


def test_authority_claim_stops_approval_requests():
    from nighthunter.supplier_profile import session_signals
    events = [{"from": "sales", "body": "As Segment Manager, I hold full authority over this negotiation."}]
    assert session_signals(events)["authority_claimed"]
    assert "authority_claimed" not in session_signals([{"from": "sales", "body": "Our offer stands."}])


def test_no_thousands_separators_in_rendered_figures():
    # Teammate P11: "2,376 ppm" was marked contradicted; keep every figure in plain digits.
    p10 = FIXTURES["case:P10"]["case"]
    text = describe_terms(p10, {"unit_price": 1234.5, "volume_per_year": 23400, "contract_months": 36,
                                "lead_time_days": 35})
    assert "23400 pcs" in text and "1234.50" in text and "," not in text.replace(", ", "")


def test_one_empty_model_reply_is_retried_not_fatal(tmp_path, monkeypatch):
    fx = deepcopy(FIXTURES["case:P02"])
    case, standard = fx["case"], fx["standard_terms"]
    monkeypatch.setattr("nighthunter.live.standard_terms", lambda events: standard)
    replies = iter(["", json.dumps({"tone": "polite", "intent": "counteroffer", "claim_ids": [],
                                    "opening": "Thank you for the offer.", "rationale": "Fair options.",
                                    "closing": "Which option suits you?"})])
    agent = LiveAgent(SimpleNamespace(complete=lambda s, u: next(replies)), SimpleNamespace(facts={}),
                      {"case": case, "evidence": fx["evidence"]}, "adaptive", tmp_path,
                      policy="packages", adaptation="expert_prose")
    sid = case["suppliers"][0]
    agent.decide(case, {sid: [{"from": "sales", "status": "open", "term_sheets": [fx["opening_offer"]],
                               "body": SUPPLIER_MAIL}]})
    record = agent.decisions[0]
    assert not record["fallback"] and record.get("model_retry") and not agent.disabled


def test_notice_evidence_is_cited_when_deferring_the_start_date(tmp_path, monkeypatch):
    fx = deepcopy(FIXTURES["case:P01"])
    case, standard = fx["case"], fx["standard_terms"]
    monkeypatch.setattr("nighthunter.live.standard_terms", lambda events: standard)
    facts = {}
    for e in fx["evidence"]:
        if e.get("citable_fact") and e.get("source"):
            facts[e["source"].split(":", 1)[1]] = e["citable_fact"]
    answer = {"tone": "partnership", "intent": "counteroffer", "claim_ids": [],
              "opening": "Thank you for the letter.", "rationale": "Fair options.", "closing": "Which suits you?"}
    agent = LiveAgent(SimpleNamespace(complete=lambda s, u: json.dumps(answer)), SimpleNamespace(facts=facts),
                      {"case": case, "evidence": fx["evidence"]}, "adaptive", tmp_path,
                      policy="packages", adaptation="expert_prose")
    sid = case["suppliers"][0]
    if "notice" not in agent.cards[sid]:
        pytest.skip("fixture lacks the contract fact needed for the notice card")
    decision = agent.decide(case, {sid: [{"from": "sales", "status": "open",
                                          "term_sheets": [fx["opening_offer"]], "body": SUPPLIER_MAIL}]})
    assert "notice" in agent.decisions[0]["validation"]["selected_claims"]
    assert case["trigger_doc"] in decision["message"]["refs"]


def test_required_request_survives_model_closing():
    from nighthunter.prose import compose
    case = {"negotiable": ["unit_price"], "buyer": {}, "title": "t"}
    choice = {"closing": "Which option is closest to your preferred structure?"}
    body, diag = compose(case, [{"from": "sales"}], [{"unit_price": 5.0}], [], choice,
                         "Could you share a cost breakdown?", require_request=True)
    assert "cost breakdown" in body and "closest to your preferred" in body and diag["required_request"]
    body, _ = compose(case, [{"from": "sales"}], [{"unit_price": 5.0}], [], choice, "Could you share a cost breakdown?")
    assert "cost breakdown" not in body
