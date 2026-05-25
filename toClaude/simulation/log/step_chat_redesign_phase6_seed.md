# Phase 6 — modeling ontology.db 시드 (Summary)

**브랜치**: `section3/chat-agent-redesign`
**일자**: 2026-05-18
**완료 step**: P6a (seed script) / P6b (실행 + 검증) / P6c (doc sync)

Phase 4d 의 sec2 endpoint 본체 wire 가 ontology.db 빈 상태 + sec3 hybrid fallback 으로 작동 중이었음. 본 phase 에서 `slab-v2-handoff.db` 의 데이터를 `ontology.db` modeling 테이블로 migration → **sec2 endpoint 가 실 데이터 surface → sec3 hybrid 가 본체 wire 활용**.

---

## 1. P6a — seed migration script

`scripts/seed_modeling_from_sim_v2.py` 신규:

- source = `data/slab-v2-handoff.db` (sim_v2 가 build 한 38 actions / 985 methods)
- target = `data/ontology.db` (modeling 측 store, 비어있던 상태)
- 양 DB 의 modeling 측 테이블 schema 거의 동일 (PK 차이만 — slab-v2-handoff = `(fqn, repo_id)` / ontology.db = `fqn`)
- `INSERT OR IGNORE` + `PRAGMA foreign_keys = OFF` 로 PK/FK 충돌 우회
- 12 테이블 복사 (Code Layer 4 + Domain 4 + Mapping 4)

migration 결과 (`uv run python scripts/seed_modeling_from_sim_v2.py`):
```
code_types        128
code_methods      985
code_fields       560
call_sites       1290
business_terms     43
business_rules     17
actions            38
realizations       43
type_realizations  36
anchor_bindings   163
composition_edges   0 (source 비어있음)
inheritance_edges   0 (source 비어있음)
```

---

## 2. P6b — Bug fix + 검증

### get_method_callers receiver fallback

sec2 측 `CodeLayerStore.get_method_callers` 가 receiver type 일치를 요구. 그러나 시드 데이터의 `call_sites.callee_receiver_static_type` 가 일부 비어 있음 (sim_v2 parser 의 제약). best-effort fallback 추가:

```python
# 기존:
if cs.callee_receiver_static_type == receiver: out.append(cs)
elif any(c.code_type_fqn == receiver for c in cs.possible_runtime_types): out.append(cs)

# 추가:
elif not cs.callee_receiver_static_type and not cs.possible_runtime_types:
    out.append(cs)   # receiver 정보 부재 → simple_name 매칭만으로 surface
```

### 서버 검증 (port 8001, ONTONG_SECTION2_API_URL=self-loop)

**sec2 endpoint 직접 호출 (이제 실 데이터)**:
- `GET /api/ontology/actions?repo_id=slab-design-real-v2` → 38 actions
- `GET /api/ontology/actions/action.scm.product.cumulative_productivity` → label "cumulative_productivity" + 2 realizations
- `GET /api/ontology/code-methods/{fqn}/body` → body_text 431 chars + return_type "ValidationResult"
- `GET /api/ontology/code-methods/{fqn}/callers` → caller 1 ("SdDesigner.design", distance 1)

**sec3 hybrid round-trip (sec2 본체 wire 활용)**:

Gate II (simulate path):
```
sources:
  ontology 1.0  get_method_body(...)         ← sec2 body endpoint
  sim_v2   0.93 translate_java_to_python
  ontology 1.0  get_entity_schema(SDOrderEntity)  ← sec2 schema endpoint
  sim_v2   1.0  synthesize_fixtures
confidence: 1.0   (이전 fallback 시 0.85, schema 부재로 -0.15. 이제 schema surface)
```

Gate III impact:
```
affected_methods: 1 (com.example...SdDesigner.design)
confidence: 1.0
sources: ontology 1.0 + sim_v2 0.9
```

### tests
- tests/simulation 138 + tests/api/test_ontology_router 19 = **157 PASS** (변경 없음 — bug fix 가 기존 test 깨지 않음)

---

## 3. 의의

Phase 4d 가 sec2 ↔ sec3 통신 인프라를 wire 했고, Phase 6 가 그 위에 실 데이터를 흘림. 이제 **sec3 multiturn agent 의 Gate II 가 fallback 없이 sec2 ontology API 본체에서 모든 데이터 받음**:
- java body, python translation, entity schema, fixtures, caller graph 모두 confidence > 0
- ontology Provenance 가 0.0 이 아니라 1.0 으로 surface (Q5 "확실한 근거")

modeling builder 가 추가로 시드 채우거나 새 repo import 하면 자동 활용.

---

## 4. 변경 파일

- 신규: `scripts/seed_modeling_from_sim_v2.py` (sec3 영역)
- 신규: `data/ontology.db.bak-sec3-20260518-003642` (백업, gitignore 권장)
- 수정: `backend/modeling/code_layer/store.py` `get_method_callers` receiver fallback 추가 (sec2 영역)
- 데이터 변경: `data/ontology.db` (modeling 테이블 12개 채워짐)

CLAUDE.md 의 section isolation rule — 사용자가 양 섹션 동시 작업 명시 허가 후 진행. sec2 측 변경은 추가만 (backward-compat).

---

## 5. 남은 작업 (외부 의존성)

- modeling builder 의 RepoImporter 가 추가 repo import 시 ontology.db 자동 갱신 (workflow)
- W74 typed-return stub 보충 (sim_v2 — Gate III sim ERROR 케이스 감소)
- bridge_agent.py deprecate (사용자 동의 후)
- idiom_diffs surface (sim_v2 rewrite_method_invocation hook 변경)

Section 3 측 단독 코드 작업은 사실상 완료. 본 phase 의 시드까지 포함하면 multiturn agent 풀 파이프라인이 **실 데이터로 완전 작동**.
