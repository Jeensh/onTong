# Step C5 — Query API (Agent Boundary 확정)

**완료**: 2026-05-02
**기반 결정**: 사용자 지침 (Agent 분리 — Plugin 방식, Core internal import 차단)

## 산출물 요약

| 항목 | 수치 |
|---|---|
| 새 모듈 | 4 (contracts/ontology_query, api/ontology_query, api/ontology_router, agents/AGENT_GUIDE) |
| 도구 | `tools/check_agent_isolation.py` |
| Tests (tests/api/) | 3 파일, **29/29 PASSED** |
| 누적 (C2~C5) tests | **121/121 PASSED** (1.38s) |
| REST endpoints | 16개 등록 (`/api/ontology/*`) |

## 디렉토리

```
backend/shared/contracts/
├── __init__.py             # public re-export
└── ontology_query.py       # DTO alias + OntologyQueryClient Protocol

backend/modeling/api/
├── __init__.py
├── ontology_query.py       # OntologyQueryClientImpl (facade)
└── ontology_router.py      # FastAPI router /api/ontology/*

backend/agents/
└── AGENT_GUIDE.md          # 새 agent 작성 규칙 (예시 포함)

tools/
└── check_agent_isolation.py # 정적 검사 도구 (CI 호환)

tests/api/
├── test_ontology_query_facade.py  # 16 facade tests
├── test_ontology_router.py        # 9 REST tests (TestClient)
└── test_isolation_tool.py         # 4 isolation 도구 tests
```

## OntologyQueryClient Protocol — 16 method

| 영역 | 메서드 |
|---|---|
| Term | `get_term`, `list_terms`, `effective_parts`, `resolve_path` |
| Code | `get_code_type`, `list_code_types`, `get_call_sites` |
| Action | `get_action`, `list_actions`, `get_realizations_for_input_type` |
| Anchor | `get_anchor_bindings_for_action`, `_for_method` |
| Queue | `list_unmapped_methods`, `list_ambiguous_call_sites`, `get_verification_progress` |
| Search | `search` (FTS-like, in-memory + score 정렬) |

모든 메서드 — Python facade + REST endpoint 동일 시그니처. OpenAPI spec 자동 생성 (`http://host/docs`).

## DTO 전략

Internal Pydantic model 들을 `backend/shared/contracts/ontology_query.py` 에서 alias 로 re-export:

```python
from backend.modeling.code_layer.schema import (
    CodeType as CodeTypeDTO,
    CodeMethod as CodeMethodDTO,
    CallSite as CallSiteDTO,
)
```

장점: 코드 중복 0, frozen=True 정합 자동, 모델 변경 시 contract 하나만 수정.
한계: field 제거/이름 변경 시 contract bump 필요 (이건 일반적인 API 진화 비용).

추가 DTO (Query 전용): `VerificationProgressDTO`, `SearchHitDTO`, `AmbiguousCallSiteDTO` (caller 컨텍스트 + LLM 추천 hook), `UnmappedMethodDTO`.

## REST routes (16개)

```
GET  /api/ontology/terms                                 list_terms
GET  /api/ontology/terms/{fqn}                           get_term
GET  /api/ontology/terms/{term_fqn}/effective-parts      effective_parts
GET  /api/ontology/code-types                            list_code_types
GET  /api/ontology/code-types/{fqn}                      get_code_type
GET  /api/ontology/code-methods/{fqn}/call-sites         get_call_sites
GET  /api/ontology/code-methods/{fqn}/anchor-bindings    get_anchor_bindings_for_method
GET  /api/ontology/actions                               list_actions
GET  /api/ontology/actions/{fqn}                         get_action
GET  /api/ontology/actions/{fqn}/realizations-for-input  dispatch
GET  /api/ontology/actions/{fqn}/resolve-path            resolve_path
GET  /api/ontology/actions/{fqn}/anchor-bindings         get_anchor_bindings_for_action
GET  /api/ontology/queue/unmapped-methods                list_unmapped_methods
GET  /api/ontology/queue/ambiguous-call-sites            list_ambiguous_call_sites
GET  /api/ontology/queue/verification-progress/{repo}    get_verification_progress
GET  /api/ontology/search                                search
```

**라우팅 주의**: catchall (`{fqn}`) 보다 specific suffix (`/effective-parts`, `/resolve-path`, `/anchor-bindings`) 가 먼저 등록되도록 순서 조정 (FastAPI 매칭 순서 의존).

## Agent isolation 정적 검사

`tools/check_agent_isolation.py`:

| 차단 | 허용 |
|---|---|
| `backend.modeling.{code,domain,mapping}_layer.*` | `backend.shared.contracts.*` |
| `backend.modeling.persistence.*` | `backend.shared.agent_framework.*` |
| `backend.modeling.code_analysis.*` | `backend.shared.*` |
| `backend.modeling.api.*` | 자기 폴더 (`backend.agents.<self>.*`) |
| `backend.application.*` (Section 1) | 표준 lib + pip deps |

위반 시 `exit 1` + 위반 line 정확히 출력. CI / pre-commit 통합 가능.

## main.py wiring

```python
from backend.modeling.api import ontology_router as ontology_query_api
from backend.modeling.persistence.database import bootstrap_database

# startup:
from backend.modeling.code_layer import orm as _code_orm
from backend.modeling.domain_layer import orm as _domain_orm
from backend.modeling.mapping_layer import orm as _mapping_orm
bootstrap_database()
ontology_query_api.init()

# routers:
app.include_router(ontology_query_api.router)
```

Section 1 wiring 절대 안 건드림.

## 검증

| 검사 | 결과 |
|---|---|
| `pytest tests/api/` | **29/29 PASSED** (0.88s) |
| 누적 `pytest tests/{code,domain,mapping}_layer tests/api/` | **121/121 PASSED** (1.38s) |
| `python -c "import backend.main"` | ✓ OK (16 ontology routes 등록) |
| `tools/check_agent_isolation.py` | ✓ OK (agents 폴더 없음, skip 통과) |
| `frontend tsc --noEmit` | ✓ 에러 없음 |

## 다음 step

**C6 — Workbench UI**. 5-mode rail 폐기 후 통합 화면 재구성 + UX 이터레이션 (gstack `/design-shotgun`, `/browse`, `/design-review`, `/qa` 활용). 6 sub-step + N회 사용자 피드백 사이클.

승인 시 시작.
