"""Class.role / Method.role 자동 분류 (D2=A 정합).

룰 우선순위 (annotation > 이름 패턴 > signature). 자신 없는 케이스는 UNKNOWN
유지 → 사용자 큐 (Q2'=C). LLM 보조는 별도 hook (이 모듈 외).

목표: 5000+ class 환경에서 80% 이상 자동 분류, 나머지만 사람 검토.

분류 결과를 입력 CodeType 리스트에 적용해 새 인스턴스 반환 (immutable).
"""
from __future__ import annotations

import logging
import re

from backend.modeling.code_layer.schema import (
    CodeMethod,
    CodeType,
    CodeTypeKind,
    CodeTypeRole,
    MethodRole,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Class role 분류
# ---------------------------------------------------------------------------
# annotation → role 매핑
_CLASS_ANNOTATION_ROLE: dict[str, CodeTypeRole] = {
    # framework — Spring/JPA/Hibernate
    "@Configuration":  CodeTypeRole.FRAMEWORK,
    "@Aspect":         CodeTypeRole.FRAMEWORK,
    "@EnableJpaRepositories": CodeTypeRole.FRAMEWORK,
    "@SpringBootApplication": CodeTypeRole.FRAMEWORK,
    "@Bean":           CodeTypeRole.FRAMEWORK,
    "@ConfigurationProperties": CodeTypeRole.FRAMEWORK,
    "@ControllerAdvice": CodeTypeRole.FRAMEWORK,
    # infra — Repository / Mapper / DTO
    "@Repository":     CodeTypeRole.INFRA,
    "@Mapper":         CodeTypeRole.INFRA,    # MyBatis
    # domain — Service / Component / Entity / RestController
    "@Entity":         CodeTypeRole.DOMAIN,
    "@Service":        CodeTypeRole.DOMAIN,
    "@Component":      CodeTypeRole.DOMAIN,
    "@RestController": CodeTypeRole.DOMAIN,
    "@Controller":     CodeTypeRole.DOMAIN,
}

# 이름 패턴 (정규식)
# Jpo (JPA persistent object) + PK + slab-design 의 *Logic / *Wrapper 도 INFRA 후보
_INFRA_NAME_RE = re.compile(
    r"(.*Repository|.*Mapper|.*Dto|.*DTO|.*Util|.*Utils|.*Helper|.*Adapter|.*Converter"
    r"|.*Jpo|.*PK)$"
)
_FRAMEWORK_NAME_RE = re.compile(
    r"^(Abstract|Base)[A-Z]\w*|.*Configuration$|.*Config$|.*Aspect$|.*ExceptionHandler$"
    r"|.*Application$|.*Bootstrap$|.*EventListener$"
)
# slab-design 의 핵심 도메인 클래스 패턴 (Action / Designer / Driver / Service)
_DOMAIN_NAME_RE = re.compile(
    r".*Designer$|.*Driver$|.*Action$|.*Validator$|.*Classifier$"
    r"|.*Calculator$|.*Resolver$|.*Provider$|.*Service$|.*Logic$"
    r"|.*Entity$|.*Wrapper$|.*Extractor$"
)


def _classify_class_role(ct: CodeType) -> CodeTypeRole:
    name = ct.simple_name
    # 1. INFRA 이름 패턴 우선 — *Jpo / *PK / *Repository 등은 @Entity annotation 보다 강함
    #    (slab-design 컨벤션: Jpo = raw DB row → INFRA, *Entity = rich domain → DOMAIN)
    if _INFRA_NAME_RE.match(name):
        return CodeTypeRole.INFRA
    # 2. annotation
    for ann in ct.annotations:
        # @Service("...") 같은 경우 base 추출
        base = ann.split("(", 1)[0].strip()
        role = _CLASS_ANNOTATION_ROLE.get(base)
        if role is not None:
            return role
    # 3. 그 외 이름 패턴
    if _FRAMEWORK_NAME_RE.match(name):
        return CodeTypeRole.FRAMEWORK
    if _DOMAIN_NAME_RE.match(name):
        return CodeTypeRole.DOMAIN
    # 3. interface — capability 후보. 이름이 명백히 infra 가 아니면 domain.
    if ct.kind == CodeTypeKind.INTERFACE:
        return CodeTypeRole.DOMAIN
    # 4. abstract class 이름이 Abstract*/Base* 면 framework 후보 (위 _FRAMEWORK_NAME_RE 가 잡음).
    #    그 외 abstract class (예: abstract Order) 는 도메인 추상 — DOMAIN 처리.
    # 5. 일반 class / record / enum — DOMAIN
    if ct.kind in (CodeTypeKind.CLASS, CodeTypeKind.ABSTRACT_CLASS, CodeTypeKind.RECORD, CodeTypeKind.ENUM):
        return CodeTypeRole.DOMAIN
    return CodeTypeRole.UNKNOWN


# ---------------------------------------------------------------------------
# Method role 분류
# ---------------------------------------------------------------------------
_HELPER_NAME_RE = re.compile(
    r".*(Internal|Helper|Util|Validate)$|^_.*"
)
_ADAPTER_NAME_RE = re.compile(
    r"^(get|set|is|has|to|toString|toEntity|toDto|fromEntity|fromDto|equals|hashCode|builder)([A-Z].*)?$"
)


def _classify_method_role(method: CodeMethod, parent_role: CodeTypeRole) -> MethodRole:
    name = method.name

    # framework / infra 클래스의 메서드는 자동 ADAPTER (Action 매핑 면제)
    if parent_role in (CodeTypeRole.FRAMEWORK, CodeTypeRole.INFRA):
        return MethodRole.ADAPTER

    # 1. 단순 접근자 / 빌더
    if _ADAPTER_NAME_RE.match(name):
        return MethodRole.ADAPTER
    # 2. private + 짧은 이름 + helper 패턴 → HELPER
    if "private" in method.modifiers:
        if _HELPER_NAME_RE.match(name):
            return MethodRole.HELPER
        # private + 짧은 body → helper 후보
        if method.body_text and len(method.body_text.splitlines()) <= 8:
            return MethodRole.HELPER
        # private + 긴 body → BUSINESS 도 가능성, UNKNOWN 처리 (사용자 큐)
        return MethodRole.UNKNOWN
    # 3. constructor — adapter 로 (기본 build 동작)
    if method.is_constructor:
        return MethodRole.ADAPTER
    # 4. 그 외 — public/protected 비-getter → BUSINESS
    return MethodRole.BUSINESS


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def classify_roles(types: list[CodeType]) -> list[CodeType]:
    """입력 CodeType 리스트에 role 적용. 새 인스턴스 반환 (frozen=True 정합).

    분류 결과 통계는 logger 로 출력.
    """
    out: list[CodeType] = []
    class_counts: dict[str, int] = {}
    method_counts: dict[str, int] = {}

    for ct in types:
        cls_role = _classify_class_role(ct)
        class_counts[cls_role.value] = class_counts.get(cls_role.value, 0) + 1

        new_methods: list[CodeMethod] = []
        for m in ct.methods:
            m_role = _classify_method_role(m, cls_role)
            method_counts[m_role.value] = method_counts.get(m_role.value, 0) + 1
            new_methods.append(m.model_copy(update={"role": m_role}))

        out.append(ct.model_copy(update={"role": cls_role, "methods": new_methods}))

    logger.info(
        "classify_roles: classes %s / methods %s",
        class_counts, method_counts,
    )
    return out


__all__ = ("classify_roles",)
