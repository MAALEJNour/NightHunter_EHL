"""RFQ runner: one concurrent worker per supplier thread, shared offers, exactly one close.

    python scripts/rfq_live.py --local --case case:S02          # local scripted simulator, no model
    python scripts/rfq_live.py --case case:D02 --model          # hosted sandbox (no practice quota)

Every thread has its own 60 s clock from the supplier's reply, so each worker answers its supplier
as soon as that reply arrives. Packages come from nighthunter.rfq.plan_rfq (held to the market and
never beyond the best acceptable rival); a lower rival price may be cited once per bidder; framing
text is model-written only with --model and always passes nighthunter.prose filters. Only the
latest PRIMARY sheet is ever accepted, by rfq.close_decision, under one case-level lock.
"""

import argparse
import json
import socket
import threading
import time
from datetime import UTC, datetime

from arena_kit import ArenaClient
from arena_kit.agents.llm import parse
from arena_kit.client import ArenaError
from arena_kit.data import DataPackage
from arena_kit.docs import standard_terms
from arena_kit.play import fetch_documents

from nighthunter.context import DEFAULT_DATA, ROOT, CaseContextBuilder, encoded
from nighthunter.live import LiveAgent
from nighthunter.prose import compose
from nighthunter.rfq import close_decision, live, plan_rfq, rank_bidders, rival_claims
from nighthunter.supplier_profile import build_profile

ENDED = {"walked_away", "no_bid"}
REQUEST = "Which of these options works best for you, or which single element would you adjust?"
CASE_TIME_LIMIT_S = 420  # practice has no wave cap; keep RFQs well inside a final wave anyway


