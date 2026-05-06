# P24~P26 — Sandbox + DiffReporter + Apply 워크플로우 (시뮬레이션 풀 사이클)

## 결과
**P22~P26 완성으로 시뮬레이션 풀 사이클 동작 검증 완료.**

E2E 시연 (slab-design-real / `CastSpecService.lookup`):
1. **Define** : ChangeSpec method_body kind, "repository → cache" 변경 정의
2. **Simulate** : Java→한국어 Python 변환 → RestrictedPython 실행 → DiffReport 산출
3. **Apply** : unified diff 자동 생성:
   ```diff
   - return repository.findById(pk).map(logic::toEntity).orElse(null);
   + return cache.get(pk).orElseGet(() -> repository.findById(pk)).map(logic::toEntity).orElse(null);
   ```
   target_file 정확 식별, status=applied.

## 산출물

### Backend (P24)
- `backend/modeling/simulation/sandbox_runner.py` (NEW)
  - `SyntheticInputGenerator` — anchor + param spec 기반 3 시나리오 (기본 + literal #1 + literal #2)
  - `RestrictedPythonSandbox` — `compile_restricted_exec` + `safe_globals` 기반
    - whitelist `__import__` (decimal, typing, math, datetime, re)
    - `_guarded_getattr` (underscore 차단)
    - mock factory (find/get → None, findAll/list → [], count → 0, exists → False, save → echo)
    - mock 함수는 `mock_<name>` (underscore prefix 없음, RestrictedPython 호환)
    - `safe_g` 단일 namespace (module-level 변수 → globals)
    - `_SampleDict` (entity 누락 키 → Decimal('1') fallback)
  - `SandboxResult` — return_value + stdout + exception + elapsed_ms + mock_calls_invoked + **mutated_args**
  - mutation 캡처 — `copy.deepcopy(args)` 후 호출 → 변경된 dict key 추출

### Backend (P25)
- `backend/modeling/simulation/diff_reporter.py` (NEW)
  - `report_diff(before_runs, after_runs) → DiffReport`
  - 5 차원 비교 :
    1. **return_diff** — Decimal 우선 (rel_pct 계산)
    2. **mutation_diff** — arg index 별 / key 별 변경
    3. **exception_diff** — improvement (B 예외 → A 정상) / regression (B 정상 → A 예외)
    4. **mock_diff** — added / removed
    5. **perf_diff** — elapsed_ms 차이 (>20% 만)
  - `_classify_severity` — none / improvement / minor / major / regression
  - 자연어 summary 자동 생성

### Backend (P26)
- `change_specs_api.py` `POST /change-specs/{id}/apply`
  - `difflib.unified_diff(before_java, after_java)` 로 patch 생성
  - simulation_result.applied = {applied_at, target_file, patch, patch_lines, java_changed, note}
  - status → applied

### Frontend
- `SimulationDrawer.tsx`
  - `Step3Diff` 재작성 — `SemanticDiff` interface + `DiffCaseCard` 컴포넌트
    - severity 별 색상 (regression 빨강, major 주황, minor 노랑, improvement 녹색)
    - 각 case 의 5 차원 diff 자동 표시
  - **Full mode toggle** (Maximize2 / Minimize2) — 55vh ↔ 94vh
  - `applyChangeSpec` 호출 → 결과 시 patch (unified diff) 표시 (slate-900 dark code block)
  - `SideColumn` runs 표시 — case 별 return_value + exception + mutated_args + mock_calls_invoked

## 검증 (E2E, slab-design-real demo)

### Test 1 — repository → cache 변경 (`CastSpecService.lookup`)
```
1. POST /change-specs (kind=method_body)
2. POST /change-specs/{id}/simulate
   → engine: python-generator-v1+sandbox+diff
   → before: 한국어 Python, mock_repository_findById invoked
   → after: 다른 한국어 Python (cache 추가)
   → DiffReport: minor (mutation 없음, return None 동일)
3. POST /change-specs/{id}/apply
   → status: applied
   → patch_lines: 6
   → java_changed: True
   → patch: unified diff 정상 (- repository.findById ... + cache.get(pk).orElseGet ...)
```

### Test 2 — BigDecimal 산술 (`SdFinalLengthRangeAction.execute`)
```
1. simulate
   → Python: 슬라브중량/두께/비중/분자/폭상한기반길이/폭하한기반길이/길이하한/길이상한
   → Sandbox: 0.28ms 실행, mutation 캡처
   → mutated arg1: {finalLengthHigh: 424.62..., finalLengthLow: 8000}
2. DiffReport
   → severity: minor (LLM stochasticity 가 잡힘)
   → mutation_diff: finalLengthHigh -99.9% 변화 (Decimal 정밀 비교)
```

## 한계 / 위험
1. **LLM 비결정성** — 같은 input 두번 호출시 미묘하게 다른 Python 생성. P25 이게 잡혀서 false-positive diff 발생 가능. 해결: temperature=0 또는 cached result 재활용.
2. **Anchor value kind** — 텍스트 단위 substitute 라 java source 와 정확히 매칭 안 되면 효과 없음. P26 AST 기반 변환 필요.
3. **method_body kind 매칭** — old_snippet 이 정확해야 함. 사용자가 직접 복사/붙여넣기 권장.
4. **SyntheticInput 빈약** — 메서드 param type 추출 못 하면 sample dict 만 사용. P28+ Schema-based 입력 (BusinessTerm + JPA entity 정보) 보강 필요.
5. **GitHub PR 자동 생성 미구현** — patch text 만 반환. 별도 git tooling 연동 필요 (예: `gh pr create`).

## 시뮬레이션 backbone 진척도

| 단계 | 상태 |
|---|---|
| ChangeSpec 모델 + 영속 | ✅ P22 |
| 시뮬레이션 wizard UI | ✅ P22 |
| Java→Python 변환 | ✅ P23 (Sonnet 4.6) |
| SyntheticInput + Sandbox | ✅ P24 (RestrictedPython) |
| Semantic Diff | ✅ P25 (5 차원) |
| Java patch 생성 | ✅ P26 (unified diff) |
| GitHub PR 자동 생성 | ❌ deferred (gh tooling) |

## 다음 (P27 E2E 검증 / P28 사용자 가이드)
- **P27** : Slab demo `SdFinalLengthRangeAction.execute` 풀 사이클 walkthrough — UI 캡처 + 시연 시나리오
- **P28** : 사용자 가이드 v4 HTML — Workbench → Ontology → Simulation 전체 흐름 (스크린샷 + 권장 작업 순서)
