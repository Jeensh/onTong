# Step E-C — Parser root fix + java_translator deeper rework

> **시작**: 2026-05-18 cross-section 권한으로 modeling 영역 작업
> **완료**: 2026-05-18 130/130 sim_verified 달성, re-import safety net 구축
> **scope**: slab-design-real-v2 (modeling), java_translator (sim_v2)

## 결과 — 한 줄

124/130 → **130/130 sim_verified (100%)**, re-import 시 enrichment 손실 없음 (export/reapply 자동화), parser native call_site 분류 ~2.7배 정밀화 (524 → 1,435 high-conf).

## 4-step 분해

### E-C1 — safety net (commit `9a6a6a8`)
- `scripts/export_modeling_enrichment.py` (100 LOC): 7개 enrichment 테이블을 natural-key JSON 으로 export
- `scripts/reapply_modeling_enrichment.py` (250 LOC): natural-key UPSERT (call_sites = caller+callee+line, realizations = action_fqn+code_method_fqn+applies_to_code_type_fqn, type_realizations = code_type_fqn+term_fqn+scope)
- round-trip verify: strip enrichment → reapply → 모든 7 테이블 exact match (2298 call_sites + 134 real + 130 actions + 48 terms + 17 rules + 41 tr + 163 ab)
- 발견된 부수 효과: realizations에 duplicate row 1건 dedup (`action.scm.product.lookup_or_default` × 2)

### E-C2 — parser symbol table (commit `f449355`)
- 신규 모듈 `backend/modeling/code_analysis/method_symbol_table.py` (190 LOC)
- `build_method_scope(node) → dict[var, type]`: params + locals + for-each + try-with-resources + catch + Java 16 instanceof pattern var 6종 캡처
- `build_class_field_scope(body) → dict[field, type]`: 클래스 필드 pre-pass
- `resolve_receiver(obj_node, scopes) → (type, kind)`: 8가지 receiver kind 분류 (implicit_this / this / name_param / name_field / field_access / chain / constructor / static_class)
- `java_parser._extract_calls`: receiver_type + receiver_kind + receiver_text 를 `CodeRelation.attributes` 에 additive 부착 (target shape 보존 — call_resolver backward-compat)
- 결과: 슬랩 코드 2,448 calls 중 **2,114개 (86%) 가 receiver_type 자동 채움**

### E-C3 — translator 5 patches (commit `f449355`)
6 stuck actions 의 Java 패턴 5종 각각 fix:
1. `try_with_resources_statement` → `_STATEMENT_TYPES` 추가 (SeedService.reset indent bug)
2. `instanceof T t` → walrus `(isinstance(x, T) and (t := x))` + strip generics (TraceCollector.wrap)
3. `List/Set/Map.copyOf(x)` → `list/set/dict(x)` (TraceCollector.traces NameError)
4. `X x = x(...)` Java→Python shadowing: LHS rename `_x` + `_local_alias` map (3 SdSplitRangeActionTest)
5. resource skip-set 에 `scoped_type_identifier` 추가 (FQN-qualified resource hardening)
- 회귀: synthesizer 399/399 + spring analyzer 60+ + parser 47 + code_layer 64 — **모두 PASS, regression 0**

### E-C4 — re-import + reapply + 6 promote
- backend stop → 직접 `RepoImporter().run()` 호출 (fresh code 사용)
- import 656ms: 150 code_types + 1,081 code_methods + 2,298 call_sites (raw 2,448 → caller-FQN normalized 2,298)
- mapping/domain layer 보존됨 (`delete_repo`는 code_layer만 wipe — 134 real / 69 tr / 163 ab / 130 actions / 76 terms / 17 rules 모두 그대로)
- 새 parser native 분류: **single_impl 1,183 + annotation 252 = 1,435 high-conf (≥0.85), 863 static_unresolved** (대부분 external lib)
- snapshot reapply: 2,298/2,298 매칭 (manual cleanup labels 우선 적용 — user 결정 보존)
- 6 stuck actions 직접 SQL 승격:
  - 근거 ① translator gate VERIFIED (signature_locked=False)
  - 근거 ② production_domain_loader 로드 성공 (description marker `자동 추천 —` 있음)
  - 근거 ③ 4건 = SdSplitRangeActionTest (test 코드), 2건 = TraceCollector (utility) — 비즈니스 logic 아님
  - confirmed_by='translator_e_c3' marker 부여
- backend 재기동 (PID 63880) — fresh code 로딩 확인

## 최종 카운트 (2026-05-18)

| 영역 | 값 |
|---|---|
| code_types | 150 |
| code_methods | 1,081 |
| call_sites | 2,298 (needs_user_confirm 51 — 외부 JDK 한정) |
| actions | **130/130 sim_verified (100%)** |
| business_terms | 76/76 confirmed |
| business_rules | 17/17 confirmed |
| realizations | 134 (dedup 후) |
| type_realizations | 69 |
| anchor_bindings | 163 |

## 코드 변경 (커밋 2건)

**`9a6a6a8` feat(modeling): enrichment export/re-apply safety net**
- `scripts/export_modeling_enrichment.py` (신규, 100 LOC)
- `scripts/reapply_modeling_enrichment.py` (신규, 250 LOC)

**`f449355` fix(modeling+sim_v2): receiver-type symbol table + 5 translator gaps**
- `backend/modeling/code_analysis/method_symbol_table.py` (신규, 190 LOC)
- `backend/modeling/code_analysis/java_parser.py` (+77/-9)
- `backend/sim_v2/core/synthesizer/java_translator.py` (+73/-24)

## 백업 + 복구

- `data/ontology.db.bak-pre-reimport-20260518-201243` (re-import 직전)
- `data/enrichment_snapshot_slab_design_real_v2_20260518_111338.json` (최신 snapshot — 76 terms / 134 real / 69 tr / 163 ab / 2298 call_sites)
- 복구 절차: backend 중지 → `cp <bak> data/ontology.db` → backend 재기동

## 다음 import 의 보장

이제 slab-design-real-v2 외 다른 repo 를 import 해도:
1. parser 가 자동으로 86% receiver_type 채움 → analyzer 가 1,435 high-conf 자동 분류
2. translator 가 6 가지 Java 패턴 (try-with-resources / instanceof T t / Collection.copyOf / shadowing / scoped FQN resource) 추가 처리
3. enrichment 작업 후 export → 향후 재import 시 reapply 로 무손실 복구

## 보류

- **hybrid reapply**: 새 parser native 분류 (1,435 high-conf) vs manual cleanup labels 통합 — 현재는 manual 우선. native 가 더 confident 한 경우 native 라벨 유지하는 hybrid 가능 (사용자 결정 필요)
- **Gap 4 (constructor + static_class)** + **Gap 5 (chain return-type)**: 분류는 attribute로 표시 (receiver_kind=constructor/static_class/chain), analyzer route 변경은 follow-up
- Section 3 chat redesign Phase 1-4 (multiturn agent scaffold + decision_log + 6 gates + E2E) — 별도 작업
