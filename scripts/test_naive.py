"""Run the upstream naive buyer against a temporary local arena (no .env or LLM)."""

import argparse
import json
import socket
import threading
import time
from pathlib import Path

import uvicorn
from arena_kit import ArenaClient, RemoteTable, play
from arena_kit.agents import NaiveAgent
from arena_kit.data import DataPackage
from arena_kit.sim import Sim, create_app, load_cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=["case:S01", "case:S02", "case:S03", "all"], default="case:S01")
    parser.add_argument("--out", type=Path, help="Optionally save local baseline metrics as JSON")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    package = DataPackage(root / "vendor/negotiation-arena-kit/data")
    state = Sim(load_cases(), facts=package.facts)
    # Bind before starting the server so another process cannot steal our port.
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    url = f"http://127.0.0.1:{sock.getsockname()[1]}"
    server = uvicorn.Server(uvicorn.Config(create_app(state), log_level="warning", lifespan="off"))
    worker = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    clients = []
    try:
        worker.start()
        deadline = time.monotonic() + 10
        while not server.started:
            if not worker.is_alive() or time.monotonic() >= deadline:
                raise RuntimeError("Local simulator failed to start within 10 seconds")
            time.sleep(0.02)
        # Explicit local credentials prevent use of any real key in the environment.
        registration = ArenaClient(url, api_key="local-registration")
        clients.append(registration)
        key = registration.register("NightHunter local baseline", "sim")["api_key"]
        client = ArenaClient(url, api_key=key)
        clients.append(client)
        case_ids = ["case:S01", "case:S02", "case:S03"] if args.case == "all" else [args.case]
        results = []
        for case_id in case_ids:
            table = RemoteTable(client)
            started = time.monotonic()
            result = play(table, case_id, NaiveAgent(anchor=0.10, close_gap=0.01))
            fields = ("ended", "deal", "must_haves_ok", "supplier_id", "terms", "c_open", "c_deal", "score")
            summary = {"case_id": case_id, "agent": "upstream_naive", "environment": "local_scripted_simulator",
                       "elapsed_seconds": round(time.monotonic() - started, 3), "llm_calls": 0,
                       **{k: result.get(k) for k in fields}}
            results.append(summary)
            print(json.dumps(summary, indent=2))
            if not result.get("ended"):
                raise RuntimeError(f"{case_id} did not finish")
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(results, indent=2) + "\n")
    finally:
        for client in clients:
            client.http.close()
        server.should_exit = True
        if worker.is_alive():
            worker.join(timeout=10)
        sock.close()
        if package.db:
            package.db.close()


if __name__ == "__main__":
    main()
