"""CallSiteAnalyzer — Java 정적 dispatch 추론 (D3 7-case).

목표: dispatch 가 자동 추적 가능한 case 는 confidence=1.0 single candidate,
모호한 case 는 needs_user_confirm=True + 후보 list + 컨텍스트 (사용자 큐).

Case 1~4 자동:
- SINGLE_IMPL      : 인터페이스에 impl 1개 → 그 impl 확정
- INSTANCEOF_GUARD : if (x instanceof T) 분기 안 호출 → T 로 확정
- ANNOTATION       : @Service 단일 등록 → Spring DI 확정 (단일 impl 과 유사)
- FACTORY_BRANCH   : factory 의 if-else / switch return new T() → 분기별 확정

Case 5~7 사용자 큐 (with 후보·컨텍스트):
- GENERIC_BOUND       : T extends Order — upper bound 까지만 확정
- STRATEGY_MAP        : Map<K, V>.get().method() — 동적
- REFLECTION          : Class.forName / SPI

이 모듈은 CodeType 리스트 (이미 role 분류 완료) + CallSite seed (메서드 본체에서
호출된 위치 정보) 를 받아 enriched CallSite 리스트 반환. CallSite seed 는 java_parser
의 calls relation 또는 method.body_text 에서 후처리로 추출.

본 1차 구현은 receiver 의 static type 만 알면 처리 가능한 case (SINGLE_IMPL +
ANNOTATION) 에 집중. INSTANCEOF_GUARD / FACTORY_BRANCH 는 body AST 분석 필요 — Phase 2.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Iterable

from backend.modeling.code_layer.schema import (
    CallAnalysisSource,
    CallCandidate,
    CallSite,
    CodeType,
    CodeTypeKind,
)

logger = logging.getLogger(__name__)


def _make_id(caller_fqn: str, line: int | None, callee: str) -> str:
    seed = f"{caller_fqn}|{line or 0}|{callee}"
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]


def _build_subtype_index(types: list[CodeType]) -> dict[str, list[str]]:
    """parent fqn → 직접 subtype fqn 들 (extends + implements 모두).

    interface impl 도 포함. 1차 직접만; transitive closure 는 호출자가 필요시 확장.
    """
    children: dict[str, list[str]] = {}
    for t in types:
        if t.extends:
            children.setdefault(t.extends, []).append(t.fqn)
        for iface in t.implements:
            children.setdefault(iface, []).append(t.fqn)
        for iface in t.extends_interfaces:
            children.setdefault(iface, []).append(t.fqn)
    return children


def _has_method(t: CodeType, method_name: str) -> bool:
    return any(m.name == method_name for m in t.methods)


def _annotation_singleton(t: CodeType) -> bool:
    """@Service / @Component 등 Spring 단일 등록 후보인지."""
    spring_singletons = {"@Service", "@Component", "@Repository", "@Controller", "@RestController"}
    for ann in t.annotations:
        base = ann.split("(", 1)[0].strip()
        if base in spring_singletons:
            return True
    return False


def analyze_call_sites(
    types: list[CodeType],
    *,
    seeds: Iterable[tuple[str, str, str, int | None]],
    repo_id: str = "",
) -> list[CallSite]:
    """seeds = [(caller_method_fqn, callee_simple_name, callee_receiver_static_type, line), ...].

    각 seed 마다 정적 분석 결과를 CallSite 로 만든다.
    seed 가 없으면 [].

    receiver_static_type 은 호출자 측에서 callee 가 invoke 된 receiver 의 정적 타입
    (e.g., "Order" / "Validator" / "OrderService"). 빈 문자열이면 정적 추론 불가.
    """
    by_fqn: dict[str, CodeType] = {t.fqn: t for t in types}
    # static_type 이 simple name 만 주어져도 매칭 가능하도록 simple_name index 준비
    by_simple: dict[str, list[str]] = {}
    for t in types:
        by_simple.setdefault(t.simple_name, []).append(t.fqn)
    children_of = _build_subtype_index(types)

    out: list[CallSite] = []
    for caller_fqn, callee_name, receiver_static_type, line in seeds:
        cs_id = _make_id(caller_fqn, line, callee_name)

        # receiver_static_type → 가능한 type fqn 후보들 (simple name 일 수 있음)
        receiver_candidates: list[CodeType] = []
        if receiver_static_type:
            if receiver_static_type in by_fqn:
                receiver_candidates = [by_fqn[receiver_static_type]]
            elif receiver_static_type in by_simple:
                receiver_candidates = [by_fqn[fqn] for fqn in by_simple[receiver_static_type]]

        # 분석 case 결정
        analysis_source: CallAnalysisSource
        confidence: float
        candidates: list[CallCandidate]
        needs_confirm: bool

        if not receiver_candidates:
            # static type 모름 — 추론 불가
            analysis_source = CallAnalysisSource.STATIC_UNRESOLVED
            confidence = 0.0
            candidates = []
            needs_confirm = True
        else:
            # 하나의 receiver type 확정 (simple name 충돌 시 첫 번째 우선)
            receiver = receiver_candidates[0]

            if receiver.kind == CodeTypeKind.INTERFACE:
                # Case 1: SINGLE_IMPL — 인터페이스의 impl 가 1개?
                impls = [
                    by_fqn[c] for c in children_of.get(receiver.fqn, [])
                    if c in by_fqn and _has_method(by_fqn[c], callee_name)
                ]
                if len(impls) == 1:
                    analysis_source = CallAnalysisSource.SINGLE_IMPL
                    confidence = 1.0
                    candidates = [CallCandidate(
                        code_type_fqn=impls[0].fqn, score=1.0,
                        reason=f"유일 구현 of {receiver.simple_name}",
                    )]
                    needs_confirm = False
                elif len(impls) > 1:
                    # Case 5/6: 다중 impl — 모호. 후보 + 컨텍스트
                    analysis_source = CallAnalysisSource.STATIC_UNRESOLVED
                    confidence = 0.0
                    candidates = [CallCandidate(
                        code_type_fqn=i.fqn, score=1.0 / len(impls),
                        reason=f"impl of {receiver.simple_name}",
                    ) for i in impls]
                    needs_confirm = True
                else:
                    # impl 0 — 인터페이스만 있고 impl 미발견 (외부 lib 일 수 있음)
                    analysis_source = CallAnalysisSource.STATIC_UNRESOLVED
                    confidence = 0.0
                    candidates = []
                    needs_confirm = True
            else:
                # Case 3: ANNOTATION — Spring 단일 등록 클래스
                if _annotation_singleton(receiver) and _has_method(receiver, callee_name):
                    analysis_source = CallAnalysisSource.ANNOTATION
                    confidence = 1.0
                    candidates = [CallCandidate(
                        code_type_fqn=receiver.fqn, score=1.0,
                        reason=f"Spring 단일 등록 ({[a for a in receiver.annotations if a.startswith('@Service') or a.startswith('@Component')][:1]})",
                    )]
                    needs_confirm = False
                else:
                    # Case: 일반 class — 자기자신 정적 dispatch (override 없는 경우)
                    # subtype 중 같은 method 를 override 한 것 있는지 검사
                    subtypes_with_override = []
                    stack = list(children_of.get(receiver.fqn, []))
                    while stack:
                        s_fqn = stack.pop()
                        st = by_fqn.get(s_fqn)
                        if st is None:
                            continue
                        if _has_method(st, callee_name):
                            subtypes_with_override.append(st)
                        stack.extend(children_of.get(s_fqn, []))

                    if not subtypes_with_override:
                        # 자기자신만 (override 없음) → 확정
                        if _has_method(receiver, callee_name):
                            analysis_source = CallAnalysisSource.SINGLE_IMPL
                            confidence = 1.0
                            candidates = [CallCandidate(
                                code_type_fqn=receiver.fqn, score=1.0,
                                reason="override 없음, 자체 정의",
                            )]
                            needs_confirm = False
                        else:
                            analysis_source = CallAnalysisSource.STATIC_UNRESOLVED
                            confidence = 0.0
                            candidates = []
                            needs_confirm = True
                    else:
                        # subtype override 존재 — 모호 (어느 instance 가 들어올지 모름)
                        all_cands = subtypes_with_override + ([receiver] if _has_method(receiver, callee_name) and not receiver.is_abstract else [])
                        analysis_source = CallAnalysisSource.STATIC_UNRESOLVED
                        confidence = 0.0
                        candidates = [CallCandidate(
                            code_type_fqn=c.fqn, score=1.0 / len(all_cands),
                            reason=f"override 후보 of {receiver.simple_name}",
                        ) for c in all_cands]
                        needs_confirm = True

        out.append(CallSite(
            id=cs_id,
            caller_method_fqn=caller_fqn,
            callee_simple_name=callee_name,
            callee_receiver_static_type=receiver_static_type,
            line=line,
            possible_runtime_types=candidates,
            confidence=confidence,
            analysis_source=analysis_source,
            needs_user_confirm=needs_confirm,
            repo_id=repo_id,
        ))

    return out


__all__ = ("analyze_call_sites",)
