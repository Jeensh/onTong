"""Sandbox runner — subprocess 격리 + resource limit + JSON I/O.

In-process 실행이 가능한 step (registry.py)을 외부 Python 프로세스에서 돌려
메모리/CPU 한도 + 예외 폭발 격리. Agent 1/2가 다수 케이스를 돌릴 때 사용.

CLI:
    python -m backend.simulation.sandbox.runner \\
        --step productivity \\
        --input '{"order":{"confirmedPlantCd":"K K K   "},"rules":{"hr":"0.95"}}'

Python API:
    from backend.simulation.sandbox.runner import run_in_subprocess
    result = run_in_subprocess("productivity", {...}, timeout_sec=5, mem_mb=256)
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass
from typing import Any, Optional


# ─── 한도 기본값 ─────────────────────────────────────────────────────

DEFAULT_TIMEOUT_SEC = 5
DEFAULT_MEM_MB = 256


# ─── Subprocess 진입점 ────────────────────────────────────────────────


def _entrypoint(argv: list[str]) -> int:
    """`python -m backend.simulation.sandbox.runner` 진입.

    --apply-limits 가 켜져 있고 POSIX이면 resource.setrlimit으로 자기 자신 제한.
    """
    parser = argparse.ArgumentParser(description="slab-design step sandbox runner")
    parser.add_argument("--step", help="step id (validator|productivity|thickness|split_range|slab_count|slab_weight|pipeline)")
    parser.add_argument("--input", default="{}", help="JSON string for step inputs")
    parser.add_argument("--input-file", default=None, help="JSON file path (overrides --input)")
    parser.add_argument("--apply-limits", action="store_true", help="POSIX resource.setrlimit")
    parser.add_argument("--mem-mb", type=int, default=DEFAULT_MEM_MB)
    parser.add_argument("--cpu-sec", type=int, default=DEFAULT_TIMEOUT_SEC)
    parser.add_argument("--list", action="store_true", help="list available step ids")
    args = parser.parse_args(argv)

    # registry는 entrypoint 내부에서 import (자식 프로세스 빠른 시작)
    from . import registry  # noqa: WPS433

    if args.list:
        print(json.dumps({"steps": registry.list_steps()}))
        return 0

    if not args.step:
        parser.error("--step is required (or use --list)")
        return 2  # unreachable; parser.error sys.exits

    if args.apply_limits and os.name == "posix":
        _apply_posix_limits(mem_mb=args.mem_mb, cpu_sec=args.cpu_sec)

    if args.input_file:
        with open(args.input_file, "r", encoding="utf-8") as fh:
            inputs = json.load(fh)
    else:
        inputs = json.loads(args.input)

    started = time.perf_counter()
    try:
        result = registry.run_step(args.step, inputs)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        print(json.dumps({"ok": True, "step": args.step, "result": result, "elapsed_ms": elapsed_ms}))
        return 0
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        print(json.dumps({
            "ok": False,
            "step": args.step,
            "error": {
                "type": type(e).__name__,
                "message": str(e),
                "traceback": traceback.format_exc(),
            },
            "elapsed_ms": elapsed_ms,
        }))
        return 1


def _shutdown_short_lived_resources() -> None:
    """short-lived 자식 프로세스 종료 직전 cleanup.

    psycopg_pool ConnectionPool background thread 가 join 안 되면 5초 이상 hang
    → 호출자 subprocess wallclock timeout. close_pool() 명시 호출로 즉시 종료.
    """
    try:
        from backend.simulation.storage.postgres.connection import close_pool
        close_pool()
    except Exception:
        pass


def _apply_posix_limits(*, mem_mb: int, cpu_sec: int) -> None:
    """POSIX resource.setrlimit — Linux/macOS만 동작."""
    try:
        import resource  # POSIX only
    except ImportError:
        return

    # CPU 시간 (초)
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_sec, cpu_sec + 1))
    except (ValueError, OSError):
        pass

    # 메모리 (bytes) — macOS에서는 RLIMIT_AS가 무시되는 경우 있음, 그래도 시도
    bytes_ = mem_mb * 1024 * 1024
    for key in ("RLIMIT_AS", "RLIMIT_DATA"):
        if hasattr(resource, key):
            try:
                resource.setrlimit(getattr(resource, key), (bytes_, bytes_))
            except (ValueError, OSError):
                pass


# ─── 부모 프로세스 API ────────────────────────────────────────────────


@dataclass
class SandboxResult:
    """run_in_subprocess 반환값."""

    ok: bool
    step: str
    result: Optional[dict] = None
    error: Optional[dict] = None
    elapsed_ms: int = 0
    stdout: str = ""
    stderr: str = ""

    def raise_for_error(self) -> None:
        if not self.ok:
            raise RuntimeError(f"sandbox failed: {self.error}")


def run_in_subprocess(
    step_id: str,
    inputs: dict,
    *,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    mem_mb: int = DEFAULT_MEM_MB,
    apply_limits: bool = True,
    python_exe: Optional[str] = None,
) -> SandboxResult:
    """`python -m backend.simulation.sandbox.runner ...`을 외부 프로세스로 실행.

    부모와 stdout/stderr 분리. timeout은 subprocess.timeout으로 강제.
    Windows에서는 apply_limits=True여도 setrlimit 미적용 (best-effort).
    """
    python_exe = python_exe or sys.executable
    cmd = [
        python_exe, "-m", "backend.simulation.sandbox.runner",
        "--step", step_id,
        "--input", json.dumps(inputs),
        "--mem-mb", str(mem_mb),
        "--cpu-sec", str(timeout_sec),
    ]
    if apply_limits and platform.system() != "Windows":
        cmd.append("--apply-limits")

    started = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec + 2,  # subprocess wallclock — RLIMIT_CPU와 별개 안전망
            cwd=_project_root(),
        )
    except subprocess.TimeoutExpired as e:
        elapsed = int((time.perf_counter() - started) * 1000)
        return SandboxResult(
            ok=False,
            step=step_id,
            error={"type": "Timeout", "message": f"subprocess wallclock > {timeout_sec + 2}s"},
            elapsed_ms=elapsed,
            stdout=e.stdout or "",
            stderr=e.stderr or "",
        )

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""

    # 성공 케이스: stdout 마지막 줄이 JSON
    last_line = (stdout.strip().splitlines()[-1] if stdout.strip() else "")
    try:
        payload = json.loads(last_line)
    except json.JSONDecodeError:
        return SandboxResult(
            ok=False,
            step=step_id,
            error={
                "type": "ProtocolError",
                "message": "subprocess did not emit JSON on stdout",
                "returncode": proc.returncode,
            },
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            stdout=stdout,
            stderr=stderr,
        )

    return SandboxResult(
        ok=bool(payload.get("ok")),
        step=payload.get("step", step_id),
        result=payload.get("result"),
        error=payload.get("error"),
        elapsed_ms=int(payload.get("elapsed_ms", 0)),
        stdout=stdout,
        stderr=stderr,
    )


def _project_root() -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    # backend/simulation/sandbox/ → 3단계 상위 = project root
    return os.path.normpath(os.path.join(here, "..", "..", ".."))


# ─── ProcessPoolExecutor 헬퍼 (병렬 실행) ─────────────────────────────


def run_batch(
    step_id: str,
    inputs_list: list[dict],
    *,
    max_workers: int = 4,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    mem_mb: int = DEFAULT_MEM_MB,
) -> list[SandboxResult]:
    """다수 케이스를 병렬로 실행. 큰 N은 ThreadPoolExecutor로 충분 (각 자식이 무거운 일을 함)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results: list[SandboxResult | None] = [None] * len(inputs_list)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_idx = {
            pool.submit(
                run_in_subprocess, step_id, inp,
                timeout_sec=timeout_sec, mem_mb=mem_mb,
            ): idx for idx, inp in enumerate(inputs_list)
        }
        for fut in as_completed(future_to_idx):
            idx = future_to_idx[fut]
            try:
                results[idx] = fut.result()
            except Exception as e:  # noqa: BLE001
                results[idx] = SandboxResult(
                    ok=False, step=step_id,
                    error={"type": type(e).__name__, "message": str(e)},
                )
    # type: ignore — 채워졌음
    return [r if r is not None else SandboxResult(ok=False, step=step_id, error={"type": "Unknown"}) for r in results]


if __name__ == "__main__":
    rc = _entrypoint(sys.argv[1:])
    sys.stdout.flush()
    sys.stderr.flush()
    _shutdown_short_lived_resources()
    # os._exit 로 background thread join 우회 — stdout flush 이후이므로 안전.
    os._exit(rc)
