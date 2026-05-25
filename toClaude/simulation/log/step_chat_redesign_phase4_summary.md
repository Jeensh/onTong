# Phase 4 — HTTPOntologyClient swap + state machine 명시화 (Summary)

**브랜치**: `section3/chat-agent-redesign`
**일자**: 2026-05-18
**완료 step**: P4a (HybridOntologyClient) / P4b (next_gate_kind) / P4c (verification + doc sync)

Phase 4 의 핵심 — Section 2 API 와의 점진적 연결. **하이브리드 패턴**: sec2 가 노출하는 endpoint 는 httpx wire, 그렇지 않은 endpoint 는 `SimV2BackedOntologyClient` delegate. sec2 측 endpoint 추가 시 점진적으로 fallback 에서 옮겨감.

---

## 1. P4a — HybridOntologyClient

신규 클래스 in `backend/section3/agents/multiturn/ontology_client.py`:

```python
class HybridOntologyClient:
    def __init__(self, *, base_url, http_client=None, fallback=None, timeout=10.0):
        self._http = http_client or httpx.AsyncClient(base_url=base_url, timeout=timeout)
        self._fallback = fallback or SimV2BackedOntologyClient()

    async def search_action_by_keyword(self, query, *, repo_id, top_n=5) -> list[ActionCandidate]:
        # sec2: GET /api/ontology/search?q=&repo_id=&limit=
        # 응답 (list[SearchHitDTO]) 중 kind="action" 만 필터 → ActionCandidate
        # code_method_fqn 은 search response 에 없음 → "" (후속 get_action_detail 시 보강)

    async def get_action_detail(self, action_id, *, repo_id) -> ActionRef | None:
        # sec2: GET /api/ontology/actions/{fqn} → ActionDTO
        # realizations[0].code_method_fqn 추출 (scope="primary" 우선)

    async def get_method_body(self, fqn, *, repo_id) -> str | None:
        return await self._fallback.get_method_body(fqn, repo_id=repo_id)

    async def get_entity_schema(self, entity_name, *, repo_id):
        return await self._fallback.get_entity_schema(entity_name, repo_id=repo_id)

    async def get_caller_graph(self, method_fqn, *, repo_id):
        return await self._fallback.get_caller_graph(method_fqn, repo_id=repo_id)
```

**핵심 디자인**:
- sec2 가 노출하는 2 endpoint 만 wire (search / actions/{fqn})
- 나머지 3 endpoint (method_body / entity_schema / caller_graph) 는 sec2 API 에 부재 → SimV2BackedOntologyClient delegate
- 모든 HTTP 호출은 `try/except` graceful — sec2 API 불안정 시 빈 결과 + sim_v2 fallback (Q5 "빠진 대로")
- 점진적 swap: sec2 가 endpoint 추가 시 fallback 에서 본체로 옮김 (작은 PR 단위)

**Backward-compat**: `HTTPOntologyClient = HybridOntologyClient` alias 유지

### get_ontology_client() default 분기

```python
def get_ontology_client() -> OntologyClient:
    sec2_url = os.environ.get("ONTONG_SECTION2_API_URL", "").strip()
    if sec2_url:
        return HybridOntologyClient(base_url=sec2_url)
    return SimV2BackedOntologyClient()
```

- env `ONTONG_SECTION2_API_URL` 있으면 Hybrid (sec2 + sim_v2)
- 없으면 100% SimV2BackedOntologyClient (Phase 2~3 동작 그대로)

test: `tests/simulation/test_multiturn_hybrid_ontology.py` **10 PASS**
- sec2 search endpoint wire (action 만 필터, term 제외)
- sec2 actions/{fqn} endpoint wire (realizations primary)
- 404 / 500 / 빈 응답 graceful
- method_body / entity_schema / caller_graph delegate
- custom fallback injection

---

## 2. P4b — confirm.next_gate_kind state machine 명시화

`POST /confirm/{sid}/{turn}` 의 `ConfirmResponse.next_gate_kind` 가 `None` 만 반환했음. spec v2 §2 state machine 을 explicit 계산:

