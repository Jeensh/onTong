# Section 2 모델링 + 온톨로지 핸드오프 (2026-05-20)

> **브랜치**: `share/section2-modeling-foundation`
> **From**: jeensh (modeling + simulation 작업자)
> **For**: 시뮬레이션 담당 개발자
> **목적**: 동일 modeling Section 2 위에서 본인 시뮬레이션 에이전트를 Section 3 의 탭으로 자유롭게 추가/수정할 수 있도록 공유

## 한 줄 요약

slab-design-real-v2 기준 **136/136 actions sim_verified, 1,472 high-conf call_sites, 76 confirmed terms, 148 realizations** 까지 정리 완료. parser 가 import 시 86% receiver_type 자동 채움 + translator 5 patches + re-import safety net + Authoring 인터뷰 flow 안정화. 본인 에이전트를 Section 3 탭으로 추가 시 base 로 가져다 쓸 수 있는 상태.

---

## 가져갈 것

### 코드 (이미 main 또는 이 브랜치에 머지됨)

**Section 2 (modeling) — 핵심 업그레이드**
- `backend/modeling/code_analysis/method_symbol_table.py` (신규, 190 LOC) — per-method symbol scope (params + locals + for-each + try-with-resources + catch + Java 16 instanceof pattern var + class field)
- `backend/modeling/code_analysis/java_parser.py` — `_extract_calls` 가 `attributes["receiver_type"]` + `receiver_kind` + `receiver_text` additive 부착. target shape 보존 (call_resolver backward-compat).
- `backend/modeling/code_layer/importer.py` — Gap 5 chain return-type post-pass (`_resolve_chain_receivers` 2-level iter).
- `scripts/export_modeling_enrichment.py` + `scripts/reapply_modeling_enrichment.py` — re-import 안전망 (natural-key UPSERT, `--hybrid` mode 로 native high-conf 보존).
- `scripts/close_risk4_audit.py` — 6 new actions + 14 new realizations (SdDesigner orchestrator + SdSlabSaveAction projection + 5 DG production validators).
- `scripts/verify_stuck_actions_runtime.py` — translator 6 케이스 runtime exec 검증.

**sim_v2 — translator + verifier 5 patches**
- `backend/sim_v2/core/synthesizer/java_translator.py` — try-with-resources / `instanceof T t` walrus / Collection.copyOf / LHS shadowing rename / scoped FQN resource + `class_field_scope` 인자 (implicit-this 필드 → `self.X`).
- `backend/sim_v2/core/verification/action_method_verifier.py` — `_load_class_field_scope` 로 code_fields 에서 자동 로드.

**Section 3 — 멀티턴 chat 에이전트 (참고용, 본인 에이전트 탭과 같이 둘 base)**
- `backend/section3/agents/multiturn/` — 6-gate state machine (intent / target / code / python / fixtures / sandbox) + Phase 13a (locate/explain) + 13b (search_terms) + 13c (hypothesis + conditions)
- `backend/section3/api/multiturn_router.py` — 4 endpoint (`/start`, `/respond`, `/confirm`, `/session/{sid}` + `/stream`)
- `frontend/src/components/section3/multiturn/` — `MultiturnChat` 컨테이너 + 5 카드 컴포넌트 + Zustand store
- 222 tests PASS (multiturn 영역)

### 데이터 (`data/ontology.db` — 백업 권장)

slab-design-real-v2 기준 현재 카운트:

| 영역 | 값 |
|---|---|
| code_types | 150 |
| code_methods | 1,081 |
| call_sites | 2,298 (needs_user_confirm 51 = 외부 JDK only) |
| **actions** | **136 / 136 sim_verified (100%)** |
| business_terms | 76 (all confirmed) |
| business_rules | 17 (all confirmed) |
| realizations | 148 |
| type_realizations | 69 |
| anchor_bindings | 163 |

백업:
- `data/ontology.db.bak-pre-reimport-20260518-201243` — re-import 직전
- `data/ontology.db.bak-pre-hybrid-*` — hybrid reapply 직전
- `data/enrichment_snapshot_slab_design_real_v2_20260518_115945.json` — 최신 snapshot (모든 enrichment + sim_verified state)

---

## 재import 시 enrichment 무손실 절차

1. backend 중지 (DB lock 해제)
2. **백업**: `cp data/ontology.db data/ontology.db.bak-pre-myreimport-$(date +%Y%m%d-%H%M%S)`
3. **export 최신**: `.venv/bin/python scripts/export_modeling_enrichment.py --repo-id slab-design-real-v2`
4. re-import (UI Import 버튼 or `RepoImporter().run(ImportJob(...))`)
5. **hybrid reapply** (native parser 분류 보존): `.venv/bin/python scripts/reapply_modeling_enrichment.py --db data/ontology.db --snapshot <최신>.json --hybrid`
6. backend 재기동

