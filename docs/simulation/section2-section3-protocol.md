# Section 2 ↔ Section 3 통신 프로토콜 명세

> **대상**: Claude Code
> **목적**: Section 2 (Modeling) ↔ Section 3 (Simulation) 간의 통신 인터페이스를 명세한다.
> **위치**: `backend/shared/contracts/ontology.py`
> **버전**: v1.0

---

## 0. 설계 원칙

1. **단일 진입점**: Section 3은 단 하나의 엔드포인트(`POST /api/modeling/ontology/query`)로 Section 2를 호출
2. **Intent 기반 분기**: 5종의 intent로 요청 종류 구분
3. **Status 기반 응답**: 5종의 status로 응답 상태 구분
4. **타입 안전성**: 모든 요청/응답은 Pydantic 모델로 검증
5. **확장 가능**: parameters/result는 dict로 두어 Agent별 자유 확장

---

## 1. Pydantic 계약 (`backend/shared/contracts/ontology.py`)

```python
"""
Section 2 (Modeling) ↔ Section 3 (Simulation) API Contract
"""
from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Dict, Any
from enum import Enum
from datetime import datetime


class Intent(str, Enum):
    """요청 의도 (Section 2가 어떤 핸들러를 사용할지 결정)"""
    QUERY = "query"                          # 단순 데이터 조회
    SIMULATE = "simulate"                    # 파라미터 기반 계산 실행
    IMPACT_ANALYSIS = "impact_analysis"      # 변경 사항의 파급 효과 분석
    OPTIMIZE = "optimize"                    # 최적값 찾기
    EXPLAIN = "explain"                      # 원인 / 규칙 / 위치 설명


class Status(str, Enum):
    """응답 상태"""
    SUCCESS = "success"                      # 완전 답변
    PARTIAL = "partial"                      # 부분 답변
    NEED_MORE_INFO = "need_more_info"        # HITL 트리거
    UNSUPPORTED = "unsupported"              # 지원 안 함
    ERROR = "error"                          # 실행 오류


# ─────────────────────────────────────────────────────────────
# 요청 모델
# ─────────────────────────────────────────────────────────────

class OntologyRequest(BaseModel):
    """Section 3 → Section 2 요청"""
    
    request_id: str = Field(..., description="요청 추적용 고유 ID (UUID 권장)")
    
    intent: Intent = Field(
        ..., 
        description="요청 의도. 5종 중 하나"
    )
    
    natural_language: Optional[str] = Field(
        None,
        description="원본 사용자 발화 (자연어 디버깅/로깅용)"
    )
    
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="구조화된 파라미터. intent별로 스키마 다름"
    )
    
    context: Optional[Dict[str, Any]] = Field(
        None,
        description="대화 히스토리, 온톨로지 버전 등 컨텍스트"
    )
    
    expected_output: Optional[Dict[str, Any]] = Field(
        None,
        description="원하는 응답 형식 힌트 (예: visualization type)"
    )


# ─────────────────────────────────────────────────────────────
# Missing Info (HITL 트리거)
# ─────────────────────────────────────────────────────────────

class MissingInfoQuestion(BaseModel):
    """추가 정보 요청 — UI 자동 생성용"""
    
    field: str = Field(..., description="채워야 할 필드 키")
    question: str = Field(..., description="사용자에게 표시할 질문")
    input_type: Literal[
        "select", "multi_select", "text", "number",
        "date_range", "structured_form"
    ] = Field(..., description="UI 입력 타입")
    options: Optional[List[Dict[str, str]]] = Field(
        None, 
        description="select/multi_select 시 선택지"
    )
    default_value: Optional[Any] = None


class MissingInfo(BaseModel):
    """need_more_info 응답에 첨부됨"""
    
    questions: List[MissingInfoQuestion]
    reason: str = Field(..., description="왜 추가 정보가 필요한지 설명")


# ─────────────────────────────────────────────────────────────
# 응답 모델
# ─────────────────────────────────────────────────────────────

class VisualizationHint(BaseModel):
    """결과 시각화 타입 힌트"""
    
    type: Literal[
        "table", "chart_line", "chart_bar", "chart_pie",
        "graph_highlight", "impact_tree", "3d_slab",
        "before_after_comparison", "text"
    ]
    payload: Dict[str, Any] = Field(default_factory=dict)
    alternative_views: List[str] = Field(default_factory=list)


class OntologyResponse(BaseModel):
    """Section 2 → Section 3 응답"""
    
    request_id: str
    
    status: Status
    
    confidence: float = Field(
        1.0, 
        ge=0.0, le=1.0,
        description="응답 신뢰도 (0~1)"
    )
    
    result: Optional[Dict[str, Any]] = Field(
        None,
        description="status가 success/partial일 때 결과 데이터"
    )
    
    missing_info: Optional[MissingInfo] = Field(
        None,
        description="status가 need_more_info일 때 추가 질문"
    )
    
    follow_up: Optional[Dict[str, Any]] = Field(
        None,
        description="후속 질문 제안 등"
    )
    
    execution_trace: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="실행 단계 추적 (디버깅용)"
    )
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ─────────────────────────────────────────────────────────────
# Result 데이터 형식 (intent별)
# ─────────────────────────────────────────────────────────────
# 아래는 result 필드 안에 들어가는 권장 구조 (참고용)

class ImpactAnalysisResult(BaseModel):
    """intent=impact_analysis일 때의 result"""
    summary: str
    direct_impact: Dict[str, Any]      # {methods: [], tables: [], steps: []}
    indirect_impact: Dict[str, Any]    # {downstream_methods: [], affected_steps: []}
    risk_level: Literal["HIGH", "MEDIUM", "LOW"]
    risk_factors: List[str] = Field(default_factory=list)
    visualization: Optional[VisualizationHint] = None


class TestDataResult(BaseModel):
    """intent=simulate (test_data 모드)일 때의 result"""
    test_cases: List[Dict[str, Any]]
    code_skeleton: Optional[str] = None
    data_dependencies: List[str] = Field(default_factory=list)


class LocatorResult(BaseModel):
    """intent=explain일 때의 result"""
    matched_terms: List[Dict[str, Any]]
    process_locations: List[Dict[str, Any]]
    source_locations: List[Dict[str, Any]]
    data_locations: List[Dict[str, Any]]
    related_terms: List[Dict[str, Any]] = Field(default_factory=list)
    visualization: Optional[VisualizationHint] = None
```

