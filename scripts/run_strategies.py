"""Compare negotiation strategies on the single-supplier practice cases, strictly sequentially.

    python scripts/run_strategies.py --name S1 --limit-usd 0.70 \
        --conditions current=current/current packages=packages/current prose=packages/expert_prose

Each condition is label=policy/adaptation. One frozen dossier per case is shared by all conditions;
order rotates per case. Stops on: code/prompt change, budget ceiling, a broken must-have, or the
same error twice in a row. Hosted practice sessions consume quota; model calls are ledgered.
"""

import argparse
import glob
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from arena_kit.cli import load_env
from arena_kit.client import ArenaClient
from arena_kit.cost import must_haves_ok
from arena_kit.data import DataPackage
from arena_kit.docs import standard_terms

from nighthunter.compare import fingerprint
from nighthunter.context import DEFAULT_DATA, ROOT, CaseContextBuilder, encoded
from nighthunter.live import LiveAgent
from nighthunter.packages import plan_packages
from nighthunter.supplier_profile import build_profile
from nighthunter.validation import validate_sheets

CASES = ("P01", "P02", "P03", "P04", "P07", "P08", "P10", "P11", "P18")
REFERENCE = Path.home() / "Downloads/saved-negotiation-conversations-2026-10-10/replays/practice-20261010T141311Z"


def spend(start):
    path = ROOT / "artifacts/llm-budget.json"
    return sum(r["accounted_usd"] for r in (json.loads(path.read_text()) if path.exists() else [])[start:])


