# onTong — Phase 1 실행 TodoList (v2)

> 기반 문서: `plan/master_plan.md`
> 최종 갱신: 2025-03-25 (전문가 검토 반영)
> 사용법: 각 단계를 순서대로 Claude에게 지시. 완료 시 `[x]`로 체크.

---

## Section 2 — OD-11 방향 전환 (ACTIVE, 2026-04-19~)

> **상세**: `toClaude/modeling/OD-11-PLAN.md`
> **배경**: OD-10이 착오 판단. 매뉴얼 1차 → 코드 1차로 피벗. 삭제본 복원 + 확장 결정.
> **우선순위**: Phase A (문서화) 완료 후 Phase B (Round 1 HTML 초안 + 스키마 확정) 착수.

### Phase A — 문서화 + 복원 결정

| # | Task | 의존 | 상태 | 산출물 |
|---|------|------|------|--------|
| OD-11-A1 | OD-11-PLAN.md 작성 | - | [x] | `toClaude/modeling/OD-11-PLAN.md` |
| OD-11-A2 | TODO/HANDOFF/CHANGES/memory 갱신 | A1 | [x] | 4 files |
| OD-11-A3 | 복원 범위 사용자 최종 승인 | A2 | [x] | 2026-04-19 "응 동의" + "진행해" |

### Phase B — Round 1 스키마 (코드 쪽 + Spring)

| # | Task | 의존 | 상태 | 산출물 |
|---|------|------|------|--------|
| OD-11-B1 | Round 1 HTML 설명서 초안 | A3 | [x] | `toClaude/modeling/round1-code-schema.html` (2026-04-19) |
| OD-11-B2 | Q1~Q8 피드백 반영 rev.2 (확장성·데이터 계보·Reflection·hops) | B1 | [x] | HTML rev.2 (2026-04-19) |
| OD-11-B2' | Q9~Q11 답변 rev.3 반영 (동적 매핑 3 분석기 / 임시 섹션 / slab 엔진 타겟) | B2 | [x] | HTML rev.3 (2026-04-19) |
| OD-11-B3 | `parser_protocol.py` 복원 + `EntityKindRegistry` 플러그인화 (Q1/Q2) | B2' | [x] | `backend/modeling/code_analysis/parser_protocol.py` — 16 entity + 17 relation 기본 등록, 21/21 테스트 통과 (2026-04-19) |
| OD-11-B4 | `java_parser.py` 복원 + Spring 분석기 분리 + `graph_writer.py` 17 엣지 지원 | B3 | [x] | `backend/modeling/code_analysis/{java_parser,graph_writer}.py` + `spring/` 패키지 (6 stub analyzer), 51/51 테스트 통과 (2026-04-19) |
| OD-11-B5 | Spring 8 난제 PoC (DI/AOP/Reflection/Data JPA/Bean/Event/Scheduled/Profile) | B4 | [~] | 8 PoC 모듈 (아래 B5-1~B5-8 참조) |
| ├ OD-11-B5-1 | `DIAnalyzer` — `@Autowired`/`@Inject`/생성자 주입 → `AUTOWIRES` + `spring_bean` | B4 | [x] | `backend/modeling/code_analysis/spring/di_analyzer.py` + `tests/test_spring_di_analyzer.py` 23/23 통과, 111/111 누적 (2026-04-19) |
| ├ OD-11-B5-2 | `AopAnalyzer` — `@Aspect` + 5 advice + `@Pointcut` + `@Order` → `aspect` + `INTERCEPTS` | B5-1 | [x] | `backend/modeling/code_analysis/spring/aop_analyzer.py` + `tests/test_spring_aop_analyzer.py` 23/23 통과 (2026-04-19) |
| ├ OD-11-B5-3 | `HttpAnalyzer` — `@RestController`/`@Controller` + `@RequestMapping` + 5 method shortcut → `http_endpoint` + `MAPS_URL` | B5-2 | [x] | `backend/modeling/code_analysis/spring/http_analyzer.py` + `tests/test_spring_http_analyzer.py` 26/26 통과 (2026-04-19) |
| ├ OD-11-B5-4 | `EventsAnalyzer` — `ApplicationEventPublisher`/`@EventListener` → `event_type` + `PUBLISHES`/`HANDLES` | B5-3 | [x] | `backend/modeling/code_analysis/spring/events_analyzer.py` + `tests/test_spring_events_analyzer.py` 19/19 통과 (2026-04-19) |
| ├ OD-11-B5-5 | `ScheduledAnalyzer` — `@Scheduled` → `scheduled_task` | B5-4 | [x] | `backend/modeling/code_analysis/spring/scheduled_analyzer.py` + `tests/test_spring_scheduled_analyzer.py` 15/15 통과, Spring 5-analyzer 누적 106/106 + 모델링 전체 180/180 (2026-04-19) |
| ├ OD-11-B5-6 | `ProfileAnalyzer` — `@Profile`/`@ConditionalOnProperty` 속성 주입 (class-level 는 B5-1 에서 기 처리) | B5-5 | [x] | `backend/modeling/code_analysis/spring/profile_analyzer.py` + `java_parser.py` enrich 훅 + `tests/test_spring_profile_analyzer.py` 17/17 통과, Spring 6-analyzer 123/123 + 모델링 전체 197/197 (2026-04-19) |
| ├ OD-11-B5-7 | `JpaAnalyzer` — Spring Data JPA Repository + 쿼리 메서드 | B5-6 | [x] | `backend/modeling/code_analysis/spring/jpa_analyzer.py` 신규 (~210 LOC) — `@Repository` 또는 `JpaRepository`/`CrudRepository`/`PagingAndSortingRepository`/`Repository` 4 base interface extends 탐지 + 첫 generic 파라미터 = entity simple name. **메서드 이름 컨벤션** : `find*By*`/`get*By*`/`query*By*`/`read*By*`/`search*By*` → `READS_TABLE` (`jpa_operation="find"`) / `exists*By*` → `"exists"` / `count*By*` → `"count"` / `delete*By*`/`remove*By*` → `WRITES_TABLE` (`"delete"`) / `save`/`saveAll`/`saveAndFlush` (정확) → `WRITES_TABLE` (`"save"`) / 그 외 edge 없음. **edge attributes** : `jpa_operation` + `jpa_property_path` (예: `findByEmailAndStatus` → `["email","status"]` And/Or split + camelCase 첫글자 소문자화) + `target_kind="jpa_entity_simple_name"`. target = entity simple name (CrossFileEnricher v2 에서 `@Table(name=...)` 으로 향후 rewrite, 본 analyzer scope 외). class declaration / 일반 interface (Spring Data 미extends) 무시. spring/__init__.py + `scripts/dump_entities_snapshot.py` 12번째로 등록. `tests/test_spring_jpa_analyzer.py` 27/27 PASS (TestDetection 5 + TestMethodNameOperations 14 parametrized + TestMethodAttributes 3 + TestMultipleMethods 2 + TestProtocol 3). Slab 샘플 (JPA 없음) 12-analyzer 결과 95/177 그대로 — JPA 없는 코드 안 깨짐 검증. 전체 1627 PASS / 20 FAIL (전부 Section 1 baseline). **데모 코드가 JPA 사용 시 즉시 효과** — Repository 메서드 → 테이블 접근 그래프 자동 추출. (2026-04-25) |
| └ OD-11-B5-8 | Reflection static marker — L1 정적 감지 (L3 런타임은 B7) | B5-6 | [x] | `backend/modeling/code_analysis/spring/reflection_analyzer.py` + `tests/test_spring_reflection_analyzer.py` 20/20 통과, Spring 7-analyzer 143/143 + 모델링 전체 217/217 (2026-04-19, B5-7 스킵) |
| OD-11-B6 | 동적 매핑 3 분석기 + Cross-file Enricher (Q9) | B5 | [x] | 4 모듈 완료 (B6-1 MapStruct + B6-2 BeanUtils + B6-3 NativeSQL + B6-4 CrossFileEnricher). 스펙 `toClaude/modeling/OD-11-B6-SPEC.md` 2026-04-19 승인. 모델링 범위 272/272 통과 (2026-04-19) |
| ├ OD-11-B6-1 | `MapStructAnalyzer` — `@Mapper` + `@Mapping(source/target/expression)` → `PROPAGATES_TO`/`DERIVES_FROM` (FIELD→FIELD) | B5-8 | [x] | `backend/modeling/code_analysis/spring/mapstruct_analyzer.py` + `tests/test_spring_mapstruct_analyzer.py` 16/16 통과, Spring 8-analyzer 159/159, 모델링 범위 223/224 (lineage 1 선행 실패) (2026-04-19) |
| ├ OD-11-B6-2 | `BeanUtilsAnalyzer` — Spring/Apache/ModelMapper `copyProperties`/`map` → METHOD marker `beanutils_calls` (교집합은 B6-4) | B6-1 | [x] | `backend/modeling/code_analysis/spring/beanutils_analyzer.py` + `tests/test_spring_beanutils_analyzer.py` 13/13 통과, Spring 9-analyzer 172/172, 모델링 범위 283/284 (lineage 1 선행 실패) (2026-04-19) |
| ├ OD-11-B6-3 | `NativeSqlAnalyzer` — `@Query`/`createNativeQuery`/`JdbcTemplate` → `READS_TABLE`/`WRITES_TABLE` (sqlglot) | B6-2 | [x] | `backend/modeling/code_analysis/spring/native_sql_analyzer.py` + `tests/test_spring_native_sql_analyzer.py` 16/16 통과, Spring 10-analyzer 190/190, 모델링 범위 262/262 (lineage 1 선행 실패, Wiki 영역), `sqlglot = "^23.0"` 추가 (2026-04-19) |
| └ OD-11-B6-4 | `CrossFileEnricher` — repo-level FIELD 교집합 + column→field 해소 + DB_TABLE dedup | B6-3 | [x] | `backend/modeling/code_analysis/cross_file_enricher.py` + `jpa_annotation_extractor.py` + `tests/test_cross_file_enricher.py` 10/10 통과, 모델링 범위 272/272 (lineage 1 선행 실패, Wiki 영역) (2026-04-19) |
| OD-11-B7 | Reflection literal resolver + 런타임 계측 수집기 (B7-0/1/2 subphase, Q4) | B6 | [x] | SPEC: `toClaude/modeling/OD-11-B7-SPEC.md`, decisions HTML: `OD-11-B7-decisions.html`. B7-0/1/2 전부 완료 (2026-04-19) |
| ├ OD-11-B7-0 | `ReflectionAnalyzer` marker 에 `arg_kind` ∈ {literal, variable, concat, type, other} 추가, `arg` 의미를 소스 텍스트로 변경 | B6-4 | [x] | `backend/modeling/code_analysis/spring/reflection_analyzer.py` + `tests/test_spring_reflection_analyzer.py` 25/25 통과, 모델링 범위 231/231 (2026-04-19) |
| ├ OD-11-B7-1 | `reflection_literal_resolver.py` — `getBean`/`Class.forName` literal → `class_index`·`bean_index` 매칭해 `CALLS{source:static_literal\|static_unresolved}` 엣지 emit | B7-0 | [x] | `backend/modeling/code_analysis/reflection_literal_resolver.py` + `tests/test_reflection_literal_resolver.py` 15/15 통과, `di_analyzer.py` SPRING_BEAN.attributes["bean_name"] 확장 (@Component/@Service/@Bean + camelCase fallback), 통합 타깃 73/73, 모델링 범위 295/295 (2026-04-19) |
| └ OD-11-B7-2 | `runtime_collector.py` Protocol + `ReflectionTrace`/`CallTrace` DTO + `JsonFileCollector` + `merge_runtime_traces` + synthetic `ParseResult(file_path="<runtime>")` | B7-1 | [x] | `backend/modeling/code_analysis/runtime_collector.py` + `tests/test_runtime_collector.py` 14/14 통과, `parser_protocol.py` `REFLECTS_AS` 등록 (기본 kind 17→18), 통합 타깃 117/117, 모델링 범위 309/309 (2026-04-19) |
| OD-11-B8 | Impact/BFS hops 자율 조정 API 스펙 + 쿼리 엔진 파라미터화 (Q6, 4-way subphase) | B7 | [ ] | SPEC: `toClaude/modeling/OD-11-B8-SPEC.md` (Q1~Q7 승인 완료). `backend/modeling/query/query_engine.py` + `query_models.py` 신규 설계 (구버전 복원 아님) |
| ├ OD-11-B8-0 | DTO (`ImpactQuery`/`ImpactMode`/`AffectedEntity`/`ImpactResult`/`EdgeRow`/`EntityRow`/`ImpactConfig`) + `GraphView` Protocol + `InMemoryGraphView` 어댑터 | B7-2 | [x] | `backend/modeling/query/query_models.py` (95 LOC) + `graph_view.py` (90 LOC) + `tests/test_query_models.py` 15/15 + `tests/test_in_memory_graph_view.py` 10/10 통과, 모델링 범위 199/199 (2026-04-19) |
| ├ OD-11-B8-1 | `QueryEngine.impact` BFS 코어 (incoming 기본) + 3-mode 필터 (safe/observed/potential) + path/confidence_min/edge_source_chain 추적 | B8-0 | [x] | `backend/modeling/query/query_engine.py` (165 LOC) + `tests/test_query_engine_impact.py` 14/14 통과, 모델링 범위 213/213 (2026-04-19) |
| ├ OD-11-B8-2 | hops 자율 축소 + timeout + `hops_shrunk_reason` 리포팅 + `frontier_warn_threshold` 경고 | B8-1 | [x] | `backend/modeling/query/query_engine.py` +27 LOC + `tests/test_query_engine_shrink.py` 7/7 통과, 모델링 범위 21 파일 329/329 (2026-04-19) |
| └ OD-11-B8-3 | Reverse Lookup 스텁 (`direction="outgoing"`) + `<reflection-site>` 진단 수집 + `unresolved_sources` 채우기 | B8-2 | [x] | `backend/modeling/query/query_engine.py` +38 LOC + `tests/test_query_engine_reverse.py` 8/8 통과, 모델링 범위 22 파일 337/337 (2026-04-19) |
| OD-11-B9 | Slab 엔진 sample repo 수령 → 파서 가동 첫 E2E (Q11) | B8 + 사용자 제공 | [ ] | sample repo 경로 + 파싱 결과 리포트 |

### Phase C — Round 2 스키마 (비즈니스 개념 + 브릿지)

| # | Task | 의존 | 상태 | 산출물 |
|---|------|------|------|--------|
| OD-11-C1 | Round 2 HTML 설명서 초안 | Phase B | [x] | `toClaude/modeling/round2-concept-bridge.html` rev.2 — Q1~Q7 사용자 합의 반영 (2026-04-20). 노드 2종 (BusinessTerm/BusinessRule) + 엣지 2종+1예약 (REALIZES/VALIDATES/DERIVED_FROM) + Resolver 4단 + 수동 seed → 자동 제안 → 사람 승인 파이프라인 확정. Process/Role 은 Phase D 이월. |
| OD-11-C2 | `mapping_models.py` 재설계 (1:N + method-level 기본) | C1 | [x] | `backend/modeling/mapping/{__init__,mapping_models}.py` 신규 (~180 LOC). Pydantic DTO 5종 : `BusinessTerm` / `BusinessRule` / `ConceptBinding` / `ConceptBindingSet` (primary unique + (term,code) pair 중복 거부) / `ResolutionAuditLog`. Enum 5종 : `BusinessTermSource`/`BindingSource`/`BindingScope`/`RuleSeverity`/`ResolutionSource`. `tests/test_mapping_models.py` 28/28 통과 (0.08s), 모델링 범위 365/365 (2026-04-20). |
| OD-11-C3 | `term_resolver.py` 재구조화 (임베딩 + data-driven alias) | C2 | [x] | `backend/modeling/query/term_resolver.py` 신규 (~280 LOC) + `tests/test_term_resolver.py` 35/35 통과 (0.09s), 모델링 범위 400/400 (2026-04-20). 4-stage chain (exact 1.0 / alias 1.0 / embedding ≥ 0.78 / LLM ≥ 0.6 / MISS) + `EmbeddingProvider` Protocol + `InMemoryEmbeddingProvider` (테스트/데모) + `OpenAIChromaProvider` (Q6 A 프로덕션 참조) + `LLMResolver` Protocol + `ResolutionCutoffs` / `ResolutionResult` / `Candidate` / `SimHit` / `LLMProposal` DTO + `ResolutionAuditLog` 1회/쿼리. |
| OD-11-C4 | Reverse Lookup API 초안 | C3 | [x] | `backend/modeling/api/reverse_lookup_api.py` (~235 LOC) + `backend/modeling/mapping/{audit_store,concept_store}.py` 신규. REST `GET /api/modeling/reverse_lookup` + SSE `GET /api/modeling/reverse_lookup/stream` (resolving/resolved/complete 3 event). 체인 : `TermResolver(C3).resolve → audit_store.append → ConceptBindingStore.list_by_term(scope_filter) → include_unconfirmed 필터 → InMemoryGraphView(term→code REALIZES) → QueryEngine.reverse_lookup(edge_kinds={REALIZES})`. `ReverseLookupResponse` DTO (query_term/resolution/scope_filter/include_unconfirmed/impact). 게이트 : MISS/unconfirmed → impact=None. `parser_protocol.py` Round 2 kinds 등록 확장 (business_term/business_rule + realizes/validates/derived_from, 17→18 엔티티 + 18→21 릴레이션). `main.py` startup wiring : `ONTONG_EMBEDDING=openai` → `OpenAIChromaProvider`, else `InMemoryEmbeddingProvider` seed. `tests/test_reverse_lookup_api.py` 22/22 통과 (0.33s), 모델링 회귀 422/422 (2026-04-20). |

### Phase D — Round 3 스키마 (기준서/문서 + 갭 탐지)

