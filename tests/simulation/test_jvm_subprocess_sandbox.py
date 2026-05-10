"""JvmSubprocessSandbox (spec 05 §2.5 + §5) 검증.

실 Java 미존재 환경에서 동작 — subprocess.run 을 monkeypatch 로 mock.
- envelope 직렬화 (§5.2) / 역직렬화 (§5.3 / §5.4)
- timeout 처리
- Java/jar 미존재 시 SubprocessNotAvailable
- ok / error envelope 분기
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

import pytest

from backend.shared.contracts.simulation import (
    RunInputs,
    RunOptions,
    SandboxCapabilities,
    TypedValue,
)


def _capabilities():
    return SandboxCapabilities(backend="jvm_subprocess", max_heap_mb=256)


def _run_inputs():
    return RunInputs(
        slots={"primary": TypedValue(_type="scm.order.Order", value={"width": 1180})},
        primary_input_slot="primary",
    )


# ─── 1. 인스턴스화 / Java 검증 ─────────────────────────────────────


def test_init_rejects_non_jvm_subprocess_backend():
    from backend.simulation.runner.jvm_subprocess_sandbox import JvmSubprocessSandbox

    cap = SandboxCapabilities(backend="stub")
    with pytest.raises(ValueError, match="jvm_subprocess"):
        JvmSubprocessSandbox(cap)


def test_init_raises_when_java_missing(monkeypatch):
    """java 가 PATH 에 없으면 SubprocessNotAvailable."""
    from backend.simulation.runner.jvm_subprocess_sandbox import (
        JvmSubprocessSandbox,
        SubprocessNotAvailable,
    )

    monkeypatch.setattr(shutil, "which", lambda _: None)
    monkeypatch.delenv("JAVA_HOME", raising=False)
    with pytest.raises(SubprocessNotAvailable):
        JvmSubprocessSandbox(_capabilities())


def test_init_raises_when_instrumentation_jar_missing(monkeypatch):
    from backend.simulation.runner.jvm_subprocess_sandbox import (
        JvmSubprocessSandbox,
        SubprocessNotAvailable,
    )

    # java 는 fake (which 가 path 반환)
    monkeypatch.setattr(shutil, "which", lambda x: "/fake/java" if x == "java" else None)
    monkeypatch.setattr(
        "backend.simulation.runner.jvm_subprocess_sandbox._is_executable",
        lambda p: True,
    )
    cap = SandboxCapabilities(
        backend="jvm_subprocess",
        instrumentation_jar="/nonexistent/jar.jar",
    )
    with pytest.raises(SubprocessNotAvailable, match="instrumentation_jar"):
        JvmSubprocessSandbox(cap)


def test_init_succeeds_with_executable_java(monkeypatch):
    from backend.simulation.runner.jvm_subprocess_sandbox import JvmSubprocessSandbox

    monkeypatch.setattr(shutil, "which", lambda x: "/fake/java")
    monkeypatch.setattr(
        "backend.simulation.runner.jvm_subprocess_sandbox._is_executable",
        lambda p: True,
    )
    sandbox = JvmSubprocessSandbox(_capabilities())
    assert sandbox is not None


# ─── 2. dispatch — ok envelope (spec 05 §5.3) ────────────────────


def test_dispatch_parses_ok_envelope(monkeypatch):
    """JVM stdout 가 §5.3 ok envelope → DispatchResult."""
    from backend.simulation.runner.jvm_subprocess_sandbox import JvmSubprocessSandbox

    # mock subprocess.run — JVM 의 ok 응답
    ok_envelope = {
        "request_id": "abc",
        "status": "ok",
        "outputs": {"slabResult": {"_type": "scm.slab.Slab", "width": 1180}},
        "realized_method_fqn": "com.example.SdDesigner.runStep1",
        "dispatch_consistent": True,
        "dispatch_mismatch_reason": None,
        "anchor_hits": [
            {"anchor_id": "a1", "marker": "자리 1 = HR", "line": 58, "captured_value": "HR"}
        ],
        "br_triggers": [
            {"br_fqn": "br.x.A", "outcome": "passed",
             "enforcer_method_fqn": "com.X.enforce", "violation_path": None,
             "expected": None, "actual": None},
        ],
        "duration_ms": 142,
    }

    def _fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            cmd, returncode=0,
            stdout=json.dumps(ok_envelope, ensure_ascii=False),
            stderr="[JVM] dispatched OK\n",
        )

    monkeypatch.setattr(shutil, "which", lambda x: "/fake/java")
    monkeypatch.setattr(
        "backend.simulation.runner.jvm_subprocess_sandbox._is_executable",
        lambda p: True,
    )
    monkeypatch.setattr(subprocess, "run", _fake_run)

    sandbox = JvmSubprocessSandbox(_capabilities())
    result = sandbox.dispatch("action.x", _run_inputs(), RunOptions())

    assert result.realized_method_fqn == "com.example.SdDesigner.runStep1"
    assert result.dispatch_consistent is True
    assert result.outputs == {"slabResult": {"_type": "scm.slab.Slab", "width": 1180}}
    assert result.duration_ms == 142
    assert len(result.captured_anchors) == 1
    assert result.captured_anchors[0].marker == "자리 1 = HR"
    assert len(result.captured_brs) == 1
    assert result.captured_brs[0].outcome == "passed"
    assert "JVM" in result.jvm_log


# ─── 3. dispatch — error envelope (spec 05 §5.4) ─────────────────


def test_dispatch_parses_error_envelope(monkeypatch):
    """error envelope → dispatch_consistent=False + mismatch_reason 채움."""
    from backend.simulation.runner.jvm_subprocess_sandbox import JvmSubprocessSandbox

    err_envelope = {
        "request_id": "xyz",
        "status": "error",
        "error_kind": "dispatch_unresolved",
        "error_message": "no realization for input type X",
        "partial_outputs": {},
        "duration_ms": 5,
    }

    def _fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            cmd, returncode=0, stdout=json.dumps(err_envelope), stderr="",
        )

    monkeypatch.setattr(shutil, "which", lambda x: "/fake/java")
    monkeypatch.setattr(
        "backend.simulation.runner.jvm_subprocess_sandbox._is_executable",
        lambda p: True,
    )
    monkeypatch.setattr(subprocess, "run", _fake_run)

    sandbox = JvmSubprocessSandbox(_capabilities())
    result = sandbox.dispatch("action.x", _run_inputs(), RunOptions())
    assert result.dispatch_consistent is False
    assert "no realization" in (result.dispatch_mismatch_reason or "")


# ─── 4. timeout 처리 ─────────────────────────────────────────────


def test_dispatch_raises_timeout_error(monkeypatch):
    from backend.simulation.runner.jvm_subprocess_sandbox import JvmSubprocessSandbox

    def _fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 30.0)

    monkeypatch.setattr(shutil, "which", lambda x: "/fake/java")
    monkeypatch.setattr(
        "backend.simulation.runner.jvm_subprocess_sandbox._is_executable",
        lambda p: True,
    )
    monkeypatch.setattr(subprocess, "run", _fake_run)

    sandbox = JvmSubprocessSandbox(_capabilities())
    with pytest.raises(TimeoutError, match="timeout"):
        sandbox.dispatch("action.x", _run_inputs(), RunOptions(timeout_sec=30))


# ─── 5. JVM crash (exit code != 0) ───────────────────────────────


def test_dispatch_raises_jvm_crash_on_nonzero_exit(monkeypatch):
    from backend.simulation.runner.jvm_subprocess_sandbox import (
        JvmSubprocessSandbox,
        JVMCrashError,
    )

    def _fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            cmd, returncode=139, stdout="", stderr="SIGSEGV in JVM",
        )

    monkeypatch.setattr(shutil, "which", lambda x: "/fake/java")
    monkeypatch.setattr(
        "backend.simulation.runner.jvm_subprocess_sandbox._is_executable",
        lambda p: True,
    )
    monkeypatch.setattr(subprocess, "run", _fake_run)

    sandbox = JvmSubprocessSandbox(_capabilities())
    with pytest.raises(JVMCrashError, match="139"):
        sandbox.dispatch("action.x", _run_inputs(), RunOptions())


# ─── 6. invalid JSON 응답 ─────────────────────────────────────────


def test_dispatch_raises_serialization_error_on_bad_json(monkeypatch):
    from backend.simulation.runner.jvm_subprocess_sandbox import (
        JvmSubprocessSandbox,
        SerializationError,
    )

    def _fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="not json", stderr="")

    monkeypatch.setattr(shutil, "which", lambda x: "/fake/java")
    monkeypatch.setattr(
        "backend.simulation.runner.jvm_subprocess_sandbox._is_executable",
        lambda p: True,
    )
    monkeypatch.setattr(subprocess, "run", _fake_run)

    sandbox = JvmSubprocessSandbox(_capabilities())
    with pytest.raises(SerializationError, match="JSON"):
        sandbox.dispatch("action.x", _run_inputs(), RunOptions())


# ─── 7. envelope 직렬화 정합성 (spec 05 §5.2) ─────────────────────


def test_input_envelope_includes_type_field_per_slot(monkeypatch):
    """envelope 의 inputs 가 spec 05 §5.5 의 _type 필드 포함."""
    from backend.simulation.runner.jvm_subprocess_sandbox import JvmSubprocessSandbox

    captured: dict[str, Any] = {}

    def _fake_run(cmd, **kwargs):
        captured["stdin"] = kwargs.get("input", "")
        return subprocess.CompletedProcess(
            cmd, returncode=0,
            stdout=json.dumps({"status": "ok", "outputs": {}, "anchor_hits": [], "br_triggers": []}),
            stderr="",
        )

    monkeypatch.setattr(shutil, "which", lambda x: "/fake/java")
    monkeypatch.setattr(
        "backend.simulation.runner.jvm_subprocess_sandbox._is_executable",
        lambda p: True,
    )
    monkeypatch.setattr(subprocess, "run", _fake_run)

    sandbox = JvmSubprocessSandbox(_capabilities())
    sandbox.dispatch("action.x", _run_inputs(), RunOptions())

    envelope = json.loads(captured["stdin"])
    assert envelope["action_fqn"] == "action.x"
    assert envelope["primary_input_slot"] == "primary"
    # primary slot 의 _type 필드
    assert envelope["inputs"]["primary"]["_type"] == "scm.order.Order"
    assert envelope["inputs"]["primary"]["value"] == {"width": 1180}
    # options
    assert envelope["options"]["timeout_ms"] == 30000  # default 30s


# ─── 8. JavaSandbox Protocol 호환 (orchestrator 가 swap 가능) ─────


def test_jvm_subprocess_satisfies_java_sandbox_protocol(monkeypatch):
    """isinstance(sandbox, JavaSandbox) 가 True — orchestrator 와 swap 가능."""
    from backend.simulation.runner.java_sandbox import JavaSandbox
    from backend.simulation.runner.jvm_subprocess_sandbox import JvmSubprocessSandbox

    monkeypatch.setattr(shutil, "which", lambda x: "/fake/java")
    monkeypatch.setattr(
        "backend.simulation.runner.jvm_subprocess_sandbox._is_executable",
        lambda p: True,
    )
    sandbox = JvmSubprocessSandbox(_capabilities())
    assert isinstance(sandbox, JavaSandbox)