`--hybrid` 가 핵심 — manual cleanup labels 우선이 아니라, native parser 가 single_impl/annotation 으로 ≥0.85 conf 분류한 행은 그대로 두고, static_unresolved 만 snapshot 으로 채움. slab-design 기준 1,435 행 native 보존 + 853 행 manual fill.

---

## 본인 에이전트를 Section 3 탭으로 추가

현재 Section 3 UI 진입점: `frontend/src/components/section3/Section3Section.tsx`. nav 가 이미 여러 view (`dashboard / multiturn / ...`) 를 갖고 있어서 본인 에이전트 view 추가는 간단:

1. **백엔드 진입점 분리** — 본인 agent 의 `/api/section3/myagent/*` router 신설. multiturn router 와 같은 패턴 (`backend/section3/api/multiturn_router.py` 참고).
2. **frontend** — `frontend/src/components/section3/myagent/` 폴더 신설 (multiturn/ 폴더 패턴 참고). `Section3Section` 의 nav 에 탭 추가.
3. **데이터 공유** — `ontology.db` 와 `code_types/code_methods/business_terms/business_rules/actions/realizations/...` 테이블 직접 읽기. `backend/sim_v2/core/ontology/domain_layer/production_domain_loader.py` 의 `load_actions(session, repo_id)` 가 130+ actions 를 다 surface 하므로 그대로 사용 가능.

---

## 검증된 sim 흐름 (재사용 가능)

- `backend/sim_v2/core/synthesizer/java_translator.py` — Java method → Python source. 130 actions 모두 valid Python emit.
- `backend/sim_v2/core/verification/action_method_verifier.py` — translator gate (signature_locked 판정). 130 actions 모두 VERIFIED.
- `backend/sim_v2/core/verification/sandbox_stubs.py` `build_stub_namespace()` — stubs 자동 합성.
- `backend/sim_v2/core/verification/behavior_twin_runner.py` `BehaviorTwinRunner.run_fixture()` — 실 exec.
- 6 (예전 stuck) actions runtime 검증: `PYTHONPATH=. .venv/bin/python scripts/verify_stuck_actions_runtime.py`

---

## 주요 commit (이 브랜치 기준)

```
5d2b11a fix(authoring): interview button activation + light-theme amber contrast
ebd741d fix(modeling+sim_v2): close 5 demo risks → 136/136 sim_verified, 1472 high-conf calls
f449355 fix(modeling+sim_v2): receiver-type symbol table + 5 translator gaps
9a6a6a8 feat(modeling): enrichment export/re-apply safety net
344ba1a fix(sim_v2): java translator gaps + loader realizations fallback
848d61d docs(simulation): modeling data full audit + enrichment report
```

(main 부터 이 브랜치까지 약 1,650 파일 / 128k 라인 — Section 3 chat redesign 작업 포함)

---

## 관련 문서

- `toClaude/simulation/MODELING_DATA_AUDIT.md` — Phase A~E + E-C arc 전체 요약 (130/130 sim_verified 도달 과정)
- `toClaude/simulation/log/step_ec_parser_translator_rework.md` — E-C arc 단계별 분해 (E-C1~E-C4)
- `toClaude/simulation/HANDOFF.md` — Phase 13a/b/c 기준 다음 작업 후보 6개 (Section 3 측)
- `toClaude/modeling/CHANGES.md` — 모델링 측 cross-section 작업 로그
- `toClaude/_shared/agent_tools_schema.md` — agent 가 호출 가능한 ontology tool 카탈로그

---

## 보류 / 후속

- **hybrid reapply 디폴트화**: 현재는 `--hybrid` flag 명시 필요. 일반화 후 default 로 전환 검토.
- **Gap 4 (constructor + static_class) analyzer route**: 분류 attribute 는 부착되나 analyzer 가 `AUTO_FILTERED_STDLIB` route 로 routing 하지 않음. 추가하면 51 deferred 더 줄어듬.
- **Section 3 chat 의 LLM intent classifier**: `OPENAI_API_KEY` 가 .env 에 있어야 candidates 가 채워짐. backend 가 dotenv 로드하는지 확인 필요.
- **2 개 시뮬레이션 에이전트 탭 공존 디자인**: nav + URL routing + 세션 분리 정책 합의 필요. multiturn 의 `?sid=` URL 추적 패턴 참고.
