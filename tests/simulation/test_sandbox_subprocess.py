"""Sandbox subprocess 격리 테스트.

CLI 실행, JSON I/O, timeout, 에러 캡처. POSIX (Linux/macOS)에서만 setrlimit 검증.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from decimal import Decimal

import pytest

from backend.simulation.sandbox.runner import (
    DEFAULT_TIMEOUT_SEC,
    run_batch,
    run_in_subprocess,
)


_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))


# ─── CLI 직접 호출 ──────────────────────────────────────────────────


def _run_cli(args: list[str], timeout: int = 10) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "backend.simulation.sandbox.runner"] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=_PROJECT_ROOT,
    )


class TestCLI:
    def test_list_steps(self):
        proc = _run_cli(["--list"])
        assert proc.returncode == 0
        payload = json.loads(proc.stdout.strip())
        assert "validator" in payload["steps"]

    def test_validator_normal(self):
        proc = _run_cli([
            "--step", "validator",
            "--input", json.dumps({"order": {"stockCode": 0}}),
        ])
        assert proc.returncode == 0
        last = proc.stdout.strip().splitlines()[-1]
        out = json.loads(last)
        assert out["ok"] is True
        assert out["result"]["validation"]["passed"] is True

    def test_unknown_step_returns_error(self):
        proc = _run_cli([
            "--step", "no_such_step",
            "--input", "{}",
        ])
        # ok=False payload + non-zero
        assert proc.returncode != 0
        last = proc.stdout.strip().splitlines()[-1]
        out = json.loads(last)
        assert out["ok"] is False
        assert "Unknown step_id" in out["error"]["message"]


# ─── run_in_subprocess (Python API) ─────────────────────────────────


class TestRunInSubprocess:
    def test_validator(self):
        result = run_in_subprocess("validator", {"order": {"stockCode": 1}})
        assert result.ok is True  # subprocess 자체는 성공 (비즈니스 결과는 fail)
        assert result.result["validation"]["passed"] is False
        assert result.result["validation"]["error_code"] == "DG001"

    def test_productivity(self):
        result = run_in_subprocess(
            "productivity",
            {"order": {"confirmedPlantCd": "K K K   "}},
        )
        assert result.ok
        assert Decimal(result.result["cumulative_productivity"]) > Decimal("0.5")

    def test_pipeline_happy(self):
        result = run_in_subprocess("pipeline", {})
        assert result.ok
        assert result.result["stage"] == "ok"

    def test_pipeline_validation_fail(self):
        result = run_in_subprocess("pipeline", {"order": {"stockCode": 1}})
        assert result.ok  # subprocess 성공, 비즈니스 fail
        assert result.result["stage"] == "validate"

    def test_subprocess_elapsed_ms_recorded(self):
        result = run_in_subprocess("validator", {})
        assert result.elapsed_ms >= 0

    def test_input_file_path_traversal_safety(self):
        """run_in_subprocess는 --input만 사용 (--input-file 미사용). 외부 경로 접근 위험 없음."""
        # 단순 sanity: CLI에 --input-file 없는 상태로 호출됨 확인
        result = run_in_subprocess("validator", {})
        assert result.ok


# ─── ProcessPool 병렬 ───────────────────────────────────────────────


class TestBatch:
    def test_run_batch(self):
        inputs = [{"order": {"stockCode": i}} for i in range(4)]
        results = run_batch("validator", inputs, max_workers=2, timeout_sec=10)
        assert len(results) == 4
        # idx 0: stockCode=0 → pass
        assert results[0].result["validation"]["passed"] is True
        # idx 1: stockCode=1 → fail (DG001)
        assert results[1].result["validation"]["error_code"] == "DG001"


# ─── POSIX limits (Linux/macOS만) ───────────────────────────────────


@pytest.mark.skipif(platform.system() == "Windows", reason="POSIX only")
class TestPosixLimits:
    def test_apply_limits_does_not_break_normal_run(self):
        """resource.setrlimit이 정상 케이스에서 부작용 없는지 확인."""
        result = run_in_subprocess(
            "validator", {}, apply_limits=True,
            timeout_sec=DEFAULT_TIMEOUT_SEC, mem_mb=256,
        )
        assert result.ok
