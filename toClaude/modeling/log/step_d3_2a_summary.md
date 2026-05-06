# Step OD-11-D3-2-a — CONFLICTS_WITH deterministic (rule_ast + drift + engine)

완료일: 2026-04-21

## 스코프

D3-2 3-subphase 중 1/2 (D3-2-a). CONFLICTS_WITH deterministic 2 stage 구현 +
Strategy Engine skeleton. LLM comparator 는 Protocol + Fake 테스트 더블까지만,
실 OpenAI 구현은 D3-2-b 로 분리.

## 신규 산출물

### Backend (3 파일 + 2 edit)

1. `backend/modeling/manuals/manual_models.py` — `GapSeverity` 에 LOW/MEDIUM/HIGH/CRITICAL
   4값 추가. 기존 HARD/SOFT 유지 (MISSING_IN 호환).

2. `backend/modeling/gap_detection/rule_ast_differ.py` (~230 LOC)
   - `RuleStatementTokens(numbers, comparators, units)` frozen dataclass
   - `extract_quantities(text) -> RuleStatementTokens` — 정규식 4 패턴
     - 숫자 : `-?\d+(?:\.\d+)?` (정수/소수/음수)
     - 비교 : ≥/≤/>=/<=/==/!=/>/</=/이상/이하/초과/미만/같음/동일/부터/까지
     - 단위 : %/원/달러/$/개/건/명/회/kg/g/t/일/시간/분/초/주/월/년
   - `DiffOutcome(numeric/comparator/unit_mismatch, has_mismatch)` — 세 셋 비교
   - `_canonical_comparator` 로 `≥ ≡ >= ≡ 이상` 통일
   - `RuleASTDiffer(clock)` — `compare(left, right)` + `find_conflicts(...)`
   - **빈 쪽은 mismatch 아님** : 수량 근거가 있어야 rule_ast hit. 자연어 only rule 은 stage 2 embedding 으로 위임.
   - Hit severity = `GapSeverity.HIGH` (LLM 재평가 가능).

3. `backend/modeling/gap_detection/embedding_drifter.py` (~120 LOC)
   - `@runtime_checkable TextEmbedder` Protocol (`embed(text) -> list[float]`)
   - `_cosine(a, b)` — zero-vector 안전.
   - `CosineDrifter(embedder, cutoff=0.65, clock)`
   - `find_drift(rules, fragments, described_in, config)` — described_in 매핑 쌍에서 cos < cutoff
   - IMAGE kind 스킵 (OCR 텍스트는 OCR_TEXT kind 로 들어옴)
   - Hit severity = `GapSeverity.MEDIUM` (LLM 재평가 전 중립).

4. `backend/modeling/gap_detection/gap_engine.py` (~240 LOC)
   - `@runtime_checkable LLMComparator` Protocol (`compare(rule, fragment, prior_severity, config) -> (severity, reasoning)`)
   - `@runtime_checkable GapEngine` Protocol (`detect_conflicts(...) -> list[GapCandidate]`)
   - `HierarchicalGapEngine(rule_differ, drifter, llm_comparator=None, gap_store=None, clock)`
     - Stage 1 rule_ast → hit pair 는 `locked_pairs` 에 마킹
     - Stage 2 drift → locked_pairs 는 skip (dedup)
     - Stage 3 LLM (optional) → severity + reasoning merge (description 에 append)
     - gap_store 주입 시 upsert
   - `LLMOnlyGapEngine(llm_comparator=None, gap_store, clock)` — stage 1/2 skip. comparator 없으면 `[]` + warning.
   - `create_gap_engine(mode, rule_differ, drifter, llm_comparator, gap_store, clock)` factory → GapMode 분기.

5. `backend/modeling/gap_detection/__init__.py` — public re-exports 확장
   - rule_ast : RuleASTDiffer / RuleStatementTokens / DiffOutcome / extract_quantities
   - drift : TextEmbedder / CosineDrifter
   - engine : GapEngine / HierarchicalGapEngine / LLMOnlyGapEngine / LLMComparator / create_gap_engine

### 테스트 (3 신규 + 2 touch, 30 신규 tests)

6. `tests/test_rule_ast_differ.py` (14 tests)
   - extract_quantities 4 (numbers+units+comparators / ASCII ops / 소수·범위 / 순수 산문)
   - compare 5 (identical / numeric / flip / unit / both empty)
   - find_conflicts 5 (mapping required / numeric emit / tokens empty skip / stable id / IMAGE skip)

7. `tests/test_embedding_drifter.py` (7 tests)
   - Protocol conformance
   - no mapping → []
   - 고유사도 cos=1 → skip
   - 직교 cos=0 → 후보 severity=MEDIUM
   - custom cutoff 경계
   - IMAGE skip
   - re-scan stable id

8. `tests/test_gap_engine_conflicts.py` (9 tests)
   - Hierarchical 5 (rule_ast hit short-circuit / drift when rule_ast empty / no mapping / LLM override / store persistence)
   - LLMOnly 2 (comparator 없으면 [] / 있으면 매핑 쌍 처리)
   - Factory 2 (mode 별 분기)

9. `tests/test_manual_models.py` — `test_gap_enum_values` 에 4값 assertion 추가, `test_conflict_binding_severity_enum_validates` 의 invalid literal 을 "apocalyptic" 로 교체 (critical 은 이제 정식 값).

## 설계 결정

