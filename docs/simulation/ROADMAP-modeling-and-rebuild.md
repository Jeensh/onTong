# onTong 모델링·시뮬레이션 통합 로드맵

> **이 문서를 가장 먼저 읽어주세요.** Claude Code가 작업할 전체 흐름과 4개 명세 문서의 관계를 정리합니다.
> **버전**: v1.0
> **작성일**: 2026-04-25

---

## 0. 한눈에 보기

```
이번 작업의 목표:
├── Section 2 (Modeling)에 Neo4j 기반 3-Layer 온톨로지 구축
└── Section 3 (Simulation)을 고정 Agent 3종 + 표준화 시뮬레이션으로 재구축
```

지난 회의에서 결정된 방향:
- 자유 대화형 → **틀이 정해진 Agent 3종**
- 시나리오 A/B/C → **표준화된 메뉴 허브**
- Mock 데이터 → **Section 2 온톨로지 호출**
- 도메인 지식이 Agent에 분산 → **온톨로지에 집중**

---

## 1. 4개 명세 문서 관계도

```
┌─────────────────────────────────────────────────────┐
│ 📘 ROADMAP-modeling-and-rebuild.md  ← 이 문서       │
│   (전체 흐름 + 작업 순서)                            │
└────────────────┬────────────────────────────────────┘
                 │ 참조
        ┌────────┴────────┬─────────────────┐
        ↓                 ↓                 ↓
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ 🟢 ontology- │  │ 🟠 section3- │  │ 🔵 section2- │
│  modeling-   │  │  rebuild-    │  │  section3-   │
│  spec.md     │  │  spec.md     │  │  protocol.md │
│              │  │              │  │              │
│ Section 2    │  │ Section 3    │  │ 두 섹션 간   │
│ 온톨로지 구축 │  │ 재구축 명세  │  │ 통신 계약    │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                  │                  │
       └──────────┬───────┴──────────────────┘
                  ↓
         ┌──────────────────┐
         │ 🟣 ontology-data-│
         │  seed.md         │
         │                  │
         │ 모든 시드 데이터  │
         │ (JSON)           │
         └──────────────────┘
```

### 문서별 역할

| 문서 | 무엇을 정의 | 누가 참조 |
|------|----------|---------|
| **ROADMAP** (이 문서) | 4주 전체 작업 순서 | 모든 작업의 시작 |
| **ontology-modeling-spec** | Section 2 온톨로지 구축 방법 | Modeling 작업자 |
| **section3-rebuild-spec** | Section 3 재구축 방법 | Simulation 작업자 |
| **section2-section3-protocol** | API 계약 | 두 섹션 모두 |
| **ontology-data-seed** | 시드 데이터 정의 | Modeling 작업자 |

---

## 2. 4주 통합 로드맵

```
Week 1 ─────────────────────────────────────
  Day 1-2: 인프라 (Neo4j) + 폴더 구조
  Day 3-5: Layer 1 + Layer 2 (수동)
  → 산출: Neo4j에 70+ 노드, Browser 시각화 가능

Week 2 ─────────────────────────────────────
  Day 6-7: jQAssistant 도입 + Layer 3 추출
  Day 8-9: Layer 2 ↔ Layer 3 매핑
  Day 10:  shared/contracts/ontology.py
  → 산출: 3-Layer 통합, 검증 쿼리 6개 통과

Week 3 ─────────────────────────────────────
  Day 11-12: Section 2 API 라우터
  Day 13-15: Section 3 기존 코드 제거 + 신규 폴더
  → 산출: Section 2 API 동작, Section 3 폴더 정리 완료

Week 4 ─────────────────────────────────────
  Day 16-17: Agent 3종 백엔드
  Day 18-19: Agent 3종 프론트엔드
  Day 20:    E2E 통합 테스트
  → 산출: 데모 가능한 완성품
```

---

## 3. Week별 상세 진행

### 📅 Week 1 — 온톨로지 기반 구축

#### Day 1: 인프라 셋업
- [ ] **참조 문서**: `ontology-modeling-spec.md` Section 2
- [ ] docker-compose.yml에 Neo4j 추가
- [ ] .env / .env.example 환경변수 추가
- [ ] pyproject.toml에 neo4j 의존성 추가
- [ ] `docker compose up -d neo4j` → http://localhost:7474 접속 확인

#### Day 2: 폴더 구조
- [ ] **참조 문서**: `ontology-modeling-spec.md` Section 1
- [ ] `backend/modeling/ontology/` 폴더 + 하위 디렉토리 생성
- [ ] `client.py` 작성 → 연결 테스트 (`python -m backend.modeling.ontology.client`)
- [ ] "Hello onTong!" 응답 확인

