# Step C1 — Clean Slate (Section 2/3 archive + drop)

**완료**: 2026-05-01
**기반 결정**: Q10=D + 사용자 지침 (타협 없음, 충돌 시 기존 삭제)

## 산출물 요약

| 항목 | 수치 |
|---|---|
| Archive 된 파일 | 346 개 |
| Archive 된 Python LOC | 20,079 |
| Archive 된 TSX LOC | 18,089 |
| backend/main.py 라인 감소 | 965 → 431 (-534, -55%) |
| Archive 된 SQLite | data/ontology.db (13 tables) |
| Git tag (rollback 보장) | `pre-clean-slate-2026-05-01` |
| Frontend 탭 | wiki / modeling / simulation 3개 → wiki 1개 |

## Archive 위치

`archive/2026-05-pre-clean-slate/` — `.gitignore` 처리됨 (git 추적 X)

```
archive/2026-05-pre-clean-slate/
├── backend/
│   ├── modeling/        # 11 dirs (mapping, ontology, simulation, query, impact, sweepers,
│   │                    #          gap_detection, manuals, manual_ingest, demo, api)
│   └── simulation/      # Section 3 전체 (agent, api, client, data, mock, storage, tools, visualization)
├── frontend/
│   ├── sections/
│   │   ├── ModelingSection.tsx
│   │   └── modeling/   # 27 컴포넌트
│   ├── simulation_components/
│   ├── simulation_lib/
│   └── lib_api/modeling.ts
└── data/
    └── ontology.db.snapshot   # 13 tables (business_terms, business_rules, concept_binding_proposals,
                               #            change_specs, method_anchors, code_node_meta, etc.)
```

## 보존 (가치 있음, 다음 step 에서 새 모델로 어댑터)

| 영역 | 위치 |
|---|---|
| Java parser | `backend/modeling/code_analysis/` (java_parser, parser_protocol, method_anchor, cross_file_enricher, reflection_*, spring/* 10 analyzer) |
| Persistence 인프라 | `backend/modeling/persistence/database.py` |
| 인프라 | `backend/modeling/infrastructure/` |
| Agent framework | `backend/shared/agent_framework/` |
| Contracts | `backend/shared/contracts/` |
| Section 1 (wiki) 전체 | **건드리지 않음** — `backend/wiki`, `backend/application/{wiki,agent,metadata}`, `backend/api/search.py`, frontend wiki |
| 인프라 데이터 | `data/sessions/`, `data/users.json` (auth) |

## main.py 변경

3 블록 제거:
1. **Imports** (라인 55-60) — modeling_api, simulation_api, slab_agent_router 등 6 imports
2. **Wiring** (라인 250-787) — 538 라인. Neo4j init, BusinessTerm/ConceptBinding store wiring, manual_ingest pipeline, gap_detection, anchors, rules, ontology graph, domain map, binding health, multi_impact, code_node_meta, change_specs (Section 2) + sim_client init (Section 3)
3. **Router includes** (라인 902-907) — modeling_api / gaps_api / simulation_api / slab_agent / custom_agent

Section 1 (wiki / search / agent / approval / files / metadata / conflict / lock / acl / skill / persona / auth / graph / group) 라우터 + wiring 모두 건드리지 않음.

## 검증 결과

| 검사 | 결과 |
|---|---|
| `python -c "import backend.main"` | ✓ OK (main.py 깨끗하게 import) |
| 보존 모듈 import (java_parser, spring 분석기, persistence, agent_framework, contracts) | ✓ OK |
| `tsc --noEmit` (frontend) | ✓ 에러 없음 |
| Section 1 무결성 | ✓ wiki 측 파일·라우터 그대로 |
| Git tag rollback 가능 | ✓ `pre-clean-slate-2026-05-01` |

## 영향 받은 endpoint

**제거된 라우터 (Section 2/3, 더 이상 응답 X)**:
- `/api/modeling/*` (modeling_api 전체)
- `/api/modeling/gaps/*`
- `/api/simulation/*`
- `/api/slab/*` (slab_agent)
- `/api/custom/*` (custom_agent)

**그대로 (Section 1)**:
- `/api/wiki/*`, `/api/search/*`, `/api/agent/*`, `/api/approval/*`, `/api/files/*`,
  `/api/metadata/*`, `/api/conflict/*`, `/api/lock/*`, `/api/acl/*`, `/api/skill/*`,
  `/api/persona/*`, `/api/auth/*`, `/api/graph/*`, `/api/group/*`

## 다음 step

**C2 — Code Layer 신설**: backend/modeling/code_analysis/ 의 Java 분석 출력을 새 CodeType / CodeMethod / CallSite 모델로 매핑하는 어댑터. CallSiteAnalyzer Case 1~4 자동 + Class.role / Method.role 자동 분류.

승인 시 시작.