```python
def _next_gate_kind(decision, action) -> str | None:
    kind = decision.gate_kind
    if kind == "target_selected":
        if action == "retry":  return "target_selected"
        if action == "confirm":
            intent = decision.payload["intent"]
            if intent == "simulate": return "bundle_prepared"
            if intent == "impact":   return "executed_impact"
            return None  # ambiguous
    if kind == "bundle_prepared":
        if action == "confirm":          return "executed_simulation"
        if action in ("modify", "retry"): return "bundle_prepared"
    # executed_* → 종료
    return None
```

이로써 UI 는 `payload.kind` 추측 안 하고 `confirm` 응답의 `next_gate_kind` 로 진행할 다음 단계 알 수 있음. 백엔드가 single source of truth.

test 5개 추가 (test_multiturn_router):
- target_selected + simulate + confirm → "bundle_prepared"
- target_selected + impact + confirm → "executed_impact"
- target_selected + retry → "target_selected"
- ambiguous + confirm → None
- bundle_prepared + confirm → "executed_simulation"

---

## 3. P4c — Verification

### 3.1 tests/simulation (137 PASS)

| 파일 | tests |
|---|---|
| 기존 9 파일 | 122 PASS |
| **test_multiturn_hybrid_ontology** | **10 신규** |
| test_multiturn_router | +5 (next_gate_kind 케이스) |

**총 137 PASS** (122 → 137, +15)

### 3.2 서버 검증

**next_gate_kind 분기**:
```
POST /confirm/{sid}/2 simulate intent → {"ok":true,"next_gate_kind":"bundle_prepared"}
POST /confirm/{sid}/2 impact intent   → {"ok":true,"next_gate_kind":"executed_impact"}
```

**Hybrid fallback (sec2 API 불가)**:
```
ONTONG_SECTION2_API_URL=http://localhost:9999 (unreachable)
POST /start "주문 검증 시뮬" → turn 1 ambiguous stub
POST /respond → turn 2 intent=simulate
  - candidates: 5 (sim_v2 fallback 동작)
  - ontology source confidence: 0.0 (sec2 호출 실패, graceful 빈 결과)
```

Q5 "빠진 내용은 빠진대로" — sec2 API 불안정해도 sim_v2 가 5 candidates 정상 surface.

---

## 4. 잔여 (Phase 4 후속)

| # | Item | Status |
|---|---|---|
| HybridOntologyClient (sec2 search + actions wire + sim_v2 fallback) | ✅ |
| confirm.next_gate_kind explicit state machine | ✅ |
| sec2 API 신규 endpoint 협업 — `method_body` / `entity_schema` / `caller_graph` | (협업 요청) |
| `data/ontology.db` 시드 (caller_graph / entity_schemas / W74 stub) | (modeling team) |
| 옛 `bridge_agent.py` deprecate | (사용자 동의 후) |
| SSE 실시간 스트리밍 — backend step events + frontend hook 전환 | (TBD) |
| `idiom_diffs` surface — Section3Translator hook | (sim_v2 협업) |
| Frontend 가 `next_gate_kind` 사용 — UI 의 payload.kind 추측 제거 | (TBD, polish) |

---

## 5. 협업 요청 (Section 2 owner)

Phase 4 의 "온전한" HybridOntologyClient wire 를 위해 sec2 측 endpoint 3개 추가 요청:

**#1 `GET /api/ontology/code-methods/{fqn:path}/body`**:
- 반환: `{"body_text": str}` 또는 404
- 현재: `SimV2BackedOntologyClient` 가 sim_v2_bridge.load_body_text 로 우회

**#2 `GET /api/ontology/entities/{entity_name}/schema`**:
- 반환: `{"entity_name", "fields": [{"name","type_name","nullable"}]}`
- 현재: 빈 결과 (Gate II 의 schema_summary 가 항상 empty)

**#3 `GET /api/ontology/code-methods/{fqn:path}/callers`**:
- 반환: `[{"fqn", "distance", "via"}]` — 역방향 caller graph (callee 의 호출자들)
- 현재: 빈 결과 (Gate III impact 의 affected_methods 가 항상 empty)

이 3 endpoint 추가 시 HybridOntologyClient 의 fallback delegation 을 본체 wire 로 교체 (작은 PR 단위로 가능).