#### Day 3: Layer 1 구축
- [ ] **참조 문서**: `ontology-data-seed.md` Section A
- [ ] `data/terms.json` 작성 (시드 문서의 JSON 그대로 복사)
- [ ] `builders/layer1_business.py` 작성
- [ ] 빌드 실행: `python -m backend.modeling.ontology.builders.layer1_business`
- [ ] Neo4j Browser에서 19개 Term + 5개 Category 확인
- [ ] **검증 쿼리 1, 2 통과** (`ontology-modeling-spec.md` Section 9-1)

#### Day 4: Layer 2 구축
- [ ] **참조 문서**: `ontology-data-seed.md` Section B, C, F
- [ ] `data/steps.json` 작성 (12 Step)
- [ ] `data/standards.json` 작성 (14 SC)
- [ ] `data/variables.json` 작성 (10 Variable)
- [ ] `data/error_codes.json` 작성 (1 ErrorCode)
- [ ] `builders/layer2_process.py` 작성
- [ ] 빌드 실행 → 검증
- [ ] **검증 쿼리 3 통과**

#### Day 5: Bridge (Layer 1 ↔ 2)
- [ ] **참조 문서**: `ontology-data-seed.md` Section D
- [ ] `data/bridges.json` 작성 (15 REFERS_TO_PROCESS)
- [ ] `builders/bridges.py` 작성
- [ ] 빌드 + 검증
- [ ] **검증 쿼리 4 통과**

> Week 1 완료 시점: Neo4j에 70+ 노드, 100+ 관계가 있고 4개 검증 쿼리가 모두 동작.

---

### 📅 Week 2 — Layer 3 자동 추출 + Bridge

#### Day 6: jQAssistant 도입
- [ ] **참조 문서**: `ontology-modeling-spec.md` Section 5
- [ ] `sample-repos/scm-demo/pom.xml`에 jQAssistant 플러그인 추가
- [ ] `mvn jqassistant:scan` 실행
- [ ] Neo4j Browser에서 :Type, :Method 노드 확인

#### Day 7: Layer 3 정규화
- [ ] **참조 문서**: `ontology-modeling-spec.md` Section 5-3
- [ ] `data/tables.json` 작성 (14 Table)
- [ ] `builders/layer3_code.py` 작성 (jQA 결과 → 우리 스키마)
- [ ] 빌드 실행
- [ ] **검증 쿼리 5 통과**

#### Day 8: Method ↔ Step 매핑 (Stage 1+2)
- [ ] **참조 문서**: `ontology-modeling-spec.md` Section 6-2
- [ ] Naming Convention 패턴 매칭 코드 작성
- [ ] LLM 보조 매핑 코드 작성
- [ ] 매핑 결과 출력 (CSV/JSON)

#### Day 9: 수동 검증 + Form 매핑
- [ ] **참조 문서**: `ontology-data-seed.md` Section E-2
- [ ] LLM 결과를 사람이 검증 (스프레드시트 등)
- [ ] FORM_TO_STANDARD 매핑 자동 적용
- [ ] **검증 쿼리 6 통과** ⭐ (3-Layer 통합)

#### Day 10: shared/contracts 작성
- [ ] **참조 문서**: `section2-section3-protocol.md` 전체
- [ ] `backend/shared/contracts/ontology.py` 작성
- [ ] `backend/shared/contracts/test_ontology.py` 작성 + pytest 통과

> Week 2 완료 시점: 3-Layer 온톨로지 완성, API 계약 등록.

---

### 📅 Week 3 — Section 2 API + Section 3 정리

#### Day 11-12: Section 2 API
- [ ] **참조 문서**: `ontology-modeling-spec.md` Section 8
- [ ] `queries/impact_queries.py` 작성
- [ ] `queries/test_data_queries.py` 작성
- [ ] `queries/locator_queries.py` 작성
- [ ] `api/ontology_router.py` 작성
- [ ] `main.py`에 라우터 등록
- [ ] curl 테스트:
  ```bash
  curl -X POST http://localhost:8001/api/modeling/ontology/query \
    -d '{"request_id":"t1","intent":"impact_analysis","parameters":{"target":{"kind":"table","id":"TB_C40_050SC070"}}}'
  ```

#### Day 13: Section 3 기존 코드 제거
- [ ] **참조 문서**: `section3-rebuild-spec.md` Section 3
- [ ] 기존 `agent/scenario_a_agent.py` 등 삭제
- [ ] 기존 `mock/` 폴더 삭제
- [ ] Custom Agent Hub 관련 컴포넌트 삭제
- [ ] **보존 컴포넌트 확인**: SlabViewer3D, SlabParamController, SlabImpactPanel

