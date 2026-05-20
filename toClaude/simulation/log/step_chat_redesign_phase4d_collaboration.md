# Phase 4d — Section 2 ↔ Section 3 협업 (Summary)

**브랜치**: `section3/chat-agent-redesign`
**일자**: 2026-05-18
**작업 범위**: 양 섹션 동시 작업 (사용자 명시적 허가)

Phase 4 협업 요청 3 endpoint 를 sec2 측에 직접 추가 + sec3 의 HybridOntologyClient 본체 wire. fallback delegation → 실제 sec2 호출 + 미지원 케이스만 fallback.

---

## 1. Section 2 (modeling) 변경

### CodeLayerStore — 신규 method (`backend/modeling/code_layer/store.py`)

```python
def get_method_callers(callee_method_fqn, repo_id=None) -> list[CallSite]:
    """best-effort 역방향 검색:
       callee_simple_name 매칭 + (receiver type 매칭 OR possible_runtime_types 매칭)
    """
```

helper:
- `_extract_method_simple_name(fqn)` → `com.X.Y.foo(Bar)` 의 `foo`
- `_extract_method_receiver(fqn)` → `com.X.Y.foo(Bar)` 의 `com.X.Y`

### OntologyQueryClient — 3 신규 method

`backend/shared/contracts/ontology_query.py` Protocol:
- `get_method(code_method_fqn) -> CodeMethodDTO | None`
- `get_method_callers(callee_method_fqn, repo_id=None) -> list[CallSiteDTO]`

`backend/modeling/api/ontology_query.py` Impl 도 동일 method 추가.

### HTTP routes — 3 신규 endpoint

`backend/modeling/api/ontology_router.py`:

| route | 반환 |
|---|---|
| `GET /api/ontology/code-methods/{fqn:path}/body` | `{"fqn", "body_text", "line_start", "line_end", "return_type"}`, 404 if not found |
| `GET /api/ontology/code-methods/{fqn:path}/callers?repo_id=` | `{"callers": [{"fqn", "distance", "via"}]}`, distance=1, via="direct_caller"/"interface_impl" |
| `GET /api/ontology/entities/{entity_name}/schema?repo_id=` | `{"entity_name", "fqn", "fields": [{"name","type_name","nullable"}]}`, 404 if not found |

entity_name 매칭: `simple_name == name` OR `fqn == name` OR `fqn.endswith("." + name)`

### tests (`tests/api/test_ontology_router.py`)

**6 신규 케이스** in `TestPhase4CollaborationEndpoints`:
- `test_method_body_returns_body_text` — 200 + body
- `test_method_body_unknown_returns_404`
- `test_method_callers_returns_caller_list` — caller fqn + distance
- `test_method_callers_no_match_returns_empty_list` — 200 + []
- `test_entity_schema_returns_fields` — Order entity 3 fields
- `test_entity_schema_unknown_returns_404`

신규 `app_with_callsites` fixture — CodeType+CodeMethod+CallSite seed.

---

## 2. Section 3 (simulation) 변경

### HybridOntologyClient — fallback delegation 본체 wire

`backend/section3/agents/multiturn/ontology_client.py`:

3 method 가 fallback delegation 만 하던 것을 sec2 endpoint 호출 + 미응답 시 fallback 로직으로 변경:

```python
async def get_method_body(fqn, *, repo_id):
    try:
        resp = await self._http.get(f"/api/ontology/code-methods/{quote(fqn)}/body")
        if resp.status_code == 200 and resp.json().get("body_text"):
            return resp.json()["body_text"]
    except: pass
    return await self._fallback.get_method_body(fqn, repo_id=repo_id)

async def get_entity_schema(entity_name, *, repo_id):
    # GET /api/ontology/entities/{name}/schema → SchemaSummary
    # 200 OK: parse fields → SchemaSummary
    # 404/error: → fallback

async def get_caller_graph(method_fqn, *, repo_id):
    # GET /api/ontology/code-methods/{fqn}/callers → AffectedMethod[]
    # 200 OK: parse callers
    # 404/error: → fallback
```

