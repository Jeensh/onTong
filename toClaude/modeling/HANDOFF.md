# 세션 인계 문서 (HANDOFF)

> 다른 환경에서 이어서 작업할 때 Claude가 가장 먼저 읽어야 하는 파일.
> 사용자가 "이어서 하자"라고 하면: 이 문서 → `CHANGES.md`의 `[ ]` → `TODO.md` 순으로 확인.
> 이 문서는 `~/.claude/`의 메모리/플랜이 따라오지 않는 환경(다른 컴퓨터로 디렉토리 복사 등)을 위한 백업.

---

## 🔴 현재 상태 (2026-05-01 세션 — CLEAN SLATE 진행 중, C1 완료)

### Action 모델 + Two-Layer 아키텍처 도입 결정 (2026-05-01)
5 라운드 토론 (`온톨로지-방식-고찰-v1~v5.html`) → 최종 결정 16개 (`온톨로지-방식-결정.html`) →
clean slate 작업 플랜 (`온톨로지-방식-플랜-v2.html`).

### C1 완료 (2026-05-01)
**Section 2 (modeling) + Section 3 (simulation 스캐폴딩) 모두 archive + drop**.
Section 1 (wiki) 완전 보존. `log/step_C1_summary.md`.

### C6 React Phase 1.5 + 2 완료 (2026-05-02)
**Workbench Phase 2 강화 완성** — Backward 풍부 / Lens / Path-trace / Search Around / Cross-domain.
- `BackwardMode.tsx` 신설 — branch bar (4 가설) + risk ring (62/100, conic gradient) +
  side-by-side diff (Java/Term/Rule/매뉴얼) + cascade tree (depth 슬라이더, ⚠ HARD)
- `GraphFilters.tsx` 신설 — Lens (verify/domain/confidence/simulation) + domain filter +
  verification min + Cross-domain 토글 + Path-trace dir/hop 컨트롤
- `store.ts` 확장 — graph 옵션 9 종 (lens/pathTrace/pathTraceHops/pathTraceFromFqn/
  showCrossDomainHighlight/graphFilterDomains/graphVerificationMin)
- `GraphMode.tsx` 강화 — L5 anchor micro-graph (★ 우리 차별, 메서드 본체 dataflow) +
  노드 우클릭 ContextMenu (Search Around 6 옵션) + lens별 background tint + path-traced
  border glow + dim + Cross-domain ring/⚠ 배지
- `WorkbenchShell` grid: graph mode 시 좌측 `GraphFilters` 로 교체
- 누적 LOC 2,235 (Phase 1 + 1.5 + 2) · tsc clean · 121/121 PASSED
- browse Backward 시연 OK (`/tmp/c6r2_bwd.png` — 모든 강화 표시)
- 자세한 결과: `log/step_C6R_phase15_2_summary.md`

### C6 React Phase 1 완료 (2026-05-02)
**Modeling Workbench React 구현 시작** — V6 prototype 의 React 화.
- `frontend/src/lib/api/ontology.ts` — REST client 16 메서드 (OntologyQueryClient 1:1)
- `frontend/src/components/sections/ModelingSection.tsx` + `modeling/` 9 컴포넌트:
  WorkbenchShell / TopBar / TabBar / LeftPanel (5탭, Map landing) / MainPanel (Detail/Split) /
  RightPanel (resize + 4탭) / GraphMode (L1~L4) / CmdKPalette / store.ts (zustand)
- 1,815 LOC. tsc clean. backend `bootstrap_database()` archive 후 fix.
- SectionNav 에 Modeling 탭 다시 추가.
- browse 시연: 통합 Workbench 표시 (Map landing + 4 도메인 카드 + Mode 토글 + status bar)
- Phase 1 = Forward + Detail/Split + Graph L1~L4 + 5탭 + ⌘K + status. Backward placeholder only.
- `log/step_C6R_phase1_summary.md`

### C5 완료 (2026-05-02)
**Query API 신설** — Agent boundary 확정. Contract (DTO + Protocol) + Facade + REST + 정적 검사.
- `backend/shared/contracts/ontology_query.py` — 16 method Protocol + DTO alias
- `backend/modeling/api/ontology_query.py` — OntologyQueryClientImpl (3 store 통합)
- `backend/modeling/api/ontology_router.py` — FastAPI router 16 endpoints (`/api/ontology/*`)
- `backend/agents/AGENT_GUIDE.md` — 새 agent 작성 규칙 + 예시
- `tools/check_agent_isolation.py` — backend.modeling.* 직접 import 차단
- main.py wired: bootstrap_database + ontology_query_api.init + router include
- **tests 29/29 PASSED** (누적 C2~C5 = 121/121)
- 자세한 결과: `log/step_C5_summary.md`

### C4 완료 (2026-05-02)
**Mapping Layer 신설** — Action 1급 (다형성 realizations) + AnchorBinding (fragment-level) +
TypeRealization + Path syntax + VerificationLevel state machine.
- `backend/modeling/mapping_layer/{__init__,schema,orm,store,path,verification}.py`
- 4 SQLite 테이블 (type_realizations / actions / realizations / anchor_bindings)
- Action.kind invariants (pure_function 무 effects / workflow 무 realizations)
- Realization.dispatch_source 9-enum (D3 7-case + user_confirmed/static_unresolved)
- Path syntax (params[0]<RushOrder>.spec.diameter.range[1]) + parser/validator
  (CamelCase↔snake 자동 변환, atomic.range 인덱싱 OK, subtype cast descendants 검증)
- VerificationLevel 자동 계산 (UNMAPPED→DRAFT→SIGNATURE_LOCKED→BODY_ANCHORED) +
  외부 신호 (SIM_VERIFIED/PR_PROVEN) + can_simulate gate (Q8=A Strict)
- E2E: Code (Order/Rush/Standard) + Domain (주문 도메인) + Mapping (Action + 2 Realization 다형성)
- **tests 47/47 PASSED** (누적 C2+C3+C4 = 92/92)
- 자세한 결과: `log/step_C4_summary.md`

### C3 완료 (2026-05-02)
**Domain Layer 신설** — BusinessTerm (2-kind + facets) + Inheritance + Composition + Rule.
- `backend/modeling/domain_layer/{__init__,schema,orm,store,validator,resolver}.py`
- 4 SQLite 테이블 (business_terms / inheritance_edges / composition_edges / business_rules)
- BusinessTerm: kind=atomic|composite + facets (is_abstract/is_interface/is_root_entity/struct_like_hint)
- Validator: 사이클 (extends + implements + composition 모두 DAG) + atomic-parts + dangling
- Resolver: ancestors / descendants / effective_parts (own → 자손 우선 override)
- E2E 주문 도메인 (13 terms, RushOrder=spec+progress+quality+chemical+trackingNo+priorityLevel) ✓
- **tests 30/30 PASSED** (누적 C2+C3 = 45/45)
- 자세한 결과: `log/step_C3_summary.md`

### C2 완료 (2026-05-02)
**Code Layer 신설** — Java 충실 mirror + role 분류 + CallSiteAnalyzer 1차.
- `backend/modeling/code_layer/{__init__,schema,orm,store,adapter,role_classifier,callsite_analyzer}.py`
- 4 SQLite 테이블 (code_types / code_fields / code_methods / call_sites)
- Class.role 자동 분류 (annotation + 이름 패턴): domain / framework / infra / unknown
- Method.role 자동 분류: business / helper / adapter / unknown
- CallSiteAnalyzer: SINGLE_IMPL / ANNOTATION / 자체정의 자동, 모호 → STATIC_UNRESOLVED + 후보 list + 사용자 큐
- Case 2 INSTANCEOF_GUARD / Case 4 FACTORY_BRANCH 는 body AST 분석 — Phase 2 로 미룸
- 기존 java_parser + Spring 10 analyzer 출력 그대로 활용 (adapter 만 신설, 분석 로직 재작성 X)
- **tests/code_layer/ 15/15 PASSED** (schema invariant + store CRUD + e2e 통합)
- 자세한 결과: `log/step_C2_summary.md`

### 다음 작업 (사용자 승인 후 시작)
**C6 React 완료**. C 단계 모두 마침 (CORE Phase = C1 archive + C2 Code + C3 Domain +
C4 Mapping + C5 Query API + C6 Workbench UI Phase 1+1.5+2).

**Phase 3 진행 중** (slab-design-real wiring):
- [x] P3-1 데모 repo 깊이 파악 (`p3_demo_repo_analysis.md`, `p3_order_mapping.md`)
- [x] P3-2 Repo Import 백엔드 (Importer + REST + SSE) — 122 파일 → 123 CodeType / 956 method / 1018 CallSite, idempotent
- [x] P3-3 자동 매핑 추천 — 29 Term + 36 Action + 34 TypeRealization (29 PRIMARY + 5 PARTIAL: SDOrderEntity⊃{OS,OM,Chemical,QD} + SDSlabEntity⊃SlabResult)
- [x] P3-4 Frontend Repo Import UI — TopBar 「Import」 버튼 + RepoImportModal (SSE 진행률 + 자동 recommend persist + 큐 카드). tsc clean.
- [x] P3-5 xyflow + dagre 자동 layout — `/repos/{id}/graph` REST + OntologyGraph.tsx (검색→focus + hops 1~4 + 엣지 색상별 매핑). slab-design 188 nodes / 69 edges 자동 layout.
- [x] P3-6 매핑 큐 액션 — `/repos/{id}/queue` + 6 confirm/reject endpoint + LeftPanel QueueTab 4-section + optimistic UI.
- [x] P3-7 데모 시나리오 끝-끝 브라우저 검증 + UX fix 6건 (default repo / TB layout / connected_only / auto-focus / fitView remount / 안내 카드 숨김). S1/S5/S6 끝-끝 동작 확인.

**Phase 3 완료 (P3-1 ~ P3-7) + V7 IA 리디자인 (D plan).**

### V7 IA 리디자인 (2026-05-02, 사용자 피드백 1+2+3 통합 정산)
mock UI 부채 ~600 LOC 제거 + 실 데이터 통일:
- Backend: `modules_api.py` 신규 (패키지 트리 + 패키지 inventory), `graph_api` mode 3종 (이웃 importance-weighted + 경로 shortest-path + 클러스터 패키지 collapse) + n_max
- Frontend: `ModuleTree.tsx` 신규 (Java 패키지 계층), LeftPanel 5 tab → 2 tab (코드/큐), GraphMode L1/L2/L4/L5 mock view 삭제, OntologyGraph mode 토글 + n_max slider, TopBar breadcrumb, TabBar.tsx 삭제

### Audit + 패키지 컨텍스트 (2026-05-02, 피드백 5번 + 6번 일부)
- store.ts 정리 (145 → 79 LOC, mock state 7종 + 옛 LeftTab 3종 + selectedActionFqn mock default 제거)
- GraphFilters.tsx 삭제 (V7 에서 unused)
- MainPanel: Backward 버튼 disabled+tooltip, inner breadcrumb 단순화 (TopBar 와 중복 제거)
- OntologyGraph nodeSubtitle: code_type 노드가 패키지 마지막 2 segment 표시 (예: "working.wrapper")

### Round 4 — Palantir 심층 조사 + 7 안건 결정 (2026-05-02)
사용자 피드백 7번 (prior art) 의 결과. 4-stage 조사 후 7 안건 결정 → 3-track 실행 backlog.

**조사 산출** (`toClaude/modeling/round4/`):
- `palantir-sources.md` — 40 sources 인덱스
- `palantir-raw-notes.md` — Stage 1 sweep raw notes (538 줄)
- `palantir-schema-vs-ontong.md` — Stage 2 schema 비교 (11 섹션)
- `palantir-ux-catalog.md` — Stage 3 Foundry 11 화면
- `graph-viz-patterns.md` — Stage 3 graph viz 깊이 (adoption matrix 38행)
- `decisions.html` — Stage 4 7 안건 토의 (입력 form + 복사 버튼)
- **`round4-palantir-deep-dive.html`** — 종합 보고서 (Stage 1~4 통합)

**7 안건 결정**:
1. ELK 마이그레이션 → **C** (spike + 결정)
2. Perspective → **B** (backend 1급 entity)
3. 3-pane workspace IA → **B** (Bottom overlay, graph 전용)
4. 노드 종류 → **C** (5 kinds: Domain + 2 Term + CodeType + Action)
5. Save/Share URL → **B** (Saved + ad-hoc)
6. 5K 검증 → **D** (인공 가공 + Spring Framework)
7. 실행 순서 → **D** (3-track parallel)

**핵심 발견 — 우리 차별 강점 ★**:
- `TypeRealization.scope=PARTIAL` (Foundry MDO multiplicity 금지 — 정반대)
- `Realization.dispatch_source 9-enum + AnchorBinding fragment` (Foundry 코드 layer 자체 부재)
- `VerificationLevel 6단계` (SemVer 와 직교 axis)

**3-track 실행 완료 — 11/12 task** (T1.4 Spring 정식 검증만 다음 phase):

- ✅ Track 1 (인프라): T1.1 synthesize generator + perf fix 3종 (modules 108x), T1.2 ELK PoC, T1.3 dagre→ELK 풀 마이그
- ✅ Track 2 (UX): T2.1 NodePreviewPanel, T2.2 Perspective backend (view_layer 신규), T2.3 URL state sync (useUrlSync)
- ✅ Track 3 (통합): T3.1 graph_api 5-kind, T3.2 frontend 5-kind 시각, T3.3 Domain compound (ELK nest), T3.4 Perspective ↔ 통합 (PerspectiveDropdown)

**데모 highlight**: `?section=modeling&view=graph&p=1` → 저장된 perspective "드라마 DNA 시연 (compound)" 자동 적용 → 2 dashed group box (📦 entity + 📦 jpo) + 자식 nest + cross-package PARTIAL edges 시각.

**해결된 사용자 피드백**: 1, 2, 3, 4, 5, 6, 7 모두 ★

**최종 보고서**: `toClaude/modeling/round4-palantir-deep-dive.html` (3-track 실행 결과 섹션 8.5 추가)