#### Day 14-15: Section 3 신규 폴더 구조
- [ ] **참조 문서**: `section3-rebuild-spec.md` Section 3-3
- [ ] `backend/simulation/agents/` 폴더 생성
- [ ] `backend/simulation/client/ontology_client.py` 작성
- [ ] `backend/simulation/api/agents_router.py` 스켈레톤 작성

> Week 3 완료 시점: Section 2가 RESTful API 제공, Section 3는 신규 구조 준비.

---

### 📅 Week 4 — Agent 3종 구현

#### Day 16: Agent 1 (영향도)
- [ ] **참조 문서**: `section3-rebuild-spec.md` Section 4-2
- [ ] `agents/agent1_impact.py` 작성
- [ ] `api/agents_router.py`에 `/impact` 엔드포인트
- [ ] curl 테스트 통과
- [ ] **시나리오 Test 1 통과**

#### Day 17: Agent 2 (테스트 데이터) + Agent 3 (위치)
- [ ] **참조 문서**: `section3-rebuild-spec.md` Section 4-3, 4-4
- [ ] `agents/agent2_test_data.py` 작성
- [ ] `agents/agent3_locator.py` 작성
- [ ] `/test-data`, `/locator` 엔드포인트 추가
- [ ] **시나리오 Test 2, 3 통과**

#### Day 18: 프론트엔드 메인 허브 + 공통 컴포넌트
- [ ] **참조 문서**: `section3-rebuild-spec.md` Section 5
- [ ] `AgentHub.tsx` 작성 (메인 허브)
- [ ] `EntitySearchBox.tsx` 작성 (자동완성)
- [ ] `ResultTable.tsx` 작성

#### Day 19: 프론트엔드 Agent 폼 3개
- [ ] `Agent1ImpactForm.tsx` 작성
- [ ] `Agent2TestDataForm.tsx` 작성
- [ ] `Agent3LocatorForm.tsx` 작성

#### Day 20: E2E 통합 테스트
- [ ] **참조 문서**: `section3-rebuild-spec.md` Section 7
- [ ] Section 3 탭 → AgentHub 표시
- [ ] Agent 1 폼 → SC070 검색 → 영향도 분석 → 결과 표시
- [ ] Agent 2 폼 → Step 2 → 테스트 데이터 5개 생성
- [ ] Agent 3 폼 → "Edging" → 소스/테이블/Step 위치 표시
- [ ] 데모 시나리오 녹화/캡처

> Week 4 완료 시점: 데모 가능한 완성품!

---

## 4. 최종 산출물 체크리스트

### Section 2 (Modeling)
- [ ] Neo4j 컨테이너 동작 (docker-compose)
- [ ] `backend/modeling/ontology/` 모듈 전체
- [ ] Layer 1: 19 Term + 5 Category
- [ ] Layer 2: 12 Step + 14 Standard + 10 Variable + 1 ErrorCode
- [ ] Layer 3: jQAssistant 자동 추출 + 정규화
- [ ] Bridge 관계: Layer 1↔2, Layer 2↔3
- [ ] `backend/shared/contracts/ontology.py`
- [ ] API 엔드포인트 3개:
  - `POST /api/modeling/ontology/query`
  - `GET /api/modeling/ontology/graph/stats`
  - `GET /api/modeling/ontology/term/search`
- [ ] 검증 쿼리 6개 모두 통과

### Section 3 (Simulation)
- [ ] 기존 시나리오 A/B/C, Custom Agent Hub 제거
- [ ] `backend/simulation/agents/` 3개 Agent
- [ ] `backend/simulation/client/ontology_client.py`
- [ ] API 엔드포인트 3개:
  - `POST /api/simulation/agents/impact`
  - `POST /api/simulation/agents/test-data`
  - `POST /api/simulation/agents/locator`
- [ ] Frontend AgentHub + 3개 폼 컴포넌트
- [ ] 공통 컴포넌트: EntitySearchBox, ResultTable
- [ ] 시나리오 Test 1~3 모두 통과
- [ ] E2E 데모 흐름 완성

---

## 5. 작업 시 주의사항

### 5-1. 기존 코드 보호
- **`backend/application/` (Wiki) 절대 건드리지 말 것**
- **`backend/modeling/`의 기존 파일** (분석 콘솔, 매핑 워크벤치 등)도 그대로 두기
- 신규 작업은 `backend/modeling/ontology/` 하위에만 추가