| # | Task | 의존 | 상태 | 산출물 |
|---|------|------|------|--------|
| OD-11-D1 | Round 3 HTML 설명서 초안 | Phase C | [x] | `toClaude/modeling/round3-manual-gap.html` rev.2 (Q1~Q9 합의 반영, 2026-04-20). 노드 5종 (BusinessProcess/Role/ManualDocument/ManualSection/ManualFragment) + 엣지 6종 (PART_OF/RESPONSIBLE_FOR/DESCRIBED_IN/CONFLICTS_WITH/MISSING_IN/PARENT_PROCESS). 주요 결정 : Q1=C (PARENT_PROCESS 엣지 분리), Q2=A (Role team 단위 고정), Q3=C (DESCRIBED_IN → Section+Fragment 양쪽), Q4=C+A 전환 (기본 hierarchical 3단 + `gap_mode=llm_only` 모드 선택), Q5=A (LLM severity 제안 + 사람 승인), Q6=A (MISSING_IN 양방향), Q7=E (UI+watch folder+git hook 3 트리거), Q8=B (authoritative flag 명시), Q9=D (pypdf+pdfplumber+python-docx 전부 + OCREngine 재사용). 771 LOC. |
| OD-11-D1.5 | Round 3 DTO 확장 (조직 + 기준서 + Gap) | D1 | [x] | `backend/modeling/manuals/{__init__,manual_models}.py` 신규 + `backend/modeling/mapping/{__init__,mapping_models}.py` 확장. Pydantic DTO 13종 : BusinessProcess (parent 필드 없음, Q1=C) / Role (team 접두어 강제, Q2=A) / PartOfBinding / RoleBinding (team-only) / ParentProcessBinding (self-ref 금지) / ParentProcessBindingSet (three-color DFS cycle detection + 중복 엣지 거부) / ManualDocument (authoritative=False 기본, Q8=B) / ManualSection / ManualFragment (kind ∈ text/image/table/formula/ocr_text) / DescribedInBinding (target_kind ∈ manual_section/manual_fragment) / ConflictBinding (severity/detected_by/gap_mode, Q4=C+A) / MissingBinding (direction ∈ code_only/manual_only). Enum 9종 신규 (RoleKind/ResponsibilityKind + ManualFormat/ManualFragmentKind/GapSeverity/GapDetectedBy/GapMode/GapDirection/DescribedInTargetKind). `tests/test_manual_models.py` 44 + `tests/test_mapping_models.py` 확장 60 → 104/104 통과 (0.07s). 모델링 회귀 246/246 (2026-04-20). |
| OD-11-D1.6 | parser_protocol EntityKinds/RelationKinds 확장 | D1.5 | [x] | `backend/modeling/code_analysis/parser_protocol.py` 확장 — Entity +5 (business_process/role/manual_document/manual_section/manual_fragment) + Relation +6 (part_of/responsible_for/parent_process/described_in/conflicts_with/missing_in), 모두 category="concept". `EntityKinds`/`RelationKinds` 편의 상수 확장. `tests/test_parser_protocol_phase_d.py` 신규 24/24 PASS. 모델링 회귀 524/524 PASS. ontology/schema.py Literal 과 모듈 경계 분리 확인 (충돌 없음). graph_writer 화이트리스트는 `RelationKindRegistry.is_registered` 동적 검증으로 자동 통과. 2026-04-20. |
| OD-11-D2 | PDF/PPT/이미지/Word 인제스트 파이프라인 (OCR/python-pptx/python-docx 재활용) | D1.6 | [ ] | `backend/modeling/manual_ingest/` — D2-1/D2-2/D2-3 서브로 분할. |
| OD-11-D2-1 | 5 포맷 파서 + ManualParser Protocol + ParseResult DTO (pypdf/python-docx/python-pptx/OCREngine 재사용) | D1.6 | [x] | `backend/modeling/manual_ingest/` 신규 패키지 — `parser_protocol.py` (Protocol + ParseResult + FQN/checksum helpers) + 5 파서 (`md_parser.py` heading-stack + paragraph/fence/table chunking / `pdf_parser.py` pypdf 페이지=섹션 / `docx_parser.py` Heading style 기반 / `pptx_parser.py` 슬라이드=섹션 / `image_parser.py` OCREngine 주입 + OCR_TEXT Fragment + 실패 warning). `tests/_manual_ingest_fixtures.py` (pypdf low-level 스트림 + python-docx/python-pptx fixture) + 6 테스트 (`test_manual_ingest_*`) 48/48 PASS. 모델링 회귀 251/251 PASS (2026-04-20). `pyproject.toml` deps 추가 (pypdf ^5.0 / pdfplumber ^0.11 / python-docx ^1.2 / python-pptx ^1.0). |
| OD-11-D2-2 | Ingest pipeline + manual registry + 업로드 API (체크섬 중복 스킵 + 임베딩 + graph 쓰기) | D2-1 | [x] | `backend/modeling/manual_ingest/{manual_registry.py, embedding_store.py, pipeline.py}` + `backend/modeling/api/manuals_api.py` — `ManualIngestPipeline` (SKIP/UPDATE/FORCE + doc-fqn dedup + optional graph/embedding) + `InMemoryManualRegistry` (Protocol + authoritative 토글 Q8=B) + `InMemoryManualEmbeddingStore` + `ChromaManualEmbeddingStore` (`manual_fragments` 컬렉션) + `CodeGraphManualWriter` 어댑터 (Manual*→CodeEntity) + REST `POST /api/modeling/manuals/upload` (multipart) + `GET /api/modeling/manuals` + `POST /manuals/{fqn}/authoritative` + SSE `POST /manuals/upload/stream` (parsing/persisting/complete). `tests/test_manual_registry.py` 13 + `tests/test_manual_ingest_pipeline.py` 13 + `tests/test_manuals_api.py` 10 = 36/36 PASS. 모델링 회귀 329/329 (manual+ontology+reverse_lookup+spring+term_resolver). 전체 1376 passed / 21 failed (Section 1 baseline, 이번 변경과 무관). `backend/main.py` lifespan 에 파이프라인/레지스트리/임베딩 wiring + `modeling/api/modeling.py` 에 manuals 라우터 include (2026-04-20). |
| OD-11-D2-3 | 3 트리거 wiring (UI 업로드 + watch folder + git hook) Q7=E | D2-2 | [x] | `backend/modeling/manual_ingest/watch_folder.py` (폴링 기반 `ManualFolderWatcher` + `WatchScanResult` — mtime+size 스냅샷 diff → `IngestMode.UPDATE`, 재귀 서브폴더, `seed_existing` 토글, 삭제 추적) + `backend/modeling/manual_ingest/git_hook_webhook.py` (`GitHookRequest`/`GitHookResponse` + `parse_git_webhook_payload` + `ingest_changed_files` — repo_root 기반 상대/절대 경로 resolve, path escape 방어, unsupported 확장자 skipped, removed 집계) + `backend/modeling/api/manuals_api.py` 에 `POST /api/modeling/manuals/git-hook` 추가 (`GitHookResponseDTO`, `asyncio.to_thread`, `ValueError→400` / 미초기화 503) + `frontend/src/lib/api/modeling.ts` 확장 (`listRegisteredManuals`/`uploadManual`/`toggleManualAuthoritative`/`uploadManualStream` async generator, fetch+ReadableStream+TextDecoder 로 POST+SSE 구현) + `frontend/src/components/sections/modeling/ManualUpload.tsx` 신규 (드롭존 + 모드 pill + SSE 라이브 이벤트 + 목록 + authoritative 토글 스위치) + `ModelingSection.tsx` 탭 "매뉴얼 업로드" 추가. `tests/test_manual_watch_folder.py` 12 + `tests/test_manual_git_hook_webhook.py` 11 + `tests/test_manuals_api_git_hook.py` 7 = 30/30 PASS. 모델링 회귀 677/677 (D2 영역 66/66). 전체 1406 passed / 21 baseline failed. TS clean. Runtime smoke OK (152 routes, +1 D2-2 대비). (2026-04-21) |
| OD-11-D3 | 갭 탐지 엔진 (코드↔기준서 diff) | D2 | [~] | `backend/modeling/gap_detection/` — D3-1/D3-2/D3-3 서브로 분할 |
| OD-11-D3-1 | MISSING_IN 양방향 탐지기 (Q6=A, code_only/manual_only) | D2 | [x] | `backend/modeling/gap_detection/{gap_models,gap_store,missing_in_detector,__init__}.py` — `GapCandidate`/`ScanConfig`/`ScanResult` DTO + `GapStore` Protocol + `InMemoryGapStore` (upsert 시 confirmed 보호) + `MissingInDetector` (code_only=SOFT, manual_only=HARD, stable id sha1[:16] re-scan idempotent) + `SimpleHeuristicExtractor` (4 regex: `**bold**`/`` `code` ``/`「한글」`/`"ascii"`, IMAGE kind 스킵). `tests/test_gap_store.py` 10 + `tests/test_missing_in_detector.py` 18 = 28/28 PASS (0.06s). 모델링 회귀 705/705. 전체 1434 passed / 21 baseline. 152 routes (변동 없음, D3-1 은 API 미추가). (2026-04-21) |
| OD-11-D3-2 | CONFLICTS_WITH 3단 hierarchical + llm_only (Q4=C+A) | D3-1 | [x] | `rule_ast_differ.py` + `embedding_drifter.py` + `llm_comparator.py` + `gap_engine.py` Strategy — D3-2-a + D3-2-b 완료 (2026-04-21). 2 deterministic stage + pydantic-ai LLM stage 3 + Hierarchical/LLM-only Strategy. |
| OD-11-D3-2-a | CONFLICTS_WITH deterministic (rule_ast + drift + engine skeleton) | D3-1 | [x] | `backend/modeling/gap_detection/{rule_ast_differ,embedding_drifter,gap_engine}.py` — `extract_quantities` (숫자/비교연산자/단위 정규식 4 패턴) + `RuleStatementTokens` + `DiffOutcome` + `RuleASTDiffer` (HIGH severity hit, IMAGE 스킵, described_in 매핑 쌍만) + `TextEmbedder` Protocol + `CosineDrifter(cutoff=0.65)` (MEDIUM severity, zero-vector 안전) + `LLMComparator` Protocol + `GapEngine` Protocol + `HierarchicalGapEngine` (stage 1 hit → stage 2 skip dedup / optional LLM stage 3 severity override) + `LLMOnlyGapEngine` (skeleton, comparator 없으면 []+warning) + `create_gap_engine(mode=…)` factory. `GapSeverity` 확장 +4 (LOW/MEDIUM/HIGH/CRITICAL). `tests/test_rule_ast_differ.py` 14 + `tests/test_embedding_drifter.py` 7 + `tests/test_gap_engine_conflicts.py` 9 = 30/30 PASS. 모델링 회귀 735/735 (+30). 전체 1464 passed / 21 baseline. 152 routes. (2026-04-21) |
| OD-11-D3-2-b | LLM Comparator 실 구현 + severity 재평가 (Q5=A) | D3-2-a | [x] | `backend/modeling/gap_detection/llm_comparator.py` — pydantic-ai Agent + `llm_factory.get_model()` 재사용 + `output_type=LLMComparisonResult` (Literal low/medium/high/critical) + Graceful degrade (prior severity 폴백) + Belt-and-suspenders `_coerce_conflict_severity` 이차 방어. `tests/test_llm_comparator.py` 12 PASS + 1 integration SKIP. 모델링 회귀 747/747, 전체 1476 passed / 21 baseline. `backend/main.py` lifespan 에 `ONTONG_LLM_COMPARATOR=openai` 분기 (engine 주입은 D3-3). `pyproject.toml` integration marker 등록. (2026-04-21) |
| OD-11-D3-3 | 승인 큐 + REST/SSE API + 프런트 스텁 (Q5=A) | D3-2 | [x] | `backend/modeling/gap_detection/gap_scanner.py` + `backend/modeling/api/gaps_api.py` + `backend/modeling/gap_detection/embedding_drifter.py` (`HashingTextEmbedder` 추가) + `frontend/src/lib/api/modeling.ts` (scanGaps/scanGapsStream/listGaps/confirmGap + GapCandidateDto/UnifiedScanResponse/SseEvent) + `frontend/src/components/sections/modeling/GapQueue.tsx` 신규 + `ModelingSection.tsx` MAIN_NAV "갭 큐" 탭 추가. `GapScanner` 오케스트레이터 (`MissingInDetector` + `GapEngine` + `ManualRegistry` auto-pull fragments + progress callback) + `UnifiedScanResult` (frozen, `.all` property) + partial hybrid API 계약 (fragments 미지정 시 ManualRegistry 자동 조회, rules/described_in 은 body 필수). 4 routes : `POST /api/modeling/gaps/scan` (sync) + `POST /api/modeling/gaps/scan/stream` (SSE scanning→stage1_missing_in→stage2_conflicts→complete, asyncio.to_thread + 버퍼드 flush 로 TestClient race 해결) + `GET /api/modeling/gaps` (direction/severity/include_confirmed 필터) + `POST /api/modeling/gaps/{gap_id}/confirm`. `main.py` lifespan 에 `_gap_store` / `_missing_detector` / `_gap_engine` / `_gap_scanner` wiring + gaps_api.init + router include. `tests/test_gap_scanner.py` 10 + `tests/test_gaps_api.py` 12 = 22/22 PASS. 모델링 회귀 회귀 127/127 (gap 계열). 전체 pytest 1498 passed / 31 baseline (우리 변경 무관). TS clean (orphan ManualOntologyBuilder/ManualUpload 제외). 156 routes (D3-2-b 대비 +4). (2026-04-21) |
| OD-11-D4 | 사람 검증 UI 설계 | D3 | [ ] | 프론트 디자인 스펙 |
| OD-11-UX-1 | ModelingSection 사이드바 정리 — 테스트 불필요 탭 숨김 | D3-3 | [x] | `frontend/src/components/sections/ModelingSection.tsx` — MAIN_NAV="갭 큐" 단일, SETTINGS_NAV=[], `needsRepoSelector` 유도 상수, `activeView` 초기 `"gap-queue"`, Repo selector/placeholder/demo 로드 버튼 조건부 렌더. ViewRouter switch 는 보존 (legacy 컴포넌트 import 그대로). 미사용 lucide import 정리. TS clean. 배경: UI/UX 대대적 개편 가능성 — `memory/feedback_ui_ux_rework.md`. (2026-04-21) |
| OD-11-E1-a | Slab Design Engine 샘플 프로젝트 생성 (Phase E 준비 작업) | D3-3 | [x] | `sample-repos/slab-design-engine/` 14 파일 — Spring Boot 3 / Java 17. 패키지 `com.ontong.slab.{config,domain,constraint,optimizer,service,controller}` + `pom.xml` + `application.yml` + `README.md`. 도메인 = 직육면체 Slab (L×W×T + grade), 목적식 = `max ρ·L·W·T` s.t. 설비 제약 4종 (압연기 폭 2400 / 가열로 길이 12000 / 크레인 하중 45000 / 두께 180~240). `WeightMaximizer` 50mm 그리드 + `adjustWeightBias(1.02)` 안전계수. REST `POST /slabs/design`. **의도적 gap 후보 5종** 심어둠 (매직넘버 240/1.02/50 + `adjustWeightBias()` code_only + 보정 후 재검증 누락 manual_only). 한국어 Javadoc 에 비즈니스 룰 자연어 포함 (규칙 추출기 타겟). `javac 17` 문법 검증 clean. 다음: 코드 분석 파이프라인 등록 + 대응 매뉴얼 작성. (2026-04-21) |
| OD-11-E1-b | Slab 엔진 코드 분석 파이프라인 등록 검증 | E1-a | [x] | `JavaParser` 기본 = **85 entities / 167 relations / 0 errors**. Spring 10-analyzer 일괄 = **90 entities / 172 relations / 0 errors** (+5/+5). 신규 entity = `spring_bean` × 4 + `http_endpoint` × 1 (POST `/slabs/design`). 신규 relation = `AUTOWIRES` × 4 + `MAPS_URL` × 1. **DI 그래프 검증** : Controller → Service → WeightMaximizer → {Checker, Properties} 의도한 wiring 그대로. **한계** : `EquipmentProperties` 가 `config_property` 로 승격되지 않음 (`@ConfigurationProperties` 전담 analyzer 없음). `field.attributes` 리터럴 값 (240/1.02/50) 포함 여부 미확인 — CONFLICTS_WITH 매직넘버 감지 의존. Javadoc → BusinessRule 추출기 부재. 다음 후보 : A1 entities.json 스냅샷 / A2 field.attributes 검증 / A3 Javadoc 추출기 / B 매뉴얼 작성. (2026-04-21) |
| OD-11-E1-c | (A2) JavaParser field 추출 확장 — `field.attributes` 에 `field_type` / `initializer` / `initializer_kind` (리터럴 vs 표현식) 캡처 | E1-b | [x] | `backend/modeling/code_analysis/java_parser.py` `_extract_field` 확장 + `_classify_initializer` 신규 (literal_number/literal_string/literal_boolean/literal_null/literal_char/expression 6 분류, unary_expression 부호 wrapping 처리) + `tests/test_java_parser_field_attributes.py` 20/20 PASS (TestFieldType 4 + TestInitializerLiteral 10 + TestInitializerEdgeCases 3 + TestSlabSampleLiterals 3). Slab 실증 : `WEIGHT_BIAS_FACTOR=1.02` / `GRID_STEP_MM=50.0` / `maxThicknessMm=240.0` 모두 attributes 에 노출. modeling 회귀 309/309 (B6 + B7 + spring + java_parser + cross_file 범위). 전체 1518 PASS / 20 FAIL (전부 Section 1 baseline). CONFLICTS_WITH 매직넘버 감지 입력 확보. (2026-04-25) |
| OD-11-E1-d | (A3) Javadoc → BusinessRule 추출기 — 한국어 자연어 룰 → `BusinessRule` Pydantic DTO + `VALIDATES` 엣지. CONFLICTS_WITH gap 감지의 코드 쪽 rule 입력. | E1-c | [x] | `backend/modeling/code_analysis/javadoc_rule_extractor.py` 신규 (~190 LOC, `JavadocRuleExtractor` 클래스 + `extract_rules_from_file()` convenience). tree-sitter 로 `block_comment` 노드 재파싱 → `/** ... */` 인 것만 채택 → 다음 sibling declaration (class/interface/enum/method/constructor) 매칭 → `(line_start, kind)` 색인으로 ParseResult.entities 의 FQN 해소 → bullet/문장 분리 → 룰 휴리스틱 (`이상\|이하\|초과\|미만\|불가\|금지\|이어야\|여야\|되어야\|해야 한다\|허용되지\|던진다` 키워드 OR `≤≥<=>===!=` 부등식 + 식별자) → 통과 문장만 `BusinessRule` 생성. **FQN** = `{target_fqn}#rule{N}` (1-indexed deterministic). **Severity** = HARD if 금지/불가/Exception/허용되지/차단/초과할 수 없 키워드, else SOFT. **field 는 v1 skip**. 일반 `/* */` block_comment 는 skip. `tests/test_javadoc_rule_extractor.py` 23/23 PASS (TestBasic 3 + TestClassLevelBullets 4 + TestMethodLevel 4 + TestSeverity 3 + TestMetadata 3 + TestSlabSample 4 + TestExtractorClassAPI 2). **Slab 실증** : WeightMaximizer 7 rules (목적식 + 제약 체인) / EquipmentConstraintChecker 7 rules (4 class-level bullets + 3 method-level) / Slab 1 rule (HARD Exception) / EquipmentProperties 0 rules (descriptive only) — **총 15 BusinessRule + 15 VALIDATES**. 모델링 회귀 332/332 (E1-c 309 → +23). 전체 1541 PASS / 20 FAIL (전부 Section 1 baseline). RuleASTDiffer 입력 데이터 확보. **terms_ref 는 빈 list — C3 TermResolver 로 별도 채움**. (2026-04-25) |
| OD-11-E1-f | (CPA) `ConfigPropertiesAnalyzer` 11번째 Spring analyzer — `@ConfigurationProperties` → `config_property` entity + `has_config` 엣지 | E1-d | [x] | `backend/modeling/code_analysis/spring/config_properties_analyzer.py` 신규 (~190 LOC) + `spring/__init__.py` export. **3 어노테이션 형식 지원** : `@ConfigurationProperties(prefix="...")` keyword / `@ConfigurationProperties("...")` 단일 값 / `@ConfigurationProperties` 마커 (prefix=""). **Field 선택** : 비-static instance field 만 (constants 제외, final 허용 — 생성자 바인딩 호환). **Entity FQN** = `{prefix}.{fieldName}` (camelCase canonical). **attributes** : `prefix` / `key` (canonical) / `key_kebab` (Spring relaxed binding alias `_CAMEL_TO_KEBAB_RE = r"([a-z0-9])([A-Z])"`) / `field_name` / `field_type` / `default_value` (initializer literal text, 없으면 키 부재) / `bound_class_fqn` / `bound_field_fqn`. **Relation** : 기존 등록 `has_config` 사용 (parser_protocol L169). `tests/test_spring_config_properties_analyzer.py` 27/27 PASS (TestAnnotationForms 5 + TestFieldSelection 4 + TestAttributes 6 + TestHasConfigEdge 4 + TestKebabCaseEdgeCases 2 + TestSlabSample 4 + TestProtocol 2). **Slab 실증** : 11-analyzer 일괄 적용 시 90→**95 entities** (+5) / 172→**177 relations** (+5). EquipmentProperties 의 5 instance field 모두 `config_property` 로 승격 (`slab.equipment.maxThicknessMm` `default=240.0` `kebab=slab.equipment.max-thickness-mm` 등) + `has_config` 5 엣지 (source=`com.ontong.slab.config.EquipmentProperties`). 모델링 코드 분석 회귀 359/359 (E1-d 332 → +27). 전체 1568 PASS / 20 FAIL (전부 Section 1 baseline). **CONFLICTS_WITH gap 감지** : 매뉴얼 "두께 250mm 이상 허용" ↔ `slab.equipment.maxThicknessMm.default_value=240.0` 직접 비교 가능. **runtime wiring** : backend/main.py 미등록 (Phase E 코드 분석 파이프라인 wiring 시 11 analyzer 모두 함께 합류 예정). (2026-04-25) |
| OD-11-E1-g | (RR) `RuleRegistry` 신규 + `GapScanner.rule_source` auto-pull (D3-3 미수거 1/3) | E1-f | [x] | `backend/modeling/gap_detection/rule_registry.py` 신규 (~110 LOC) : `RuleRegistry` Protocol + `InMemoryRuleRegistry` (`dict[repo_id, dict[rule_fqn, BusinessRule]]` 내부 구조, `(repo_id, rule_fqn)` 복합 키 idempotent upsert) + `seed_rules_from_repo(path, repo_id, registry, parser=None)` convenience (`SeedResult(total_files_scanned, total_rules, errors)`) — `JavadocRuleExtractor` 활용 .java 자동 인제스트, FQN 결정성 덕에 두 번 돌려도 idempotent. `gap_detection/__init__.py` export 추가 (4종). **`GapScanner` 확장** : `rule_source: Optional[RuleRegistry]` 필드 + `_resolve_rules(business_rules, repo_id)` (fragments 패턴 답습 — `None` → auto-pull, 명시 list/[] → 그대로). `business_rules` 시그니처 `Iterable=()` → `Optional[Iterable]=None` 변경. **`gaps_api.ScanRequest`** : `rules: list[BusinessRule] = Field(default_factory=list)` → `rules: list[BusinessRule] | None = None` (`fragments` 와 동일 정책, body 미지정 시 auto-pull). **`backend/main.py` lifespan** : `InMemoryRuleRegistry()` 인스턴스 생성 + `GapScanner(rule_source=_rule_registry)` 주입. `tests/test_rule_registry.py` 16/16 PASS (TestProtocol 1 + TestBasic 5 + TestIdempotency 1 + TestMultiRepoIsolation 2 + TestSeeder 4 + TestScannerIntegration 2 — 명시 [] 는 auto-pull 차단 검증 포함). 모델링 gap 회귀 138/138 (rule+gap+manual 범위). 전체 1584 PASS / 20 FAIL (전부 Section 1 baseline). **End-to-end demo** : Slab repo 11 java files → 16 BusinessRule seed → `scanner.scan(business_rules=None)` 로 errors=0 정상 수행. main.py 156 routes 그대로 (API 신규 없음 — body 형식만 격상). **운영 시드 메커니즘** : `seed_rules_from_repo` 는 Python 함수로 노출만, 자동 startup seeding 안 함 (어떤 repo 를 어디서 가져올지 의견 분리 — REPL/스크립트/향후 API 로 호출). (2026-04-25) |
| OD-11-E1-h | (SSE) `gaps_api.scan_stream` 진짜 stage-by-stage streaming 재설계 (D3-3 미수거 2/3) | E1-g | [x] | `backend/modeling/api/gaps_api.py` `scan_stream_endpoint` 재구현 — 기존 buffered-flush PoC (전체 scan 종료 후 stages 일괄 emit) 제거, **`asyncio.Queue` + `loop.call_soon_threadsafe(queue.put_nowait, ...)` 패턴**으로 worker thread → main loop 안전 전달. `_on_progress` 콜백이 stage 받자마자 main loop queue 에 push, async generator 가 await queue.get() 으로 drain → 클라이언트 SSE 실시간 yield. **STAGE_COMPLETE 처리** : 콜백에서 suppress (그 시점에 result 없음), scan 정상 반환 후 `(STAGE_COMPLETE, payload)` 별도 push. **에러 surfacing** : worker 예외 시 `("error", {"detail": "{ExcType}: {msg}"})` SSE event emit, complete 안 보냄, except + finally + sentinel `None` 으로 generator 정상 종료. **fire-and-forget worker** : `asyncio.create_task(asyncio.to_thread(_sync_scan))` (await 하면 buffered 됨). `tests/test_gaps_api.py` 신규 3 케이스 추가 — `test_scan_stream_pattern_pushes_stages_via_threadsafe_queue` (worker thread + 진짜 asyncio.Queue + threading.Event gate 로 패턴 자체 검증, gate 5초 timeout 으로 buffered 리그레션 차단) + `test_scan_stream_emits_complete_event_with_payload` (complete event 가 라벨 아닌 UnifiedScanResponse JSON payload 담음) + `test_scan_stream_propagates_scan_exception` (RuntimeError → "error" event 후 generator 정상 종료, complete 안 옴). **TestClient ASGITransport 한계 메모** : 신규 테스트가 패턴 검증으로 우회 — ASGITransport 가 SSE chunks 를 버퍼링해 E2E 실시간 검증이 sync TestClient 에서는 불가. 실 uvicorn 데모는 demo_guide_modeling.md 시나리오로. `tests/test_gaps_api.py` 15/15 PASS (기존 12 + 신규 3). 모델링 gap+rule+manual 회귀 141/141. 전체 1587 PASS / 20 FAIL (전부 Section 1 baseline). **D3-3 미수거 2/3 완결**. (2026-04-25) |
| OD-11-E1-i | (EV) `GapCandidate.evidence` + `POST /gaps/{id}/reevaluate` + GapQueue evidence panel + 재평가 버튼 (D3-3 미수거 3/3) | E1-h | [x] | **백엔드** : `gap_models.py` `GapCandidate` 에 `evidence: dict[str, object] = field(default_factory=dict)` 추가 (frozen dataclass). `RuleASTDiffer._make_candidate` / `CosineDrifter._make_candidate` / `HierarchicalGapEngine._apply_llm` / `LLMOnlyGapEngine` 각자 stage 별 evidence 채움 (rule_statement / fragment_text / mismatch / cosine / cutoff / llm_reasoning / llm_severity 등). `gaps_api.GapCandidateDTO` 에 evidence 필드 노출. **신규 엔드포인트** `POST /api/modeling/gaps/{gap_id}/reevaluate` (~75 LOC) : evidence 의 rule_statement + fragment_text 로 stub `BusinessRule` + `ManualFragment` 재구성 → comparator.compare() 직접 호출 → severity + reasoning 갱신, evidence 에 `llm_reasoning`/`llm_severity` 추가, store.upsert. **에러 핸들링 우선순위 404→422→503** : gap 없음 404 / MISSING_IN gap (direction != None) 422 / comparator 미설정 503 / evidence 누락 500. **`gaps_api.init()` 시그니처 확장** : `llm_comparator: LLMComparator | None` 추가 (D3-2-b 의 PydanticAILLMComparator 인스턴스 직결). `backend/main.py` lifespan 에서 `_llm_comparator` 를 `gaps_api.init` 에 그대로 패스. **프런트** : `modeling.ts` `GapCandidateDto` 인터페이스를 백엔드와 1:1 맞춤 (기존 `gap_id`/`gap_type`/`confidence` 가짜 필드 제거 → `id`/`detected_by`/`gap_mode` 정정, `direction: GapDirection | null` 으로 conflicts null 허용, `evidence: Record<string, unknown>` 추가). `reevaluateGap(gapId)` 함수 신규. `GapQueue.tsx` : (i) 행 좌측 토글 컬럼 (▸/▾) 추가 — evidence 있으면 펼치기 가능. (ii) 펼친 행 아래 evidence panel `<pre>` JSON pretty-print (minimal — 사용자 정책 "최소 침습"). (iii) CONFLICTS_WITH 행 (direction === null) 에만 "재평가" 버튼 (Sparkles 아이콘) — `reevaluateGap()` 호출 후 in-place 갱신. (iv) 모든 `g.gap_id` 사용처를 `g.id` 로 정정 (기존 인터페이스 가짜 필드였던 잔재 제거). **TDD 신규 5 케이스** : `test_scan_response_includes_evidence_for_conflicts` / `test_reevaluate_unknown_gap_returns_404` / `test_reevaluate_missing_in_gap_returns_422` / `test_reevaluate_without_comparator_returns_503` / `test_reevaluate_calls_comparator_and_updates_gap` (StubComparator + 즉시 store 갱신 확인). `tests/test_gaps_api.py` 20/20 PASS (기존 15 + 신규 5). 모델링 gap+rule+manual 회귀 146/146. 전체 1592 PASS / 20 FAIL (Section 1 baseline). main.py 157 routes (+1). TS GapQueue/modeling.ts clean (기존 orphan ManualOntologyBuilder/ManualUpload 사전 에러는 무관). **D3-3 미수거 3/3 완결 — D3-3 인프라 100% 종결**. (2026-04-25) |
| OD-11-E1-j | (A1) `scripts/dump_entities_snapshot.py` — JavaParser 11-analyzer 결과 JSON 스냅샷 | E1-i | [x] | `scripts/dump_entities_snapshot.py` 신규 (~140 LOC) — argparse `--repo` / `--out` / `--repo-id` (기본값 Slab), `_build_parser()` 11-analyzer 일괄 구성, `dump_snapshot(repo_path, repo_id)` Java rglob → ParseResult → `asdict` 직렬화 → `{metadata: {repo_id, repo_path, generated_at, analyzers, totals}, files: {<rel-path>: {language, errors, entities, relations}}}` 스키마. **파일 경로 키 = repo_path 기준 상대경로** (다른 머신에서도 안정적). `tests/test_dump_entities_snapshot.py` 8/8 PASS — `_build_parser` 11 analyzer 구성 / 스냅샷 스키마 (top-level keys, metadata fields, 파일 키 절대경로 금지, entities/relations list, config_property 5개 + maxThicknessMm default 240.0 + kebab alias 보존) / JSON serialization round-trip / tmp_path 파일 작성. **Slab 실행** : `11 files / 95 entities / 177 relations / 0 errors` — E1-f 검증과 동일 (회귀 baseline). 출력 파일 `sample-repos/slab-design-engine/.analyzed/entities.json` (~114KB). **`.gitignore`** 에 `**/.analyzed/` 추가 — regenerable artifact, parser 변경 시 재실행. 전체 1600 PASS / 20 FAIL (전부 Section 1 baseline). 데모 코드 도착 후에도 같은 스크립트 그대로 실행해 비교 자료로 활용. (2026-04-25) |

