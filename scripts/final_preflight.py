"""Fail-closed local and optional arena preflight for the Live Final launcher.

This performs no negotiation and makes no model calls. With ``--online`` it makes only
the read-only team identity request (GET /v1/me), so the launcher can verify the key
without relying on the upstream CLI's zero-exit-on-error behavior.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import math
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIN_FINAL_RESERVE_USD = 2.00  # must cover the final launch's hard per-run cap
EXPECTED_TEAM = "NightHunter"
EXPECTED_ARENA_URL = "https://arena.tacto.ai"
EXPECTED_LLM_BASE_URL = "https://api.openai.com/v1"
class PreflightError(RuntimeError):
    def __init__(self, message: str, status: list[str] | None = None):
        super().__init__(message)
        self.status = status or []


def ledger_spend(records: object) -> float:
    """Validate the persistent ledger and return all reserved/accounted spend."""
    if not isinstance(records, list):
        raise PreflightError("LLM ledger must contain a JSON list")
    total = 0.0
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise PreflightError(f"LLM ledger record {index + 1} is malformed")
        amount = record.get("accounted_usd")
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise PreflightError(f"LLM ledger record {index + 1} has no valid accounted amount")
        if not math.isfinite(amount) or amount < 0:
            raise PreflightError(f"LLM ledger record {index + 1} has an invalid accounted amount")
        total += amount
    return total


def run(command: list[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    except OSError as exc:
        return subprocess.CompletedProcess(command, 127, "", type(exc).__name__)


def git_checks() -> tuple[str, list[str]]:
    errors: list[str] = []
    head = run(["git", "rev-parse", "HEAD"])
    branch = run(["git", "branch", "--show-current"])
    upstream = run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    status = run(["git", "status", "--porcelain", "--untracked-files=normal"])
    if any(result.returncode for result in (head, branch, upstream, status)):
        return "unknown", ["Git metadata or upstream tracking branch could not be verified"]
    commit = head.stdout.strip()
    if branch.stdout.strip() != "main":
        errors.append("current branch must be main")
    if status.stdout.strip():
        errors.append("worktree has uncommitted or untracked files; freeze the reviewed commit first")
    remote = run(["git", "rev-parse", upstream.stdout.strip()])
    if remote.returncode or remote.stdout.strip() != commit:
        errors.append("HEAD does not match the locally recorded upstream commit; push the frozen commit first")
    return commit, errors


def check_final_pid_file(path: Path) -> None:
    if not path.exists():
        return
    raw_pid = path.read_text().strip()
    if not raw_pid.isdigit() or int(raw_pid) <= 0:
        raise PreflightError("final runner PID file is malformed; inspect it before proceeding")
    try:
        os.kill(int(raw_pid), 0)
    except ProcessLookupError:
        path.unlink()
    except PermissionError as exc:
        raise PreflightError("final runner PID exists but cannot be inspected") from exc
    else:
        raise PreflightError(f"final runner PID {raw_pid} is still active; do not start a second copy")


def check_launch_lock(path: Path) -> None:
    if not path.exists():
        return
    owner_path = path / "pid"
    if not owner_path.is_file():
        raise PreflightError("launcher start lock is incomplete; inspect it before proceeding")
    owner = owner_path.read_text().strip()
    if not owner.isdigit() or int(owner) <= 0:
        raise PreflightError("launcher start lock has an invalid owner PID; inspect it before proceeding")
    try:
        os.kill(int(owner), 0)
    except ProcessLookupError:
        owner_path.unlink()
        try:
            path.rmdir()
        except OSError as exc:
            raise PreflightError("stale launcher lock contains unexpected files; inspect it manually") from exc
    except PermissionError as exc:
        raise PreflightError("launcher lock owner exists but cannot be inspected") from exc
    else:
        raise PreflightError(f"another launcher is already starting the final (PID {owner})")


def check_ledger_lock(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise PreflightError("another model runner currently holds the LLM budget ledger lock") from exc
        finally:
            try:
                fcntl.flock(lock, fcntl.LOCK_UN)
            except OSError:
                pass


def check(root: Path = ROOT, *, online: bool = False) -> list[str]:
    """Run all checks and return user-safe status lines; raise on any failed gate."""
    root = root.resolve()
    if root != ROOT:
        raise PreflightError("preflight must run from this repository's root")
    errors: list[str] = []
    status: list[str] = []

    commit, git_errors = git_checks()
    errors.extend(git_errors)
    if not git_errors:
        status.append(f"source: clean main at {commit[:12]}, matching the recorded upstream commit")

    env_path = root / ".env"
    if not env_path.is_file():
        errors.append("root .env is missing")
    else:
        ignored = run(["git", "check-ignore", "-q", ".env"])
        tracked = run(["git", "ls-files", "--error-unmatch", ".env"])
        if ignored.returncode != 0 or tracked.returncode == 0:
            errors.append("root .env must be ignored by Git and untracked")

    try:
        from arena_kit.cli import load_env

        load_env(env_path)
    except Exception as exc:
        errors.append(f"could not load root environment file ({type(exc).__name__})")

    required = ("ARENA_API_KEY", "LLM_API_KEY")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        errors.append("required secret variables are missing from the environment: " + ", ".join(missing))
    if os.environ.get("ARENA_URL", "").rstrip("/") != EXPECTED_ARENA_URL:
        errors.append("ARENA_URL does not point to the official arena")
    if os.environ.get("LLM_PROVIDER") != "openai":
        errors.append("LLM_PROVIDER must be openai")
    if os.environ.get("LLM_BASE_URL", "").rstrip("/") != EXPECTED_LLM_BASE_URL:
        errors.append("LLM_BASE_URL does not point to the priced OpenAI endpoint")

    try:
        from nighthunter.context import DEFAULT_DATA, DEFAULT_RELEASE, CaseContextBuilder
        from nighthunter.live import PRICES, TOTAL_LIMIT_USD
        from scripts.final_runner import FINAL_RUN_LIMIT_USD, FINAL_TOTAL_LIMIT_USD

        model_name = os.environ.get("LLM_MODEL")
        if model_name not in PRICES:
            errors.append("LLM_MODEL is not in the reviewed price table")
        if not (DEFAULT_DATA / "facts.json").is_file():
            errors.append("pinned public data package is missing")
        if not (DEFAULT_RELEASE / "facts.json").is_file():
            errors.append("Sunday release data/facts.json is missing")
        else:
            dossier_builder = CaseContextBuilder()
            status.append(f"data: base package and Sunday release loaded ({len(dossier_builder.facts):,} facts)")

        ledger_path = root / "artifacts/llm-budget.json"
        if not ledger_path.is_file():
            errors.append("persistent LLM budget ledger is missing; do not recreate or reset it")
        else:
            records = json.loads(ledger_path.read_text())
            spent = ledger_spend(records)
            remaining = FINAL_TOTAL_LIMIT_USD - spent
            if remaining < MIN_FINAL_RESERVE_USD:
                errors.append(
                    f"LLM final budget reserve is too low: ${remaining:.6f} remains; "
                    f"at least ${MIN_FINAL_RESERVE_USD:.2f} is required"
                )
            else:
                status.append(
                    f"final model budget: ${spent:.6f} accounted of ${FINAL_TOTAL_LIMIT_USD:.2f}; "
                    f"${remaining:.6f} remains; this launch is capped at ${FINAL_RUN_LIMIT_USD:.2f}"
                )
            practice_remaining = max(0.0, TOTAL_LIMIT_USD - spent)
            status.append(
                f"practice/live budget: ${practice_remaining:.6f} remains under its separate "
                f"${TOTAL_LIMIT_USD:.2f} cumulative cap"
            )
            try:
                check_ledger_lock(ledger_path.with_suffix(".lock"))
            except PreflightError as exc:
                errors.append(str(exc))

        if sys.version_info[:2] != (3, 12):
            errors.append("runner must use Python 3.12")
        status.append(f"runtime: Python {sys.version_info.major}.{sys.version_info.minor}")
    except Exception as exc:
        errors.append(f"local data/model preflight failed ({type(exc).__name__})")

    try:
        check_launch_lock(root / "artifacts/final_runner.launch.lock")
        check_final_pid_file(root / "artifacts/final_runner.pid")
    except PreflightError as exc:
        errors.append(str(exc))

    try:
        for name in ("scripts/final_runner.py", "scripts/rfq_live.py", "nighthunter/live.py",
                     "nighthunter/context.py", "nighthunter/packages.py", "nighthunter/rfq.py"):
            compile((root / name).read_text(), name, "exec")
    except Exception as exc:
        errors.append(f"runner source validation failed ({type(exc).__name__})")
    else:
        status.append("code: runner and negotiation modules compile")

    if online and not errors:
        try:
            from arena_kit import ArenaClient

            client = ArenaClient()
            try:
                identity = client.me()
            finally:
                client.http.close()
            if identity.get("team_name") != EXPECTED_TEAM or identity.get("status") != "active":
                errors.append("arena key did not identify an active NightHunter team")
            else:
                practice = identity.get("practice", {}).get("left")
                status.append(f"arena key: verified active NightHunter team (practice left: {practice})")
        except Exception as exc:
            details = f"HTTP {exc.status}" if hasattr(exc, "status") else type(exc).__name__
            errors.append(f"arena identity check failed ({details}); runner was not started")

    if errors:
        raise PreflightError("\n".join(f"- {error}" for error in errors), status)
    status.append(f"freeze candidate: {commit}; verify this exact hash on ehl.gg before the event")
    status.append("preflight passed; this check opened no session and made no model call")
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--online", action="store_true", help="verify active team identity with GET /v1/me")
    args = parser.parse_args()
    try:
        print("\n".join(f"OK {line}" for line in check(online=args.online)), flush=True)
    except PreflightError as exc:
        if exc.status:
            print("\n".join(f"OK {line}" for line in exc.status), flush=True)
        print(f"PREFLIGHT FAILED\n{exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
