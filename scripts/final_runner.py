"""Live Final runner: play every case of each wave in parallel within the wave's cap.

    python scripts/final_runner.py --final                                  # the Live Final (5 waves)
    python scripts/final_runner.py --rehearse case:D01 case:D02 --set sandbox --cap 480   # rehearsal
    python scripts/final_runner.py --rehearse case:S01 case:S02 case:S03 --local --cap 480

Single-supplier cases: the kit's `play` loop (deadline-aware closing) with our LiveAgent
(--policy packages, --adaptation expert_prose). RFQ cases (2-3 suppliers): our concurrent
RfqNegotiator (one worker per bidder, one close). One shared, thread-safe budgeted model: budget is
reserved under a lock, API calls run in parallel. The runner reads only /v1/cases, sessions and
threads - never the event feed, screen or leaderboard (brief rule 1). Sessions are resumed, never
reopened (a 409 names the running session).
"""

import argparse
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from arena_kit import ArenaClient
from arena_kit.client import ArenaError
from arena_kit.data import DataPackage
from arena_kit.play import play

from nighthunter.context import DEFAULT_DATA, ROOT, CaseContextBuilder, encoded
from nighthunter.live import BudgetedModel, LiveAgent, RecordingTable

CLOSE_MARGIN_S = 120  # RFQ: stop negotiating this long before the cap. FAQ (11 Oct): replies can take more than a
                      # minute under the final's load and a reply after the cap is lost; our cases need 60-230 s of 480.
SINGLE_EXTRA_S = 30   # single-supplier: the kit closes at cap - max(90 s, slowest round + 15 s); give it 30 s more
MAX_PARALLEL = 10     # arena limit: at most 10 open sessions per key
FINAL_RUN_LIMIT_USD = 2.0  # keep a hard per-launch ceiling inside the cumulative ledger cap
FINAL_TOTAL_LIMIT_USD = 15.0  # owner-approved final-only cumulative cap (11 Oct); practice stays at $7