---

## 2. Intent별 요청/응답 예시

### 2-1. Intent: `impact_analysis`

**요청 (Section 3 → Section 2):**
```json
{
  "request_id": "req-20260418-001",
  "intent": "impact_analysis",
  "parameters": {
    "target": {
      "kind": "table",
      "id": "TB_C40_050SC070"
    },
    "modification": "add_column",
    "change_kind": "data"
  }
}
```

**응답:**
```json
{
  "request_id": "req-20260418-001",
  "status": "success",
  "confidence": 0.95,
  "result": {
    "summary": "TB_C40_050SC070 변경 시 메서드 10개, Step 2개 영향",
    "direct_impact": {
      "methods": [
        {"class": "SlabDesignService", "name": "calculatePrimaryWidthRange", "line": 142}
      ],
      "affected_steps": [
        {"step_number": 2, "korean_name": "1차 폭범위 계산", "via_standard": "SC070"}
      ]
    },
    "indirect_impact": {
      "downstream_methods": ["calculateSecondaryWidthRange", "calculateTargetWidth"]
    },
    "risk_level": "HIGH",
    "visualization": {
      "type": "impact_tree",
      "payload": {"root": "TB_C40_050SC070"}
    }
  }
}
```

### 2-2. Intent: `simulate` (테스트 데이터 생성)

**요청:**
```json
{
  "request_id": "req-20260418-002",
  "intent": "simulate",
  "parameters": {
    "target": {"kind": "step", "id": "step_2"},
    "test_data_request": {
      "case_types": ["normal", "boundary", "error"],
      "count": 5
    }
  }
}
```

**응답:**
```json
{
  "request_id": "req-20260418-002",
  "status": "success",
  "result": {
    "test_cases": [
      {
        "case_id": "TC001",
        "case_type": "normal",
        "input": {"target_width": 1040, "target_thickness": 250},
        "expected_output": {"feasible": true, "primary_width_range": [960, 1110]}
      }
    ],
    "code_skeleton": "@Test\nvoid test_primaryWidth_normal() { ... }",
    "data_dependencies": ["TB_C40_050SC030", "TB_C40_050SC070"]
  }
}
```

### 2-3. Intent: `explain` (위치 파악)

**요청:**
```json
{
  "request_id": "req-20260418-003",
  "intent": "explain",
  "natural_language": "Edging 로직 어디 있어?",
  "parameters": {
    "scope": ["source", "table", "process"]
  }
}
```

**응답:**
```json
{
  "request_id": "req-20260418-003",
  "status": "success",
  "result": {
    "matched_terms": [
      {"id": "term_edging", "korean": "Edging", "english": "Edging"}
    ],
    "process_locations": [
      {"step_number": 2, "korean_name": "1차 폭범위 계산"},
      {"step_number": 13, "korean_name": "Target폭 재계산 (3pass)"}
    ],
    "source_locations": [
      {"class": "SlabDesignService", "method": "calculatePrimaryWidthRange",
       "file_path": ".../SlabDesignService.java", "line": 142}
    ],
    "data_locations": [
      {"table": "TB_C40_050SC070", "standard_code": "SC070"}
    ]
  }
}
```

### 2-4. Status: `need_more_info` (HITL)

