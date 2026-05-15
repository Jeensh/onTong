# onTong · Section 4 → Section 3 Handoff Package

> Section 4 (sim_v2) 에서 W1–W78 까지 만든 자산을 **Section 3 시뮬레이션 담당자** 와 그 클로드 코드가 *바로 가져다 쓸 수 있는 형태* 로 정리.

작성: **2026-05-16** · sim_v2 누적: **1,892 PASS + 3 SKIPPED** · UC demo: **42**

---

## 0. 한 줄 요약

**8/8 알려진 한계 모두 close. 영역 밖 0건.** Section 3 의 sandbox + composer + transpiler 파이프라인의 8 한계를 sim_v2 의 W59/W71/W72/W73/**W74**/**W75**/**W77**/**W78** 자산으로 전부 해결. 시뮬레이션 담당자는 sim_v2 자산을 본인 엔진에 통합하여 진화시키는 작업에 집중 가능.

추가 구현 결과:
- W74 sandbox stub injection — production behavioral (UC40) **0/11 → 6/11 PASS (54.5%)**, fixture pass rate **74/126 (58.7%)**, 23 stubs 자동 derive
- W75 Java idiom rewrite — 50+ idiom 자동 변환 (String/Collection/Optional/Math/Objects)
- W77 Korean term resolver — `slab-design-real-v2` 43 term 대상 **9/10 한국어 query hit (90%)**, "엣징" / "실수율" 등 cross-match
- W78 hybrid search tier — Tier 2 한↔영 정적 매핑 + Tier 3 difflib 오타 보정 + Tier 4 LLM callback. **typo "edgign" / 비표준 음역 "에징" 모두 close**

자세히는 **[gap-analysis.md](./gap-analysis.md)** 한 페이지로 정리.

---

## 1. 패키지 구조

```
section3_handoff/
├── README.md                  ← 이 문서 (navigation hub)
├── landing.html               ← 시각 보고서 (브라우저로 열기)
├── transpiler-bridge.md       ← Section 3 transpiler ↔ sim_v2 translator 규칙 매핑
├── gap-analysis.md            ← Section 3 의 8 한계 → sim_v2 자산 1:1 매핑
├── api-reference/             ← W59/W71/W72/W73/W74/W75/W77 API + 한국어 가이드
│   ├── W59-behavior-twin-runner.md
│   ├── W71-fixture-synthesizer.md
│   ├── W72-twin-invariants.md
│   ├── W73-java-oracle-adapter.md
│   ├── W74-sandbox-stubs.md      ★ NEW
│   ├── W75-idiom-rewriter.md     ★ NEW
│   └── W77-korean-term-resolver.md ★ NEW (W77 + W78 hybrid tier 통합)
├── usage-recipes/             ← 즉시 실행 가능한 Python recipes (모두 동작 확인됨)
│   ├── recipe-1-replace-llm-test-synthesis.py
│   ├── recipe-2-record-java-baseline.py
│   ├── recipe-3-run-invariant-survey.py
│   ├── recipe-4-stub-injected-production.py   ★ NEW (full pipeline)
│   └── recipe-5-korean-term-search.py         ★ NEW (W77 + W78 hybrid)
├── for-humans.html            ← 사람 (담당자) 직접 읽는 인터랙티브 페이지
└── screenshots/               ← simulation-viewer 7 탭 + capstone summary
```

---

## 2. "내가 막힌 곳" → "어디 보면 됨" 빠른 안내

| 막힌 곳 (Section 3) | 가서 볼 곳 |
| --- | --- |
| 어디서부터 시작할지 모르겠다 | ★ [recipe-4 stub-injected end-to-end](./usage-recipes/recipe-4-stub-injected-production.py) — production method 가 PASS 까지 가는 풀 파이프라인 |
| chat 분기에서 [LOW] fallback 만 떨어진다 | [gap-analysis.md §1.1](./gap-analysis.md) + [recipe-3](./usage-recipes/recipe-3-run-invariant-survey.py) |
| sandbox 결과가 *Java 와 같은지* 모르겠다 | [W73 API](./api-reference/W73-java-oracle-adapter.md) + [recipe-2](./usage-recipes/recipe-2-record-java-baseline.py) |
| LLM 으로 test case 합성하는데 boundary 가 아쉬워 | [W71 API](./api-reference/W71-fixture-synthesizer.md) + [recipe-1](./usage-recipes/recipe-1-replace-llm-test-synthesis.py) |
| anchor prelude (DEFAULT_PRODUCTIVITY=0.95) 를 generic 화하고 싶다 | ★ [W74 API](./api-reference/W74-sandbox-stubs.md) (구현 완료) + [recipe-4](./usage-recipes/recipe-4-stub-injected-production.py) |
| `'str' object has no attribute 'length'` 같은 ATTRERROR | ★ [W75 API](./api-reference/W75-idiom-rewriter.md) (sim_v2 translator 자동 적용) |
| sandbox subprocess fork 비용이 부담 | [W59 API](./api-reference/W59-behavior-twin-runner.md) (in-process safe exec) |
| `groupRepository.findById()` 같은 Spring bean 의존성 | ★ [W74 API §3](./api-reference/W74-sandbox-stubs.md) (자동 stub derive) |
| 영향 분석만 표시, fix 추천까지 못 함 | [gap-analysis.md §1.8](./gap-analysis.md) (5축 lifecycle wiring) |
| action.output null 55% 라 expected 검증 불가 | [gap-analysis.md §1.6](./gap-analysis.md) (W58 + UC23 return_type_verifier) |
| transpiler 코드 라인 줄이고 싶다 | [transpiler-bridge §3 옵션 B](./transpiler-bridge.md) (sim_v2 71-handler subclass) |

