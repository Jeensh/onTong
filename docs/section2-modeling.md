# Section 2 — Modeling 기능 가이드

> **대상 사용자**: IT 담당자 (레거시 코드 유지보수 + 도메인 매핑)
> **목적**: 레거시 코드를 도메인 온톨로지에 매핑하여 영향 분석 + 시뮬레이션
> **상태**: Phase 1a (분석 콘솔) + Phase 2a (매핑 워크벤치) 완료, Phase 1b (Neo4j BFS) 예정

Section 2(Modeling)는 레거시 코드와 비즈니스 도메인의 간극을 메우는 영역입니다. 코드 엔티티를 온톨로지 노드에 매핑해두면, IT 담당자가 한국어로 "이 기능 바꾸면 어디 깨지지?"를 물을 수 있고, 파라메트릭 시뮬레이션으로 before/after 비교를 즉시 확인할 수 있습니다.

---

## 1. 분석 콘솔 (Phase 1a)

Section 2의 메인 진입 화면. 한국어 자연어로 코드·도메인 엔티티를 탐색합니다.

- **Term Resolution Chain** — 한국어 별칭(30개) → fuzzy 매칭(임계값 0.55) → LLM fallback 3단계로 질문을 엔티티 ID로 정규화
- **영향 프로세스 분석** — resolve된 엔티티에 연결된 SCM 프로세스 목록 + 영향도 표시
- **사이드바 재구성** — "분석 콘솔"이 기본 탭, 기존 탭(스킬, 이미지 등)은 "설정" 구분선 아래로 정리

## 2. 시뮬레이션 패널 (Phase 1a)

파라미터 슬라이더로 before/after 비교를 즉시 수행하는 파라메트릭 시뮬레이터입니다.

- **9개 SCM 데모 엔티티** — 안전재고 계산기, 리드타임 추정, 수요 예측 등 실제 업무 함수 기반
- **Sim Registry** — 엔티티 ID → 계산 함수 매핑 (확장 시 `sim_registry.py`에 함수만 등록)
- **Sim Engine** — 변경된 파라미터 → 영향 범위 BFS 추적 → diff 리포트 반환
- **결정론적 결과** — 같은 파라미터 → 같은 결과 (재현 가능성 보장)

## 3. 매핑 워크벤치 (Phase 2a, 2026-04-16)

코드 파일과 도메인 온톨로지를 나란히 놓고 드래그-드롭으로 매핑을 생성합니다.

- **Source Viewer** — 좌측 파일 트리 + Monaco read-only 에디터 + 엔티티 gutter marker
- **Mapping Canvas** — React Flow 도메인 온톨로지 그래프 + 엔티티 패널 + 드래그-드롭 매핑 + fitView 자동 적용
- **55/45 분할 패널** — 캔버스 ↔ 뷰어 양방향 연동 (캔버스에서 노드 클릭 시 뷰어가 해당 파일로 이동)
- **Source API** — 파일 트리 + 파일 내용 + 엔티티 위치 조회 (path traversal / symlink 방어 포함, 14 tests)
- **Seed API** — "SCM 데모" 버튼으로 샘플 레포 + 엔티티 + 매핑을 한 번에 세팅

## 4. 백엔드 구조

```
backend/modeling/
├── api/
│   ├── engine_api.py      ← /engine/query, /simulate, /params, /status
│   ├── source_api.py      ← /source/tree, /file, /entity (Phase 2a)
│   ├── mapping_api.py     ← /mapping/{repo_id} CRUD, /gaps, /resolve
│   ├── code_api.py        ← tree-sitter 코드 파싱
│   ├── ontology_api.py    ← 도메인 온톨로지 CRUD
│   ├── approval_api.py    ← 매핑 승인 워크플로우
│   ├── query_api.py       ← 질의 분석
│   ├── seed_api.py        ← 데모 데이터 시딩
│   └── modeling.py        ← /api/modeling/health
├── agent/                 ← ModelingAgent (ontology_query, code_trace, impact_analysis)
├── simulation/
│   ├── sim_engine.py      ← BFS 기반 영향 추적
│   ├── sim_registry.py    ← 9개 엔티티 × 계산 함수 매핑
│   └── sim_models.py      ← ParametricSimResult 등 Pydantic 모델
├── query/
│   └── term_resolver.py   ← Korean alias + fuzzy + LLM fallback
├── code_analysis/         ← tree-sitter 기반 Java 파서
├── mapping/               ← 코드 ↔ 도메인 엔티티 매핑 저장소
├── ontology/              ← SCOR + ISA-95 기반 도메인 온톨로지
├── approval/              ← 매핑 승인 큐
└── change/                ← 변경 이력 추적
```

