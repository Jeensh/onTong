# ADR-003: Two-Engine Substrate — Integrator + Proposal Lifecycle + Revision Pointer

작성일: 2026-05-13
상태: 확정 (사용자 결정, 2026-05-13)
선행: ADR-001 (Python twin), ADR-002 (Two-Engine + plugin)
관련: ADR-004 (Schema Layer), ADR-005 (Recommendation LLM defenses)
관련 결정: D1 (Two-Engine 채택), D7 (ADR-003 작성)

## 컨텍스트

ADR-002 가 두 engine 의 분리 결정:
- Verification Engine (deterministic, Anchored Twin Synthesizer)
- Recommendation Engine (LLM-based)

두 engine 의 통합 mechanism 미명세:
1. Recommendation 이 proposal 을 어떻게 발행하는가?
2. Proposal 의 lifecycle (draft / reviewed / accepted / rejected / merged)?
3. Verification 이 Recommendation 의 proposal 을 어떻게 oracle 로 활용?
4. 변경 추적 (revision pointer) 의 model?

Round 2 종합 (`SYNTHESIS-ROUND2.html`) 의 Integrator 가 이 통합 layer 의 이름. 본 ADR 이 정식 명세.

## 결정

**Two-engine Substrate = Integrator + Proposal lifecycle + Revision pointer.**

### 1. Integrator role

Integrator 는 두 engine 의 message bus + state manager:
- Recommendation → Integrator: proposal 발행
- Integrator → Verification: oracle 호출 ("이 proposal 의 twin 결과는?")
- Verification → Integrator: oracle response
- Integrator → Recommendation: oracle 결과 기반 proposal refinement
- Integrator → User: proposal review request

```python
# core/integrator/integrator.py

class Integrator:
    def __init__(self, verification: VerificationEngine, recommendation: RecommendationEngine):
        ...

    def submit_proposal(self, prop: Proposal) -> ProposalId:
        """Recommendation Engine 에서 호출. Proposal 을 PROPOSED state 로 등록."""
        ...

    def request_oracle(self, prop_id: ProposalId, fixture_subset: list[FixtureRef]) -> OracleResult:
        """Verification Engine 호출 (해당 fixture 의 twin 실행)."""
        ...

    def refine_proposal(self, prop_id: ProposalId, refinement: ProposalRefinement) -> None:
        """Recommendation 의 self-correction 또는 user feedback 반영."""
        ...

    def review_proposal(self, prop_id: ProposalId, user_decision: ReviewDecision) -> None:
        """User 의 accept / reject / change_request 반영."""
        ...

    def merge_proposal(self, prop_id: ProposalId) -> RevisionId:
        """Accepted proposal 의 실제 적용 (ontology + code + schema 변경)."""
        ...
```

### 2. Proposal lifecycle

```
State machine:
  DRAFT ─→ PROPOSED ─→ ORACLED ─→ REVIEWED ─→ ACCEPTED ─→ MERGED
                              │              │             │
                              ↓              ↓             ↓
                          (refine loop)  (rejected)   (apply revision)
                                              │
                                              ↓
                                          REJECTED (terminal)
```

States:
- **DRAFT**: Recommendation Engine 내부 작업 중
- **PROPOSED**: Integrator 에 등록, oracle 미실행
- **ORACLED**: Verification 의 oracle 결과 첨부, user review 가능 상태
- **REVIEWED**: User 의 feedback 수신, change_request 시 refine loop (→ DRAFT 또는 PROPOSED 재진입)
- **ACCEPTED**: User 가 최종 승인, merge 대기
- **MERGED**: Revision pointer 발급, 변경 실 적용 (terminal)
- **REJECTED**: 폐기 (terminal)

상태 전이는 Integrator 가 enforce. 잘못된 전이는 reject.

### 3. Proposal data model

```python
# core/integrator/proposal.py

class Proposal(BaseModel):
    id: ProposalId
    type: Literal["schema_change", "code_change", "ontology_evolution"]
    description: str  # natural language summary from Recommendation

    # 변경 candidate (type 별 schema)
    schema_diff: SchemaDiff | None       # for schema_change (ADR-004)
    code_diff: CodeDiff | None           # for code_change
    ontology_diff: OntologyDiff | None   # for ontology_evolution

    # Oracle 결과 (state >= ORACLED)
    oracle_result: OracleResult | None

    # Lifecycle
    state: Literal["DRAFT", "PROPOSED", "ORACLED", "REVIEWED", "ACCEPTED", "MERGED", "REJECTED"]
    created_at: datetime
    last_updated_at: datetime
    history: list[ProposalEvent]

    # Metadata
    plugin: str  # 발행 plugin (e.g., "v2-slab-design", "broadleaf", "banking")
    user_feedback: list[UserFeedback]
```

