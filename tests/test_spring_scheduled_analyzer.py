"""OD-11-B5-5 : Spring ScheduledAnalyzer — `@Scheduled` → `scheduled_task` 엔티티.

감지 대상:
  - 메서드 레벨 `@Scheduled` 애너테이션.
  - 각 `@Scheduled` 메서드마다 `scheduled_task` 엔티티 emit.
    - qn = `<method FQN>#scheduled` (메서드 엔티티와 충돌 회피. `@Bean` 의 `#bean` 패턴과 동일).
    - `attributes.method_fqn` = 메서드 FQN (bean 클래스.메서드).
  - 속성 (있을 때만 기록):
    - `fixed_rate`, `fixed_delay`, `initial_delay` (ms 리터럴 또는 placeholder 문자열)
    - `cron` : cron 표현식
    - `zone` : 타임존 문자열
  - `fixedRateString` / `fixedDelayString` / `initialDelayString` 은 String variant 로,
    동일 키 (`fixed_rate` / `fixed_delay` / `initial_delay`) 에 placeholder 문자열 그대로 저장.

엣지: 없음. 이 analyzer 는 entity-only.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from backend.modeling.code_analysis.java_parser import JavaParser
from backend.modeling.code_analysis.parser_protocol import EntityKinds
from backend.modeling.code_analysis.spring import (
    DIAnalyzer,
    ScheduledAnalyzer,
)

_LANG = Language(tsjava.language())


def _parse(src: str):
    p = Parser(_LANG)
    return p.parse(src.encode())


def _run(src: str, pkg_name: str | None = "com.x", file_path: str = "X.java"):
    tree = _parse(src)
    a = ScheduledAnalyzer()
    return a.analyze(tree=tree, content=src.encode(), file_path=file_path, pkg_name=pkg_name)


# ---------------------------------------------------------------------------
# Basic detection
# ---------------------------------------------------------------------------
def test_scheduled_method_produces_entity() -> None:
    src = """
public class JobRunner {
    @Scheduled(fixedRate = 1000)
    public void tick() {}
}
"""
    entities, relations = _run(src)
    tasks = [e for e in entities if e.kind == EntityKinds.SCHEDULED_TASK]
    assert len(tasks) == 1
    t = tasks[0]
    assert t.qualified_name == "com.x.JobRunner.tick#scheduled"
    assert t.name == "tick"
    assert t.attributes["method_fqn"] == "com.x.JobRunner.tick"
    assert t.attributes["fixed_rate"] == "1000"
    assert relations == []


def test_plain_method_without_scheduled_ignored() -> None:
    src = """
public class NotAJob {
    public void doWork() {}
}
"""
    entities, _ = _run(src)
    assert not any(e.kind == EntityKinds.SCHEDULED_TASK for e in entities)


# ---------------------------------------------------------------------------
# Attribute variants — ms literals
# ---------------------------------------------------------------------------
def test_fixed_delay_recorded() -> None:
    src = """
public class J {
    @Scheduled(fixedDelay = 5000)
    public void t() {}
}
"""
    entities, _ = _run(src)
    t = next(e for e in entities if e.kind == EntityKinds.SCHEDULED_TASK)
    assert t.attributes["fixed_delay"] == "5000"
    assert "fixed_rate" not in t.attributes


def test_initial_delay_recorded() -> None:
    src = """
public class J {
    @Scheduled(fixedRate = 1000, initialDelay = 500)
    public void t() {}
}
"""
    entities, _ = _run(src)
    t = next(e for e in entities if e.kind == EntityKinds.SCHEDULED_TASK)
    assert t.attributes["fixed_rate"] == "1000"
    assert t.attributes["initial_delay"] == "500"


# ---------------------------------------------------------------------------
# cron + zone
# ---------------------------------------------------------------------------
def test_cron_expression_recorded() -> None:
    src = """
public class J {
    @Scheduled(cron = "0 0 * * * *")
    public void t() {}
}
"""
    entities, _ = _run(src)
    t = next(e for e in entities if e.kind == EntityKinds.SCHEDULED_TASK)
    assert t.attributes["cron"] == "0 0 * * * *"
    assert "fixed_rate" not in t.attributes
    assert "fixed_delay" not in t.attributes


def test_cron_with_zone_recorded() -> None:
    src = """