## 5. 프론트엔드 구조

```
frontend/src/components/sections/modeling/
├── AnalysisConsole.tsx       ← 분석 콘솔 메인 (Phase 1a)
├── SimulationPanel.tsx       ← 시뮬레이션 파라미터 슬라이더 (Phase 1a)
├── ModelingSection.tsx       ← 섹션 루트 + 뷰 라우팅
├── MappingWorkbench.tsx      ← 매핑 워크벤치 (Phase 2a)
├── SourceViewer.tsx          ← Monaco 기반 소스 뷰어
└── MappingCanvas.tsx         ← React Flow 온톨로지 그래프
```

## 6. API 엔드포인트

| 메서드 | 경로 | 설명 |
| ------ | ---- | ---- |
| `POST` | `/api/modeling/engine/query` | 한국어 질의 → 엔티티 resolve + 영향 프로세스 |
| `POST` | `/api/modeling/engine/simulate` | 파라메트릭 시뮬레이션 실행 (before/after) |
| `GET` | `/api/modeling/engine/params/{entity_id}` | 엔티티 파라미터 메타데이터 |
| `GET` | `/api/modeling/engine/status` | 엔진 초기화 상태 |
| `POST` | `/api/modeling/code/parse` | tree-sitter 파싱 → 엔티티 추출 |
| `GET` | `/api/modeling/code/graph/{repo_id}` | 코드 의존성 그래프 |
| `GET` | `/api/modeling/source/tree/{repo_id}` | 파일 트리 |
| `GET` | `/api/modeling/source/file/{repo_id}` | 파일 내용 조회 |
| `GET` | `/api/modeling/source/entity/{repo_id}/{qname}` | 엔티티 위치 조회 |
| `GET` | `/api/modeling/mapping/{repo_id}` | 매핑 목록 |
| `POST` | `/api/modeling/mapping/{repo_id}` | 매핑 생성/수정 |
| `DELETE` | `/api/modeling/mapping/{repo_id}/{code}` | 매핑 삭제 |
| `GET` | `/api/modeling/mapping/{repo_id}/gaps` | 미매핑 엔티티 목록 |
| `GET` | `/api/modeling/ontology/tree` | 도메인 온톨로지 트리 |
| `POST` | `/api/modeling/ontology/node` | 온톨로지 노드 생성 |
| `POST` | `/api/modeling/approval/submit` | 매핑 승인 요청 |
| `POST` | `/api/modeling/seed/scm-demo` | SCM 샘플 데이터 시딩 |
| `GET` | `/api/modeling/health` | 헬스 체크 |

전체 목록: [API 레퍼런스](api-reference.md)

## 7. 향후 개발 계획

| 단계 | 내용 | 상태 |
| ---- | ---- | ---- |
| Phase 1a | 분석 콘솔 + 시뮬레이션 패널 (9개 엔티티) | ✅ 완료 (2026-04-15) |
| Phase 2a | 매핑 워크벤치 (Source Viewer + Mapping Canvas) | ✅ 완료 (2026-04-16) |
| Phase 1b | Neo4j BFS 기반 실제 의존성 그래프 | 🔜 다음 |
| Phase 2b | 코드 편집 샌드박스 (gVisor/Kata Containers) | 🔜 예정 |
| Section 3 연동 | MockModelingClient → RealModelingClient 교체 | 🔜 예정 |

---

## 관련 문서

| 문서 | 설명 |
| ---- | ---- |
| [Section 2 설계 명세](superpowers/specs/2026-04-12-section2-modeling-design.md) | 초기 Modeling MVP 설계 |
| [Engine Phase 1a 플랜](superpowers/plans/2026-04-15-modeling-engine-phase1a.md) | 분석 콘솔 구현 플랜 |
| [매핑 워크벤치 설계](superpowers/specs/2026-04-16-source-viewer-mapping-workbench-design.md) | Phase 2a 설계 명세 |
| [플랫폼 아키텍처 v2](../toClaude/_shared/reports/platform_architecture_v2.md) | 3-Section 전체 설계 (16개 섹션) |
