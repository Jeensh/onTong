# Authoring 모드 확장 계획 (JPA Entity → JPA / Service / Action)

> 2026-05-13 합의. 현재 Authoring 백엔드는 JPO (JPA Entity) 만 지원하지만 설계 vision (Round 5 Step 13 §1) 은 JPO + Service + Action. 3 phase 로 격차 해소.

## 합의된 결정

| # | 항목 | 결정 |
|---|------|------|
| Q1 | Action method-level UX | **2-단계**: 좌측 트리에서 클래스 클릭 → MainPanel 메서드 리스트 → 메서드 클릭 → Action 추출 |
| Q2 | Service 범위 | **Single class first**: `@Service` 한 클래스만. Feature bundle (Service+Repo+DTO) 은 Phase D 별도 |
| Q3 | Internal naming | **`jpo` → `extracted` 리네임**. Phase B 에서 한 번에. in-flight session 은 어차피 깨지므로 미루지 않음 |
| Q4 | LLM tier | **Per-kind 차등**: Entity=STANDARD, Service=HARD (의존 그래프 추론), Action=STANDARD |
| Q5 | Auto-detect 모호 | POJO → Generic; `@Component` → Service 카테고리; Action 은 명시 선택만 (heuristic 은 Phase D) |

---

## 진행 상태 (2026-05-13)

| Phase | Status | Commit |
|-------|--------|--------|
| A — UI honesty | ✅ | `ee1b066` |
| 계획 문서 | ✅ | `c661387` |
| B-1 schema | ✅ | `d0c2f19` |
| B-2 dispatcher | ✅ | `d0c2f19` |
| B-3 prompt | ✅ | `d0c2f19` |
| B-4 API + SSE | ✅ | `f1c58fc` |
| B-5 TS types | ✅ | `23f4d14` |
| B-6 store rename | ⏸ pending | — |
| B-7 ExtractedView branch | ⏸ pending | — |
| B-8 disable downstream | ⏸ pending | — |
| B-9 SelectionBanner copy | ⏸ pending | — |

**Backend 준비 완료**: `/extract` 와 `/extract/stream` 엔드포인트가 `ExtractedClass` discriminated union 반환. @Entity 클래스는 그대로 JPO 추출, 외 클래스는 새 lightweight Generic 추출. LLM 까지 동작.

**Frontend 상태**: TS types 추가됨. 하지만 store 의 `jpo` 필드 + AuthoringMode 의 `s.jpo` 13곳 + downstream button gating (hypothesis 등) 미완. 현재 빌드 통과하지만 사용자가 non-@Entity 클래스 선택 시 cast 실패로 runtime error 발생 가능 — B-6/B-7/B-8 까지 가야 안전.

**다음 세션 첫 작업**: B-6. 다음 옵션 중 결정 필요:
- (a) Full rename `jpo → extracted` in store + AuthoringMode, backend replay `r.current.jpo` 는 translation layer 로 흡수 (`extracted: r.current.jpo`)
- (b) 타입만 `ExtractedClass | null` 로 바꾸고 변수명은 `jpo` 유지 (안전하지만 semantic mismatch)

Q3 합의는 (a) 이지만 backend replay 의존성 발견했으므로 재확인 권장.

---

## Phase A ✅ (완료, commit `ee1b066`)

사용자 텍스트 6곳 정리 (JPO → JPA Entity), roadmap 안내 추가. 백엔드 무변경.

---

## Phase B — Generic Java fallback (1-2일)

**목표**: `@Entity` 없는 Java 클래스도 추출 가능. Lightweight schema, hypothesis 까지는 못 감 (Phase C 대기).

### B-1. Backend 스키마 신규 (반나절)

신규 파일 `backend/application/authoring/capabilities/generic_class_extractor.py`:

```python
class MethodSig(BaseModel):
    name: str
    params: list[str]            # "type name" pairs
    return_type: str
    javadoc_first_line: str | None
    annotations: list[str]       # @Transactional 등

class FieldSig(BaseModel):
    name: str
    java_type: str
    annotations: list[str]       # @Autowired 등

class ExtractedGenericClass(BaseModel):
    kind: Literal["generic"] = "generic"
    package: str
    class_name: str
    class_annotations: list[str]   # @Service / @Component / @Controller / 기타
    methods_outline: list[MethodSig]
    fields_outline: list[FieldSig]
    class_docstring: str | None
```

기존 `ExtractedJpo` 에 `kind: Literal["jpo"] = "jpo"` discriminator 추가.

### B-2. Backend 진입점 분기 (반나절)

`code_extractor.py` 의 `extract_jpo_from_file` 옆에 `extract_from_file` (dispatcher):

```python
async def extract_from_file(path, content, *, session_id, turn_no, event_pump=None):
    if "@Entity" in content or "@jakarta.persistence.Entity" in content:
        return await extract_jpo_from_file(...)
    return await extract_generic_from_file(...)
```

타입: `ExtractedClass = ExtractedJpo | ExtractedGenericClass` (Annotated discriminated union, `kind` field).

### B-3. Backend 프롬프트 (1-2시간)

신규 `backend/application/authoring/prompts/generic_extraction.md`:
- Service-aware: class-level annotations 강조 (`@Service`, `@Controller`, `@Component`)
- methods_outline 에 javadoc 1줄 + annotations 만 (body 제외 — 비용 절감)
- fields_outline 에 `@Autowired` field 강조 (의존성 단서)

### B-4. Backend API + SSE (1-2시간)

- `backend/api/authoring.py:338` — response_model 을 union 으로
- SSE event payload 에 `kind` 필드 propagation
- ExtractRequest 변경 없음

### B-5. Frontend TS types (1시간)

