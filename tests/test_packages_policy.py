"""Offline integration checks for the opt-in package policy; fake model, no HTTP."""

import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from arena_kit.cost import must_haves_ok

from nighthunter.context import ROOT
from nighthunter.live import LiveAgent


FIXTURES = json.loads((ROOT / "tests/fixtures/hosted_practice_cases.json").read_text())


def make_agent(tmp_path, monkeypatch, *, answer=None, policy="packages", case_id="case:P02",
               configure=None):
    fx = deepcopy(FIXTURES[case_id])
    case, standard = fx["case"], fx["standard_terms"]
    if configure:
        configure(case, fx["opening_offer"])
    monkeypatch.setattr("nighthunter.live.standard_terms", lambda events: standard)
    calls = []

    def complete(system, user):
        calls.append((system, user))
        if isinstance(answer, Exception):
            raise answer
        return json.dumps(answer or {"tone": "polite", "intent": "counteroffer", "claim_ids": []})

    agent = LiveAgent(SimpleNamespace(complete=complete), SimpleNamespace(facts={}),
                      {"case": case, "evidence": fx["evidence"]}, "adaptive", tmp_path, policy=policy)
    sid = case["suppliers"][0]
    threads = {sid: [{"from": "sales", "status": "open", "term_sheets": [fx["opening_offer"]]}]}
    return agent, case, sid, threads, calls


def test_packages_are_sent_exactly_and_model_terms_are_ignored(tmp_path, monkeypatch):
    answer = {"tone": "partnership", "intent": "approval", "claim_ids": [],
              "action": "accept", "supplier_id": "sup:fake",
              "body": "Unsupported promise", "term_sheets": [{"unit_price": 0.01}]}
    agent, case, sid, threads, calls = make_agent(tmp_path, monkeypatch, answer=answer)
    decision = agent.decide(case, threads)
    record = agent.decisions[0]
    assert not record["fallback"]
    assert decision["supplier_id"] == sid
    assert decision["message"]["term_sheets"] == [
        {"terms": row["terms"]} for row in record["plan"]["packages"]]
    assert "Unsupported promise" not in decision["message"]["body"]
    assert "approval" in calls[0][0].lower()
    state = json.loads(calls[0][1].split("\nLIVE STATE:\n", 1)[1])[sid]
    assert state["plan"] == record["plan"]
    assert state["profile"] == record["profile"]
    approval = next(t for t in state["profile"]["tactics"] if t["tactic"] == "request_approval")
    assert approval["refs"] and approval["provenance"] == "source_linked"
    assert state["approval_intent_hint"] == record["approval_hint"]
    assert json.loads((tmp_path / "decisions.json").read_text())[0]["plan"] == record["plan"]


def test_recommend_accept_uses_safe_close_without_model(tmp_path, monkeypatch):
    agent, case, sid, threads, calls = make_agent(tmp_path, monkeypatch)
    monkeypatch.setattr("nighthunter.live.plan_packages", lambda *a, **k: {
        "recommend_accept": True, "packages": [], "target_cost": 0})
    decision = agent.decide(case, threads)
    assert decision["message"]["action"] == {
        "type": "accept", "term_sheet_id": threads[sid][0]["term_sheets"][0]["term_sheet_id"]}
    assert not calls
    assert agent.decisions[0]["close_reason"] == "planner_recommends_accept"


@pytest.mark.parametrize("status,remaining,expected", [
    ("final_offer", 10, "final_offer"), ("open", 1, "last_buyer_message")])
def test_terminal_conditions_close_without_model(tmp_path, monkeypatch, status, remaining, expected):
    agent, case, sid, threads, calls = make_agent(tmp_path, monkeypatch)
    threads[sid][0]["status"] = status
    case["round_limit"] = remaining
    decision = agent.decide(case, threads)
    assert decision["message"]["action"]["type"] == "accept"
    assert not calls
    assert agent.decisions[0]["close_reason"] == expected


def test_model_failure_sends_neutral_planned_packages(tmp_path, monkeypatch):
    agent, case, sid, threads, calls = make_agent(tmp_path, monkeypatch, answer=RuntimeError("offline failure"))
    decision = agent.decide(case, threads)
    record = agent.decisions[0]
    assert len(calls) == 1 and record["fallback"]
    assert record["fallback_action"] == "neutral_planned_packages"
    assert decision["message"].get("action") is None
    assert decision["message"]["term_sheets"] == [
        {"terms": row["terms"]} for row in record["plan"]["packages"]]


def test_batch_ceiling_closes_instead_of_continuing_session(tmp_path, monkeypatch):
    agent, case, sid, threads, calls = make_agent(
        tmp_path, monkeypatch, answer=ValueError("Batch budget exhausted before request"))
    decision = agent.decide(case, threads)
    assert len(calls) == 1
    assert decision["message"].get("action")
    assert "Batch budget exhausted" in agent.decisions[0]["reason"]


