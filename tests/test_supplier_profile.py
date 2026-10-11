import json

from nighthunter.context import ROOT
from nighthunter.supplier_profile import build_profile

FIXTURES = json.loads((ROOT / "tests/fixtures/hosted_practice_cases.json").read_text())


def profile(case_id, evidence=None):
    fx = FIXTURES[case_id]
    return build_profile(fx["case"], {"evidence": fx["evidence"] if evidence is None else evidence},
                         fx["case"]["suppliers"][0])


def tactics(p):
    return {t["tactic"] for t in p["tactics"]}


def test_p01_mid_year_change_cash_and_stale_costing():
    p = profile("case:P01")
    assert p["trigger_check"]["mid_year_effective_date"]
    assert p["trigger_check"]["notice_compliant"]  # compliant notice is not a breach
    assert p["cash_pressure"] and p["stale_costing"]
    assert {"defer_effective_date", "price_early_payment", "request_cost_breakdown"} <= tactics(p)


def test_p02_approval_threshold_and_longer_payment():
    p = profile("case:P02")
    assert p["approval_threshold_pct"] == 2.0
    assert not p.get("cash_pressure")
    assert not p["trigger_check"]["mid_year_effective_date"]
    assert {"request_approval", "ask_longer_payment"} <= tactics(p)


def test_p03_freeze_and_open_terms():
    p = profile("case:P03")
    assert p["price_freeze"]
    assert "payment_days" in p["open_fields"]
    assert "trade_non_price_terms" in tactics(p)


def test_signals_carry_sources_and_history_is_summarised():
    p = profile("case:P01")
    assert all(s["ref"] for s in p["signals"])
    assert p["history"]["settled_below_ask_every_time"]


def test_other_suppliers_documents_are_ignored():
    # Simulate an RFQ dossier: P01's cash e-mail must not mark P02's supplier as cash-pressed.
    mixed = FIXTURES["case:P02"]["evidence"] + [
        e for e in FIXTURES["case:P01"]["evidence"] if e.get("table") == "documents"]
    assert not profile("case:P02", mixed).get("cash_pressure")


def test_empty_dossier_is_neutral():
    p = profile("case:P02", evidence=[])
    assert p["signals"] == [] and "approval_threshold_pct" not in p
    assert tactics(p) <= {"ask_longer_payment"}


def test_sunday_release_signals():
    # Release letters/news (2026-10-11): group price lists freeze price; cash and insolvency signal pressure.
    from nighthunter.supplier_profile import build_profile
    case = {"case_id": "case:X", "negotiable": ["unit_price", "payment_days"], "parts": ["part:1"],
            "suppliers": ["sup:70510"], "buyer": {"category_goal": "stabilise"}}
    letter = {"table": "documents", "source": "documents:doc:20261001-70510-S5",
              "row": {"id": "doc:20261001-70510-S5", "supplier_id": "sup:70510"},
              "document": "our price list 2027 applies to all customers without exception; our board has ruled out "
                          "individual price reductions for the coming year. We remain open to discuss payment terms."}
    p = build_profile(case, {"evidence": [letter]}, "sup:70510")
    assert p["price_freeze"] and p["open_fields"] == ["payment_days"]
    cash = {**letter, "row": {"id": "doc:x", "supplier_id": "sup:70510"},
            "document": "Our bank is watching our figures every month; please pay our invoices within 10 days."}
    assert build_profile(case, {"evidence": [cash]}, "sup:70510").get("cash_pressure")
    news = {"table": "news", "source": "news:news:20261006-S1",
            "row": {"id": "news:20261006-S1", "supplier_id": "sup:70510", "topic": "insolvency",
                    "headline": "files for insolvency", "body": "a provisional administrator keeps production running"}}
    p = build_profile(case, {"evidence": [news]}, "sup:70510")
    assert p["cash_pressure"] and p["supply_risk"]


def test_release_rows_only_in_non_practice_dossiers():
    import json

    from nighthunter.context import DEFAULT_RELEASE, CaseContextBuilder
    if not (DEFAULT_RELEASE / "facts.json").is_file():
        return
    fx = json.load(open("tests/fixtures/hosted_practice_cases.json"))["case:P11"]["case"]
    builder = CaseContextBuilder()
    origins = lambda s: {e.get("origin") for e in builder.build({**fx, "set": s}, 40000)["evidence"]}  # noqa: E731
    assert "release" not in origins("practice") and "release" in origins("hidden")
