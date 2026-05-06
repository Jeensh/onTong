# OD-11 방향 전환 계획 (Direction Pivot)

> 작성: 2026-04-19
> 결정권자: 사용자
> 영향 범위: Section 2 전체 재설계
> 선행 문서: `toClaude/modeling/HANDOFF.md`, `CHANGES.md`, `TODO.md`

---

## 요약 한 줄

**매뉴얼 1차 → 레거시 코드 1차.** 온톨로지는 Java/Spring 소스와 업무처리기준서를 **메서드 단위로 매핑한 결과물**이며, Section 2는 그 매핑을 사람이 만들고 검증할 수 있는 **모델링 툴**이다. 3대 기능(영향도/역매핑/테스트 생성)이 이 매핑 위에서 동작한다.

---

## 1. 피벗 배경

OD-1 ~ OD-10까지는 "공장 암묵지(SOP) → LLM → Ontology YAML → Neo4j 트리" 라는 **매뉴얼 1차 흐름**으로 설계돼 있었다. 사용자 검토 결과 이 방향으로는 팀의 실제 목적을 달성할 수 없음이 확인됐다.

**진짜 출발점**:
- 레거시 시스템이 10년 유지보수됐다
- 최초에는 업무처리기준서(SOP)에 맞춰 만들어졌지만, 그 이후의 변경은 코드에만 반영되고 기준서에는 안 남았다
- 따라서 **현재 진실의 원천은 코드**이고, 기준서는 부족분을 채워야 할 부차적 참조다

**OD-10 정리가 착오였다**: 당시 "매뉴얼 1차 방향에 맞게" 깔끔하게 정리한다는 명분으로 `code_analysis/`, `mapping/`, `change/`, `query/`, `simulation/`, `approval/`, `git_connector.py` 등을 전부 삭제했다. 그런데 이들이 사실 **지금 새로 피벗한 방향(코드 1차)에 정확히 부합하는 인프라**였다. 복원 필요. (아직 커밋 안 됐음 : `git restore` 가능 상태)

---

## 2. 이전 방향 vs 새 방향 비교

| 항목 | 이전 (OD-1~10) | 새 방향 (OD-11~) |
|------|---------------|-----------------|
| 1차 소스 | 매뉴얼 마크다운 | **Java/Spring 레거시 코드** |
| 기준서 역할 | 온톨로지의 원재료 | 코드 매핑 검증용 참조 (사람이 보완 작성) |
| 온톨로지 생성 | LLM이 매뉴얼 → YAML | 파서가 코드 → 초안 + 사람이 매핑 검증/보완 |
| 매핑 단위 | Process 수준 | **메서드 단위** (+ 필요 시 필드/어노테이션) |
| 표준 참조 | SCOR + ISA-95 표준 트리 | **회사 실제 코드 구조** (표준 트리는 보조 레퍼런스) |
| 목적 산출물 | 자체 완결 Ontology YAML | 코드 ↔ 비즈니스 개념 매핑 그래프 |
| 3대 소비자 | WhatIf / WhyTrace / Diagnostic 에이전트 | **Impact / Reverse Lookup / Test Generation** |
| Primary Layer 의미 | 매뉴얼에서 파생된 공식/룰 | 코드에서 파생된 엔티티 + 사람이 단 비즈니스 매핑 |

---

## 3. 최종 목적 (재정의)

**10년간 코드에만 쌓인 변경을 되찾고, 비즈니스 관점에서 시스템을 안전하게 바꿀 수 있게 하는 것.**

구체적으로:
- **신규 개발자가 오자마자** "이 함수가 뭘 하는지, 누가 쓰는지, 왜 이렇게 돼 있는지"를 비즈니스 용어로 읽을 수 있어야 함
- **현업이 요구하는 변경사항**을 정확한 코드 위치로 꽂을 수 있어야 함
- **코드를 바꾸기 전에** 그 변경이 어디까지 파급되는지 알 수 있어야 함
- **변경 후** 그 영향 범위만 자동으로 테스트 데이터 생성 + 실행이 돼야 함

