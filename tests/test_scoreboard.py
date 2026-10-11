from nighthunter.scoreboard import flags, report

CASE = {"case_id": "case:X", "title": "t", "type": "renewal", "negotiable": ["unit_price", "payment_days"],
        "buyer": {"category_goal": "leverage", "reference_payment_days": 60}}


def run(events, result):
    return {"source": "ours", "run": "r", "label": "x", "case": CASE, "result": result, "events": events}


def sup(price, status="open"):
    return {"actor": "supplier", "sid": "sup:1", "status": status, "offers": [{"unit_price": price}],
            "sheets": [], "action": None, "claims": []}


def buy(price):
    return {"actor": "buyer", "sid": "sup:1", "status": None, "offers": [],
            "sheets": [{"unit_price": price, "payment_days": 60}], "action": "send", "claims": []}


def test_flags_detect_known_mistakes():
    result = {"deal": True, "supplier_id": "sup:1", "score": 0.4, "terms": {"payment_days": 14},
              "cost_breakdown": {"payment_terms": 500.0}}
    events = [sup(10), buy(8), sup(9.5), buy(8), sup(9, "final_offer"), buy(8.5), sup(8.9)]
    got = flags(run(events, result))
    assert {"short_payment", "repeated_buyer_package", "countered_final_offer"} <= set(got)


def test_closed_while_supplier_moving_and_report():
    result = {"deal": True, "supplier_id": "sup:1", "score": 0.5, "terms": {}, "cost_breakdown": {}}
    r = run([sup(10), buy(8), sup(9.5), buy(8.2), sup(9)], result)
    assert "closed_while_supplier_moving" in flags(r)
    assert "case:X" in report([r])