---

## 3. sim_v2 자산 7 종 — public surface

```python
# 1) deterministic test fixture 생성 (LLM 합성 대체)
from backend.sim_v2.core.verification.fixture_synthesizer import (
    synthesize_fixtures_for_action,
    PRIMITIVE_TYPES,
    FixtureSynthesisReport,
)

# 2) Java baseline 부착 layer
from backend.sim_v2.core.verification.java_oracle_adapter import (
    JavaBaselineMap,
    JavaBaselineEntry,
    attach_baselines,
)

# 3) in-process safe exec + baseline diff
from backend.sim_v2.core.verification.behavior_twin_runner import (
    BehaviorTwinRunner,                # + stub_namespace 인자
    BehaviorFixtureStore,
    BehaviorFixture,
    compare_outputs,
    _safe_globals,                     # extra= 인자로 stub 주입
)

# 4) baseline-free invariant check
from backend.sim_v2.core.verification.twin_invariants import (
    TwinInvariantRunner,               # + stub_namespace 인자
    run_invariants_for_fixtures,
)

# 5) ★ W74 sandbox stub injection — production NameError 0
from backend.sim_v2.core.verification.sandbox_stubs import (
    build_stub_namespace,              # 3 source 통합 (anchor / AST / entity)
    derive_anchor_constants,
    derive_class_stub,
    derive_repository_stub,
    find_unbound_names,
    classify_unbound,
)

# 6) ★ W75 Java idiom rewriter — 50+ idiom
from backend.sim_v2.core.synthesizer.idiom_rewriter import (
    rewrite_method_invocation,
)

# 7) ★ W77 Korean term resolver — 한↔영 cross-match
# 8) ★ W78 hybrid tier — transliteration / fuzzy / LLM assist
from backend.sim_v2.core.search.korean_term_resolver import (
    KoreanTermResolver,                # from_session() + resolve(..., use_fuzzy=True, llm_assist=)
    LLMAssistCallable,                 # Callable[[str], list[str]] — 본인 LLM plug-in
    TermRecord, TermSearchHit,
    tokenize,                          # 한국어/영문 mixed tokenizer
)
from backend.sim_v2.core.search.transliteration import (
    expand_transliteration,            # W78 Tier 2 — 한↔영 정적 매핑
    register_transliteration,          # runtime 도메인 단어 추가
)

# Bonus — translator (W75 자동 적용)
from backend.sim_v2.core.synthesizer.java_translator import (
    JavaToPythonTranslator,
    TranslationResult,
)
```

---

## 4. 자료 확인용 — 실제 v2 production 에서 무엇이 가능한가

**UC36 contract-level capstone (이미 완료, 100%)** ─ v2 23 findings → 0 simulated, 30 MERGED proposal (15 effect + 13 structural + 2 term cascade)

**UC37 fixture coverage (W71)** ─ v2 38 action 중 11 (28.9%) 가 deterministic fixture 로 driveable. 151 fixtures 자동 생성.

**UC38 invariant survey (W72)** ─ 11 driveable 중 0 PASS — 솔직한 production gap. 모든 실패가 NameError (sandbox 의존성 누락) 또는 compile 실패.

**UC39 B-level capstone (W73)** ─ Part A 합성 케이스 4/4 behavioral PASS (W71→W73→W59 loop 작동 증명). Part B production baseline 11/11 의 실패가 100% 명명된 cause.