---

## 4. 3대 기능 요구 (Section 3에서 실행, Section 2는 이를 떠받치는 스키마 설계)

### 기능 1. Impact Analysis (영향도)
> 특정 값/소스가 바뀌었을 때 어떤 기능들이 연관돼 있고 어떻게 바뀌는지

- 입력: 메서드 qualified name 또는 필드/컬럼 이름
- 출력: BFS 그래프 탐색으로 연관된 메서드/엔드포인트/배치/스케줄 목록 + 비즈니스 개념 역매핑
- 알고리즘은 **결정적(deterministic)** 이어야 함. LLM은 term resolution 단에서만 허용.

### 기능 2. Reverse Lookup (역매핑)
> 비즈니스 용어로 된 요청사항 → 관련 소스 위치 및 대상

- 입력: 한국어 비즈니스 용어 (예: "안전재고 계산 로직 바꿔 주세요")
- 출력: 후보 메서드/클래스/엔드포인트 목록 (confidence + 매핑 근거)
- 체인: exact → alias → 임베딩 유사도 → LLM fallback (기존 `term_resolver.py` 구조 재사용)

### 기능 3. Test Generation (테스트 자동화)
> 특정 기능을 테스트하기 위한 데이터 생성 및 테스트 실행

- 입력: 메서드 또는 비즈니스 프로세스
- 출력: 입력값 도메인에 맞춘 테스트 케이스 + 실행 결과
- 필요한 스키마 요소: 메서드별 precondition / postcondition / 입력 range / 예외 케이스

→ 이 3개를 모두 충족할 수 있는 **온톨로지 스키마**가 Section 2의 핵심 산출물.

---

## 5. 기술 스택 고정

- **Java / Spring** : 주 타겟. 여타 스택은 현재 범위 밖.
- **Parser** : tree-sitter Java (기존 `java_parser.py` 재활용 가능)
- **Graph DB** : Neo4j (기존 `:CodeEntity{repo_id}` 스키마 기반, Spring 특화 엔티티 kind 확장)
- **플러그인 아키텍처** : AST 파서 + Spring 전용 분석기 + (선택) 런타임 계측 에이전트 + 사람이 보완하는 annotation 레이어

---

## 6. Spring 8 난제 (정적 분석으로 안 잡히는 것들)

단일 AST 파서로는 부족한 이유.

| # | 난제 | 처리 방식 |
|---|------|----------|
| 1 | `@Autowired` DI : 인터페이스↔구현 매핑이 AST에 없음 | Spring 전용 분석기로 Bean 그래프 별도 구축 |
| 2 | AOP 프록시 (`@Transactional`/`@Cacheable`/`@Around`) : 호출이 advice 경유 | Aspect 엔티티를 노드로 모델링, INTERCEPTS 엣지 추가 |
| 3 | Reflection (`Method.invoke`, `Class.forName`) : 정적 추론 불가 | 사람이 ontology annotation으로 마크 + (추후) 런타임 계측 옵션 |
| 4 | Spring Data JPA 메서드 파생 (`findByCustomerId`) : 원 SQL 없음 | Spring Data 전용 파서로 메서드명 → 추론 SQL 엔티티 생성 |
| 5 | `@Bean Configuration` : classpath scan 외 Bean 정의 경로 | Configuration 클래스 전용 분석 (메서드 반환 → Bean) |
| 6 | `ApplicationEventPublisher` : publisher↔listener 암시 엣지 | 이벤트 클래스를 노드로, PUBLISHES / HANDLES 엣지 |
| 7 | `@Scheduled` / Kafka Listener : HTTP 아닌 진입점 | 별도 진입점 엔티티 kind (SCHEDULE_ENTRY, MSG_LISTENER) |
| 8 | `@ConditionalOnProperty` / 프로파일 : 설정마다 Bean 그래프 달라짐 | 조건식을 Bean 엣지에 속성으로 저장, 런타임 프로파일 필터링 지원 |