### 5-2. 멱등성
- 모든 빌더는 두 번 실행해도 같은 결과여야 함
- `clear_layer()` 먼저 호출 후 빌드

### 5-3. 시드 데이터 분리
- 데이터는 JSON 파일로, 코드는 Python으로 분리
- 데이터 수정 시 코드 변경 없이 가능해야 함

### 5-4. 환경변수
- 비밀번호, URL은 `.env`에서 받음
- 하드코딩 금지

### 5-5. Section 2 미완성 시 Section 3 개발 가능하게
- `OntologyClient`에 `USE_MOCK_ONTOLOGY=true` 옵션 제공
- Mock 응답 데이터를 미리 준비

---

## 6. 트러블슈팅

### Neo4j 연결 안 됨
```bash
docker compose logs neo4j
# 메모리 부족이면 NEO4J_dbms_memory_heap_max__size를 1G로 줄이기
```

### jQAssistant 결과가 우리 스키마와 다름
- 정상. Day 7의 정규화 단계에서 처리
- Cypher 변환 스크립트가 핵심

### Method ↔ Step 매핑 정확도 낮음
- Stage 1 (정규식) + Stage 2 (LLM) + Stage 3 (수동) 3단계 적용
- 100% 자동화는 어려움. 80% 자동, 20% 수작업 인정

### Section 3 → Section 2 호출 느림
- Redis 캐싱 추가 (TTL 5분)
- 또는 Neo4j 쿼리 인덱스 점검

---

## 7. 완성 후 데모 시나리오 (참고)

```
[5분 데모]

1. (30초) Section 3 탭 클릭 → AgentHub 표시
   "이게 새로 만든 기능 표준화 Agent 허브입니다"

2. (90초) Agent 1 — 영향도 파악
   - "TB_C40_050SC070 검색"
   - "데이터 변경 / 컬럼 추가" 선택
   - "분석 실행" → 직접 영향 메서드 + Step + 위험도 HIGH 표시
   "기준 변경 시 어디까지 파급되는지 자동으로 알려줍니다"

3. (90초) Agent 2 — 테스트 데이터
   - "Step 2 (1차 폭범위) 선택"
   - "정상 + 경계값 + 에러" 선택
   - "생성" → 5개 테스트 케이스 + JUnit 코드
   "기능 테스트용 데이터를 자동 생성합니다"

4. (90초) Agent 3 — 위치 파악
   - "Edging 로직 어디 있어?" 입력
   - "위치 파악 실행" → 프로세스 + 소스 + 테이블 표시
   "자연어로 물어보면 정확한 위치를 알려줍니다"

5. (30초) 마무리
   "모든 Agent는 Section 2의 온톨로지를 호출합니다.
    온톨로지에 새로운 기준이 추가되면 Agent가 자동으로 인식합니다."
```

---

## 8. 작업 시작하기

```bash
# 1. 레포 클론 + 브랜치
git clone https://github.com/Jeensh/onTong.git
cd onTong
git checkout -b feat/ontology-and-rebuild

# 2. 의존성
poetry install

# 3. 첫 번째 작업: Day 1
# → ontology-modeling-spec.md Section 2 따라하기

# 작업 완료 후
git add .
git commit -m "feat: implement ontology + section3 rebuild"
git push -u origin feat/ontology-and-rebuild
```

---

## 9. 의존성 그래프 (작업 순서 시각화)

```
Day 1 (Neo4j) ──────────────────────────┐
                                         ↓
Day 2 (폴더+client) ─────────────────────┤
                                         ↓
Day 3 (Layer 1) ─────────────────────────┤
                                         ↓
Day 4 (Layer 2) ─────────────────────────┤
                                         ↓
Day 5 (Bridge) ──────────────────────────┤
                                         ↓
Day 6-7 (jQA + Layer 3) ─────────────────┤
                                         ↓
Day 8-9 (L2↔L3 매핑) ────────────────────┤
                                         ↓
Day 10 (contracts) ──────┬───────────────┤
                         │               │
                         ↓               ↓
                  Day 11-12        Day 13-15
                  (Sec2 API)       (Sec3 정리)
                         │               │
                         └───────┬───────┘
                                 ↓
                          Day 16-17 (Agent BE)
                                 ↓
                          Day 18-19 (Agent FE)
                                 ↓
                          Day 20 (E2E 테스트)
                                 ↓
                              완료 🎉
```

---

## 10. 한 줄 요약

> **"4주 동안 Neo4j에 3-Layer 온톨로지 구축(Section 2) → 그 위에 고정 Agent 3종 시뮬레이터(Section 3)를 만든다. 각 주마다 동작 가능한 산출물 보장."**