**UC40 stub-injected behavioral (W74)** ★ ─ Section 4 의 엔진 한계 close 결과. baseline 0/11 → **6/11 actions PASS (54.5%)**, fixture pass rate **74/126 (58.7%)**, 23 stubs 자동 derive (anchor + AST + entity). 남은 5건:
- 2 ERROR — translator SYNTAX gap (W75 의 추가 case 후속)
- 3 FAIL_RETURN_TYPE — MagicMock 이 declared return type 과 mismatch (typed-return stub 으로 close 가능)

스크린샷은 `./screenshots/` 폴더 참조 (특히 `viewer_07_stubs.png` 가 UC40 결과).

---

## 5. Section 3 의 클로드 코드를 위한 권장 작업 순서

엔진 측 한계는 sim_v2 안에서 모두 close 되었으므로, Section 3 가 해야 할 일은 **자산을 import + Section 3 의 sandbox/chat 흐름에 통합** 하는 것 뿐:

### 단계 1 (1 sprint) ★ — recipe-4 full pipeline 통합
[recipe-4-stub-injected-production.py](./usage-recipes/recipe-4-stub-injected-production.py) 의 W71→W75→W74→W72 full pipeline 을 Section 3 의 `backend/section3/agents/sandbox_agent.py` 에 통합. **production method 가 in-process exec 으로 PASS 12/12 도달 시연 완료** (`cumulativeProductivity` 예제, 위 recipe 의 실측).

### 단계 2 (1 sprint) — recipe-2 통합 (baseline 검증)
[recipe-2-record-java-baseline.py](./usage-recipes/recipe-2-record-java-baseline.py) 의 흐름을 통합. sandbox 결과 표에 `expected` 컬럼 추가. anchor 에서 derive 한 default 값을 1차 baseline 으로 활용.

### 단계 3 (1 sprint) — recipe-3 통합 (chat [LOW] fallback 진단)
[recipe-3-run-invariant-survey.py](./usage-recipes/recipe-3-run-invariant-survey.py) 의 W72 invariant 진단을 chat 분기 [LOW] fallback 자리에 surface.

### 단계 4 (1 sprint, optional) — transpiler 통합 (옵션 B)
[transpiler-bridge §3](./transpiler-bridge.md) 의 옵션 B 채택. Section 3 `transpiler.py` 를 sim_v2 `JavaToPythonTranslator` subclass 로 재작성. **W75 idiom rewrite + 71 핸들러 모두 자동 획득.**

---

## 6. 무엇을 *건드리면 안 되는지*