class RfqNegotiator:
    def __init__(self, client, case_id, folder, model=None, dossier=None, deadline=None, opened=None):
        # deadline: absolute time.time() to stop negotiating (final wave cap minus a closing margin);
        # opened: (session_id, case, threads) when the session was already opened or resumed.
        self.deadline, self.opened = deadline, opened
        self.client, self.case_id, self.folder, self.model = client, case_id, folder, model
        self.lock, self.close_lock, self.model_lock = threading.Lock(), threading.Lock(), threading.Lock()
        self.closed, self.result, self.log, self.cited = False, None, [], {}
        self.dossier = dossier

    def record(self, who, sid, message):
        with self.lock:
            self.log.append({"who": who, "supplier_id": sid, "at": time.monotonic() - self.t0,
                             "message": message})
            (self.folder / "conversation.json").write_text(json.dumps(self.log, indent=2, default=str))

    def open(self):
        self.t0 = time.monotonic()
        if self.deadline is None:
            self.deadline = time.time() + CASE_TIME_LIMIT_S
        if self.opened:
            self.session_id, self.case, self.threads = self.opened
        else:
            opened = self.client.open_session(self.case_id)
            self.session_id, self.case, self.threads = opened["session_id"], opened["case"], opened["threads"]
        (self.folder / "session.json").write_text(json.dumps({"session_id": self.session_id,
                                                              "case_id": self.case_id}))
        for sid, events in self.threads.items():
            for m in events:
                fetch_documents(self, m)
                self.record("Supplier", sid, m)
        self.standards = {sid: standard_terms(ev) for sid, ev in self.threads.items()}
        self.dossier = self.dossier or {"evidence": []}
        self.profiles = {sid: build_profile(self.case, self.dossier, sid) for sid in self.case["suppliers"]}
        self.ranking = rank_bidders(self.case, self.dossier, self.profiles)
        (self.folder / "ranking.json").write_text(json.dumps(self.ranking, indent=2))

    def attachment(self, attachment_id):  # used by fetch_documents
        return self.client.attachment(self.session_id, attachment_id)

    def moves_left(self, sid):
        return self.case.get("round_limit", 10) - sum(m.get("from") == "buyer" for m in self.threads[sid])

    def framing(self, sid, plan, rival):
        if not self.model:
            return {}
        state = {"supplier_id": sid, "latest_supplier_email": (self.threads[sid][-1].get("body") or "")[-1500:],
                 "our_options": [p["terms"] for p in plan["packages"]], "rival_price_cited": bool(rival),
                 "bidder_read": next((r for r in self.ranking if r["supplier_id"] == sid), None),
                 "messages_left": self.moves_left(sid)}
        system = (ROOT / "prompts/expert_prose.md").read_text() + (
            "\nRFQ: several suppliers bid in parallel. Code may add one checked sentence with a lower rival"
            " price; do not mention rivals yourself. Return JSON with opening, rationale, closing only.")
        with self.model_lock:
            try:
                return parse(self.model.complete(system, encoded(state),
                                                 max_output=700 if self.model.reasoning_effort == "low" else 4096)) or {}
            except Exception as exc:  # framing is optional; the planned options still go out
                return {"error": str(exc)}

    def decide_close(self, final=False):
        with self.lock:
            plans = plan_rfq(self.case, self.threads, self.standards, self.profiles)
            moves = {s: (0 if final or self.threads[s][-1].get("status") in {"agreed", "final_offer"}
                         else self.moves_left(s)) for s in self.threads}
            return close_decision(self.case, self.threads, self.standards, plans, moves), plans

    def send(self, sid, message):
        """The arena runs one call per session at a time: 409 "busy ... retry" -> wait and resend (P05,
        11 Oct: a busy 409 stopped a bidder's worker, its clock ran out and it walked away)."""
        while True:
            try:
                return self.client.send_message(self.session_id, sid, message)
            except ArenaError as exc:
                if exc.status == 409 and "busy" in str(exc.detail).lower() and time.time() < self.deadline + 60:
                    time.sleep(1.0)
                    continue
                raise

    def refresh(self, sid):
        """Re-read one bidder's thread from the arena (after a timeout the arena has moved it on)."""
        try:
            thread = self.client.thread(self.session_id, sid)
        except ArenaError:
            return
        messages = thread.get("messages") or []
        with self.lock:
            if len(messages) >= len(self.threads[sid]):
                self.threads[sid] = messages
        self.record("Arena (refreshed)", sid, {"status": thread.get("status"), "offer_id": thread.get("offer_id")})

    def close(self, decision):
        with self.close_lock:
            if self.closed:
                return
            # Accept only what is standing NOW: re-read every live thread and decide again (P05, 11 Oct:
            # a stale offer ID was accepted after the bidder had moved on -> HTTP 422 -> no deal).
            if (decision["message"].get("action") or {}).get("type") == "accept":
                for sid in list(live(self.threads)):
                    self.refresh(sid)
                fresh, _ = self.decide_close(final=True)
                decision = fresh or decision
            for attempt in (1, 2):
                self.record("Buyer (submitted)", decision["supplier_id"], decision["message"])
                try:
                    reply = self.send(decision["supplier_id"], decision["message"])
                    break
                except ArenaError as exc:
                    self.record("Arena", decision["supplier_id"], {"error": exc.status, "detail": str(exc.detail)})
                    if attempt == 2 or exc.status not in (409, 422):
                        raise
                    for sid in list(live(self.threads)):
                        self.refresh(sid)
                    decision, _ = self.decide_close(final=True)
                    if not decision:
                        raise
            self.closed = True
            self.result = reply.get("result", reply)
            self.record("Result", decision["supplier_id"], self.result)

    def worker(self, sid):
        while not self.closed and time.time() < self.deadline:
            if self.threads[sid][-1].get("status") in {"agreed", "final_offer"}:
                # Act inside this bidder's 60 s: close now if its offer is the best acceptable one.
                decision, _ = self.decide_close()
                if decision and (decision["message"].get("action") or {}).get("type") == "accept":
                    return self.close(decision)
                return
            if self.threads[sid][-1].get("status") in ENDED or self.moves_left(sid) <= 1:
                return
            decision, plans = self.decide_close()
            if decision:
                return self.close(decision)
            plan = plans.get(sid) or {}
            if not plan.get("packages"):
                return
            with self.lock:
                claims = [c for c in rival_claims(self.case, self.threads, self.standards, sid)
                          if c["ref"] not in self.cited.setdefault(sid, set())]
            rival = claims[0] if claims else None
            choice = self.framing(sid, plan, rival)
            terms = [p["terms"] for p in plan["packages"]]
            # Bidders ask "how many pieces?" (P05: 83 times in 15 of 24 sessions; even the 92.4 run never
            # answered). State the binding RFQ volume in the first message and whenever asked.
            first = not any(e.get("from") == "buyer" for e in self.threads[sid])
            volume = LiveAgent.volume_answer(self.case, self.threads[sid], terms, proactive=first)
            volume += LiveAgent.fixed_term_answer(self.case, self.threads[sid])
            body, diag = compose(self.case, self.threads[sid], terms,
                                 volume + ([rival["sentence"]] if rival else []),
                                 choice, REQUEST, near_limit=self.moves_left(sid) <= 7)
            message = {"subject": f"Re: {self.case['title']}", "body": body,
                       "refs": [rival["ref"]] if rival else [], "term_sheets": [{"terms": t} for t in terms]}
            if self.closed:
                return
            self.record("Buyer (submitted)", sid, {**message, "diagnostics": diag})
            try:
                reply = self.send(sid, message)
            except ArenaError as exc:
                if exc.status != 409:
                    raise
                # Late (timeout) or ended: the arena has the thread's real state - re-read and go on.
                self.record("Arena", sid, {"error": exc.status, "detail": str(exc.detail)})
                self.refresh(sid)
                continue
            fetch_documents(self, reply)
            with self.lock:
                if rival:
                    self.cited[sid].add(rival["ref"])
                self.threads[sid] += [{**message, "from": "buyer"}, reply]
            self.record("Supplier", sid, reply)

    def run(self):
        self.open()
        workers = [threading.Thread(target=self.worker, args=(sid,), daemon=True) for sid in live(self.threads)]
        for w in workers:
            w.start()
        for w in workers:
            w.join(timeout=max(1.0, self.deadline - time.time()) + 75)
        if not self.closed:
            decision, _ = self.decide_close(final=True)
            if decision:
                self.close(decision)
        state = self.client.session(self.session_id)
        result = self.result if isinstance(self.result, dict) and "score" in self.result else state.get("result")
        summary = {"case_id": self.case_id, "session_id": self.session_id, "result": result,
                   "end_reason": state.get("end_reason"), "elapsed_s": round(time.monotonic() - self.t0, 1),
                   "buyer_messages": {s: 10 - self.moves_left(s) for s in self.threads},
                   "replay_url": state.get("replay_url")}
        (self.folder / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
        return summary


def local_client():
    import uvicorn
    from arena_kit.sim import Sim, create_app, load_cases
    package = DataPackage(DEFAULT_DATA)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    url = f"http://127.0.0.1:{sock.getsockname()[1]}"
    server = uvicorn.Server(uvicorn.Config(create_app(Sim(load_cases(), facts=package.facts)),
                                           log_level="warning", lifespan="off"))
    threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True).start()
    while not server.started:
        time.sleep(0.02)
    key = ArenaClient(url, api_key="local-registration").register("NightHunter local RFQ", "sim")["api_key"]
    return ArenaClient(url, api_key=key)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--local", action="store_true", help="Local scripted simulator; no .env, no model")
    parser.add_argument("--model", action="store_true", help="Model-written framing (budget-ledgered)")
    parser.add_argument("--set", default="practice")
    parser.add_argument("--reasoning-effort", choices=["low", "medium", "high"], default="low")
    parser.add_argument("--llm-model", help="Overrides LLM_MODEL (must be priced in nighthunter.live.PRICES)")
    args = parser.parse_args()
    folder = ROOT / "artifacts/rfq" / f"{args.case.split(':')[-1]}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    folder.mkdir(parents=True)
    model = None
    if args.local:
        if args.model:
            raise SystemExit("--local never uses the model")
        client = local_client()
        dossier = None
    else:
        from arena_kit.cli import load_env

        from nighthunter.live import BudgetedModel
        load_env(ROOT / ".env")
        client = ArenaClient()
        case = next(c for c in client.cases(args.set) if c["case_id"] == args.case)
        dossier = CaseContextBuilder().build(case, 40000)
        (folder / "dossier.json").write_text(encoded(dossier))
        if args.model:
            model = BudgetedModel(ROOT / "artifacts/llm-budget.json", model=args.llm_model)
            model.max_calls = 36  # three bidders x up to ten messages + preflight
            model.reasoning_effort = args.reasoning_effort
    try:
        print(json.dumps(RfqNegotiator(client, args.case, folder, model, dossier).run(), indent=2, default=str))
    finally:
        if model:
            model.close()
        client.http.close()


if __name__ == "__main__":
    main()
