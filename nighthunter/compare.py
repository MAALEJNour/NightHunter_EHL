"""Sequential, frozen-input prompt comparison on one hosted practice case."""

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from .context import ROOT, encoded
from .experiment import VARIANTS


def fingerprint():
    files = sorted((ROOT / "nighthunter").glob("*.py")) + sorted((ROOT / "prompts").glob("*.md"))
    return hashlib.sha256(b"".join(p.name.encode() + p.read_bytes() for p in files)).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dossier", type=Path, required=True)
    parser.add_argument("--repeats", type=int, choices=[1, 2, 3], default=2)
    parser.add_argument("--variants", nargs="+", choices=VARIANTS, default=list(VARIANTS))
    parser.add_argument("--policies", nargs="+", choices=["current", "economics", "packages"],
                        default=["current"])
    parser.add_argument("--input-versions", nargs="+",
                        choices=["current", "unused_claims", "buyer_history", "offer_history"],
                        default=["current"])
    parser.add_argument("--adaptations", nargs="+", choices=["current", "reply_aware"], default=["current"])
    args = parser.parse_args()
    variants = list(dict.fromkeys(args.variants))
    policies = list(dict.fromkeys(args.policies))
    input_versions = list(dict.fromkeys(args.input_versions))
    adaptations = list(dict.fromkeys(args.adaptations))
    conditions = [(variant, policy, input_version, adaptation) for variant in variants
                  for policy in policies for input_version in input_versions for adaptation in adaptations]
    dossier = json.loads(args.dossier.read_text())
    folder = ROOT / "artifacts/comparisons" / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    folder.mkdir(parents=True)
    frozen = folder / "dossier.json"
    frozen.write_text(encoded(dossier))
    code_hash = fingerprint()
    manifest = {"case_id": dossier["case"]["case_id"], "code_and_prompts_sha256": code_hash,
                "context_sha256": hashlib.sha256(encoded(dossier).encode()).hexdigest(),
                "repeats": args.repeats, "conditions": conditions, "runs": [], "status": "running"}
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"Comparison: {folder}", flush=True)
    for repeat in range(args.repeats):
        order = conditions if repeat % 2 == 0 else list(reversed(conditions))
        for variant, policy, input_version, adaptation in order:
            label = variant if policies == ["current"] else f"{variant}_{policy}"
            if input_versions != ["current"]:
                label += f"_{input_version}"
            if adaptations != ["current"]:
                label += f"_{adaptation}"
            if fingerprint() != code_hash:
                raise RuntimeError("Code or prompts changed during comparison; stopped to preserve fairness")
            target = folder / f"{repeat + 1}_{label}"
            print(f"Starting repeat {repeat + 1}: {label}", flush=True)
            with (folder / f"{repeat + 1}_{label}.log").open("w") as log:
                completed = subprocess.run(
                    [sys.executable, "-m", "nighthunter.live", "--case", dossier["case"]["case_id"],
                     "--variant", variant, "--policy", policy, "--input-version", input_version,
                     "--adaptation", adaptation,
                     "--dossier", str(frozen), "--out", str(target)],
                    cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False,
                )
            row = {"repeat": repeat + 1, "variant": variant, "policy": policy, "input_version": input_version,
                   "adaptation": adaptation,
                   "condition": label, "exit_code": completed.returncode,
                   "directory": str(target), "status": "failed", "score": None}
            if (target / "summary.json").exists():
                summary = json.loads((target / "summary.json").read_text())
                if summary["context_sha256"] != manifest["context_sha256"]:
                    raise RuntimeError("Run context differed from frozen context")
                row.update(status="completed", score=summary["result"].get("score"),
                           deal=summary["result"].get("deal"), fallbacks=summary["fallbacks"],
                           autonomous=summary["autonomous_completion"],
                           cost_usd=summary["accounted_usd_upper"],
                           seconds=summary["elapsed_seconds"], session_id=summary["session_id"],
                           package_diagnostics=summary.get("package_diagnostics", []))
            manifest["runs"].append(row)
            (folder / "manifest.json").write_text(json.dumps(manifest, indent=2))
            print(json.dumps(row), flush=True)
            if completed.returncode:
                # Avoid charging more cases after an infrastructure failure; preserve its record.
                manifest["status"] = "stopped_after_failure"
                (folder / "manifest.json").write_text(json.dumps(manifest, indent=2))
                raise SystemExit(1)
    manifest["status"] = "complete"
    manifest["aggregates"] = {}
    for variant, policy, input_version, adaptation in conditions:
        label = variant if policies == ["current"] else f"{variant}_{policy}"
        if input_versions != ["current"]:
            label += f"_{input_version}"
        if adaptations != ["current"]:
            label += f"_{adaptation}"
        rows = [r for r in manifest["runs"] if r["condition"] == label]
        manifest["aggregates"][label] = {
            "attempts": len(rows), "mean_score": sum((r.get("score") or 0) for r in rows) / len(rows),
            "deals": sum(bool(r.get("deal")) for r in rows),
            "fallbacks": sum(r.get("fallbacks", 0) for r in rows),
            "package_decisions": sum(len(r.get("package_diagnostics", [])) for r in rows),
            "cost_usd": sum(r.get("cost_usd", 0) for r in rows),
        }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest["aggregates"], indent=2), flush=True)


if __name__ == "__main__":
    main()
