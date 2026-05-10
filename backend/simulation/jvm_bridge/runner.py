"""Java Bridge subprocess 래퍼.

slab-design 자체는 무수정. `java_bridge/` 가 slab-design 의 jar 를 dependency 로
참조하고 Spring Bean override 로 Oracle/Kafka 를 mock 으로 swap.

Bridge JAR 경로 우선순위:
1. env `SIMULATION_JAVA_BRIDGE_JAR` (절대경로)
2. `backend/simulation/jvm_bridge/java_bridge/target/java-bridge-*.jar` (mvn package 산출물)
3. 없으면 `is_bridge_available() == False` → fallback to Python only.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class JavaBridgeError(RuntimeError):
    """Bridge 호출 실패 — JAR 미존재 / Java 미설치 / subprocess timeout / 비-zero exit."""


_BRIDGE_DIR = Path(__file__).parent / "java_bridge"
_DEFAULT_TIMEOUT_SEC = 30.0


def _bridge_jar_path() -> Optional[Path]:
    env_path = os.getenv("SIMULATION_JAVA_BRIDGE_JAR")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p
        return None

    target_dir = _BRIDGE_DIR / "target"
    if not target_dir.is_dir():
        return None
    # java-bridge-*.jar 패턴 (Spring Boot fat jar)
    matches = sorted(target_dir.glob("java-bridge-*.jar"))
    # spring-boot-* 또는 -original 변형 제외 — fat jar 만
    matches = [m for m in matches if "original" not in m.name and "sources" not in m.name]
    return matches[-1] if matches else None


_SLAB_DESIGN_HTTP_URL = os.getenv(
    "SIMULATION_SLAB_DESIGN_URL", "http://localhost:8080"
)


def _slab_design_http_available() -> bool:
    """slab-design Spring Boot (8080) 가 H2 프로파일로 떠 있는가?
    HTTP 모드가 가용하면 subprocess JVM 호출 대신 HTTP 호출 → 자동으로 H2 시드 데이터 활용.
    """
    try:
        import urllib.request

        req = urllib.request.Request(
            f"{_SLAB_DESIGN_HTTP_URL}/api/sd/admin/counts", method="GET"
        )
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            return resp.status == 200
    except Exception:
        return False


def is_bridge_available() -> bool:
    """slab-design HTTP 또는 java-bridge JAR 둘 중 하나라도 가용하면 True."""
    if _slab_design_http_available():
        return True
    if shutil.which("java") is None:
        return False
    return _bridge_jar_path() is not None


def _decimal_default(o: Any) -> Any:
    """JSON 직렬화 시 Decimal → string (정밀도 보존)."""
    if isinstance(o, Decimal):
        return str(o)
    if hasattr(o, "isoformat"):
        return o.isoformat()
    raise TypeError(f"Not JSON serializable: {type(o)}")


@dataclass
class JavaResult:
    """Bridge 호출 결과."""
    ok: bool
    payload: dict[str, Any]            # parsed stdout JSON
    stderr: str
    elapsed_sec: float


def run_java(
    inputs: dict[str, Any],
    *,
    timeout_sec: float = _DEFAULT_TIMEOUT_SEC,
    java_opts: Optional[list[str]] = None,
) -> JavaResult:
    """slab-design 의 SdDesigner.design() 을 자바 프로세스로 호출.

    inputs 예:
        {
          "order": {
            "cmpCd": "K", "orgCd": "K01", "orderNo": "ORD-001",
            "stockCode": 0, "orderWidth": "1200", "orderLength": "3000",
            "pkgWgtLow": "5", "pkgWgtHigh": "30",
            "confirmedPlantCd": "K K K   ",
            "smDue": "2026-06-01", ...
          },
          "fixtures": {                                    # 선택 — Bridge mock 에 주입
            "castSpec": [...], "hrSpec": [...], "edgingSpec": [...]
          }
        }

    출력:
        JavaResult(ok=True, payload={"slab": {...}, "designStatus": "...", "errorCode": null|"DG..."})
    """
    # ★ 우선순위 1: slab-design HTTP (8080) 가 떠 있으면 그쪽으로 호출
    #    → MockConfig 빈 fixture 문제 회피 + H2 in-memory 시드 데이터 자동 활용
    if _slab_design_http_available():
        return _run_via_http(inputs, timeout_sec=timeout_sec)

    if not is_bridge_available():
        raise JavaBridgeError(
            "Java Bridge 미가용 — slab-design Spring Boot 를 H2 프로파일로 기동 (포트 8080):\n"
            "  java -jar slab-design-boot/target/slab-design-boot-1.0.0-SNAPSHOT.jar "
            "--spring.profiles.active=h2\n"
            "또는 java-bridge fat jar 빌드:\n"
            "  cd backend/simulation/jvm_bridge/java_bridge && mvn package -DskipTests"
        )

    jar_path = _bridge_jar_path()
    assert jar_path is not None
    cmd = ["java", *(java_opts or []), "-jar", str(jar_path)]

    payload_str = json.dumps(inputs, default=_decimal_default, ensure_ascii=False)

    import time
    started = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            input=payload_str,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise JavaBridgeError(f"Java Bridge timeout ({timeout_sec}s)") from exc
    elapsed = time.monotonic() - started

    if proc.returncode != 0:
        return JavaResult(
            ok=False,
            payload={"error": "non_zero_exit", "exit_code": proc.returncode},
            stderr=proc.stderr,
            elapsed_sec=elapsed,
        )

    try:
        parsed = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError as exc:
        return JavaResult(
            ok=False,
            payload={"error": "invalid_json", "raw_stdout": proc.stdout[:2000]},
            stderr=proc.stderr,
            elapsed_sec=elapsed,
        )

    return JavaResult(ok=True, payload=parsed, stderr=proc.stderr, elapsed_sec=elapsed)


def _run_via_http(inputs: dict[str, Any], *, timeout_sec: float) -> JavaResult:
    """slab-design Spring Boot (8080) 의 admin/test-design endpoint 로 단일 주문 설계 호출.

    inputs.order 의 (cmpCd, orgCd, orderNo) 를 추출 → POST → SDSlabEntity + history 반환.
    H2 시드 데이터가 자동 활용되므로 fixture mock 불필요.
    """
    import time
    import urllib.error
    import urllib.request

    order = inputs.get("order", {}) or {}
    cmp_cd = order.get("cmpCd", "01")
    org_cd = order.get("orgCd", "K")
    order_no = order.get("orderNo")
    if not order_no:
        return JavaResult(
            ok=False,
            payload={"error": "missing_orderNo", "hint": "inputs.order.orderNo 필요"},
            stderr="",
            elapsed_sec=0.0,
        )

    body = json.dumps(
        {"cmpCd": cmp_cd, "orgCd": org_cd, "orderNo": order_no},
        default=_decimal_default,
        ensure_ascii=False,
    ).encode("utf-8")

    req = urllib.request.Request(
        f"{_SLAB_DESIGN_HTTP_URL}/api/sd/admin/test-design",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8")
            elapsed = time.monotonic() - started
    except urllib.error.HTTPError as exc:
        return JavaResult(
            ok=False,
            payload={"error": "http_error", "status": exc.code, "detail": str(exc)},
            stderr="",
            elapsed_sec=time.monotonic() - started,
        )
    except urllib.error.URLError as exc:
        return JavaResult(
            ok=False,
            payload={"error": "url_error", "detail": str(exc)},
            stderr="",
            elapsed_sec=time.monotonic() - started,
        )

    try:
        parsed = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        return JavaResult(
            ok=False,
            payload={"error": "invalid_json", "raw": raw[:2000]},
            stderr="",
            elapsed_sec=elapsed,
        )

    # admin/test-design 의 응답 형태:
    # {"status": "success"|"skipped"|"error", "slab": {...}|null,
    #  "counts": {"history_added": N, "result_added": N}, "history": [...]}
    # → JavaResult.payload 형태로 normalize
    slab = parsed.get("slab")
    history = parsed.get("history", [])
    last_step = history[-1] if history else {}
    design_status = "OK" if parsed.get("status") == "success" else "FAIL"
    error_code = last_step.get("errorCode") if last_step else None

    normalized = {
        "ok": parsed.get("status") in ("success", "skipped"),
        "slab": slab if slab else last_step.get("snapshot"),  # snapshot 은 string JSON
        "designStatus": design_status,
        "errorCode": error_code,
        "history": history,
        "counts": parsed.get("counts", {}),
        "_source": "slab-design-http",
    }

    return JavaResult(
        ok=True,  # HTTP 200 = bridge 호출 자체는 성공 (algorithm 결과는 normalized 안에서 판단)
        payload=normalized,
        stderr="",
        elapsed_sec=elapsed,
    )