→ 이 8개 전부가 스키마 설계 시 처음부터 반영돼야 함. 사후 땜빵 불가.

---

## 7. 기준서(업무처리기준서) 워크플로우

### 7-1. 기준서의 역할 변경

- **이전**: 기준서가 온톨로지의 **원재료** (LLM이 변환)
- **지금**: 기준서가 코드 매핑의 **검증 파트너** (사람이 주도 작성, 코드와 차이로 갭 탐지)

### 7-2. 입력 형태

- 사람이 직접 작성 : Markdown 기준
- **기존 문서 재활용** : PDF / PPT / 이미지 / Word 가 이미 현장에 흩어져 있음
- **툴이 도와야 할 것** : 이들을 마크다운으로 컨버트 + 구조 추출 + 사람이 보완

### 7-3. 컨버트 파이프라인 (재활용 가능 모듈)

| 기존 파일 포맷 | 기존 자원 활용 |
|---------------|-------------|
| PDF | 기존 이미지 OCR (Section 1 image search 파이프라인 `backend/application/image/ocr_engine.py`) 재활용 |
| 이미지 | 동일 |
| PPT | `backend/api/files.py`에 python-pptx JSON 파싱 있음, 재활용 가능 |
| Word | 추가 필요 (python-docx) |

→ 사용자가 PDF/PPT/이미지/Word 업로드 → 툴이 텍스트/구조 추출 → 사람이 마크다운으로 정리 → 코드 매핑과 비교 → 누락분 탐지.

### 7-4. 갭 탐지 (Gap Detection)

- **코드에만 있고 기준서에 없음** : 10년 드리프트의 증거. "이 메서드 왜 만들어졌는지" 추적 필요
- **기준서에만 있고 코드에 없음** : 명세만 있고 구현 안 됨 or 과거에 빠진 로직
- **양쪽 다 있지만 내용 충돌** : 기준서 갱신이 안 된 경우

→ 리포트 형태로 노출해서 사람이 해소.

---

## 8. 3라운드 설계 루트 (온톨로지 스키마 확정)

> 각 라운드 끝에 HTML 설명서 1장. 사용자가 "진짜 됐다" 확인 뒤 다음 라운드.

### Round 1. 코드 쪽 스키마 + Spring 특화
- 노드 kind : Package / Class / Interface / Enum / Method / Field / Constructor / SpringBean / HttpEndpoint / DatabaseTable / DatabaseColumn / ConfigProperty / Aspect / ScheduledTask / EventListener
- 엣지 kind : CONTAINS / CALLS / EXTENDS / IMPLEMENTS / DEPENDS_ON / READS / WRITES / AUTOWIRES / INTERCEPTS / HANDLES / PUBLISHES / MAPS_URL / READS_TABLE / WRITES_TABLE / HAS_CONFIG
- 메서드 단위 precondition / postcondition 필드 포함
- 검증 시나리오 : "`OrderController.place()` 를 바꾸면 어디까지 영향?"
- **Impact Analysis 요구 충족 여부 검증**

### Round 2. 비즈니스 개념 + 코드↔개념 브릿지
- 노드 kind : BusinessTerm / BusinessRule / BusinessProcess / Role
- 브릿지 엣지 : REALIZES (메서드/클래스 ↔ 비즈니스 개념) / VALIDATES (비즈니스 룰 ↔ 메서드) / DERIVED_FROM
- 하나의 개념이 여러 코드 위치에 매핑되는 1:N 구조
- 검증 시나리오 : "'안전재고'" → `SafetyStockCalculator` + `SafetyStock` 테이블 + 관련 엔드포인트 묶음 역매핑
- **Reverse Lookup 요구 충족 여부 검증**

