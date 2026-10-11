"""Run the approved nine-case practice batches sequentially with hard stop rules."""

import argparse
import glob
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from arena_kit.client import ArenaClient
from arena_kit.cost import must_haves_ok
from arena_kit.data import DataPackage
from arena_kit.docs import standard_terms
from arena_kit.cli import load_env

from nighthunter.compare import fingerprint
from nighthunter.context import DEFAULT_DATA, ROOT, CaseContextBuilder, encoded
from nighthunter.live import LiveAgent
from nighthunter.packages import plan_packages
from nighthunter.supplier_profile import build_profile
from nighthunter.validation import validate_sheets

CASES = ("P01", "P02", "P03", "P04", "P07", "P08", "P10", "P11", "P18")
BATCH_LIMITS = {"A": 0.75, "A2": 0.75, "A3": 0.60}
REFERENCE = Path.home() / "Downloads/saved-negotiation-conversations-2026-10-10/replays/practice-20261010T141311Z"


def ledger_records():
    path = ROOT / "artifacts/llm-budget.json"
    return json.loads(path.read_text()) if path.exists() else []


def batch_spend(start):
    return sum(row["accounted_usd"] for row in ledger_records()[start:])


def opening_for(reference, name, sid):
    paths = glob.glob(str(reference / f"case_{name}*__threads.json"))
    if len(paths) != 1:
        raise ValueError(f"Expected one saved opening for {name}, found {len(paths)}")
    messages = json.loads(Path(paths[0]).read_text())["thread_details"][sid]["messages"]
    return messages[:1]