def opening_for(name, sid):
    paths = glob.glob(str(REFERENCE / f"case_{name}*__threads.json"))
    return json.loads(Path(paths[0]).read_text())["thread_details"][sid]["messages"][:1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--conditions", nargs="+", required=True)
    parser.add_argument("--cases", nargs="+", default=list(CASES))
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--limit-usd", type=float, required=True)
    args = parser.parse_args()
    conditions = []
    for spec in args.conditions:
        label, rest = spec.split("=")
        parts = rest.split("/")
        policy, adaptation = parts[0], parts[1]
        extra = []
        if len(parts) > 2:
            extra += ["--anchor-scale", parts[2]]
        if len(parts) > 3:
            extra += ["--reanchor", parts[3]]
        if len(parts) > 4:
            extra += ["--reasoning-effort", parts[4]]
        if len(parts) > 5:
            extra += ["--llm-model", parts[5]]
        conditions.append((label, policy, adaptation, extra))
    total = len(args.cases) * len(conditions) * args.repeats

    load_env(ROOT / ".env")
    client = ArenaClient()
    try:
        quota_start = client.me().get("practice", {}).get("left")
        if not isinstance(quota_start, int) or quota_start < total:
            raise SystemExit(f"Insufficient practice quota for {total} sessions: {quota_start}")
        hosted = {c["case_id"]: c for c in client.cases("practice")}
    finally:
        client.http.close()

    folder = ROOT / "artifacts/strategies" / f"{args.name}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    folder.mkdir(parents=True)
    package, frozen = DataPackage(DEFAULT_DATA), {}
    try:
        for name in args.cases:
            case = hosted[f"case:{name}"]
            if len(case["suppliers"]) != 1:
                raise SystemExit(f"{name} is not single-supplier")
            dossier = CaseContextBuilder().build(case, 40000)
            sid = case["suppliers"][0]
            opening = opening_for(name, sid)
            std = standard_terms(opening)
            terms = [r["terms"] for r in plan_packages(case, std, opening, build_profile(case, dossier, sid))["packages"]]
            if not terms or validate_sheets(case, terms, std) != terms or not all(must_haves_ok(case, t, std) for t in terms):
                raise SystemExit(f"Round-0 plan failed for {name}; no session opened")
            path = folder / name / "dossier.json"
            path.parent.mkdir()
            path.write_text(encoded(dossier))
            for _, policy, adaptation, _ in conditions:  # claim cards and prompts build offline
                LiveAgent(SimpleNamespace(complete=lambda *a: "{}"), package, dossier, "adaptive",
                          path.parent, policy=policy, adaptation=adaptation)
            frozen[name] = (path, hashlib.sha256(path.read_bytes()).hexdigest())
    finally:
        if package.db:
            package.db.close()

    ledger = ROOT / "artifacts/llm-budget.json"
    start = len(json.loads(ledger.read_text())) if ledger.exists() else 0
    code = fingerprint()
    manifest = {"name": args.name, "status": "running", "conditions": conditions, "cases": args.cases,
                "repeats": args.repeats, "model": "per condition (--llm-model)", "variant": "adaptive",
                "code_and_prompts_sha256": code, "ledger_start_index": start,
                "limit_usd": args.limit_usd, "quota_start": quota_start, "runs": []}
    manifest_path = folder / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"{args.name}: {folder}; {total} runs; quota {quota_start}", flush=True)
    last_error = None
    for i, name in enumerate(args.cases):
        order = conditions[i % len(conditions):] + conditions[:i % len(conditions)]
        for repeat in range(1, args.repeats + 1):
            for label, policy, adaptation, extra in order:
                path, digest = frozen[name]
                if fingerprint() != code:
                    manifest["status"] = "stopped_code_changed"
                elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                    manifest["status"] = "stopped_dossier_changed"
                elif spend(start) >= args.limit_usd:
                    manifest["status"] = "stopped_budget_ceiling"
                if manifest["status"] != "running":
                    break
                run = folder / name / f"{label}_{repeat}"
                print(f"Starting {name} {label} #{repeat} ({len(manifest['runs']) + 1}/{total})", flush=True)
                with (folder / name / f"{label}_{repeat}.log").open("w") as log:
                    done = subprocess.run(
                        [sys.executable, "-m", "nighthunter.live", "--case", f"case:{name}",
                         "--variant", "adaptive", "--policy", policy, "--input-version", "current",
                         "--adaptation", adaptation, "--dossier", str(path), "--out", str(run),
                         "--batch-start-index", str(start), "--batch-limit-usd", str(args.limit_usd), *extra],
                        cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False)
                row = {"case": name, "label": label, "policy": policy, "adaptation": adaptation, "extra": extra,
                       "repeat": repeat, "dir": str(run), "exit_code": done.returncode, "score": None}
                summary = run / "summary.json"
                if summary.exists():
                    s = json.loads(summary.read_text())
                    result = s.get("result") or {}
                    ok = not result.get("deal") or must_haves_ok(hosted[f"case:{name}"], result.get("terms") or {})
                    row.update(status="completed", score=result.get("score"), deal=result.get("deal"),
                               must_haves_ok=ok, fallbacks=s.get("fallbacks"), rounds=s.get("rounds"))
                    last_error = None
                    if not ok:
                        manifest["status"] = "stopped_broken_must_have"
                else:
                    err = run / "error.json"
                    row.update(status="error", error=json.loads(err.read_text()) if err.exists() else None)
                    kind = json.dumps(row["error"], sort_keys=True)
                    if kind == last_error:
                        manifest["status"] = "stopped_repeated_error"
                    last_error = kind
                manifest["runs"].append(row)
                manifest["spend_usd"] = spend(start)
                manifest_path.write_text(json.dumps(manifest, indent=2))
                print(f"  -> {row['status']} score={row['score']} fallbacks={row.get('fallbacks')} "
                      f"spend={manifest['spend_usd']:.4f}", flush=True)
                if manifest["status"] != "running":
                    break
            if manifest["status"] != "running":
                break
        if manifest["status"] != "running":
            break
    if manifest["status"] == "running":
        manifest["status"] = "complete"
    client = ArenaClient()
    try:
        manifest["quota_end"] = client.me().get("practice", {}).get("left")
    finally:
        client.http.close()
    manifest["spend_usd"] = spend(start)
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"{args.name} {manifest['status']}: {len(manifest['runs'])}/{total} runs, "
          f"USD {manifest['spend_usd']:.4f}", flush=True)


if __name__ == "__main__":
    main()