### 4. Oracle protocol

Verification Engine 의 oracle 호출:

```python
# core/verification/oracle.py

class OracleRequest(BaseModel):
    proposal_id: ProposalId
    fixture_subset: list[FixtureRef]  # 어떤 fixture 로 검증?

    # 변경 simulate scope
    apply_schema_diff: SchemaDiff | None
    apply_code_diff: CodeDiff | None
    apply_ontology_diff: OntologyDiff | None

class OracleResult(BaseModel):
    proposal_id: ProposalId
    by_fixture: dict[FixtureRef, FixtureOracleResult]
    aggregate_status: Literal["PASS", "FAIL_BREAKING", "FAIL_DRIFT", "INCONCLUSIVE"]
    summary: str  # human readable

class FixtureOracleResult(BaseModel):
    fixture: FixtureRef
    java_baseline_output: Any   # pre-change twin
    python_proposal_output: Any  # post-change twin
    output_diff: OutputDiff
    trace_diff: TraceDiff  # ADR-002 의 trace diff mechanism
    status: Literal["PASS", "FAIL_OUTPUT", "FAIL_TRACE", "ERROR"]
```

Oracle 은 사용자 requirement R3 (동일 input → 동일 output), R4 (동일 처리 과정), R5 (수정 전후 비교) 의 결정자.

### 5. Revision pointer

Merge 된 proposal 은 revision pointer 생성:

```python
class Revision(BaseModel):
    id: RevisionId
    proposal: ProposalId

    # 변경 실 적용 위치
    ontology_revision: str    # ontology git tag / migration version
    code_revision: str        # source code git commit
    schema_revision: str      # DDL migration version (ADR-004)

    # Lineage
    parent_revision: RevisionId | None  # 이전 revision (chain)
    fixture_baseline: dict[FixtureRef, Any]  # post-change baseline (next proposal 의 oracle 비교 기준)

    created_at: datetime
    created_by: str  # user
```

Revision pointer 는 R5 (수정 전후 비교) 의 기준점. 모든 후속 proposal 의 oracle 이 latest revision 기준.

### 6. Concurrency + isolation

- 동일 plugin 의 multiple proposal 동시 가능 — 각자 independent oracle
- Merge 시 last-write-wins (timestamp 기반), conflict 시 user review 요청
- 여러 plugin 의 cross-plugin proposal (e.g., schema change affecting multiple systems) 는 phase 2

## State 전이의 events

```python
class ProposalEvent(BaseModel):
    timestamp: datetime
    from_state: str
    to_state: str
    actor: Literal["recommendation_engine", "integrator", "verification_engine", "user"]
    notes: str
    artifacts: dict  # state 별 첨부 (oracle_result, user_feedback, ...)
```

매 state transition 의 audit log — proposal 의 history 가 full reproducibility.

## 결과 / 영향

- Verification ↔ Recommendation 의 통신 protocol 명세 → 두 engine 의 independent 개발 가능
- Proposal lifecycle 의 명시적 state machine → audit trail
- Revision pointer 의 lineage → R5 (수정 전후 비교) 의 mechanism
- Oracle 의 PASS/FAIL_BREAKING/FAIL_DRIFT/INCONCLUSIVE 4-tier → Recommendation 의 self-correction 신호

## Honest limits

- Cross-plugin proposal 의 saga (e.g., schema change affecting v2 + Broadleaf) 는 본 ADR scope 외 — phase 2
- Proposal 의 race condition (동시 merge) 은 simple last-write-wins, 정교한 conflict resolution 미포함
- Revision pointer 의 distributed scenario (multi-developer) 는 git 기반 conflict resolution 에 위임

## 참조

- DECISIONS-CONFIRMED.md (D1, D7)
- ADR-001 (Python twin)
- ADR-002 (Two-Engine + plugin)
- ADR-004 (Schema Layer — schema_diff 의 정의)
- ADR-005 (Recommendation Engine LLM defenses — proposal 의 source)
- `SYNTHESIS-ROUND2.html` (Integrator 의 motivation)
- 사용자 R3-R5 (verification requirements)