### Round 3. 기준서/문서 + 갭 탐지
- 노드 kind : ManualDocument / ManualSection / ManualFragment
- 인제스트 엣지 : DESCRIBED_IN / CONFLICTS_WITH / MISSING_IN
- PDF/PPT/이미지 → 텍스트/구조 추출 → 개념 매칭 제안 → 사람 검증 → 매핑 고정
- 검증 시나리오 : "코드에는 있고 기준서에 없는 로직" 리포트
- **10년 드리프트 회수 가능성 검증**

### Test Generation 스키마
- 별도 라운드 불필요. Round 1의 메서드 precondition/postcondition + 입력 range + Spring Data JPA 레포지토리의 쿼리 조건이 Test Generation 엔진이 활용할 스키마.
- Section 3에서 실행 엔진 구현.

---

## 9. 복원 vs Scratch 매트릭스

### Keep (복원 + 확장) : 새 방향과 결이 맞아 재활용

| 파일 | 상태 | 확장 방향 |
|------|------|----------|
| `backend/modeling/code_analysis/parser_protocol.py` | 그대로 복원 | EntityKind / RelationKind 에 Spring 관련 값 추가 |
| `backend/modeling/code_analysis/java_parser.py` | 그대로 복원 | 어노테이션 추출 로직 별도 Spring 분석기로 분리 |
| `backend/modeling/code_analysis/graph_writer.py` | 그대로 복원 | 새 엔티티 kind 반영 |
| `backend/modeling/query/query_engine.py` | 그대로 복원 | 그래프 엣지 확장만 |
| `backend/modeling/change/change_detector.py` | 그대로 복원 | 필요 시 비즈니스 매핑 단까지 확장 |
| `backend/modeling/infrastructure/git_connector.py` | 그대로 복원 | 변경 없음 |

### Rewrite (컨셉 살려 재작성) : 모델이 얕음

| 파일 | 문제 | 방향 |
|------|------|------|
| `backend/modeling/mapping/mapping_models.py` | `Mapping.code`가 단일 qualified name. 1:N 필요 | `BusinessTerm` 노드 + 다중 `ConceptBinding` 엣지로 재설계 |
| `backend/modeling/mapping/mapping_service.py` | CRUD는 재활용 가능, method-level 1급 시민 아님 | method-level 기본값, granularity=CLASS는 옵션 |
| `backend/modeling/query/term_resolver.py` | 한국어 alias 하드코딩 | 온톨로지 `BusinessTerm.aliases` 에서 끌어오도록 재구조화 + 임베딩 단 추가 |

### Scratch (새 방향에 안 맞음)

| 파일 | 이유 |
|------|------|
| `backend/modeling/ontology/scor_template.py` (이미 OD-6에서 YAML로 변환됨) | SCOR/ISA-95 표준 중심 설계. 참조 보조로만 유지, 주된 축은 회사 코드 구조 |
| `backend/modeling/ontology/domain_models.py` (이미 OD-6에서 삭제됨) | - |
| `backend/modeling/simulation/*` | Section 3 이후. 스키마 확정 후 재설계 |
| `backend/modeling/approval/*` | 2차 기능. OD-11 범위 밖 |
| 프론트엔드 삭제된 컴포넌트 대부분 | UX 패턴은 참고하되 새 스키마 위에 재작업 |

### 현재 코드 중 재활용

| 파일 | 역할 |
|------|------|
| `backend/modeling/ontology/schema.py` (Formula / Rule / Term 부분) | 비즈니스 룰 표현용으로 부분 재활용 |
| `backend/modeling/ontology/validator.py` (Sub-DSL 파서) | 매핑 제약식 (precondition / postcondition) 검증용으로 전용 |
| `backend/modeling/ontology/builder_service.py` | 매뉴얼 인제스트 보조 도구의 한 단계로 흡수 (LLM이 PDF/PPT 초안 정리 도울 때) |
| `backend/application/image/ocr_engine.py` | 기준서 PDF/이미지 OCR에 재활용 |
| `backend/api/files.py`의 python-pptx JSON 파싱 | 기준서 PPT 파싱에 재활용 |

