# Section 3 — Simulation HANDOFF

섹션 담당: 시뮬레이션 Claude 세션
쓰기 영역: `toClaude/simulation/`, `backend/simulation/`, `backend/shared/contracts/{ontology,simulation}.py`
읽기 전용: `toClaude/wiki/`, `toClaude/modeling/`, `toClaude/_shared/`, `backend/modeling/api/{ontology_query, ontology_router}` (DTO + facade 만)

## 현재 상태 (2026-05-16)

**브랜치**: `section3-integration` — origin/main 머지 완료 (commit `0e72d8a`) + Sprint 1 통합 진행 후

**최근 완료 (Section 4 인계 Sprint 1~5, 2026-05-16)**:

| Sprint | 작업 | 상태 |
|---|---|---|
| 1 | recipe-4 full pipeline (W71→W75→W74→W72) | ✅ 12/12 cumulativeProductivity PASS |
| 2 | recipe-2 Java baseline + sandbox 표 expected 컬럼 | ✅ file-based load_baseline_map + BehaviorTwinRunner 경로 |
| 3 | recipe-3 invariant 진단 → chat fallback surface | ✅ quick_diagnose_action + simv2_suggestions 이벤트 |
| 4 | recipe-5 W77+W78 한국어 검색 → bridge | ✅ find_action_candidates (term + LIKE) |
| 5 (opt) | transpiler 옵션 B (sim_v2 subclass) | ✅ Section3Translator 동적 subclass |

- 신설 파일: `backend/section3/sim_v2_bridge.py` (16 public 심볼) · `backend/section3/section3_translator.py` · `tests/simulation/test_sim_v2_bridge.py` (13 test) · `data/baselines/README.md`
- 수정 파일: `backend/section3/agents/{sandbox,bridge}_agent.py` · `frontend/src/components/section3/EventStreamView.tsx`
- 데모 6종 sanity check 완료 (UC36/37/38/40/41/42 + bonus recipe-5)
- 백엔드 재기동 후 /health 200, 프론트 3000 동작

**이전 완료 (2026-05-10)**:
- main 머지 / sample-repos main 100% 정렬 / 인계 검증 9/9
- STEP 3a-f 종결 (ChangeSpec/SimResult/Runner/Orchestrator/RunHandle/spec_router/ontology evidence)
- 백엔드 simulation 패키지 (sandbox / agents / transpile / jvm_bridge) + 프론트 27 패널 + 9 lib API

## 다음 세션 첫 작업

Section 4 인계 Sprint 1~5 모두 완료. 다음 후보:

1. **W74 typed-return stub** — `BehaviorTwinRunner` 의 FAIL_RETURN_TYPE 케이스 (UC40 의 5건 中 3건) close. sim_v2 측 작업이라 협업 필요.
2. **impact_analysis [LOW] fallback** — bridge_agent 의 `impact_analysis` 분기도 `_emit_simv2_suggestions` surface (현재는 simulate 만)
3. **legacy transpiler.py 정리** — ontology.db 비어 있어 미사용. 안전 제거 + composer 경로 deprecate
4. **`data/ontology.db` 시드 작업** — modeling 측에 v2 데이터 import 요청 (현재 ontology.db 0 actions)
5. **frontend SandboxPanel** — chat 이외 sandbox 직접 진입점에서 sim_v2 후보 검색 surface (현재는 BridgeChatPanel 만)

데이터 사실:
- `data/ontology.db` (316KB) — 비어 있음 (0 actions)
- `data/slab-v2-handoff.db` (3.4MB) — slab-design-real-v2 38 actions · 유일한 실측 데이터 소스
- legacy `/api/ontology/*` HTTP 는 빈 DB 를 가리키므로 sim_v2 직통이 사실상 primary 경로

## 환경 설정 메모

- 백엔드 실행: `venv/` (`.venv/`가 아님). uvicorn `backend.main:app --host 0.0.0.0 --port 8001`
- 프론트엔드: port 3000, Next.js rewrite `/api/*` → `http://localhost:8001/api/*`
- slab-design (Java legacy 데모): port 8080, `--spring.profiles.active=h2` (단, **`sample-repos/slab-design/` 폴더 제거됨** — 통합 작업 시 `slab-design-real_v2/` 와 매핑 결정 필요)
- ontology 데이터: `data/ontology.db` (read-only ground truth, 80MB SQLite, 9/9 검증 통과)
- 시뮬 결과 저장: `backend/simulation/data/storage.db` 또는 신설 (modeling DB 와 분리)

## Section 2 통합 인터페이스

| 통합 지점 | 사용할 API |
|---|---|
| ontology Core query | `from backend.modeling.api.ontology_query import OntologyQueryClientImpl` (Python facade, DTO 만) |
| 또는 HTTP | `GET http://localhost:8001/api/ontology/{terms,actions,business-rules,anchor-bindings,...}` |
| 금지 (CI 차단) | `backend.modeling.{mapping_layer,domain_layer,code_layer,persistence}.*` — `tools/check_agent_isolation.py` 가 검사 |

## 환경 의존성 (main 통합 시 추가 설치된 것)

```
sqlalchemy, alembic, anthropic, sqlglot, hypothesis, fakeredis, pytest-postgresql, locust,
pydantic-ai-slim[anthropic]
+ frontend: elkjs, @xyflow/react
```