- **자연어 vs DSL** : BusinessRule.statement 는 자유 텍스트 str. 따라서 "AST 비교" 는 **수량 표현만 추출**하는 경량 정규식으로 축소. 나머지 의미 비교는 embedding/LLM 단계 책임. 과도한 NLP/파서 투자 회피.
- **빈 토큰 = not mismatch** : rule_ast 는 "수량 근거가 있어야" hit. 양쪽이 순수 산문이면 stage 1 은 침묵하고 stage 2 embedding 이 판정.
- **canonical comparator** : ≥/>=/이상 은 모두 `ge` 로 정규화해 "이상 vs ≥" 은 동의어 취급. 단 "이상 vs 이하" 는 canonical `ge` vs `le` 로 다름.
- **severity 4값 + 2값 공존** : `GapSeverity` Enum 확장 (HARD/SOFT + LOW/MEDIUM/HIGH/CRITICAL). MISSING_IN 은 기존 2값만, CONFLICTS_WITH 는 4값. 단일 Enum 으로 타입 단순화 + 필터 용이.
- **Strategy skeleton** : `HierarchicalGapEngine` 은 llm_comparator=None 도 지원 — deterministic 2 stage 만 돌린 결과 반환. 이 덕에 D3-2-a 만으로도 사람 검증 가능한 파이프라인이 나옴. D3-2-b 에서 실 LLM 만 끼워넣으면 완성.
- **stage dedup** : rule_ast hit 쌍은 drift stage 에서 skip — 같은 쌍이 두 번 등장하지 않음. LLM override 시에도 동일 candidate 만 갱신.
- **stable id** : rule_ast 는 `sha1("rule_ast|target|counterpart")`, drift 는 `sha1("drift|...")`, llm_only 는 `sha1("llm_only|...")`. prefix 로 stage 충돌 방지.
- **IMAGE 스킵** : 두 stage 모두 `ManualFragmentKind.IMAGE` 는 비교 대상 아님. OCR 텍스트는 `OCR_TEXT` kind 로 들어오므로 별도 fragment 로 참여.
- **gap_store optional** : 엔진 배출은 `list[GapCandidate]` 직접 반환. store 주입시에만 upsert. D3-3 오케스트레이터가 store 주입 여부 결정.
- **LLMOnly skeleton** : D3-2-a 에서는 comparator 없으면 [] + warning. 실 LLM 은 D3-2-b.

## 검증

### Red phase
```bash
$ .venv/bin/python -m pytest tests/test_rule_ast_differ.py ...
ModuleNotFoundError: No module named 'backend.modeling.gap_detection.rule_ast_differ'
```

### Green phase
```bash
$ .venv/bin/python -m pytest tests/test_rule_ast_differ.py tests/test_embedding_drifter.py tests/test_gap_engine_conflicts.py tests/test_manual_models.py::test_gap_enum_values -v
... 30 passed in 0.08s
```

### 모델링 회귀
```bash
$ .venv/bin/python -m pytest tests/ -k "modeling or ... or rule_ast or embedding_drifter or gap_engine" -q
735 passed, 750 deselected in 2.14s
```
D3-1 기준 705 → 735 (+30 D3-2-a 신규).

### 전체 스위트
```bash
$ .venv/bin/python -m pytest tests/ --tb=no -q
21 failed, 1464 passed, 39 warnings in 67.71s
```
Baseline 21 failures (Section 1 skill_api) 그대로 유지. D3-1 대비 1434 → 1464 (+30).

### Runtime smoke
```bash
$ .venv/bin/python -c "from backend.main import app; print(len(app.routes))"
152   # 변동 없음 (D3-2-a 도 API 미추가 — D3-3 예정)

$ .venv/bin/python -c "from backend.modeling.gap_detection import HierarchicalGapEngine, LLMOnlyGapEngine, RuleASTDiffer, CosineDrifter, create_gap_engine"
# 성공
```

## 엔트리 포인트

### Python
```python
from backend.modeling.gap_detection import (
    HierarchicalGapEngine,
    RuleASTDiffer,
    CosineDrifter,
    ScanConfig,
    InMemoryGapStore,
)
from backend.modeling.manuals.manual_models import GapMode

# 최소 embedder — 실제로는 OpenAIChromaProvider 나 pydantic-ai wrapper
class MyEmbedder:
    def embed(self, text: str) -> list[float]:
        ...

store = InMemoryGapStore()
engine = HierarchicalGapEngine(
    rule_differ=RuleASTDiffer(),
    drifter=CosineDrifter(embedder=MyEmbedder(), cutoff=0.65),
    llm_comparator=None,     # D3-2-b 까지는 None 으로 운영 가능
    gap_store=store,
)

conflicts = engine.detect_conflicts(
    rules=[...],
    fragments=[...],
    described_in=[...],      # rule_fqn ↔ fragment_fqn 매핑
    config=ScanConfig(repo_id="prod", gap_mode=GapMode.HIERARCHICAL),
)
# store.list_pending() → 승인 큐
```

### REST
D3-3 예정 (`POST /api/modeling/gaps/scan`, `GET /gaps`, `POST /gaps/{id}/confirm`, SSE).

## D3-2-b 진입 조건

D3-2-a 완료. 다음은 **D3-2-b LLM Comparator 실 구현** :
- `backend/modeling/gap_detection/llm_comparator.py` — pydantic-ai Agent or direct OpenAI
  - 프롬프트 : rule.statement + fragment.text + prior_severity → (severity, reasoning)
  - severity 는 Literal[low/medium/high/critical]
  - 환각 방어 (LLM 이 반환한 severity 가 enum 에 없으면 MEDIUM fallback)
- HierarchicalGapEngine / LLMOnlyGapEngine 은 그대로 — comparator 주입만 하면 동작.
- `backend/main.py` startup 에 `ONTONG_LLM_COMPARATOR=openai` 환경변수 분기.
- 테스트 : fake comparator 로 통합 + 실 LLM 호출은 integration 태그 분리.

또는 **D3-3 승인 큐 API + UI** 로 병행 — 이미 engine + store 가 준비됐기 때문에 REST/SSE + 프런트 스텁이 가능하다.
