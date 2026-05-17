# 📋 onTong 모델링·시뮬레이션 통합 작업 — Claude Code 작업 지시

> **이 문서는 Claude Code가 이 작업을 시작할 때 가장 먼저 보는 문서입니다.**

---

## 🎯 작업 개요

이번 작업은 onTong 프로젝트의 **두 섹션을 동시에 개발/재구축**합니다.

```
┌─────────────────────────────────────────────────────┐
│ Section 2 (Modeling) — 온톨로지 구축 [신규]          │
│ Section 3 (Simulation) — 고정 Agent로 재구축 [갈아엎음] │
└─────────────────────────────────────────────────────┘
```

지난 회의에서 결정된 핵심 방향:
- ✅ Section 2: Neo4j 기반 3-Layer 온톨로지 (업무 용어 + 업무처리기준서 ↔ 소스)
- ✅ Section 3: 자유 대화 → **틀이 정해진 고정 Agent 3종**으로 재구축

---

## 📚 문서 읽는 순서

**반드시 이 순서대로** 읽고 작업을 시작하세요.

### 1️⃣ 먼저 읽을 문서
[**ROADMAP-modeling-and-rebuild.md**](./ROADMAP-modeling-and-rebuild.md)
- 4주 통합 로드맵
- Day별 작업 순서
- 모든 다른 문서가 어떻게 연결되는지 설명

### 2️⃣ 그 다음 (작업 영역에 따라)

**Section 2 (Modeling) 작업 시:**
- [**ontology-modeling-spec.md**](./ontology-modeling-spec.md) — 온톨로지 구축 명세
- [**ontology-data-seed.md**](./ontology-data-seed.md) — 모든 시드 데이터
- [**section2-section3-protocol.md**](./section2-section3-protocol.md) — API 계약

**Section 3 (Simulation) 작업 시:**
- [**section3-rebuild-spec.md**](./section3-rebuild-spec.md) — 재구축 명세
- [**section2-section3-protocol.md**](./section2-section3-protocol.md) — API 계약

---

## 🚦 작업 시작 전 체크리스트

### 환경 준비
- [ ] onTong 레포 클론 완료
- [ ] Python 3.10+ 가상환경 활성화
- [ ] Docker Desktop 실행 중
- [ ] 기존 docker compose 서비스 (chroma, redis) 동작 확인

### 작업 브랜치
```bash
git checkout main && git pull
git checkout -b feat/ontology-and-rebuild
```

### 첫 명령
**ROADMAP 문서를 열어서 Day 1부터 시작하세요.**

---

## 📂 생성될 파일 구조 (전체)

```
onTong/
├── backend/
│   ├── modeling/
│   │   └── ontology/                       ← 신규 (Section 2)
│   │       ├── client.py
│   │       ├── builders/
│   │       │   ├── layer1_business.py
│   │       │   ├── layer2_process.py
│   │       │   ├── layer3_code.py
│   │       │   ├── bridges.py
│   │       │   └── build_all.py
│   │       ├── data/
│   │       │   ├── terms.json
│   │       │   ├── steps.json
│   │       │   ├── standards.json
│   │       │   ├── variables.json
│   │       │   ├── error_codes.json
│   │       │   ├── tables.json
│   │       │   └── bridges.json
│   │       ├── queries/
│   │       │   ├── impact_queries.py
│   │       │   ├── test_data_queries.py
│   │       │   └── locator_queries.py
│   │       └── api/
│   │           └── ontology_router.py
│   │
│   ├── simulation/                          ← 갈아엎음 (Section 3)
│   │   ├── agents/                          ← 신규
│   │   │   ├── agent1_impact.py
│   │   │   ├── agent2_test_data.py
│   │   │   └── agent3_locator.py
│   │   ├── client/                          ← 신규
│   │   │   └── ontology_client.py
│   │   └── api/
│   │       └── agents_router.py             ← 신규
│   │   (기존 agent/, mock/ 폴더는 삭제)
│   │
│   └── shared/contracts/
│       └── ontology.py                       ← 신규 (계약)
│
├── frontend/src/
│   ├── components/simulation/
│   │   ├── AgentHub.tsx                      ← 신규
│   │   ├── Agent1ImpactForm.tsx              ← 신규
│   │   ├── Agent2TestDataForm.tsx            ← 신규
│   │   ├── Agent3LocatorForm.tsx             ← 신규
│   │   └── shared/
│   │       ├── EntitySearchBox.tsx           ← 신규
│   │       └── ResultTable.tsx               ← 신규
│   │   (기존 ScenarioSelector, SimCopilot 등 삭제)
│   │
│   └── lib/simulation/
│       ├── agentApi.ts                        ← 신규
│       └── types.ts                            ← 신규
│
├── sample-repos/scm-demo/
│   └── pom.xml                                ← jQAssistant 추가
│
├── docker-compose.yml                          ← Neo4j 추가
└── .env.example                                ← Neo4j 변수 추가
```

---

## 🛡 절대 건드리지 말 것

- `backend/application/` — Wiki (Section 1)
- `backend/modeling/` 내의 기존 파일들 (분석 콘솔, 매핑 워크벤치)
- `backend/core/`, `backend/infrastructure/` (공유 인프라)
- `frontend/src/components/sections/` (섹션 네비게이션)

---

## ✅ 4주 후 최종 결과물

```
✅ Neo4j에 3-Layer 온톨로지 구축
   - Layer 1: 19개 업무 용어
   - Layer 2: 12개 Step + 14개 SC기준
   - Layer 3: jQAssistant 자동 추출 클래스/메서드/테이블

✅ Section 2 API 3개:
   - POST /api/modeling/ontology/query
   - GET  /api/modeling/ontology/graph/stats
   - GET  /api/modeling/ontology/term/search

✅ Section 3 Agent 3종:
   - 영향도 파악 Agent
   - 테스트 데이터 생성 Agent
   - 비즈니스 용어 위치 파악 Agent

✅ Frontend AgentHub + 3개 폼
   - 자유 대화 없음, 구조화된 폼만

✅ E2E 데모 시나리오 동작
```

---

## 🎬 데모 한 장면

```
사용자: Section 3 탭 클릭
→ "기능 표준화 Agent 허브" 화면

사용자: "Agent 1 — 영향도 파악" 클릭
→ 폼 표시 (자유 채팅 아님!)

사용자: 
  - 변경 유형: "데이터 변경" 선택
  - 대상: "TB_C40_050SC070" 자동완성으로 선택
  - 변경 종류: "컬럼 추가" 선택
  - [영향도 분석 실행] 클릭

→ 결과 테이블:
  - 직접 영향 메서드: 2개
  - 영향받는 Step: Step 2, Step 13
  - 간접 영향: 8개 메서드
  - 위험도: HIGH
```

---

## 🤝 작업 중 막히면

1. **로드맵 다시 확인**: `ROADMAP-modeling-and-rebuild.md`의 트러블슈팅 섹션
2. **검증 쿼리 활용**: 각 단계마다 검증 쿼리가 정의되어 있음
3. **계약 문서 재확인**: API 형식이 헷갈리면 `section2-section3-protocol.md`

---

## 작업을 시작합시다 🚀

[**📘 ROADMAP-modeling-and-rebuild.md를 열어 Day 1부터 시작하세요.**](./ROADMAP-modeling-and-rebuild.md)
