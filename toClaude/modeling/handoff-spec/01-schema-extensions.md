# 01 — Schema Extensions

> **목적**: 시뮬 에이전트가 동작하기 위해 부족한 스키마를 보강. 기존 DTO 보강 (BR / Action / BusinessTerm) + 신규 엔티티 (DesignGap / SimulationScenario) 정의.
>
> **적용 위치**: `backend/shared/contracts/ontology_query.py` 의 DTO + `backend/modeling/data/*` 의 storage 모델 + 마이그레이션.

---

## 0. 개관

| # | 변경 대상 | 종류 | 시뮬 에이전트가 사용하는 시점 |
|---|---|---|---|
| 1 | `BusinessRule` 보강 | 필드 3개 추가 | SimResult 의 BR 위반 판정 + violated_at_call backtrack |
| 2 | `Action` 보강 | 필드 2개 추가 | workflow → 하위 호출 그래프 traversal + PRIMARY 코드 위치 dispatch |
| 3 | `BusinessTerm.facets.default_value` | 필드 1개 추가 | 시뮬 fixture 생성 시 기본값 |
| 4 | `DesignGap` 신규 엔티티 | 신설 | design-gaps 36 항목 1급 객체화 + Phase E backlog |
| 5 | `SimulationScenario` 신규 엔티티 | 신설 | 시뮬 카탈로그 + Action↔scenario 연결 |

---

## 1. BusinessRule 보강

### 1.1 현재 (예상)

```python
class BusinessRuleDTO(BaseModel):
    fqn: str            # 예: "br.scm.slab.SlabResult.NoChemDeviation"
    name: str
    description: str
    severity: Literal["error", "warning", "info"]
    declared_on_term: str | None  # 적용 대상 BusinessTerm fqn
```

### 1.2 보강 후

```python
class IncidentRef(BaseModel):
    """운영 사고 history. P-2018-0098 등."""
    incident_id: str            # "P-2018-0098"
    occurred_at: str            # ISO date "2018-04-23"
    summary: str                # 한 줄 요약
    triggered_by: str | None    # 발생 원인 액션 fqn (있다면)
    fixed_at_commit: str | None # 수정 커밋 sha (있다면)


class BRViolationCallSite(BaseModel):
    """BR 가 위반 가능한 코드 호출 지점 — guard 가 막아주는 곳 + 막지 못하는 곳 모두."""
    caller_method_fqn: str      # 호출하는 메서드
    callee_method_fqn: str      # 호출되는 메서드
    line: int                   # 라인 번호
    is_guarded: bool            # True = 코드에 if/throw 가 있음, False = 잠재 위반
    guard_action_fqn: str | None  # guard 역할 Action (있다면)


class BusinessRuleDTO(BaseModel):
    fqn: str
    name: str
    description: str
    severity: Literal["error", "warning", "info"]
    declared_on_term: str | None

    # ★ 신규
    enforced_by: list[str] = []
    """이 BR 을 코드에서 enforce 하는 method fqn 목록.
    예: ["scm.SdSlabValidator.validateSlabResult"].
    시뮬 SIM_VERIFIED 판정 시 이 메서드들의 호출 결과를 검증."""

    violated_at_call: list[BRViolationCallSite] = []
    """이 BR 이 위반될 수 있는 call site 목록.
    is_guarded=True/False 모두 포함 — guard 누락 검출용 (Gap Inspector).
    Phase C 의 DG001~005 + Phase B 의 BR3 회의실에서 도출됨."""

    operational_history: list[IncidentRef] = []
    """이 BR 이 도입된 배경의 운영 사고 history.
    예: [P-2018-0098 (정XX 슬래브 폭 미달 사고), 2017 회의 결정].
    시뮬 explanation panel 에 노출."""
```

### 1.3 라이프사이클

| 단계 | 누가 채우는가 |
|---|---|
| `enforced_by` | **자동** — Action 매핑 시 `kind="guard"` 인 Action 을 collect. 사람이 정정 가능. |
| `violated_at_call` | **자동** — CallSiteAnalyzer 가 `enforced_by` 메서드 → 호출 그래프 역추적 + guard 미달 site 마킹. |
| `operational_history` | **수동** — 사람이 인터뷰/문서에서 채움 (Round 5/6 archive 가 source). |

### 1.4 design-gaps 와의 관계

- design-gap #18 (BR enforcement 추적) 는 본 보강으로 해소.
- design-gap #19 (위반 site 의 guard 누락 검출) 는 `is_guarded=False` flag 로 해소.

---

## 2. Action 보강

### 2.1 현재 (예상)

