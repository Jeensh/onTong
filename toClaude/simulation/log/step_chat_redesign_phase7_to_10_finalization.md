# Phase 7~10 — Section 3 finalization (v1 deprecate + idiom diffs + W74 typed-return + caller graph 정확도)

**브랜치**: `section3/chat-agent-redesign`
**일자**: 2026-05-18
**완료**: P7 (v1 deprecate) / P8 (idiom_diffs surface) / P9 (W74 typed-return stubs) / P10 (caller graph 정확도)

본 단계는 Phase 1~6 의 production 완료 위에서 남은 외부 의존 항목을 모두 종결.

---

## Phase 7 — bridge_agent v1 deprecate

**산출물**
- `backend/section3/agents/bridge_agent.py` — module docstring 에 deprecation banner + multiturn v2 migration path 명시
- `backend/section3/api/router.py` — `/api/section3/chat` 응답 header
  - `X-Deprecated: true`
  - `Warning: 299 - "Section 3 chat v1 is deprecated; migrate to /api/section3/multiturn/* (Phase 1~6 complete)"` (RFC 7234)
  - `X-Deprecation-Date: 2026-05-18`
  - `X-Replacement: /api/section3/multiturn/start`
- `frontend/src/components/section3/BridgeChatPanel.tsx` — 상단에 dismissible 한 amber 색 deprecation banner. multiturn 으로 가는 "/?view=multiturn" 링크.
- `frontend/src/components/section3/Section3Section.tsx` — nav 라벨 변경: "멀티턴 chat (v2 권장)" / "v1 chat (deprecated)".
- `tests/simulation/test_section3_v1_deprecation.py` 신규 — 2 tests
  - `test_chat_v1_emits_deprecation_headers` — 4종 header surface 확인
  - `test_chat_v1_still_streams_body` — SSE 본체 동작 유지

backward-compat 유지 — 기존 호출자가 v1 endpoint 를 그대로 사용 가능, 다만 응답에 deprecation 메타 동봉.

---

## Phase 8 — idiom_diffs surface

**문제**: Gate II 의 `GateBundle.idiom_diffs` 가 항상 빈 리스트. W75 idiom rewriter 가 50+ Java idiom 을 자동 rewrite 하면서도 어떤 idiom 이 적용됐는지 surface 안 함.

**해결**
- `backend/sim_v2/core/synthesizer/idiom_rewriter.py` — `rewrite_method_invocation(..., trace=None)` 의 새 kwarg. 매칭 시 `{idiom_name, java_snippet, python_snippet, tier, arity}` dict 를 trace 에 append.
- `backend/sim_v2/core/synthesizer/java_translator.py`
  - `JavaToPythonTranslator.__init__` 에 `self._idiom_trace: list[dict] = []`
  - `translate()` 에서 `_idiom_trace` reset
  - `_translate_method_invocation` 에서 `rewrite_method_invocation(..., trace=self._idiom_trace)` 호출
  - `TranslationResult.idiom_rewrites` 신규 필드 (default_factory=list)
- `backend/section3/sim_v2_bridge.py` — `translate_java_to_python` 반환을 `(src, fn)` 2-tuple → `(src, fn, idiom_rewrites)` 3-tuple 로 확장. backward-compat fallback 도 gate_ii 에 추가.
- `backend/section3/agents/multiturn/gate_ii.py` — translated 가 3-tuple 일 때 idiom_rewrites 추출 → `_extract_idiom_diffs(...)` 가 IdiomDiff[] dedup 후 GateBundle 에 surface.
- `frontend/src/components/section3/multiturn/GateBundleCard.tsx` — 새 "Idiom diff" tab. java→python 매핑 표.

**tests 추가**
- `backend/sim_v2/tests/core/synthesizer/test_w75_idiom_rewriter.py` +6 — trace 기능 검증 (static/typed/unknown tier, non-match, accumulate, no-kwarg compat)
- `tests/simulation/test_multiturn_gate_ii.py` +3 — 3-tuple consumption, dedup, 2-tuple backward-compat

**효과**: 사용자가 Java body 와 Python 변환만 보고 "왜 다른지" 추측하던 것 → "어떤 Java idiom 이 어떤 Python 패턴으로 변환됐는지" 명확.

---

## Phase 9 — W74 typed-return stubs (FAIL_RETURN_TYPE 감소)

**문제**: `BehaviorTwinRunner` 가 stubbed bean 의 method 호출 결과를 MagicMock 으로 받음. 호출자가 그 값을 string/int/BigDecimal 로 사용하면 `_output_type_ok` 의 invariant check 에서 FAIL_RETURN_TYPE.

**해결**
- `backend/sim_v2/core/verification/sandbox_stubs.py`
  - `_typed_default_for(rt)` — Java return-type → typed Python default 매핑
    - `String` → `""`, `int/Integer/long/Long/short/byte` → `0`, `boolean` → `False`, `float/double` → `0.0`, `BigDecimal/BigInteger` → `Decimal("0")`, `List/Set/...` → `[]`, `Map/...` → `{}`, `Optional` → `None`, `void` → None (skip), 도메인 타입 → None (MagicMock 유지)
  - `derive_method_return_defaults(session, repo_id)` — `code_methods.return_type` 전체 스캔 → simple_name 별로 typed default 누적. 같은 simple_name 에 다른 family 가 있으면 drop (ambiguous), 같은 family 면 keep.
  - `_install_typed_returns(stub, defaults)` — stub 의 각 method 이름에 typed default 설치
  - `derive_class_stub`, `derive_entity_stub_from_code_types`, `derive_repository_stub` 에 optional `method_return_defaults` kwarg
  - `build_stub_namespace`: defaults 미지정 시 자동으로 `derive_method_return_defaults` 호출 (graceful failure → 빈 dict)