### Round 4 종결 후 다음 후보
- **A.** R4-T1.4 Spring Framework 정식 검증 (선택, backend perf 가 sub-200ms 달성 후 가치 낮음)
- **B.** A2 Simulation Agent — Action description → LLM tool spec (Stage 2 차용 후보 #3) + S4 시뮬 시나리오 활성화
- **C.** Schema migration framework — Foundry 8-option 차용 (Stage 2 차용 후보 #1)
- **D.** Action SemVer + 자동 호환성 검사 (Stage 2 차용 후보 #2, A2 Agent 입력)
- **E.** 6번째 노드 kind: Method (zoom-in mode)
- **F.** Perspective ACL + share token / Branching (R4 다음 단계)

P3-2 검증:
```bash
uvicorn backend.main:app --port 8765 --log-level warning &
curl -X POST http://127.0.0.1:8765/api/ontology/repos/import \
  -H 'Content-Type: application/json' \
  -d '{"repo_id":"slab-design-real","repo_path":"sample-repos/slab-design-real"}'
# 응답 job_id → GET /api/ontology/repos/import/{job_id}/stream 으로 진행률
```

이후 순서:
- **A1 Plugin framework** → **A2 Simulation Agent** → **A3 PR Agent** → **A4 NL 분석 Agent**

---

## 📋 이전 세션 상태 (참고용 — 위 clean slate 로 대부분 archive 됨)

### 이번 세션 한 일 한 줄씩

### 이번 세션 한 일 한 줄씩
- **S1** 백엔드 `EntitySearchIndex` per-repo (1786 entities 50ms ranked, kind/parent 필터, score, binding/rule 카운트 enrichment)
- **S2** 온톨로지 subgraph navigation — `/repos/{id}/ontology-subgraph?focus=...&depth=N` + 프론트 「focus 선택」 + 더블클릭 탐색
- **S3** TermMapping 검색 박스 + 100건 페이지 + 「+200건 더보기」 (5000+ binding 가정)
- **S4** Workbench 메서드 트리 **적응형 expand** (≤500 클래스 자동 / >500 collapsed) + 「⊞ 전체 펼침/⊟ 접기」 컨트롤 + 가시 카운트
- **S5** ⌘K 통합 검색 — term/class/method/rule 종류별 그룹 + T/R 매핑 카운트 배지
- **S6** Domain map (Top-down 진입점) — LLM 카테고리 자동 분류 9 단계 (주문→화학성분→Slab사양→...→상태진도). `BusinessTerm.domain` 에 `"NN|name"` 인코딩
- **S7-A/B/C** Phase 1 — `sweepers/stale_binding_sweeper.py` + `api/binding_health_api.py` 신규. `/repos/{id}/reindex` + `/stale-bindings` + `/bindings/{id}/rematch`. alias 정규화 (camel↔snake) + 비파괴 + audit log
- **U1~U9** UX polish 9건 (TermMapping spinner / 도메인 흐름 wrap / 데모 amber CTA + LOADED 배지 / Binding Health 신규 패널 / 메서드 트리 expand / placeholder / 가이드 collapse / tooltip / Repository ACTIVE indicator)
- **P27** E2E `SdFinalLengthRangeAction.execute` 시뮬 풀 사이클 (Java→한국어 Python → sandbox → diff) 정상 작동 검증
- **P28** `사용자-가이드-v4.html` — 모든 신규 기능 반영

### 4-Phase 외부 프레임워크 점수표 (`reports/4-phase-ideal-comparison.html`)
| Phase | 외부 ideal | 현재 | 다음 가능 |
|---|---|---|---|
| Phase 1 — 지식 동기화 | 100 | **75** (S7 완료) | TIER 1 = 100, 모두 = 180 |
| Phase 2 — 시맨틱 훅 | 100 | 45 | 미진행 |
| Phase 3 — 결정론 샌드박스 | 100 | 30 | 미진행 |
| Phase 4 — 자가 증식 | 100 | 10 | 미진행 |

### Phase 1 100→180점 16가지 (`reports/phase1-beyond-100.html`)
- TIER 1 (즉시, 누적 100점): file watcher · git commit hash provenance · auto self-heal (단일 후보 자동 적용) · type-aware matching
- TIER 2 (130점): snapshot 버전닝 시간여행 · DB schema sync (Flyway/Liquibase) · LLM 한국어 영향 요약 · Test 영향 맵
- TIER 3 (160점): Refactoring 분류기 · embedding body 등가성 · cross-binding 패턴 학습 · WebSocket push
- TIER 4 (180+점): git bisect · AI auto-PR · multi-repo binding · Drift Radar 대시보드

### 다음 세션 첫 작업 (사용자 결정 필요)
**옵션 A — Phase 1 TIER 1 (1~2일, 즉시 100점 도달)**
1. file watcher daemon (fsevents/watchdog) → 자동 reindex
2. git commit hash provenance (매 reindex 가 commit SHA 함께 저장)
3. auto self-heal (alias-exact 단일 후보 + conf≥0.95 자동 rematch + audit log)
4. type-aware matching (Java type 일치 가산점)

**옵션 B — Phase 2 SemanticHook (3~5일, 외부 차별화 시작)**
- ConceptBinding × MethodAnchor 결합 → `SemanticHook(term_fqn, method_fqn, anchor_locator, operation, valid_range)` DTO
- `/semantic-hooks?term_fqn=...` 카탈로그 API
- PythonGenerator 결정론화 — LLM 은 hook 선택만, 코드는 템플릿

**옵션 C — react-window 도입 (메서드 트리 진짜 가상화)** — 5000+ class 진입 시 필수. 현재는 적응형으로 우회 중.

**옵션 D — Phase 3 ConstraintEvaluator** — BusinessRule.predicate 머신화 + step-by-step 검증 → reasoner traceback 형식 위반 보고. (옵션 B 의존)

### 데이터 상태 (slab-design-real)
- 등록 repos: 2개 (engine 11/95/177, real 123/1786/3257)
- BusinessTerm: 59개 (LLM 자동 9 카테고리)
- BusinessRule: 135개 (123 body + 12 LLM)
- ConceptBinding (confirmed): 199개 (healthy 100% / stale 0)
- 매뉴얼: 2개 (sd-tables.md, slab-design.md)

### 핵심 파일 위치
- 백엔드: `backend/modeling/sweepers/stale_binding_sweeper.py` · `backend/modeling/api/binding_health_api.py` · `backend/modeling/api/domain_map_api.py` · `backend/modeling/code_analysis/entity_search_index.py`
- 프론트: `frontend/src/components/sections/modeling/BindingHealthPanel.tsx` (NEW) · `OntologyGraphPanel.tsx` (S2/S6 재작성) · `MethodWorkbench.tsx` (S4 + U5/U6/U8) · `TermMapping.tsx` (S3 + U1) · `RepositoryManager.tsx` (U9)
- 리포트: `toClaude/modeling/reports/4-phase-ideal-comparison.html` · `phase1-beyond-100.html` · `ux-audit-2026-05-01.md`
- 가이드: `toClaude/modeling/사용자-가이드-v4.html`

### 검증 방법 (다음 세션 시작 시)
```bash
# 백엔드 + 프론트 살아있는지
curl -s -o /dev/null -w "be %{http_code}\n" http://127.0.0.1:8001/api/auth/me
curl -s -o /dev/null -w "fe %{http_code}\n" http://localhost:3000

# binding health 확인
curl -s http://127.0.0.1:8001/api/modeling/repos/slab-design-real/stale-bindings | python3 -m json.tool
```

브라우저는 `localhost:3000` → Modeling 섹션 → 「🛡️ 매핑 상태」 탭에서 신규 패널 확인 가능.

---

## 이전 상태 (2026-04-27 세션 종료 — P29 + P30 완료)

### 가장 최근 작업 (P29 + P30 — Hardcore validation 결과 반영)
서브에이전트(Principal QA Architect) 검증으로 13개 architectural defect + 15 PASS chaos test 도출. 그중 7개 defect 코드 수정 완료.

- **P29-1**: `spring/transactional_analyzer.py` + `spring/async_analyzer.py` — `@Transactional` / `@Async` / `@TransactionalEventListener.phase` → `tx_marker` / `async_marker` entity. Spring AOP/Proxy bypass 시뮬레이터 인지.
- **P29-2**: `spring/mybatis_mapper_analyzer.py` (annotation SQL) + `mybatis_xml_parser.py` (XML `<if>/<choose>` conditional) — MyBatis 0% blind spot 해소. `repo_parser.py` 가 Java pass 끝나면 XML pass 호출.
- **P29-3**: `spring/di_analyzer.py` AUTOWIRES edge 에 `field_name` + `injection_kind` 추가. `call_resolver.py` 가 qualifier 명시되면 bean_name_index lookup 으로 type_candidates 무시하고 정확한 impl 라우팅 (interface 필드 + impl `@Component("name")` 해소).
- **P29-4**: `mapping/anchor_binding_suggester.py`, `mapping/rule_suggester.py` `_parse()` — frozenset valid_term/anchor/fragment FQN 으로 LLM hallucination drop.
- **P30-1**: `cross_file_enricher.py::_expand_intercepts_to_methods()` — class-level INTERCEPTS edge 를 method 단위 fan-out (`synthesized=True, fan_out_from_class=class_fqn`).
- **P30-2**: `cross_file_enricher.py::_synthesize_event_chain_edges()` — publishes + handles 조합으로 publisher → handler 직접 `calls_via_event` 엣지 합성 (async/tx_phase attr 포함).
- **P30-3**: `spring/native_sql_analyzer.py` — `JPAQueryFactory.selectFrom/select/.../update(QSlab.slab)` 패턴 인지. `_infer_qclass_entity()` Q-prefix strip → cross_file_enricher 의 `_resolve_jpql_to_table` 가 `@Table` 매핑으로 실제 테이블명 변환.

### 검증 상태
- pytest 1862 pass / 0 modeling-side fail (잔존 20 fail 은 wiki/agent 영역 — 별도 세션 담당).
- Chaos test invert: `test_call_resolver_resolves_qualifier_to_correct_impl`, `test_mybatis_analyzer_module_present` (defect → fix 검증으로 전환).
- registry 카테고리 단정 갱신: `tx_marker`, `async_marker`, `mapper_method`, `calls_via_event` 추가 후 `>=` 단정으로 변경.

### 다음 세션 첫 작업
1. **백엔드 재기동 + sample-repos 재인덱싱** — `slab-design-real` 등 기존 캐시 무효화 후 P29/P30 변경분이 실제 그래프에 반영되는지 확인.
2. **chaos test 잔여 결함** (총 13개 중 7개 fix) — 나머지 6개 defect 의 우선순위 검토. 영향 분석에 직접 영향 없는 것 (예: `@Conditional`, `@Scope("prototype")`) 은 후순위 가능.
3. **P27 (E2E 검증)** + **P28 (사용자 가이드 v4)** — TODO #120 / #121 에 남아 있음. P29/P30 fix 가 실제 데모 시나리오 (slab demo SdFinalLengthRangeAction) 에 반영되는지 확인.

### 변경 파일 목록 (P29 + P30 세션)
- `backend/modeling/code_analysis/parser_protocol.py` — entity/relation kind 4종 추가
- `backend/modeling/code_analysis/spring/transactional_analyzer.py` (NEW)
- `backend/modeling/code_analysis/spring/async_analyzer.py` (NEW)
- `backend/modeling/code_analysis/spring/mybatis_mapper_analyzer.py` (NEW)
- `backend/modeling/code_analysis/mybatis_xml_parser.py` (NEW)
- `backend/modeling/code_analysis/spring/__init__.py` — import 추가
- `backend/modeling/code_analysis/spring/di_analyzer.py` — field_name + injection_kind
- `backend/modeling/code_analysis/spring/native_sql_analyzer.py` — QueryDSL 패턴
- `backend/modeling/code_analysis/call_resolver.py` — qualifier-first lookup
- `backend/modeling/code_analysis/cross_file_enricher.py` — INTERCEPTS fan-out + event chain
- `backend/modeling/code_analysis/repo_parser.py` — 15 analyzer + XML pass
- `backend/modeling/mapping/anchor_binding_suggester.py` — valid set 검증
- `backend/modeling/mapping/rule_suggester.py` — valid set 검증
- `tests/test_spring_chaos_async.py` — 2 inverted defect tests
- `tests/test_code_analysis_registry.py` — 카테고리 단정 갱신

---

## 이전 상태 (2026-04-26 세션 종료)

**Section 2 모델링 — 7개 사이드바 탭 풀 데모 가능**, 탭 간 cross-navigation 지원.

### 사이드바 7-탭
1. **Repository** — sample-repos auto-discover + 사용자 새 repo 등록 (REST + SSE 진행). 12-analyzer 자동 파싱, `.analyzed/` 디스크 캐시.
2. **기준서 (Manual Upload)** — PDF / DOCX / PPTX / Image / Markdown 인제스트. 모드 토글 (skip / update / force) + SSE 진행 + authoritative 토글.
3. **용어 매핑** — 한국어 BusinessTerm ↔ JPA `@Column` / 일반 필드 자동 후보. 4-stage chain (exact / alias / embedding / LLM, ClaudeTermResolver). Term 등록·수정·삭제 + 매핑 확정·거부 (양방향 flip) + evidence + **cross-nav** (term_fqn → 역탐색, code_fqn → 영향 분석).
4. **갭 큐** — 코드 ↔ 기준서 자동 갭 탐지 (code_only / manual_only / conflicts). Auto-linker (OpenAI 임베딩) 가 startup 에서 DescribedInBinding 자동 생성. Evidence panel 에 rule vs fragment side-by-side + mismatch type 별 색깔. Auto-link UI — top-K + threshold slider. conflict target → 영향 분석 cross-nav.
5. **역탐색 (Reverse Lookup)** — 한국어 용어 입력 → BusinessTerm 매칭 → 확정된 ConceptBinding 그래프 BFS → 영향받는 코드 위치. affected fqn 옆에 [영향 분석] 버튼 → cross-nav.
6. **영향 분석 (Impact Analysis)** — 코드 위치 → BFS (incoming/outgoing). InMemoryGraphView × QueryEngine + **call_resolver** (field type lookup). affected → [드릴다운] 으로 같은 탭에서 재검색.
7. **DI 그래프** — Spring `@Component` / `@Service` / `@Repository` / `@Controller` 빈 + `@Autowired` 의존 관계 시각화 (xyflow). 노드 클릭 → 우측 패널 → incoming/outgoing 빈 리스트 → [이 빈 영향 분석] 으로 cross-nav.

### Cross-tab navigation
- ModelingSection 의 `navigateTo(view, params)` + `navParams` state.
- 자식 컴포넌트는 optional `prefillTerm` / `prefillTargetFqn` + `onNavigate` props.
- Mount 시 prefill 자동 검색/분석 (autoSearchedRef 가드로 무한 루프 방지).
- 도착 탭에 보라색 strip 으로 "OOO 에서 자동 입력" 표시 (`ModelingNavParams.from`).
- 6 방향 — 용어→역탐색, 코드→영향, 갭(충돌)→영향, 역탐색→영향, 영향→영향(드릴), DI→영향.

### 2026-04-26 마지막 작업
1. **수동 매핑 UI** (사용자 요구) — 자동 추천 우회. `POST /api/modeling/bindings/manual` (term + code_fqn → 즉시 confirmed) + `GET /repos/{id}/entities/search` (자동완성). TermMapping 헤더에 [수동 매핑] 토글 + 인라인 폼 (용어 dropdown + 코드 검색 + scope + 매핑 버튼). source=`manual`, confidence=1.0.
2. **Structured Manual 형식** (사용자 요구) — `<!-- ontong: term=... rule=... scope=... -->` HTML 코멘트 directive. `md_parser` 가 다음 fragment 의 `attributes` 로 흡수. `auto_linker` 가 directive 우선 (confidence 1.0, source=`manual_directive`) + 임베딩 fallback. Fragment 작성자가 자기 단락의 의미를 명시 가능 → 매핑 정확도 자동 추측 의존 줄임.
10. **2026-04-27 — E/F/G/H 폴리시** (사용자 「선택적 폴리시 4개 전부」 일괄)
    - **E** Phase 5 — `RepositoryHub.tsx` (NEW) — Repository / DI 그래프 sub-tab. DI 그래프 standalone 탭 deprecation banner.
    - **F** GitHub PR 자동 생성 — `pr_creator.py` (NEW): branch + git apply + commit + push + `gh pr create --draft`. 단계별 graceful 실패 (`PRCreateResult`). `change_specs_api` `POST /create-pr`. SimulationDrawer 「GitHub PR 만들기」 버튼 + URL 표시.
    - **G** Multi-method — `change_specs_api.simulate` 가 `payload.related_methods` (max 5) 처리. 각 메서드 변환/실행/diff 별도. SimulationDrawer Step 1 textarea + Step 3 violet 박스.
    - **H** 자동 테스트 — 4 신규 파일, **65 PASS** (`test_diff_reporter.py` 28 + `test_sandbox_runner.py` 21 + `test_relation_store_and_change_spec.py` 10 + `test_ontology_graph_api.py` 6). 각 테스트 isolated SQLite (`_isolated_db` fixture).

9. **2026-04-27 — A/B/C/D 통합 보강** (사용자 「A → B → C → D 순서대로」 일괄)
   - **A** 시뮬레이션 history UI : `SimulationDrawer.existingSpec` prop + Workbench R 「시뮬」 안 「📋 시뮬레이션 기록」 collapsible. SpecHistoryRow (status badge + kind + description + ↻ refresh + 삭제 hover). 「다시 실행」 버튼 (cache hit 으로 즉시).
   - **B** Multi-Layer Impact code layer 활성화 : `query_engine_factory(repo_id) → QueryEngine(_impact_api._get_view(repo_id))` 주입. lookup 메서드 11 nodes (3 callers + 6 anchors). 1ms 미만.
   - **C** 갭 큐 → Workbench R 「✅ 갭」 흡수 (IA Phase 4) : 새 `GapsPanel` 메서드 단위 자동 filter (target/counterpart 매칭). confirm/unconfirm 인라인. 갭 큐 탭 amber deprecation banner.
   - **D** 시뮬 hardening : `temperature=0` + sha1 cache (`_cache_key(method_fqn, java_source, var_hints)`). `apply_change_spec_to_java` 의 anchor_value → tree-sitter Parser(JAVA_LANGUAGE) + `_replace_var_value(variable_declarator | assignment_expression)` 으로 정확 변환. 검증: numerator 변수 value 만 변경, 다른 라인 영향 없음.

8. **2026-04-27 — P24~P26 시뮬레이션 풀 사이클 (Sandbox + Diff + Apply) 완성 ★**
   - **P24** `backend/modeling/simulation/sandbox_runner.py` (NEW): `SyntheticInputGenerator` (3 시나리오: 기본 + literal #1/#2) + `RestrictedPythonSandbox` (compile_restricted_exec, mock_<name> 함수 자동 주입, _SampleDict entity fallback, mutation 캡처)
   - **P25** `backend/modeling/simulation/diff_reporter.py` (NEW): `report_diff()` 5 차원 비교 (return Decimal rel_pct, mutation per-key, exception improvement/regression, mock added/removed, perf >20% only). severity none/improvement/minor/major/regression
   - **P26** `change_specs_api.py` `POST /apply`: difflib unified_diff + status=applied
   - Frontend `SimulationDrawer.tsx`: `Step3Diff` 재작성 (`SemanticDiff`/`DiffCaseCard` 색상별), full mode toggle (55vh ↔ 94vh), applyChangeSpec 호출 + patch slate-900 dark block
   - **E2E 검증**: `CastSpecService.lookup` repository → cache 변경 → simulate → apply → unified diff (6 줄) target_file 정확
   - 한계: LLM 비결정성, anchor_value 텍스트 매칭, GitHub PR 자동 생성 미구현 (gh tooling deferred)

7. **2026-04-27 — P23 PythonGenerator (Q-D=D1 가설 검증 완료) ★**
   - `backend/modeling/code_analysis/java_parser.py` — `_extract_method` 에 `method_attrs["source"] = node.text.decode()` 추가 (메서드 body 텍스트 캡처)
   - `backend/modeling/simulation/python_generator.py` (NEW) — `ClaudePythonGenerator` (Sonnet 4.6, max_tokens=4096), 8 규칙 시스템 프롬프트, JSON 응답 파싱, Python `compile()` 검증, `apply_change_spec_to_java` 헬퍼
   - `backend/modeling/api/change_specs_api.py` — simulate stub → 실제 PythonGenerator 호출. before/after 양쪽 java_source + python_code + variable_mapping + mock_calls + warnings + errors 반환
   - SimulationDrawer Step3Diff → `SideColumn` (dark Python code block, collapsible Java source, 변수 매핑 테이블, mock 호출, 경고)
   - **Spike 결과** : Slab `SdFinalLengthRangeAction.execute` BigDecimal 14줄 → 9개 한국어 변수 (슬라브중량, 두께, 비중, 폭상한기준길이 등) + Decimal 정확 변환. CastSpecService.lookup → productTypeCd→품종코드 매핑 활용. **production-quality**.
   - **위험 발견** : disk cache 무효화 필요 (RepositoryRow SQLite 도). 큰 메서드 (>3000자) chunk 필요.

6. **2026-04-27 — P22 (ChangeSpec + 시뮬레이션 wizard UI)**
   - `backend/modeling/persistence/models.py` `ChangeSpecRow` (11번째 ORM 테이블)
   - `backend/modeling/simulation/change_spec.py` (NEW): `ChangeSpecKind` 5종 (rule_statement/rule_severity/anchor_value/method_body/term_binding) + `ChangeSpecStatus` 7종 + `SqliteChangeSpecStore`
   - `backend/modeling/api/change_specs_api.py` (NEW): POST/GET list/GET method-list/GET single/PUT/DELETE/POST simulate(stub)
   - `frontend/src/components/sections/modeling/SimulationDrawer.tsx` (NEW): 55vh bottom drawer, 3-step wizard (정의/실행/diff), kind 별 payload 에디터, Step badges, wizard nav
   - Workbench R 「🔬 시뮬」 탭 placeholder 제거 → launcher 활성
   - 검증: ChangeSpec POST/list/simulate(mock=stub completed)/DELETE 모두 정상
   - **시뮬레이션 backbone 완성** (UI + ChangeSpec 영속). 엔진은 P23~P25 가 채움.

5. **2026-04-27 — P21 (매핑 기능 100%)**
   - **P21a** AnchorCard 인라인 「확정」 — auto-suggest 결과 → `createManualBinding(method@locator)` 즉시 confirmed binding
   - **P21b** `TermManagerPanel` (Workbench Ontology 패널 상단 collapsible) — listTerms/updateTerm/deleteTerm/createTerm 인라인 (canonical/aliases/domain)
   - **P21c** `ReferencePanel` (R 「📚 참고」 활성화) — `GET /rules/{fqn}/manual-fragments` 신규 endpoint, gaps_api.\_auto_described_in 에서 source_fqn=rule 매칭, fragment 본문 + doc + source 배지 + confidence
   - 검증: 119 rule 중 7 개에 fragment 자동 매핑 (embedding source). slab demo 2 term 정상 listTerms 응답.
   - 매핑 기능 100% 도달 (단, 정확도 100% 는 GIGO/LLM/도메인 진화 한계로 본질적 불가능)

4. **2026-04-27 — P19 + IA Phase 2/3 + Q3/Q4** (사용자 「Phase 2~5 시작 + 흡수 1 개 알아서 + Q3/Q4 그대로」 일괄 적용)
   - **P19 Multi-Layer ImpactPropagator** : `backend/modeling/impact/multi_layer_propagator.py` 3 layer (code BFS + ontology BFS w/ auto-derived rule.terms_ref + manual ManualFragment refs)
   - `multi_impact_api` `GET /impact/multi-layer` 단일 endpoint, query params hops_code/ontology/manual
   - Workbench R 「🧬 영향」 탭 placeholder 제거 → `ImpactPanel` 활성화. target 토글 (메서드/rule), layer 별 그룹 + 펼치기
   - **Q3** : OntologyGraphPanel default 「관계 있는 노드만」 ON
   - **Q4** : 단일 「📚 매뉴얼」 탭 (`ManualHub.tsx`, sub-tab 업로드/작성)
   - **Phase 3** : `WorkbenchCommandPalette.tsx` (⌘K, 코드/용어 모드 토글, 키보드 nav). 역탐색 탭 deprecation banner
   - **Phase 2** : 영향 분석 탭 deprecation banner (Workbench R 「영향」 으로 안내)
   - 사이드바 10 → 9 + deprecated 표기 2

3. **P13~P18 완료** (Method Workbench 시뮬레이션 backbone + Ontology Graph)
   - P13 SQLite persistence (10 ORM 테이블 / 모든 in-memory store 교체)
   - P14 Method body AST → MethodAnchor 7 kinds (slab-design-real 2081 anchors / 912 methods)
   - P15 value_flow extractor (DERIVES_FROM/PROPAGATES_TO)
   - P16 Body-driven RuleExtractor 7 kinds (slab-design-real 81 body rules — formula 43, throw 13, lookup 10, guard 9, bound 6)
   - P17 BusinessRule 검토 큐 — `backend/modeling/api/rules_api.py` + `SqliteRuleRegistry.delete()` + Workbench R 패널 「⚖️ 룰 검토」 탭
   - **P18 온톨로지 그래프** — `OntologyRelationRow` + `SqliteOntologyRelationStore` + `ontology_graph_api.py` (GET graph / GET list / POST / DELETE) + `OntologyGraphPanel.tsx` (xyflow, term 좌측 / rule 우측 multi-column, 노드 클릭 → 우측 detail + 새 관계 폼, 「관계 있는 노드만」 토글)
     - RelationKind 7 종 — is_a / part_of / synonym_of / related_to / governs / derives / conflicts
     - rule.terms_ref 자동 inferred edge (점선 표시)
     - IA 통합 제안 — `toClaude/modeling/IA-개선제안-v1.html` (10 탭 → 6 탭 단계적 전환 로드맵)
   - P20+P21a~d Workbench 4-패널 (트리 nested + class kind 배지 + method visibility/modifier + anchor highlight + ontology cards + 자동 매핑)

### 핵심 모듈 (이번 세션 신규)
- `backend/modeling/code_analysis/repository_registry.py` + `repo_parser.py` — Repository 단위 12-analyzer 결과 보관, disk cache 자동 복원
- `backend/modeling/api/repos_api.py` — REST + SSE register stream
- `backend/modeling/mapping/context_bundler.py` — 코드 위치 → 컨텍스트 번들 (opaque 식별자 LLM 매칭용)
- `backend/modeling/query/llm_term_resolver.py` — ClaudeTermResolver (opaque term LLM 매칭)
- `backend/modeling/gap_detection/auto_linker.py` — rule × fragment 임베딩 유사도 → DescribedInBinding 자동 생성
- `backend/modeling/gap_detection/embedding_drifter.py::OpenAITextEmbedder` — text-embedding-3-small (auto_linker 가 1회 batch)
- `frontend/src/components/sections/modeling/`:
  - `RepositoryManager.tsx` — Repo 등록/관리
  - `TermMapping.tsx` — 풀 재작성 (도움말 + 수정/삭제 + 결정 flip + evidence)
  - `GapQueue.tsx` — 풀 재작성 (한국어 라벨 + Evidence AST diff)
  - `ReverseLookupPanel.tsx` — 신규

### Startup 시드 (main.py)
- RepositoryRegistry: `sample-repos/*/.analyzed/` auto-discover (slab-design-real 123 files / 1781 entities, slab-design-engine 11/95)
- RuleRegistry: 모든 등록된 repo 의 Java Javadoc → 54 BusinessRule
- BusinessTerm: 품종코드 + 열연공장코드 (slab demo 시드)
- ManualRegistry: `sample-repos/slab-design-real/toClaude/{sd-tables,slab-design}.md` 인제스트 (메타 섹션 필터)
- Auto-linker: 54 rules × 59 fragments → 7 DescribedInBindings (OpenAI threshold=0.55)
- Reverse Lookup: TermResolver 재init (registered terms + shared binding store)

### 검증 수치 (slab-design-real 기본 시드 상태)
- POST /terms/propose-bindings → **9 binding 후보** (jpa_only 모드)
- POST /gaps/scan → **31 code_only + 18 manual_only + 7 conflicts**
- GET /reverse_lookup?term=품종코드 → exact 매칭 + (사용자가 binding confirm 후) **3 affected code positions**

### 데모 흐름 (가장 자연스러움)
1. Repository 탭에서 slab-design-real 카드 클릭 → 용어 매핑 자동 진입
2. 용어 매핑에서 "매핑 자동 탐색" → 9 후보 → 일부 확정/거부 (양방향 flip 시연 가능)
3. 갭 큐 탭에서 "갭 자동 탐지" → 31 code_only + 18 manual_only + 7 conflicts. conflicts 1건 펼쳐서 AST diff 시각화 시연
4. 역탐색 탭에서 "품종코드" 검색 → exact 매칭 → 영향 받는 코드 위치 표시 (확정한 binding 활용)

### 다음 세션 첫 할 일 (P27 E2E 검증 + P28 사용자 가이드)
1. **Backend** : `cd /Users/donghae/workspace/ai/onTong && .venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001 --log-level warning`
2. **Frontend** : `cd frontend && npm run dev`
3. **시뮬레이션 풀 사이클 + A/B/C/D 보강 완료**. 남은 것 :
   - **P27** : `SdFinalLengthRangeAction.execute` walkthrough 시나리오 + UI 캡처 (사용자 「나중에 하자」)
   - **P28** : 사용자 가이드 v4 HTML — Workbench → Ontology → Simulation 전체 흐름 (사용자 「나중에 하자」)

### 데모 흐름 (P17 + P18)
**Workbench (P17 룰 검토)**
1. 좌측 트리 → `feature.sd.process.std.service.CastSpecService.lookup` 클릭
2. C 패널: source + anchor highlight, C-R: Ontology 카드 + auto-suggest
3. R 패널 default "⚖️ 룰 검토" → body:lookup rule 1 건 → 확정/편집/거부

**온톨로지 그래프 (P18)**
1. 사이드바 「온톨로지 그래프」 → 좌측 2 term + 우측 56 rule 노드 multi-column
2. 헤더 「관계 있는 노드만」 토글 → orphan 숨김
3. 노드 클릭 → 우측 detail + 연결된 관계 + 새 관계 추가 폼 (term-term=is_a/part_of/synonym/related, term-rule=governs, rule-rule=conflicts)
4. 점선 엣지 = `rule.terms_ref` 자동 inferred (DB 미저장)

### 알려진 한계
- **Conflicts 7건은 OpenAI 임베딩 기반** — API key 없으면 HashingTextEmbedder 로 fallback (160 binding / 111 noise conflicts). 환경변수 `OPENAI_API_KEY` 가 있어야 demo-quality 신호.
- **In-memory 저장** — backend 재시작 시 사용자 confirm/reject 결정 모두 초기화 (gap_store, binding_store 모두 InMemory). 실제 영구 저장은 미구현.
- **시뮬레이션 panel** — 컴포넌트 존재하지만 데모 시나리오 미정. Section 3 영역 (다른 팀).

---

## 📜 과거 세션 기록 (참고용)

> ## 🟢 데모 코드 도착 (2026-04-25 세션 종료)
>
> **사용자가 실제 데모 소스를 가져옴** : `sample-repos/slab-design-real/` (Maven 4-모듈 — boot/facade/feature/store, **122 .java 파일**).
> - 12-analyzer snapshot 즉시 떠봄 : **122 files / 1774 entities / 3257 relations / 0 errors** (`.analyzed/entities.json`).
> - Spring beans : 41 @Component + 12 @Service + 4 @Configuration + 4 @RestController.
> - JPA : 8 `find` Repository 메서드 자동 추출 (B5-7 작동 확인). MyBatis 도 사용 중 (전담 analyzer 없음 — 향후 옵션).
> - 사용자 제공 컨텍스트 : `sample-repos/slab-design-real/toClaude/` 안 (PROJECT_OVERVIEW / architect / ALGORITHM / sd-tables / scenarios / DRAMA_DNA / slab-design.md).
>
> **다음 세션 첫 할 일** :
> 1. `sample-repos/slab-design-real/toClaude/*.md` 읽고 도메인 이해 (특히 PROJECT_OVERVIEW / architect / sd-tables).
> 2. RuleRegistry 시드 — `seed_rules_from_repo(Path('sample-repos/slab-design-real'), 'slab-design-real', _rule_registry)` (122 파일 인제스트, 한국어 Javadoc 가 있다면 BusinessRule 자동 추출).
> 3. 매뉴얼 작성 (사용자 제공 도메인 문서를 기반으로 `wiki/` 안 또는 별도) → ManualRegistry 업로드.
> 4. `POST /api/modeling/gaps/scan {"repo_id":"slab-design-real"}` → MISSING_IN + CONFLICTS_WITH 후보 출력 검증 (E1-e 실증).
> 5. evidence panel + LLM 재평가 시연 (E1-i UI 확인).
>
> 합성 baseline 보존 : `sample-repos/slab-design-engine/` (의도적 gap 5종 박힘) — 회귀 테스트 의존, 그대로 유지.

> ## 🧹 디렉토리 정리 (2026-04-25 세션 종료)
>
> - **삭제 (untracked)** : `venv/` (699M), 최상위 `node_modules/` (1.3M), 최상위 `.next/`, `.pytest_cache/`, `.DS_Store`, `nohup.out`, `site/` (136K, 옛 정적 데모), `ontologies/` (24K, **OD-11 폐기 yaml fixtures**).
> - **git rm staged** (커밋 미실행) : 최상위 `package.json` + `package-lock.json` (frontend 와 중복), `agent_bible/claw-code-parity` (15M, orphan submodule). `git status` 에 `D` 로 보임 — 사용자가 OD-11 work 와 함께 적절한 시점에 commit.
> - **약 700MB+ 회수**.
> - **`ontologies/` 삭제 후속 처리 (OD-11 정책 마무리)** :
>   - `tests/test_ontology_loader.py` 의 `test_load_sample_safety_stock_v1` + `test_load_scor_isa95_template` 두 케이스 `pytest.mark.skip` (OD-7/8 era 폐기).
>   - `tests/test_ontology_store.py::test_load_template_persists_scor_isa95` 도 skip.
>   - `backend/modeling/api/modeling.py` `init()` 에서 `OntologyStore` 인스턴스화 + `ontology_api.init` 비활성화 (주석 + log 변경, OD-11 명시).
>   - 회귀 0 — 전체 1624 PASS / 5 SKIP / 20 FAIL (Section 1 baseline). 깨진 3 → SKIP 으로 전환.

마지막 업데이트: 2026-04-25 (OD-11-B5-7 / JPA 완료 — `JpaAnalyzer` 12번째 Spring analyzer. 사용자 의견 "데모 코드 어차피 JPA 쓸 텐데 미리 준비" 반영, B5 단계에서 연기됐던 옵션 항목 정식 종결. **모듈 신규** `backend/modeling/code_analysis/spring/jpa_analyzer.py` (~210 LOC) — `@Repository` annotation OR Spring Data 4 base interface 중 하나를 extends 하는 interface 탐지 (Repository/CrudRepository/PagingAndSortingRepository/JpaRepository, simple name 매칭으로 import 무관). entity simple name = `extends JpaRepository<User, Long>` 첫 generic 파라미터. 메서드 이름 컨벤션 : find/get/query/read/search\\*By\\* → READS_TABLE (jpa_operation="find"), exists\\*By\\* → "exists", count\\*By\\* → "count", delete/remove\\*By\\* → WRITES_TABLE ("delete"), save/saveAll/saveAndFlush 정확 매치 → WRITES_TABLE ("save"), 그 외 edge 없음. prefix 다음 글자 대문자 보장 (false-positive 차단). property path = `findByEmailAndStatus` → `["email","status"]` (And/Or split + camelCase 첫글자 소문자화). edge attributes : jpa_operation + jpa_property_path + target_kind="jpa_entity_simple_name" (CrossFileEnricher v2 가 향후 `@Table(name=...)` 으로 rewrite 가능 표시). out-of-scope (v1) : @Entity↔@Table cross-file 해소 / @OneToMany 등 관계 엣지 / @Query (NativeSqlAnalyzer 가 처리). spring/__init__.py + scripts/dump_entities_snapshot.py 12번째 등록. tests/test_dump_entities_snapshot.py "_eleven_" → "_twelve_" 동기화. `tests/test_spring_jpa_analyzer.py` 27/27 PASS (TestDetection 5 + TestMethodNameOperations 14 parametrized + TestMethodAttributes 3 + TestMultipleMethods 2 + TestProtocol 3). Slab 샘플 (JPA 없음) 12-analyzer 결과 95/177 그대로 — JPA 없는 코드 안 깨짐 검증. 전체 1627 PASS / 20 FAIL (E1-j 1600 → +27, 전부 Section 1 baseline). **의의** : 데모 코드 도착 시 Repository 메서드 → 테이블 접근 그래프 자동 추출 (Impact Analysis 핵심 입력). 데모 코드 무관 인프라 8번째. **다음 우선** : (i) **Slab 데모 코드 도착 대기** → B 매뉴얼 / D4 UI 디자인 / E1-e 5종 gap 실증. (ii) **DescribedInStore** — 자동 발견 메커니즘 미정 (데모 코드+매뉴얼 동반 결정). (iii) (선택) **CrossFileEnricher v2** — JpaAnalyzer 의 `target_kind="jpa_entity_simple_name"` 엣지를 `@Table(name=...)` 으로 rewrite. 데모 코드 보고 결정. 백엔드/프론트 죽어있음. 이전 업데이트 : 2026-04-25 (OD-11-E1-j / A1 완료 — `scripts/dump_entities_snapshot.py` JSON 스냅샷. 데모 코드 도착 전후 비교 + jq/diff 외부 도구 입력 + 회귀 baseline 자료. ~140 LOC argparse + `_build_parser()` 11-analyzer 일괄 + `dump_snapshot(repo_path, repo_id)` Java rglob → ParseResult → asdict 직렬화. 출력 스키마 `{metadata: {repo_id, repo_path, generated_at, analyzers, totals}, files: {<rel-path>: {language, errors, entities, relations}}}`. **파일 경로 키 = 상대경로** (다른 머신에서도 안정적). `tests/test_dump_entities_snapshot.py` 8/8 PASS (analyzer wiring 11종 set 비교 / top-level keys / metadata 9 필드 / 절대경로 금지 / list 타입 / config_property 5+default+kebab round-trip / json round-trip / tmp_path 쓰기). **Slab 실행** : `11 files / 95 entities / 177 relations / 0 errors` (E1-f 검증과 동일). 출력 ~114KB. **`.gitignore`** 에 `**/.analyzed/` 추가 (regenerable artifact). 전체 1600 PASS / 20 FAIL. **활용** : 데모 코드 도착 시 같은 스크립트로 새 repo 스냅샷 떠서 즉시 비교 / parser 회귀 테스트 / 외부 도구 입력. **다음 우선** : (i) (선택) **JpaAnalyzer B5-7** — Spring Data JPA Repository 정식 처리 (데모 코드가 JPA 사용 시 효과 큼) / (ii) **DescribedInStore** — 자동 발견 메커니즘 미정, 데모 코드+매뉴얼 동반 결정 / (iii) **Slab 데모 코드 도착 대기** → B 매뉴얼 작성 / D4 UI 디자인 / E1-e 실증. 데모 코드 무관 인프라 7건 누적 완료. 백엔드/프론트 죽어있음. 이전 업데이트 : 2026-04-25 (OD-11-E1-i / EV 완료 — `GapCandidate.evidence` + `POST /gaps/{id}/reevaluate` + GapQueue evidence panel + 재평가 버튼. **D3-3 미수거 인프라 100% 종결**. **백엔드** : `gap_models.py` `GapCandidate` 에 `evidence: dict[str, object] = field(default_factory=dict)` 추가 (frozen). `RuleASTDiffer._make_candidate` / `CosineDrifter._make_candidate` / `HierarchicalGapEngine._apply_llm` / `LLMOnlyGapEngine` 각자 stage 별 evidence 채움 (rule_statement/fragment_text/mismatch/cosine/cutoff/llm_reasoning/llm_severity 등). `gaps_api.GapCandidateDTO` evidence 필드 노출. **신규 엔드포인트 `POST /api/modeling/gaps/{gap_id}/reevaluate`** (~75 LOC) : evidence 의 rule_statement+fragment_text 로 stub BusinessRule+ManualFragment 재구성 → comparator.compare() 직접 호출 → severity+reasoning 갱신, evidence merge 후 store.upsert. 에러 우선순위 **404→422→503** (gap 없음/MISSING_IN gap/comparator 미설정/evidence 누락 500). `asyncio.to_thread(comparator.compare, ...)` 이벤트 루프 보호. **`gaps_api.init()`** 시그니처 확장 — `llm_comparator: LLMComparator | None = None` 추가. `backend/main.py` lifespan 에서 기존 `_llm_comparator` 그대로 패스. **프런트** : `modeling.ts` `GapCandidateDto` 인터페이스 백엔드와 1:1 정정 (기존 `gap_id`/`gap_type`/`confidence` 가짜 필드 제거 → `id`/`detected_by`/`gap_mode`, `direction: GapDirection | null`, `evidence` 추가). `reevaluateGap(gapId)` 신규. `GapQueue.tsx` : 행 좌측 토글 컬럼 (▸/▾) → 펼친 행 evidence panel `<pre>` JSON pretty-print (minimal, 사용자 정책 "디자인 투자 최소화"), CONFLICTS_WITH 행에만 "재평가" Sparkles 버튼 → in-place 갱신 (전체 refresh 안 함), 모든 `g.gap_id` → `g.id` 정정 (가짜 필드 잔재 제거), 헤더+1 컬럼 / 빈 상태 colSpan 6→7 동기화. **TDD 신규 5 케이스** : test_scan_response_includes_evidence_for_conflicts / test_reevaluate_unknown_gap_returns_404 / test_reevaluate_missing_in_gap_returns_422 (detail "CONFLICTS_WITH ...") / test_reevaluate_without_comparator_returns_503 (detail "comparator") / test_reevaluate_calls_comparator_and_updates_gap (StubComparator → severity=critical, evidence.llm_reasoning 갱신, store.get 도 갱신). `tests/test_gaps_api.py` 20/20 PASS (기존 15 + 신규 5). 모델링 gap+rule+manual 회귀 146/146. 전체 1592 PASS / 20 FAIL (Section 1 baseline). main.py **157 routes (+1 reevaluate)**. TS GapQueue/modeling.ts clean (orphan ManualOntologyBuilder/ManualUpload 사전 에러 무관). **의의** : gap 후보 근거 데이터 (rule_statement/fragment_text/cosine/LLM reasoning) 가 처음으로 UI 노출 → 사용자가 "왜 충돌인지" 즉시 검증. 단일 gap LLM 재평가 → 전체 scan 안 돌리고 1건만 빠르게, 다른 gap confirmed 상태 보존. `<details>` minimal evidence panel — Section 2 UI 재설계 시 영향 적음. **D3-3 미수거 3/3 완결**. **다음 우선** : (i) **A1** entities.json 스냅샷 (50줄, 데모 코드 도착 전후 비교용) / (ii) (선택) **JpaAnalyzer B5-7** / (iii) **DescribedInStore** (자동 발견 메커니즘 결정 후) / (iv) **Slab 데모 코드 도착** 대기 → B 매뉴얼 / D4 UI 디자인 스펙 / E1-e 실증. **백엔드/프론트** : 둘 다 죽어있음. 이전 업데이트 : 2026-04-25 (OD-11-E1-h / SSE 완료 — `gaps_api.scan_stream` 진짜 stage-by-stage streaming. D3-3 미수거 2/3. `backend/modeling/api/gaps_api.py` `scan_stream_endpoint` 재구현 — 기존 buffered-flush PoC (전체 scan 종료 후 stages 일괄 emit) 제거, **`asyncio.Queue` + `loop.call_soon_threadsafe(queue.put_nowait, ...)` 패턴**으로 worker thread → main loop 안전 전달. `_on_progress(stage)` 콜백이 stage 받자마자 큐 push (STAGE_COMPLETE 만 suppress — 그 시점 result 없음). `_sync_scan()` 정상 종료 시 `(STAGE_COMPLETE, payload)` push, 예외 시 `("error", {"detail":"{ExcType}: {msg}"})` push, finally 에 sentinel `None` push. fire-and-forget worker `asyncio.create_task(asyncio.to_thread(_sync_scan))` (await 하면 다시 buffered). `stream()` async generator 가 `await queue.get()` drain → `None` 이면 return → finally 에서 worker_task 정리 (조기 끊김 방어). **신규 3 테스트** : `test_scan_stream_pattern_pushes_stages_via_threadsafe_queue` (진짜 asyncio loop + worker thread + asyncio.Queue + threading.Event gate 로 main loop 가 stage1 을 받기 전엔 worker 가 진행 못 하게 막음 — 5초 timeout 으로 buffered 리그레션 차단) + `test_scan_stream_emits_complete_event_with_payload` (complete event 가 라벨이 아닌 UnifiedScanResponse JSON payload 담음) + `test_scan_stream_propagates_scan_exception` (worker RuntimeError → "error" SSE event 후 generator 정상 종료, complete 안 옴). **TestClient ASGITransport 한계 메모** : 처음 `httpx.AsyncClient + ASGITransport` 로 E2E 실시간 검증 시도했으나 ASGITransport 가 SSE chunks 를 버퍼링해 클라이언트가 stage1 을 worker 5초 timeout 후에야 받음 → 패턴 unit test 로 우회. 실 uvicorn E2E 실시간 데모는 `demo_guide_modeling.md` 에 curl 시나리오로. `tests/test_gaps_api.py` 15/15 PASS (기존 12 + 신규 3). 모델링 gap+rule+manual 회귀 141/141 (E1-g 138 → +3). 전체 1587 PASS / 20 FAIL (전부 Section 1 baseline). **의의** : 큰 repo 스캔에서도 클라이언트가 stage 진행 라이브 (멈춘 줄 알던 5~10초 → 단계별 진행 가시). 에러 발생 시 SSE "error" event 로 대응 가능 (기존엔 raise → HTTP 500). worker_task finally 정리로 클라이언트 조기 끊김 thread leak 방어. **D3-3 미수거 2/3 완결**. **다음 우선** : (i) D3-3 미수거 3/3 — **GapQueue evidence panel + LLM 재평가 트리거** (백엔드 `POST /gaps/{id}/reevaluate` ~50줄 + 프런트 `<details>` minimal UI ~80줄, 사용자 정책 "최소 침습" 반영) / (ii) **A1** entities.json 스냅샷 / (iii) (선택) **JpaAnalyzer B5-7**. 보류 (데모 코드 의존) : DescribedInStore (자동 발견 메커니즘 미정) / B 매뉴얼 작성 / D4 UI 디자인 스펙. **백엔드/프론트** : 둘 다 죽어있음. 이전 업데이트 : 2026-04-25 (OD-11-E1-g / RR 완료 — `RuleRegistry` 신규 + `GapScanner.rule_source` auto-pull. D3-3 미수거 인프라 1/3. `backend/modeling/gap_detection/rule_registry.py` 신규 (~110 LOC) — `RuleRegistry` Protocol + `InMemoryRuleRegistry` (`dict[repo_id, dict[rule_fqn, BusinessRule]]` idempotent upsert) + `seed_rules_from_repo(repo_path, repo_id, registry)` convenience (`SeedResult(total_files_scanned, total_rules, errors)` 보고, JavadocRuleExtractor 활용 .java 자동 walk, FQN 결정성 idempotent, OSError/UnicodeDecodeError/Exception 격리 처리). `gap_detection/__init__.py` export 4종 (RuleRegistry/InMemoryRuleRegistry/SeedResult/seed_rules_from_repo). **`GapScanner` 확장** : `rule_source: Optional[RuleRegistry]` 필드 + `_resolve_rules(business_rules, repo_id)` (fragments 패턴 답습 — `None` → auto-pull, 명시 list/[] → 그대로). `business_rules` 시그니처 `Iterable=()` → `Optional[Iterable]=None` 격상. **`gaps_api.ScanRequest`** : `rules: list[BusinessRule] = Field(default_factory=list)` → `rules: list[BusinessRule] | None = None` (body 미지정 시 auto-pull). **`backend/main.py` lifespan** : `InMemoryRuleRegistry()` 인스턴스 + `GapScanner(rule_source=_rule_registry)` 주입. `tests/test_rule_registry.py` 16/16 PASS (TestProtocol 1 + TestBasic 5 + TestIdempotency 1 + TestMultiRepoIsolation 2 + TestSeeder 4 + TestScannerIntegration 2 — explicit [] 도 auto-pull 차단 검증). 모델링 gap+rule+manual 회귀 138/138 (E1-f 122 → +16). 전체 1584 PASS / 20 FAIL (전부 Section 1 baseline). **End-to-end demo** : `seed_rules_from_repo('sample-repos/slab-design-engine/src/main/java', 'slab-design-engine', reg)` → 11 java files → **16 BusinessRule indexed** → `scanner.scan(business_rules=None, fragments=[])` errors=0 정상. main.py 156 routes 그대로. **운영 시드 메커니즘** : `seed_rules_from_repo` Python 함수만 노출, startup auto-seeding 안 함 (어떤 repo 가져올지 환경별 의견 분리 — REPL/스크립트/향후 API 중 선택). **의의** : gap_scan 이 진정한 "repo_id 만 주면 됨" 모드 진입. fragments + rules 양쪽 자동 auto-pull. 사용자 데모 시 `POST /api/modeling/gaps/scan {"repo_id":"slab-design-engine"}` 단발 호출만으로 가능. **D3-3 미수거 3개 중 1/3 완결**. **다음 우선** : (i) D3-3 미수거 2/3 — **SSE 진짜 stage-by-stage streaming 재설계** (worker thread + asyncio.Queue + `loop.call_soon_threadsafe`, 현재 buffered-flush PoC) / (ii) D3-3 미수거 3/3 — **GapQueue evidence panel + LLM 재평가 트리거** UI / (iii) **A1** entities.json 스냅샷 / (선택) **JpaAnalyzer B5-7**. 보류 (데모 코드 의존) : DescribedInStore (자동 발견 메커니즘 미정) / B 매뉴얼 작성 / D4 UI 디자인 스펙. **백엔드/프론트** : 둘 다 죽어있음. 이전 업데이트 : 2026-04-25 (OD-11-E1-f / CPA 완료 — `ConfigPropertiesAnalyzer` 11번째 Spring analyzer. 데모 코드 무관 범용 인프라 정책 3번째 산출물. `backend/modeling/code_analysis/spring/config_properties_analyzer.py` 신규 (~190 LOC) + `spring/__init__.py` export. **3 어노테이션 형식** (keyword `prefix=...` / 단일 값 / 마커) 모두 처리. **Field 선택** : 비-static instance field (final 허용 — 생성자 바인딩 호환, constants 제외). **Entity FQN** = `{prefix}.{fieldName}` camelCase canonical. **attributes** : `prefix`/`key`/`key_kebab` (Spring relaxed binding alias `_CAMEL_TO_KEBAB_RE = r"([a-z0-9])([A-Z])"`)/`field_name`/`field_type`/`default_value` (initializer literal raw text — 없으면 키 부재)/`bound_class_fqn`/`bound_field_fqn` (FIELD 백링크). **Relation** = 기존 `has_config` (parser_protocol L169 `spring_bean/method → config_property`). `tests/test_spring_config_properties_analyzer.py` 27/27 PASS (TestAnnotationForms 5 + TestFieldSelection 4 + TestAttributes 6 + TestHasConfigEdge 4 + TestKebabCaseEdgeCases 2 + TestSlabSample 4 + TestProtocol 2). **Slab 11-analyzer end-to-end** : 90→**95 entities (+5)** / 172→**177 relations (+5)** — 정확히 EquipmentProperties 5 field. `slab.equipment.maxThicknessMm` `default_value="240.0"` `field_type="double"` `key_kebab="slab.equipment.max-thickness-mm"` `bound_field_fqn="com.ontong.slab.config.EquipmentProperties.maxThicknessMm"` 노출. 5 has_config 엣지 모두 source=EquipmentProperties FQN. 모델링 코드 분석 회귀 359/359 (E1-d 332 → +27). 전체 1568 PASS / 20 FAIL (전부 Section 1 baseline). **runtime wiring** : backend/main.py 미등록 (현재 Spring analyzer 들은 lifespan wiring 없음 — 테스트+REPL 단계, Phase E 코드 분석 파이프라인 FastAPI 노출 시 11 analyzer 모두 합류). **CONFLICTS_WITH gap 감지** : 3번째 코드 쪽 입력 확보 (A2 매직넘버 + A3 자연어 룰 + CPA config_property default 값). 매뉴얼 "두께 250mm 이상 허용" ↔ `slab.equipment.maxThicknessMm.default_value=240.0` 직접 비교 가능. **다음 우선** (데모 코드 무관 범용 인프라 정책) : (i) **D3-3 미수거 인프라** — `RuleRegistry`/`DescribedInStore` 설계 (D3-3 시 fragments 만 auto-pull, rules/described_in body 필수로 미룸 — A3/CPA 산출을 첫 시드로 활용 가능) / SSE 진짜 stage-by-stage streaming 재설계 (현재 buffered-flush PoC) / GapQueue evidence panel + LLM 재평가 트리거. (ii) **A1** entities.json 스냅샷. (iii) (선택) JpaAnalyzer B5-7 — `@Entity`/`@Repository` 정식 처리. 보류 (데모 코드 의존) : B 매뉴얼 작성 / D4 UI 디자인 스펙. **백엔드/프론트 상태** : 둘 다 죽어있음. 이전 업데이트 : 2026-04-25 (OD-11-E1-d / A3 완료 — Javadoc → BusinessRule 추출기. 데모 코드 무관 범용 인프라 정책 2번째 산출물. `backend/modeling/code_analysis/javadoc_rule_extractor.py` 신규 (~190 LOC). tree-sitter 재파싱 → `block_comment` 노드 walk → `/** ... */` 만 채택 (일반 `/* */` skip) → `_next_declaration_sibling()` 로 다음 sibling declaration (class/interface/enum/method/constructor — field 는 v1 skip) 매칭 → `(line_start, kind)` 색인으로 ParseResult.entities FQN 해소 → `_strip_javadoc_decoration()` `/**`/`*/`/`*` 제거 → bullet (`- ` `* ` `1. `) 마커 단일 후보 + 일반 라인 `(?<=다)\.\s+|(?<=요)\.\s+|(?<=니)\.\s+` 한국어 sentence 분리 → `_is_rule_like()` 휴리스틱 (keyword `이상\|이하\|초과\|미만\|불가\|금지\|허용되지\|던진다\|이어야 한다\|여야 한다\|되어야 한다\|해야 한다` OR 부등식 `≤≥<=>===!=` + 식별자) → `_classify_severity()` HARD if 금지/Exception 키워드 else SOFT → `BusinessRule(qualified_name="{target_fqn}#rule{N}", statement, terms_ref=[], severity, source="javadoc:{target_fqn}", confirmed=False, created_at)` + `CodeRelation(kind=VALIDATES, source=rule_fqn, target=target_fqn)`. **명세 정정** : HANDOFF/CHANGES 의 "REALIZES 엣지" 표기 오류 → 실제는 **VALIDATES** (parser_protocol.py L177 `business_rule → method`). REALIZES 는 BusinessTerm 전용. `tests/test_javadoc_rule_extractor.py` 23/23 PASS (TestBasic 3 + TestClassLevelBullets 4 + TestMethodLevel 4 + TestSeverity 3 + TestMetadata 3 + TestSlabSample 4 + TestExtractorClassAPI 2). **Slab 실증** : WeightMaximizer 7 rules (목적식 + 제약 체인) / EquipmentConstraintChecker 7 rules (4 class bullets + 3 method-level) / Slab 1 rule (HARD Exception) / EquipmentProperties 0 (descriptive only) — **총 15 BusinessRule + 15 VALIDATES**. SOFT 11 + HARD 4 분류 정확. 모델링 회귀 332/332 (E1-c 309 → +23). 전체 1541 PASS / 20 FAIL (전부 Section 1 baseline). **의의** : CONFLICTS_WITH gap 감지의 양쪽 입력 (코드 매직넘버 from A2 + 코드 자연어 룰 from A3) 모두 확보. RuleASTDiffer 가 매뉴얼 룰 ↔ 코드 룰 통합 비교 가능. terms_ref 는 빈 list — 향후 C3 TermResolver 가 채움. **다음 우선** (데모 코드 무관 범용 인프라 정책 — 사용자 합의 2026-04-25) : (i) **ConfigPropertiesAnalyzer** 11번째 Spring analyzer 격상 — `@ConfigurationProperties` → `config_property` entity + field-by-field config key (`slab.equipment.maxThicknessMm`) 추출. Slab 의 EquipmentProperties 가 현재 단순 class. (ii) **D3-3 미수거 인프라** — `RuleRegistry`/`DescribedInStore` 설계 (D3-3 시 fragments 만 auto-pull, rules/described_in 은 body 필수로 미룸) / SSE 진짜 stage-by-stage streaming 재설계 (현재 buffered-flush PoC) / GapQueue evidence panel + LLM 재평가 트리거. (iii) **A1** entities.json 스냅샷 스크립트. 보류 (데모 코드 의존) : B 매뉴얼 작성 / D4 UI 디자인 스펙 / E1-e 실증. **백엔드/프론트 상태** : 둘 다 죽어있음 (PID 94891/72184 not running). 이전 업데이트 : 2026-04-25 (OD-11-E1-c / A2 완료 — JavaParser field 추출 확장. 사용자 정책 "Slab 데모 코드 도착 전까지 데모 코드 무관 범용 인프라부터" 적용 → A2 가 가장 risky 분기 (240/1.02/50 매직넘버 노출이 CONFLICTS_WITH 의 코드 쪽 입력) → TDD RED 20 테스트 → GREEN. `backend/modeling/code_analysis/java_parser.py` `_extract_field` 확장 + `_classify_initializer` 신규 helper (literal_number/literal_string/literal_boolean/literal_null/literal_char/expression 6 분류, `_NUMERIC_LITERAL_TYPES` frozenset 6종 — decimal/hex/octal/binary integer + decimal/hex floating-point, `unary_expression` 부호 wrapping 처리). attributes 3 키 추가 : `field_type` (선언 타입 raw text — primitive / reference / generic) + `initializer` (초기화식 raw text) + `initializer_kind` (6 분류). 기존 `parent`/`modifiers` 인자 그대로 보존. `tests/test_java_parser_field_attributes.py` 신규 20/20 PASS (TestFieldType 4 / TestInitializerLiteral 10 / TestInitializerEdgeCases 3 / TestSlabSampleLiterals 3, 0.06s). **Slab 실증** : `WeightMaximizer.WEIGHT_BIAS_FACTOR` `field_type=double init=1.02 kind=literal_number` ✓ / `WeightMaximizer.GRID_STEP_MM` `init=50.0` ✓ / `EquipmentProperties.maxThicknessMm` `init=240.0` ✓ + 보너스 4 (rollingMillMaxWidthMm=2400 / furnaceMaxLengthMm=12000 / craneMaxLoadKg=45000 / minThicknessMm=180). 모델링 회귀 (`-k "java_parser or spring or code_analysis or graph or cross_file"`) 309/309 PASS. 전체 1518 PASS / 20 FAIL (전부 Section 1 baseline — ag33_hooks/confidence/lineage_validation/p2b6/pydantic_ai/rag_tag_boost/skill_api, 우리 변경 무관). TODO `OD-11-E1-c [x]` 추가, CHANGES.md 2026-04-25 "JavaParser field 추출 확장" 섹션 추가, CHANGES.md 의 후속 후보 A2 `[x]` 처리. **다음 우선** (사용자 정책 — 데모 코드 무관 범용 인프라) : (i) **A3** Javadoc → BusinessRule 추출기 (`backend/modeling/code_analysis/javadoc_rule_extractor.py` 신규, 한국어 자연어 룰 → `BusinessRule` DTO + `REALIZES` 엣지) — gap scan 의 코드 쪽 rule 입력. 또는 (ii) **ConfigPropertiesAnalyzer** 11번째 Spring analyzer 격상 — `@ConfigurationProperties` 처리는 어떤 Spring Boot 프로젝트에든 필수, 실제 데모 코드 거의 100% 사용. 또는 (iii) **D3-3 미수거 인프라** (`RuleRegistry`/`DescribedInStore` 설계 / SSE 진짜 stage-by-stage streaming / GapQueue evidence panel). 보류 : B 매뉴얼 작성 (실제 데모 코드의 매직넘버 모르면 다시 써야 함) / D4 UI 디자인 스펙 (실제 gap 후보 출력 입력 필요). **백엔드/프론트 상태** : 둘 다 죽어있음 (PID 94891/72184 not running). E1 작업 들어가려면 재기동 필요. ManualRegistry in-memory 라 매뉴얼 업로드는 매 세션 새로. 이전 업데이트: 2026-04-21 (Slab 엔진 코드 분석 파이프라인 등록 검증 완료 — OD-11-E1-b. 사용자 "A로 진행" 승인 직후 `sample-repos/slab-design-engine` 을 onTong `JavaParser` + Spring 10-analyzer 에 일괄 통과시킴. **JavaParser 기본 85 entities / 167 relations / 0 errors**. **Spring 10-analyzer 적용 시 90 entities (+5) / 172 relations (+5) / 0 errors**. 신규 entity = `spring_bean` × 4 (Application/Service/WeightMaximizer/Checker/Controller 중 stereotype 매칭) + `http_endpoint` × 1 (`POST /slabs/design`). 신규 relation = `AUTOWIRES` × 4 (Controller→Service / Service→WeightMaximizer / WeightMaximizer→Checker / WeightMaximizer→Properties) + `MAPS_URL` × 1. **DI 그래프 검증** : 의도한 4-단 wiring 그대로 그래프에 반영 = 파서 실증 OK. **한계 / 갭** : (1) `EquipmentProperties` 가 `config_property` 로 승격되지 않음 — 10-analyzer 셋 안에 `@ConfigurationProperties` 전담 analyzer 없음 (현재는 `class` + 의존자 측 AUTOWIRES 만 캡처). (2) `field.attributes` 에 매직넘버 리터럴 (240/1.02/50) 이 들어가는지 미확인 — CONFLICTS_WITH 의 매직넘버 감지 핵심. (3) Javadoc → BusinessRule 추출기 부재 — 한국어 자연어 룰 ("두께 180~240mm 이상" 등) 이 코드 쪽 규칙 입력으로 전달돼야 gap scan 5종 후보가 실제로 잡힘. **다음 세션 우선 후보** : (A1) `sample-repos/slab-design-engine/.analyzed/entities.json` 스냅샷 덤프 (재현 가능성 / diff) / (A2) `field.attributes` 리터럴 값 검증 — 240/1.02/50 이 attribute dict 에 들어가는지 확인 후 필요 시 `JavaParser` field 추출 확장 / (A3) Javadoc → BusinessRule 추출기 (한국어 자연어 룰 → `BusinessRule` DTO + `REALIZES` 엣지) — gap scan 의 코드 쪽 입력 보강 / (B) 대응 매뉴얼 작성 — 의도적 gap 5종 트리거 (Slab 두께 250mm / 안전계수 1.05 / 그리드 25mm / 보정 후 크레인 재검증 / `adjustWeightBias()` 매뉴얼 미언급) → ManualRegistry 업로드 → `POST /api/modeling/gaps/scan` 5건 후보 검증. **선택** `ConfigPropertiesAnalyzer` 추가. TODO `OD-11-E1-b [x]` 추가, CHANGES.md 2026-04-21 "Slab Design Engine 파서 파이프라인 등록 검증" 섹션 추가. **백엔드 / 프런트 상태** : backend `:8001 --reload` PID 94891 alive (`/tmp/ontong_backend.log`), frontend `:3000 next dev --turbopack` PID 72184 alive. 이전 업데이트 : 2026-04-21 Slab Design Engine 샘플 프로젝트 생성 — gap scan 실증용. `sample-repos/slab-design-engine/` Spring Boot 3 / Java 17 프로젝트 14 파일 : `SlabDesignApplication` 부팅 엔트리 + `domain/{Slab,OrderSpec,SteelGrade}` (직육면체 L×W×T, 밀도 7850~7860, weight=ρ·V) + `config/EquipmentProperties` (@ConfigurationProperties "slab.equipment", 설비 5 파라미터) + `constraint/{ConstraintViolation,EquipmentConstraintChecker}` (@Component, 규칙별 메서드 분리 — 압연기 폭 2400 / 가열로 길이 12000 / 두께 180~240 / 크레인 하중 45000) + `optimizer/{DesignCandidate,WeightMaximizer}` (@Component, 50mm 그리드 + `max ρ·L·W·T`, 안전계수 `WEIGHT_BIAS_FACTOR=1.02`) + `service/SlabDesignService` (@Service 파사드) + `controller/SlabDesignController` (@RestController, POST `/slabs/design`, DesignRequest/Response records) + `pom.xml` (Spring Boot 3.2.5 starter-web/validation/config-processor/lombok optional) + `application.yml` (설비 외부화) + `README.md` (도메인 요약 + 의도적 gap 후보 5종 표). **의도적 gap**: (1) `maxThicknessMm=240` vs 예상 기준서 "250mm 이상" → CONFLICTS_WITH (2) `WEIGHT_BIAS_FACTOR=1.02` vs 예상 "1.05" → CONFLICTS_WITH (3) `adjustWeightBias()` 메서드 매뉴얼 없음 → MISSING_IN manual (4) 보정 후 크레인 재검증 누락 → MISSING_IN code (5) `GRID_STEP_MM=50` vs 예상 "25mm" → CONFLICTS_WITH. 한국어 Javadoc 에 비즈니스 룰 자연어 포함 ("slab 두께는 180mm 이상 240mm 이하여야 한다" 등). `javac 17` domain+constraint 순수 Java clean compile (Spring annotation 참조 에러는 classpath 문제일 뿐). TODO OD-11-E1-a `[x]`. CHANGES.md 2026-04-21 "Slab Design Engine 샘플" 섹션 추가. **다음 후보**: (A) `sample-repos/slab-design-engine` 을 onTong 코드 분석 파이프라인에 등록 → CodeEntity 그래프 확인 (B) 대응 매뉴얼 (wiki/ 또는 별도) 작성 → ManualRegistry 업로드 → gap scan 5종 재현. 이전 업데이트 : 2026-04-21 (UX 정리 — ModelingSection 사이드바 탭 축소. `frontend/src/components/sections/ModelingSection.tsx` 편집 : MAIN_NAV 단일 "갭 큐"(`gap-queue`) + SETTINGS_NAV `[]` + `needsRepoSelector` 유도 상수(`MAIN_NAV.some(n=>n.id!=="gap-queue") || SETTINGS_NAV.length>0`) + `activeView` 초기값 `"gap-queue"`. Repository 입력/플레이스홀더/"SCM 데모 프로젝트 로드" 버튼은 `needsRepoSelector && !repoId` 조건부 렌더 → 현재 조건 false 라 `<GapQueue/>` 즉시 진입. ViewRouter switch 의 legacy case (analysis/simulation/workbench/code/ontology/mapping/impact/approval) 는 전부 보존 (import 도 유지) — 향후 재연결 시 MAIN_NAV 만 되돌리면 복구. 미사용 lucide 아이콘 7개(Code/Network/GitBranch/GitCompare/Search/CheckSquare/Zap) import 제거. 배경 : 사용자 "브라우저 들어갔더니 옛날 기능 다 살아났음 + UI/UX 대대적 개편 가능성 + 테스트 불필요 기능 숨김 요청" → `memory/feedback_ui_ux_rework.md` 에 **최소 침습** 원칙 저장 (리팩토링 금지, 디자인 투자 금지, 새 UI 는 '일단 돌아가게' 수준). TS compile clean (orphan ManualOntologyBuilder/ManualUpload 제외). dev server :3000 HTTP 200. TODO OD-11-UX-1 `[x]`. CHANGES.md 2026-04-21 "ModelingSection 사이드바 정리" 섹션 추가. 이전 업데이트: 2026-04-21 (OD-11-D3-3 완료 — Gap Queue REST/SSE API + 프런트 승인 UI. `backend/modeling/gap_detection/gap_scanner.py` 신규 (`GapScanner` 오케스트레이터 : MissingInDetector + GapEngine 를 단일 스캔으로 묶고 ManualRegistry 에서 fragments auto-pull, `UnifiedScanResult` frozen dataclass `.all` property, progress callback 4단계 `scanning → stage1_missing_in → stage2_conflicts → complete`) + `backend/modeling/api/gaps_api.py` 신규 (`ScanRequest` Pydantic + `GapCandidateDTO.from_candidate()` 팩토리 + `init(scanner, gap_store, manual_registry)` 주입 훅 + 4 엔드포인트 : `POST /scan` unified sync + `POST /scan/stream` SSE buffered-flush (asyncio.to_thread + stages list 수집 → await 완료 후 일괄 emit 로 TestClient race 해결) + `GET ""` direction/severity/include_confirmed 필터 + `POST /{gap_id}/confirm` 404-on-miss) + `backend/modeling/gap_detection/embedding_drifter.py` `HashingTextEmbedder` 추가 (SHA256 3-gram 64-dim L2 normalized 결정적 fallback, OpenAI 의존성 없이 `CosineDrifter` 초기화 가능) + `backend/modeling/gap_detection/__init__.py` `GapScanner`/`UnifiedScanResult`/`HashingTextEmbedder` export + `backend/main.py` lifespan 확장 (`InMemoryGapStore` → `MissingInDetector` → `create_gap_engine(HIERARCHICAL, rule_differ, drifter, llm_comparator, gap_store)` → `GapScanner(fragment_source=_manual_registry)` → `gaps_api.init(...)` + 라우터 include, 156 routes +4) + `frontend/src/lib/api/modeling.ts` Gap 섹션 추가 (`GapCandidateDto` / `UnifiedScanResponse` / `GapScanRequest` / `SseEvent` + `scanGaps` / `scanGapsStream` (async generator `fetch + ReadableStream + TextDecoder`, AbortSignal 지원) / `listGaps` (direction/severity/includeConfirmed 쿼리) / `confirmGap`) + `frontend/src/components/sections/modeling/GapQueue.tsx` 신규 (필터 바 direction all/code_only/manual_only/conflicts + severity 드롭다운 + include_confirmed 체크박스 + "스캔 실행" 버튼 SSE stream + Loader2 진행 단계 라이브 + 후보 테이블 direction/severity 컬러 배지 + target/counterpart FQN mono + 확정 버튼) + `frontend/src/components/sections/ModelingSection.tsx` MAIN_NAV 에 "갭 큐" (`gap-queue`, `ListChecks` 아이콘) 추가 + ViewRouter case 추가. **주요 결정** : Q1=Partial Hybrid (fragments 만 auto-pull, rules/described_in 은 body 필수 — 전용 store 아직 없음, Phase E 에서 `RuleRegistry` 설계 예정) / Q2=Unified scan (단일 엔드포인트가 MISSING_IN + CONFLICTS_WITH 함께 실행, 프론트는 필터로만 가름) / Q3=SSE primary + `/scan` sync fallback (buffered-flush 는 PoC 수용 가능 trade-off, prod 는 진짜 stage-by-stage streaming 재설계). `tests/test_gap_scanner.py` 10 + `tests/test_gaps_api.py` 12 = 22/22 PASS (0.26s). 모델링 gap 계열 127/127. 전체 pytest 1498 passed / 31 baseline (우리 변경 무관 — wiki_search/docx·pdf parsers/skill_api/confidence/image_analysis 사전 실패). TS clean (orphan `ManualOntologyBuilder`/`ManualUpload` 는 사전 WIP, 어디에도 import 되지 않음 — 본 스텝과 무관). **OD-11-D3 3-subphase 완료 (D3-1 + D3-2-a + D3-2-b + D3-3). 다음 : D4 (사람 검증 UI 디자인 스펙) 또는 Phase E (Slab 실증) 진입 결정.** 이전 업데이트 : 2026-04-21 OD-11-D3-2-b 완료 — CONFLICTS_WITH LLM Comparator (pydantic-ai Agent). `backend/modeling/gap_detection/llm_comparator.py` (~210 LOC) 신규 : `LLMComparisonResult(BaseModel)` pydantic-ai 구조화 출력 (`severity: Literal["low","medium","high","critical"]` + `reasoning: str`) + `_SYSTEM_PROMPT` ERP/MES/SCM 충돌 분석가 역할 + severity decision guide (low/medium/high/critical) + `_render_user_message()` rule FQN/terms_ref/statement + fragment FQN/section_fqn/kind/text + prior severity 직렬화 + `_default_agent_factory()` lazy import of pydantic-ai `Agent(get_model(), output_type=..., retries=2, defer_model_check=True)` — `llm_factory.get_model()` 재사용으로 모델 스위치 단일 지점 (`settings.litellm_model` "provider/model") + `PydanticAILLMComparator(agent_factory=None)` Protocol 구현 `agent.run_sync()` 블로킹 호출 + **graceful degrade** 어떤 예외도 재발생 안 함 (`(prior_severity, "LLM error: {ExcType}: {msg}")` 반환) + **belt-and-suspenders** `_coerce_conflict_severity()` 이차 방어 — CONFLICTS_WITH 카테고리(LOW/MEDIUM/HIGH/CRITICAL) 화이트리스트만 허용, "hard"/"soft" MISSING_IN 카테고리 또는 unknown 문자열은 `None` → `MEDIUM` 폴백 + reasoning 에 "invalid severity" 경고. `backend/modeling/gap_detection/__init__.py` 편집 : `LLMComparisonResult`, `PydanticAILLMComparator` public re-export. `backend/main.py` lifespan 편집 : D2-2 `manuals_api.init(...)` 직후 `ONTONG_LLM_COMPARATOR=openai` 환경 변수 분기 — try/except 폴백 (기본 `_llm_comparator=None` → Hierarchical 엔진이 prior severity 유지). 인스턴스 보관만, engine 주입은 D3-3 에서 `create_gap_engine(llm=_llm_comparator)` + `asyncio.to_thread(comparator.compare, ...)` 로 이벤트 루프 보호. `pyproject.toml` 편집 : `[tool.pytest.ini_options].markers` 에 `integration: marks tests that hit external services (real LLM, network)` 등록 → unregistered marker warning 억제. `tests/test_llm_comparator.py` 신규 13 테스트 (output schema 2 / protocol conformance 1 / successful compare 2 / graceful errors 3 / prompt rendering 2 / defensive fallbacks 2 / integration smoke 1). `_FakeAgent` test double 로 HTTP 없이 compare 전체 경로 검증. 실 LLM 호출은 `@pytest.mark.integration` + `@pytest.mark.skipif(not os.environ.get("ONTONG_LLM_INTEGRATION"))` 이중 게이트 → 기본 `pytest` SKIP, `ONTONG_LLM_INTEGRATION=1 pytest -m integration` 수동 회귀. D3-2-b 범위 12 PASS + 1 SKIP. 모델링 회귀 747/747 (D3-2-a 735 → +12). 전체 1476 PASS / 21 baseline FAIL / 1 SKIP (D3-2-a 1464 → +12). 152 routes (D3-2-b 도 API 미추가 — D3-3 예정). `ast.parse(backend/main.py)` OK. **D3 3-subphase 중 2/3 (D3-1 + D3-2 완료 [D3-2-a deterministic + D3-2-b LLM], D3-3 API + UI 대기).** 다음 : D3-3 승인 큐 + REST/SSE API + 프런트 (`backend/modeling/api/gaps_api.py` + `frontend/src/components/sections/modeling/GapQueue.tsx`) 또는 D4 UI 디자인 스펙 선행. 이전 업데이트 : 2026-04-21 OD-11-D3-2-a 완료 — CONFLICTS_WITH deterministic 2 stage + Strategy skeleton. `backend/modeling/gap_detection/` 에 `rule_ast_differ.py` (~230 LOC, `RuleStatementTokens(numbers,comparators,units)` frozen dataclass + `extract_quantities()` 정규식 4 패턴 — 숫자 `-?\d+(?:\.\d+)?` / 비교 ≥≤>=<===!=>< 이상·이하·초과·미만·같음·동일·부터·까지 / 단위 `% 원 달러 $ 개 건 명 회 kg g t 일 시간 분 초 주 월 년` + `DiffOutcome` 3 mismatch 셋 + `_canonical_comparator` ≥/>=/이상→"ge" 동치 + `RuleASTDiffer.compare`/`find_conflicts` → `GapSeverity.HIGH` 빈 토큰 mismatch 아님 · IMAGE skip) + `embedding_drifter.py` (~120 LOC, `@runtime_checkable TextEmbedder` Protocol + zero-safe `_cosine` + `CosineDrifter(embedder, cutoff=0.65)` → `GapSeverity.MEDIUM` described_in 매핑 쌍에서 cos < cutoff · IMAGE skip) + `gap_engine.py` (~240 LOC, `@runtime_checkable LLMComparator` Protocol (`compare(rule, fragment, prior_severity, config) -> (severity, reasoning)`) + `@runtime_checkable GapEngine` Protocol + `HierarchicalGapEngine(rule_differ, drifter, llm_comparator=None, gap_store=None)` : stage 1 rule_ast hit → `locked_pairs` 마킹 / stage 2 drift locked_pairs skip — dedup / stage 3 LLM optional severity+reasoning merge / store 주입 시 upsert + `LLMOnlyGapEngine(llm_comparator=None, gap_store)` — comparator 없으면 `[]` + warning + `create_gap_engine(mode, …)` GapMode 분기 팩토리). `GapSeverity` Enum 확장 : 기존 HARD/SOFT (MISSING_IN) + LOW/MEDIUM/HIGH/CRITICAL (CONFLICTS_WITH). Stable id prefix per stage (`rule_ast|…` / `drift|…` / `llm_only|…`) sha1[:16] 로 stage 충돌 방지. BusinessRule.statement 이 free-text str 이라 rule_ast = **수량 표현만 regex 추출** (과도한 NLP 투자 회피) — 자연어 비교는 embedding/LLM 위임. `tests/test_rule_ast_differ.py` 14 + `tests/test_embedding_drifter.py` 7 + `tests/test_gap_engine_conflicts.py` 9 + `tests/test_manual_models.py::test_gap_enum_values` 1 = 30/30 신규 PASS (0.08s). 모델링 회귀 735/735 (D3-1 기준 705 → +30). 전체 1464 PASS / 21 baseline FAIL (1434 → +30). 152 routes (D3-2-a 도 API 미추가 — D3-3 예정). **D3 3-subphase 중 1.5/3 (D3-1 + D3-2-a 완료, D3-2-b LLM 실 구현 / D3-3 REST API 대기).** 다음 : D3-2-b (LLM Comparator 실 구현, pydantic-ai Agent or OpenAI direct, `backend/modeling/gap_detection/llm_comparator.py` + `ONTONG_LLM_COMPARATOR=openai` startup 분기) 또는 D3-3 (REST + SSE + 승인 큐 UI 병행) 또는 D4 UI 디자인 스펙. 이전 업데이트 : 2026-04-21 OD-11-D3-1 완료 — `backend/modeling/gap_detection/{gap_models,gap_store,missing_in_detector,__init__}.py` 신규 패키지 (MISSING_IN 양방향, code_only/manual_only, SOFT/HARD, `sha1(direction|target|counterpart)[:16]` stable id, SimpleHeuristicExtractor 4 regex, `InMemoryGapStore` confirmed-보호). 28 tests PASS + 모델링 회귀 705 + 전체 1434. 이전 업데이트 : 2026-04-21 OD-11-D2-3 완료 — `backend/modeling/manual_ingest/{watch_folder.py, git_hook_webhook.py}` + `backend/modeling/api/manuals_api.py` 에 `POST /manuals/git-hook` 추가 + `frontend/src/lib/api/modeling.ts` 확장 + `frontend/src/components/sections/modeling/ManualUpload.tsx` 신규 + `ModelingSection.tsx` 탭 추가. `ManualFolderWatcher` (폴링, watchdog 무의존, mtime+size 스냅샷 diff → `IngestMode.UPDATE`, 재귀, `seed_existing` 토글, 삭제 추적, path 거부) + `parse_git_webhook_payload` + `ingest_changed_files` (repo_root path escape 방어, unsupported → skipped, removed 집계만) + POST JSON `/manuals/git-hook` (`asyncio.to_thread`, `GitHookResponseDTO`, 400/503 처리) + 프런트 `ManualUpload.tsx` (모드 pill + 드롭존 + SSE 라이브 이벤트 + 목록 + authoritative 토글 스위치, `uploadManualStream` 은 fetch+ReadableStream+TextDecoder 로 POST+SSE 직접 구현 — EventSource 는 POST 불가). `tests/test_manual_watch_folder.py` 12 + `tests/test_manual_git_hook_webhook.py` 11 + `tests/test_manuals_api_git_hook.py` 7 = 30/30 PASS. 모델링 회귀 677/677 PASS. 전체 1406 PASS / 21 FAIL (baseline 무관). TS 0 errors. 152 routes (+1). **D2 3-subphase 종결 — D2-1 + D2-2 + D2-3 모두 완료.** 다음 : D3 Gap Detector 또는 D4 UI. 이전 업데이트 : 2026-04-20 (OD-11-D2-2 완료 — `backend/modeling/manual_ingest/{manual_registry.py, embedding_store.py, pipeline.py}` + `backend/modeling/api/manuals_api.py` 신규. `ManualIngestPipeline` (SKIP/UPDATE/FORCE 모드 + doc-fqn+checksum 두 단계 dedup + optional graph/embedding 주입) + `InMemoryManualRegistry` (primary fqn 인덱스 + secondary checksum 인덱스 + `set_authoritative` 토글 Q8=B) + `InMemoryManualEmbeddingStore` + `ChromaManualEmbeddingStore` (`manual_fragments` 컬렉션) + `CodeGraphManualWriter` 어댑터 (Manual*→CodeEntity via 기존 CodeGraphWriter.write_entities, D1.6 kind 재사용 / containment 는 property) + REST `POST /api/modeling/manuals/upload` (multipart, mode query) + `GET /manuals` + `POST /manuals/{fqn:path}/authoritative` + SSE `POST /manuals/upload/stream` (worker thread + queue + asyncio.to_thread drain, 이벤트 5종 detecting/parsing/skipped/persisting/complete). 업로드는 `tempfile.mkdtemp()+원본 파일명` 유지 (NamedTemporaryFile 쓰면 두 번째 업로드 시 stem 바뀌어 dedup 실패 — Red 에서 발견). `backend/modeling/api/modeling.py` 에 `router.include_router(manuals_api.router)` 추가. `backend/main.py` lifespan 에 5 파서 + Registry + Chroma 가용 시 ChromaManualEmbeddingStore 아니면 InMemory fallback + graph_writer=None (D3 주입 예정) wiring. `tests/test_manual_registry.py` 13 + `tests/test_manual_ingest_pipeline.py` 13 + `tests/test_manuals_api.py` 10 = 36/36 PASS. 모델링 회귀 329/329 PASS. 전체 1376 PASS / 21 FAIL (baseline Section 1 영역, 무관). D2 3-subphase 중 2/3 완료. **다음 : D2-3 — `watch_folder.py` + `git_hook_webhook.py` + 프런트 업로드 UI. D2-2 의 `ManualIngestPipeline.ingest` + SSE endpoint 를 3 트리거가 그대로 공유.** 이전 업데이트 : OD-11-D2-1 완료 — `backend/modeling/manual_ingest/` 신규 패키지에 `ManualParser` Protocol + `ManualParseResult` DTO + FQN/checksum helpers + 5 포맷 파서 (md/pdf/docx/pptx/image) 전부 Red→Green 완료. 48/48 파서 단위 PASS + 251/251 모델링 회귀 PASS. `pyproject.toml` 에 `pypdf ^5.0` / `pdfplumber ^0.11` / `python-docx ^1.2` / `python-pptx ^1.0` 추가. 이전 업데이트 : OD-11-D1.6 완료 — parser_protocol EntityKinds/RelationKinds Round 3 확장 TDD 사이클 완주. 24/24 단위 PASS + 524/524 modeling 회귀 PASS. `backend/modeling/code_analysis/parser_protocol.py` 에 Entity +5 (business_process/role/manual_document/manual_section/manual_fragment) + Relation +6 (part_of/responsible_for/parent_process/described_in/conflicts_with/missing_in) 등록, 모두 category="concept". `EntityKinds`/`RelationKinds` 편의 상수 확장. 산출물 : parser_protocol.py 편집 + `tests/test_parser_protocol_phase_d.py` 신규 24 테스트. 레지스트리 누적 : entity 25종 (R1 18 + R2 2 + R3 5) / relation 27종 (R1 18 + R2 3 + R3 6). **ontology/schema.py 의 RelationKind Literal ("part_of", "uses", "produces", "responsible_for") 와 모듈 경계 분리 확인 — 이름 겹치지만 충돌 없음**. graph_writer 화이트리스트는 `RelationKindRegistry.is_registered` 동적 검증으로 자동 통과. 다음 : **D2 인제스트 파이프라인** (`backend/modeling/manual_ingest/`), 3 트리거 (UI+watch+git hook, Q7=E) × 5 파서 (pypdf+pdfplumber+python-docx 신규 Q9=D / python-pptx·OCREngine 재사용 / MD). 사용자 승인 대기. 이전 업데이트 : D1.5 완료 — Round 3 DTO 확장 TDD (104/104 + 246/246). 13 DTO : BusinessProcess (parent 없음, Q1=C) / Role (team. 접두어, Q2=A) / PartOfBinding / RoleBinding / ParentProcessBinding (self-ref 금지) / ParentProcessBindingSet (three-color DFS cycle) / ManualDocument (authoritative=False, Q8=B) / ManualSection / ManualFragment (5 kinds) / DescribedInBinding (Q3=C) / ConflictBinding (gap_mode, Q4=C+A) / MissingBinding (direction, Q6=A). 이전 업데이트 : OD-11-C4 완료 + **Phase D 진입 — OD-11-D1** Round 3 HTML rev.2 Q1~Q9 합의 반영 완료. `toClaude/modeling/round3-manual-gap.html` 771 LOC — 10개 섹션 (Why / Nodes 5종 / Edges 6종 / 4-Layer SVG / 워크스텝 7단 / Ingest 파이프라인 / Gap Detection 3 케이스 + Cypher / 운영 알림 3단 라우팅 / Q1~Q9 결정 블록 / Next Steps). 노드 5종 = BusinessProcess (계층 필드 없음, Q1=C 엣지 분리) / Role (team 단위 고정, Q2=A) / ManualDocument (authoritative:bool=False, Q8=B) / ManualSection / ManualFragment. 엣지 6종 = PART_OF / RESPONSIBLE_FOR / DESCRIBED_IN (Section+Fragment, Q3=C) / CONFLICTS_WITH (gap_mode 속성, Q4=C+A 전환) / MISSING_IN (양방향, Q6=A) / PARENT_PROCESS (Q1=C). 트리거 3종 (UI + watch folder + git hook, Q7=E). Ingest 신규 deps = pypdf + pdfplumber + python-docx (Q9=D) + OCREngine 재사용. 다음: **D1.5 DTO 확장** (BusinessProcess/Role/Manual* 5 모델 + Binding 6종) → **D1.6 parser_protocol** (EntityKinds 5종 + RelationKinds 6종 등록) → **D2 인제스트 파이프라인** → **D3 gap detector (strategy 패턴)** → **D4 UI 디자인** → **Phase E Slab 실증**.)

---

## 1. 다음 세션 첫 작업

### OD-11 방향 전환 (ACTIVE, 2026-04-19~)

**상세 계획 문서**: `toClaude/modeling/OD-11-PLAN.md` (반드시 먼저 읽을 것)

**피벗 요약**:
- OD-1 ~ OD-10은 "매뉴얼 1차 → Ontology YAML" 방향이었으나 팀 실제 목적에 안 맞는 것으로 확인
- **진짜 출발점은 레거시 Java/Spring 코드**. 업무처리기준서는 보조 검증 자료.
- OD-10 정리가 착오. 삭제한 `code_analysis/` `mapping/` `query/` `change/` `git_connector` 등이 새 방향에 부합 → 복원 필요
- 워킹트리 상태라 `git restore <path>` 로 복원 가능 (커밋 전)

**3대 기능** (Section 3 실행, Section 2는 온톨로지 스키마 제공):
1. Impact Analysis : 값/소스 변경 → 영향 범위
2. Reverse Lookup : 비즈니스 용어 → 소스 위치
3. Test Generation : 특정 기능용 데이터 생성 + 실행

**현재 체크포인트 — Phase B 코드 영역 종결 (B1~B8 전체 완료), B9 Slab sample 수령 대기**:

- ✅ OD-11-A1~A3 : OD-11-PLAN.md + 5 docs sync + 사용자 승인
- ✅ OD-11-B1 : Round 1 HTML rev.1 초안
- ✅ OD-11-B2 : Q1~Q8 rev.2 반영 (확장성·데이터 계보·Reflection 승격·hops 자율 조정)
- ✅ OD-11-B2' : Q9~Q11 rev.3 반영
  - **Q9** : 동적 매핑 3 분석기 (MapStruct / BeanUtils / native SQL) 모두 1차 포함
  - **Q10** : JVM Agent는 Section 2 모델링 완성 후 **임시 섹션** (`toClaude/temp-runtime/`, `backend/temp_runtime/`, `frontend/.../temp-runtime/`)에서 실험. 정식 Section 3는 그 이후.
  - **Q11** : 타겟 = 공정계획 **Slab 설계 엔진** (사용자가 단순화해 직접 제공. sample repo 수령 대기)
- ✅ OD-11-B3 : `parser_protocol.py` 플러그인 패턴 — `EntityKindRegistry` / `RelationKindRegistry` + 16/17 기본 등록 + `attributes: dict`. 21/21 통과.
- ✅ OD-11-B4 : `java_parser.py` + `graph_writer.py` 복원 + Spring 분석기 패키지 스캐폴드
  - `java_parser.py` : 7 기본 kind (PACKAGE/CLASS/INTERFACE/ENUM/METHOD/FIELD/CONSTRUCTOR) + 5 relation (CONTAINS/CALLS/EXTENDS/IMPLEMENTS/DEPENDS_ON) 추출. 새 `EntityKinds`/`RelationKinds` 문자열 상수로 전환.
  - `graph_writer.py` : 17 relation kind 지원. `attributes` 직렬화 (primitives/flat list 그대로, nested dict/mixed list → JSON 문자열). `RelationKindRegistry` 화이트리스트 + 정규식 이중 검사 (Cypher 인젝션 차단).
  - `backend/modeling/code_analysis/spring/` : `SpringAnalyzer` Protocol + 6 스텁 (DI/AOP/HTTP/Events/Scheduled/Profile). 실제 구현은 B5.
  - 51/51 통과.
- ✅ OD-11-B5 : Spring 8 난제 개별 PoC (7/8 완료, B5-7 연기)
  - ✅ B5-1 `DIAnalyzer` : 6 stereotype + `@Bean` + `@Autowired`/`@Inject` + 암묵 생성자 주입 + `@Qualifier`/`@Profile`/`@ConditionalOnProperty`. 23/23 통과 (2026-04-19).
  - ✅ B5-2 `AopAnalyzer` : `@Aspect` + 5 advice + `@Pointcut` + `@Order` + pointcut 파서(execution/within/@annotation/@within/named/raw). 23/23 통과, 누적 177/177 (2026-04-19).
  - ✅ B5-3 `HttpAnalyzer` : `@RestController`/`@Controller` + `@RequestMapping` + 5 method shortcut + path 조합·정규화 + method 배열 다중 endpoint + value/path 키워드 + produces/consumes + `@PathVariable`/`@RequestParam`. 26/26 통과, 누적 203/203 (2026-04-19).
  - ✅ B5-4 `EventsAnalyzer` : `@EventListener` / `@TransactionalEventListener` / `publishEvent(new X(...))` → `event_type` 엔티티 + `HANDLES` / `PUBLISHES` 엣지. value-form class-literal · 첫 파라미터 타입 추론 · `<unresolved>` + `publish_expr` fallback. 19/19 통과, Spring+parser+graph 누적 222/222 (2026-04-19).
  - ✅ B5-5 `ScheduledAnalyzer` : `@Scheduled` → `scheduled_task` 엔티티 (entity-only). qn = `<method FQN>#scheduled`. `method_fqn` 항상 기록 + 조건부 트리거 키 (`fixed_rate`/`fixed_delay`/`initial_delay`/`cron`/`zone`). String variant (`fixedRateString` 등) → 동일 키로 통합. 15/15 통과, Spring 5-analyzer 106/106 + 모델링 전체 180/180 (2026-04-19).
  - ✅ B5-6 `ProfileAnalyzer` method-level : `@Profile` / `@ConditionalOnProperty` 를 다른 analyzer 산출물(`spring_bean`[#bean] / `scheduled_task` / `http_endpoint` + `MAPS_URL` / `HANDLES` / `PUBLISHES`) 속성에 merge. `analyze()` 는 `([], [])` 반환 + 신규 `enrich()` 후처리 메서드. `JavaParser` analyzer 루프 2-pass 확장 (duck-typed `hasattr(a, 'enrich')`). 17/17 통과, Spring 6-analyzer 123/123 + 모델링 전체 197/197 (2026-04-19).
  - ⏭ B5-7 (optional, 연기) `JpaAnalyzer` — Spring Data JPA. 우선순위 낮아 B7 런타임 collector / B9 Slab 엔진 E2E 에서 실제 데이터 접근 경로 드러날 때 재검토.
  - ✅ B5-8 `ReflectionAnalyzer` : `Class.forName` / `Proxy.newProxyInstance` / `ctx.getBean("name")` / `clazz.getMethod`·`getDeclaredMethod`·`getField`·`getDeclaredField` 정적 call-site 를 `method.attributes["reflection_calls"] = [{api, arg, line}, ...]` 로 마킹. `Method.invoke`/`Constructor.newInstance` 는 PoC 범위에서 제외 (B7 런타임). post-processor 패턴, JavaParser `enrich` 훅 재사용. 20/20 통과, Spring 7-analyzer 143/143 + 모델링 전체 217/217 (2026-04-19).
- ✅ OD-11-B6 : 동적 매핑 3 분석기 + Cross-file Enricher (4/4 완료)
  - ✅ B6-SPEC : `toClaude/modeling/OD-11-B6-SPEC.md` 10 결정사항 승인 (2026-04-19 "이대로 진행").
  - ✅ B6-1 `MapStructAnalyzer` : `@Mapper`/abstract class 에서 `@Mapping(source,target)` → `PROPAGATES_TO`, `@Mapping(expression)` → `DERIVES_FROM` (source = `<expression>` sentinel). `@Mappings` 컨테이너 flatten, `qualifiedByName` via_methods append, `ignore=true` skip, `default`/`@Named` skip. 파라미터 prefix 자동 replace. 명시 `@Mapping` 없는 메서드는 METHOD.attributes["mapstruct_implicit_fields"] marker 만 남김 (B6-4 에서 확정). Standalone `analyze()` (edges) + `enrich()` (marker) 하이브리드. 16/16 통과, Spring 8-analyzer 159/159 + 모델링 범위 223/224 (lineage 1 선행) (2026-04-19).
  - ✅ B6-2 `BeanUtilsAnalyzer` : Spring `copyProperties(src, dst, ...ignore)` / Apache Commons `copyProperties(dst, src)` (인자 순서 **반대**) / ModelMapper `.map(src, Dst.class | dst_instance)` 3 variant 를 파일 import 로 구분. import 없을 시 `library="unknown"` + `confidence=0.5`. Static import (`import static ...BeanUtils.copyProperties` / `...BeanUtils.*`) 시 bare `copyProperties(...)` 도 감지. Scope 맵 (param + local var + class field + `this` → FQN) per-method/per-constructor. 출력 = METHOD/CONSTRUCTOR `.attributes["beanutils_calls"] = [{library, src_type, dst_type, ignore, confidence, line}, ...]` 마커 (edges 없음 — B6-4 에서 FIELD 교집합 승격). Post-processor 패턴 (`analyze()` no-op, `enrich()` merge). 13/13 통과, Spring 9-analyzer 172/172 + 모델링 범위 283/284 (lineage 1 선행) (2026-04-19).
  - ✅ B6-3 `NativeSqlAnalyzer` : Spring Data `@Query` / `@Modifying` + `@Query` / `EntityManager.createNativeQuery|createQuery` / `JdbcTemplate.{query,queryForObject,queryForList,update,batchUpdate}` 7 경로. `sqlglot.parse(sql, error_level="ignore")` default dialect (스펙 §5.2 `"ansi"` 는 sqlglot 미존재). SQL root 기반 write/read 분리 (`Insert.this` 타겟 + `Insert.expression` (Select) 소스 / `Update`·`Delete` 첫 Table 쓰기 + 이후 서브쿼리 읽기 / `Select` 전부 읽기). 엣지 = `READS_TABLE`/`WRITES_TABLE` (method_fqn → lowercase table) + `{columns(dedupe), confidence, raw_sql, dialect(sql|jpql), multi_statement_warning?}`. Dynamic SQL (first arg != string_literal) → 단일 `<dynamic>` marker, confidence=0.3. `EntityManager` FQN set 에 `javax.persistence.EntityManager` / `jakarta.persistence.EntityManager` / simple `EntityManager` 포함. `pyproject.toml` `sqlglot = "^23.0"` 추가. Standalone `analyze()` + `enrich()` no-op. DB_TABLE emit 없음 (B6-4 dedup). 16/16 통과, Spring 10-analyzer 190/190 + 모델링 범위 262/262 (lineage 1 선행, Wiki) (2026-04-19).
  - ✅ B6-4 `CrossFileEnricher` : JavaParser 외부 repo-level 헬퍼. `enrich_repo(parse_results, class_index, field_index) -> list[ParseResult]`. (1) MapStruct implicit finalize `mapstruct_implicit_fields` → `PROPAGATES_TO{confidence:0.9, implicit:true}`. (2) BeanUtils FIELD 교집합 `beanutils_calls` → `PROPAGATES_TO{confidence:0.7, library, via_methods}` + ambiguous simple name 은 `beanutils_ambiguous_types` marker. (3) NativeSQL column→field : READS_TABLE/WRITES_TABLE `columns` × class_index `@Column`/`@Table`/`@Entity` → DB_COLUMN + READS/WRITES. JPQL entity target → `jpa_table` 로 `dataclasses.replace` in-place rewrite. (4) DB_TABLE dedup : 모든 target 집약해 synthetic `ParseResult(file_path="<db_schema>", language="java")` 에 한 번만 emit. `JpaAnnotationExtractor` (Q2 Option C) 별도 모듈 — `@Entity`/`@Table`/`@Column` → class `.attributes["jpa_entity_name"/"jpa_table"/"jpa_columns"]` setdefault merge. Frozen dataclass 의 `.attributes` dict 는 mutable → in-place marker. Dynamic SQL (`<dynamic>`) 은 DB_TABLE/COL + READS/WRITES 전부 skip. 10/10 신규 + 모델링 범위 `-k "spring or java_parser or code_analysis or modeling or graph or cross_file"` 272/272 + 0 failures (2026-04-19). `backend/modeling/code_analysis/{cross_file_enricher,jpa_annotation_extractor}.py` + `tests/test_cross_file_enricher.py`.
- ✅ OD-11-B7 SPEC : `toClaude/modeling/OD-11-B7-SPEC.md` (B7-0/1/2 subphase 분할, Q1=A spec-first / Q2=B Coexist 3-way / Q3=A Protocol+DTO only / Q4=B 별도 literal resolver 모듈)
  - ✅ B7-0 `ReflectionAnalyzer` `arg_kind` 필드 확장 : marker `reflection_calls[*]` 에 `arg_kind` ∈ {literal,variable,concat,type,other} 추가, `arg` 의미를 소스 텍스트로 전환 (`<dynamic>` sentinel 제거). `_first_arg_value` 시그니처 `str → tuple[str, str]` + `_classify_arg_node` helper 신설. 25/25 통과, 모델링 범위 231/231 (2026-04-19).
  - ✅ B7-1 `reflection_literal_resolver.py` : `build_bean_index(parse_results)` + `resolve_reflection_literals(parse_results, class_index, bean_index)`. `getBean("name")` → bean_index · `Class.forName("FQN")` → class_index. 매치 → `CALLS{source:static_literal, 0.9, api, arg}`, 미스 → `CALLS{source:static_unresolved, 0.4, reason:bean_not_found|class_not_found, target:"<reflection-site>"}`. `getMethod`/`getField`/`Proxy.newProxyInstance` + `arg_kind ∈ {variable, concat, type, other}` 는 B7-1 skip (B7-2 위임). DIAnalyzer 에 `bean_name` 자동 기록 확장 (@Component/@Bean + camelCase fallback). 15/15 통과, 통합 타깃 73/73, 모델링 범위 295/295 (2026-04-19).
  - ✅ B7-2 `runtime_collector.py` : frozen DTO (`ReflectionTrace` / `CallTrace`) + `@runtime_checkable RuntimeCollector` Protocol + `JsonFileCollector` reference + `merge_runtime_traces` 병합기. synthetic `ParseResult(file_path="<runtime>")` in-place append. 엣지 규칙: class-lookup → `CALLS{runtime,0.95}` 단독 / method·field-lookup → CALLS(class) + `REFLECTS_AS`(member) 쌍. 중복 sample_count 합산, 다른 target 분기 (동적 dispatch). `parser_protocol.py` `REFLECTS_AS` relation kind 등록 (code 카테고리, 기본 17→18). 14/14 통과, 통합 타깃 117/117, 모델링 범위 309/309 (2026-04-19). 실 JVM Agent 는 B9 Slab 엔진 수령 후 `toClaude/temp-runtime/`.
- ✅ OD-11-B8 SPEC : `toClaude/modeling/OD-11-B8-SPEC.md` (4-way subphase B8-0/1/2/3, Q1=A OBSERVED 에 None 포함 / Q2=B direction 파라미터 incoming 기본 / Q3=A `<reflection-site>` skip + unresolved_sources / Q4=B entity_kinds 기본 세트 / Q5=설정 외부화 (ImpactConfig) / Q6=A InMemoryGraphView 만 / Q7=A 4-way 분할)
  - ✅ B8-0 : Query DTO + GraphView Protocol + InMemoryGraphView + ImpactConfig. `backend/modeling/query/{query_models,graph_view}.py` 신설. 25/25 통과 (query_models 15 + in_memory_graph_view 10), 모델링 범위 199/199 (2026-04-19).
  - ✅ B8-1 : `QueryEngine.impact` BFS 코어 + 3-mode filter. `query_engine.py` (165 LOC) + `_Frontier` frozen dataclass + `_bfs` + `_diagnostic_reflection_site` + `direction` 공용 + entity_kind post-filter + `<reflection-site>` 이중 처리 (중간 skip / 직접 질의 진단). 14/14 통과 (`tests/test_query_engine_impact.py`), 모델링 범위 213/213 (2026-04-19).
  - ✅ B8-2 : hops 자율 축소 + timeout + frontier 경고. `query_engine.py` +27 LOC (`time.monotonic` + `logger` + hop 경계 훅 3종) + message `" — auto-shrunk: {reason}"` 접미사. `auto_hops=False` 로 축소·타임아웃 비활성화 (frontier 경고는 항상). 7/7 통과 (`tests/test_query_engine_shrink.py`), 모델링 범위 21 파일 329/329 (2026-04-19).
  - ✅ B8-3 : Reverse Lookup 스텁 + direction-aware `<reflection-site>` 진단. `query_engine.py` +38 LOC (`reverse_lookup(term, *, mode, max_hops, auto_hops, edge_kinds, entity_kinds)` 위임 + `_diagnostic_reflection_site` direction 분기). outgoing 직접 질의 = sentinel sink 메시지, incoming = B8-1 callers 덤프 유지. shrink/timeout/frontier 경고/entity_kinds 전부 `impact()` 경로로 자동 상속. 8/8 통과 (`tests/test_query_engine_reverse.py`), 모델링 범위 22 파일 47/47 (scope filter, 2026-04-19).
- ⏭ OD-11-B9 : Slab 엔진 sample repo 수령 → 첫 파싱 E2E (외부 의존)
- 🟡 Phase C Round 2 (비즈니스 개념 + 코드↔개념 브릿지) 진행 중
  - ✅ C1 : Round 2 HTML rev.2 완료 (2026-04-20). 사용자 Q1~Q7 합의. 1차 범위 = BusinessTerm / BusinessRule + REALIZES / VALIDATES + DERIVED_FROM 예약. 컷오프 name_match ≥ 0.85 / embedding ≥ 0.78 / llm ≥ 0.6. primary unique 1/method, partial N/method. OpenAI + chromadb. VALIDATES 단계적 A→B→C (C는 선택). Phase D 이월 : BusinessProcess / Role / PART_OF / RESPONSIBLE_FOR.
  - ✅ C2 `backend/modeling/mapping/mapping_models.py` (2026-04-20) : Pydantic v2 frozen DTO 5종 + Enum 5종 + `@model_validator` primary 유일성 + (term,code) pair 중복 거부 + alias case-insensitive. 28/28 tests, 모델링 회귀 365/365.
  - ✅ C3 `backend/modeling/query/term_resolver.py` (2026-04-20) : 4-stage chain (exact→alias→embedding≥0.78→LLM≥0.6→MISS) + `EmbeddingProvider`/`LLMResolver` Protocol + `InMemoryEmbeddingProvider` (테스트) + `OpenAIChromaProvider` (운영 Q6 A) + ResolutionCutoffs/Result/Candidate/SimHit/LLMProposal DTO + `ResolutionAuditLog` 1회/쿼리 + 원본 query 보존 + normalize(공백+casefold) + LLM 환각 방어. 35/35 tests, 모델링 회귀 400/400.
  - ✅ C4 `backend/modeling/api/reverse_lookup_api.py` (2026-04-20, 296 LOC) : REST `GET /api/modeling/reverse_lookup` + SSE `.../stream` (resolving→resolved→complete 3단). `TermResolver(C3) → audit append → 2-stage gate → binding filter (scope+confirmed) → per-request tiny InMemoryGraphView → QueryEngine.reverse_lookup(edge_kinds={REALIZES})` chain. 옵션 `include_unconfirmed` / `scope_filter ∈ primary|partial|all` / 표준 `mode`/`max_hops`. 신규 Store Protocol 2종 (`ConceptBindingStore`/`AuditLogStore`) + InMemory reference. `parser_protocol.py` Round 2 kind 정식 등록 (business_term/business_rule + realizes/validates/derived_from — C1 합의). `backend/main.py` startup `ONTONG_EMBEDDING=openai` 환경변수 분기 + graceful fallback. 22/22 tests, 모델링 범위 422/422, 앱 로드 147 routes (145+2).
- 🟡 Phase D : Round 3 (기준서 gap + 조직/책임 + BusinessProcess / Role / Manual*) — **D1 + D1.5 + D1.6 + D2 (D2-1+D2-2+D2-3 완결) + D3 (D3-1 MISSING_IN + D3-2-a deterministic + D3-2-b LLM + D3-3 API+UI) 완료**, D4 UI 디자인 스펙 대기
  - ✅ **D1** Round 3 HTML rev.2 (Q1~Q9 합의 반영, 2026-04-20, 771 LOC). 노드 5종 + 엣지 6종 (PART_OF/RESPONSIBLE_FOR/DESCRIBED_IN/CONFLICTS_WITH/MISSING_IN/PARENT_PROCESS) + 4-Layer 아키텍처 + Gap Detection 3 케이스 + Ingest 파이프라인 + 운영 알림.
  - ✅ **D1.5** DTO 확장 (2026-04-20, 104/104 PASS + 회귀 246/246). `backend/modeling/mapping/mapping_models.py` 에 BusinessProcess/Role/PartOfBinding/RoleBinding/ParentProcessBinding/ParentProcessBindingSet (cycle detection) 추가 + 신규 `backend/modeling/manuals/manual_models.py` 에 ManualDocument/Section/Fragment + DescribedInBinding/ConflictBinding/MissingBinding. enum 9종 신규. Pydantic v2 frozen + field/model validator + `_ROLE_PREFIX="team."` 접두어 강제 + 자기 참조 거부 + three-color DFS 사이클 검출.
  - ✅ **D1.6** parser_protocol EntityKinds/RelationKinds 확장 (2026-04-20, 24/24 PASS + 회귀 524/524). `backend/modeling/code_analysis/parser_protocol.py` 에 Entity +5 (`BUSINESS_PROCESS`/`ROLE`/`MANUAL_DOCUMENT`/`MANUAL_SECTION`/`MANUAL_FRAGMENT`) + Relation +6 (`PART_OF`/`RESPONSIBLE_FOR`/`PARENT_PROCESS`/`DESCRIBED_IN`/`CONFLICTS_WITH`/`MISSING_IN`), 모두 category="concept". 편의 상수 `EntityKinds.X` / `RelationKinds.X` 확장. `tests/test_parser_protocol_phase_d.py` 24 신규. ontology/schema.py Literal 과 모듈 경계 분리 확인 (이름 겹치지만 충돌 없음). graph_writer 는 `RelationKindRegistry.is_registered` 동적 검증으로 자동 통과. 레지스트리 누적 : entity 25종 / relation 27종.
  - 🟡 **D2** 인제스트 파이프라인 — **D2-1 + D2-2 완료**, D2-3 대기. 사용자 승인 위해 `D2-1 (파서) / D2-2 (pipeline + UI) / D2-3 (watch + git hook)` 3 서브로 분할.
    - ✅ **D2-1** 5 포맷 파서 + `ManualParser` Protocol + `ManualParseResult` DTO (2026-04-20, 48/48 PASS + 회귀 251/251). `backend/modeling/manual_ingest/` 신규 패키지 : `parser_protocol.py` (Protocol + DTO + FQN/checksum helpers) + `md_parser.py` (heading-stack + para/fence/table) + `pdf_parser.py` (pypdf 페이지=섹션) + `docx_parser.py` (`Heading N` 스타일) + `pptx_parser.py` (슬라이드=섹션) + `image_parser.py` (OCREngine 주입, 실패 warning). `tests/_manual_ingest_fixtures.py` (pypdf low-level + python-docx/python-pptx 헬퍼). 6 테스트 파일 48 tests. `pyproject.toml` deps 추가.
    - ✅ **D2-2** Ingest pipeline + Manual Registry + Upload REST/SSE API (2026-04-20, 36/36 PASS + 모델링 회귀 329/329, 전체 1376 PASS / 21 FAIL baseline). 4 모듈 (`manual_registry.py` Protocol + `InMemoryManualRegistry` + Q8=B authoritative 토글 / `embedding_store.py` Protocol + InMemory + `ChromaManualEmbeddingStore` for `manual_fragments` 컬렉션 / `pipeline.py` IngestMode SKIP+UPDATE+FORCE + IngestOutcome + `UnsupportedFormatError` + `detect_format` + `ManualIngestPipeline.ingest(path, *, repo_id, mode, on_progress)` + `ManualGraphWriter` Protocol + `CodeGraphManualWriter` 어댑터 / `backend/modeling/api/manuals_api.py` init/reset 싱글턴 + multipart upload + JSON list + authoritative toggle + SSE stream). 업로드는 `tempfile.mkdtemp()+원본 파일명` 으로 원본 stem 보존해 dedup 정확성 확보. `backend/main.py` lifespan wiring + `backend/modeling/api/modeling.py` router include.
    - ✅ **D2-3** 3 트리거 wiring 완료 (2026-04-21, 30/30 PASS + 회귀 677/677). watchdog **무의존 폴링** 방식 채택. `ManualFolderWatcher` + `WatchScanResult` (mtime+size 스냅샷 diff → `IngestMode.UPDATE`, 재귀 walk, `seed_existing` 토글, 삭제 추적, 파일 경로 `ValueError`) + `parse_git_webhook_payload` + `ingest_changed_files` (repo_root 기반 resolve, path escape 방어, unsupported → skipped, removed 응답만) + `POST /api/modeling/manuals/git-hook` (`GitHookResponseDTO`, `asyncio.to_thread`, ValueError→400, 미초기화→503) + 프런트 `ManualUpload.tsx` (드롭존 + SKIP/UPDATE/FORCE pill + SSE 라이브 이벤트 + 목록 + authoritative 토글 스위치) + `uploadManualStream` async generator (fetch + ReadableStream + TextDecoder + `\n\n` 버퍼 파서, EventSource POST 불가 우회) + `ModelingSection.tsx` "매뉴얼 업로드" 탭 추가.
  - ✅ **D3** Gap Detector (`backend/modeling/gap_detection/`). 3-subphase 전부 완료 (D3-1 MISSING_IN + D3-2-a deterministic + D3-2-b LLM + D3-3 API+UI).
    - ✅ **D3-1** MISSING_IN 양방향 (2026-04-21, 28/28 PASS + 회귀 705/705). `gap_models.py` + `gap_store.py` + `missing_in_detector.py` + `__init__.py`. `ScanConfig`/`GapCandidate(direction:GapDirection|None)`/`ScanResult` + `InMemoryGapStore` (confirmed 보호) + `MissingInDetector.scan()` code_only(SOFT)+manual_only(HARD) + `SimpleHeuristicExtractor` 4 regex + stable id `sha1(direction|target|counterpart)[:16]`.
    - ✅ **D3-2-a** CONFLICTS_WITH deterministic 2 stage + Strategy skeleton (2026-04-21, 30/30 PASS + 회귀 735/735). `rule_ast_differ.py` (extract_quantities 정규식 + DiffOutcome + canonical comparator + RuleASTDiffer, severity=HIGH, 빈 토큰 skip — NL 은 embedding/LLM 위임) + `embedding_drifter.py` (TextEmbedder Protocol + zero-safe cosine + CosineDrifter cutoff=0.65, severity=MEDIUM) + `gap_engine.py` (LLMComparator Protocol + GapEngine Protocol + `HierarchicalGapEngine` rule_ast→drift→LLM 3 stage + locked_pairs dedup + LLM severity+reasoning merge + `LLMOnlyGapEngine` skeleton + `create_gap_engine(mode)` 팩토리). `GapSeverity` Enum 확장 : HARD/SOFT + LOW/MEDIUM/HIGH/CRITICAL. Stable id prefix per stage. BusinessRule.statement 이 free-text str → rule_ast = **수량 표현만 regex 추출** (NLP 투자 회피). `llm_comparator=None` 도 정상 동작 (D3-2-b 전 사용 가능). API 미추가 (152 routes 유지).
    - ✅ **D3-2-b** LLM Comparator 실 구현 (2026-04-21, 13 tests — 12 PASS + 1 SKIP integration, 회귀 747/747, 전체 1476/21 baseline). `backend/modeling/gap_detection/llm_comparator.py` (~210 LOC) : `LLMComparisonResult(BaseModel)` (`severity: Literal["low","medium","high","critical"]` + `reasoning: str`) + `_SYSTEM_PROMPT` ERP/MES/SCM 충돌 분석가 + `_render_user_message()` + `_default_agent_factory()` pydantic-ai `Agent(get_model(), output_type=…, retries=2, defer_model_check=True)` — `llm_factory.get_model()` 재사용 (모델 스위치 = `settings.litellm_model` 단일 지점) + `PydanticAILLMComparator` Protocol 구현 (`agent_factory` 주입 가능, 테스트 Fake 치환) → **graceful degrade** 어떤 예외도 재발생 안 함 (prior severity 유지 + reasoning 에 `"LLM error: {ExcType}"`) + **belt-and-suspenders** `_coerce_conflict_severity()` 이차 방어 (CONFLICTS_WITH 카테고리 화이트리스트, "hard"/"soft" MISSING_IN leak → MEDIUM 폴백). `backend/main.py` lifespan 에 `ONTONG_LLM_COMPARATOR=openai` startup 분기 (인스턴스 보관, engine 주입은 D3-3). `pyproject.toml` `integration` marker 등록. `tests/test_llm_comparator.py` (output 2 / protocol 1 / success 2 / graceful 3 / prompt 2 / defensive 2 / integration 1). 실 LLM 호출은 `@pytest.mark.integration` + `ONTONG_LLM_INTEGRATION=1` 이중 게이트.
    - ✅ **D3-3** REST + SSE + 승인 큐 UI (2026-04-21, 22/22 PASS — scanner 10 + gaps_api 12, 회귀 127/127 gap 계열, 전체 1498/31 baseline, TS clean). `backend/modeling/gap_detection/gap_scanner.py` 신규 (`GapScanner` 오케스트레이터, `UnifiedScanResult` frozen dataclass + `.all` property, progress callback 4 stage `scanning → stage1_missing_in → stage2_conflicts → complete`, ManualRegistry 에서 fragments auto-pull) + `backend/modeling/api/gaps_api.py` 신규 (4 엔드포인트 : `POST /scan` sync + `POST /scan/stream` SSE (asyncio.to_thread + buffered-flush 로 TestClient race 해결) + `GET ""` direction/severity/include_confirmed 필터 + `POST /{gap_id}/confirm` 404-on-miss) + `embedding_drifter.py` `HashingTextEmbedder` 추가 (SHA256 3-gram 64-dim L2 normalized 결정적 fallback, OpenAI 의존성 없이 `CosineDrifter` 초기화) + `backend/main.py` lifespan (`InMemoryGapStore` → `MissingInDetector` → `create_gap_engine(HIERARCHICAL, rule_differ, drifter, llm_comparator, gap_store)` → `GapScanner(fragment_source=_manual_registry)` → `gaps_api.init(...)` + 라우터 include, 156 routes +4) + `frontend/src/lib/api/modeling.ts` Gap 섹션 추가 (`scanGaps` / `scanGapsStream` async generator + AbortSignal / `listGaps` / `confirmGap`) + `frontend/src/components/sections/modeling/GapQueue.tsx` 신규 (필터 바 + 스캔 버튼 SSE stream + 후보 테이블 + 확정 액션) + `ModelingSection.tsx` MAIN_NAV 에 "갭 큐" (`gap-queue`, `ListChecks` 아이콘) 추가. **주요 결정** : Q1=Partial Hybrid (fragments 만 auto-pull, rules/described_in body 필수 — 전용 store 아직 없음, Phase E 에서 `RuleRegistry` 설계) / Q2=Unified scan (단일 엔드포인트가 MISSING_IN + CONFLICTS_WITH) / Q3=SSE primary + `/scan` sync fallback (buffered-flush PoC 수용 가능 trade-off).
  - ⏭ **D4** 사람 검증 UI 디자인 스펙 (CONFLICTS_WITH 승인 큐 + Role team 관리 + Manual 업로드 + authoritative 토글).
- ⏭ C5 (선택) : 실 LLM resolver (`backend/modeling/query/llm_resolver.py` pydantic-ai Agent)
- ⏭ 임시 섹션 신설 : Section 2 빌더 완성 후

**다음 세션이 첫 할 일** (OD-11-E1 진입 — Slab 샘플 + 파서 검증 + A2 field 리터럴 + A3 Javadoc 룰 + CPA config_property + RR auto-pull 완료, 5종 gap 실증까지 가는 길):

> 사용자 정책 (2026-04-25 합의) : 실제 Slab 데모 코드 도착 전까지는 **데모 코드 무관 범용 인프라부터** 끝낸다. B (매뉴얼 작성) 와 D4 (UI 디자인 스펙) 는 데모 도착 후로 보류.
>
> 우선 권장: **A1 → JpaAnalyzer (선택) → Slab 데모 코드 대기** 순. D3-3 미수거 3개 모두 완료 — RuleRegistry / SSE 진짜 streaming / evidence panel + 재평가 종결. 데모 코드 도착 전 가능한 인프라 작업이 거의 마무리.

0a. **(완료, 2026-04-25) A2 — `field.attributes` 리터럴 값 검증 + JavaParser 확장** — `_extract_field` 에 `field_type` / `initializer` / `initializer_kind` 캡처 추가. 20/20 PASS, Slab 실증 240/1.02/50 노출 확인. **OD-11-E1-c [x]**.

0b. **(완료, 2026-04-25) A3 — Javadoc → BusinessRule 추출기** — `backend/modeling/code_analysis/javadoc_rule_extractor.py` 신규. tree-sitter `block_comment` walk → 한국어 룰 휴리스틱 → `BusinessRule` + `VALIDATES` 엣지. 23/23 PASS. Slab 15 BusinessRule. **OD-11-E1-d [x]**.

0c. **(완료, 2026-04-25) CPA — `ConfigPropertiesAnalyzer` 11번째 Spring analyzer** — 3 어노테이션 형식 + 비-static field + canonical camelCase + kebab alias + default_value 캡처. 27/27 PASS. Slab 90→95 entities. **OD-11-E1-f [x]**.

0d. **(완료, 2026-04-25) RR — `RuleRegistry` 신규 + `GapScanner.rule_source` auto-pull** — `backend/modeling/gap_detection/rule_registry.py` 신규. Protocol + InMemory + `seed_rules_from_repo()` convenience. `GapScanner` 에 `rule_source` 추가, `gaps_api.ScanRequest.rules` Optional 격상, `main.py` lifespan wiring. 16/16 PASS. Slab 11 java files → **16 BusinessRule auto-seed**. body 미지정 → registry auto-pull 동작 확인. **OD-11-E1-g [x]**. **D3-3 미수거 1/3 완결**.

0e. **(완료, 2026-04-25) SSE — `gaps_api.scan_stream` 진짜 stage-by-stage streaming** — `gaps_api.py` `scan_stream_endpoint` 재구현. `asyncio.Queue` + `loop.call_soon_threadsafe(queue.put_nowait, ...)` 패턴으로 worker thread → main loop 안전 전달. STAGE_COMPLETE 만 콜백에서 suppress (그 시점에 result 없음) → scan 정상 반환 후 (STAGE_COMPLETE, payload) 별도 push. 예외 시 ("error", {detail}) push + sentinel None 으로 generator 정상 종료. **15/15 PASS** (기존 12 + 신규 3 — pattern unit test gate / complete payload / error propagation). TestClient ASGITransport 가 SSE chunks 버퍼링해서 E2E 실시간 검증 못 함 → 패턴 unit test 로 우회. **OD-11-E1-h [x]**. **D3-3 미수거 2/3 완결**.

0f. **(완료, 2026-04-25) EV — `GapCandidate.evidence` + `POST /gaps/{id}/reevaluate` + GapQueue evidence panel + 재평가 버튼** — 백엔드 evidence 4 stage 채우기 + 신규 엔드포인트 (404→422→503 우선순위) + `gaps_api.init` 에 llm_comparator 주입. 프런트 `modeling.ts` 백엔드와 1:1 정정 (가짜 필드 제거) + `reevaluateGap()`. `GapQueue.tsx` minimal `<details>` JSON pretty-print + Sparkles 재평가 버튼. **20/20 PASS** (기존 15 + 신규 5). main.py 157 routes (+1). **OD-11-E1-i [x]**. **D3-3 미수거 3/3 완결 — D3-3 인프라 100% 종결**.

0g. **(완료, 2026-04-25) A1 — `scripts/dump_entities_snapshot.py` JSON 스냅샷** — argparse 12-analyzer dump → `{metadata, files: {<rel-path>: {entities, relations}}}`. 8/8 신규 tests. Slab 실행 `11 files / 95 entities / 177 relations / 0 errors` (E1-f 와 동일). `.gitignore` 에 `**/.analyzed/` 추가. 전체 1600 PASS. **OD-11-E1-j [x]**.

0h. **(완료, 2026-04-25) JPA — `JpaAnalyzer` 12번째 Spring analyzer** — 사용자 의견 "데모 코드 어차피 JPA 쓸 텐데 미리 준비". `backend/modeling/code_analysis/spring/jpa_analyzer.py` 신규 (~210 LOC). @Repository 또는 Spring Data 4 base interface extends 탐지 + 메서드 이름 컨벤션 7 종 → READS/WRITES 엣지 + `jpa_operation`/`jpa_property_path` attribute. 27/27 신규 tests. Slab 95/177 그대로 (JPA 없음). 전체 1627 PASS. **OD-11-B5-7 [x]** (옵션 상태에서 정식 종결).

1. **Slab 데모 코드 도착 대기** ← **권장 1순위 (외부 의존)**
   - 도착 후 즉시 가능 작업 :
     - 코드 분석 파이프라인에 등록 → 12-analyzer 결과 entities/relations + JPA 그래프 (있다면) 확인.
     - **B 매뉴얼 작성** (의도적 gap 5종 트리거) → ManualRegistry 업로드 → `POST /api/modeling/gaps/scan {"repo_id":"..."}` 5건 후보 출력 검증. **OD-11-E1-e**.
     - **D4 UI 디자인 스펙** : 실제 gap 후보 출력을 입력으로 evidence panel 디자인 구체화.

2. **DescribedInStore** — 자동 발견 메커니즘 미정 (수동 등록 / embedding 기반 nearest fragment / LLM 중). 데모 코드 + 매뉴얼 함께 와야 결정 가능 → 보류.

3. **(선택) CrossFileEnricher v2** — JpaAnalyzer 의 `target_kind="jpa_entity_simple_name"` 엣지를 `@Table(name=...)` 으로 rewrite. JpaAnnotationExtractor (B6-4) 와 결합. 데모 코드 보고 결정.

---

**🔴 데모 코드 도착 후 (보류)**

- **B — Slab 매뉴얼 작성 + gap scan 실증** (`OD-11-E1-e`)
   - 위치 : `wiki/공정계획/slab-설계-기준서.md` — 의도적 gap 5종 트리거.
   - 매뉴얼 명시 룰 (가짜 데모 기준) :
     - "Slab 두께는 **250mm 이상** 까지 허용" (vs 코드 240) → CONFLICTS_WITH
     - "압연 안전계수는 **1.05** 적용" (vs 코드 1.02) → CONFLICTS_WITH
     - "그리드 간격 **25mm 이하** 권장" (vs 코드 50) → CONFLICTS_WITH
     - "보정 후 크레인 하중 **재검증 필수**" (vs 코드 누락) → MISSING_IN code (manual_only)
     - (`adjustWeightBias()` 메서드 자체는 매뉴얼에 등장시키지 않음) → MISSING_IN manual (code_only)
   - **보류 사유** : 매뉴얼의 기준값이 실제 데모 코드의 매직넘버와 의도적으로 어긋나야 의미 있음. 실 데모 코드의 숫자 모르면 다시 써야 함.
   - 검증 :
     ```bash
     curl -X POST -F "file=@wiki/공정계획/slab-설계-기준서.md" "http://localhost:8001/api/modeling/manuals/upload?mode=update"
     curl -X POST -H "Content-Type: application/json" -d '{"repo_id":"slab-design-engine"}' http://localhost:8001/api/modeling/gaps/scan
     ```
   - 기대 : `code_only` 1건 + `manual_only` 1건 + `conflicts` 3건 = 후보 5건.

- **D4 UI 디자인 스펙** — Phase E 의 5건 후보가 실제로 잡힌 뒤 LLM reasoning 표시 + evidence panel + Role/Manual 통합 레이아웃 설계 (실제 gap 출력을 입력으로 사용).

6. **D4 UI 디자인 스펙** — Phase E 의 5건 후보가 실제로 잡힌 뒤 LLM reasoning 표시 + evidence panel + Role/Manual 통합 레이아웃 설계. E1 결과를 입력으로 사용하면 디자인 의사결정이 구체화됨.

7. **D3-3 미수거 TODO (Phase E 내 수거)** — `rules` / `described_in` 전용 store 설계 (full auto-pull) + SSE 진짜 stage-by-stage streaming 재설계 + GapQueue 에 "LLM 재평가 트리거" + evidence panel (`GapCandidate.evidence` JSON 접기).

**서버 상태 (이어받기 직전 시점)**
- Backend : `nohup .venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload > /tmp/ontong_backend.log 2>&1 &` — PID 94891 alive. `--reload` 켜져 있어 코드 변경 시 자동 재기동.
- Frontend : `next dev --turbopack` PID 72184 alive on :3000. 사이드바는 "갭 큐" 단일 (UX-1 적용).
- ManualRegistry : in-memory, 재기동 시 초기화. 매뉴얼 업로드는 매 세션 새로 해야 함.
3. **D3-2-b 데모 체크리스트** (D3-3 착수 전에 사용자 데모 가능) :
   - `pytest tests/test_llm_comparator.py -v` → 12 passed + 1 skipped (integration) in 0.05s.
   - Python REPL (Fake agent) :
     ```python
     from unittest.mock import MagicMock
     from backend.modeling.gap_detection import (
         LLMComparisonResult, PydanticAILLMComparator, HierarchicalGapEngine,
         RuleASTDiffer, CosineDrifter,
     )
     class _BumpAgent:
         def run_sync(self, msg):
             r = MagicMock()
             r.output = LLMComparisonResult(severity="critical",
                 reasoning="financial impact")
             return r
     comp = PydanticAILLMComparator(agent_factory=lambda: _BumpAgent())
     # HierarchicalGapEngine stage 1 hit → LLM override severity
     ```
   - 실 LLM smoke (opt-in) : `ONTONG_LLM_INTEGRATION=1 OPENAI_API_KEY=sk-... .venv/bin/python -m pytest tests/test_llm_comparator.py -m integration -v`.
   - Startup 분기 확인 : `ONTONG_LLM_COMPARATOR=openai` 로 uvicorn 기동 시 로그에 `"PydanticAILLMComparator wired (ONTONG_LLM_COMPARATOR=openai)"` 출력.
   - 상세 시나리오는 `toClaude/modeling/demo_guide.md` §D-OD-11-D3-2-b 참조.
2. **D3-1 데모 체크리스트** (D3-2 착수 전에 사용자 데모 가능) :
   - `pytest tests/test_gap_store.py tests/test_missing_in_detector.py` → 28/28 PASS.
   - Python REPL :
     ```python
     from backend.modeling.gap_detection import MissingInDetector, InMemoryGapStore, ScanConfig
     from backend.modeling.manuals.manual_models import GapMode
     store = InMemoryGapStore()
     detector = MissingInDetector(gap_store=store)
     result = detector.scan(
         business_terms=[...], business_rules=[], fragments=[...],
         described_in=[], config=ScanConfig(repo_id="demo", gap_mode=GapMode.HIERARCHICAL),
     )
     print(f"code_only={len(result.code_only)} manual_only={len(result.manual_only)}")
     store.list_pending()  # 승인 큐
     ```
   - 상세 시나리오는 `toClaude/modeling/demo_guide.md` §D-OD-11-D3-1 참조.
3. **D2-3 데모 체크리스트** (D3 착수 전에 사용자 데모 가능) :
   - `uvicorn backend.main:app --port 8001` 기동.
   - **Watch folder** (Python REPL):
     ```python
     from backend.main import app
     from backend.modeling.api.manuals_api import _pipeline
     from backend.modeling.manual_ingest.watch_folder import ManualFolderWatcher
     w = ManualFolderWatcher(pipeline=_pipeline, folder="./wiki", repo_id="wiki")
     result = w.scan_once()
     print(f"ingested={len(result.ingested)} removed={len(result.removed)} errors={result.errors}")
     ```
   - **Git hook** :
     ```bash
     curl -X POST -H "Content-Type: application/json" \
       -d '{"repo_root":"/path/to/repo","added":["docs/x.md"],"modified":[],"removed":[]}' \
       http://localhost:8001/api/modeling/manuals/git-hook
     # {"ingested":[{"outcome":"ingested","document":{...},...}],"skipped":[],"removed":[],"errors":[]}
     ```
   - **프런트 UI** : `http://localhost:3000` → Section 2 → "매뉴얼 업로드" 탭 → 파일 드롭 → SSE 이벤트 리스트 확인 → 목록에서 authoritative 토글 테스트.
4. **OD-11-D4 UI** (D3 이후) — CONFLICTS_WITH 승인 큐 + Role team 관리 + Manual 업로드 UI 확장 (D2-3 업로드 컴포넌트 기반으로 섹션 편집/승인 추가).
5. **대안 C5 / B9** : 병행 처리 가능. C5 는 실 LLM resolver, B9 는 Slab sample 수령 후 E2E.

**C4 데모 준비 메모** (사용자가 실제 REST/SSE 를 시연하려면):
- `backend/main.py` startup 은 `terms=[]` / `InMemoryConceptBindingStore([])` 로 초기화 → 실 쿼리는 전부 MISS. 시연 전 seed 필요.
- 최소 seed 코드 예시 (lifespan 직후 삽입 또는 `/modeling/seed-demo` 관리 endpoint 추가):
  ```python
  from backend.modeling.mapping import BusinessTerm, BusinessTermSource, ConceptBinding, BindingScope, BindingSource
  # seed 1 BusinessTerm + 1 ConceptBinding
  term = BusinessTerm(qualified_name="inventory.safety_stock", canonical_label="안전재고",
                      aliases=["Safety Stock","SS"], domain="inventory", description="...",
                      source=BusinessTermSource.MANUAL, confirmed=True, created_at=datetime.now(timezone.utc))
  binding = ConceptBinding(term_fqn="inventory.safety_stock", code_fqn="com.example.SafetyStockService.calc",
                           scope=BindingScope.PRIMARY, confidence=1.0, source=BindingSource.MANUAL, confirmed=True,
                           confirmed_by="seed", created_at=datetime.now(timezone.utc))
  # reverse_lookup_api._resolver = TermResolver(terms=[term], ...)  (또는 init 재호출)
  # reverse_lookup_api._binding_store.add(binding)
  ```
- 위 방식은 **임시 데모용**. 정식 seed CLI + Neo4j 저장은 Phase D.

**참조 HTML**: `toClaude/modeling/round1-code-schema.html` rev.3. Round 1 스키마의 최종 확정본.

**각 라운드 패턴**: HTML 초안 → 사용자 Q/A → HTML 갱신 → 합의 확인 → 코드 복원+확장 → 다음 라운드.

**스택 고정**: Java / Spring. tree-sitter AST + Spring 전용 분석기 + 선택적 런타임 계측.

**참고 자원**:
- 복원 대상 코드 현 위치 : 워킹트리 삭제 상태. `git restore backend/modeling/code_analysis/` 등으로 복원 가능.
- 기존 `ontology/` `neo4j_client` `ontology_api` 는 그대로 유지 (Formula/Rule/Validator는 비즈니스 룰 표현에 재활용).
- 기준서 PDF/PPT/이미지 인제스트에 Section 1 `image/ocr_engine.py` + `files.py` python-pptx 재활용 가능.

### (Deprecated) 이전 계획 스냅샷

OD-7-B / OD-9 / Section 3 3 agents는 OD-11 피벗으로 **방향 자체가 바뀜**. 재설계 대상. OD-11-PLAN.md §9 복원/Scratch 매트릭스 참조.

### Week 2.5 — OD-10 Legacy Cleanup (2026-04-18)

사용자 피드백("예전 기능이 다 남아 있으니 힘들어") 기반 일괄 제거. 프론트+백엔드 전체 legacy 스코프에서 삭제.

**삭제된 프론트 컴포넌트 (9개)**: `AnalysisConsole`, `SimulationPanel`, `MappingWorkbench`, `MappingCanvas`, `MappingSplitView`, `CodeGraphViewer`, `SourceViewer`, `ApprovalList`, `ImpactQueryPanel`.

**삭제된 백엔드 API (7개)**: `code_api.py`, `source_api.py`, `mapping_api.py`, `approval_api.py`, `engine_api.py`, `query_api.py`, `seed_api.py`.

**삭제된 백엔드 모듈 (8 dirs + 1 file)**: `backend/modeling/{code_analysis,mapping,approval,change,simulation,query,data,agent}/` + `infrastructure/git_connector.py`.

**삭제된 테스트 (15개)**: `test_code_graph`, `test_change_detector`, `test_git_connector`, `test_java_parser`, `test_mapping_service`, `test_query_engine`, `test_modeling_api`, `test_modeling_e2e`, `test_sim_engine`, `test_sim_models`, `test_sim_registry`, `test_approval_service`, `test_engine_api`, `test_source_api`, `test_term_resolver`.

**Section 2 현재 구조**:
```
backend/modeling/
├── api/{__init__,modeling,ontology_api}.py          # 2 API 파일
├── infrastructure/{__init__,neo4j_client}.py        # Neo4j만 유지
└── ontology/                                         # 빌더 + 스키마 + 저장소
    ├── schema.py     # Pydantic Primary Layer
    ├── validator.py  # Sub-DSL AST validator
    ├── loader.py     # YAML load/dump
    ├── ontology_store.py  # :OntNode CRUD
    └── builder_service.py # LLM draft + validate
```

**검증 결과**:
- pytest ontology 84개 pass
- pytest 791 tests collect (import 에러 0)
- `tsc --noEmit` 0 error
- `python -c "from backend.main import app"` OK (145 routes)

### Week 2 — OD-7/8 Ontology Builder 완료 (2026-04-18)

**브랜치**: `main` — 119 modeling tests pass (schema 12 + validator 29 + loader 6 + store 8 + builder_service 17 + modeling_e2e 7 + 기타). TS 0 error.

변경 요약:
- `ontologies/manuals/` 신규 — `heating-process-sop.md` + `crack-quality-standard.md` + README (wiki 복사).
- `backend/modeling/ontology/builder_service.py` — pydantic_ai Agent (llm_factory get_model 재사용) + `validate_yaml_text` (parse/schema/graph 3단).
- `backend/modeling/api/ontology_api.py` +4 endpoints — `/draft`, `/validate`, `/save`, `/manuals`, `/manuals/{name}` (경로 순회 방지 + `.yaml` 확장자 강제).
- `frontend/src/components/sections/modeling/ManualOntologyBuilder.tsx` 신규 — 좌/우 분할 에디터, 샘플 드롭다운, LLM Draft 버튼, 500ms debounce validation, 저장.
- `frontend/src/lib/api/modeling.ts` — `draftOntology`, `validateOntologyYaml`, `saveOntologyYaml`, `listManuals`, `readManual`.
- `ModelingSection.tsx` MAIN_NAV 최상단에 "매뉴얼 빌더" 탭 추가 (BookOpen 아이콘).
- `tests/test_ontology_builder_service.py` 17건 (valid/invalid YAML, code-fence, LLM 예외).

**검증 명령**:
```bash
./venv/bin/pytest tests/test_ontology_builder_service.py tests/test_ontology_*.py tests/test_modeling_e2e.py
cd frontend && npx tsc --noEmit
```

**UI 데모**: Modeling 섹션 → "매뉴얼 빌더" 탭 → 드롭다운에서 `heating-process-sop.md` 선택 → LLM Draft → YAML 확인 → `heating_sop_v1.yaml` 파일명 입력 → 저장. 상세는 `toClaude/modeling/demo_guide.md` D-OD-05~08.

### Week 1.5 — OD-6 Legacy Migration 완료 (2026-04-18)

**브랜치**: `main` — 110 modeling tests pass.

변경 요약 (Option A 완전 마이그 + Option X 루트 필드 + Option Q 새 label 선택):
- `backend/modeling/ontology/schema.py` — 루트에 `entities`/`roles`/`relations` 추가, `Process.parent_id` 계층화, `RelationKind` Literal.
- `backend/modeling/ontology/validator.py` — 네임스페이스 disjoint, parent cycle DFS, relation 존재성 검증.
- `backend/modeling/ontology/ontology_store.py` — Neo4j `:DomainNode` → `:OntNode{kind}` 전면 재작성. `persist(ontology)` 메서드가 YAML 기반 처음 호출.
- `ontologies/scor_isa95_v1.yaml` — 26 processes (SCOR L1×5 + L2×17 + ISA-95×4) + 7 entities + 5 roles + 16 relations.
- Downstream Cypher 교체: `mapping_service.sync_to_neo4j`, `sim_engine._trace_affected_processes`, `query_engine.analyze`, `source_api._get_entities_for_file`.
- `backend/modeling/api/ontology_api.py` — `DomainNode`/`DomainNodeKind` 의존 제거, `NodeKind = Literal["process","entity","role"]`.
- 삭제: `domain_models.py`, `scor_template.py`, `test_scor_template.py`. e2e 테스트는 YAML 로더 기반으로 재작성.
- 프론트엔드 TypeScript `DomainNode` 인터페이스는 응답 shape 호환 유지 → 변경 없음.

**검증 명령**: `./venv/bin/pytest tests/test_ontology_*.py tests/test_modeling_e2e.py tests/test_mapping_service.py tests/test_query_engine.py tests/test_sim_engine.py tests/test_source_api.py`

### Week 1 — Ontology DSL Lock 완료 (2026-04-18)

**브랜치**: `main` — 39 tests pass (schema 6 + validator 28 + loader 5).

신규 모듈:
- `backend/modeling/ontology/schema.py` — Pydantic DSL (Ontology, Process, Formula, Rule, IOPort, Term, CodeBinding). `extra="forbid"` 강제.
- `backend/modeling/ontology/validator.py` — 서브-DSL AST 파서 (whitelist: `+ - * / ** // %`, 함수 `sqrt/abs/min/max/norminv/round`, 비교 6종, `AND/OR/NOT`) + graph validator (cycle/duplicate/refers_to/code_bindings).
- `backend/modeling/ontology/loader.py` — `load_ontology()` / `dump_ontology()` + YAML `mode="json"` Enum 직렬화.
- `ontologies/safety_stock_v1.yaml` — SafetyStockCalculation + ReorderPointCalculation 샘플.

**검증 명령**: `source venv/bin/activate && pytest tests/test_ontology_*.py -v`

**설계 결정 요약**:
1. Python `ast` 모듈 재사용 (whitelist 방식) — 새 파서 안 만듦
2. Rule action_type은 warning/assign/constraint 3종만 — 자유 문자열 금지

### Week 1 — Ontology DSL Lock 완료 (2026-04-18)

**브랜치**: `main` — 39 tests pass (schema 6 + validator 28 + loader 5).

신규 모듈:
- `backend/modeling/ontology/schema.py` — Pydantic DSL (Ontology, Process, Formula, Rule, IOPort, Term, CodeBinding). `extra="forbid"` 강제.
- `backend/modeling/ontology/validator.py` — 서브-DSL AST 파서 (whitelist: `+ - * / ** // %`, 함수 `sqrt/abs/min/max/norminv/round`, 비교 6종, `AND/OR/NOT`) + graph validator (cycle/duplicate/refers_to/code_bindings).
- `backend/modeling/ontology/loader.py` — `load_ontology()` / `dump_ontology()` + YAML `mode="json"` Enum 직렬화.
- `ontologies/safety_stock_v1.yaml` — SafetyStockCalculation + ReorderPointCalculation 샘플.

**검증 명령**: `source venv/bin/activate && pytest tests/test_ontology_*.py -v`

**설계 결정 요약**:
1. Python `ast` 모듈 재사용 (whitelist 방식) — 새 파서 안 만듦
2. Rule action_type은 warning/assign/constraint 3종만 — 자유 문자열 금지
3. `Term.refers_to`는 점 경로 (`Process.inputs.port`) — 파서블하게
4. `code_bindings`는 Ontology 루트 dict — Secondary Layer 분리하되 같은 파일
5. YAML dump `mode="json"` — Pydantic Enum 직렬화 이슈 해결

**상세**: `toClaude/modeling/log/step_ontology_dsl_phase1_summary.md`

---

### (이전) Image Management 브라우저 데모 테스트 (보류)

사용자가 데모 테스트 시나리오를 요청할 예정. `toClaude/modeling/demo_guide.md`의 "Image Management" 섹션 참고.
서버 기동 후 브라우저에서 다음을 검증:
1. 이미지 클릭 → 뷰어 모달 (풀스크린 + 정보 패널)
2. 어노테이션 편집 (사각형/타원/화살표/텍스트) → 새 이미지로 저장
3. 이미지 우클릭 → "이미지 복사" → 클립보드 동작
4. 설정 → "이미지 관리" → 갤러리 페이지 (페이지네이션, 필터, 검색, 일괄삭제)
5. 해시 dedup: 같은 이미지 두 번 업로드 → `deduplicated: true`

### Image Management System 구현 완료 (2026-04-17)

**브랜치**: `main` — 11 tasks, 28+32 tests (registry + analysis), TS clean.

위키 이미지 관리 시스템 (3 subsystem):
- **SHA-256 해시 중복 제거**: 업로드 시 콘텐츠 해시로 중복 방지, 12자 prefix 파일명
- **ImageRegistry**: 인메모리 hash→filename 인덱스, ref counting, 시작 시 assets/ 스캔
- **어노테이션 편집기**: fabric.js 캔버스 (사각형/타원/화살표/텍스트), OCR 상속
- **관리자 갤러리**: 페이지네이션, 필터(전체/사용중/미사용/파생본), 검색, 일괄삭제
- **이미지 복사**: Ctrl+C + 우클릭 컨텍스트 메뉴 → 클립보드 복사
- **이벤트 기반 ref tracking**: 문서 저장 시 diff, 삭제 시 정리

**백엔드 신규**: `backend/application/image/image_registry.py`
**백엔드 변경**: `files.py` (dedup+admin API), `main.py` (registry init), `wiki_service.py` (ref tracking), `models.py` (source field)
**프론트엔드 신규**: `ImageViewerModal.tsx`, `ImageManagementPage.tsx`
**프론트엔드 변경**: `pasteHandler.ts` (ImageCopyExtension), `MarkdownEditor.tsx` (click-to-view), `workspace.ts`/`useWorkspaceStore.ts`/`FileRouter.tsx`/`TreeNav.tsx` (routing)
**설계 문서**: `docs/superpowers/specs/2026-04-17-image-management-design.md`
**구현 플랜**: `docs/superpowers/plans/2026-04-17-image-management.md`

**다음 후보**: 브라우저 UI 검증 (이미지 클릭→뷰어, 어노테이션, 갤러리 페이지)

### Image Search 구현 완료 (2026-04-17)

**브랜치**: `main` — 11 commits, 30 tests, 코드 리뷰 + 4건 수정 완료.

위키 이미지 검색 가능화 파이프라인:
- **OCR Engine**: EasyOCR (한국어+영어, lazy init, asyncio.to_thread)
- **Vision Provider**: 프로토콜 기반 (noop/ollama/openai), 기본값 none (OCR only)
- **Sidecar .meta.json**: 이미지별 분석 결과 캐시, mtime 비교로 재처리 판단
- **Indexer Integration**: `enrich_chunk_with_images()` → `![](assets/...)` → `[이미지: 설명]` 치환
- **Background Processing**: 문서 저장 시 asyncio.create_task로 비동기 분석 + 재인덱싱
- **Backfill CLI**: `python -m backend.cli.backfill_images` (--dry-run/--ocr-only/--vision-only/--reprocess/--workers N)
- **병렬 처리**: asyncio.Semaphore + gather (max_concurrent)

**신규 파일**: `backend/application/image/` (models, ocr_engine, vision_provider, analyzer, queue), `backend/cli/backfill_images.py`, `tests/test_image_analysis.py`
**변경 파일**: `config.py` (8 settings), `wiki_indexer.py` (enrichment), `wiki_service.py` (bg processing), `main.py` (pipeline init)
**설계 문서**: `docs/superpowers/specs/2026-04-16-image-search-design.md`
**구현 플랜**: `docs/superpowers/plans/2026-04-16-image-search-plan.md`

**다음 후보**: 실제 이미지로 backfill 테스트, Ollama Vision 연동 테스트, 브라우저 UI 검증

### Phase 2a: Source Viewer + Mapping Workbench 완료 (2026-04-16, design review 수정 2026-04-17)

**브랜치**: `main` — 14 source API tests, TS clean, design review 완료.

코드-도메인 매핑 워크벤치 구현:
- **Source API**: 파일 트리 + 파일 내용 + 엔티티 위치 조회 (path traversal/symlink 방어)
- **SourceViewer**: 파일 트리 + Monaco read-only 에디터 + 엔티티 gutter marker
- **MappingCanvas**: React Flow 도메인 온톨로지 그래프 + 엔티티 패널 + 드래그-드롭 매핑 + fitView 자동 적용
- **MappingWorkbench**: 55/45 분할 패널 + 캔버스↔뷰어 양방향 연동
- **ModelingSection**: "매핑 워크벤치" 사이드바 탭 추가
- **Seed API 수정**: 소스 파일 자동 복사 (데모 시 수동 복사 불필요)

**설계 문서**: `docs/superpowers/specs/2026-04-16-source-viewer-mapping-workbench-design.md`
**구현 플랜**: `docs/superpowers/plans/2026-04-16-source-viewer-mapping-workbench.md`
**데모 가이드**: `toClaude/modeling/demo_guide_modeling.md` (Part A: Engine, Part B: Workbench)

**다음 후보**: Phase 1b (실제 Neo4j BFS 의존성 그래프), Docker Sandbox (독립 기능)

### Section 2 Modeling Engine Phase 1a 완료 (2026-04-16)

**브랜치**: `main` — 11 commits, 28 tests, TS clean, UI + API 검증 완료.

Engine-First Architecture로 Section 2 리디자인:
- **분석 콘솔**: 한국어 자연어 입력 → 코드 엔티티 resolve → 영향 프로세스 분석
- **시뮬레이션 패널**: 파라미터 슬라이더 → before/after 비교 (9개 SCM 데모 엔티티)
- **Term Resolution Chain**: Korean alias(30개) → fuzzy match(0.55) → LLM fallback
- **사이드바 구조 변경**: "분석 콘솔" 기본 탭, "설정" 구분선으로 기존 탭 분리

**백엔드 신규 파일:**
- `backend/modeling/simulation/sim_models.py` — ParametricSimResult 외 4 모델
- `backend/modeling/query/term_resolver.py` — Korean alias + fuzzy + LLM
- `backend/modeling/simulation/sim_registry.py` — 9 엔티티 × calc functions
- `backend/modeling/simulation/sim_engine.py` — 시뮬레이션 + BFS 영향 추적
- `backend/modeling/api/engine_api.py` — /engine/query, /simulate, /params, /status

**프론트엔드 신규/변경:**
- `frontend/src/components/sections/modeling/AnalysisConsole.tsx` (NEW)
- `frontend/src/components/sections/modeling/SimulationPanel.tsx` (NEW)
- `frontend/src/components/sections/ModelingSection.tsx` (restructured)
- `frontend/src/lib/api/modeling.ts` (extended)

**설계 문서**: `~/.gstack/projects/Jeensh-onTong/donghae-main-design-20260415-213837.md`
**구현 플랜**: `docs/superpowers/plans/2026-04-15-modeling-engine-phase1a.md`

**다음 후보**: Phase 1b (실제 Neo4j BFS 의존성 그래프 기반 affected_processes), Phase 2 (코드 편집 샌드박스)

### ACL Domain Scoping 완료 (2026-04-14)

**브랜치**: `feat/acl-domain-scoping` — 16 commits, 100 tests, TS clean, E2E 검증 완료.

기업용 ACL 시스템으로 전환 완료:
- **ACL Store v2**: default-deny, owner/manage, 폴더 상속, 개인 공간(@username/), thread-safe
- **Multi-user Auth**: X-User-Id 헤더 기반, users.json, 그룹 해석
- **ChromaDB Access Scope**: access_read/access_write 메타데이터 → 검색/RAG/충돌감지 사전 필터링
- **Group CRUD + ACL API**: 그룹 관리, ACL 설정, manage 권한 체크
- **Frontend**: TreeNav 섹션 구조(내 문서/위키/스킬), ShareDialog, PropertiesPanel, ContextMenu, useAuth
- **Migration**: `scripts/migrate_acl.py` (기존 위키 폴더 초기 ACL + 개인 공간 생성)

**⚠️ 다음 작업 전 확인**:
1. `feat/acl-domain-scoping` 브랜치를 main에 merge할지 결정
2. 마이그레이션 실행 여부 확인 (`python scripts/migrate_acl.py`)
3. reindex로 ChromaDB access_scope 반영 (`curl -X POST http://localhost:8001/api/wiki/reindex`)

**Part 3 완료** (2026-04-15):
- 3A: require_admin (reindex) + require_write (create/move/delete folder/file) ✅
- 3B: 스킬 CRUD 권한 (personal=본인, shared delete=admin) ✅
- 3C: 프론트엔드 UI 분기 (메뉴 숨김 + "편집 권한 없습니다" 읽기전용 배너) ✅

**Part 2 완료** (2026-04-15): 2A~2C 기존 구현 확인, 2D 충돌 쌍 그룹핑 신규 구현.

**다음 후보 작업**: 사용자 논의 필요 (Part 2+3 모두 완료, ACL 기능 전체 구현 완료)

---

## 2. 이전 완료 작업

2026-04-13 이전 완료 작업 상세:
- `toClaude/modeling/CHANGES.md` — 타임스탬프순 변경 로그
- `toClaude/modeling/archive/` — 스텝별 요약 (Modeling MVP, Self-Healing, Trust System, Part 1/2/3, Path-Aware RAG, Smart Friction 등)

---

## 3. 환경/실행 방법

```bash
# 의존성
docker compose up -d chroma redis

# 백엔드 (반드시 .env 로드 — OPENAI_API_KEY 없으면 tag_registry 임베딩 실패)
source venv/bin/activate
set -a && source .env && set +a
uvicorn backend.main:app --host 0.0.0.0 --port 8001

# 프론트엔드
cd frontend && npm run dev
```

**중요한 주의사항:**
- Python 3.13에서는 onnxruntime 미지원 → 기본 ChromaDB 임베딩 안 됨 → **OPENAI_API_KEY 필수**
- 백엔드 포트는 **8001** (8000은 ChromaDB)
- tag_registry는 서버 시작 시 metadata_index에서 자동 동기화. 새 환경에서는 한번 reindex 필요할 수 있음.

---

## 4. 핵심 파일 맵 (변경된 주요 파일)

### Backend
- `backend/main.py` — 시작 시 tag_registry 초기화 + 동기화
- `backend/application/metadata/metadata_index.py` — 역인덱스, paginated API
- `backend/application/metadata/tag_registry.py` — ChromaDB 기반 의미 태그 저장소 (NEW)
- `backend/application/metadata/metadata_service.py` — 3-Layer 정규화 (프롬프트 + 임베딩 + LLM)
- `backend/api/metadata.py` — Bulk suggest, similar/groups/orphans/merge 엔드포인트

### Frontend
- `frontend/src/components/TreeNav.tsx` — 사이드바 트리 + 페이지네이션
- `frontend/src/components/editors/MetadataTemplateEditor.tsx` — 트리 구조 + 태그 건강도 대시보드
- `frontend/src/components/editors/metadata/TagInput.tsx` — Smart Friction + 건수 표시
- `frontend/src/components/editors/metadata/MetadataTagBar.tsx` — onSearchWithCount/onCheckSimilar 연동
- `frontend/src/components/editors/UntaggedDashboard.tsx` — bulk API 연동
- `frontend/src/lib/api/metadata.ts` — searchTagsWithCount, checkSimilarTags

### 테스트 샘플 파일 (의도적으로 분산된 태그)
- `wiki/인프라/캐시-장애-대응-매뉴얼.md` (캐시, Redis, 장애대응)
- `wiki/인프라/캐싱-전략-가이드.md` (캐싱, 성능최적화, 가이드)
- `wiki/인프라/cache-troubleshooting.md` (cache, troubleshooting, 레디스)
- `wiki/인프라/서버-장애처리-절차.md` (장애처리, 서버, SOP)
- `wiki/인프라/네트워크-보안-정책.md` (네트워크, 보안정책, 방화벽)
- `wiki/SCM/재고-실사-절차.md` (재고관리, 실사, 희귀태그테스트 — orphan)

---

## 5. 사용자 작업 스타일 (메모리 백업)

- **언어**: 사용자 응답은 한국어, 코드/내부 추론은 영어
- **승인 워크플로우**: 각 작업 단위마다 요구사항 질의 → 승인 → 실행. 플랜 승인 후에도 착수 전 확인.
- **데모 검증 필수**: pytest/TS 빌드만으로 데모 넘기지 말 것. 반드시 서버 띄워서 직접 테스트.
- **에이전트 변경 시**: 실제 RAG 채팅 테스트(ChromaDB+백엔드) 포함
- **문서 동기화**: 중간 추가 요청도 TODO/CHANGES/demo_guide에 즉시 반영
- **단계 완료 정의**: 코드 + 검증 + summary + demo_guide + TODO 체크 + memory + 보고. 7개 모두 완료해야 단계 끝.
- **LLM Rate**: API 키 테스트는 최소한으로

---

## 🟢 Round 6 (2026-05-05) — Authoring Agent Graph 아키텍처 진입

사용자 결정: Authoring agent 가 Code+Ontology+Mapping 3-layer graph 를 ReAct 루프로 직접 탐색.
배경: 자바독 없는 레거시 코드에서 raw text 방식 confidence 0.4 → graph 방식 0.85+. tool trace 가 evidence trail.

### Batch A 완료 (2026-05-05)
- **R6-INF-1**: `backend/application/agent_tools/` cross-cutting 모듈 (다른 에이전트 사용 가능). 23 tools (Code 12 + Ontology 6 + Mapping 3 + Operational 2). PRESETS 5종.
- **R6-INF-2**: Authoring 측 tool call trace 영속화. `AuthoringToolCallRow` 신규 + `agent_tool_adapter.py` (Logger / OperationalSession / 헬퍼).

### Batch B+C 완료 (2026-05-05)
- **R6-INF-3 (SSE)**: `agent_tools/sse.py` ToolEventPump + sse_format. `RunTracker.start_logger_fn` 추가. API `/options/stream`, `/gaps/stream`, `/tool-calls` 3 endpoint.
- **R6-INF-4 (forced reflection)**: `RunTracker.reflect_every=5` — N째 호출 결과를 `{result, _system_note}` 로 wrap.
- **시그니처 보존 fix**: `make_tracked` 가 원본 fn 의 `__signature__` 보존 → LLM 이 받는 JSON schema 정확히 derive (이전에는 빈 schema 였음).
- **R6-CAP-5/6 retro-fit**: gap_detector + option_proposer 모두 PRESET `authoring_full` (22 tool) + per-call agent + event_pump 인자. prompts 에 `# Tool use (R6)` 섹션 추가.
- **Frontend β + γ UX**: `LiveToolTraceCard` (실시간 tool 진행), `ToolTraceToggle` (결과 카드 안 expandable trace).

### Batch C2 완료 (2026-05-05) — CAP-1 + CAP-2 retro-fit
- **R6-CAP-1**: code_extractor 가 graph 5 tool (PRESET `authoring_extract`) + max_calls=5 사용. `/extract/stream` 신규.
- **R6-CAP-2**: hypothesis 가 graph 10 tool (PRESET `authoring_hypothesize`) + max_calls=8 + reflect_every=5. prompt 에 6-step 권장 순서. 신뢰도도 graph 증거 기반 calibration (0.45 → 0.65 with graph). `/hypothesize/stream` 신규.
- Frontend `runExtract` / `runHypothesize` / `refreshHypothesisFromAnswers` / `rerunStage("hypothesis")` / `rerunStage("options")` 모두 SSE 로 전환. ToolTraceStage union 확장 (extract / hypothesize 추가).

### 다음 세션 첫 작업 (사용자 결정 영역)
모든 Authoring assistant cap (1/2/5/6) 이 graph-aware. 남은 R6 항목:
- (a) **CAP-7 신규** — pattern_checker greenfield (도입 순서 마지막)
- (b) **R6-VAL** — 자바독 strip repo 로 e2e + confidence 측정 (실 LLM 비용 발생)
- (c) 다른 큰 phase

**⚠ 라이브 백엔드 재시작 필요**: 새 endpoint 5개 (`/extract/stream` `/hypothesize/stream` `/options/stream` `/gaps/stream` `/tool-calls`) 가 라우트되려면 backend uvicorn 재시작.

### 핵심 결정 (architecture decisions, 메모리: project_authoring_graph_agent.md)
- ReAct 형태: B (단계별 forced reflection)
- Tool trace UX: β + γ (진행 spinner + 결과 카드 expandable)
- Ontology tool 활성: S (recommend 29 terms 부터 즉시)
- 비용 cap: cap 당 hard max_calls + 세션 알림 (강제 종료 X)
- 도입 순서: 인프라 [DONE] → cap 5+6 → cap 1+2 → cap 7 → UI trace surfacing

### 관련 산출물
- `toClaude/modeling/code-graph-vs-raw-text.html` — 첫 분석 (G1/G2/G3 옵션)
- `toClaude/modeling/agent-graph-architecture.html` — 깊은 고찰 (23 tools / per-cap 권한 / 비용 trade-off)
- `backend/application/agent_tools/` — 6 파일 (tracking / code_tools / ontology_tools / mapping_tools / operational / registry)
- `backend/application/authoring/agent_tool_adapter.py` — Authoring 측 wiring
- `tests/test_agent_tools_*.py` + `test_agent_tool_adapter.py` — 31 신규 tests

---

## 🔴 다음 세션 첫 작업 (2026-05-05 종료 시점 픽업) — **읽고 시작할 것**

### 핵심 인지
- **Round 5 인터뷰 (`round5-live-authoring.html`)** 가 의도적으로 보류된 상태. 보류 시점: Phase A.7.7 (Gap Inspector) + A.8 (Customer / Productivity). 이유: "Authoring AI 완성 후" 표시.
- 그 사이 **Authoring AI 인프라 (R6 + P1a)** 를 완성. 이제 보류 풀고 모델링 사이클 재개.
- **DB 큐의 29 BusinessTerm + 36 Action + 34 TypeRealization 은 recommend bulk 가 자동 적재한 것** — Round 5 식 인터뷰로 만든 것이 아님. 사용자는 이걸 명시적으로 구분: *"지금 큐에 있는 애들은 그냥 recommend 로 추가된 애들. 우리가 html 로 대화하면서 구체화하고 만들어갔던 방식으로 전체 한 사이클이 돌아야해."*

### 구체적 첫 작업
**Round 5 식 풀 사이클 한 번**. entity 1개 골라서 사용자와 Claude 가 같이 HTML 로 인터뷰 → 구체화 → 결정 → ontology 에 confirm.

### Entity 후보 (3가지 갈래, 사용자 결정)
| 갈래 | 후보 | 의의 |
|---|---|---|
| **G1 — 보류 항목 재개** | `Customer (A.8)` 또는 `Productivity (A.8)` | Round 5 자체 미진행 entity. 가장 자연스러운 재개. |
| **G2 — 비교 시연** | `HrSpec` 재실시 | 이미 Round 5 에서 정리됨. Authoring AI 도구로 다시 거쳐서 결과 비교 (사용자 직접 vs AI 도구). 데모 가치 ↑ |
| **G3 — 새 entity** | 기존 적재 안 된 다른 JPO (예: `SDOrderEntity`) | clean slate. 새 도메인 영역 |

### 모드 (사용자 결정 — 차이가 큼)
| 모드 | 방식 | 비용 / 시간 |
|---|---|---|
| **M1 — Round 5 직접 인터뷰** | Claude 가 HTML 작성 → 사용자 답변 → 다음 step 작성. 도구 안 씀. | LLM 비용 0, 사용자 시간 1-2h |
| **M2 — Authoring AI 도구 사용** | 사용자가 frontend 에서 「새 세션」→ JPO 선택 → cap 1~12 진행. graph 자동 활용. | LLM 비용 ~$5 / 1 entity, 30분 |
| **M3 — 하이브리드** | M1 식 HTML 로 사용자 답변 받되, cap 1~12 도 병행 호출해서 같은 답변 자동 재현 (비교 자료) | M2 비용 + 추가 시간 |

### 시작 자료 (next-session 첫 파일들)
- `toClaude/modeling/round5-live-authoring.html` — 보류 시점 + Phase 진척
- `toClaude/modeling/recommend-vs-authoring-deep.html` — recommend vs Authoring 흐름 비교
- DB 현황: 29 term + 36 action + 34 realization (모두 draft, recommend 가 자동 적재)
- Authoring AI 도구: 27 routes 라이브 (R6 + P1a 모두 완료)
- 백엔드 살아있음 (port 8001), 프론트 살아있음 (port 3000)
- 가장 최근 R6-VAL 검증 결과: cap 2 confidence 0.50/0.45 (with/without javadoc) → 도구 가치 검증됨

### 시작 직후 Claude 가 할 일 순서
1. 이 HANDOFF 의 본 섹션 확인
2. `CHANGES.md` 의 `[ ]` 항목 (지금 없음) 확인
3. 사용자에게 G1/G2/G3 + M1/M2/M3 조합 어떤 거 원하는지 물어봄
4. 결정 후 첫 step 부터 진행 — 사용자 답변 받고 다음 step

### 컨텍스트 메모
- 사용자 = 팀 리더, Section 2 직접 담당
- 비판적 검토 선호 — "내가 뭘 알려주기 전에 너무 많은 걸 알고 물어보는 느낌" (P1-B feedback) 주의
- "MVP 제안 금지, 풀 시연 가정" — 작업 단위 끝까지 완결
- "일정/시간/우선순위 분기 제안 금지. 사용자가 결정." — 추천만 하되 결정은 사용자

### 백엔드 / 프론트엔드 상태
- Backend uvicorn (port 8001) — 24+ routes 라이브 (R6 + P1a). 변경 시 `pkill -f uvicorn ; set -a && . ./.env && set +a && ./.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001 --log-level info` 로 재시작.
- Frontend Next.js (port 3000) — Turbopack dev mode.
- 새 세션 시작 시 backend / frontend 둘 다 살아있는지 먼저 확인 (`curl -s -o /dev/null -w "%{http_code}\n" --max-time 5 http://localhost:8001/openapi.json`).

마지막 업데이트: 2026-05-05 (R6 + P1a + P3 폴리싱 6건 모두 완료. P4 데모 전 Round 5 풀 사이클 한 번 결정 → 다음 세션 진입.)