```python
class ActionParam(BaseModel):
    """Action 의 inputs / outputs 슬롯."""
    name: str                        # "order", "slab" 등
    type_fqn: str                    # CodeType fqn (예: "scm.order.Order")
    role: Literal["input", "output"]


class Realization(BaseModel):
    """Action 의 다형성 코드 구현 — Agent 1 검수 보강 (Realization 정의 누락)."""
    method_fqn: str                  # "scm.SdDesigner.runStep1"
    input_type_fqn: str | None       # 이 realization 이 받는 input runtime type
                                     # (다형성 dispatch — null 이면 모든 input 적용)
    confidence: float                # 0.0 ~ 1.0 (CallSiteAnalyzer 추정)
    is_primary: bool                 # PRIMARY realization 여부 (다른 것의 base)
    line_range: tuple[int, int] | None  # method body 의 시작/끝 라인
    drama_dna_kind: str | None       # 본 realization 이 표현하는 drama DNA 종류


class ActionDTO(BaseModel):
    fqn: str
    name: str
    kind: Literal["pure_function", "effectful", "workflow"]
    declared_on_term: str | None
    inputs: list[ActionParam] = []
    outputs: list[ActionParam] = []
    realizations: list[Realization] = []
    """다형성 — 같은 Action 의 다양한 코드 구현."""
    verification_level: VerificationLevel
```

### 2.2 보강 후

```python
class DelegationEdge(BaseModel):
    """workflow 가 호출하는 하위 Action 의 직접 edge."""
    callee_action_fqn: str
    invocation_count: int = 1   # 같은 callee 를 여러 번 호출하면 증가
    is_in_loop: bool = False    # 루프 안에서 호출되는가 (A-a 21-step 루프 등)
    optional: bool = False      # if 분기 안에서 조건부 호출인가


class ActionDTO(BaseModel):
    fqn: str
    name: str
    kind: Literal["pure_function", "effectful", "workflow"]
    declared_on_term: str | None
    inputs: list[ActionParam] = []
    outputs: list[ActionParam] = []
    realizations: list[Realization] = []
    verification_level: VerificationLevel

    # ★ 신규
    realizes: list[str] = []
    """이 Action 이 실현하는 PRIMARY Action fqn 목록 (대부분 0~1개).
    예: 'scm.workflow.PerSlabIteration' realizes 'scm.workflow.SDSlabEntity_step_1_to_8'.
    시뮬 시 PRIMARY Action 을 받았을 때 실제 dispatch 할 코드 위치 결정에 사용."""

    delegates_to: list[DelegationEdge] = []
    """workflow 가 직접 호출하는 하위 Action edge 목록.
    pure_function 은 [] 빈 리스트. workflow 만 채워짐.
    Phase C 의 21-step 루프 분석 시 21 개 step Action 이 여기 등장.
    시뮬 시 transitive call graph 빌드 + Java sandbox dispatch 순서 결정."""
```

### 2.3 라이프사이클

| 단계 | 누가 채우는가 |
|---|---|
| `realizes` | **반자동** — Authoring agent 가 PRIMARY 후보 추천 + 사람이 confirm. |
| `delegates_to` | **자동** — CallSiteAnalyzer 가 method body 의 호출을 추출 + Action fqn resolve. `is_in_loop` / `optional` 도 AST 분석으로 자동. |

### 2.4 시뮬 흐름과의 관계

- 시뮬 흐름 5 step 의 ① Ontology Query 단계에서 `delegates_to` 트리를 펼쳐 호출 순서를 결정.
- ③ Java dispatch sandbox 단계에서 `realizes`(PRIMARY ↔ realization) 매핑으로 input runtime type 에 맞는 코드 선택.

### 2.5 design-gaps 와의 관계

- design-gap #5 (Java dispatch sandbox) 의 dispatch 결정 입력 = `realizes`.
- design-gap #28 (workflow 호출 그래프 부재) = `delegates_to` 로 해소.

---

## 3. BusinessTerm.facets.default_value

### 3.1 현재 (예상)

```python
class TermFacets(BaseModel):
    unit: str | None = None
    range_min: float | None = None
    range_max: float | None = None
    enum: list[str] | None = None
```

### 3.2 보강 후

```python
class TermFacets(BaseModel):
    unit: str | None = None
    range_min: float | None = None
    range_max: float | None = None
    enum: list[str] | None = None

    # ★ 신규
    default_value: Any | None = None
    """시뮬 fixture 자동 생성 시 사용할 기본값.
    None 이면 사람이 명시적으로 채워야 함.
    예: 'scm.shared.atomic.thickness'.default_value = 220 (mm)."""
```

### 3.3 라이프사이클

- **수동** — 인터뷰 시 "이 atomic 의 일반적 운영 값" 으로 채움. Phase E backlog 의 보강 작업.

---

## 4. DesignGap 엔티티 (신규)

### 4.1 동기

`design-gaps-and-questions.md` 의 36 항목이 markdown 텍스트로만 존재. 시뮬 에이전트가 "현재 unmapped/uncertain 영역" 을 프로그램적으로 알고 explanation panel 에 노출하려면 1급 객체화 필요.

### 4.2 스키마

