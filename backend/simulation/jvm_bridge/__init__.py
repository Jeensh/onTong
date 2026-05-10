"""Java ↔ Python differential testing bridge.

slab-design 자바 시스템을 **무수정** 으로 호출하기 위한 별도 Maven 프로젝트
(`java_bridge/`) + Python subprocess 래퍼.

핵심 디자인:
- slab-design 의 `SdDesigner.design()` 만 호출하고 Oracle/Kafka 의존성은 Spring
  `@Primary @Bean` override 로 mock 으로 swap.
- stdin: JSON `{"order": {...}, "fixtures": {...}}` → stdout: JSON `{"slab": {...}}`.
- subprocess timeout 30s, 1회 실행당 ~ 200ms (JVM cold start 후).

사용:
    from backend.simulation.jvm_bridge import run_java, run_differential

    java_result = run_java({"order": {...}})  # Java SdDesigner 실행
    diff = run_differential(order_dict)        # Java + Python 동시 실행 + 비교
"""

from backend.simulation.jvm_bridge.runner import (
    JavaBridgeError,
    is_bridge_available,
    run_java,
)
from backend.simulation.jvm_bridge.differential import (
    DifferentialResult,
    run_differential,
)

__all__ = [
    "JavaBridgeError",
    "DifferentialResult",
    "is_bridge_available",
    "run_java",
    "run_differential",
]