def save_manifest(path, manifest):
    path.write_text(json.dumps(manifest, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, default=REFERENCE)
    parser.add_argument("--batch", choices=sorted(BATCH_LIMITS), default="A")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    batch_limit = BATCH_LIMITS[args.batch]
    runs_per_case = 3 if args.batch == "A3" else 2
    total_runs = runs_per_case * len(CASES)
    load_env(ROOT / ".env")
    client = ArenaClient()
    try:
        me = client.me()
        quota_start = me.get("practice", {}).get("left")
        if not isinstance(quota_start, int) or quota_start < total_runs:
            raise ValueError(f"Insufficient practice quota for {total_runs} sessions: {quota_start}")
        hosted = {case["case_id"]: case for case in client.cases("practice")}
    finally:
        client.http.close()

    reference = json.loads((args.reference / "case-definitions.json").read_text())
    code_hash = fingerprint()
    script_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    folder = args.out or ROOT / f"artifacts/batch_{args.batch.lower()}" / \
        datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    folder.mkdir(parents=True, exist_ok=False)
    frozen = {}
    package = DataPackage(DEFAULT_DATA)
    try:
        for name in CASES:
            cid = f"case:{name}"
            case = hosted[cid]
            if case != reference[cid] or len(case["suppliers"]) != 1:
                raise ValueError(f"Hosted {cid} changed or is not single-supplier; no session opened")
            dossier = CaseContextBuilder().build(case, 40000)
            sid = case["suppliers"][0]
            opening = opening_for(args.reference, name, sid)
            std = standard_terms(opening)
            profile = build_profile(case, dossier, sid)
            plan = plan_packages(case, std, opening, profile)
            terms = [row["terms"] for row in plan["packages"]]
            if not terms or validate_sheets(case, terms, std) != terms or not all(
                    must_haves_ok(case, term, std) for term in terms):
                raise ValueError(f"Round-0 plan failed for {cid}; no session opened")
            target = folder / name / "dossier.json"
            target.parent.mkdir()
            target.write_text(encoded(dossier))
            for policy in ("current", "packages"):
                LiveAgent(SimpleNamespace(complete=lambda *a: "{}"), package, dossier,
                          "adaptive", target.parent, policy=policy)
            frozen[cid] = {"path": str(target),
                           "sha256": hashlib.sha256(encoded(dossier).encode()).hexdigest(),
                           "opening_sheet_count": len(terms), "claim_cards_checked": True}
    finally:
        if package.db:
            package.db.close()

    start_index = len(ledger_records())
    manifest = {"name": f"Batch {args.batch} – all single-supplier practice cases", "status": "running",
                "model": "gpt-5.6-luna", "variant": "adaptive", "input_version": "current",
                "adaptation": "current", "model_settings": {"reasoning_effort": "low",
                                                         "max_completion_tokens": 2048},
                "pricing_checked": "2026-10-10; https://developers.openai.com/api/docs/models/gpt-5.6-luna",
                "price_usd_per_million": {"input": 0.20, "output": 1.20},
                "code_and_prompts_sha256": code_hash, "runner_sha256": script_hash, "dossiers": frozen,
                "ledger_start_index": start_index, "batch_limit_usd": batch_limit,
                "quota_start": quota_start, "runs": []}
    manifest_path = folder / "manifest.json"
    save_manifest(manifest_path, manifest)
    print(f"Batch {args.batch}: {folder}; quota available {quota_start}; ledger index {start_index}", flush=True)
    consecutive_bad = 0
    last_bad_kind = None
    for i, name in enumerate(CASES):
        cid = f"case:{name}"
        if args.batch == "A3":
            order = (("current", "current", 1), ("packages", "packages_1", 1),
                     ("packages", "packages_2", 2)) if i % 2 == 0 else (
                         ("packages", "packages_1", 1), ("current", "current", 1),
                         ("packages", "packages_2", 2))
        else:
            order = tuple((policy, policy, 1) for policy in (
                ("current", "packages") if i % 2 == 0 else ("packages", "current")))
        for policy, label, repeat in order:
            if fingerprint() != code_hash:
                manifest["status"] = "stopped_code_changed"
                break
            if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != script_hash:
                manifest["status"] = "stopped_runner_changed"
                break
            dossier_path = Path(frozen[cid]["path"])
            if hashlib.sha256(dossier_path.read_bytes()).hexdigest() != frozen[cid]["sha256"]:
                manifest["status"] = "stopped_dossier_changed"
                break
            if batch_spend(start_index) >= batch_limit:
                manifest["status"] = "stopped_batch_ceiling"
                break
            run_dir = folder / name / label
            print(f"Starting {cid} {label} ({len(manifest['runs']) + 1}/{total_runs})", flush=True)
            with (folder / name / f"{label}.log").open("w") as log:
                completed = subprocess.run(
                    [sys.executable, "-m", "nighthunter.live", "--case", cid,
                     "--variant", "adaptive", "--policy", policy,
                     "--input-version", "current", "--adaptation", "current",
                     "--dossier", str(dossier_path), "--out", str(run_dir),
                     "--batch-start-index", str(start_index),
                     "--batch-limit-usd", str(batch_limit)],
                    cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False)
            summary_path = run_dir / "summary.json"
            row = {"case_id": cid, "policy": policy, "repeat": repeat, "label": label,
                   "directory": str(run_dir),
                   "exit_code": completed.returncode, "status": "error", "score": None,
                   "session_opened": (run_dir / "session.json").exists()}
            bad = bool(completed.returncode or not summary_path.exists())
            if summary_path.exists():
                summary = json.loads(summary_path.read_text())
                result = summary.get("result") or {}
                deal = bool(result.get("deal"))
                must_haves = (not deal or must_haves_ok(hosted[cid], result.get("terms") or {}))
                row.update(status="completed" if not bad else "error", score=result.get("score"),
                           deal=deal, must_haves_ok=must_haves, fallbacks=summary.get("fallbacks", 0),
                           rounds=summary.get("rounds"), accounted_usd=summary.get("accounted_usd_upper"),
                           conversation=str(run_dir / "conversation.json"))
                bad = bad or bool(row["fallbacks"])
                if not must_haves:
                    manifest["status"] = "stopped_broken_must_have"
            elif (run_dir / "error.json").exists():
                row["error"] = json.loads((run_dir / "error.json").read_text())
            decisions_path = run_dir / "decisions.json"
            if decisions_path.exists() and any(
                    "Batch budget exhausted" in str(d.get("reason", ""))
                    for d in json.loads(decisions_path.read_text())):
                manifest["status"] = "stopped_batch_ceiling"
            # A3 stops on two consecutive fallbacks, or two consecutive errors with the
            # same type/message. Different errors do not establish a repeated failure.
            if args.batch == "A3":
                if row["status"] == "error":
                    error = row.get("error") or {}
                    bad_kind = ("error", error.get("type"), error.get("message"))
                elif row.get("fallbacks"):
                    bad_kind = ("fallback",)
                else:
                    bad_kind = None
                consecutive_bad = consecutive_bad + 1 if bad_kind and bad_kind == last_bad_kind else \
                    1 if bad_kind else 0
                last_bad_kind = bad_kind
            else:
                consecutive_bad = consecutive_bad + 1 if bad else 0
            row["consecutive_errors_or_fallbacks"] = consecutive_bad
            manifest["runs"].append(row)
            manifest["batch_spend_usd"] = batch_spend(start_index)
            save_manifest(manifest_path, manifest)
            print(f"Finished {cid} {label}: {row['status']}, score={row['score']}, "
                  f"fallbacks={row.get('fallbacks')}, batch USD={manifest['batch_spend_usd']:.4f}", flush=True)
            if manifest["status"] != "running":
                break
            if consecutive_bad >= 2:
                manifest["status"] = ("stopped_repeated_error_or_fallback" if args.batch == "A3" else
                                      "stopped_two_consecutive_errors_or_fallbacks")
                break
            if "Batch budget exhausted" in str(row.get("error", {})):
                manifest["status"] = "stopped_batch_ceiling"
                break
        if manifest["status"] != "running":
            break
    if manifest["status"] == "running":
        manifest["status"] = "complete"
    manifest["batch_spend_usd"] = batch_spend(start_index)
    client = ArenaClient()
    try:
        manifest["quota_end"] = client.me().get("practice", {}).get("left")
    finally:
        client.http.close()
    save_manifest(manifest_path, manifest)
    print(f"Batch {args.batch} {manifest['status']}; {len(manifest['runs'])}/{total_runs} runs; "
          f"model USD {manifest['batch_spend_usd']:.4f}; "
          f"practice quota used {quota_start - manifest['quota_end']}", flush=True)


if __name__ == "__main__":
    main()
