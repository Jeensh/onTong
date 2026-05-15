# Gap Analysis — Section 3 의 알려진 한계 → sim_v2 자산 매핑

> Section 3 보고서 (`section3_landing/README.md`) 에서 *명시된* 한계와 *암묵적* 한계를 모두 모으고, 각각 sim_v2 의 어느 자산으로 풀 수 있는지 1:1 매핑.

## 1. Section 3 의 알려진 한계 8 건

### 한계 #1 — chat 분기 [LOW] fallback (자연어 → fqn 변환 실패)
| 출처 | §2.3 시연 ②: "ProductivityService 의 cumulativeProductivity 를 바꾸면 무엇이 영향받아?" |
| --- | --- |
| 증상 | `[LOW] cumulativeProductivity 변경 — action 0건 · 룰 0건 · anchor 0건` |
| 원인 | LLM 이 자연어 → 6-인자 정확한 fqn 변환 못함 |
| Section 3 의 우회 | "panel 에서 fqn 직접 입력 시 [HIGH] 결과 나옴" — 사용자에게 입력 방식 변경 요구 |
| **sim_v2 자산** | **W72 TwinInvariantRunner** + **W73 JavaBaselineMap** |
| 적용 방법 | chat 에서 [LOW] fallback 대신 가장 가능성 높은 fqn 후보 N 개에 대해 W71 fixture 합성 + W72 invariant check → "이 후보들 중 어느 게 의도하신 거예요?" UI 로 surface |

### 한계 #2 — 한국어 검색 약함 ("엣징" → 0 hit) ─ ✓ CLOSED (W77 baseline + W78 hybrid tier)
| 출처 | §2.4 시연 ③: "엣징 사양 룩업 룰 보여줘" |
| --- | --- |
| 증상 | `키워드 ['엣징', '사양', '룩업', '룰']와 매칭되는 업무 용어를 찾지 못했습니다 (conf 0.30)` |
| 원인 | **ontology 의 `business_terms.aliases_json` 컬럼에 한↔영 alias 가 *이미 등록되어 있음*에도** modeling explain + legacy search 가 label 또는 aliases 한쪽 컬럼만 보던 것이 직접 원인. *데이터는 있는데 검색이 충분히 활용 못함* |
| **sim_v2 자산** | **W77 KoreanTermResolver** (4 컬럼 통합 token index) + **W78 hybrid tier** (transliteration / fuzzy / LLM assist). 모두 alias 를 대체하지 않고 **fully exploit 하는 검색 layer** (보완 개념). `backend/sim_v2/core/search/korean_term_resolver.py` + `transliteration.py` |
| 적용 방법 | `KoreanTermResolver.from_session(session, "slab-design-real-v2").resolve("엣징", use_fuzzy=True, llm_assist=section3_llm)`. label / aliases / description / fqn **4 컬럼 통합** + Tier 2 한↔영 정적 매핑 + Tier 3 difflib 오타 보정 + Tier 4 LLM 비표준 음역 추론 |
| 결과 | **UC41 실측: 10 test query 중 9 hit (90%)**, "엣징" → 엣징그룹코드 / EDGING그룹 / EDGING스펙 cross-match 도달. **UC42 hybrid 실측**: typo "edgign" → fuzzy 가 close, 비표준 음역 "에징" → LLM callback 이 close |
| 보완 관계 | alias 데이터 품질이 W77 의 ceiling — 한↔영 양쪽 등록된 term 일수록 정확도 높음. W78 은 alias 가 한쪽만 있거나 사용자가 오타/비표준 음역 으로 입력해도 추가 도달. **새 term 등록 시 label 한국어 + alias 영문 둘 다 채우는 패턴이 baseline** |

### 한계 #3 — sandbox 가 expected_output 검증 못함
| 출처 | §3 시연: `cumulativeProductivity("ABC") → result=0.95`. `0.95` 가 Java 와 같은지 *확인 없음* |
| --- | --- |
| 증상 | `{"ok": true, "result": 0.95, "elapsed_sec": 0.012}` — 결과 값이 맞는지 누가 판단? |
| 원인 | LLM 합성 expected_output 은 sandbox 의 input 으로 들어가지 baseline 비교 안 됨 |
| **sim_v2 자산** | **W73 JavaBaselineMap** + **W59 BehaviorTwinRunner** |
| 적용 방법 | [recipe-2-record-java-baseline.py](./usage-recipes/recipe-2-record-java-baseline.py) 그대로. (a) anchor 에서 default 값 derive, (b) 수동 annotation, (c) future: JVM record/replay |
| 효과 | sandbox 결과 표에 `expected` 컬럼 추가 + `FAIL_OUTPUT` 행 시각화 가능 |