def test_uncompletable_primary_offer_closes_safely(tmp_path, monkeypatch):
    agent, case, sid, threads, calls = make_agent(tmp_path, monkeypatch)
    threads[sid][0]["term_sheets"][0]["terms"].pop("unit_price")
    decision = agent.decide(case, threads)
    assert decision["message"]["action"]["type"] == "walk_away"
    assert agent.decisions[0]["fallback_action"] == "safe_close"
    assert not calls


def test_final_offer_echoes_cheapest_nonprimary_sheet_when_round_remains(tmp_path, monkeypatch):
    agent, case, sid, threads, calls = make_agent(tmp_path, monkeypatch)
    threads[sid][0]["status"] = "final_offer"
    threads[sid][0]["term_sheets"] = [
        {"term_sheet_id": "offer:short", "terms": {
            "unit_price": 369.15, "payment_days": 14, "index_clause": None}},
        {"term_sheet_id": "offer:long", "terms": {
            "unit_price": 370.27, "payment_days": 45, "index_clause": None}},
    ]
    decision = agent.decide(case, threads)
    assert decision["message"]["term_sheets"] == [{"terms": {
        "unit_price": 370.27, "payment_days": 45, "index_clause": None}}]
    assert "action" not in decision["message"]
    assert not calls


@pytest.mark.parametrize("case_id,status,sheets", [
    ("case:P02", "final_offer", [
        {"term_sheet_id": "offer:70510-4", "terms": {
            "unit_price": 371.93, "payment_days": 90, "index_clause": None}},
        {"term_sheet_id": "offer:70510-4-a", "terms": {
            "unit_price": 368.85, "payment_days": 45, "index_clause": None}}]),
    ("case:P18", "final_offer", [
        {"term_sheet_id": "offer:70740-2", "terms": {
            "unit_price": 5.6, "payment_days": 90,
            "index_clause": {"series": "AS-14404", "material_share": 0.45,
                             "deadband_pct": 5.0, "base_month": "2026-08"}, "contract_months": 36}},
        {"term_sheet_id": "offer:70740-2-a", "terms": {
            "unit_price": 5.5, "payment_days": 30,
            "index_clause": {"series": "AS-14404", "material_share": 0.45,
                             "deadband_pct": 5.0, "base_month": "2026-08"}, "contract_months": 36}}]),
    ("case:P18", "open", [
        {"term_sheet_id": "offer:70740-1", "terms": {
            "unit_price": 5.6, "payment_days": 60,
            "index_clause": {"series": "AS-14404", "material_share": 0.45,
                             "deadband_pct": 0.0, "base_month": "2026-08"}, "contract_months": 36}},
        {"term_sheet_id": "offer:70740-1-a", "terms": {
            "unit_price": 5.6, "payment_days": 30,
            "index_clause": {"series": "AS-14404", "material_share": 0.45,
                             "deadband_pct": 5.0, "base_month": "2026-08"}, "contract_months": 24}}]),
])
@pytest.mark.parametrize("policy", ["current", "packages"])
def test_a2_nonstanding_alternatives_are_echoed_then_primary_accepted(
        tmp_path, monkeypatch, case_id, status, sheets, policy):
    # Minimal structured offers from the saved P02/P18 HTTP 422 conversations.
    answer = {"supplier_id": FIXTURES[case_id]["case"]["suppliers"][0], "action": "accept"}
    agent, case, sid, threads, calls = make_agent(
        tmp_path, monkeypatch, answer=answer, policy=policy, case_id=case_id)
    threads[sid][0].update(status=status, term_sheets=deepcopy(sheets))
    offers = agent.current_offers(case, threads)
    assert offers[0]["term_sheet_id"].endswith("-a") and not offers[0]["is_primary"]
    # An open packages turn normally keeps negotiating; exercise its shared close path directly.
    decision = agent.safe_close(case, threads) if status == "open" and policy == "packages" else \
        agent.decide(case, threads)
    assert "action" not in decision["message"]
    assert decision["message"]["term_sheets"] == [{"terms": offers[0]["terms"]}]
    assert not calls if policy == "packages" else len(calls) == 1
    threads[sid].append({"from": "buyer", "term_sheets": decision["message"]["term_sheets"]})
    threads[sid].append({"from": "sales", "status": "agreed", "term_sheets": [{
        "term_sheet_id": "offer:echo-primary", "terms": offers[0]["terms"]}]})
    followup = agent.decide(case, threads)
    assert followup["message"]["action"] == {
        "type": "accept", "term_sheet_id": "offer:echo-primary"}
    assert agent.decisions[-1]["close_reason"] == "alternative_echo_reply"
    assert len(calls) == (1 if policy == "current" else 0)