- `backend/sim_v2/tests/core/verification/test_w74_sandbox_stubs.py` +7 — 5가지 primitive 매핑 / overload ambiguity 해소 / generics 처리 / repository+class+namespace 통합

**효과**: 실제 production 메서드 (예: `OrderService.process()` 가 `orderRepo.getCmpCd()` 의 결과를 String 으로 사용) 호출 시 stub 가 빈 string 반환 → FAIL_RETURN_TYPE invariant 통과. Gate III sim 의 ERROR 사례 자연 감소.

---

## Phase 10 — caller graph 정확도

**문제**: 시드된 `call_sites` 의 모든 1290 row 에서 `callee_receiver_static_type` + `possible_runtime_types` 가 비어있음 (parser 한계). 결과적으로 모든 caller graph query 가 best-effort `simple_name` 매칭만 사용 — 흔한 메서드명 (`equals`, `validate`, `getCmpCd`) 에 대해 false positive 다수.

**해결: 5단계 match_kind heuristic**
- `backend/modeling/code_layer/store.py` — `get_method_callers_with_match(callee_method_fqn, repo_id=None) -> list[tuple[CallSite, str]]` 신규
  - `receiver_exact` — `callee_receiver_static_type == receiver_fqn` (strength 0.95)
  - `receiver_short` — `callee_receiver_static_type == receiver_short` (parser 가 short name 만 잡은 경우, strength 0.85)
  - `runtime_type` — possible_runtime_types 중 fqn 또는 short-name 매칭 (strength 0.85)
  - `package_proximity` — receiver/caller package 가 일치 (parser 가 receiver 못 잡았을 때, strength 0.70)
  - `name_only` — simple_name 만 일치 (best-effort fallback, strength 0.50)
- `get_method_callers` 는 thin wrapper 로 유지 (backward-compat)
- `backend/modeling/api/ontology_router.py` — `/api/ontology/code-methods/{fqn}/callers` 에 `match_kind` + `strength` 노출. caller 중복은 가장 강한 match_kind 만 surface. `min_strength` query param 으로 약한 신호 필터링 가능.
- `backend/section3/agents/multiturn/schemas.py` — `AffectedMethod` 에 optional `match_kind`, `strength` 추가
- `backend/section3/agents/multiturn/ontology_client.py` `HybridOntologyClient.get_caller_graph` — sec2 응답의 match_kind/strength 를 AffectedMethod 에 carry
- `frontend/src/lib/section3/multiturn.ts` — `AffectedMethod` 인터페이스에 두 필드 추가
- `frontend/src/components/section3/multiturn/GateExecutedImpactCard.tsx` — affected methods 표에 "match" + "신뢰" 컬럼 추가

**tests 추가**
- `tests/code_layer/test_store.py` +6 (`TestCallerGraphMatchKind`) — 5가지 match_kind + thin wrapper compat. FK 만족용 helper `_types_with_caller_method()`.
- `tests/api/test_ontology_router.py` +2 — match_kind + strength surface, min_strength 필터.

**효과**: 시드 데이터처럼 parser 가 receiver 정보 부재여도 package proximity 가 같은 module 의 caller 를 더 높은 신뢰도로 surface. UI 에서 "주의: name_only" 매치는 회색 처리 가능 (현재는 표시만, threshold 는 caller 가 결정).

---

## 통합 test 결과

**focused suite** (synthesizer + simulation + ontology_router + W74 + caller_graph):
```
uv run --no-sync python -m pytest \
  backend/sim_v2/tests/core/synthesizer/ \
  backend/sim_v2/tests/core/verification/test_w74_sandbox_stubs.py \
  tests/simulation/ \
  tests/api/test_ontology_router.py \
  tests/code_layer/test_store.py::TestCallerGraphMatchKind \
  -q

→ 619 passed in ~33s
```

기존 545 (Phase 6 end) + W75 trace 6 + gate_ii 3 + W74 typed 7 + ontology_router 2 + caller_graph 6 + v1_deprecation 2 = **571 / 619 합산**.

production_db / schema_layer_migration 의 사전-존재 실패는 별개 — slab-design-real 시드 / alembic 설치가 필요한 외부 의존 항목.

**frontend tsc**: clean (EventStreamView.tsx 의 사전 존재 오류 제외).

---

## 남은 작업 (외부 의존)

- **sim_v2 parser callsite receiver type 추출 정확도** — 현재 1290 row 가 모두 빈 receiver. parser 측 작업 (협업 필요).
- **alembic / production_db 시연** — `tests/sim_v2/.../test_production_*` 가 의존하는 외부 데이터 시드 (별도 ticket).

[[project-chat-redesign-phase6-seed]] · [[project-chat-redesign-phase5-polish]]