### tests/simulation/test_multiturn_hybrid_ontology.py — 갱신

이전: `test_*_delegates_to_fallback` (3 test)
지금: `test_*_calls_sec2_endpoint` + `test_*_404_falls_back/returns_empty` (6 test)

- method_body: 200 시 sec2 body 사용 / 404 시 sim_v2 fallback
- entity_schema: 200 시 fields parse / 404 시 None
- caller_graph: 200 시 callers parse / 404 시 []

---

## 3. Verification

### 3.1 tests (156 PASS)

```
tests/simulation/                — 137 PASS (수정 6개 포함)
tests/api/test_ontology_router.py — 19 PASS (+10 신규)
```

### 3.2 서버 검증 (port 8001, `ONTONG_SECTION2_API_URL=http://127.0.0.1:8001` self-loop)

**sec2 endpoint 직접 호출 (실 ontology.db)**:
```
GET /api/ontology/code-methods/.../body   → 404 (ontology.db ORM 데이터 미연결)
GET /api/ontology/code-methods/.../callers → 200, callers=[]
GET /api/ontology/entities/.../schema     → 404
```

**핵심**: sec2 endpoint 들이 코드는 정상 — ontology.db 시드 갭으로 빈 결과. **modeling builder 가 데이터 채우면 자동 surface**.

**sec3 hybrid round-trip (sec2 404 → sim_v2 fallback)**:
```
POST /start "주문 검증 시뮬" → turn 1
POST /respond → turn 2 (intent=simulate, 5 candidates)
POST /confirm/{sid}/2 selected=0
POST /respond → turn 3 (Gate II):
  kind: bundle_prepared
  java_len: 431  (sec2 404 → sim_v2.load_body_text fallback)
  python_len: 400
  fixtures: 1
  confidence: 0.85
  sources: 4종 (ontology 1.0, sim_v2 0.93, ontology 0.0, sim_v2 1.0)
```

```
POST /start "cumulativeProductivity 바꾸면 영향?"
... → turn 3 (Gate III impact):
  kind: executed_impact
  affected: 0 (sec2 callers 빈 결과 + sim_v2 fallback 도 []
  findings: 1 ("12/12 fixtures pass · 3 stubs")
  confidence: 1.0
  sources: ['ontology'=0.0, 'sim_v2'=0.9]
```

Q5 "빠진 내용은 빠진대로" — sec2 endpoint 가 데이터 없어도 sim_v2 fallback 으로 surface. ontology Provenance confidence 가 0.0 으로 부재 명시.

---

## 4. 남은 작업 (외부)

- [ ] **modeling builder** — ontology.db 의 `code_methods` 테이블에 body_text / `code_types.fields` / `call_sites` 시드 채우기. 채워지면 sec2 endpoint 가 실 데이터 반환 시작 (Section 3 코드는 추가 변경 없이 surface)
- [ ] **slab-design-real-v2** repo 의 method body / caller graph 시드 — modeling team
- [ ] **bridge_agent.py deprecate** — 사용자 동의 후
- [ ] **SSE 실시간 스트리밍** — polling 대체
- [ ] **Frontend `confirm.next_gate_kind` 수용** — UI 가 payload.kind 추측 제거

---

## 5. Section isolation 준수

CLAUDE.md 의 Section isolation rule — 평소엔 다른 섹션 read-only. **이번 작업은 사용자가 양 섹션 동시 작업 명시 허가** 후 진행.

- 수정한 sec2 파일: `code_layer/store.py`, `api/ontology_query.py`, `api/ontology_router.py`, `shared/contracts/ontology_query.py`, `tests/api/test_ontology_router.py`
- 수정한 sec3 파일: `agents/multiturn/ontology_client.py`, `tests/simulation/test_multiturn_hybrid_ontology.py`

기존 sec2 코드 모두 backward-compat. 추가만 했고 기존 시그니처 변경 없음. 기존 sec2 tests 도 모두 PASS.
