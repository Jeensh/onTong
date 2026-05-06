"""OD-11-B4 : Spring analyzer 스캐폴드.

실제 Spring 분석 (DI / AOP / HTTP / Events / Scheduled / Profile) 은 OD-11-B5 에서
개별 구현. B4 에서는 파이프라인에 꽂힐 자리 — `SpringAnalyzer` Protocol + 6 개 기본
구현체의 import 경로 — 만 확보한다.
"""

from __future__ import annotations

from backend.modeling.code_analysis.spring import (
    AopAnalyzer,
    DIAnalyzer,
    EventsAnalyzer,
    HttpAnalyzer,
    ProfileAnalyzer,
    ScheduledAnalyzer,
    SpringAnalyzer,
)


def test_six_analyzer_stubs_are_importable() -> None:
    for cls in (
        DIAnalyzer, AopAnalyzer, HttpAnalyzer,
        EventsAnalyzer, ScheduledAnalyzer, ProfileAnalyzer,
    ):
        inst = cls()
        assert isinstance(inst, SpringAnalyzer)


def test_analyzer_stubs_return_empty_parse_result_shape() -> None:
    """스캐폴드 단계 — 실제 분석 없이 빈 (entities, relations) 튜플을 반환하면 충분."""
    analyzer = DIAnalyzer()
    entities, relations = analyzer.analyze(tree=None, content=b"", file_path="x.java", pkg_name=None)
    assert entities == []
    assert relations == []