### Phase E — 통합 검증 (1 도메인 PoC)

| # | Task | 의존 | 상태 | 산출물 |
|---|------|------|------|--------|
| OD-11-E1 | 1 도메인 선택 + Spring 샘플 프로젝트 준비 | Phase D | [ ] | `sample-repos/` |
| OD-11-E2 | Impact Analysis 시나리오 검증 | E1 | [ ] | 검증 리포트 |
| OD-11-E3 | Reverse Lookup 시나리오 검증 | E1 | [ ] | 검증 리포트 |
| OD-11-E4 | Test Generation 시나리오 검증 | E1 | [ ] | 검증 리포트 |

**완료 기준**: 3대 기능 모두 1 도메인에서 end-to-end 동작 + 설계가 전체 레거시 커버 가능.

---

## 의존 관계 범례

```
→  : 선행 Task 완료 후 착수 가능
//  : 병렬 진행 가능
⚠️ : 백엔드 미구현 — 프론트엔드보다 먼저 작업 필요
```

---

## Step 0: 프론트엔드 환경 세팅

| # | Task | 의존 | 시간 | 상태 | 산출물 |
|---|------|------|------|------|--------|
| 0-1 | Next.js 프로젝트 초기화 (Next.js 15 + Node 20 via nvm) | - | 10m | [x] | `frontend/` |
| 0-2 | shadcn/ui 설치 + 컴포넌트 추가 (Command, Badge, Button, Select, DropdownMenu, Popover, Dialog, Sonner) | 0-1 | 15m | [x] | `components/ui/` |
| 0-3 | Zustand, @dnd-kit/core, @dnd-kit/sortable 설치 | 0-1 | 5m | [x] | `package.json` |
| 0-4 | Next.js → 백엔드 API 프록시 설정 (`next.config.ts` rewrites → `localhost:8001`) | 0-1 | 10m | [x] | `next.config.ts` |
| 0-5 | 공통 TypeScript 타입 정의 — 백엔드 `schemas.py`와 1:1 매칭 | 0-1 | 20m | [x] | `src/types/` |

**완료 기준**: `npm run dev` → 빈 앱 기동 + `curl localhost:3000/api/wiki/tree`가 백엔드 JSON 반환

---

## Step 1-A: Tab Workspace 기반 레이아웃

| # | Task | 의존 | 시간 | 상태 | 산출물 |
|---|------|------|------|------|--------|
| 1A-1 | 3-Pane 메인 레이아웃 (TreeNav \| Workspace \| AICopilot) — 리사이즈 가능 패널 | Step 0 | 40m | [x] | `app/page.tsx` |
| 1A-2 | Zustand 탭 상태 스토어 (`openTab`, `closeTab`, `setActiveTab`, `reorderTabs`) | Step 0 | 30m | [x] | `lib/workspace/useWorkspaceStore.ts` |
| 1A-3 | TabBar 컴포넌트 (열기/닫기, ● dirty, 드래그 정렬 @dnd-kit) | 1A-2 | 40m | [x] | `components/workspace/TabBar.tsx` |
| 1A-4 | WorkspacePanel 컴포넌트 (활성 탭 콘텐츠 렌더링 + 빈 상태) | 1A-2 | 20m | [x] | `components/workspace/WorkspacePanel.tsx` |
| 1A-5 | FileRouter 컴포넌트 (확장자 기반 분기 — MD만 실제, 나머지 placeholder) | 1A-4 | 20m | [x] | `components/workspace/FileRouter.tsx` |
| 1A-6 | TreeNav 컴포넌트 (`GET /api/wiki/tree` → 트리 렌더링 → 클릭 시 탭 열기) | 1A-1, 1A-2 | 40m | [x] | `components/TreeNav.tsx` |
| 1A-7 | TreeNav 파일 생성 (+ 버튼 → 인라인 파일명 입력 → PUT API → 트리 새로고침 + 탭 열기) | 1A-6 | 30m | [x] | `components/TreeNav.tsx` |
| 1A-8 | TreeNav 파일 삭제 (우클릭 컨텍스트 메뉴 → DELETE API → 트리 새로고침 + 탭 닫기) | 1A-6 | 30m | [x] | `components/TreeNav.tsx` |
| 1A-9 | TreeNav 새로고침 버튼 | 1A-6 | 5m | [x] | `components/TreeNav.tsx` |
| 1A-10 | 폴더 생성 (헤더 버튼 + 폴더 우클릭 → 새 폴더, 백엔드 POST /api/wiki/folder API 포함) | 1A-6 | 40m | [x] | `TreeNav.tsx`, `wiki.py`, `local_fs.py` |
| 1A-11 | 폴더 삭제 (우클릭 → 삭제, 빈 폴더만 허용, 백엔드 DELETE /api/wiki/folder API 포함) | 1A-6 | 30m | [x] | `TreeNav.tsx`, `wiki.py`, `local_fs.py` |
| 1A-12 | 폴더 내 파일/하위폴더 생성 (폴더 우클릭 → 새 문서/새 폴더, 인라인 입력) | 1A-10 | 20m | [x] | `TreeNav.tsx` |
| 1A-13 | 드래그앤드롭 이동 (@dnd-kit, DragOverlay, RootDropZone, 폴더 hover 자동 확장) | 1A-6 | 60m | [x] | `TreeNav.tsx` |
| 1A-14 | 이름 변경 (우클릭 → InlineInput 인라인 편집, .md 자동 추가, 열린 탭 경로 업데이트) | 1A-6 | 30m | [x] | `TreeNav.tsx`, `useWorkspaceStore.ts` |

**완료 기준**: Tree 파일 클릭 → 탭 생성 → 탭 전환 → 탭 닫기 → 빈 상태 표시

---

## Step 1-B: Markdown Editor (Tiptap)

| # | Task | 의존 | 시간 | 상태 | 산출물 |
|---|------|------|------|------|--------|
| 1B-1 | Tiptap 패키지 설치 (`@tiptap/react`, `starter-kit`, table, image, task-list, placeholder) | Step 0 | 10m | [x] | `package.json` |
| 1B-2 | MarkdownEditor 기본 — Tiptap + StarterKit + TableKit + Image + TaskList | 1B-1, 1A-5 | 60m | [x] | `editors/MarkdownEditor.tsx` |
| 1B-3 | WYSIWYG ↔ 소스 모드 토글 | 1B-2 | 40m | [x] | MarkdownEditor 내 |
| 1B-4 | 슬래시 명령어 (`/`) 커스텀 extension — 빈 줄 시작에서만 트리거, Escape 닫기 | 1B-2 | 60m | [x] | `lib/tiptap/slashCommand.ts` |
| 1B-5 | 저장: debounce 자동 저장 + Ctrl+S → `PUT /api/wiki/{path}` | 1B-2 | 30m | [x] | MarkdownEditor 내 |
| 1B-6 | 파일 열기: 탭 활성화 시 `GET /api/wiki/file/{path}` → 에디터 로드 | 1B-2 | 20m | [x] | MarkdownEditor 내 |

**완료 기준**: `.md` 클릭 → 에디터 로드 → WYSIWYG 편집 → Ctrl+S 저장 → 새로고침 후 유지 확인

---

## Step 1-C: 클립보드 붙여넣기

> ⚠️ **1C-5 (백엔드)를 먼저 구현해야** 1C-3, 1C-4 (프론트엔드 이미지 붙여넣기)를 테스트할 수 있음

| # | Task | 의존 | 시간 | 상태 | 산출물 |
|---|------|------|------|------|--------|
| 1C-5 | ⚠️ 백엔드: `POST /api/files/upload/image` + `main.py` 라우터 등록 (wiki/assets/에 저장, 경로 반환) | - | 40m | [x] | `backend/api/files.py`, `main.py` |
| 1C-1 | HTML 테이블 → Tiptap Table 노드 변환 유틸 | 1B-2 | 30m | [x] | `lib/clipboard/tableConverter.ts` |
| 1C-2 | Tiptap paste handler: `text/html` 테이블 감지 시 Table 노드 삽입 | 1C-1 | 30m | [x] | `lib/tiptap/pasteHandler.ts` |
| 1C-3 | 이미지 붙여넣기: `image/*` blob → `POST /api/files/upload/image` → `![](path)` | **1C-5** → 1B-2 | 40m | [x] | `lib/clipboard/imagePaste.ts` |
| 1C-4 | 이미지 드래그 앤 드롭 (동일 업로드 흐름) | **1C-5** → 1B-2 | 20m | [x] | MarkdownEditor 내 |

**완료 기준**: Excel 표 복사→붙여넣기→테이블 생성 / 스크린샷 Ctrl+V→이미지 업로드+삽입

---

## Step 1-D: Multi-Format 뷰어

> ⚠️ **1D-1, 1D-2 (백엔드)를 먼저 구현해야** 프론트엔드 뷰어를 테스트할 수 있음
> 💡 **MVP 전략**: Phase 1에서는 **Excel(읽기+수정) + 이미지 뷰어**를 우선 구현.
> PPT, PDF는 Phase 1.5로 분리 가능 (데모 영향 낮음).

| # | Task | 의존 | 시간 | 우선순위 | 상태 | 산출물 |
|---|------|------|------|----------|------|--------|
| 1D-1 | ⚠️ 백엔드: `GET /api/files/{path}` (바이너리 반환 + Content-Type) | 1C-5 (files.py 공유) | 30m | P1 | [x] | `backend/api/files.py` |
| 1D-2 | ⚠️ 백엔드: `PUT /api/files/{path}` (바이너리 저장, `.md` 거부) | 1D-1 | 20m | P1 | [x] | `backend/api/files.py` |
| 1D-3 | SpreadsheetViewer: Luckysheet/Univer + SheetJS `.xlsx` ↔ JSON | 1D-1 | 120m | P1 | [x] | `editors/SpreadsheetViewer.tsx` |
| 1D-4 | SpreadsheetViewer: 수정 후 저장 (`PUT /api/files/{path}`) | 1D-1, 1D-2, 1D-3 | 40m | P1 | [x] | SpreadsheetViewer 내 |
| 1D-7 | ImageViewer: `<img>` + 줌/패닝 | 1D-1 | 30m | P1 | [x] | `editors/ImageViewer.tsx` |
| 1D-5 | PresentationViewer: 백엔드 python-pptx JSON 파싱 + 프론트 HTML 렌더링 (슬라이드 네비게이션, 키보드 조작, Bold/Italic/Color/Image 지원) | 1D-1 | 60m | P1.5 | [x] | `editors/PresentationViewer.tsx`, `api/files.py` |
| 1D-6 | PdfViewer: react-pdf (페이지 네비게이션, 줌, 50페이지 이상 시 페이지네이션) | 1D-1 | 60m | P1.5 | [x] | `editors/PdfViewer.tsx` |
| 1D-8 | FileRouter placeholder 제거 → 실제 뷰어 연결 | 1D-3~7 | 15m | P1 | [x] | FileRouter.tsx |

**P1 완료 기준**: `.xlsx` 열기+수정+저장, 이미지 줌/패닝
**P1.5 완료 기준**: `.pptx` 슬라이드 보기, `.pdf` 페이지 넘기기

---

## Step 1-E: Metadata Tagging Pipeline

> ⚠️ **백엔드 Task는 반드시 순서대로 (직렬)** 진행해야 함.
> 프론트엔드 Task는 백엔드 완료 후 착수.

### 1-E 백엔드 (직렬 — B1 → B2 → B3 → B4 → B5 → B6 → B7 → B8 → B9)

| # | Task | 의존 | 시간 | 상태 | 산출물 |
|---|------|------|------|------|--------|
| 1E-B1 | `schemas.py`: `DocumentMetadata` 추가, `WikiFile`에 `metadata` + `raw_content` 필드 추가, `tags` property 호환 | - | 30m | [x] | `backend/core/schemas.py` |
| 1E-B2 | `local_fs.py`: `_parse_frontmatter()` 추가, `_to_wiki_file()`에서 YAML 파싱 → `WikiFile.metadata`, 기존 `#tag` 폴백 | **→ 1E-B1** | 40m | [x] | `backend/infrastructure/storage/local_fs.py` |
| 1E-B3 | `wiki_indexer.py`: `_metadata_to_chroma()` (파이프 구분자), `index_file()`에서 metadata 포함 | **→ 1E-B2** | 30m | [x] | `backend/application/wiki/wiki_indexer.py` |
| 1E-B4 | `chroma.py`: `query_with_filter(where=)` 메서드 추가 | **→ 1E-B3** | 20m | [x] | `backend/infrastructure/vectordb/chroma.py` |
| 1E-B5 | `rag_agent.py`: `metadata_filter` 파라미터 + `query_with_filter()` 사용 | **→ 1E-B4** | 20m | [x] | `backend/application/agent/rag_agent.py` |
| 1E-B6 | `metadata.py` 신규 + `main.py` 라우터 등록: `GET /api/metadata/tags` (전체 고유 목록) | **→ 1E-B2** | 40m | [x] | `backend/api/metadata.py`, `main.py` |
| 1E-B7 | `application/metadata/` 디렉토리 + `metadata_service.py`: LLM Auto-Tag (`suggest_metadata()`) | **→ 1E-B1** | 40m | [x] | `backend/application/metadata/metadata_service.py` |
| 1E-B8 | `metadata.py`에 `POST /api/metadata/suggest` 엔드포인트 추가 | **→ 1E-B7** | 20m | [x] | `backend/api/metadata.py` |
| 1E-B9 | 기존 `WikiSearchService.build_tag_index()`가 새 `WikiFile.tags` property로 정상 동작하는지 검증 | **→ 1E-B1** | 15m | [x] | 테스트 결과 |

### 1-E 프론트엔드 (백엔드 B1~B8 완료 후)

| # | Task | 의존 | 시간 | 상태 | 산출물 |
|---|------|------|------|------|--------|
| 1E-F1 | MetadataTagBar 컨테이너 (에디터 상단, 열기/접기, `.md` 파일만 표시) | **1E-B6 완료** + 1B-2 | 40m | [x] | `editors/metadata/MetadataTagBar.tsx` |
| 1E-F2 | TagInput (shadcn Command + Badge, 자동 완성 + 새 태그 생성) | 1E-F1 | 40m | [x] | `editors/metadata/TagInput.tsx` |
| 1E-F3 | DomainSelect / ProcessSelect (`GET /api/metadata/tags` 로드) | 1E-F1 | 30m | [x] | `editors/metadata/DomainSelect.tsx` |
| 1E-F4 | AutoTagButton (✨ → `POST /api/metadata/suggest` → 점선 Badge → 수락/거절) | **1E-B8 완료** + 1E-F1, 1E-F2 | 50m | [x] | `editors/metadata/AutoTagButton.tsx` |
| 1E-F5 | Frontmatter 동기화 유틸 (serialize / strip / merge) | 1E-F1 | 30m | [x] | `lib/markdown/frontmatterSync.ts` |
| 1E-F6 | MarkdownEditor + MetadataTagBar 통합 (열기 시 역직렬화, 저장 시 직렬화) | 1E-F1~F5 | 30m | [x] | MarkdownEditor.tsx 수정 |

**완료 기준**: MD 열기 → TagBar에 메타데이터 표시 → Auto-Tag → 수락 → 저장 → ChromaDB 반영

---

## Step 1-F: AI Copilot + SSE 스트리밍

> ⚠️ **1F-0 (백엔드)를 먼저 구현해야** 1F-5 (승인/거절)를 테스트할 수 있음

| # | Task | 의존 | 시간 | 상태 | 산출물 |
|---|------|------|------|------|--------|
| 1F-0 | ⚠️ 백엔드: RAGAgent에 Wiki 수정 요청 감지 → `ApprovalRequestEvent` 발행 로직 추가 | - | 60m | [x] | `backend/application/agent/rag_agent.py` |
| 1F-1 | SSE 클라이언트 (`fetch` + `ReadableStream`, 이벤트 타입별 파싱) | Step 0 | 40m | [x] | `lib/api/sseClient.ts` |
| 1F-2 | AICopilot 채팅 UI (메시지 목록 + 입력 + 자동 스크롤) | 1A-1, 1F-1 | 50m | [x] | `components/AICopilot.tsx` |
| 1F-3 | 스트리밍 토큰 실시간 표시 (`content_delta` 처리) | 1F-2 | 20m | [x] | AICopilot 내 |
| 1F-4 | 출처 표시 (`sources` → 파일 경로 링크, 클릭 시 탭 열기) | 1F-2, 1A-2 | 30m | [x] | AICopilot 내 |
| 1F-5 | 승인/거절 UI (`approval_request` → diff 미리보기 + 버튼 → `POST /api/approval/resolve`) | **1F-0 완료** + 1F-2 | 40m | [x] | AICopilot 내 |
| 1F-6 | 에러 핸들링 (`error` 이벤트 → Sonner Toast, 서버 다운 시 재연결 안내) | 1F-2 | 15m | [x] | AICopilot 내 |
| 1F-7 | RAG 명확화 질문 (모호한 질문 시 검색 결과 기반 되물어보기 + 멀티턴 히스토리) | 1F-0 | 60m | [x] | `rag_agent.py`, `agent.py` |
| 1F-8 | 출처 관련도 필터링 (MIN_SOURCE_RELEVANCE 기반, 명확화/답변 시 threshold 분리) | 1F-4 | 30m | [x] | `rag_agent.py` |
| 1F-9 | 에이전트 세션 관리 (새 대화, 세션 목록, 전환, 삭제, 자동 제목) | 1F-2 | 60m | [x] | `AICopilot.tsx` |

**완료 기준**: 채팅 → 스트리밍 답변 + 출처 → "Wiki에 추가해줘" → 승인/거절 동작

---

## Step 4: 샘플 데이터 마이그레이션 + 통합 테스트

| # | Task | 의존 | 시간 | 상태 | 산출물 |
|---|------|------|------|------|--------|
| 4-1 | `wiki/getting-started.md`에 YAML frontmatter 추가 (`#tag` → frontmatter 이전) | 1E-B2 완료 | 15m | [x] | wiki 파일 |
| 4-2 | `wiki/order-processing-rules.md`에 YAML frontmatter 추가 | 4-1 | 15m | [x] | wiki 파일 |
| 4-3 | `wiki/kv-cache-troubleshoot.md`에 YAML frontmatter 추가 | 4-1 | 15m | [x] | wiki 파일 |
| 4-4 | `POST /api/wiki/reindex` → ChromaDB metadata 포함 여부 확인 | 4-1~3 | 15m | [x] | 테스트 결과 |
| 4-5 | E2E: TreeNav→탭→MD 편집→저장→AI 채팅→RAG 답변→출처 | 1A~1F 전체 | 30m | [x] | 테스트 결과 |
| 4-6 | E2E: Auto-Tag→추천→수락→저장→Hybrid Search 필터 검증 | 1E 전체 | 20m | [x] | 테스트 결과 |
| 4-7 | E2E: Excel 열기/수정/저장, (P1.5: PPT 뷰어, PDF 뷰어) | 1D 전체 | 20m | [x] | 테스트 결과 |
| 4-8 | E2E: 이미지 붙여넣기, 엑셀 표 붙여넣기 | 1C 전체 | 15m | [x] | 테스트 결과 |

**완료 기준**: Phase 1 데모 시나리오 전체 통과

---

## Ad-hoc: UI/인프라 개선

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| AH-1 | 사이드바 빈 공간 우클릭 → 루트 컨텍스트 메뉴 (새 문서/새 폴더) | [x] | `TreeNav.tsx` |
| AH-2 | 인증 추상화 레이어 — Backend (User, AuthProvider, NoOpProvider, deps) | [x] | `backend/core/auth/` |
| AH-3 | 인증 추상화 레이어 — 전체 API 라우터에 auth dependency 적용 | [x] | `backend/api/*.py` |
| AH-4 | 인증 추상화 레이어 — Frontend (AuthContext, useAuth, DevProvider, Providers) | [x] | `frontend/src/lib/auth/`, `Providers.tsx` |
| AH-5 | 문서 메타데이터 이력 — Backend (created/updated/created_by/updated_by 자동 주입) | [x] | `schemas.py`, `local_fs.py`, `wiki_service.py`, `wiki.py`, `approval.py` |
| AH-6 | 문서 메타데이터 이력 — ChromaDB indexer 필드 반영 | [x] | `wiki_indexer.py` |
| AH-7 | 문서 메타데이터 이력 — Frontend 타입/파서/MetadataTagBar 이력 표시 | [x] | `wiki.ts`, `frontmatterSync.ts`, `MetadataTagBar.tsx` |
| AH-8 | AI Copilot 마크다운 렌더링 (react-markdown + remark-gfm) | [x] | `AICopilot.tsx` |
| AH-9 | 저장 후 metadata 갱신 버그 수정 (서버 응답 반영) | [x] | `MarkdownEditor.tsx` |
| AH-10 | 에이전트 라우팅 고도화 — 일반 검색/질문 패턴 WIKI_QA 라우팅 | [x] | `router.py` |
| AH-11 | 에이전트 라우팅 고도화 — LLM classifier WIKI_QA 기본 폴백 | [x] | `router.py` |
| AH-12 | RAG 시스템 프롬프트 범용화 (인사/조직 등 일반 Wiki 지원) | [x] | `rag_agent.py` |
| AH-13 | Clarity check 조건 완화 (짧은 질문 과도한 명확화 방지) | [x] | `rag_agent.py` |
| AH-14 | 대화 히스토리 기반 검색 쿼리 보강 (follow-up 컨텍스트 반영) | [x] | `rag_agent.py` |
| AH-15 | RAG 시스템 프롬프트 구조화 데이터 추출 강화 (인사정보 등) | [x] | `rag_agent.py` |
| AH-16 | 검색 범위 확대 (n_results 5→8) + 관련성 임계값 조정 (0.4→0.3) | [x] | `rag_agent.py` |
| AH-17 | 짧은 문서 인덱싱 품질 개선 (파일 경로 컨텍스트 추가) | [x] | `wiki_indexer.py` |
| AH-18 | 탐색 과정 시각화 — Backend thinking_step SSE 이벤트 | [x] | `schemas.py`, `rag_agent.py` |
| AH-19 | 탐색 과정 시각화 — Frontend ThinkingStepsDisplay 컴포넌트 | [x] | `AICopilot.tsx`, `sseClient.ts` |
| AH-20 | Self-Reflective Cognitive Pipeline — 의도분석→초안→자기검토→최종답변 | [x] | `rag_agent.py` |
| AH-21 | 페르소나 업그레이드 — 공감 IT 파트너 + Minto Pyramid + 실행 가능 다음 단계 | [x] | `rag_agent.py` |
| AH-22 | Cognitive Pipeline 백엔드 콘솔 로깅 (thought/draft/critique) | [x] | `rag_agent.py` |

