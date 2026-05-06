# Step OD-11-D3-1 — MISSING_IN 양방향 탐지기 완료

완료일: 2026-04-21

## 스코프

Gap Detector 1/3. `backend/modeling/gap_detection/` 패키지 신설 + MISSING_IN 양방향
(Q6=A) 탐지기만. CONFLICTS_WITH 3단 hierarchical/llm_only 는 D3-2, 승인 큐 API 는
D3-3.

## 신규 산출물

### Backend (3 파일 + 1 init)

1. `backend/modeling/gap_detection/gap_models.py` (~55 LOC)
   - `ScanConfig` — repo_id, gap_mode, detected_by, include_unconfirmed_terms, min_occurrence_for_manual_only
   - `GapCandidate` — id/direction/target_fqn/counterpart_fqn/severity/detected_by/gap_mode/description/confirmed/created_at
   - `ScanResult` — code_only / manual_only / errors + `.all` property

2. `backend/modeling/gap_detection/gap_store.py` (~55 LOC)
   - `GapStore` Protocol (upsert / list_pending / list_by_direction / get / confirm / remove)
   - `InMemoryGapStore` 구현
   - confirmed=True 항목은 upsert 가 **덮어쓰지 않음** (재스캔 안정성)

3. `backend/modeling/gap_detection/missing_in_detector.py` (~195 LOC)
   - `FragmentTermExtractor` Protocol
   - `SimpleHeuristicExtractor` — 4 패턴 (markdown `**bold**` + `\`code\`` + 한국어 `「」` + ASCII `""`), 2~30 자, IMAGE kind 스킵, case-insensitive dedup
   - `MissingInDetector`
     - `scan()` → `ScanResult` + gap_store.upsert
     - `_detect_code_only` : BusinessTerm + BusinessRule 가 confirmed 인데 DescribedInBinding 없음 → severity=SOFT
     - `_detect_manual_only` : Fragment 에서 강조 phrase 추출, BusinessTerm.name/aliases 에 매칭 실패, `min_occurrence` 이상 발견 → severity=HARD
     - `_stable_id` — `sha1(direction|target|counterpart)[:16]` 로 idempotent scan

4. `backend/modeling/gap_detection/__init__.py` — public API export

### 테스트 (2 파일, 28 tests)

5. `tests/test_gap_store.py` (10 tests)
   - Protocol conformance
   - upsert/get roundtrip + pending 덮어쓰기 + confirmed 보호
   - list_pending / list_by_direction
   - confirm flag flip + missing KeyError
   - remove + missing noop

6. `tests/test_missing_in_detector.py` (18 tests)
   - **Extractor 3** : bold/code/Korean quote, IMAGE skip, within-fragment dedup
   - **code_only 5** : term w/o described_in → SOFT, with → skip, rule w/o → SOFT, unconfirmed skip, include_unconfirmed flag
   - **manual_only 5** : unmatched bold → HARD, matched canonical_label skip, matched alias (case-insensitive), min_occurrence threshold, IMAGE skip
   - **Store 통합 + gap_mode 5** : upsert 확인, re-scan idempotency, confirm 보존, llm_only 전파, ScanResult.all

## 설계 결정

- **MissingBinding 대신 GapCandidate 도입** : D1.5 의 `MissingBinding` 은 graph 엣지
  DTO (severity 필드 없음). 스캔 중간 결과 + 승인 큐 상태 (confirmed, id) 를 더 풍부하게 담기
  위해 `GapCandidate` 를 별도 도입. 그래프 쓰기 시점에 `GapCandidate → MissingBinding`
  어댑터로 변환 (D3-3 혹은 D3 말미).
- **severity 2 단계 유지 (HARD/SOFT)** : D1.5 `GapSeverity` 그대로. 디자인 스펙의 4 단계
  (low/medium/high/critical) 는 CONFLICTS_WITH 에 주로 쓰이므로 D3-2 에서 LLM 제안 포함해
  재검토. MISSING_IN 은 결정적 (있음/없음) 이라 2 단계로 충분.