class SharedModel(BudgetedModel):
    """BudgetedModel for many concurrent cases: reservations under a lock, HTTP calls in parallel."""

    def __init__(self, ledger, model=None, limit_usd=2.0):
        super().__init__(ledger, model=model, total_limit_usd=FINAL_TOTAL_LIMIT_USD)
        self.run_limit, self.max_calls, self.mutex = limit_usd, 2000, threading.Lock()

    def complete(self, system, user, max_output=None):
        import os
        max_output = max_output or self.max_output
        size = len((system + user).encode("utf-8"))
        if size > 110000:
            raise ValueError("Input exceeded 110k-byte live-context limit")
        reserve = ((size + 512) * self.price_in * 1.25 + max_output * self.price_out) / 1_000_000
        with self.mutex:
            spent = sum(r["accounted_usd"] for r in self.records)
            run_spent = sum(r["accounted_usd"] for r in self.records[self.start:])
            if spent + reserve > self.total_limit or run_spent + reserve > self.run_limit:
                raise ValueError("Budget exhausted before request")
            record = {"model": self.name, "state": "reserved", "accounted_usd": reserve, "input_bytes": size,
                      "max_output_tokens": max_output, "at": datetime.now(UTC).isoformat(), "runner": "final"}
            self.records.append(record)
            self.save()
        started = time.monotonic()
        try:
            response = self.http.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {os.environ['LLM_API_KEY']}"},
                json={"model": self.name, "reasoning_effort": self.reasoning_effort,
                      "max_completion_tokens": max_output, "response_format": {"type": "json_object"},
                      "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
            if response.status_code >= 400:
                record["http_status"] = response.status_code
                raise RuntimeError(f"Model HTTP {response.status_code}")
            result = response.json()
            usage = result.get("usage")
            with self.mutex:
                if usage and "prompt_tokens" in usage and "completion_tokens" in usage:
                    record["usage"] = usage
                    record["accounted_usd"] = (usage["prompt_tokens"] * self.price_in * 1.25
                                               + usage["completion_tokens"] * self.price_out) / 1_000_000
                record["state"] = "completed" if usage else "completed_usage_unknown"
            content = result["choices"][0]["message"]["content"]
            if not content:
                raise ValueError("Empty model response")
            return content
        except Exception:
            if record["state"] == "reserved":
                record["state"] = "failed_reservation_retained"
            raise
        finally:
            with self.mutex:
                record["seconds"] = round(time.monotonic() - started, 3)
                self.save()


class PatientTable(RecordingTable):
    """Opening a session retries on HTTP 429 "at most 10 open sessions" (practice round 2, 11 Oct: P07
    failed at once while the previous round's P05 was still open) until shortly before the cap."""

    cap = None

    def open(self, case_id):
        while True:
            try:
                return super().open(case_id)
            except ArenaError as e:
                if e.status != 429 or (self.cap and time.time() > self.cap - CLOSE_MARGIN_S - 60):
                    raise
                print(f"{case_id}: arena busy ({e.detail}); retrying in 5 s", flush=True)
                time.sleep(5)


class Runner:
    offline_model = None

    def __init__(self, client, model, out, local=False):
        self.client, self.model, self.out, self.local = client, model, out, local
        self.package = DataPackage(DEFAULT_DATA)
        self.results, self.lock = {}, threading.Lock()

    def play_case(self, case, cap):
        """One case to its end; cap = absolute time.time() of the wave's cap (or rehearsal cap)."""
        cid = case["case_id"]
        folder = self.out / cid.replace(":", "_")
        folder.mkdir(parents=True, exist_ok=True)
        started = time.time()
        try:
            dossier = {"case": case, "evidence": []} if self.local else CaseContextBuilder().build(case, 40000)
            (folder / "dossier.json").write_text(encoded(dossier))
            if len(case["suppliers"]) > 1:
                from rfq_live import RfqNegotiator
                table = PatientTable(self.client, folder)
                table.case, table.cap = case, cap  # case enables resume of a running final session (409)
                opened_case, threads = table.open(cid)
                negotiator = RfqNegotiator(self.client, cid, folder, self.model, dossier,
                                           deadline=cap - CLOSE_MARGIN_S,
                                           opened=(table.session_id, opened_case or case, threads))
                summary = negotiator.run()
                result = summary.get("result") or {}
            else:
                agent = LiveAgent(self.model or self.offline_model, self.package, dossier, "adaptive", folder,
                                  policy="packages", adaptation="expert_prose")
                table = PatientTable(self.client, folder)
                table.case, table.cap = case, cap
                result = play(table, cid, agent, lambda: cap - SINGLE_EXTRA_S)
        except Exception as exc:  # one broken case must not stop the others
            result = {"error": f"{type(exc).__name__}: {exc}"}
        result = result if isinstance(result, dict) else {"result": str(result)}
        result["elapsed_s"] = round(time.time() - started, 1)
        (folder / "result.json").write_text(json.dumps(result, indent=2, default=str))
        with self.lock:
            self.results[cid] = result
        print(f"{cid}: score={result.get('score')} deal={result.get('deal')} "
              f"elapsed={result['elapsed_s']}s {result.get('error', '')}", flush=True)
        return result

    def rehearse(self, case_ids, set_name, cap_s):
        cases = {c["case_id"]: c for c in self.client.cases(set_name)}
        cap = time.time() + cap_s
        with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as pool:
            list(pool.map(lambda cid: self.play_case(cases[cid], cap), case_ids))
        return self.results

    def final(self, waves=5, poll=5.0):
        started, closed, caps = {}, set(), {}
        print("Final runner ready: polling final cases; a pre-wave 403 is expected.", flush=True)
        waiting_logged = False
        with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as pool:
            while len(closed) < waves or not all(f.done() for f in started.values()):
                try:
                    cases = self.client.cases("final")
                except ArenaError as e:
                    if e.status != 403:  # 403: no wave has started yet
                        raise
                    if not waiting_logged:
                        print("Final cases are not available yet (403); waiting for the next wave.", flush=True)
                    waiting_logged = True
                    cases = []
                if cases:
                    waiting_logged = False
                for case in cases:
                    if not case.get("open"):
                        closed.add(case.get("wave"))
                        continue
                    if case.get("seconds_left") is not None:
                        caps[case["wave"]] = time.time() + case["seconds_left"]
                    if case["case_id"] not in started and case.get("seconds_left"):
                        started[case["case_id"]] = pool.submit(self.play_case, case, caps[case["wave"]])
                time.sleep(poll)
        return self.results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--final", action="store_true")
    mode.add_argument("--rehearse", nargs="+", metavar="CASE")
    parser.add_argument("--set", default="practice")
    parser.add_argument("--cap", type=float, default=480, help="rehearsal cap in seconds (wave cap = 480)")
    parser.add_argument("--local", action="store_true", help="local arena-sim, no model, no .env")
    parser.add_argument("--llm-model", help="override LLM_MODEL (priced models only)")
    parser.add_argument("--limit-usd", type=float, default=FINAL_RUN_LIMIT_USD,
                        help=f"model spend cap for this launch (maximum {FINAL_RUN_LIMIT_USD:.2f} USD)")
    # Practice-only variant search (never used for --final: the final runs the proven defaults).
    parser.add_argument("--anchor-scale", type=float, default=1.0, help="practice only: scale the opening ask")
    parser.add_argument("--effort", choices=["low", "medium"], default="low", help="practice only: model effort")
    parser.add_argument("--flag", action="append", default=[],
                        help="practice only: turn on a module flag, e.g. packages.NEED_ALIGNED_LEAD")
    args = parser.parse_args()
    if not 0 < args.limit_usd <= FINAL_RUN_LIMIT_USD:
        raise SystemExit(f"--limit-usd must be > 0 and <= {FINAL_RUN_LIMIT_USD:.2f}")
    if args.final and (args.anchor_scale != 1.0 or args.effort != "low" or args.flag):
        raise SystemExit("variant flags are for practice rehearsals only")
    import importlib
    for name in args.flag:
        module, attr = name.rsplit(".", 1)
        mod = importlib.import_module(f"nighthunter.{module}")
        if not hasattr(mod, attr):
            raise SystemExit(f"unknown flag {name}")
        setattr(mod, attr, True)
        print(f"practice flag ON: {name}", flush=True)
    if args.anchor_scale != 1.0:
        import nighthunter.packages as planner
        planner.GOAL_MAX_CUT = {k: v * args.anchor_scale for k, v in planner.GOAL_MAX_CUT.items()}
    out = ROOT / "artifacts/final_runs" / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out.mkdir(parents=True)
    if args.local:
        from types import SimpleNamespace

        from rfq_live import local_client
        client = local_client()
        # No model locally: planner packages with template e-mails (RFQ framing is skipped when None).
        model = None
        Runner.offline_model = SimpleNamespace(complete=lambda *a, **k: "{}", reasoning_effort="low",
                                               name="offline")
        args.set = "practice"
    else:
        from arena_kit.cli import load_env
        load_env(ROOT / ".env")
        client = ArenaClient()
        model = SharedModel(ROOT / "artifacts/llm-budget.json", model=args.llm_model, limit_usd=args.limit_usd)
        model.reasoning_effort = args.effort
        model.max_output = 2048 if args.effort == "low" else 6144
    runner = Runner(client, model, out, local=args.local)
    try:
        results = runner.final() if args.final else runner.rehearse(args.rehearse, args.set, args.cap)
    finally:
        if model:
            model.close()
        client.http.close()
    scores = [r.get("score") or 0 for r in results.values()]
    summary = {"results": results, "mean_score": sum(scores) / len(scores) if scores else None,
               "model": model.name if model else None}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps({k: (v.get("score"), v.get("elapsed_s"), v.get("error")) for k, v in results.items()},
                     indent=2), flush=True)


if __name__ == "__main__":
    main()