---

## Phase 2: UI 고도화 + 메타데이터 관리

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P2-1 | 탭 시스템 확장 — VirtualTabType, openVirtualTab(), TabType 기반 라우팅 | [x] | `types/workspace.ts`, `useWorkspaceStore.ts`, `FileRouter.tsx` |
| P2-2 | 사이드바 3-섹션 전환 — 파일 트리 / 태그 브라우저 / 관리 | [x] | `TreeNav.tsx` |
| P2-3 | 백엔드 템플릿 CRUD API — JSON 파일 기반 저장/로드/항목 추가·삭제 | [x] | `api/metadata.py` |
| P2-4 | 메타데이터 템플릿 에디터 — Workspace 가상 탭, Domain/Process/Tags CRUD | [x] | `editors/MetadataTemplateEditor.tsx` |
| P2-5 | MetadataTagBar — 하드코딩 기본값 → 템플릿 API 동적 로드 | [x] | `metadata/MetadataTagBar.tsx` |
| P2-6 | 에러코드 자동 추출 — 저장 시 정규식 감지 → frontmatter 주입 | [x] | `wiki_service.py` |
| P2-7 | 태그 정규화 병합 제안 API | [x] | `api/metadata.py` |
| P2-8 | 태그 기반 사이드바 브라우저 — Domain/Process/Tags 계층 탐색 + 문서 필터 | [x] | `TreeNav.tsx`, `api/metadata.py` |
| P2-9 | 미태깅 문서 대시보드 — 목록 + 일괄 자동 태깅 + 태그 사용 통계 | [x] | `editors/UntaggedDashboard.tsx`, `api/metadata.py` |

---

## Phase 2-A: RAG 성능 고도화

> 문서 대량 증가 시 응답 속도 + 검색 품질 유지를 위한 최적화.
> 상세 설계: `toClaude/_shared/plan/master_plan.md` → Phase 2-A 섹션 참조.

### Step P2A-1: LLM 호출 병렬화 + 제거

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P2A-1-1 | 라우팅 + 쿼리보강 `asyncio.gather` 병렬화 | [x] | `agent.py`, `rag_agent.py` |
| P2A-1-2 | 명확화 확인 → 규칙 기반 전환 (LLM 제거) | [x] | `rag_agent.py` |
| P2A-1-3 | 라우팅 키워드 커버리지 확대 → LLM 폴백 빈도 최소화 | [x] | `router.py` |
| P2A-1-4 | RAG 파이프라인 지연시간 벤치마크 스크립트 | [x] | `tests/bench_rag_latency.py` |

### Step P2A-2: 하이브리드 검색 (벡터 + BM25)

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P2A-2-1 | BM25 인덱스 구축 (rank_bm25, 토큰화) | [x] | `infrastructure/search/bm25.py` |
| P2A-2-2 | RRF 병합 모듈 (벡터 + BM25 결과 융합) | [x] | `infrastructure/search/hybrid.py` |
| P2A-2-3 | RAG Agent → hybrid_search 교체 | [x] | `rag_agent.py` |
| P2A-2-4 | BM25 인덱스 자동 갱신 (문서 저장/삭제 동기화) | [x] | `wiki_indexer.py`, `bm25.py` |
| P2A-2-5 | 검색 품질 비교 테스트 | [x] | `tests/test_hybrid_search.py` |

### Step P2A-3: 증분 인덱싱

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P2A-3-1 | 파일 content hash 기반 변경 감지 | [x] | `infrastructure/storage/file_hash.py` |
| P2A-3-2 | index_file 시 해시 비교 → 변경 없으면 스킵 | [x] | `wiki_indexer.py` |
| P2A-3-3 | remove_file 개선 — metadata where 필터 기반 정확 삭제 | [x] | `wiki_indexer.py`, `chroma.py` |
| P2A-3-4 | reindex API에 force 파라미터 추가 | [x] | `wiki.py` |

### Step P2A-4: 임베딩/검색 캐싱

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P2A-4-1 | 쿼리 해시 LRU 캐시 (TTL 5분) | [x] | `infrastructure/cache/query_cache.py` |
| P2A-4-2 | RAG Agent에 캐시 히트 로직 추가 | [x] | `rag_agent.py` |
| P2A-4-3 | 문서 변경 시 캐시 무효화 | [x] | `wiki_indexer.py`, `query_cache.py` |
| P2A-4-4 | 캐시 히트율 모니터링 로그 | [x] | `query_cache.py` |

### Step P2A-5: 메타데이터 사전 필터링

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P2A-5-1 | 질문에서 domain/process 키워드 규칙 기반 추출 | [x] | `application/agent/filter_extractor.py` |
| P2A-5-2 | 추출 필터 → ChromaDB where 절 변환 | [x] | `rag_agent.py` |
| P2A-5-3 | 필터 0건 시 fallback (필터 제거 후 재검색) | [x] | `rag_agent.py` |
| P2A-5-4 | domain/process 사용 통계 캐싱 API | [x] | `filter_extractor.py` |

### Step P2A-6: Cross-encoder 리랭킹

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P2A-6-1 | Cross-encoder 래퍼 구현 | [x] | `infrastructure/search/reranker.py` |
| P2A-6-2 | RAG Agent에 리랭킹 단계 추가 | [x] | `rag_agent.py` |
| P2A-6-3 | 리랭킹 on/off 설정 + 지연 시간 로깅 | [x] | `config.py`, `reranker.py` |
| P2A-6-4 | A/B 비교 테스트 (리랭킹 유무) | [x] | `tests/test_reranker.py` |

---

## Phase 2-B: 문서 충돌 감지 & 해소

> 같은 주제 문서가 여러 개일 때 사용자가 올바른 판단을 할 수 있도록 가이드.
> 상세 설계: `toClaude/_shared/plan/master_plan.md` → Phase 2-B 섹션 참조.

### Step P2B-1: RAG 답변 충돌 감지 프롬프트

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P2B-1-1 | `_build_context_with_metadata()` — 각 문서 청크에 출처/작성자/수정일 헤더 삽입 | [x] | `rag_agent.py` |
| P2B-1-2 | `FINAL_ANSWER_SYSTEM_PROMPT` 충돌 감지 규칙 추가 — 문서 간 모순 시 경고 + 최신 문서 권고 | [x] | `rag_agent.py` |
| P2B-1-3 | `COGNITIVE_REFLECT_PROMPT` — self_critique에 문서 간 충돌 확인 항목 추가 | [x] | `rag_agent.py` |
| P2B-1-4 | 충돌 경고 SSE 이벤트 — `ConflictWarningEvent` 스키마 + 프론트엔드 경고 배너 | [x] | `schemas.py`, `agent.ts`, `AICopilot.tsx` |

### Step P2B-2: 메타데이터 기반 신뢰도 표시

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P2B-2-1 | `DocumentMetadata`에 `status` 필드 추가 (draft/review/approved/deprecated) + 파싱/직렬화 | [x] | `schemas.py`, `local_fs.py` |
| P2B-2-2 | ChromaDB 인덱서에 `status` 필드 반영 | [x] | `wiki_indexer.py` |
| P2B-2-3 | `SourceRef` 스키마 확장 — `updated`, `updated_by`, `status` 필드 + `_build_sources()` 주입 | [x] | `schemas.py`, `rag_agent.py` |
| P2B-2-4 | 프론트엔드 소스 패널 UI 개선 — 날짜 배지, 작성자, status 아이콘, "최신" 라벨 | [x] | `agent.ts`, `AICopilot.tsx` |
| P2B-2-5 | MetadataTagBar에 status 드롭다운 추가 | [x] | `wiki.ts`, `MetadataTagBar.tsx`, `frontmatterSync.ts` |

### Step P2B-3: 문서 중복/충돌 감지 대시보드

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P2B-3-1 | `ChromaWrapper.get_all_embeddings()` 메서드 추가 | [x] | `chroma.py` |
| P2B-3-2 | `ConflictDetectionService` — 문서별 임베딩 평균 → 코사인 유사도 → 클러스터링 | [x] | `conflict/conflict_service.py` |
| P2B-3-3 | `GET /api/conflict/duplicates` API — 유사 문서 쌍 목록 반환 | [x] | `api/conflict.py` |
| P2B-3-4 | `POST /api/conflict/deprecate` API — 문서 status를 deprecated로 변경 | [x] | `api/conflict.py` |
| P2B-3-5 | `ConflictDashboard` 프론트엔드 — VirtualTab, 유사 문서 테이블, 비교/폐기/병합 액션 | [x] | `ConflictDashboard.tsx`, `workspace.ts`, `FileRouter.tsx` |

### Step P2B-4: 인라인 비교 뷰 (Side-by-side diff)

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P2B-4-1 | `GET /api/wiki/compare` API — 두 문서 경로 → body + 메타데이터 반환 | [x] | `api/wiki.py` |
| P2B-4-2 | `DiffViewer` 컴포넌트 — line-by-line diff, 추가/삭제/변경 하이라이트 | [x] | `DiffViewer.tsx` |
| P2B-4-3 | VirtualTab 라우팅 — `"document-compare"` 탭 + `openCompareTab(pathA, pathB)` | [x] | `workspace.ts`, `useWorkspaceStore.ts`, `FileRouter.tsx` |
| P2B-4-4 | "이 문서가 최신" 버튼 — deprecated 자동 변경 + `superseded_by` 설정 | [x] | `DiffViewer.tsx`, `api/conflict.py` |
| P2B-4-5 | ConflictDashboard + RAG 답변에서 "비교" 액션 연동 | [x] | `ConflictDashboard.tsx`, `AICopilot.tsx` |

### Step P2B-5: 문서 계보(Lineage) 시스템

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P2B-5-1 | `DocumentMetadata`에 lineage 필드 추가 (`supersedes`, `superseded_by`, `related`) | [x] | `schemas.py`, `local_fs.py` |
| P2B-5-2 | RAG 검색 시 superseded 문서 패널티 + "새 버전 있음" 노트 | [x] | `wiki_indexer.py`, `rag_agent.py` |
| P2B-5-3 | `GET /api/wiki/lineage/{path}` API — 문서 계보 트리 반환 | [x] | `api/wiki.py` |
| P2B-5-4 | 프론트엔드 Lineage 위젯 — 이전/새 버전, 관련 문서 링크 표시 | [x] | `LineageWidget.tsx`, `MarkdownEditor.tsx` |
| P2B-5-5 | 저장 시 자동 lineage 제안 — 유사 문서 감지 시 "이 문서의 새 버전인가요?" 프롬프트 | [x] | `conflict_service.py`, `DiffViewer.tsx` |

### Step P2B-6: RAG deprecated 문서 필터링 + 최신 문서 자동 대체

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P2B-6-1 | RAG 검색에서 deprecated 문서 제외 (ChromaDB where 필터 + BM25 필터) | [x] | `rag_agent.py`, `chroma.py`, `bm25.py` |
| P2B-6-2 | deprecated만 검색된 경우 `superseded_by` 체인 추적 → 최신 문서 자동 대체 | [x] | `rag_agent.py`, `wiki_service.py` |
| P2B-6-3 | 기존 +0.3 패널티 로직 제거 (필터로 대체) + 소스 패널에 deprecated 노출 안 함 | [x] | `rag_agent.py` |

### Step P2B-7: 충돌 대시보드 해결 상태 관리

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P2B-7-1 | `DuplicatePair`에 `resolved` 필드 + 자동 해결 판정 (양방향 lineage 존재 시) | [x] | `conflict_service.py` |
| P2B-7-2 | API에 `filter` 파라미터 추가 (`unresolved` / `resolved` / `all`) | [x] | `api/conflict.py` |
| P2B-7-3 | 프론트엔드 대시보드에 탭 필터 (미해결 / 해결됨 / 전체), 기본값 "미해결" | [x] | `ConflictDashboard.tsx` |

---

## Phase 3-A: 문서 검색

> Ctrl+K 커맨드 팔레트 + MiniSearch 클라이언트 검색 + 서버 하이브리드 의미 검색
> 상세 설계: `.claude/plans/dazzling-orbiting-yeti.md` 참조.

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P3A-1 | MiniSearch 패키지 설치 | [x] | `package.json` |
| P3A-2 | 검색 zustand 스토어 — MiniSearch 인덱스 로드, 검색, 모드 전환 | [x] | `lib/search/useSearchStore.ts` |
| P3A-3 | 서버 사이드 하이브리드 검색 API — BM25+벡터 RRF 노출 | [x] | `backend/api/search.py`, `schemas.py` |
| P3A-4 | SearchCommandPalette 컴포넌트 — cmdk 기반, shouldFilter=false | [x] | `components/search/SearchCommandPalette.tsx` |
| P3A-5 | SearchResultItem — 제목 하이라이트, 경로, 스니펫, 태그 뱃지 | [x] | `components/search/SearchResultItem.tsx` |
| P3A-6 | 키보드 단축키 + 마운트 — Ctrl+K, page.tsx 마운트 | [x] | `app/page.tsx` |
| P3A-7 | TreeNav 검색 버튼 — 사이드바 헤더에 Search 아이콘 | [x] | `TreeNav.tsx` |

---

## Phase 3-B: 문서 관계 그래프

> react-force-graph-2d 기반 문서 연결 시각화, 양방향 탐색
> 상세 설계: `.claude/plans/dazzling-orbiting-yeti.md` 참조.

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P3B-1 | 그래프 데이터 API — 백링크+lineage+related 집계, BFS | [x] | `backend/api/search.py`, `schemas.py` |
| P3B-2 | 유사도 엣지 확장 — include_similar, ConflictDetectionService 연동 | [x] | `backend/api/search.py` |
| P3B-3 | Virtual Tab 등록 — `"document-graph"` 타입 | [x] | `workspace.ts`, `useWorkspaceStore.ts` |
| P3B-4 | 그래프 타입 정의 — GraphNode, GraphEdge, GraphData | [x] | `types/wiki.ts` |
| P3B-5 | react-force-graph 패키지 설치 | [x] | `package.json` |
| P3B-6 | DocumentGraph 핵심 컴포넌트 — ForceGraph2D + fetch + 툴바 | [x] | `editors/DocumentGraph.tsx` |
| P3B-7 | 노드 렌더링 — status별 색상, degree 기반 크기, 라벨 | [x] | `DocumentGraph.tsx` |
| P3B-8 | 엣지 렌더링 — 타입별 색상/스타일/화살표, 범례 | [x] | `DocumentGraph.tsx` |
| P3B-9 | 노드 클릭 네비게이션 — openTab + 우클릭 컨텍스트 메뉴 | [x] | `DocumentGraph.tsx` |
| P3B-10 | 현재 문서 중심 보기 — 열린 탭 기준 센터링 | [x] | `DocumentGraph.tsx` |
| P3B-11 | FileRouter 라우팅 — dynamic import | [x] | `FileRouter.tsx` |
| P3B-12 | TreeNav 진입점 — 관리 섹션에 그래프 메뉴 | [x] | `TreeNav.tsx` |
| P3B-13 | 노드 호버 툴팁 — 제목, 경로, status, 태그, 연결 수 | [x] | `DocumentGraph.tsx` |

### Ad-hoc: Phase 3 고도화

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P3-AH1 | 문서 열기 시 연결 문서 패널 (lineage+wikilink 백링크, 접이식) | [x] | `LinkedDocsPanel.tsx`, `MarkdownEditor.tsx` |
| P3-AH2 | 그래프 내 문서 검색 — 검색→노드 센터링+줌 | [x] | `DocumentGraph.tsx` |
| P3-AH5 | 문서 관계 그래프 검색 우선 리디자인 — 전체 그래프 대신 검색으로 중심 문서 선택, BFS 관계만 표시 | [x] | `DocumentGraph.tsx`, `search.py` |
| P3-AH3 | 문서 링크 복사 — 사이드바 우클릭 (md→`[[문서명]]`, 기타→경로) | [x] | `TreeNav.tsx` |
| P3-AH4 | WikiLink 인라인 노드 — `[[문서명]]` 입력/붙여넣기 시 클릭 가능한 링크 자동 변환, 클릭→openTab | [x] | `wikiLink.ts`, `pasteHandler.ts`, `markdown.ts`, `MarkdownEditor.tsx`, `globals.css` |

---

## 진행 요약

| Step | 내용 | Task 수 | 상태 |
|------|------|---------|------|
| Step 0 | 프론트엔드 환경 세팅 | 5 | ✅ 완료 |
| Step 1-A | Tab Workspace 레이아웃 | 14 | ✅ 완료 |
| Step 1-B | Tiptap MD 에디터 | 6 | ✅ 완료 |
| Step 1-C | 클립보드 붙여넣기 | 5 | ✅ 완료 |
| Step 1-D | Multi-Format 뷰어 (P1+P1.5) | 8 | ✅ 완료 |
| Step 1-E | Metadata Pipeline | 15 | ✅ 완료 |
| Step 1-F | AI Copilot + SSE | 9 | ✅ 완료 |
| Step 4 | 마이그레이션 + 통합 테스트 | 8 | ✅ 완료 |
| Ad-hoc | UI/인프라 개선 | 19 | ✅ 완료 |
| | **Phase 1 합계** | **89 tasks** | **✅ 완료** |
| | | | |
| Phase 2 | UI 고도화 + 메타데이터 관리 | 9 | ✅ 완료 |
| | | | |
| P2A-1 | LLM 호출 병렬화 + 제거 | 4 | ✅ 완료 |
| P2A-2 | 하이브리드 검색 (BM25) | 5 | ✅ 완료 |
| P2A-3 | 증분 인덱싱 | 4 | ✅ 완료 |
| P2A-4 | 임베딩/검색 캐싱 | 4 | ✅ 완료 |
| P2A-5 | 메타데이터 사전 필터링 | 4 | ✅ 완료 |
| P2A-6 | Cross-encoder 리랭킹 | 4 | ✅ 완료 |
| | **Phase 2-A 합계** | **25 tasks** | **✅ 완료** |
| | | | |
| P2B-1 | RAG 충돌 감지 프롬프트 | 4 | ✅ 완료 |
| P2B-2 | 메타데이터 신뢰도 표시 | 5 | ✅ 완료 |
| P2B-3 | 중복/충돌 감지 대시보드 | 5 | ✅ 완료 |
| P2B-4 | 인라인 비교 뷰 (diff) | 5 | ✅ 완료 |
| P2B-5 | 문서 계보 시스템 | 5 | ✅ 완료 |
| P2B-6 | RAG deprecated 필터 + 자동 대체 | 3 | ✅ 완료 |
| P2B-7 | 충돌 대시보드 해결 상태 관리 | 3 | ✅ 완료 |
| | **Phase 2-B 합계** | **30 tasks** | **✅ 완료** |
| | | | |
| P3A | 문서 검색 (커맨드 팔레트 + MiniSearch + 의미 검색) | 7 | ✅ 완료 |
| P3B | 문서 관계 그래프 (react-force-graph + 양방향 탐색) | 13 | ✅ 완료 |
| P3-AH | Phase 3 고도화 (연결 문서 패널, 그래프 검색, 링크 복사, WikiLink 노드, 그래프 검색 우선 UX) | 5 | ✅ 완료 |
| | **Phase 3 합계** | **24 tasks** | **✅ 완료** |
| | | | |
| P4A | 에어갭 대응 (외부 의존성 제거) | 5 | ✅ 완료 |
| P4B | Docker 컨테이너화 | 5 | ✅ 완료 |
| P4C | 스토리지 추상화 (NAS 대응) | 4 | ✅ 완료 |
| P4D | 편집 잠금 (동시 편집 방지) | 4 | ✅ 완료 |
| P4E | 권한 관리 (RBAC) | 7 | ✅ 완료 |
| P4F | 보안 강화 + 운영 안정성 | 5 | ✅ 완료 |
| P4G | 대규모 대응 (100명+, 수만 문서) | 4 | ✅ 완료 |
| | **Phase 4 합계** | **34 tasks** | **✅ 완료** |
| | | | |
| P5A | 프론트엔드 생존 (Lazy Tree + 서버 검색) | 4 | ✅ 완료 |
| P5B | 백엔드 동시성 + 비동기 인덱싱 | 7 | ✅ 완료 |
| P5C | Redis 기반 상태 공유 | 4 | ✅ 완료 |
| P5D | 수평 확장 + 리소스 운영 | 5 | ✅ 완료 |
| P5E | LLM 처리량 최적화 | 4 | ✅ 완료 |
| | **Phase 5 합계** | **24 tasks** | **✅ 완료** |
| | | | |
| CR-1 | ChromaDB 네이티브 유사도 검색 메서드 추가 | 2 | ✅ 완료 |
| CR-2 | ConflictStore 신규 (Redis + InMemory 이중 백엔드) | 1 | ✅ 완료 |
| CR-3 | ConflictService 리라이트 (incremental check_file) | 1 | ✅ 완료 |
| CR-4 | API 레이어 수정 (store 읽기 + full-scan 엔드포인트) | 1 | ✅ 완료 |
| CR-5 | WikiService 훅 연결 (save/delete/move) | 1 | ✅ 완료 |
| CR-6 | 프론트엔드 즉시 로드 + 전체 스캔 버튼 | 1 | ✅ 완료 |
| CR-7 | 테스트 작성 (Unit + E2E) | 4 | ✅ 완료 |
| | **충돌 감지 리팩토링 합계** | **11 tasks** | **✅ 완료** |
| | | | |
| SK-1 | Skill Protocol + SkillResult + SkillRegistry | 1 | ✅ 완료 |
| SK-2 | AgentContext (per-request, run_skill, emit_thinking, sse) | 1 | ✅ 완료 |
| SK-3 | 7개 스킬 추출 (query_augment, wiki_search, wiki_read, wiki_write, wiki_edit, llm_generate, conflict_check) | 7 | ✅ 완료 |
| SK-4 | ReAct loop + tool executor (tool_executor.py) | 1 | ✅ 완료 |
| SK-5 | RAGAgent 리팩토링 (skill 호출 전환, backward compat) | 1 | ✅ 완료 |
| SK-6 | main.py + api/agent.py wiring (skill 등록, AgentContext 생성) | 2 | ✅ 완료 |
| SK-7 | 기존 테스트 회귀 확인 (68/68 PASSED) | 1 | ✅ 완료 |
| | **Skill System 합계** | **14 tasks** | **✅ 완료** |

---

## Phase 4-A: 에어갭(Air-gap) 대응 — 외부 의존성 제거

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P4A-1 | PDF.js worker 로컬 번들링 — unpkg CDN → public/ 로컬 파일 | [x] | `PdfViewer.tsx`, `public/pdf.worker.min.mjs` |
| P4A-2 | Google Fonts 제거 — next/font/google → 시스템 폰트 스택 | [x] | `layout.tsx`, `globals.css` |
| P4A-3 | LLM 설정 추상화 — Ollama 로컬 모델 기본값, OpenAI는 옵션 | [x] | `config.py`, `.env.example` |
| P4A-4 | 임베딩 로컬 전환 — ChromaDB 기본 임베딩 함수 사용 | [x] | `chroma.py` |
| P4A-5 | 외부 의존성 점검 스크립트 — 빌드 산출물에 외부 URL 없는지 검증 | [x] | `scripts/check-external-deps.sh` |

## Phase 4-B: Docker 컨테이너화

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P4B-1 | Backend Dockerfile — Python 3.10-slim 멀티스테이지 빌드 | [x] | `Dockerfile.backend` |
| P4B-2 | Frontend Dockerfile — Node 20-alpine 멀티스테이지 (build→serve) | [x] | `frontend/Dockerfile` |
| P4B-3 | docker-compose.yml 통합 — backend + frontend + chromadb 추가 | [x] | `docker-compose.yml` |
| P4B-4 | 환경 변수 분리 — .env.example + docker-compose env_file 연동 | [x] | `.env.example`, `.env.production.example` |
| P4B-5 | 헬스체크 + 시작 순서 — depends_on + healthcheck | [x] | `docker-compose.yml`, `main.py` |

