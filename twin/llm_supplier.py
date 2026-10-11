"""An LLM supplier twin that reads our e-mails, and a fidelity test against real hosted replies.

    python -m twin.llm_supplier --fidelity S10 S11      # predict real supplier turns, compare

The twin role-plays the hosted supplier from the public brief's description of how suppliers decide,
the supplier's own documents in the dossier, the thread so far, and an offline floor placed from the
practice C_best. Offline evaluation only: never imported by the live agent. It earns trust only if it
predicts real suppliers' next prices better than naive baselines on conversations it has not seen.
"""

import argparse
import glob
import json
import statistics

from arena_kit.cli import load_env

from nighthunter.context import ROOT, encoded
from nighthunter.live import BudgetedModel
from nighthunter.packages import complete, price_for_cost

RULES = """You are the sales person of a supplier negotiating by e-mail with a buyer (Hollerau Pumpenwerke).
How you decide (the arena's rules for suppliers):
- You never sell below your cost floor. Bigger moves need your boss's approval.
- Data the buyer cites has been checked (claim_results). True data can disarm you ("we did not know that -
  a fair point") or meet "that is not our reality" when something else weighs more for you now. A wrong
  figure costs trust. You give nothing without a move from the buyer.
- You read the whole e-mail: term sheets, data, questions, arguments, threats, appreciation, urgency. You
  react to tone and relationship as a person would; padding does not buy price. If the buyer ignores what
  you asked for, you hold firm.
- Typical behaviour of these suppliers (measured): the first reply concedes most of what you will ever
  give; afterwards you mirror the buyer's real moves with smaller steps; if the buyer answers your big
  first drop with a much smaller step you may even raise your price; around your 3rd-5th reply you
  issue a final_offer; if pushed after a final_offer you may walk away.
Reply ONLY with JSON: {"status": "open|final_offer|agreed|walked_away", "unit_price": <your standing price
for your main term sheet>, "reason": "<one sentence>"}"""


def floor_note(case, std, terms, c_best):
    comp = {k: v for k, v in complete(case, std, terms).items() if k != "unit_price"}
    price = price_for_cost(case, std, comp, c_best)
    return f"Your private floor for your current terms is about EUR {price:.2f} per unit." if price else ""


def supplier_view(dossier, sid):
    docs = [e.get("document", "")[:400] for e in dossier["evidence"]
            if e.get("table") == "documents" and (e.get("row") or {}).get("supplier_id") == sid]
    intel = [e.get("citable_fact") or e.get("row") for e in dossier["evidence"] if e.get("table") == "supplier_intel"]
    return {"your_documents": docs[:6], "your_company": intel[:1]}


def turns(batches):
    """(run folder, case, dossier, trace prefix up to a buyer message, actual next supplier move)."""
    for batch in batches:
        for state_path in sorted(glob.glob(str(ROOT / f"artifacts/strategies/{batch}_*/P*/*/state.json"))):
            folder = state_path.rsplit("/", 1)[0]
            dossier = json.load(open(folder + "/dossier.json"))
            result = json.load(open(state_path)).get("result") or {}
            trace = result.get("trace") or []
            for i, step in enumerate(trace):
                if step["actor"] != "buyer" and step["round"] >= 1 and i and trace[i - 1]["actor"] == "buyer" \
                        and trace[i - 1]["move"].get("type") == "message" and step["move"].get("terms"):
                    yield folder, dossier, trace[:i], step, result.get("c_best")


def history(trace):
    out = []
    for step in trace:
        mv = step["move"]
        if step["actor"] == "buyer":
            out.append({"from": "buyer", "body": (mv.get("body") or "")[:1800],
                        "term_sheets": [t.get("terms") for t in mv.get("term_sheets") or []]})
        else:
            out.append({"from": "you", "status": mv.get("status"), "terms": mv.get("terms"),
                        "alternatives": [a.get("terms") for a in mv.get("alternatives") or []],
                        "claim_results": mv.get("claim_results"), "reasons": step.get("reasons")})
    return out


def predict(model, dossier, trace, c_best):
    case = dossier["case"]
    sid = case["suppliers"][0]
    last = next(s["move"] for s in reversed(trace) if s["actor"] != "buyer")
    std = {**(last.get("terms") or {})}
    user = encoded({"case": {k: case[k] for k in ("title", "type", "negotiable", "fixed_terms") if k in case},
                    **supplier_view(dossier, sid), "private": floor_note(case, std, last["terms"], c_best),
                    "thread": history(trace)})
    raw = model.complete(RULES, user, max_output=700)
    return json.loads(raw[raw.find("{"):raw.rfind("}") + 1])


def fidelity(batches, limit):
    load_env(ROOT / ".env")
    model = BudgetedModel(ROOT / "artifacts/llm-budget.json")
    model.max_calls = limit + 5
    rows = []
    try:
        for n, (folder, dossier, trace, actual, c_best) in enumerate(turns(batches)):
            if n >= limit:
                break
            last = next(s["move"] for s in reversed(trace) if s["actor"] != "buyer")["terms"]["unit_price"]
            real = actual["move"]["terms"]["unit_price"]
            try:
                guess = predict(model, dossier, trace, c_best)
            except Exception as exc:  # malformed reply: count as no prediction
                print("skip", folder, exc)
                continue
            first = actual["round"] == 1
            naive = last * (1 - (0.0117 if first else 0.0035))  # median hosted move (280 traces)
            rows.append({"case": dossier["case"]["case_id"], "round": actual["round"], "last": last, "real": real,
                         "twin": guess.get("unit_price"), "naive": round(naive, 2),
                         "status_real": actual["move"]["status"], "status_twin": guess.get("status")})
            r = rows[-1]
            print(f"{r['case'][-3:]} r{r['round']} last {last} real {real} twin {r['twin']} naive {r['naive']} "
                  f"status {r['status_real']}/{r['status_twin']}", flush=True)
    finally:
        model.close()

    def err(key):
        return statistics.mean(abs(r[key] - r["real"]) / r["real"] * 100 for r in rows if isinstance(r[key], (int, float)))

    def direction(key):  # did it predict the sign of the move (down / flat / up)?
        sign = lambda x: (x > 1e-9) - (x < -1e-9)  # noqa: E731
        ok = [sign(r["last"] - r[key]) == sign(r["last"] - r["real"]) for r in rows if isinstance(r[key], (int, float))]
        return 100 * sum(ok) / len(ok)

    print(f"\n{len(rows)} real supplier turns")
    for key in ("twin", "naive"):
        print(f"  {key:6} mean abs error {err(key):.2f} %   direction right {direction(key):.0f} %")
    print(f"  status right (twin) {100 * sum(r['status_real'] == r['status_twin'] for r in rows) / len(rows):.0f} %")
    (ROOT / "artifacts/twin_fidelity.json").write_text(json.dumps(rows, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fidelity", nargs="+", required=True, help="batch names, e.g. S10 S11")
    parser.add_argument("--limit", type=int, default=60)
    args = parser.parse_args()
    fidelity(args.fidelity, args.limit)


if __name__ == "__main__":
    main()
