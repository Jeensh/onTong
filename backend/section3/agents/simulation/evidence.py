"""신뢰도 source tracking — 각 payload field 가 어디서 왔는지·얼마나 확신하는지 추적.

사용자 요구 (2026-05-23): "온톨로지 근거 몇 프로? AI 분석 결과 몇 프로? 추측 기반인지,
실제 사실 근거인지 표시. hover 하면 근거가 보이게."

Evidence kinds:
  - ontology      : modeling 시스템의 ontology API 응답 (가장 강함)
  - business_rule : ontology business_rules.statement 직접 인용
  - seed_data     : domain_data (seed table rows) — 실제 row 값
  - java_anchor   : anchor_binding 으로 attach 된 Java method body line
  - inference     : LLM / 규칙 기반 추론 (중간)
  - propagation   : 비례식 propagation_rules (예: 단중 ∝ 두께×폭×길이×density)
  - assumption    : 명시적 가정 (예: density=7.85 default) — 가장 약함

confidence 는 0.0~1.0. ontology 직접 인용 ≥ 0.9, seed 실측 ≥ 0.85,
propagation 0.6~0.8, inference 0.4~0.7, assumption ≤ 0.5.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Literal

EvidenceKind = Literal[
    "ontology", "business_rule", "seed_data", "java_anchor",
    "inference", "propagation", "assumption",
]


@dataclass
class Evidence:
    """한 field 의 근거 1건. hover tooltip 으로 사용자에게 노출."""
    kind: EvidenceKind
    summary: str                       # 한 줄 요약 ("ontology business_term.confirmed_plant_cd")
    confidence: float = 0.5            # 0.0~1.0
    source_ref: str | None = None      # fqn / table.column / file:line 등
    detail: str | None = None          # 긴 본문 (hover 클릭 시 펼침)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvidencedField:
    """field 값 + 근거 list. field name 은 부모 dict 의 key."""
    value: Any
    evidence: list[Evidence] = field(default_factory=list)
    # 평균 confidence — 표시용 (factor: ontology 가 inference 보다 weight ↑)
    @property
    def aggregate_confidence(self) -> float:
        if not self.evidence:
            return 0.0
        WEIGHT = {
            "ontology": 1.0, "business_rule": 1.0, "seed_data": 0.9,
            "java_anchor": 0.85, "propagation": 0.75,
            "inference": 0.55, "assumption": 0.4,
        }
        total_w = sum(WEIGHT.get(e.kind, 0.5) for e in self.evidence)
        if total_w == 0:
            return 0.0
        weighted = sum(e.confidence * WEIGHT.get(e.kind, 0.5) for e in self.evidence)
        return weighted / total_w

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "evidence": [e.to_dict() for e in self.evidence],
            "confidence": round(self.aggregate_confidence, 3),
        }


@dataclass
class EvidenceBundle:
    """결과 payload 전체의 신뢰도 요약 + field 별 근거 — UI 가 chip + tooltip 으로 표시."""
    # field path → Evidence list 매핑 (예: "slabWgt": [...], "_target_change.before": [...])
    fields: dict[str, list[Evidence]] = field(default_factory=dict)
    # 카드 전체 요약 (overall): kind 별 비율 (ontology %, inference %, ...)
    overall_summary: dict[str, float] | None = None
    # 카드 전체 평균 confidence
    overall_confidence: float = 0.0

    def add(self, field_path: str, ev: Evidence | list[Evidence]) -> None:
        if isinstance(ev, Evidence):
            self.fields.setdefault(field_path, []).append(ev)
        else:
            self.fields.setdefault(field_path, []).extend(ev)

    def finalize(self) -> None:
        """overall_summary + overall_confidence 계산. payload 직렬화 직전 호출.

        사용자 요구 (2026-05-23): 근거패널에 'ontology' + 'AI 추론' 2종만 표시.
        내부 7종 evidence kind 를 2종으로 collapse.
        """
        # 내부 kind → 사용자 표시 카테고리 매핑
        # business_rule / seed_data 도 ontology 등록 데이터의 일부 → ontology
        # java_anchor 는 더 이상 발행하지 않음 (사용자 요구) → fallback 으로 ontology
        # propagation / assumption / inference → AI 추론 (자체 계산·추측)
        GROUP = {
            "ontology": "ontology", "business_rule": "ontology",
            "seed_data": "ontology", "java_anchor": "ontology",
            "propagation": "inference", "inference": "inference",
            "assumption": "inference",
        }
        if not self.fields:
            self.overall_confidence = 0.0
            self.overall_summary = {"ontology": 0.0, "inference": 0.0}
            return
        group_count: dict[str, int] = {"ontology": 0, "inference": 0}
        total_count = 0
        total_weighted_conf = 0.0
        WEIGHT = {
            "ontology": 1.0, "business_rule": 1.0, "seed_data": 0.9,
            "java_anchor": 0.85, "propagation": 0.75,
            "inference": 0.55, "assumption": 0.4,
        }
        total_w = 0.0
        for evs in self.fields.values():
            for e in evs:
                grp = GROUP.get(e.kind, "inference")
                group_count[grp] = group_count.get(grp, 0) + 1
                total_count += 1
                w = WEIGHT.get(e.kind, 0.5)
                total_weighted_conf += e.confidence * w
                total_w += w
        self.overall_summary = {
            k: round(v / total_count * 100, 1) for k, v in group_count.items()
        }
        self.overall_confidence = round(total_weighted_conf / total_w, 3) if total_w else 0.0

    def to_dict(self) -> dict[str, Any]:
        self.finalize()
        return {
            "overall_confidence": self.overall_confidence,
            "source_breakdown_pct": self.overall_summary,
            "fields": {
                k: [e.to_dict() for e in v] for k, v in self.fields.items()
            },
        }


# 흔히 쓰이는 evidence factory ────────────────────────────────────────────────

def ontology_term(term_fqn: str, label: str | None = None, detail: str | None = None) -> Evidence:
    return Evidence(
        kind="ontology",
        summary=f"ontology business_term: {label or term_fqn}",
        confidence=0.95,
        source_ref=term_fqn,
        detail=detail,
    )


def ontology_action(action_fqn: str, label: str | None = None) -> Evidence:
    return Evidence(
        kind="ontology",
        summary=f"ontology action: {label or action_fqn}",
        confidence=0.92,
        source_ref=action_fqn,
    )


def business_rule(rule_fqn: str, statement: str, severity: str = "soft") -> Evidence:
    return Evidence(
        kind="business_rule",
        summary=f"business rule [{severity}]: {rule_fqn}",
        confidence=0.95 if severity == "hard" else 0.85,
        source_ref=rule_fqn,
        detail=statement,
    )


def seed_data(table: str, column: str, value: Any, row_pk: str = "") -> Evidence:
    return Evidence(
        kind="seed_data",
        summary=f"seed {table}.{column} = {value}" + (f" (pk={row_pk})" if row_pk else ""),
        confidence=0.88,
        source_ref=f"{table}.{column}",
    )


def java_anchor(method_fqn: str, line: int | None, locator: str | None = None) -> Evidence:
    loc_suffix = f":{line}" if line is not None else ""
    return Evidence(
        kind="java_anchor",
        summary=f"Java anchor: {method_fqn.split('.')[-1].split('(')[0]}{loc_suffix}",
        confidence=0.85,
        source_ref=f"{method_fqn}{loc_suffix}",
        detail=locator,
    )


def inference(reason: str, confidence: float = 0.55) -> Evidence:
    return Evidence(
        kind="inference",
        summary=f"AI 추론: {reason[:60]}",
        confidence=confidence,
        detail=reason,
    )


def propagation(formula: str, base_fields: list[str], confidence: float = 0.75) -> Evidence:
    return Evidence(
        kind="propagation",
        summary=f"전파 규칙: {formula}",
        confidence=confidence,
        source_ref=", ".join(base_fields),
        detail=f"공식: {formula} (의존 필드: {', '.join(base_fields)})",
    )


def assumption(text: str, confidence: float = 0.4) -> Evidence:
    return Evidence(
        kind="assumption",
        summary=f"가정: {text[:60]}",
        confidence=confidence,
        detail=text,
    )