## Phase 4-C: 스토리지 추상화

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P4C-1 | StorageBackend ABC 정의 (이미 완료) | [x] | `storage/base.py` |
| P4C-2 | LocalFSBackend 구현 (이미 완료) | [x] | `storage/local_fs.py` |
| P4C-3 | NASBackend 구현 — 마운트 경로 기반 | [x] | `storage/nas_backend.py` |
| P4C-4 | 스토리지 팩토리 + 설정 — config에 storage_backend 설정 | [x] | `config.py`, `storage/factory.py` |

## Phase 4-D: 편집 잠금

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P4D-1 | Lock 서비스 — 인메모리 잠금 관리 (TTL 자동 해제) | [x] | `lock_service.py` |
| P4D-2 | Lock API — POST /lock, DELETE /unlock, GET /lock/status | [x] | `api/lock.py` |
| P4D-3 | 에디터 잠금 UI — 편집 시 잠금 획득, 타 사용자 읽기전용 | [x] | `MarkdownEditor.tsx` |
| P4D-4 | 자동 해제 — 탭 닫기/세션 종료/5분 TTL 만료 자동 해제 | [x] | `lock_service.py`, `MarkdownEditor.tsx` |

## Phase 4-E: 권한 관리 (RBAC)

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P4E-1 | 권한 모델 정의 — 기존 User.roles 활용 | [x] | `auth/models.py` (기존) |
| P4E-2 | ACL 저장소 — 폴더/문서별 접근 권한 JSON 관리 | [x] | `auth/acl_store.py` |
| P4E-3 | 권한 체크 의존성 — require_read/require_write | [x] | `auth/permission.py` |
| P4E-4 | Wiki API 권한 적용 — 읽기/쓰기/삭제에 권한 체크 | [x] | `api/wiki.py` |
| P4E-5 | RAG 권한 필터 — 검색 결과에서 접근 불가 문서 제외 | [x] | `rag_agent.py` |
| P4E-6 | 프론트엔드 권한 반영 — 403 에러 시 저장 실패 표시 | [x] | `MarkdownEditor.tsx` (기존 toast) |
| P4E-7 | 권한 관리 UI — ACL 설정 패널 + TreeNav 메뉴 | [x] | `PermissionEditor.tsx`, `api/acl.py` |

## Phase 4-F: 보안 강화 + 운영 안정성

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P4F-1 | 시크릿 관리 — .env 분리, .gitignore 강화 | [x] | `.env.example`, `.gitignore` |
| P4F-2 | CORS 강화 — 와일드카드 제거, 명시적 화이트리스트 | [x] | `main.py` |
| P4F-3 | 구조화 로깅 — JSON 포맷 + 요청 ID 추적 | [x] | `main.py`, `logging_config.py` |
| P4F-4 | 입력 검증 강화 — 파일 경로 검증, 요청 크기 제한 | [x] | `api/wiki.py` |
| P4F-5 | 백엔드 에러 핸들러 — 전역 예외 처리 | [x] | `main.py` |

## Phase 4-G: 대규모 대응 + 성능

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P4G-1 | 검색 인덱스 페이지네이션 — offset/limit 파라미터 | [x] | `search.py` |
| P4G-2 | 트리 지연 로딩 — depth 파라미터 + subtree API | [x] | `wiki.py` |
| P4G-3 | ChromaDB 배치 인덱싱 — 100건 단위 배치 upsert | [x] | `chroma.py` |
| P4G-4 | API 응답 캐싱 — 트리 API ETag/304 | [x] | `wiki.py` |

---

## Phase 5-A: 프론트엔드 생존 — Lazy Tree + 서버 검색

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P5A-1 | 트리 Lazy Loading — depth=1 초기 로드 + subtree API 연동 | [x] | `TreeNav.tsx`, `wiki.ts`, `wiki.py`, `local_fs.py`, `base.py`, `schemas.py` |
| P5A-2 | 서버 사이드 검색 — MiniSearch 제거, `/api/search/quick` 신규 | [x] | `useSearchStore.ts`, `search.py` |
| P5A-3 | 트리 증분 업데이트 — 전체 재조회 → 낙관적 로컬 업데이트 | [x] | `TreeNav.tsx` |
| P5A-4 | 프론트엔드 ETag 활용 — If-None-Match 전송 + 304 캐시 | [x] | `wiki.ts` |

## Phase 5-B: 백엔드 동시성 + 비동기 인덱싱

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P5B-1 | Uvicorn 멀티 워커 — `--workers 4` + 리소스 제한 | [x] | `Dockerfile.backend`, `docker-compose.yml`, `config.py` |
| P5B-2 | 비동기 인덱싱 — save 즉시 반환, 백그라운드 인덱싱 큐 + 인덱싱 상태 추적 | [x] | `wiki_service.py`, `wiki.py` |
| P5B-2a | 인덱싱 상태 UI — 에디터/트리에 반영 여부 표시, 파일별 수동 재인덱싱, 관리 페이지에서 미반영 문서 일괄 재인덱싱 | [x] | `MarkdownEditor.tsx`, `wiki.py` (API: index-status, reindex/{path}, reindex-pending) |
| P5B-3 | BM25 주기적 리빌드 — 10초 백그라운드 + threading.Lock | [x] | `bm25.py` |
| P5B-4 | 하이브리드 검색 병렬화 — asyncio.gather(vector, bm25) | [x] | `search.py` |
| P5B-5 | 시작 시 백그라운드 인덱싱 — 블로킹 → create_task | [x] | `main.py` |
| P5B-6 | `list_all_files()` 최적화 — 메타 캐시 + 경량 list_file_paths | [x] | `local_fs.py`, `base.py` |

## Phase 5-C: Redis 기반 상태 공유

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P5C-1 | Redis 도입 + Lock 이관 — SET NX EX 원자 잠금 | [x] | `docker-compose.yml`, `config.py`, `lock_service.py`, `lock.py` |
| P5C-2 | Redis 기반 쿼리 캐시 — 무제한 LRU + 멀티 워커 공유 | [x] | `query_cache.py` |
| P5C-3 | Lock Refresh 배치화 — batch-refresh API + 중앙 매니저 | [x] | `MarkdownEditor.tsx`, `lock.py`, `wiki.ts`, `lockManager.ts` |
| P5C-4 | ACL 캐싱 + 핫 리로드 — LRU + 파일 변경 감지 | [x] | `acl_store.py` |

## Phase 5-D: 수평 확장 + 리소스 운영

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P5D-1 | Nginx 리버스 프록시 + 로드 밸런서 | [x] | `nginx.conf`, `docker-compose.yml` |
| P5D-2 | Docker 리소스 제한 — CPU/메모리 제한 | [x] | `docker-compose.yml` |
| P5D-3 | ChromaDB 커넥션 풀링 — Settings 설정 | [x] | `chroma.py` |
| P5D-4 | `get_all_embeddings()` 페이지네이션 — 1000건 배치 | [x] | `chroma.py` |
| P5D-5 | SSE 실시간 이벤트 — 트리/잠금/인덱싱 브로드캐스트 | [x] | `main.py`, `wiki_service.py`, `TreeNav.tsx`, `event_bus.py` |

## Phase 5-E: LLM 처리량 최적화

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P5E-1 | RAG LLM 파이프라인 최적화 — reflection 캐시 + 세마포어 | [x] | `rag_agent.py` |
| P5E-2 | LLM 응답 캐싱 — cognitive_reflect 인메모리 캐시 (10분 TTL) | [x] | `rag_agent.py` |
| P5E-3 | Ollama 동시 처리 — NUM_PARALLEL + llm_semaphore_limit | [x] | `docker-compose.yml`, `config.py`, `rag_agent.py` |
| P5E-4 | 백그라운드 검색 인덱스 캐싱 — backlinks/tags 60s TTL 캐시 | [x] | `search.py` |
| P5E-5 | 메타데이터 엔드포인트 최적화 — frontmatter-only 읽기 + 60s TTL 캐시 | [x] | `metadata.py`, `local_fs.py`, `base.py`, `wiki_service.py` |

---

## 충돌 감지 리팩토링 (Batch → Incremental)

> 기존 O(n²) 전체 스캔(79초)을 문서 저장 시 ChromaDB HNSW 쿼리(~50ms)로 대체.
> 설계 문서: `~/.gstack/projects/onTong/donghae-unknown-design-20260330-155500.md`
> 플랜: `~/.claude/plans/dazzling-orbiting-yeti.md`

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| CR-1 | ChromaDB `get_file_embeddings()` + `query_by_embedding()` 추가 | [x] | `chroma.py` |
| CR-2a | `ConflictStore` ABC + `InMemoryConflictStore` 구현 | [x] | `conflict_store.py` |
| CR-2b | `RedisConflictStore` 구현 (SHA256 해시 키) | [x] | `conflict_store.py` |
| CR-3a | `ConflictService.check_file()` — 파일별 증분 감지 | [x] | `conflict_service.py` |
| CR-3b | `ConflictService.remove_file()` + `full_scan()` + `get_pairs()` + `update_metadata()` | [x] | `conflict_service.py` |
| CR-4a | `GET /duplicates` 리라이트 — store 직접 읽기 | [x] | `api/conflict.py` |
| CR-4b | `POST /full-scan` + `GET /scan-status` 신규 | [x] | `api/conflict.py` |
| CR-5a | `_bg_index()` 훅 — 인덱싱 후 `check_file()` | [x] | `wiki_service.py` |
| CR-5b | `delete_file()` + `move_file()` + `move_folder()` 훅 | [x] | `wiki_service.py` |
| CR-6 | 프론트엔드 즉시 로드 + "전체 스캔" 버튼 + 프로그레스 | [x] | `ConflictDashboard.tsx` |
| CR-7 | 테스트 — conflict_store + conflict_service + API + E2E | [x] | `tests/test_p2b3_conflict_dashboard.py` |

## Skill System 기반 구축

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| SK-1 | Skill Protocol + SkillResult + SkillRegistry | [x] | `backend/application/agent/skill.py` |
| SK-2 | AgentContext (per-request context, run_skill, emit_thinking, sse) | [x] | `backend/application/agent/context.py` |
| SK-3a | QueryAugmentSkill — 후속 질문 → 독립 검색 쿼리 변환 | [x] | `backend/application/agent/skills/query_augment.py` |
| SK-3b | WikiSearchSkill — 하이브리드 검색 (vector + BM25 + RRF + 필터 + reranking) | [x] | `backend/application/agent/skills/wiki_search.py` |
| SK-3c | WikiReadSkill — 단일 문서 읽기 | [x] | `backend/application/agent/skills/wiki_read.py` |
| SK-3d | WikiWriteSkill — 새 문서 생성 + 승인 요청 | [x] | `backend/application/agent/skills/wiki_write.py` |
| SK-3e | WikiEditSkill — 기존 문서 편집 + 승인 요청 | [x] | `backend/application/agent/skills/wiki_edit.py` |
| SK-3f | LLMGenerateSkill — LLM 호출 (streaming/non-streaming, tool-use 지원) | [x] | `backend/application/agent/skills/llm_generate.py` |
| SK-3g | ConflictCheckSkill — 문서 간 모순 감지 | [x] | `backend/application/agent/skills/conflict_check.py` |
| SK-4 | ReAct loop + tool executor (LLM tool-use 에이전트용 공용 유틸) | [x] | `backend/application/agent/tool_executor.py` |
| SK-5 | RAGAgent 리팩토링 — skill 호출 전환, ctx 없을 때 inline fallback | [x] | `backend/application/agent/rag_agent.py` |
| SK-6a | main.py — register_all_skills() + chroma/storage 전달 | [x] | `backend/main.py` |
| SK-6b | api/agent.py — AgentContext 생성 + ctx=ctx kwarg 전달 | [x] | `backend/api/agent.py` |
| SK-7 | 기존 테스트 회귀 확인 (68/68 PASSED) | [x] | `tests/` |

## User-Facing Skill System (사용자 스킬 관리)

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| US-1 | Pydantic 스키마 (SkillMeta, SkillListResponse, SkillCreateRequest, ChatRequest.skill_path, GraphNode.node_type) | [x] | `schemas.py` |
| US-2 | UserSkillLoader — _skills/ 스캔, frontmatter 파싱, 캐시, [[wikilink]] 참조 문서 로딩 | [x] | `backend/application/skill/skill_loader.py` |
| US-3 | SkillMatcher — trigger 키워드 매칭 (substring + token overlap) | [x] | `backend/application/skill/skill_matcher.py` |
| US-4 | AgentContext 확장 — user_skill, skill_context 필드 | [x] | `backend/application/agent/context.py` |
| US-5 | api/agent.py 스킬 해석 — 명시적 skill_path + 자동 매칭 + SSE skill_match 이벤트 | [x] | `backend/api/agent.py` |
| US-6 | RAGAgent._handle_skill_qa — 스킬 기반 Q&A (지시사항 + 참조 문서 → LLM 답변) | [x] | `backend/application/agent/rag_agent.py` |
| US-7 | Skill CRUD API — list, get, create, update, delete, match 엔드포인트 | [x] | `backend/api/skill.py` |
| US-8 | main.py 와이어링 — UserSkillLoader/SkillMatcher 초기화, skill_api 라우터 등록 | [x] | `backend/main.py` |
| US-9 | 프론트엔드 타입 — SkillMeta, SkillListResponse, GraphNode.node_type | [x] | `types/wiki.ts` |
| US-10 | API 클라이언트 — fetchSkills, createSkill, deleteSkill, matchSkill | [x] | `lib/api/skills.ts` |
| US-11 | 사이드바 Skills 탭 — SkillsSection, SkillCard, 인라인 생성 폼 | [x] | `TreeNav.tsx` |
| US-12 | Copilot 통합 — 스킬 피커 버튼, selectedSkill pill, 자동 제안 배너 | [x] | `AICopilot.tsx` |
| US-13 | SSE 확장 — skillPath 파라미터, onSkillMatch 콜백, skill_match 이벤트 | [x] | `sseClient.ts` |
| US-14 | 그래프 노드 타입 구분 — node_type=skill, 다이아몬드 렌더링, 보라색, 범례 | [x] | `search.py`, `DocumentGraph.tsx` |
| US-15 | 기존 테스트 회귀 확인 (68/68 PASSED) | [x] | `tests/` |
| | **User-Facing Skill System 합계** | **15 tasks** | **✅ 완료** |
| | | | |
| ST | Skill 시스템 테스트 추가 (loader, matcher, API) | 4 | ✅ 완료 |

## Skill System 고도화 (카테고리 + 우선순위 + 무시 관리)

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| SE-1 | 스키마 확장 — category, priority, pinned (BE SkillMeta/SkillCreateRequest/SkillListResponse + FE types) | [x] | `schemas.py`, `wiki.ts` |
| SE-2 | skill_loader 카테고리 추출 — 폴더 경로 기반 + frontmatter 오버라이드, categories 집계 | [x] | `skill_loader.py` |
| SE-3 | 카테고리 기반 스킬 생성 경로 + frontmatter 출력 | [x] | `api/skill.py` |
| SE-4 | 매칭 priority 가중치 (score * (0.8 + p*0.04)) + pinned/priority tiebreaker | [x] | `skill_matcher.py` |
| SE-5 | PATCH toggle API — enabled 필드 flip | [x] | `api/skill.py` |
| SE-6 | toggleSkill API 클라이언트 | [x] | `skills.ts` |
| SE-7 | 사이드바 카테고리 접이식 그룹 + 검색 + 토글 + 복제 + pinned 표시 | [x] | `TreeNav.tsx` |
| SE-8 | 생성 폼 카테고리/우선순위 필드 추가 | [x] | `TreeNav.tsx` |
| SE-9 | Copilot 피커 카테고리 그룹핑 + 검색 | [x] | `AICopilot.tsx` |
| SE-10 | localStorage dismissed 영속화 | [x] | `AICopilot.tsx` |
| SE-11 | 데모 스킬 카테고리 폴더 이동 (HR, Finance, SCM) | [x] | `wiki/_skills/` |
| SE-12 | 기존 테스트 회귀 확인 (68/68 PASSED) | [x] | `tests/` |
| | **Skill System 고도화 합계** | **12 tasks** | **✅ 완료** |

## Skill System 버그픽스 + UX 개선

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| SF-1 | storage.write() frontmatter 손상 수정 — 스킬 CRUD에 직접 파일 쓰기 적용 | [x] | `api/skill.py` |
| SF-2 | PATCH toggle API 직접 파일 쓰기 — storage.write() 우회 | [x] | `api/skill.py` |
| SF-3 | 스킬 목록 API 비활성 포함 — include_disabled=True로 사이드바 재활성화 가능 | [x] | `api/skill.py`, `skill_loader.py` |
| SF-4 | Copilot 피커 실시간 갱신 — 열 때마다 refreshSkillList() | [x] | `AICopilot.tsx` |
| SF-5 | HR 스킬 파일 복원 (type: skill frontmatter) | [x] | `wiki/_skills/HR/신규입사자-온보딩.md` |
| SF-6 | 참조 문서 탐색 시각화 — 개별 📄 thinking step 표시 | [x] | `rag_agent.py` |
| SF-7 | 스킬 생성 템플릿 — 지시사항/배경/제약조건/질문예시/참조문서 가이드 | [x] | `api/skill.py` |
| | **버그픽스 + UX 개선 합계** | **7 tasks** | **✅ 완료** |

## 6-Layer Skill Architecture (gstack 패턴 적용)

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| SL-1 | SkillContext 모델 추가 + SkillCreateRequest에 5개 optional 필드 (role, workflow, checklist, output_format, self_regulation) | [x] | `schemas.py`, `wiki.ts` |
| SL-2 | skill_loader — load_skill_context() → SkillContext 구조체 반환, 6개 섹션 추출, 참조문서 누락 추적 | [x] | `skill_loader.py` |
| SL-3 | AgentContext.skill_context 타입 변경 (str → Any) | [x] | `context.py` |
| SL-4 | api/agent.py — Preamble 런타임 주입 (날짜, 사용자) | [x] | `api/agent.py` |
| SL-5 | _handle_skill_qa — 6-Layer 시스템 프롬프트 빌더 (Preamble→Role→Workflow→Instructions→Checklist→Output→Regulation) | [x] | `rag_agent.py` |
| SL-6 | _build_skill_markdown — 마크다운 생성에 새 6개 섹션 + 템플릿 추가 | [x] | `api/skill.py` |
| SL-7 | 데모 스킬 업그레이드 — 신규입사자-온보딩.md를 6-layer 형식으로 전환, 출장비 기본 형식 유지 (하위호환 검증) | [x] | `wiki/_skills/HR/신규입사자-온보딩.md` |
| SL-8 | 기존 테스트 회귀 확인 (68/68 PASSED) | [x] | `tests/` |
| SL-9 | 후속 질문 스킬 유지 — sessionSkill state로 세션 내 자동 유지 + 자동매칭 저장 + UI 표시 | [x] | `AICopilot.tsx` |
| | **6-Layer Skill 합계** | **9 tasks** | **✅ 완료** |

## FE 고급 설정 UI — 스킬 생성 6-Layer 폼

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| SA-1 | SkillContext TypeScript 타입 추가 | [x] | `types/wiki.ts` |
| SA-2 | ReferencedDocsPicker 컴포넌트 (문서 검색/선택) | [x] | `components/skills/ReferencedDocsPicker.tsx` |
| SA-3 | SkillCreateDialog 모달 컴포넌트 (6-Layer 입력 폼) | [x] | `components/skills/SkillCreateDialog.tsx` |
| SA-4 | TreeNav.tsx 통합 (고급 설정 버튼 + 모달 연결) | [x] | `TreeNav.tsx` |
| SA-5 | 스킬 컨텍스트 API 엔드포인트 (GET /api/skills/{path}/context) | [x] | `api/skill.py` |
| SA-6 | 스킬 복제 시 6-Layer 콘텐츠 복사 | [x] | `skills.ts`, `TreeNav.tsx` |
| | **FE 고급 설정 UI 합계** | **6 tasks** | **✅ 완료** |

## 스킬 관리 편의 기능 (우클릭 컨텍스트 메뉴 + 드래그앤드롭)

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| SU-1 | 스킬 우클릭 컨텍스트 메뉴 (삭제/복제/토글/편집) | [x] | `TreeNav.tsx` |
| SU-2 | 스킬 삭제 확인 다이얼로그 + 삭제 핸들러 | [x] | `TreeNav.tsx` |
| SU-3 | 스킬 드래그앤드롭 (카테고리 간 이동) | [x] | `TreeNav.tsx`, `api/skill.py` |
| SU-4 | 테스트 + 문서 업데이트 | [x] | `demo_guide.md`, `TODO.md` |

## Skill 시스템 테스트 추가

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| ST-1 | skill_loader Unit 테스트 — frontmatter 파싱, 카테고리 추출, 6-Layer 섹션, 캐시, wikilink | [x] | `tests/test_skill_loader.py` |
| ST-2 | skill_matcher Unit 테스트 — substring/Jaccard, threshold, priority, 한국어 토큰화 | [x] | `tests/test_skill_matcher.py` |
| ST-3 | Skill API Integration 테스트 — CRUD, toggle, move, match, context | [x] | `tests/test_skill_api.py` |
| ST-4 | 전체 회귀 확인 (기존 68 + 신규 77 = 145 PASSED) | [x] | 테스트 결과 |

---

## Pydantic AI 프레임워크 마이그레이션

> 에이전트 프레임워크 유지보수성 확보를 위해 Pydantic AI로 마이그레이션.
> SIMULATION/DEBUG_TRACE 에이전트 구현은 동료가 별도 진행 (본 TODO 범위 밖).

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| PA-1 | Pydantic AI 의존성 추가 + 환경 구성 | [x] | `pyproject.toml`, `llm_factory.py` |
| PA-2 | 기존 Skill 프로토콜 → Pydantic AI `@agent.tool` 전환 + 구조화 출력 모델 | [x] | `models.py`, `pydantic_tools.py` |
| PA-3 | AgentPlugin/Registry 유지 (Hybrid 접근) + litellm 제거 (5개 스킬) | [x] | `skills/*.py` |
| PA-4 | RAGAgent 마이그레이션 (cognitive_reflect + 스트리밍 + 인라인 핸들러) | [x] | `rag_agent.py` |
| PA-5 | ReAct 루프 (tool_executor.py) → Pydantic AI 내장 도구 호출 전환 | [x] | `tool_executor.py`, `react_agent.py` |
| PA-6 | SSE 스트리밍 연동 확인 (기존 이벤트 타입 유지) | [x] | `api/agent.py` (변경 없음) |
| PA-7 | 기존 테스트 회귀 확인 (174/174 PASS, 신규 29개) | [x] | `tests/test_pydantic_ai_migration.py` |
| PA-8 | 새 에이전트 구조로 SIMULATION/DEBUG_TRACE 스캐폴딩 | [x] | `simulator_agent.py`, `tracer_agent.py` |