```python
class DesignGap(BaseModel):
    gap_id: int                         # 1~36 (Phase A 22 + B 5 + C 9)
    area: Literal[
        "anchor", "br", "action", "term",
        "verification", "scenario", "ux", "data", "infra"
    ]
    title: str                          # "SIM_VERIFIED 자동 결정"
    question: str                       # 길이 1~3 문장
    impact: str                         # 구체적 영향 (1~3 문장)
    candidate_resolution: str | None    # "D.3 에서 판정 정책 명세" 등
    severity: Literal["critical", "major", "minor"]
    status: Literal["open", "scheduled", "resolved", "wontfix"]
    scheduled_for: str | None           # "Phase E", "Phase D.3" 등
    related_term_fqns: list[str] = []   # 영향받는 term/action fqn (있다면)
    related_action_fqns: list[str] = []
    related_br_fqns: list[str] = []
    source_phase: Literal["A", "B", "C", "D", "E"]
    introduced_at: str                  # ISO date "2026-05-09"
```

### 4.3 라이프사이클

- **자동 + 수동** — Phase A/B/C 진행 중 발견된 의문이 markdown 에 추가됨. Phase E 일괄 결정 시 status / scheduled_for 갱신.

### 4.4 사용처

- 시뮬 에이전트의 explanation panel 에서 "이 결과는 design-gap #X 영향 받음" 알림.
- API 보강 endpoint `/api/ontology/design-gaps` (`02-ontology-api-additions.md` 참조).

---

## 5. SimulationScenario 엔티티 (신규)

### 5.1 동기

시뮬 에이전트의 카탈로그 — 어떤 시나리오로 어떤 Action 을 검증할지. ChangeSpec 입력 + scenario_fixture 가 1:N 관계가 될 수 있어 시나리오는 별도 엔티티.

### 5.2 스키마

```python
class SimulationScenario(BaseModel):
    scenario_id: str                    # "SC-2018-Slab-Width-Underflow"
    kind: Literal[
        "regression",       # 운영 사고 재현
        "boundary",         # 경계값 테스트 (range_min/max)
        "drama",            # drama DNA 시연용
        "integration",      # 21-step end-to-end
        "br_violation",     # 특정 BR 위반 유도
    ]
    name: str
    description: str
    target_action_fqn: str              # 시나리오가 검증하려는 PRIMARY Action
    expected_brs: list[str] = []        # 통과해야 할 BR fqn 목록
    expected_anchors: list[str] = []    # 통과해야 할 AnchorBinding marker
    inputs: dict[str, Any]              # action_fqn 의 inputs 슬롯 → 값
    expected_outputs: dict[str, Any] | None  # 알면 채움 (None = 자유)
    origin: Literal["incident", "interview", "synthetic"]
    incident_ref: IncidentRef | None    # origin="incident" 인 경우 운영 사고 참조
    introduced_at: str                  # ISO date
```

### 5.3 라이프사이클

| 출처 | 누가 채우는가 |
|---|---|
| `kind="regression"` (P-2018-0098 등) | **수동** — 운영 사고 backtrack 시 등록 |
| `kind="boundary"` | **자동** — atomic.facets.range_min/max 에서 boundary case 자동 생성 |
| `kind="drama"` | **수동** — drama DNA 6종 (Round 5/6 archive 의 도메인 전문가 인용) |
| `kind="integration"` | **자동** — 21-step 의 representative happy path 자동 생성 |
| `kind="br_violation"` | **자동** — BR 의 enforced_by 역방향으로 위반 입력 자동 생성 |

### 5.4 사용처

- 시뮬 에이전트의 scenario picker UI.
- `/api/simulation/runs` 의 `scenario_id` 입력 (`03-simulation-api-spec.md` 참조).
- VerificationLevel 진급 (DRAFT → BODY_ANCHORED → SIM_VERIFIED) 의 input 으로 사용.

---

## 6. Migration 가이드 요약

| 단계 | 작업 |
|---|---|
| 1 | `backend/shared/contracts/ontology_query.py` 의 BusinessRuleDTO / ActionDTO / TermFacets 보강 |
| 2 | `DesignGap` / `SimulationScenario` 신규 DTO 추가 (같은 파일) |
| 3 | storage 의 BR/Action/BusinessTerm 컬럼 추가 (optional 컬럼, default empty list) |
| 4 | DesignGap / SimulationScenario 신규 테이블 추가 |
| 5 | 기존 데이터 default 채우기 (`enforced_by=[]`, `delegates_to=[]` 등 빈 리스트) |
| 6 | DesignGap 36 항목 seed (`design-gaps-and-questions.md` → DB) |
| 7 | SimulationScenario seed (운영 사고 7건 + 21-step happy path 1건) |

### 호환성

- 기존 endpoint 의 응답에 새 필드가 추가됨 — **클라이언트는 무시 가능** (default empty list).
- 신규 endpoint 는 별도 추가 — 기존 동작 변경 없음.
- 마이그레이션 1회 — DesignGap / SimulationScenario 테이블 신설 + BR / Action / BusinessTerm 컬럼 추가.

---

마지막 업데이트: 2026-05-10
