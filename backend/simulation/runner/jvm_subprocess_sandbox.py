"""JvmSubprocessSandbox (spec 05 §2.5 jvm_subprocess tier + §5 Python↔Java boundary).

실제 Java 코드를 별도 process 로 spawn 해 dispatch 실행 + anchor/BR capture.
Python 측은 spec 05 §5.2~5.4 의 JSON envelope (입력 / 출력 / 에러) 로 통신.

격리 정책 (spec 05 §2.5):
- JVM 충돌 / OOM 이 시뮬 process 를 죽이지 않음 (subprocess 격리)
- 직렬화 비용 ~100ms/dispatch 감수 — 운영 v1 권장 tier
- timeout: subprocess.run(timeout=...) 으로 강제 kill

graceful fallback:
- Java / instrumentation jar 미존재 시 → SubprocessNotAvailable raise
- 호출자 (orchestrator / spec_router) 가 StubJavaSandbox 로 자동 fallback 가능
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from typing import Any, Optional

from backend.shared.contracts.simulation import (
    AnchorHit,
    BRTrigger,
    DispatchResult,
    RunInputs,
    RunOptions,
    SandboxCapabilities,
)

logger = logging.getLogger(__name__)


class SubprocessNotAvailable(RuntimeError):
    """Java / instrumentation jar 미존재 — 호출자가 fallback 결정."""


class JvmSubprocessSandbox:
    """spec 05 §2.5 jvm_subprocess tier — 실제 JVM subprocess 호출.

    Constructor:
        capabilities       : SandboxCapabilities(backend='jvm_subprocess', ...)
        java_executable    : 'java' 또는 절대경로 (default: shutil.which('java'))
        instrumentation_jar: anchor/BR capture 용 jar 경로 (capabilities.instrumentation_jar)

    Raises:
        SubprocessNotAvailable: Java / jar 미존재 (생성자 시점에 검증)
    """

    def __init__(
        self,
        capabilities: SandboxCapabilities,
        *,
        java_executable: Optional[str] = None,
        instrumentation_jar: Optional[str] = None,
    ):
        if capabilities.backend != "jvm_subprocess":
            raise ValueError(
                f"JvmSubprocessSandbox 는 SandboxCapabilities.backend='jvm_subprocess' 만 받음 — "
                f"got {capabilities.backend!r}"
            )
        self._cap = capabilities

        self._java = java_executable or shutil.which("java") or os.getenv("JAVA_HOME")
        if self._java is None or not _is_executable(self._java):
            raise SubprocessNotAvailable(
                f"java executable 미존재 (java={self._java!r}). "
                f"PATH 또는 JAVA_HOME 설정 / SandboxCapabilities.java_version 확인."
            )

        self._jar = instrumentation_jar or capabilities.instrumentation_jar
        if self._jar and not os.path.exists(self._jar):
            raise SubprocessNotAvailable(
                f"instrumentation_jar 미존재: {self._jar!r}"
            )

        logger.info(
            "JvmSubprocessSandbox wired: java=%s, jar=%s, max_heap=%dMB",
            self._java, self._jar, capabilities.max_heap_mb,
        )

    # ─── Public — JavaSandbox Protocol ────────────────────────

    def dispatch(
        self,
        action_fqn: str,
        inputs: RunInputs,
        run_options: RunOptions,
    ) -> DispatchResult:
        """spec 05 §2.2 dispatch — JVM subprocess 로 실 Java method 실행.

        흐름 (spec 05 §5.2~5.4):
          1. inputs envelope 직렬화 (JSON)
          2. java -jar instrumentation.jar (또는 단순 java -cp ...) subprocess spawn
          3. stdin 으로 envelope 전달, stdout 으로 결과 수신
          4. JSON envelope 역직렬화 → DispatchResult

        Raises:
            TimeoutError       : subprocess timeout 초과
            JVMCrashError      : process exit code != 0
            SerializationError : JSON 파싱 실패
        """
        envelope = self._build_input_envelope(action_fqn, inputs, run_options)
        envelope_json = json.dumps(envelope, ensure_ascii=False, default=str)

        cmd = self._build_command(run_options)
        logger.debug("JVM subprocess: %s (envelope %d bytes)", cmd, len(envelope_json))

        try:
            proc = subprocess.run(
                cmd,
                input=envelope_json,
                capture_output=True,
                text=True,
                timeout=run_options.timeout_sec,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(
                f"JVM subprocess timeout after {run_options.timeout_sec}s for {action_fqn!r}"
            ) from exc

        if proc.returncode != 0:
            raise JVMCrashError(
                f"JVM subprocess exit {proc.returncode} for {action_fqn!r}: "
                f"stderr={proc.stderr[:500]!r}"
            )

        return self._parse_output_envelope(proc.stdout, jvm_log=proc.stderr)

    # ─── 내부 — envelope 직렬화 (spec 05 §5.2) ──────────────────

    def _build_input_envelope(
        self,
        action_fqn: str,
        inputs: RunInputs,
        run_options: RunOptions,
    ) -> dict[str, Any]:
        """spec 05 §5.2 입력 envelope.

        {request_id, action_fqn, method_fqn, inputs, options}
        """
        slots_serial: dict[str, Any] = {}
        for name, tv in inputs.slots.items():
            slots_serial[name] = {
                "_type": tv.type_,  # spec 05 §5.5 type 식별자
                "value": tv.value,
            }
        return {
            "request_id": _make_request_id(),
            "action_fqn": action_fqn,
            "method_fqn": None,  # JVM 측 dispatch 가 결정 (spec 05 §2.3)
            "inputs": slots_serial,
            "primary_input_slot": inputs.primary_input_slot,
            "overrides": inputs.overrides,
            "options": {
                "timeout_ms": int(run_options.timeout_sec * 1000),
                "instrumentation": "all" if run_options.capture_traces else "none",
            },
        }

    # ─── 내부 — envelope 역직렬화 (spec 05 §5.3 / §5.4) ────────

    @staticmethod
    def _parse_output_envelope(stdout: str, jvm_log: str) -> DispatchResult:
        """spec 05 §5.3 출력 envelope 또는 §5.4 에러 envelope.

        {status, outputs, anchor_hits, br_triggers, duration_ms, jvm_log_ref}
        """
        try:
            envelope = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise SerializationError(
                f"JVM subprocess stdout 가 valid JSON 아님: {stdout[:200]!r}"
            ) from exc

        status = envelope.get("status", "ok")
        if status == "error":
            # error envelope (spec 05 §5.4)
            return DispatchResult(
                outputs=envelope.get("partial_outputs", {}),
                realized_method_fqn=envelope.get("realized_method_fqn"),
                dispatch_consistent=False,
                dispatch_mismatch_reason=envelope.get("error_message", "JVM error"),
                duration_ms=envelope.get("duration_ms", 0),
                jvm_log=jvm_log,
                captured_anchors=[],
                captured_brs=[],
            )

        # ok envelope (spec 05 §5.3)
        anchors = [
            AnchorHit(
                anchor_id=h.get("anchor_id", ""),
                marker=h.get("marker", ""),
                line=h.get("line", 0),
                captured_value=h.get("captured_value"),
            )
            for h in envelope.get("anchor_hits", [])
        ]
        triggers = [
            BRTrigger(
                br_fqn=t.get("br_fqn", ""),
                enforcer_method_fqn=t.get("enforcer_method_fqn"),
                outcome=t.get("outcome", "passed"),
                violation_path=t.get("violation_path"),
                expected=t.get("expected"),
                actual=t.get("actual"),
            )
            for t in envelope.get("br_triggers", [])
        ]
        return DispatchResult(
            outputs=envelope.get("outputs", {}),
            realized_method_fqn=envelope.get("realized_method_fqn"),
            dispatch_consistent=envelope.get("dispatch_consistent", True),
            dispatch_mismatch_reason=envelope.get("dispatch_mismatch_reason"),
            duration_ms=envelope.get("duration_ms", 0),
            jvm_log=jvm_log,
            captured_anchors=anchors,
            captured_brs=triggers,
        )

    # ─── 내부 — JVM 명령 빌드 ────────────────────────────────

    def _build_command(self, run_options: RunOptions) -> list[str]:
        """java -Xmx{N}m -jar {instrumentation_jar} 형식.

        instrumentation_jar 미설정 시 단순 dispatch wrapper 가정 — 호출자가 jar 명세 책임.
        """
        cmd = [self._java, f"-Xmx{self._cap.max_heap_mb}m"]
        for cp_root in self._cap.classpath_roots:
            cmd.extend(["-cp", cp_root])
        if self._jar:
            cmd.extend(["-jar", self._jar])
        return cmd


# ─── 예외 ───────────────────────────────────────────────────────


class JVMCrashError(RuntimeError):
    """JVM subprocess exit code != 0."""


class SerializationError(RuntimeError):
    """JVM stdout JSON 파싱 실패."""


# ─── 헬퍼 ───────────────────────────────────────────────────────


def _is_executable(path: str) -> bool:
    """path 가 실 executable file (또는 PATH 의 binary) 인지 확인."""
    if os.path.isfile(path) and os.access(path, os.X_OK):
        return True
    # which() 로 PATH 검색
    return shutil.which(path) is not None


def _make_request_id() -> str:
    import uuid
    return uuid.uuid4().hex


__all__ = [
    "JvmSubprocessSandbox",
    "SubprocessNotAvailable",
    "JVMCrashError",
    "SerializationError",
]