public class J {
    @Scheduled(cron = "0 15 10 * * ?", zone = "Asia/Seoul")
    public void t() {}
}
"""
    entities, _ = _run(src)
    t = next(e for e in entities if e.kind == EntityKinds.SCHEDULED_TASK)
    assert t.attributes["cron"] == "0 15 10 * * ?"
    assert t.attributes["zone"] == "Asia/Seoul"


# ---------------------------------------------------------------------------
# String variants → unified keys
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("attr_key, expected_key, value", [
    ("fixedRateString", "fixed_rate", "${app.rate}"),
    ("fixedDelayString", "fixed_delay", "${app.delay}"),
    ("initialDelayString", "initial_delay", "${app.initial}"),
])
def test_string_variants_unified(attr_key: str, expected_key: str, value: str) -> None:
    src = f"""
public class J {{
    @Scheduled({attr_key} = "{value}")
    public void t() {{}}
}}
"""
    entities, _ = _run(src)
    t = next(e for e in entities if e.kind == EntityKinds.SCHEDULED_TASK)
    assert t.attributes[expected_key] == value


def test_placeholder_with_cron() -> None:
    src = """
public class J {
    @Scheduled(cron = "${app.cron}")
    public void t() {}
}
"""
    entities, _ = _run(src)
    t = next(e for e in entities if e.kind == EntityKinds.SCHEDULED_TASK)
    assert t.attributes["cron"] == "${app.cron}"


# ---------------------------------------------------------------------------
# Multiple @Scheduled methods
# ---------------------------------------------------------------------------
def test_multiple_scheduled_methods_emit_separate_entities() -> None:
    src = """
public class J {
    @Scheduled(fixedRate = 1000)
    public void a() {}

    @Scheduled(cron = "0 0 * * * *")
    public void b() {}

    public void notScheduled() {}
}
"""
    entities, _ = _run(src)
    tasks = [e for e in entities if e.kind == EntityKinds.SCHEDULED_TASK]
    assert len(tasks) == 2
    qns = {t.qualified_name for t in tasks}
    assert qns == {"com.x.J.a#scheduled", "com.x.J.b#scheduled"}


def test_no_attributes_produces_entity_with_no_trigger_keys() -> None:
    """`@Scheduled` 그 자체는 유효하지 않지만 방어적으로 entity 는 emit, 트리거 속성은 없음."""
    src = """
public class J {
    @Scheduled
    public void t() {}
}
"""
    entities, _ = _run(src)
    tasks = [e for e in entities if e.kind == EntityKinds.SCHEDULED_TASK]
    assert len(tasks) == 1
    attrs = tasks[0].attributes
    # method_fqn 은 항상 기록
    assert attrs["method_fqn"] == "com.x.J.t"
    # 트리거 키는 전부 없음
    for k in ("fixed_rate", "fixed_delay", "initial_delay", "cron", "zone"):
        assert k not in attrs


# ---------------------------------------------------------------------------
# Integration with JavaParser
# ---------------------------------------------------------------------------
def test_java_parser_accepts_scheduled_analyzer() -> None:
    src = """
package com.x;
public class J {
    @Scheduled(fixedRate = 1000)
    public void tick() {}
}
"""
    parser = JavaParser(spring_analyzers=[ScheduledAnalyzer()])
    result = parser.parse_file(Path("J.java"), src)
    kinds = {e.kind for e in result.entities}
    assert EntityKinds.SCHEDULED_TASK in kinds


def test_java_parser_with_di_and_scheduled() -> None:
    src = """
package com.x;
@Component
public class Worker {
    @Autowired
    private OrderService svc;

    @Scheduled(cron = "0 0 * * * *")
    public void hourly() {}
}
"""
    parser = JavaParser(spring_analyzers=[DIAnalyzer(), ScheduledAnalyzer()])
    result = parser.parse_file(Path("Worker.java"), src)
    kinds = {e.kind for e in result.entities}
    assert EntityKinds.SPRING_BEAN in kinds       # DIAnalyzer
    assert EntityKinds.SCHEDULED_TASK in kinds    # ScheduledAnalyzer


def test_java_parser_without_scheduled_analyzer_no_tasks() -> None:
    src = """
package com.x;
public class J {
    @Scheduled(fixedRate = 1000)
    public void tick() {}
}
"""
    result = JavaParser().parse_file(Path("J.java"), src)
    assert not any(e.kind == EntityKinds.SCHEDULED_TASK for e in result.entities)