**응답 예시 (정보 부족 시):**
```json
{
  "request_id": "req-20260418-004",
  "status": "need_more_info",
  "missing_info": {
    "reason": "변경 대상 종류가 명시되지 않았습니다",
    "questions": [
      {
        "field": "target.kind",
        "question": "변경 대상이 무엇인가요?",
        "input_type": "select",
        "options": [
          {"id": "table", "label": "테이블"},
          {"id": "method", "label": "메서드"},
          {"id": "class", "label": "클래스"}
        ]
      }
    ]
  }
}
```

이때 Section 3 프론트엔드는 `input_type`만 보고 자동으로 UI 폼을 생성한다.

---

## 3. 에러 처리

### 3-1. Status별 처리 가이드

| status | Section 3 측 처리 |
|--------|-------------------|
| `success` | result 표시 |
| `partial` | result 표시 + "추가로 ~한 정보가 더 필요합니다" 안내 |
| `need_more_info` | missing_info 기반 폼 자동 생성 → 재요청 |
| `unsupported` | "이 요청은 현재 지원되지 않습니다" 안내 + Wiki 링크 제공 |
| `error` | "오류가 발생했습니다" 안내 + 재시도 버튼 |

### 3-2. HTTP 상태 코드

- `200`: 모든 status (응답 본문에서 status 필드 확인)
- `400`: 요청 형식 오류 (Pydantic 검증 실패)
- `500`: 서버 내부 오류

---

## 4. 엔드포인트 정리

### Section 2 (Modeling) 제공

```
POST /api/modeling/ontology/query
GET  /api/modeling/ontology/graph/stats
GET  /api/modeling/ontology/term/search?q=<keyword>&limit=<n>
```

### Section 3 (Simulation) 제공

```
POST /api/simulation/agents/impact      ← Agent 1
POST /api/simulation/agents/test-data   ← Agent 2
POST /api/simulation/agents/locator     ← Agent 3
```

### 호출 흐름

```
[User UI]
   ↓ Agent 1 폼 제출
[Section 3: /api/simulation/agents/impact]
   ↓ OntologyClient.query()
[Section 2: /api/modeling/ontology/query]
   ↓ Cypher 쿼리
[Neo4j]
```

---

## 5. 환경변수

```bash
# Section 3에서 Section 2 호출용
MODELING_API_URL=http://localhost:8001  # Section 2 base URL

# Section 3 개발 시 Section 2 미완성 상태 대응
USE_MOCK_ONTOLOGY=false  # true이면 Mock 응답 사용
```

---

## 6. 테스트 (필수 통과)

`backend/shared/contracts/test_ontology.py`:

```python
import pytest
from backend.shared.contracts.ontology import (
    OntologyRequest, OntologyResponse, Intent, Status, MissingInfo
)


def test_request_validation():
    """요청 모델 검증"""
    req = OntologyRequest(
        request_id="test-001",
        intent=Intent.IMPACT_ANALYSIS,
        parameters={"target": {"kind": "table", "id": "TB_C40_050SC070"}}
    )
    assert req.intent == "impact_analysis"


def test_response_serialization():
    """응답 직렬화"""
    resp = OntologyResponse(
        request_id="test-001",
        status=Status.SUCCESS,
        result={"summary": "test"}
    )
    json_str = resp.model_dump_json()
    assert "success" in json_str


def test_missing_info_structure():
    """HITL 응답 구조"""
    resp = OntologyResponse(
        request_id="test-002",
        status=Status.NEED_MORE_INFO,
        missing_info=MissingInfo(
            reason="대상 명시 필요",
            questions=[{
                "field": "target.kind",
                "question": "무엇을 변경하시나요?",
                "input_type": "select",
                "options": [{"id": "table", "label": "테이블"}]
            }]
        )
    )
    assert resp.missing_info.questions[0].input_type == "select"
```

---

## 7. 작업 순서

1. `backend/shared/contracts/ontology.py` 작성 (이 문서의 코드 그대로)
2. `backend/shared/contracts/test_ontology.py` 작성 + 실행
3. Section 2팀이 OntologyResponse 형식으로 응답 구현
4. Section 3팀이 OntologyRequest 형식으로 요청 구현
5. 통합 테스트 (curl 또는 pytest)

---

## 8. 주의사항

- **이 파일은 두 섹션의 공식 계약**이므로, 수정 시 양쪽 팀의 합의가 필요하다.
- **Pydantic v2 문법** 사용 (`model_dump()` 등).
- **`status`와 `intent` Enum 값을 임의로 추가하지 말 것**. 추가하려면 본 문서를 먼저 갱신.
- **Section 3 → Section 2 호출은 비동기**이므로 `httpx.AsyncClient` 사용.
- **timeout은 30초**로 설정 (jQAssistant 분석 등 무거운 작업 대응).