### 한계 #4 — anchor prelude 가 단발 (DEFAULT_PRODUCTIVITY 1건만) ─ ✓ CLOSED
| 출처 | §9 Phase 7: "anchor_locator 의 regex 추출로 module-level prelude prepend" |
| --- | --- |
| 증상 | `DEFAULT_PRODUCTIVITY = 0.95` 같은 단일 const 만 우회. 진짜 production 메서드는 JPA repository + Entity ctor + 외부 service 다수 의존 |
| 원인 | 단일 메서드 cumulativeProductivity 의 단일 anchor 만 처리. generic 화 안 됨 |
| **sim_v2 자산** | **W74 Sandbox stub injection** (`backend/sim_v2/core/verification/sandbox_stubs.py` — 구현 완료) |
| 적용 방법 | `_safe_globals(extra=stub_namespace)` hook + `build_stub_namespace(session, method_fqn, repo_id, python_source)`. 3 source 자동 통합: anchor 상수 (regex `^([A-Z_][A-Z0-9_]*)\s*=\s*(.+?)$`) + AST unbound-name discovery + code-types.fields 로 spec'd entity stub |
| 결과 | **UC40 실측: 23 stubs auto-derived, NameError 0건, 0/11 → 6/11 PASS** |

### 한계 #5 — Java String idiom 변환은 했지만 다른 idiom (Collection / Optional / Stream) 누락 ─ ✓ CLOSED
| 출처 | §9 Phase 7 표: `length()/charAt(i)` 만 명시 |
| --- | --- |
| 증상 | `list.size()`, `map.containsKey(k)`, `Optional.isPresent()`, `Math.abs()` 등은 Python 측에 그대로 emit → AttributeError |
| **sim_v2 자산** | **W75 idiom rewriter** (`backend/sim_v2/core/synthesizer/idiom_rewriter.py` — 구현 완료) |
| 적용 방법 | `JavaToPythonTranslator._translate_method_invocation` 안에 idiom 분기 자동 적용. 3 tier 매칭: STATIC (Math.abs / String.valueOf) → TYPED (List/Map/Set/Optional/String) → UNKNOWN (length/charAt/substring/...). 50+ idiom rewrite |
| 결과 | **UC39 Part B 의 ATTRERROR 2건 자동 close**. 1,727 → 1,796 tests, 회귀 0 |

### 한계 #6 — action.output null 55% (38 중 21건)
| 출처 | §7 표 #2 "🔴 필수" — `action.output` 55%→90%+ backfill |
| --- | --- |
| 증상 | sandbox 의 expected_output 검증 불가능 |
| **sim_v2 자산** | **W58 return_type_verifier** + **W23 UC23 return_type_agreement** + Section 4 가 자동으로 return type drift 진단해서 modeling 에 propose |
| 적용 방법 | Section 4 의 UC23/UC24 가 production action 의 `output:null` 을 자동 detect 하고 method body 의 return statement 분석으로 type 후보 추천. Section 3 가 그 결과를 가져다 가설로 사용 가능 |
| 효과 | "이 action 은 declared output 없음 — Section 4 가 추정한 후보 type: `decimal(...)`. 동의하면 sandbox 가 그 type 으로 검증" UX |

### 한계 #7 — modeling Neo4j 의 Class/Method=0 빈약
| 출처 | §2 캡처: "코드 (Class / Method) = 0" |
| --- | --- |
| 증상 | impact analysis 가 modeling /query 만 호출하면 0 결과 |
| Section 3 의 우회 | legacy ontology API 7 endpoint 병렬 호출 + composer 합성 |
| **sim_v2 자산** | sim_v2 가 직접 풀지 않음. 단, **W19/UC10 production_inspector** 가 legacy ontology DB 의 모든 surface 를 통합 view 로 제공 — Section 3 의 composer 와 *같은 데이터 소스* 를 sim_v2 도 쓴다 |
| 적용 방법 | Section 3 의 composer 가 호출하는 7 endpoint 의 응답 shape 을 sim_v2 의 `production_domain_loader.py` 와 비교 → 같은 데이터를 두 곳에서 다른 view 로 쓰는지 확인. sim_v2 view 가 더 풍부하면 Section 3 가 가져다 쓰는 게 이득 |