`frontend/src/lib/api/authoring.ts`:
```typescript
export interface ExtractedJpo { kind: "jpo"; package: string; ... }
export interface ExtractedGenericClass { kind: "generic"; package: string; ... }
export type ExtractedClass = ExtractedJpo | ExtractedGenericClass;
```

### B-6. Frontend store rename (2-3시간, HIGH RISK)

`frontend/src/lib/stores/authoring.ts` (또는 위치 어디든):
- `jpo: ExtractedJpo | null` → `extracted: ExtractedClass | null`
- 모든 selector / setter / persistence key 업데이트
- `AuthoringMode.tsx` 의 13곳 `s.jpo` 참조 → `s.extracted`
- `BUNDLED_HR_SPEC_JPO` 라는 상수명은 유지 (사용처는 변수 의미가 분명)

### B-7. Frontend ExtractedView 분기 (1-2시간)

```typescript
function ExtractedView({ extracted }: { extracted: ExtractedClass }) {
  if (extracted.kind === "jpo") return <JpoView jpo={extracted} />;
  return <GenericClassView c={extracted} />;
}
```

`GenericClassView`: class_name + 주요 annotations chip + methods.length / fields.length 요약.

### B-8. Downstream disable (1시간)

`kind === "generic"` 일 때:
- ② 가설 / ③ 인터뷰 / ⑤ 옵션 / ⑥ 갭 / ⑦ 패턴 / ⑨ Archive / ✓ Confirm 모두 disabled
- 툴팁: "Service / Action 의 hypothesis 는 Phase C 에서 지원. 현재 추출만 가능."

### B-9. SelectionBanner 메시지 확장 (30분)

"JPA Entity 클래스 (@Entity) 선택" → "Java 클래스 선택 (JPA Entity 권장 — Service / 일반 클래스는 추출만 지원)"

### Phase B 완료 기준

- @Entity 클래스 선택 → 기존 JPO pipeline 그대로 (regression 없음)
- @Service / @Controller / @Component 클래스 선택 → Generic 추출 성공, hypothesis 버튼 disabled
- POJO (어노테이션 없음) 클래스 선택 → Generic 추출 성공
- TS 빌드 + pytest 통과

---

## Phase C — Service / Action 완전 확장 (1-2주)

### C-1. 스키마 추가 (1-2일)

`backend/application/authoring/capabilities/`:
- `service_extractor.py` — `ExtractedService` 스키마
  - `kind: "service"`, dependencies (`@Autowired` 타입 리스트), exposed methods (public 메서드 시그니처), transaction_boundary (`@Transactional` method 리스트), rest_endpoints (`@RequestMapping` etc)
- `action_extractor.py` — `ExtractedAction` 스키마
  - `kind: "action"`, method-level: signature, callees (이 method 가 호출하는 method FQN list), side_effects (DB write / external call 추정), br_refs (관련 BR FQN), anchors_hint
- Union 확장: `ExtractedClass = ExtractedJpo | ExtractedGenericClass | ExtractedService | ExtractedAction`

### C-2. Hypothesis 분기 (2일)

`hypothesis.py` 내 dispatcher:
- ExtractedJpo → 기존 `EntityHypothesis` (도메인 entity)
- ExtractedService → 신규 `ServiceHypothesis` (책임 / 협력자 / 핵심 책임 1줄)
- ExtractedAction → 신규 `ActionHypothesis` (도메인 동사 / params 의미 / output 의미)

신규 프롬프트 2개:
- `service_hypothesis.md`
- `action_hypothesis.md`

ExtractedGenericClass 입력시 → "어떤 kind 로 해석할지 사용자 선택" UI prompt (Service / Action / Skip)

### C-3. Interview / Options / Gaps / Pattern / Archive / Naming (3-4일)

각 capability 의 prompt + dispatcher 분기. 가장 큰 변화는 interview:

| kind | 인터뷰 질문 종류 |
|------|------------------|
| Entity (기존) | PK 의미, 컬럼 도메인, lifecycle |
| Service | 책임 경계, transaction scope, event publish, dependency 의미 |
| Action | parameter 도메인 의미, side-effect 분류, BR 강제 시점, idempotency |

Options / Gaps / Pattern check 도 kind 별 비교 기준이 다름.

### C-4. UI kind 인식 (1-2일)

- Toolbar 좌측에 kind chip 추가 (auto-detected, override dropdown)
- ExtractedView, HypothesisView, OptionsView 모두 kind branch
- "다음 추천" 로직 — dependency-aware:
  - Entity 완료 후 → 그 entity 를 사용하는 Service 추천
  - Service 완료 후 → 그 Service 의 핵심 Action 추천
- Method-level Action selection: 클래스 선택 → MainPanel 메서드 리스트 → 메서드 클릭 → Action 추출 (Q1 결정)

### C-5. Testing + Docs (2일)

- pytest fixture: 각 kind 별 sample Java file (entity / service / controller / action method)
- `WORKFLOW_GUIDE.md` 업데이트 — 3 entity type 워크플로
- `demo_guide.md` 새 시나리오 3개

---

## Phase D (future, 미합의)

- Service feature bundle (Service + Repo + DTO 묶음 추출)
- Action heuristic auto-detect (controller endpoint, @Transactional method)
- Cross-entity dependency graph view in Authoring panel

---

## 진행 순서 + 세션 budget

| Phase | 추정 공수 | 세션 수 |
|-------|----------|--------|
| A | 30분 | ✅ 1 (완료) |
| B | 1-2일 | 2-3 세션 |
| C-1 | 1-2일 | 2-3 세션 |
| C-2 | 2일 | 2 세션 |
| C-3 | 3-4일 | 3-4 세션 |
| C-4 | 1-2일 | 2 세션 |
| C-5 | 2일 | 2 세션 |

각 세션 끝에 commit + 이 문서 update.