## Pydantic AI 데모 테스트 버그 수정

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| BF-1 | 스킬 참조문서 wikilink 해석 — 하위 디렉토리 검색 | [x] | `skill_loader.py` |
| BF-2 | LiteLLMProvider API 키 → OpenAIProvider 직접 사용 | [x] | `llm_factory.py` |
| BF-3 | Write intent 패턴 확장 (체크리스트/가이드/매뉴얼 등) | [x] | `rag_agent.py` |
| BF-4 | LLM Provider 추상화 — 레지스트리 패턴, 7개 프로바이더 | [x] | `llm_factory.py`, `config.py` |
| BF-5 | LLM 모델 업그레이드 (gpt-4o-mini → gpt-4o) | [x] | `.env` |
| BF-6 | 키워드 라우팅 → LLM 통합 분류 (UserIntent) | [x] | `router.py`, `rag_agent.py`, `models.py`, `structured_agents.py`, `api/agent.py` |
| BF-7 | 충돌 감지 — context 확장(6000자) + zip 불일치 + conflict_check 2차 호출 | [x] | `rag_agent.py` |
| BF-8 | Lineage 동기화 — status 미설정 시 supersedes/superseded_by 자동 정리 | [x] | `local_fs.py`, `wiki_service.py` |
| BF-9 | 충돌 설명 한국어 출력 | [x] | `rag_agent.py`, `conflict_check.py` |
| BF-10 | 채팅 입력 히스토리 (↑↓ 방향키) | [x] | `AICopilot.tsx` |
| BF-11 | 문서 생성/수정 워크스페이스 직접 작업 (채팅 승인 제거) | [x] | `schemas.py`, `wiki_edit.py`, `wiki_write.py`, `rag_agent.py`, `AICopilot.tsx`, `MarkdownEditor.tsx`, `useWorkspaceStore.ts`, `sseClient.ts` |
| BF-12 | README.md + docs/tech-stack.md 업데이트 | [x] | `README.md`, `docs/tech-stack.md` |
| BF-13 | 충돌 비교 해결 — ConflictPair 모델 + SSE 이벤트 확장 | [x] | `schemas.py` |
| BF-14 | 충돌 비교 해결 — 페어 빌드 로직 + ConflictStore 연동 | [x] | `rag_agent.py`, `context.py`, `agent.py`, `main.py` |
| BF-15 | 충돌 비교 해결 — 채팅 배너 "나란히 비교" 버튼 + 해결 상태 반영 | [x] | `AICopilot.tsx`, `sseClient.ts`, `useWorkspaceStore.ts`, `DiffViewer.tsx` |
| BF-16 | 충돌 감지 오탐 수정 + 요약 품질 개선 | [x] | `rag_agent.py` |

---

### 권장 작업 순서 (크리티컬 패스)

```
Step 0 (환경)
  → Step 1-A (레이아웃)
    → Step 1-B (에디터)  ─────────────────────────┐
      → Step 1-C (클립보드, BE 먼저)               │ 병렬 가능
  → Step 1-E BE (B1→B9 직렬)                      │
    → Step 1-E FE (F1→F6)                         │
  → Step 1-D BE (1D-1,2)                          │
    → Step 1-D FE (뷰어들)                         │
  → Step 1-F (1F-0 BE 먼저 → FE)  ────────────────┘
    → Step 4 (통합 테스트)
```

---

## 작업 지시 방법

각 Step을 시작할 때:
```
Step 0 시작해줘
```

특정 태스크 범위 지정:
```
1E-B1부터 1E-B5까지 진행해줘
```

백엔드 먼저 지시:
```
Step 1-C 백엔드(1C-5)부터 시작해줘
```

완료 태스크는 이 파일 + `CHECKLIST.md`에서 동시 업데이트합니다.

---

## 🔷 3-Section Platform (모델링/시뮬레이션은 별도 팀 진행)

> Modeling(Section 2) + Simulation(Section 3)은 다른 팀에서 별도 진행 중.
> 아래는 Wiki 팀에서 완료한 공유 인프라 스캐폴딩 기록만 남김.

### Phase 0 완료분 (Wiki 팀 기여)

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| V2-0-2 | `shared/contracts/simulation.py` — typed 계약 합의 | [x] | `backend/shared/contracts/simulation.py` |
| V2-0-3 | `shared/agent_framework/` — BaseAgent Protocol 추출 | [x] | `backend/shared/agent_framework/` |
| V2-0-10 | `backend/modeling/` 스캐폴딩 | [x] | `backend/modeling/` |
| V2-0-11 | `backend/simulation/` 스캐폴딩 + mock 서버 | [x] | `backend/simulation/` |
| V2-0-12 | Frontend Section 네비게이션 + 3-pane 레이아웃 | [x] | `SectionNav.tsx`, `ModelingSection.tsx`, `SimulationSection.tsx` |
| V2-0-17 | Section 3 개발자 가이드 | [x] | `docs/section3-developer-guide.md` |

> Phase 0 잔여 (온톨로지, shared/ 추출, wiki/ 이동, Neo4j, job queue 등) 및 Phase 1~3은 모델링/시뮬레이션 팀 관할.

### Phase 1a — Engine-First Architecture (2026-04-16)

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| E1a-1 | Simulation Data Models (ParametricSimResult 외 4 모델) | [x] | `backend/modeling/simulation/sim_models.py` |
| E1a-2 | Term Resolver (Korean alias 30개 + fuzzy + LLM) | [x] | `backend/modeling/query/term_resolver.py` |
| E1a-3 | Simulation Registry (9 SCM entities × calc functions) | [x] | `backend/modeling/simulation/sim_registry.py` |
| E1a-4 | Simulation Engine (param clamp + calc + BFS impact) | [x] | `backend/modeling/simulation/sim_engine.py` |
| E1a-5 | Engine API (/engine/query, /simulate, /params, /status) | [x] | `backend/modeling/api/engine_api.py` |
| E1a-6 | Seed Enhancement (sim_entities count) | [x] | `backend/modeling/api/seed_api.py` |
| E1a-7 | Frontend API Client (4 functions + 6 types) | [x] | `frontend/src/lib/api/modeling.ts` |
| E1a-8 | AnalysisConsole (자연어 입력 → 영향 분석 UI) | [x] | `frontend/.../modeling/AnalysisConsole.tsx` |
| E1a-9 | SimulationPanel (파라미터 슬라이더 + before/after) | [x] | `frontend/.../modeling/SimulationPanel.tsx` |
| E1a-10 | Sidebar Restructure (MAIN/SETTINGS nav, 기본탭=analysis) | [x] | `frontend/.../ModelingSection.tsx` |

> 28 tests, TS clean, UI+API 검증 완료. 다음: Phase 2a (소스 뷰어 + 매핑 캔버스).

### Phase 2a — Source Viewer + Mapping Workbench (구현 완료 ✅)

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| E2a-1 | Source API (파일 트리 + 내용 + 엔티티 위치) | [x] | `backend/modeling/api/source_api.py` |
| E2a-2 | Source Viewer (파일 트리 + Monaco 읽기 전용) | [x] | `frontend/.../modeling/SourceViewer.tsx` |
| E2a-3 | Mapping Canvas (React Flow 도메인 그래프) | [x] | `frontend/.../modeling/MappingCanvas.tsx` |
| E2a-4 | Canvas 코드 엔티티 패널 + 드래그 매핑 | [x] | `frontend/.../modeling/MappingCanvas.tsx` |
| E2a-5 | Mapping Workbench 통합 (분할 패널 + 양방향 연동) | [x] | `frontend/.../modeling/MappingWorkbench.tsx` |
| E2a-6 | Sidebar + ModelingSection 통합 | [x] | `frontend/.../ModelingSection.tsx` |
| E2a-7 | Design Review 수정: Seed API 소스 파일 자동 복사 | [x] | `backend/modeling/api/seed_api.py` |
| E2a-8 | Design Review 수정: React Flow fitView 노드 로딩 후 재실행 | [x] | `frontend/.../modeling/MappingCanvas.tsx` |

> 14 source API tests, TS clean, design review 완료. 데모 가이드: `toClaude/modeling/demo_guide_modeling.md`

### Ontology-First Redesign — Week 1 DSL Lock (2026-04-18)

> 설계 문서: `~/.gstack/projects/Jeensh-onTong/donghae-main-design-20260418-173359.md` (APPROVED with scope correction). Section 2 = 온톨로지 빌더 (primary). 3 agents는 Section 3로 이관 예정, 검증용으로 `backend/modeling/agents/` 격리 구현.

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| OD-0 | Scope 정정 반영 (Premise 8 + Migration Architecture) | [x] | `~/.gstack/.../design-20260418-173359.md` |
| OD-1 | Pydantic schema (Ontology + OntologyHeader + Process + Formula + Rule + IOPort + Term + CodeBinding, `extra="forbid"`) | [x] | `backend/modeling/ontology/schema.py` |
| OD-2 | Sub-DSL AST 파서 + graph validator (arithmetic/boolean whitelist, cycle/duplicate/refers_to 검증) | [x] | `backend/modeling/ontology/validator.py` |
| OD-3 | YAML loader/dumper (`load_ontology`/`dump_ontology`, validation 기본 on, Enum→str) | [x] | `backend/modeling/ontology/loader.py` |
| OD-4 | 샘플 온톨로지 (SafetyStockCalculation + ReorderPointCalculation, 2 proc, 4 rules, 3 terms, 2 bindings) | [x] | `ontologies/safety_stock_v1.yaml` |
| OD-5 | pytest 39개 (schema 6 + validator 28 + loader 5) 모두 pass | [x] | `tests/test_ontology_{schema,validator,loader}.py` |
| OD-6 | Legacy ontology 이관 — `:DomainNode`→`:OntNode{kind}` 전면 재작성 (schema 루트 entities/roles/relations + Process.parent_id), SCOR+ISA-95 YAML 기반 템플릿, downstream Cypher 일괄 교체, domain_models.py/scor_template.py 삭제 | [x] | `backend/modeling/ontology/{schema,validator,loader,ontology_store}.py`, `ontologies/scor_isa95_v1.yaml`, `tests/test_ontology_{schema,validator,loader,store}.py`, `test_modeling_e2e.py` |
| OD-7 | 매뉴얼 markdown 샘플 2건 확보 (가열공정 SOP + 균열 품질기준) — 팀 분배표는 팀원 정보 필요로 별도 대화 | [x] | `ontologies/manuals/{heating-process-sop,crack-quality-standard}.md`, `ontologies/manuals/README.md` |
| OD-8 | Ontology Builder UI — 매뉴얼 빌더 탭 신설 (markdown + YAML 분할 에디터, `/draft` LLM 연동, 실시간 `/validate`, `/save`) | [x] | `backend/modeling/ontology/builder_service.py`, `backend/modeling/api/ontology_api.py` (+4 endpoints), `frontend/.../modeling/ManualOntologyBuilder.tsx`, `frontend/.../lib/api/modeling.ts`, `ModelingSection.tsx` (MAIN_NAV 최상단), `tests/test_ontology_builder_service.py` |
| OD-10 | Legacy Cleanup — Engine Phase 1a/2a 잔재 일괄 제거. 프론트 9 컴포넌트 + `modeling.ts` 17 함수 + 백엔드 7 API + 8 디렉터리 + 15 테스트 삭제. `ModelingSection` nav `builder`+`ontology` 2탭으로 단순화 | [x] | `backend/modeling/{api,ontology,infrastructure}/`, `frontend/.../modeling/{ModelingSection,DomainOntologyEditor,ManualOntologyBuilder}.tsx`, `frontend/.../lib/api/modeling.ts` |

> OD-6~8+10 완료: 84 ontology tests pass + 791 tests collect (import 0 error) + TS 0 error. 검증: `./venv/bin/pytest tests/test_ontology_*.py tests/test_neo4j_client.py && cd frontend && npx tsc --noEmit && ./venv/bin/python -c "from backend.main import app"`

### 향후 인프라 확장 (Phase 2a 완료 후)

| # | Task | 트리거 조건 | 상태 | 비고 |
|---|------|-----------|------|------|
| INFRA-1 | Docker Sandbox (컨테이너 생성/실행/삭제) | 샌드박스 Phase 착수 시 | [ ] | Docker Engine API 접근 필요 |
| INFRA-2 | Redis 파일 트리 캐싱 | 대규모 repo (10만+ 파일) 대응 시 | [ ] | 현재 직접 스캔으로 충분 |
| INFRA-3 | 매핑 이력 추적 (Audit Trail) | 매핑 변경 이력 요구 시 | [ ] | 현재 YAML은 이력 관리 약함 |
| INFRA-4 | WebSocket 실시간 동기화 | 멀티유저 동시 매핑 지원 시 | [ ] | 현재 단일 사용자 충분 |

---

## 🧠 에이전트 고도화 (agent_bible 분석 기반, v3)

> 기반 문서: `toClaude/_shared/agent_bible_analysis/99_adoption_plan.md` (v3 — 전문가 리뷰 반영)
> 제1 목표: 에이전트 이해력/답변 품질 최대화

### Phase 1: 이해력 혁신 (VOC 직접 해결)

| # | Task | 의존 | 상태 | 산출물 |
|---|------|------|------|--------|
| AG-1-1 | ontong.md 생성 (에이전트 성격/규칙 정의) | - | [x] | `backend/ontong.md` |
| AG-1-2 | 시스템 프롬프트 교체 (FINAL_ANSWER_SYSTEM_PROMPT → ontong.md 로드) | AG-1-1 | [x] | `rag_agent.py` |
| AG-1-3 | 토큰 기반 히스토리 윈도우 (history[-6:] → 동적 예산) | - | [x] | `rag_agent.py`, `wiki_edit.py` |
| AG-1-4 | 구조화된 대화 요약 (규칙 기반, Scope/Skills/Requests/Docs/Current) | AG-1-3 | [x] | `rag_agent.py` |
| AG-1-5 | Continuation instruction 추가 ("요약 인정하지 말고 이어서") | AG-1-4 | [x] | `rag_agent.py`, `ontong.md` |
| AG-1-6 | query_augment 강화 + 주제 전환 감지 (topic_shift) | - | [x] | `skills/query_augment.py`, `rag_agent.py`, `models.py`, `api/agent.py` |
| AG-1-7 | 스킬 프롬프트 마크다운 분리 (코드 ↔ LLM 지시 분리) | AG-1-1 | [x] | `skills/prompts/*.md`, `prompt_loader.py` |
| AG-1-8 | Cognitive Reflect 제거 (AG-1-1~2 검증 후) | AG-1-2 | [x] | `rag_agent.py`, `structured_agents.py` |

### Phase 2: 실행 최적화

| # | Task | 의존 | 상태 | 산출물 |
|---|------|------|------|--------|
| AG-2-1 | 스킬별 도구 풀 제한 (allowed-tools 매핑) | Phase 1 | [x] | `context.py`, `api/agent.py` |
| AG-2-2 | 파이프라인 병렬화 (query_augment ∥ vector_search) | Phase 1 | [x] | `api/agent.py` (기존 병렬화 충분) |
| AG-2-3 | SkillResult feedback 필드 추가 | Phase 1 | [x] | `skill.py`, `wiki_search.py`, `rag_agent.py` |

### Phase 3: 인프라 강화

| # | Task | 의존 | 상태 | 산출물 |
|---|------|------|------|--------|
| AG-3-1 | 세션 영속성 (JSONL append) | Phase 2 | [x] | `core/session.py`, `api/agent.py` |
| AG-3-2 | 스킬 권한 매핑 (READ/WRITE/EXECUTE) | Phase 2 | [x] | `skill.py`, `context.py` |
| AG-3-3 | PreSkill/PostSkill 훅 시스템 | AG-3-2 | [x] | `skill.py` HookRegistry, `hooks.py` 내장훅, `context.py` 훅 파이프라인 |

### V2-Phase 2: 비즈니스 시뮬레이션 연동 (Section 3)

| # | Task | 의존 | 상태 | 산출물 |
|---|------|------|------|--------|
| V2-2-1 | 파라메트릭 시뮬레이션 엔진 (Monte Carlo 등) | Phase 1 | [ ] | `backend/modeling/simulation/executor.py` |
| V2-2-2 | 비동기 job queue 연동 (시뮬레이션 실행) | V2-0-15, V2-2-1 | [ ] | `backend/modeling/simulation/job_queue.py` |
| V2-2-3 | OutputFormat별 결과 가공 (ChartOutput, TableOutput, GanttOutput) | V2-2-1 | [ ] | `backend/modeling/simulation/formatter.py` |
| V2-2-4 | Parametric mock 서버 (정적 JSON X, 파라미터 기반 동적 생성) | Phase 0 | [x] | `backend/simulation/mock/scenarios/slab_size_simulator.py`, `backend/simulation/tools/mock_simulator.py` |
| V2-2-5 | SimAgent 기본 구현 (시나리오 설계 + 결과 해석) | V2-2-4 | [x] | `backend/simulation/agent/` (scenario_a/b/c, agent_builder, custom_runner) |
| V2-2-6 | SimCopilot 프론트엔드 (채팅 + 대시보드 하이브리드) | V2-2-5 | [x] | `frontend/src/components/simulation/` (SimulationSidebar, CustomAgentHub, AgentBuilderChat, CustomAgentRunner, CustomAgentFormBuilder) |
| V2-2-7 | ScenarioDashboard (차트/테이블/Gantt 시각화) | V2-2-3 | [ ] | `frontend/src/components/simulation/ScenarioDashboard.tsx` |
| V2-2-8 | ParameterForm (시나리오 파라미터 입력 폼) | V2-2-4 | [ ] | `frontend/src/components/simulation/ParameterForm.tsx` |
| V2-2-9 | 시나리오 버전 관리 + 결과 저장소 | V2-2-6 | [ ] | `backend/simulation/storage/` |
| V2-2-10 | CompareView (시나리오 A vs B 비교) | V2-2-9 | [ ] | `frontend/src/components/simulation/CompareView.tsx` |
| V2-2-11 | Mock → 실제 API 전환 테스트 | V2-2-1, V2-2-5 | [ ] | 통합 테스트 |

### V2-Phase 3: 데이터 통합 + 운영 연동 (Section 3)

### Phase 4: Q&A ReAct 루프

| # | Task | 의존 | 상태 | 산출물 |
|---|------|------|------|--------|
| AG-4-1 | Q&A 멀티턴 자율 검색 (ReAct 루프 확장) | Phase 2 | [x] | `rag_agent.py`, `models.py`, `prompts/qa_react.md` |
| AG-4-2 | 검색 결과 자기 평가 + 재검색 전략 | AG-4-1 | [x] | `skills/prompts/qa_react.md` (충분성 체크리스트 + 재검색 전략 5단계) |
| AG-4-3 | 사용자 확인 루프 + CompletionStatus | AG-4-1 | [x] | ClarificationRequestEvent SSE, CompletionStatus enum, emit_clarification() |

### 에이전트 고도화 진행 요약

| Phase | 내용 | Task 수 | 상태 |
|-------|------|---------|------|
| Phase 1 | 이해력 혁신 | 8 | ✅ 완료 (8/8) |
| Phase 2 | 실행 최적화 | 3 | ✅ 완료 (3/3) |
| Phase 3 | 인프라 강화 | 3 | ✅ 완료 (3/3) |
| Phase 4 | Q&A ReAct 루프 | 3 | ✅ 완료 (3/3) |
| | **합계** | **17/17 완료** | 전체 완료 |
| V2-Phase 0 | 공유 인프라 구축 | 17 | 🔨 6/17 완료 |
| V2-Phase 1 | 코드 영향 분석 MVP | 11 | ⬜ 미시작 |
| V2-Phase 2 | 비즈니스 시뮬레이션 연동 | 11 | 🔨 3/11 완료 (V2-2-4~6) |
| V2-Phase 3 | 데이터 통합 + 운영 연동 | 6 | ⬜ 미시작 |
| | **V2 합계** | **45 tasks** | |

---

## 세션 35 (2026-04-07) — Smart Friction 레이턴시 최적화

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| S35-1 | Smart Friction 선제 캐싱 — 디바운스 search와 동시에 `onCheckSimilar` 백그라운드 호출, 캐시 히트 시 Enter 즉시 반응 | [x] | `frontend/src/components/editors/metadata/TagInput.tsx` |
| S35-2 | similarCache LRU 50개 제한 — Map 삽입 순서 기반 경량 LRU, 장시간 세션 메모리 누수 방지 | [x] | `frontend/src/components/editors/metadata/TagInput.tsx` |

## 세션 36 (2026-04-07~08) — 태그 자동화 고도화 (Phase A+B)

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| S36-A1 | 프롬프트 외부화 (auto_tag_pass1/pass2/auto_tag.md) | [x] | `backend/application/agent/skills/prompts/auto_tag*.md` |
| S36-A2 | 컨텍스트 확장 — filename/parent/neighbor tags/neighbor domains/related docs | [x] | `metadata_service.py`, `metadata_index.py` (4개 메서드 추가) |
| S36-A3 | 2-pass 계층 추론 (domain/process → tags scoped) | [x] | `metadata_service.py` `_pass1_domain`/`_pass2_tags` |
| S36-A4 | Few-shot 7개 도메인 예시 | [x] | `backend/application/metadata/auto_tag_examples.json` |
| S36-A5 | Always-normalize + `TagAlternative` 스키마 | [x] | `metadata_service.py`, `core/schemas.py` |
| S36-A6 | 프론트 Soft UI (alternatives 칩 + 치환 클릭) | [x] | `AutoTagButton.tsx`, `MetadataTagBar.tsx` |
| S36-A7 | Confidence 자동 보정 | [x] | `metadata_service.py` |
| S36-A8 | 회귀 테스트 (domain 정확도 100%, 22건 자동 치환) | [x] | `tests/test_auto_tag_quality.py`, `tests/fixtures/auto_tag_baseline.json` |
| S36-B1 | `extract_query_tags` (쿼리→태그 의미매칭) | [x] | `backend/application/agent/filter_extractor.py` |
| S36-B2 | RAG tag boost rerank (`ONTONG_TAG_BOOST_WEIGHT`) | [x] | `backend/application/agent/rag_agent.py` |
| S36-B3 | Tag-only fallback (domain 0건 → 태그 필터 → 무필터) | [x] | `backend/application/agent/rag_agent.py` |
| S36-B4 | RAG 평가 스크립트 (12 쿼리, baseline hit@5=1.0) | [x] | `tests/test_rag_tag_boost.py`, `tests/fixtures/rag_eval_queries.json` |

---

## 세션 37 (2026-04-09) — Path-Aware RAG + 대화형 경로 명확화

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| S37-P1-1 | 경로 프리픽스 함수 `_build_path_prefix()` | [x] | `wiki_indexer.py` |
| S37-P1-2 | 모든 청크에 경로 프리픽스 적용 | [x] | `wiki_indexer.py` |
| S37-P1-3 | 구조화된 경로 메타데이터 (`path_depth_1/2/stem`) | [x] | `wiki_indexer.py` |
| S37-P1-4 | 재인덱싱 실행 + 검증 | [x] | `wiki_service.py` |
| S37-P2-1 | `extract_path_filter()` 쿼리 경로 추출 | [x] | `filter_extractor.py` |
| S37-P2-2 | wiki_search 스킬 경로 필터 통합 | [x] | `skills/wiki_search.py` |
| S37-P3-1 | `_detect_path_ambiguity()` 경로 분산 분석 | [x] | `rag_agent.py` |
| S37-P3-2 | _handle_qa() 명확화 이벤트 발행 통합 | [x] | `rag_agent.py` |
| S37-P3-3 | `clarification_response_id` 활성화 + 경로 재검색 | [x] | `api/agent.py` |
| S37-P3-4 | 세션 `path_preferences` 누적 | [x] | `session.py`, `context.py` |
| S37-P4-1 | `_path_boost_rerank()` 경로 부스트 리랭크 | [x] | `rag_agent.py` |
| S37-P4-2 | _handle_qa() 리랭크 통합 | [x] | `rag_agent.py` |
| S37-E1 | 평가 + 회귀 테스트 | [x] | `tests/test_rag_tag_boost.py` 회귀 통과 |
| S37-E2 | 브라우저 E2E 검증 | [x] | 사용자 데모 확인 완료 |
| S37-DOC | 문서 동기화 (CHANGES, demo_guide, HANDOFF) | [x] | `toClaude/` |

## 세션 37 버그 수정

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| S37-BF1 | 스킬 무시 버튼 무효 — `dismissed_skills` 프론트→백 전달 | [x] | `schemas.py`, `api/agent.py`, `sseClient.ts`, `AICopilot.tsx` |
| S37-BF2 | 사이드바 스킬 목록 미표시 — FastAPI `redirect_slashes` + 라우트 slash 충돌 | [x] | `main.py`, `api/skill.py` |
| S37-BF3 | 보안-점검-도우미 스킬 frontmatter 누락 (`type: skill`, `trigger`) | [x] | `wiki/_skills/보안/보안-점검-도우미.md` |
| S37-BF4 | 채팅 첫 응답 지연 체감 — classify 전 즉시 thinking_step 이벤트 발행 | [x] | `api/agent.py` |