- **휴리스틱 추출기 기본** : term_resolver 통합은 D3-2. D3-1 은 완전히 결정적 (regex) 으로
  유지해 테스트 단순화 + 독립 검증 가능. 추출기는 `FragmentTermExtractor` Protocol 이라
  D3-2 에서 resolver-backed 버전으로 교체 가능.
- **confirmed 보호** : `InMemoryGapStore.upsert` 가 기존 gap 이 confirmed 면 no-op.
  사람이 한 번 검토한 갭은 다음 배경 스캔에서 reset 되지 않는다.
- **stable id** : sha1(direction|target|counterpart)[:16] 로 re-scan idempotent. 같은
  입력으로 재실행하면 동일 id → 덮어쓰기 또는 confirmed 보존.
- **`direction | None`** : `GapCandidate.direction` 은 Optional. CONFLICTS_WITH (D3-2)
  는 direction 없이 target/counterpart 쌍으로 표현될 예정이라 미리 Optional 로.

## 검증

### Red phase
```bash
$ .venv/bin/python -m pytest tests/test_gap_store.py tests/test_missing_in_detector.py -x
ModuleNotFoundError: No module named 'backend.modeling.gap_detection'
```

### Green phase
```bash
$ .venv/bin/python -m pytest tests/test_gap_store.py tests/test_missing_in_detector.py -v
28 passed in 0.06s
```

### 모델링 회귀
```bash
$ .venv/bin/python -m pytest tests/ -k "modeling or spring or manual or ... or gap or ingest or missing_in"
705 passed, 750 deselected in 2.58s
```
D2-3 기준 677 → 705 (+28 D3-1 신규).

### 전체 스위트
```bash
$ .venv/bin/python -m pytest tests/ --tb=no -q
21 failed, 1434 passed, 39 warnings in 55.28s
```
Baseline 21 failures (Section 1 skill/wiki) 그대로 유지. D2-3 대비 1406 → 1434 (+28).

### Runtime smoke
```bash
$ .venv/bin/python -c "from backend.main import app; print(len(app.routes))"
152   # 변동 없음 (D3-1 은 API 미추가)

$ .venv/bin/python -c "from backend.modeling.gap_detection import MissingInDetector, InMemoryGapStore, ScanConfig"
# 성공
```

## 엔트리 포인트

### Python
```python
from backend.modeling.gap_detection import (
    MissingInDetector,
    InMemoryGapStore,
    ScanConfig,
    GapCandidate,
)
from backend.modeling.manuals.manual_models import GapDirection, GapMode

store = InMemoryGapStore()
detector = MissingInDetector(gap_store=store)

result = detector.scan(
    business_terms=[...],
    business_rules=[...],
    fragments=[...],
    described_in=[...],
    config=ScanConfig(repo_id="prod", gap_mode=GapMode.HIERARCHICAL),
)
# result.code_only, result.manual_only, result.all
# store.list_pending() → 사람 검토 큐
# store.confirm(gap_id) → 승인
```

### REST
D3-3 예정 (`POST /api/modeling/gaps/scan`, `GET /gaps`, `POST /gaps/{id}/confirm`, SSE).

## D3-2 진입 조건

D3-1 완료. 다음은 **D3-2 CONFLICTS_WITH** :
- `rule_ast_differ.py` — Round 2 DSL AST 비교 (BusinessRule.statement ↔ Fragment.text)
- `embedding_drifter.py` — cosine < 0.65 후보
- `llm_comparator.py` — LLM 의미 비교 + severity(low/medium/high/critical) 제안
- `gap_engine.py` — Strategy 패턴 (`hierarchical` 3단 직렬 / `llm_only` 단독)
- CONFLICTS_WITH 를 `GapCandidate` 로 저장 (direction=None, target=code_fqn, counterpart=fragment_fqn)

또는 D4 UI 디자인 스펙으로 선행. 사용자 승인 대기.