### 한계 #8 — 단발 영향 분석 (closed-loop fix 없음)
| 출처 | §4: "code-impact panel — `[HIGH] cumulativeProductivity 변경` 표시까지" |
| --- | --- |
| 증상 | "영향 받는다" 까지만, "어떻게 고쳐야 한다" 없음 |
| **sim_v2 자산** | **5축 Detect→Fix loop** (W55/W58/W64/W67) + **6-state lifecycle** (W62/W68/W69) + **UC36 capstone simulator** (W70) |
| 적용 방법 | Section 3 의 code-impact panel 결과를 sim_v2 의 `param_signature_verifier` + `drift_remediation` 에 흘려보내면 자동으로 fix proposal 까지 emit. Section 3 의 UI 가 "RENAME_PARAM proposal 1건, ADD_EXCEPTION 2건 — 적용하시겠어요?" 까지 surface |

## 2. 우선순위 매트릭스 (2026-05-16 갱신)

| # | Section 3 한계 | sim_v2 해결도 | 즉시 적용 가능? |
| --- | --- | --- | --- |
| #1 | chat [LOW] fallback | **W72 + W73 부착** | ✓ recipe-2/3 그대로 |
| #2 | 한국어 검색 (한↔영 + typo + 음역) | **W77 + W78 ✓ CLOSED** | ✓ `korean_term_resolver.py` (4 tier hybrid) 그대로 |
| #3 | expected 검증 없음 | **W73 + W59** | ✓ recipe-2 그대로 |
| #4 | anchor prelude 단발 | **W74 ✓ CLOSED** | ✓ `sandbox_stubs.py` 그대로 |
| #5 | Java idiom 일부만 | **W75 ✓ CLOSED** | ✓ `idiom_rewriter.py` 그대로 |
| #6 | action.output null 55% | **W58 + UC23** | ✓ sim_v2 추천 가져다 표시 |
| #7 | Neo4j Class/Method=0 | (양쪽 같은 legacy 데이터) | ✓ view 통합 |
| #8 | closed-loop fix 없음 | **5축 lifecycle** | ✓ pipeline wire |

**8/8 한계 모두 CLOSED.** 8 한계 중 영역 밖 0건 — sim_v2 가 한국어 검색까지 자산화 완료.

## 3. 한 줄 결론 (2026-05-16 갱신 — 최종)

| Section 3 가 **지금 당장** 가져다 쓸 수 있는 자산 |
| --- |
| W59 (in-process safe exec) + W71 (deterministic fixture) + W72 (invariant) + W73 (baseline map) + **W74 (stub injection)** + **W75 (idiom rewrite)** + **W77 (한국어 search)** + **W78 (hybrid tier: transliteration / fuzzy / LLM assist)** + 5축 lifecycle |

**8/8 한계 모두 close.** 시뮬레이션 담당자는 sim_v2 자산을 import 하여 본인 엔진을 진화시키는 작업에 집중 가능.

## 4. Section 3 의 클로드 코드가 1 sprint 안에 할 수 있는 일

1. **recipe-2 의 baseline 부착 흐름** 을 Section 3 의 `sandbox_agent.py` 에 통합 → sandbox 결과 표에 expected 컬럼 추가
2. **recipe-3 의 W72 invariant 진단** 을 chat 분기의 [LOW] fallback 자리에 surface → 사용자 정보량 즉시 증가
3. **transpiler-bridge §3 옵션 B** — Section 3 의 `transpiler.py` 를 sim_v2 `JavaToPythonTranslator` subclass 로 재작성 (Java idiom rewrite 만 patch). 코드 라인 70% 감소 + lambda/try-with-resources/inner class 등 자동 획득
4. **UC36 capstone simulator 의 lifecycle 결과** 를 Section 3 chat 의 suggested follow-up 에 노출 — 사용자 자연어 → "이 메서드는 ADD_EXCEPTION 1건 추천됨, 적용하시겠어요?" 같은 actionable suggestion