## Status Simplification + Lineage/Versioning Overhaul

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| SL-1 | Status 단순화 — review/미설정 제거, draft/approved/deprecated만 | [x] | `schemas.py`, `local_fs.py` |
| SL-2 | Approved 강등 — 내용 수정 시 자동 draft + undeprecate→draft | [x] | `wiki_service.py`, `conflict.py` |
| SL-3 | 프론트엔드 타입/드롭다운/뱃지 업데이트 | [x] | `wiki.ts`, `DocumentInfoDrawer.tsx`, `MetadataTagBar.tsx`, `DocumentInfoBar.tsx`, `DocumentGraph.tsx` |
| SL-4 | Scoring — review=70/unset=50 제거, draft 폴백 40 | [x] | `scoring_config.py`, `confidence.py` |
| SL-5 | MetadataIndex — status/supersedes/superseded_by 저장 + 역참조 인덱스 | [x] | `metadata_index.py`, `wiki_service.py`, `main.py` |
| SL-6 | Lineage 검증 — 자기참조/사이클/경쟁 대체/무후계 폐기 | [x] | `lineage_validator.py`, `wiki_service.py`, `api/wiki.py` |
| SL-7 | Deprecation 연쇄 — 충돌 자동 해결, deprecated 제외, 0건 폴백 | [x] | `wiki_service.py`, `metadata_index.py`, `wiki_search.py` |
| SL-8 | Version Chain API + Timeline UI | [x] | `api/wiki.py`, `VersionTimeline.tsx`, `LineageWidget.tsx` |
| SL-9 | Reference Integrity + Deprecation UX | [x] | `wiki_service.py`, `TreeNav.tsx`, `api/metadata.py` |
| SL-10 | Metadata Inheritance + Bulk Status | [x] | `api/wiki.py` |

---

## UI/UX Overhaul — Content-First Layout

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| UX-1 | TreeNav 접기 — collapsible prop, Cmd+B, 아이콘 스트립, localStorage 유지 | [x] | `app/page.tsx` |
| UX-2 | AICopilot 접기 — 동일 패턴, Cmd+J | [x] | `app/page.tsx` |
| UX-3 | DocumentInfoBar — 32px 단일 행 통합 정보 바 | [x] | `editors/DocumentInfoBar.tsx` |
| UX-4 | DocumentInfoDrawer — 3탭 overlay drawer, Cmd+I | [x] | `editors/DocumentInfoDrawer.tsx` |
| UX-5 | MarkdownEditor 리팩토링 — 3개 스택 컴포넌트 → InfoBar+InfoDrawer 교체 | [x] | `editors/MarkdownEditor.tsx` |
| UX-6 | AI 팝아웃 — floating window 분리, 드래그/리사이즈, dock back, Cmd+J 토글 | [x] | `app/page.tsx` |

---

## Part 2 — 충돌 & Lineage

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P2-2A | Lineage 사이클 감지 — visited set + warning 로그 | [x] | `rag_agent.py` |
| P2-2C-BE | 검색 결과 deprecated 뱃지 — SourceRef에 superseded_by 필드, deprecated 소스 포함 | [x] | `schemas.py`, `rag_agent.py`, `sseClient.ts` |
| P2-2C-FE | deprecated "폐기됨" 뱃지 + "→ 새 버전" 링크 | [x] | `AICopilot.tsx` |
| P2-2B-BE | 폐기 되돌리기 API — POST /api/conflict/undeprecate | [x] | `api/conflict.py` |
| P2-2B-FE | ConflictDashboard deprecated 문서 "되돌리기" 버튼 | [x] | `ConflictDashboard.tsx` |
| P2-2D | 충돌 쌍 그룹핑 — 같은 file_a 공유 쌍을 그룹 렌더링 | [x] | `ConflictDashboard.tsx` |
| P2-REDIS | 충돌 스캔 결과 Redis 영속화 + 기본 threshold 0.85 | [x] | `.env`, `conflict_service.py` |
| P2-FIX1 | VersionTimeline `wiki:lineage-changed` 이벤트 리스너 — 폐기 되돌리기 후 타임라인 자동 갱신 | [x] | `VersionTimeline.tsx` |
| P2-FIX2 | `_clear_stale_lineage_refs` MetadataIndex 갱신 누락 수정 — version-chain API stale 데이터 버그 | [x] | `wiki_service.py` |

## 스코어링 중앙화 + UX 개선 (세션 39)

| # | Task | 상태 | 파일 |
|---|------|------|------|
| S-1 | scoring_config.py 중앙 설정 생성 | [x] | `trust/scoring_config.py` |
| S-2 | confidence.py → SCORING 참조 리팩터 | [x] | `trust/confidence.py` |
| S-3 | search.py min_similarity 0.5→0.7 + composite 중앙화 | [x] | `api/search.py` |
| S-4 | rag_agent.py boost floor 중앙화 | [x] | `rag_agent.py` |
| S-5 | conflict_service.py 임계값 중앙화 | [x] | `conflict_service.py` |
| S-6 | wiki_service.py auto_suggest 임계값 중앙화 | [x] | `wiki_service.py` |
| U-1 | LinkedDocsPanel 기본 2건 + 더 보기 토글 | [x] | `LinkedDocsPanel.tsx` |
| E-1 | GET /api/wiki/scoring-config 투명성 API | [x] | `api/wiki.py` |
| V-1 | 신뢰도 pill 클릭 시 시그널 상세 팝오버 | [x] | `MarkdownEditor.tsx` |
| V-2 | ScoringDashboard 관리자 페이지 | [x] | `ScoringDashboard.tsx`, `TreeNav.tsx`, `FileRouter.tsx` |
| V-3 | AI소스 뱃지 툴팁 강화 (해석 메시지) | [x] | `AICopilot.tsx` |

## Trust System Phase 3 — 읽기 시 맥락

| # | Task | 상태 | 파일 |
|---|------|------|------|
| P3-1 | CitationTracker (Redis/InMemory) | [x] | `trust/citation_tracker.py`, `rag_agent.py` |
| P3-2 | ConfidenceResult 확장 (citation_count, newer_alternatives) | [x] | `trust/confidence.py`, `trust/confidence_service.py` |
| P3-3 | TrustBanner 컴포넌트 | [x] | `TrustBanner.tsx`, `MarkdownEditor.tsx` |
| P3-4 | 와이어링 (main.py) | [x] | `main.py` |
| P3-5 | 단위 테스트 14개 | [x] | `tests/test_phase3_trust.py` |

## Trust System Phase 1 — Document Confidence Score

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| T1-1 | ConfidenceScorer 엔진 (신뢰도 0-100 계산) | [x] | `trust/confidence.py`, `trust/confidence_cache.py`, `trust/confidence_service.py` |
| T1-2 | Confidence API 엔드포인트 | [x] | `api/wiki.py` — GET /confidence/{path}, /confidence-batch |
| T1-3 | RAG 랭킹 통합 (신뢰도 기반 mild boost) | [x] | `rag_agent.py`, `schemas.py` — SourceRef 확장 |
| T1-4 | 프론트엔드 신뢰도 뱃지 | [x] | `AICopilot.tsx` (소스 dot), `MarkdownEditor.tsx` (헤더 pill), `sseClient.ts` |
| T1-5 | 와이어링 + 테스트 + 문서 | [x] | `main.py`, `tests/test_confidence.py` (28 pass) |

## Trust System Phase 2 — Write-Time Related Document Nudge

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| T2-1 | 관련 문서 API (`GET /api/search/related`) | [x] | `api/search.py`, `schemas.py` (RelatedDocResult) |
| T2-2 | LinkedDocsPanel AI 추천 섹션 | [x] | `LinkedDocsPanel.tsx` — "참고할 만한 문서" 섹션 |
| T2-3 | 저장 시 자동 related 제안 | [x] | `wiki_service.py` — _auto_suggest_related() |
| T2-4 | 와이어링 + 테스트 + 문서 | [x] | `main.py`, `tests/test_related_search.py` (12 pass) |

## Trust System Phase 4 — Smart Conflict Resolution

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P4-1 | TypedConflict 모델 + ConflictAnalysis LLM 모델 | [x] | `schemas.py`, `models.py` |
| P4-2 | analyze_pair() + StoredConflict 확장 | [x] | `conflict_check.py`, `conflict_store.py`, `prompts/conflict_analyze_pair.md` |
| P4-3 | 해결 액션 API (resolve, typed, analyze-pair) | [x] | `api/conflict.py`, `conflict_service.py` |
| P4-4 | ConflictDashboard 유형 뱃지 + 해결 버튼 UI | [x] | `ConflictDashboard.tsx`, `TreeNav.tsx`, `useWorkspaceStore.ts` |
| P4-5 | 관리 다이제스트 (BE + FE) | [x] | `trust/digest.py`, `MaintenanceDigest.tsx`, `FileRouter.tsx`, `main.py` |
| P4-6 | 테스트 + 문서 업데이트 | [x] | `tests/test_phase4_smart_conflict.py` (13 pass) |

## User-Driven Self-Healing — Phase A: Foundation Fixes

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| PA-1 | MetadataIndex에 updated/updated_by/created_by/related 필드 추가 | [x] | `metadata_index.py` — on_file_saved() 확장, rebuild() extended kwarg 지원 |
| PA-2 | _get_backlink_count 버그 수정 (항상 0 반환 → related 기반 카운팅) | [x] | `confidence_service.py:191-208` |
| PA-3 | _is_owner_active 버그 수정 (항상 False → updated_by/updated 기반 체크) | [x] | `confidence_service.py:210-243` |
| PA-4 | 프론트엔드 사용자 ID를 백엔드 인증과 연결 | [x] | `auth/currentUser.ts`, `AuthContext.tsx`, `lockManager.ts`, `MarkdownEditor.tsx`, `api/auth.py` |
| PA-5 | Phase A 테스트 작성 및 검증 | [x] | `tests/test_phase_a_confidence_signals.py` (16 pass) |

## User-Driven Self-Healing — Phase B: User Feedback Loop

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| PB-1 | FeedbackTracker 백엔드 (InMemory + Redis) | [x] | `trust/feedback_tracker.py` — FeedbackTracker, InMemory/RedisFeedbackStore, FeedbackSummary |
| PB-2 | Feedback API 엔드포인트 | [x] | `api/wiki.py` — POST/GET /api/wiki/feedback/{path}, main.py 와이어링 |
| PB-3 | TrustBanner 피드백 버튼 | [x] | `TrustBanner.tsx` — "확인했음"/"수정 필요" 버튼 + 피드백 카운트 표시 |
| PB-4 | AICopilot 소스 thumbs | [x] | `AICopilot.tsx` — 소스 카드 옆 thumbs up/down 버튼 |
| PB-5 | Phase B 테스트 | [x] | `tests/test_phase_b_feedback.py` (12 pass) |

## User-Driven Self-Healing — Phase C: Score Integration

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| PC-1 | Confidence 시그널 가중치 재조정 + user_feedback 추가 | [x] | `scoring_config.py` (freshness 25, backlinks 10, owner 10, user_feedback 15), `confidence.py` (_score_user_feedback + compute_confidence 확장) |
| PC-2 | ConfidenceService 피드백 연동 | [x] | `confidence_service.py` (set_feedback_tracker, _get_feedback_counts), `main.py` 와이어링 순서 수정 |
| PC-3 | "확인했음" → freshness 갱신 | [x] | `api/wiki.py` (_refresh_document_timestamp: verified 시 updated/updated_by frontmatter 갱신) |
| PC-4 | Phase C 테스트 | [x] | `tests/test_phase_c_score_integration.py` (20 pass) |

## User-Driven Self-Healing — Phase D: Knowledge Graph Unification

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| PD-1 | Relationship 모델 + GraphStore | [x] | `core/schemas.py` (Relationship, GraphResult, GraphStats), `graph/graph_store.py` (InMemory + Redis) |
| PD-2 | GraphBuilder | [x] | `graph/graph_builder.py` — metadata.related/supersedes → related/supersedes, ConflictStore → conflicts |
| PD-3 | Graph API + main.py 와이어링 | [x] | `api/graph.py` (GET /api/graph/{path}, GET /api/graph/stats), main.py 초기화 + tree_change 연동 |
| PD-4 | Phase D 테스트 | [x] | `tests/test_phase_d_knowledge_graph.py` (22 pass) |

---

## ACL Domain Scoping (기업용 접근 권한 고도화)

> 단일 풀 개인위키 → 기업용 ECM 변환. 개인 공간, 세밀한 ACL, ChromaDB access_scope, 사이드바 구조화.
> 브랜치: `feat/acl-domain-scoping` | 16 commits | 100 tests

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| ACL-1 | User 모델 확장 + Group 모델 & GroupStore | [x] | `auth/models.py`, `auth/group_store.py`, `data/users.json` |
| ACL-2 | ACL Store v2 (default-deny, owner/manage, inheritance) | [x] | `auth/acl_store.py` (31+2 tests) |
| ACL-3 | NoOpProvider 다중 사용자 — X-User-Id 헤더, 그룹 해석 | [x] | `auth/noop_provider.py` (17 tests) |
| ACL-4 | Access Scope 계산 모듈 — ChromaDB 필터용 | [x] | `auth/scope.py` (10 tests) |
| ACL-5 | ChromaDB 메타데이터 확장 — access_read/access_write 주입 | [x] | `wiki_indexer.py`, `wiki_service.py` |
| ACL-6 | 검색 ACL 스코핑 — search/RAG/conflict 사전 필터링 | [x] | `wiki_search.py`, `rag_agent.py`, `conflict_service.py` |
| ACL-7 | Group CRUD API + ACL API 확장 (manage 권한 체크) | [x] | `api/group.py`, `api/acl.py` (25 tests) |
| ACL-8 | main.py 통합 + acl_changed 이벤트 핸들러 | [x] | `main.py`, `event_bus.py` (async callback) |
| ACL-9 | Frontend 타입 + API 클라이언트 + useAuth 훅 | [x] | `types/auth.ts`, `lib/api/acl.ts`, `hooks/useAuth.ts` |
| ACL-10 | 공통 ContextMenu 컴포넌트 (뷰포트 보정) | [x] | `components/ContextMenu.tsx` |
| ACL-11 | ShareDialog + PropertiesPanel | [x] | `components/ShareDialog.tsx`, `components/PropertiesPanel.tsx` |
| ACL-12 | TreeNav 섹션 분리 (내 문서/위키/스킬) + ACL 아이콘 | [x] | `components/TreeNav.tsx` |
| ACL-13 | Backend tree API ACL 필터링 + 개인 공간 엔드포인트 | [x] | `api/wiki.py`, `core/schemas.py` |
| ACL-14 | 마이그레이션 스크립트 | [x] | `scripts/migrate_acl.py` |
| ACL-15 | 통합 검증 + 디렉터리 경로 해석 버그 수정 | [x] | 100 tests pass, TS clean, E2E API 검증 |

### Part 3: 엔드포인트 권한 강화

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P3-A | require_admin + 미보호 엔드포인트 권한 적용 | [x] | `permission.py`, `api/wiki.py` |
| P3-B | 스킬 CRUD 권한 (personal=본인, shared delete=admin) | [x] | `api/skill.py` |
| P3-C | 프론트엔드 권한 기반 UI 분기 (메뉴 숨김 + 읽기전용 배너) | [x] | `TreeNav.tsx`, `MarkdownEditor.tsx` |

### Part 2: 충돌 & Lineage 보강

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P2-A | Lineage 사이클 감지 (visited set + break) | [x] | `rag_agent.py` (기존 구현) |
| P2-B | 폐기 되돌리기 (POST /undeprecate + 되돌리기 버튼) | [x] | `api/conflict.py`, `ConflictDashboard.tsx` (기존 구현) |
| P2-C | 검색 결과 deprecated 뱃지 + 새 버전 링크 | [x] | `AICopilot.tsx` (기존 구현) |
| P2-D | 충돌 쌍 그룹핑 (GET /grouped + hot files 요약) | [x] | `conflict_service.py`, `api/conflict.py`, `ConflictDashboard.tsx` |

---

## Image Search (위키 이미지 검색 가능화)

> 이미지(스크린샷, 대화 캡처, 에러 화면)에서 텍스트 추출 + 맥락 설명 생성 → 검색/RAG 파이프라인 통합
> 브랜치: `main` | 11 commits | 30 tests | 설계: `docs/superpowers/specs/2026-04-16-image-search-design.md`

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| IMG-1 | Data models + sidecar I/O | [x] | `backend/application/image/models.py` |
| IMG-2 | OCR engine (EasyOCR wrapper) | [x] | `backend/application/image/ocr_engine.py` |
| IMG-3 | Vision provider abstraction (noop/ollama) | [x] | `backend/application/image/vision_provider.py` |
| IMG-4 | ImageAnalyzer orchestrator + sidecar caching | [x] | `backend/application/image/analyzer.py` |
| IMG-5 | Configuration settings (8 env vars) | [x] | `backend/core/config.py` |
| IMG-6 | Indexer integration (enrich_chunk_with_images) | [x] | `backend/application/wiki/wiki_indexer.py` |
| IMG-7 | Background processing queue (asyncio.Semaphore) | [x] | `backend/application/image/queue.py` |
| IMG-8 | WikiService + main.py wiring | [x] | `wiki_service.py`, `main.py` |
| IMG-9 | Backfill CLI (--dry-run, --ocr-only, --vision-only, --workers) | [x] | `backend/cli/backfill_images.py` |
| IMG-10 | E2E integration tests | [x] | `tests/test_image_analysis.py` |
| IMG-FIX | Code review fixes (URL filter, parallel workers, dedup check) | [x] | queue.py, wiki_indexer.py, backfill_images.py |

---

## Image Management (위키 이미지 관리 시스템)

> SHA-256 해시 중복 제거 + fabric.js 어노테이션 + 관리자 갤러리
> 브랜치: `main` | 설계: `docs/superpowers/specs/2026-04-17-image-management-design.md`
> 플랜: `docs/superpowers/plans/2026-04-17-image-management.md`

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| IMGM-1 | ImageRegistry core (hash index + ref counting + scan) | [x] | `backend/application/image/image_registry.py` |
| IMGM-2 | Source field on ImageAnalysis sidecar | [x] | `backend/application/image/models.py` |
| IMGM-3 | Upload SHA-256 hash dedup | [x] | `backend/api/files.py` |
| IMGM-4 | Registry init + event handlers in main.py | [x] | `backend/main.py` |
| IMGM-5 | Ref tracking on document save (diff old/new) | [x] | `backend/application/wiki/wiki_service.py` |
| IMGM-6 | Admin API (stats, paginated list, delete, bulk-delete) | [x] | `backend/api/files.py` |
| IMGM-7 | OCR inheritance endpoint | [x] | `backend/api/files.py` |
| IMGM-8 | fabric.js install + ImageCopyExtension (Ctrl+C + context menu) | [x] | `pasteHandler.ts`, `MarkdownEditor.tsx` |
| IMGM-9 | ImageViewerModal (fullscreen + annotation editor) | [x] | `ImageViewerModal.tsx` |
| IMGM-10 | ImageManagementPage (admin gallery + pagination + bulk delete) | [x] | `ImageManagementPage.tsx` |
| IMGM-11 | Routing + types + admin gate | [x] | `workspace.ts`, `useWorkspaceStore.ts`, `FileRouter.tsx`, `TreeNav.tsx` |

---

## Phase 3 — slab-design-real Wiring (ACTIVE, 2026-05-01~)

> 데모 repo: `sample-repos/slab-design-real` (122 Java, 4-module Maven, 21-step SCM 알고리즘).
> 분석: `toClaude/modeling/p3_demo_repo_analysis.md` + `p3_order_mapping.md`.

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P3-1 | slab-design-real 깊이 파악 (도메인/모듈/Action 후보) | [x] | `p3_demo_repo_analysis.md`, `p3_order_mapping.md` |
| P3-2 | Repo Import 백엔드 (Importer + REST + SSE) | [x] | `code_layer/importer.py`, `code_layer/adapter.py` (sig+dedup), `code_layer/role_classifier.py` (Jpo→INFRA), `code_layer/callsite_analyzer.py` (caller fqn 정합), `api/repo_import.py`, `persistence/database.py` (FK pragma), `main.py` |
| P3-3 | 자동 매핑 추천 — Action/Term/TypeRealization 후보 | [x] | `code_layer/recommender.py` (slab glossary + ActionKind 휴리스틱 + Entity⊃Jpo PARTIAL 자동 검출), `api/recommend_api.py` (`POST /repos/{id}/recommend?persist=true&min_confidence=0.7`), `main.py`. 결과: 29 BusinessTerm (12@conf1.0) + 36 Action (29 declared_on_term 자동) + 34 TypeRealization (29 PRIMARY + 5 PARTIAL = SDOrderEntity⊃{OS,OM,Chemical,QD} + SDSlabEntity⊃SlabResult). |
| P3-4 | Frontend Repo Import UI | [x] | `frontend/src/lib/api/ontology.ts` (startRepoImport / streamRepoImportProgress(EventSource) / getRepoImportStatus / recommendForRepo + 4 신규 DTO), `components/sections/modeling/RepoImportModal.tsx` (form → SSE 진행률 → 자동 recommend persist → done 카드), `TopBar.tsx` Import 버튼. 폴백: SSE 끊기면 status poll 자동 전환. tsc clean. |
| P3-5 | xyflow + dagre 자동 layout (Graph mode) | [x] | `backend/modeling/api/graph_api.py` (`GET /repos/{id}/graph?focus_fqn=&hops=`, BFS subgraph + 600 노드 hard cap), `frontend/src/lib/api/ontology.ts` (`getOntologyGraph` + DTO 4종), `frontend/src/components/sections/modeling/OntologyGraph.tsx` (xyflow + dagre LR + 검색→focus + hops 1~4 + minimap + custom node + 엣지 색상별 PRIMARY/PARTIAL/realization), `GraphMode.tsx` L3 view 교체 + 키보드 가드 (input 입력 시 1~5 단축키 무발화). |
| P3-6 | 매핑 큐 액션 — confirm / reject | [x] | `backend/modeling/api/queue_actions_api.py` (`GET /repos/{id}/queue` 통합 + 6 confirm/reject endpoint, Term/Action/Realization). 큐는 `confirmed=False` 만. confirm 시 Action verification draft → signature_locked 자동 진행. reject 시 Term 거절은 의존 Realization 도 cascade 정리. `frontend/src/lib/api/ontology.ts` (7 메서드 + 5 DTO). `LeftPanel.tsx` QueueTab 재구성 — 4-section tab (Term/Action/Real/Code legacy) + 카운트 배지 + 행별 confirm/reject 버튼 + optimistic UI (실패 시 reload). |
| P3-7 | 데모 시나리오 (S1/S5/S6) 끝-끝 브라우저 검증 + UX fix | [x] | 헤드리스 Chromium 으로 Import → Graph → 큐 confirm 풀 사이클 검증. 발견된 UX 이슈 6건 fix: ① `store.ts` default repo "scm" → "slab-design-real" (페이지 reload 후 빈 그래프 발생 회피), ② `OntologyGraph.tsx` LR → TB layout (188 노드 가독성), ③ `graph_api.py` `connected_only=true` default 추가 (isolated 70 framework code_type 제외 → 117 노드), ④ 데이터 로드 후 가장 connected term/action 자동 focus + hops=2 (스타형 그래프 첫 진입 임팩트 ↑), ⑤ ReactFlow `key` prop 으로 focus 변경 시 remount → fitView 재실행, ⑥ `GraphMode.tsx` 키보드 안내 카드 L3 (실제 그래프) 에서 숨김 (minimap 과 겹침). 검증: Import 353ms→done 카드, 자동 매핑 99 적재, 그래프 자동 focus 7 노드 가시화 (SDOrderEntity ⊃ 4 PARTIAL amber 점선 ★ 드라마 DNA), 큐 ✓ 클릭 → optimistic UI + 백엔드 28/36/34 정합. tsc clean. |

