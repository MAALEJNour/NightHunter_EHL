import fcntl
import math
import os
import sys

import pytest

from scripts.final_preflight import (
    PreflightError,
    check_final_pid_file,
    check_launch_lock,
    check_ledger_lock,
    ledger_spend,
    run,
)
from arena_kit.client import ArenaError
from nighthunter.live import TOTAL_LIMIT_USD
from scripts.final_runner import (
    FINAL_RUN_LIMIT_USD,
    FINAL_TOTAL_LIMIT_USD,
    Runner,
    main as final_runner_main,
)


def test_ledger_spend_includes_all_reservations_and_completions():
    records = [
        {"accounted_usd": 0.4, "state": "completed"},
        {"accounted_usd": 0.1, "state": "failed_reservation_retained"},
    ]

    assert ledger_spend(records) == pytest.approx(0.5)


@pytest.mark.parametrize("records", [
    {},
    [None],
    [{"accounted_usd": True}],
    [{"accounted_usd": -0.01}],
    [{"accounted_usd": math.inf}],
    [{"accounted_usd": "0.20"}],
])
def test_ledger_spend_rejects_malformed_entries(records):
    with pytest.raises(PreflightError):
        ledger_spend(records)


def test_preflight_detects_an_active_budget_writer(tmp_path):
    lock_path = tmp_path / "budget.lock"
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(PreflightError, match="another model runner"):
            check_ledger_lock(lock_path)
        fcntl.flock(lock, fcntl.LOCK_UN)


def test_preflight_turns_process_execution_errors_into_check_failures(monkeypatch):
    def denied(*args, **kwargs):
        raise PermissionError("blocked by sandbox")

    monkeypatch.setattr("scripts.final_preflight.subprocess.run", denied)

    result = run(["ps"])

    assert result.returncode != 0
    assert result.stderr == "PermissionError"


def test_preflight_refuses_a_live_final_runner_pid(tmp_path):
    pid_path = tmp_path / "final_runner.pid"
    pid_path.write_text(str(os.getpid()))

    with pytest.raises(PreflightError, match="still active"):
        check_final_pid_file(pid_path)


def test_preflight_removes_a_stale_final_runner_pid(tmp_path, monkeypatch):
    pid_path = tmp_path / "final_runner.pid"
    pid_path.write_text("999999999")

    def missing_process(pid, signal):
        raise ProcessLookupError

    monkeypatch.setattr("scripts.final_preflight.os.kill", missing_process)

    check_final_pid_file(pid_path)

    assert not pid_path.exists()


def test_preflight_refuses_a_concurrent_launcher(tmp_path):
    lock_path = tmp_path / "final_runner.launch.lock"
    lock_path.mkdir()
    (lock_path / "pid").write_text(str(os.getpid()))

    with pytest.raises(PreflightError, match="another launcher"):
        check_launch_lock(lock_path)


def test_preflight_cleans_a_stale_launcher_lock(tmp_path, monkeypatch):
    lock_path = tmp_path / "final_runner.launch.lock"
    lock_path.mkdir()
    (lock_path / "pid").write_text("999999999")

    def missing_process(pid, signal):
        raise ProcessLookupError

    monkeypatch.setattr("scripts.final_preflight.os.kill", missing_process)

    check_launch_lock(lock_path)

    assert not lock_path.exists()


def test_final_runner_rejects_per_launch_budget_above_two_dollars(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["final_runner.py", "--final", "--limit-usd", "2.01"])

    with pytest.raises(SystemExit, match="<= 2.00"):
        final_runner_main()


def test_final_budget_raise_is_scoped_to_final_only():
    assert TOTAL_LIMIT_USD == 7
    assert FINAL_TOTAL_LIMIT_USD == 15
    assert FINAL_RUN_LIMIT_USD == 2


def test_final_runner_reports_pre_wave_403_as_waiting(tmp_path, capsys):
    class WaitingClient:
        calls = 0

        def cases(self, set_name):
            self.calls += 1
            if self.calls == 1:
                raise ArenaError(403, "wave has not started")
            return [{"case_id": "case:test", "wave": 1, "open": False}]

    client = WaitingClient()
    runner = Runner(client, model=None, out=tmp_path)
    try:
        runner.final(waves=1, poll=0)
    finally:
        if runner.package.db:
            runner.package.db.close()

    output = capsys.readouterr().out
    assert "Final runner ready: polling final cases" in output
    assert "not available yet (403); waiting" in output