---

## 10. 범위

- **데모 범위** : 1 도메인 (예 : 재고/구매 중 하나). 1 스프링 프로젝트 사이즈.
- **개발 범위** : 설계는 **레거시 전체를 커버 가능**하게. 즉 스키마와 파서가 특정 도메인에만 의존하면 안 됨. 10만 라인+ 규모 가정.
- **성능** : 영향 분석 BFS는 인덱스 있는 상태에서 대화형 응답 (< 2초) 목표.

---

## 11. OD-11 태스크 목록 (초안)

> 라운드별 HTML 설명서는 사용자 승인 checkpoint.

### Phase A : 문서화 + 복원 결정
- [ ] **OD-11-A1** : OD-11-PLAN.md 작성 (이 문서)
- [ ] **OD-11-A2** : TODO.md / HANDOFF.md / CHANGES.md / memory project_status 갱신
- [ ] **OD-11-A3** : 복원 범위 사용자 최종 승인 (이 문서 확인 후)

### Phase B : Round 1 스키마 (코드 쪽 + Spring)
- [ ] **OD-11-B1** : Round 1 HTML 설명서 초안 (`toClaude/modeling/round1-code-schema.html`)
- [ ] **OD-11-B2** : 사용자 피드백 수렴 및 HTML 갱신 반복
- [ ] **OD-11-B3** : 스키마 합의 후 `parser_protocol.py` 복원 + 확장
- [ ] **OD-11-B4** : `java_parser.py` 복원 + Spring 분석기 분리 설계
- [ ] **OD-11-B5** : Spring 8 난제 처리 방식 각각 PoC

### Phase C : Round 2 스키마 (비즈니스 개념 + 브릿지)
- [ ] **OD-11-C1** : Round 2 HTML 설명서 초안
- [ ] **OD-11-C2** : 사용자 승인 후 `mapping_models.py` 재설계
- [ ] **OD-11-C3** : `term_resolver.py` 재구조화 (임베딩 + alias data-driven)
- [ ] **OD-11-C4** : Reverse Lookup API 초안

### Phase D : Round 3 스키마 (기준서/문서 + 갭 탐지)
- [ ] **OD-11-D1** : Round 3 HTML 설명서 초안
- [ ] **OD-11-D2** : PDF / PPT / 이미지 인제스트 파이프라인 (기존 모듈 재활용)
- [ ] **OD-11-D3** : 갭 탐지 엔진 초안
- [ ] **OD-11-D4** : 사람 검증 UI 설계

### Phase E : 통합 검증
- [ ] **OD-11-E1** : 1 도메인 PoC (재고 or 구매 중 택1) E2E
- [ ] **OD-11-E2** : 3대 기능 각각 검증 시나리오

(각 Phase 는 사용자 확인 후 순차 진행. Phase B까지가 현재 우선순위.)

---

## 12. 다음 첫 작업

**Phase A 완료 후 → OD-11-B1 : Round 1 HTML 설명서 초안 작성**.

사용자가 Round 1 HTML을 보고 "이해됐다 + 이 방향 맞다" 하면 OD-11-B3 (복원+확장 시작). 이해 안 되거나 방향 안 맞으면 HTML 갱신 반복.

---

## 13. 참조

- 피벗 이전 산출물 : `toClaude/modeling/section2-explainer.html` (매뉴얼 1차 방향 설명. OD-11 이후 deprecated, 참조용으로만 남김)
- 삭제된 코드 복원 소스 : 현재 워킹트리가 아직 커밋 전이므로 `git restore <path>` 로 복원 가능. 커밋 상태라면 `git show HEAD:<path>` 사용.
- 이전 설계 문서 : `~/.gstack/projects/Jeensh-onTong/donghae-main-design-20260418-173359.md` (매뉴얼 1차 시절. OD-11 이후 이 문서가 상위)