---

## Round 4 — Palantir 심층 조사 (2026-05-02)

> 사용자 피드백 7번 (prior art 리서치) 의 결과물.
> 산출: `round4/palantir-sources.md` · `palantir-raw-notes.md` · `palantir-schema-vs-ontong.md` · `palantir-ux-catalog.md` · `graph-viz-patterns.md` · `decisions.html` · `round4-palantir-deep-dive.html` (종합 보고서)

### Stage 1~4 (조사 + 결정)
| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| R4-S1 | Stage 1 sweep — 40 sources 인덱스 + 7 영역 raw notes | [x] | `round4/palantir-sources.md`, `palantir-raw-notes.md` |
| R4-S2 | Stage 2 schema deep-dive — 11 섹션 side-by-side, 5 의문점 (3 완전 + 2 부분) | [x] | `round4/palantir-schema-vs-ontong.md` |
| R4-S3 | Stage 3 UX + graph viz catalog — Foundry 11 화면 + 외부 5 ref + adoption matrix 38행 | [x] | `round4/palantir-ux-catalog.md`, `graph-viz-patterns.md` |
| R4-S4 | Stage 4 7 안건 결정 회의 (HTML 토론 페이지) | [x] | `round4/decisions.html` (입력 가능 form + 복사 버튼) |
| R4-S4-종합 | 종합 보고서 — 한 페이지 요약 + 7 안건 + 차별 강점 / 빠뜨린 facet + 3-track backlog + 미적용 항목 | [x] | `round4-palantir-deep-dive.html` |

### Track 1 — 인프라 검증 (실측 evidence)
| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| R4-T1.1 | 117 → 5K 인공 가공 generator script + perf 측정 + bottleneck fix | [x] | `scripts/synthesize_5k_repo.py` (기존 repo 41× cloning, 5043 CodeType + 1189 Term + 1476 Action + 1394 TypeRealization in 5.7s). **6 metric 측정**: graph cluster 1.85s → **180ms**, modules **15s → 140ms** (108x). bottleneck 3종 fix: ① modules N+1 (`list_type_realizations` per-CodeType → 1회 fetch + in-memory lookup), ② mapping N+1 (`list_actions` per-Action realizations → 1 query in_() group), ③ `list_types_summary` 신규 (method body_text 안 로드, ~10x faster). graph_api + modules_api 둘 다 summary 사용. 회귀 테스트 95/97 PASS (2 fail 은 사전 존재 — FK pragma 영향, 무관). |
| R4-T1.2 | ELK PoC (xyflow + ELK 통합) — 117 + 5K layout 시간 측정 | [x] | `frontend/src/app/elk-spike/page.tsx` 신규 (repo×layout×compound 토글 + layout 시간 표시), `elkjs` 설치 + `public/elk-worker.min.js` 배치, dynamic import 로 web-worker 의존 우회. **결과**: 117@dagre 13ms, 117@elk-layered+compound 142ms, 5K(cap 600)@dagre 24ms, 5K@elk-layered flat 56ms, 5K@elk-layered+compound 88ms. 둘 다 sub-200ms 합격선. ELK 만 compound 지원. |
| R4-T1.3 | 안건 1 micro-decision (풀 마이그 / hybrid / dagre 유지) | [x] | **결정: B 풀 ELK 마이그**. production `OntologyGraph.tsx` 의 dagre → ELK Layered 교체. dynamic import (`elkjs/lib/elk-api.js`) + `public/elk-worker.min.js`. async layout (useEffect + useState). Loading 표시 추가. 검증: 117 노드 deep link → 정상 (10 node + 9 edge, PARTIAL drama DNA 시각). dagre dep 는 spike 페이지 만 유지. tsc clean. |
| R4-T1.4 | Spring Framework 정식 검증 — 6 metric 측정 (안건 6C) | [ ] | 측정 결과 노트 + bottleneck follow-up backlog |

### Track 2 — UX 빠른 가치 (안건 3 + 2 + 5)
| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| R4-T2.1 | NodePreviewPanel.tsx — 그래프 모드 노드 클릭 → bottom slide-up 240px | [x] | `frontend/src/components/sections/modeling/NodePreviewPanel.tsx` 신규 + `OntologyGraph.tsx` 통합. 헤더 (kind dot/라벨/pin/close), 2-col body (좌 FQN/role/domain/verification/confirmed, 우 1-hop neighbors + edge kinds + kind detail), footer (이 노드 중심 / Detail 모드 열기 + Term/Action 큐 확정/거절 conditional). pin 시 다른 노드 클릭해도 갈아치움 X. 큐 mutation 후 reloadTick 으로 graph reload. tsc clean. ValidationResult 클릭 검증 OK (1 Term + 2 Action neighbor, 1 PRIMARY + 2 impl, 7 methods). |
| R4-T2.2 | Perspective backend entity (안건 2 B) — Pydantic + ORM + REST CRUD | [x] | 새 layer `backend/modeling/view_layer/` (`schema.py` Perspective + PerspectiveSpec, `orm.py` PerspectiveRow, `store.py` ViewLayerStore CRUD). REST `backend/modeling/api/perspective_api.py` (LIST/POST/GET/PUT/DELETE 5 endpoint, repo isolation 검증). `main.py` ORM 등록 + router. `tests/view_layer/test_store.py` 5/5 PASS (create/get/list/update/delete/repo isolation/id validation). curl 5-step lifecycle 검증 OK (Next proxy 통과). 1차 read-only public, owner_id 만 future ACL prep. |
| R4-T2.3 | URL state sync (안건 5 B) — useSearchParams ↔ store 양방향 sync | [x] | `useUrlSync.ts` 훅 (page.tsx 최상단 mount, workspace section + repo + graph mode/focus/target/n_max + perspective_id 양방향 sync, 200ms debounce, router.replace history 안 쌓음). store 에 graph state lift (`graphMode`/`graphFocus`/`graphTarget`/`graphNMax`/`activePerspectiveId` + `applyGraphState`). API client `getPerspective` + 4 메서드. OntologyGraph 「URL」 복사 버튼. **검증**: deep link `?section=modeling&view=graph&focus=...&n_max=80&repo=...` 새 탭에서 자동 진입 → 10 노드 (SDOrderEntity ⊃ 4 PARTIAL) 시각화. 새로고침 후 state 완전 복원. |

### Track 3 — 통합 마무리 (Track 1+2 합류)
| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| R4-T3.1 | graph_api 5-kind 확장 (안건 4 C) — Domain emit + CONTAINS edge + Term split | [x] | `graph_api.py` GraphNodeKind +"domain", GraphEdgeKind +"contains". Domain 노드 emit (직접 클래스 가진 Java 패키지만, id `pkg::{fqn}`, label = 마지막 segment, extra: class_count + members). CONTAINS edge: Domain → CodeType. summary 에 nodes_domain. include_kinds default 5종. **검증**: slab-design-real 5K — 222 nodes (123 code + 29 term + 36 action + **34 domain**), 192 edges (incl 123 contains). focus 시: 15 nodes (7 term + 6 code + 0 action + 2 pkg). |
| R4-T3.2 | frontend 5-kind 시각 컴포넌트 — kind 별 모양/색/크기 spec | [x] | `ontology.ts` GraphNodeKind +"domain" + GraphEdgeKind +"contains". `OntologyGraph.tsx`: KIND_COLOR domain=slate, OntologyNode 가 atomic term=pill / domain=dashed border + 📦 prefix. nodeSubtitle 5-kind 분기 (term: composite·root/atomic, domain: 패키지 · N class). edgeKindColor contains=slate. NodeBadge Pkg toolbar 표시. NodePreviewPanel KIND_COLOR/LABEL_KO domain 추가. |
| R4-T3.3 | Domain compound (안건 1 B = 풀 ELK 활용) — 패키지 box 안에 자식 CodeType nest | [x] | store 에 `graphCompound` state + setter. `OntologyGraph.tsx` `buildLayout` compound 분기 (Domain 노드 children 으로 멤버 nest, contains edge 제외). `DomainGroupNode` 컴포넌트 (slate dashed border + 📦 헤더 + class count). toolbar 에 `[v] 패키지 묶음` 토글. `useUrlSync.ts` `?compound=1` 양방향 sync. **검증**: deep link `?compound=1` → 2 group box (entity / jpo) 안에 자식 CodeType nest, PARTIAL/PRIMARY edge 가 cross-package 로 자연스럽게 표현 (drama DNA 더 명확). |
| R4-T3.4 | Perspective ↔ 5 kind 통합 — visible kinds + edge + lens + filter + layout 묶음 저장 | [x] | Backend `view_layer/schema.py` PerspectiveSpec 에 `compound: bool` 추가 + `visible_kinds` default 5종 (+domain) + `visible_edge_kinds` default 7종 (+contains). Frontend `ontology.ts` PerspectiveSpecDTO 에 compound 필드. `useUrlSync.ts` 가 saved perspective fetch 시 compound 도 적용. `PerspectiveDropdown.tsx` 신규 — toolbar 한 칸 dropdown (저장된 view 목록 + 적용 + 「현 view 저장」 prompt + 삭제 + active 해제). active 상태 violet 강조. `OntologyGraph.tsx` toolbar 통합. **검증**: `?p=1` deep link → spec.compound=true 자동 적용 (✓ 패키지 묶음 체크) + focus 적용 + 2 group box 시각, dropdown 이름 정상 표시. |

### 다음 phase 보류
- Schema migration framework (Foundry 8-option) — 가장 큰 빈 영역
- Action SemVer + 자동 호환성 검사 (A2 Agent 입력)
- Action description → LLM tool spec 자동 변환 (A2 Agent)
- 6번째 노드 kind: Method (zoom-in mode)
- Perspective 권한 (ACL) + share token
- Branching / Proposal 흐름
- Hover preview / mini-graph
- Time-travel / graph diff

---

## Round 6 — Authoring Agent Graph 아키텍처 (2026-05-05)

> 사용자 결정: Authoring agent 가 raw text 가 아닌 Code+Ontology+Mapping graph 를 ReAct 루프로 직접 탐색.
> 분석 문서: `agent-graph-architecture.html`. 메모리: `project_authoring_graph_agent.md`.
> 확정: ReAct=B(forced reflection) / trace=β+γ / ontology=S(즉시) / cost=cap 당 hard max_calls + 세션 알림 / 권한=HTML §3 표.

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| R6-INF-1 | Agent tool registry — 23개 tool in-process Python 함수 + pydantic_ai `tool_plain` + per-cap allowlist + cross-cutting 위치 | [x] | `backend/application/agent_tools/{__init__,tracking,code_tools,ontology_tools,mapping_tools,operational,registry}.py` (cross-cutting). 23 tools: Code 12 + Ontology 6 + Mapping 3 + Operational 2. PRESETS 5 (authoring_full/extract/hypothesize/pattern_check/naming). `tests/test_agent_tools_registry.py` 10 PASS, `tests/test_agent_tools_graph_queries.py` 17 PASS (실 DB). |
| R6-INF-2 | Tool 호출 cost / trace logging — AuthoringToolCallRow + log_tool_call + Authoring 측 adapter (Logger + OperationalSession) | [x] | `application/authoring/orm.py` AuthoringToolCallRow 신규, `cost.py` log_tool_call 확장, `agent_tool_adapter.py` 신규 (AuthoringToolLogger / AuthoringOperationalSession / build_run_tracker / build_operational_session / list_tool_calls_for_session). `tests/test_agent_tool_adapter.py` 4 PASS. `authoring_tool_call_log` 테이블 자동 생성 확인. |
| R6-INF-3 | SSE 이벤트 — `tool_call_start` / `tool_call_end` + `/options/stream` + `/gaps/stream` + `/tool-calls` (γ trace 조회) endpoint | [x] | `agent_tools/sse.py` ToolEventPump + sse_format, `api/authoring.py` 3 신규 endpoint, `frontend/src/lib/api/authoring.ts` postSSE generator + ToolStreamEvent + ToolCallRow + 3 메서드. tests `test_agent_tools_sse.py` 4 PASS, `test_authoring_sse_endpoints.py` 3 PASS. |
| R6-INF-4 | ReAct 루프 forced reflection — `RunTracker.reflect_every` (default 5). N마다 tool 결과를 `{result, _system_note}` 로 wrap 하여 LLM 이 정리·결정 step 강제 | [x] | `agent_tools/tracking.py` reflect_every + wrap_with_reflect, prompt 룰 (gap_detection.md / option_proposal.md `# Tool use` 섹션). tests `test_run_tracker_forced_reflection_wraps_result` PASS. |
| R6-CAP-5 | Cap 5 (gap_detector) retro-fit — PRESET `authoring_full` (22 tool) + max_calls=12 + event_pump 인자 + per-call agent | [x] | `capabilities/gap_detector.py` retrofit, `prompts/gap_detection.md` Tool use 섹션. 회귀 8/8 PASS. |
| R6-CAP-6 | Cap 6 (option_proposer) retro-fit — PRESET `authoring_full` (22 tool) + max_calls=10 + event_pump 인자 + per-call agent | [x] | `capabilities/option_proposer.py` retrofit, `prompts/option_proposal.md` Tool use 섹션. 회귀 7/7 PASS. |
| R6-CAP-1 | Cap 1 (code_extractor) retro-fit — PRESET `authoring_extract` (5 tool: code_lookup/code_search/find_related_jpos/get_method_body/note_observation) + max_calls=5 + reflect_every=None (예산 작아 불필요) + event_pump 인자 + per-call agent | [x] | `capabilities/code_extractor.py` retrofit, `prompts/code_extraction.md` Tool use 섹션. SSE `/extract/stream` endpoint 신규. 회귀 7/7 PASS. |
| R6-CAP-2 | Cap 2 (hypothesis) retro-fit — PRESET `authoring_hypothesize` (10 tool, ontology+code+mapping+operational) + max_calls=8 + reflect_every=5 + event_pump 인자 + per-call agent | [x] | `capabilities/hypothesis.py` retrofit, `prompts/hypothesis.md` Tool use 섹션 (3-step recommended order: find_existing_mapping → find_related_jpos → domain_search). SSE `/hypothesize/stream` endpoint 신규. 회귀 6/6 PASS. |
| R6-CAP-7 | Cap 7 (pattern_checker) 신규 — greenfield ReAct + PRESET `authoring_pattern_check` (5 tool: domain_search/term_lookup/find_terms_in_domain/find_term_realizations/note_observation) + max_calls=6 + reflect_every=5. Schema: PatternCheck (findings + consistency_score + summary + recommendation). cap 6 (option_proposer) 다음, cap 8 (naming) 전 단계의 ontology-vs-ontology 일관성 검사. | [x] | `capabilities/pattern_checker.py` 신규, `prompts/pattern_check.md` 신규. SSE `/pattern/stream` + sync `/pattern` endpoint. Frontend: `PatternCheck` 타입 + `pattern` ChatKind + `runPatternCheck` action + `PatternView` 컴포넌트 (severity 색상 + alignment 배지 + recommendation 색상) + 툴바 ⑦ 패턴 버튼. tests `test_pattern_endpoint_returns_check`, `test_pattern_stream_emits_done` PASS. |
| R6-UI-1 | Tool trace 진행 spinner (β) — `🔍 phase 요약 … graph 탐색 중` ChatThread 위에 라이브 카드. SSE 이벤트 → `activeToolTrace` 상태 | [x] | `frontend/src/components/sections/modeling/authoring/store.ts` activeToolTrace + consumeStream + ToolStreamEvent 타입, `AuthoringMode.tsx` LiveToolTraceCard 컴포넌트. TS clean. |
| R6-UI-2 | Tool trace expandable (γ) — 결과 카드 footer `🔍 어떻게 알아냈나` 토글 → tool 시퀀스 + duration · cached · error | [x] | `AuthoringMode.tsx` ToolTraceToggle 컴포넌트, ChatBubble 통합. ChatMessage.toolTrace 필드 추가. TS clean. |
| R6-VAL | End-to-end 검증 — 자바독 strip 으로 cap 1+2+5+6+7 풀 사이클 + confidence 측정. **결과: cap 2 confidence -0.05 only (with doc 0.50 → blind 0.45)** — graph 가 docs 부재를 거의 완전 회복. cap 7 가 5 findings 정확히 잡아냄. 전체 LLM 비용 $6.34 (cold cache, 정상 세션은 $2-3). | [x] | `scripts/r6_validation.py`, `toClaude/modeling/r6_validation_report.md`, `r6_val_run.log`, `r6_val_summary.json`. 백엔드 재시작 → 21 routes 등록 (7 신규). 회귀 0. 세션 A(baseline)/B(blind) DB 영속화. |

### 정렬 메모
- Tool 카탈로그 23개 (Code 12 / Ontology 6 / Mapping 3 / Operational 2) — 시그니처는 `agent-graph-architecture.html` §2 참조
- Cap 별 max_calls: cap 5=12, cap 6=10, cap 2=8, cap 7=6, cap 1=5, cap 3·8=3, cap 4·9=0
- Ontology cold-start 대비: ontology tool 검색 결과 0개 → "ontology 비어있음" 명시 (false positive 회피)

---

## 🔴 다음 세션 첫 작업 (2026-05-05 세션 종료 시점)

> Round 5 식 풀 사이클 한 번 — Authoring AI 도구 다 만들어졌으니 사용자-Claude HTML 인터뷰로 entity 1개 (또는 multi) 끝까지 보내고 ontology 에 confirm.

### 시작점
- 첫 화면: `toClaude/modeling/next-session-cycle-start.html` (이 세션 종료 직전 작성)
- 첫 메모리: `project_round5_resume.md` (인덱스에 등록됨)
- 보류 시점: Round 5 Phase A.7.7 (Gap Inspector) + A.8 (Customer / Productivity)

### 결정해야 할 것 (사용자에게 물어봐서)
1. Entity 갈래: **G1** (Customer/Productivity 미진행) / **G2** (HrSpec 재실시 비교) / **G3** (신규)
2. 모드 갈래: **M1** (직접 HTML, LLM 0) / **M2** (Authoring AI 도구) / **M3** (하이브리드)
3. 스코프: 1 entity 또는 multi-entity (5+)

기본 추천: **G2 + M3** (HrSpec 재실시 + 하이브리드). 단 사용자 의도 확인 필수.

### 환경 점검 명령
```
curl -s http://localhost:8001/openapi.json | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('routes:', len([p for p in d.get('paths',{}) if 'authoring' in p]))
"
```
24+ 기대. 죽어있으면 backend 재시작:
```
pkill -f 'uvicorn backend.main:app' ; sleep 1
set -a && . ./.env && set +a && ./.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001 --log-level info &
```

### Round 6 — A: Demo-ready 마무리 (2026-05-05)

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| R6-CAP-10 | Next-step advisor — Sonnet, no graph tools, pure state policy. SessionStateSnapshot → NextStep (recommended_action 13종 / priority 3종 / reason_korean / alternatives). | [x] | `capabilities/next_step.py`, `prompts/next_step.md`, `/sessions/{id}/next-step` endpoint. Frontend: `runNextStep` action, `NextStepView` 컴포넌트, `⑩ 다음 단계` 툴바 버튼. |
| R6-UI-VERIFY | Browser e2e 검증 — `/browse` 로 Authoring 흐름 진입 + cap 1 + cap 2 트리거 + β 카드 시각 확인. | [x] | 스크린샷 `/tmp/r6_ui_during_extract.png` (cap 1 β), `/tmp/r6_cap2_during.png` (cap 2 β). 결과: cap 1+2 모두 β 카드 정상 렌더링. 작은 UX fix: "graph" → "그래프" (한국어 일관성). 한계: browse 서버 안정성 부족으로 cap 2 done state 시각 검증 안 됨 (γ trace 는 integration test 로 보증). |
| R6-DEMO-GUIDE | `demo_guide.md` 에 R6 흐름 섹션 추가. | [x] | 9단계 흐름 + β 진행 카드 설명 + γ trace 펼치기 + 검증 시나리오 + 비용 추정 (~$5-7 풀 사이클, warm cache 절반). |

---

## P1-a Multi-entity workflow (2026-05-05)

> 사용자 결정: 추천대로 (P1 Authoring 확장 진입). 한 세션 = 한 JPO 한계 해소.

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P1a-A | Frontend-only multi-entity v1 — 세션 안에서 여러 entity 연속 처리. `CompletedEntityCycle` + `startNextEntity()` action + `NextEntityButton` (violet, archive/confirm 후 active) + `CompletedEntitiesPreview` 사이드바. messages/turnNo/cost/session 은 keep. | [x] | `store.ts` (state + action + reset 갱신), `AuthoringMode.tsx` (NextEntityButton 툴바 우측, CompletedEntitiesPreview 우측 사이드바). 백엔드 무변경 (decisions/cost 이미 누적). TS clean, 142 PASS. |
| P1a-B | Backend session resume — `decision_kind` "next_entity_started" 추가 (cycle boundary marker). `replay.py` 가 decisions chronologically walk, cycle 별 current/completed 분리, persisted_fqns merge. API `GET /replay` + `POST /next-entity-marker`. Frontend `?authoring_session=<id>` URL 자동 trigger + ↻ 이어서 / 🔗 URL 버튼. | [x] | `application/authoring/session.py` (DecisionKind 확장), `replay.py` 신규, `api/authoring.py` 2 endpoint, `lib/api/authoring.ts` 3 타입 + 2 method, `store.ts` `resumeSession` action + `startNextEntity` 가 marker 호출, `AuthoringMode.tsx` `ResumeSessionButton` + `CopySessionUrlButton` + auto-resume `useEffect`. tests `test_authoring_replay.py` 5 PASS. |
| P1a-C | Smart next-entity 제안 — Cap 11 신규 (Sonnet). 5 signal (pk_overlap / same_package / uncovered_domain / frequent_caller / inheritance_chain). PRESET `authoring_pick_next` 6 tools. SSE β trace 지원. NextEntityView signal 별 색상 + confidence % + 「① 이 JPO 로 시작」 클릭. `⤳ 다음 Entity` 버튼이 자동 trigger (fire-and-forget). | [x] | `capabilities/next_entity.py`, `prompts/next_entity.md`, `agent_tools/registry.py` PRESET, `api/authoring.py` 2 endpoint, `lib/api/authoring.ts`, `store.ts`, `AuthoringMode.tsx` (NextEntityView + auto-trigger). 회귀 0 (146 PASS). Backend 재시작 → 24 routes. |
| P1a-D | Cap 7 cross-entity — pattern_check 가 completedEntities 입력으로 받아 세션 내 패턴 catch. PriorEntitySnapshot schema (10 필드) + prompt 룰 ("In-session priors are the strongest signal") + sync/stream endpoint 양쪽 forwarding + frontend store 가 completedEntities → priors 변환. | [x] | `capabilities/pattern_checker.py`, `prompts/pattern_check.md`, `api/authoring.py`, `lib/api/authoring.ts`, `store.ts`. 신규 4 PASS in `tests/test_authoring_pattern_checker_priors.py`. 회귀 0 (146 PASS). Backend 재시작 + openapi schema 검증 OK. |
| P1a-E | 종합 archive — Cap 12 신규 (Sonnet, no graph tools). EntitySnapshot 입력 → ComprehensiveArchiveBody (title/executive_summary/entity_sections/cross_cutting_observations/decisions_made/next_steps_korean) → Python `_render_markdown` 가 deterministic 마크다운 생성 (빈 섹션 skip). Frontend 「📚 종합 archive」 cyan 버튼 (≥1 entity 노출, ≥2 fully-active) + `ComprehensiveArchiveView` (react-markdown + .md 다운로드). | [x] | `capabilities/comprehensive_archive.py`, `prompts/comprehensive_archive.md`, `api/authoring.py` `/comprehensive-archive` endpoint, `lib/api/authoring.ts` 타입 6종, `store.ts` action, `AuthoringMode.tsx` 버튼 + view. tests `test_authoring_comprehensive_archive_render.py` 5 PASS. |