@pytest.mark.parametrize("case_id,sheets", [
    ("case:P02", [
        {"term_sheet_id": "offer:70510-4", "terms": {
            "unit_price": 371.93, "payment_days": 90, "index_clause": None}},
        {"term_sheet_id": "offer:70510-4-a", "terms": {
            "unit_price": 368.85, "payment_days": 45, "index_clause": None}}]),
    ("case:P18", [
        {"term_sheet_id": "offer:70740-2", "terms": {
            "unit_price": 5.6, "payment_days": 90,
            "index_clause": {"series": "AS-14404", "material_share": 0.45,
                             "deadband_pct": 5.0, "base_month": "2026-08"}, "contract_months": 36}},
        {"term_sheet_id": "offer:70740-2-a", "terms": {
            "unit_price": 5.5, "payment_days": 30,
            "index_clause": {"series": "AS-14404", "material_share": 0.45,
                             "deadband_pct": 5.0, "base_month": "2026-08"}, "contract_months": 36}}]),
])
def test_a2_no_round_accepts_only_primary_when_it_beats_fallback(tmp_path, monkeypatch, case_id, sheets):
    agent, case, sid, threads, _ = make_agent(tmp_path, monkeypatch, case_id=case_id)
    threads[sid][0]["term_sheets"] = sheets
    case["round_limit"] = 0
    decision = agent.safe_close(case, threads)
    assert decision["message"]["action"] == {
        "type": "accept", "term_sheet_id": sheets[0]["term_sheet_id"]}
    assert not agent.pending_alternative


def test_approval_intent_requires_documented_threshold(tmp_path, monkeypatch):
    agent, case, sid, threads, _ = make_agent(
        tmp_path, monkeypatch, case_id="case:P08", answer={
            "tone": "polite", "intent": "approval", "claim_ids": []})
    assert "approval_threshold_pct" not in agent.profiles[sid]
    decision = agent.decide(case, threads)
    assert "person responsible for approving" not in decision["message"]["body"]
    assert agent.decisions[0]["approval_hint"] is False


def test_empty_late_plan_closes_without_model_fallback(tmp_path, monkeypatch):
    agent, case, sid, threads, calls = make_agent(tmp_path, monkeypatch, case_id="case:P11")
    threads[sid][0]["term_sheets"][0]["terms"] = {
        "unit_price": 45.5, "ppm_commitment": 300, "chargeback_eur_per_complaint": 0}
    monkeypatch.setattr("nighthunter.live.plan_packages", lambda *a, **k: {
        "recommend_accept": False, "packages": [], "target_cost": 712002.0})
    decision = agent.decide(case, threads)
    assert decision["message"]["action"]["type"] == "accept"
    assert agent.decisions[0]["close_reason"] == "planner_exhausted"
    assert not agent.decisions[0]["fallback"] and not calls


def test_current_policy_keeps_model_selected_terms(tmp_path, monkeypatch):
    answer = {"supplier_id": "sup:70510", "action": "send", "tone": "polite",
              "intent": "counteroffer", "claim_ids": [],
              "term_sheets": [{"unit_price": 365.0, "payment_days": 60, "index_clause": None}]}
    agent, case, sid, threads, calls = make_agent(tmp_path, monkeypatch, answer=answer, policy="current")
    decision = agent.decide(case, threads)
    assert not agent.decisions[0]["fallback"]
    assert len(calls) == 1
    assert decision["message"]["term_sheets"][0]["terms"] == answer["term_sheets"][0]
    assert not agent.profiles


@pytest.mark.parametrize("case_id,field,opening,required,op", [
    ("case:P10", "volume_per_year", 19890, 22230, ">="),
    ("case:P11", "ppm_commitment", 6400, 1500, "<="),
])
def test_noncompliant_opening_can_be_countered_but_not_accepted(
        tmp_path, monkeypatch, case_id, field, opening, required, op):
    # Portable P10/P11-shaped regression: the actual hosted definitions are dry-checked
    # separately before the batch; no outside-repository replay is needed in the test suite.
    def configure(case, offer):
        case["case_id"] = case_id
        case["negotiable"].append(field)
        case["term_options"][field] = [opening, required]
        case["buyer"]["must_haves"] = [{"field": field, "op": op, "value": required}]
        offer["terms"][field] = opening
        if case_id == "case:P10":
            case["type"] = "capacity"
            case["buyer"].update(need_per_year=23400, horizon_years=2,
                                 fallback_unit_price=37.36, category_goal="secure_supply")
            case["term_options"][field] = [opening, 23400]
            offer["terms"]["unit_price"] = 32.2

    agent, case, sid, threads, calls = make_agent(tmp_path, monkeypatch, configure=configure)
    assert not must_haves_ok(case, threads[sid][0]["term_sheets"][0]["terms"])
    assert not agent.current_offers(case, threads)
    decision = agent.decide(case, threads)
    assert len(calls) == 1
    assert decision["message"].get("action") is None
    assert decision["message"]["term_sheets"]
    assert all(must_haves_ok(case, s["terms"]) for s in decision["message"]["term_sheets"])
    assert agent.safe_close(case, threads)["message"]["action"]["type"] == "walk_away"