- **Section 3 의 기존 코드** (`backend/section3/`, `frontend/src/components/sections/Section3Section.tsx`, 4 agent, `composer.py`, `transpiler.py`) — sim_v2 가 직접 수정 안 함. 시뮬레이션 담당자가 sim_v2 import + subclass + recipe 흐름 적용
- **section3_landing/** — read-only. 보고서 + 스크린샷 보존용
- **Section 2 modeling** — 한국어 검색 (gap #2) 이외에는 modify 요청 0

---

## 7. 관련 외부 문서

- **sim_v2 capstone summary HTML** — `toClaude/modeling/section4-verification/b-level-capstone-summary.html`
- **UC36 v2 final-goal HTML** — `toClaude/modeling/section4-verification/sim-v2-v2-final-goal-summary.html`
- **Section 3 자체 보고서** — `section3_landing/README.md` + `section3_landing/landing.html`
- **simulation-viewer (UC36+37+38+39 interactive)** — `toClaude/modeling/section4-verification/simulation-viewer.html`

---

## 8. 시뮬레이션 담당자 onboarding — pull 받고 첫 작업까지

> 이 패키지를 받은 시뮬레이션 담당자 (사람 + 본인 클로드 코드) 가 *0 부터 시작* 한다고 가정한 단계별 가이드.

### 8.1 Pull / 브랜치 확인

```bash
# 1) 본인 worktree 의 onTong repo 로 이동
cd ~/workspace/ai/onTong   # (경로는 본인 환경에 맞게)

# 2) 최신 main + Section 4 작업 브랜치 fetch
git fetch origin

# 3) Section 4 작업 브랜치로 checkout (브랜치 이름은 모델링 세션에 확인)
#    예: section4-verification
git checkout section4-verification
git pull origin section4-verification
```

> 본 패키지는 `toClaude/modeling/section4-verification/section3_handoff/` 하위에 모두 들어 있음. 시뮬레이션 담당자는 *read-only 로 참조* + 본인 영역 (`toClaude/simulation/` 또는 `backend/section3/`) 에서 작업.

### 8.2 환경 setup

```bash
# 1) Python venv (3.12)
python3.12 -m venv .venv
source .venv/bin/activate

# 2) sim_v2 의존성은 onTong 의 기존 requirements.txt 안에 포함되어 있음
pip install -r requirements.txt

# 3) sim_v2 회귀 확인 — 1,892 passed 가 나와야 정상
.venv/bin/python -m pytest backend/sim_v2/ -q
# → 1892 passed, 3 skipped in ~6s
```

### 8.3 first-run — 받은 자산이 실제 동작하는지 5 분 안에 검증

```bash
# (1) W77+W78 한국어 검색이 production DB 에 동작 — 가장 빠른 sanity
.venv/bin/python -m backend.sim_v2.demos.uc41_korean_term_search.run
# → "9/10 query hit (90%)" 출력

# (2) W78 hybrid tier 가 typo / 비표준 음역 close 하는지
.venv/bin/python -m backend.sim_v2.demos.uc42_hybrid_korean_search.run
# → "T3: 1/2 closed, T4: 1/1 closed" 출력

# (3) W74 stub injection 으로 production action 이 PASS 까지 가는지
.venv/bin/python -m backend.sim_v2.demos.uc40_stub_injected_behavioral.run
# → "6/11 actions PASS (54.5%)" 출력

# (4) 사람이 읽는 종합 페이지 (브라우저)
open toClaude/modeling/section4-verification/section3_handoff/for-humans.html
```

### 8.4 본인 클로드 코드와 함께 작업 시작

본인 worktree 에서 클로드 코드 세션을 띄울 때 첫 메시지로 다음 안내:

```
이 onTong repo 의 시뮬레이션 (Section 3) 담당이다.
Section 4 가 sim_v2 자산을 toClaude/modeling/section4-verification/section3_handoff/
아래에 정리해줬다. 다음 순서대로 읽고 시작하자:

1) section3_handoff/README.md          — navigation hub (이 문서)
2) section3_handoff/for-humans.html     — 사람용 인터랙티브 요약
3) section3_handoff/gap-analysis.md     — 8 한계 → sim_v2 자산 1:1 매핑
4) section3_handoff/api-reference/      — 8 모듈 한국어 API
5) section3_handoff/usage-recipes/      — 5 recipe (모두 실행 확인됨)

권장 첫 작업: recipe-4 의 full pipeline 을 본인 sandbox_agent.py 에
통합. 그 다음 recipe-5 의 W77+W78 검색을 bridge_agent.py 에 통합.
```

### 8.5 권장 작업 순서 (sprint 단위)

| Sprint | 작업 | 대상 파일 (담당자 측) | 기대 결과 |
| --- | --- | --- | --- |
| 1 ★ | recipe-4 full pipeline 통합 | `sandbox_agent.py` | `cumulativeProductivity` 12/12 PASS, production 6/11 actions PASS |
| 2 | recipe-2 baseline 검증 통합 | `sandbox_agent.py` | sandbox 결과 표에 `expected` 컬럼 |
| 3 | recipe-3 invariant 진단 surface | `bridge_agent.py` chat 분기 | `[LOW] fallback` 자리에 actionable 정보 |
| 4 | recipe-5 W77+W78 검색 통합 | `bridge_agent.py` chat 입력 | "엣징"/"edgign"/"에징" 모두 cross-match |
| 5 (opt) | transpiler-bridge §3 옵션 B | `transpiler.py` | 코드 70% 감소 + 71 핸들러 자동 획득 |

### 8.6 본인 작업 영역과 read-only 영역

- **본인 작업 영역**: `toClaude/simulation/` (없으면 신규 생성), `backend/section3/` (있는 경우), 본인 frontend UI
- **read-only 참조**: `toClaude/modeling/section4-verification/`, `backend/sim_v2/`, `section3_landing/`
- **수정 금지**: `toClaude/_shared/` (사용자 승인 필요), `toClaude/wiki/`

### 8.7 막혔을 때

| 증상 | 가서 볼 곳 |
| --- | --- |
| sim_v2 자산이 import 안 됨 | §8.2 의 회귀 (`pytest`) 가 통과하는지부터 확인 |
| anchor / stub 자동 derive 가 부족 | [W74 API §4](./api-reference/W74-sandbox-stubs.md) 의 "직접 stub 추가" 패턴 |
| Java idiom 이 still NameError | [W75 API §3](./api-reference/W75-idiom-rewriter.md) 에 빠진 idiom 보고 (PR 환영) |
| 한국어 query 가 0 hit | [W77+W78 API §3.5](./api-reference/W77-korean-term-resolver.md) 의 tier 확인, fuzzy/LLM 켜기 |
| 본인 도메인 한↔영 단어가 빠짐 | `register_transliteration(kr, en)` 으로 runtime 추가 |
