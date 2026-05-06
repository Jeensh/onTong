"""call_resolver tests."""

from __future__ import annotations

from backend.modeling.code_analysis.call_resolver import resolve_calls
from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity, CodeRelation, EntityKinds, ParseResult,
)


def _cls(fqn: str, name: str) -> CodeEntity:
    return CodeEntity(
        kind=EntityKinds.CLASS, qualified_name=fqn, name=name,
        file_path=f"{name}.java", line_start=1, line_end=10,
        parent=None, attributes={},
    )


def _method(class_fqn: str, name: str) -> CodeEntity:
    return CodeEntity(
        kind=EntityKinds.METHOD, qualified_name=f"{class_fqn}.{name}", name=name,
        file_path=f"{class_fqn.rsplit('.',1)[-1]}.java", line_start=2, line_end=5,
        parent=class_fqn, attributes={},
    )


def _field(class_fqn: str, name: str, java_type: str) -> CodeEntity:
    return CodeEntity(
        kind=EntityKinds.FIELD,
        qualified_name=f"{class_fqn}.{name}", name=name,
        file_path=f"{class_fqn.rsplit('.',1)[-1]}.java", line_start=2, line_end=2,
        parent=class_fqn, attributes={"field_type": java_type},
    )


def test_field_type_lookup_resolves_call():
    """controller.service.method() pattern."""
    cls_svc = _cls("com.x.SvcA", "SvcA")
    method_svc = _method("com.x.SvcA", "doIt")
    cls_ctrl = _cls("com.x.CtrlA", "CtrlA")
    field_svc = _field("com.x.CtrlA", "svc", "SvcA")  # @Autowired SvcA svc
    method_ctrl = _method("com.x.CtrlA", "handle")
    # Call from CtrlA.handle to svc.doIt — parser writes target as "com.x.svc.doIt" 패턴
    rel = CodeRelation(
        kind="calls",
        source="com.x.CtrlA.handle",
        target="com.x.svc.doIt",  # unresolved
        file_path="CtrlA.java", line=3,
    )
    pr = ParseResult(
        entities=[cls_svc, method_svc, cls_ctrl, field_svc, method_ctrl],
        relations=[rel], file_path="multi.java", language="Java",
    )
    new_edges, stats = resolve_calls([pr])
    assert stats.total_calls == 1
    assert stats.newly_resolved == 1
    assert len(new_edges) == 1
    assert new_edges[0].source == "com.x.CtrlA.handle"
    assert new_edges[0].target == "com.x.SvcA.doIt"
    assert new_edges[0].attributes["resolution"] == "field_type_lookup"
    assert new_edges[0].attributes["original_target"] == "com.x.svc.doIt"


def test_already_resolved_call_no_op():
    cls = _cls("com.x.A", "A")
    m1 = _method("com.x.A", "m1")
    m2 = _method("com.x.A", "m2")
    rel = CodeRelation(kind="calls", source="com.x.A.m1", target="com.x.A.m2",
                       file_path="A.java", line=3)
    pr = ParseResult(entities=[cls, m1, m2], relations=[rel],
                     file_path="A.java", language="Java")
    new_edges, stats = resolve_calls([pr])
    assert stats.already_resolved == 1
    assert stats.newly_resolved == 0
    assert new_edges == []


def test_unresolvable_when_field_type_unknown():
    cls = _cls("com.x.A", "A")
    method = _method("com.x.A", "run")
    # 필드 타입의 클래스가 어디에도 없음
    field = _field("com.x.A", "external", "ExternalLib")
    rel = CodeRelation(kind="calls", source="com.x.A.run", target="com.x.external.invoke",
                       file_path="A.java", line=3)
    pr = ParseResult(entities=[cls, method, field], relations=[rel],
                     file_path="A.java", language="Java")
    _, stats = resolve_calls([pr])
    assert stats.still_unresolved == 1
    assert stats.newly_resolved == 0


def test_method_not_found_in_target_class_skipped():
    cls_svc = _cls("com.x.Svc", "Svc")
    # Svc 에는 doIt 없음
    cls_ctrl = _cls("com.x.Ctrl", "Ctrl")
    field = _field("com.x.Ctrl", "svc", "Svc")
    method_ctrl = _method("com.x.Ctrl", "h")
    rel = CodeRelation(kind="calls", source="com.x.Ctrl.h", target="com.x.svc.doIt",
                       file_path="Ctrl.java", line=3)
    pr = ParseResult(entities=[cls_svc, cls_ctrl, field, method_ctrl], relations=[rel],
                     file_path="multi.java", language="Java")
    _, stats = resolve_calls([pr])
    assert stats.still_unresolved == 1
    assert stats.newly_resolved == 0


def test_dedup_same_resolved_edge():
    cls_svc = _cls("com.x.Svc", "Svc")
    m_svc = _method("com.x.Svc", "go")
    cls_ctrl = _cls("com.x.Ctrl", "Ctrl")
    field = _field("com.x.Ctrl", "svc", "Svc")
    m_ctrl = _method("com.x.Ctrl", "h")
    # 같은 source → target 이 두 번 (다른 line)
    rel1 = CodeRelation(kind="calls", source="com.x.Ctrl.h", target="com.x.svc.go",
                        file_path="Ctrl.java", line=3)
    rel2 = CodeRelation(kind="calls", source="com.x.Ctrl.h", target="com.x.svc.go",
                        file_path="Ctrl.java", line=10)
    pr = ParseResult(entities=[cls_svc, m_svc, cls_ctrl, field, m_ctrl],
                     relations=[rel1, rel2], file_path="multi.java", language="Java")
    new_edges, stats = resolve_calls([pr])
    # 둘 다 resolved 시도, 중복 제거 → 1 edge
    assert stats.newly_resolved == 1
    assert len(new_edges) == 1
