# E~H 폴리시 — Phase 5 / GitHub PR / multi-method / 자동 테스트

## 결과
사용자 「선택적 폴리시 4개 전부 진행」 — 4 작업 일괄 완료.

| 작업 | 결과 |
|---|---|
| **E** Phase 5 — DI 그래프 → Repository 흡수 | `RepositoryHub` (manage / DI 그래프 sub-tab). DI 그래프 standalone 탭 deprecation banner. |
| **F** GitHub PR 자동 생성 (gh CLI) | `pr_creator.py` (NEW): branch + apply + commit + push + `gh pr create --draft`. 단계별 graceful 실패. SimulationDrawer 「GitHub PR 만들기」 버튼. |
| **G** 시뮬레이션 multi-method | ChangeSpec.payload.related_methods (max 5) → 각 메서드 변환/실행/diff 결합. Step 1 textarea + Step 3 결과 카드. |
| **H** 자동 테스트 보강 | 4 신규 테스트 파일, **65 PASS** (diff_reporter 28 + sandbox_runner 21 + relation_store/change_spec 10 + ontology_graph_api 6). |

## 산출물

### E — Repository hub
- `frontend/src/components/sections/modeling/RepositoryHub.tsx` (NEW)
  - sub-tab `📦 저장소 관리` (RepositoryManager) / `🧬 DI 그래프` (DiGraphPanel)
- `ModelingSection.tsx`
  - `case "repository"` → `RepositoryHub` 사용
  - DI 그래프 sidebar description "(deprecated) Repository 탭 안 「DI 그래프」 sub-tab 으로 흡수"
  - `case "di-graph"` 에 amber deprecation banner wrapper

### F — GitHub PR 자동
- `backend/modeling/simulation/pr_creator.py` (NEW)
  - `create_pr_from_change_spec(spec_id, description, target_method_fqn, patch, target_file, repo_root?)`
  - Pre-checks: gh CLI 존재, git repo 검증, remote 존재
  - Stages: branch (reuse if exists) → `git apply` (`-p0/1/2/3` fallback) → commit (한국어 commit msg) → `push -u origin` → `gh pr create --draft`
  - `PRCreateResult` (success/stage/pr_url/branch_name/commit_sha/error/message)
- `change_specs_api.py` `POST /change-specs/{id}/create-pr` — pre-condition status=applied + applied.patch + target_file
- `simulation_result.pr` 에 결과 저장
- Frontend `SimulationDrawer`
  - 「GitHub PR 만들기」 버튼 (applied banner 안)
  - `createPrForChangeSpec` API 호출
  - PR 결과 표시 — success: emerald box + 클릭 가능한 PR URL + branch/commit; failure: red box + stage + error + message

### G — Multi-method
- `change_specs_api.py` `simulate` 안 `payload.related_methods: list[str]` 처리
  - 각 method 별 source 추출 → java patch 적용 (target 변경 적용) → before/after Python 변환 → sandbox 실행 → 별도 diff
  - Safety cap 5 methods, max_cases=2 (성능)
- `simulation_result.related_methods: list[{method_fqn, java_changed, before_python, after_python, diff}]`
- Frontend Step 1 — collapsible 「🔗 관련 메서드 추가」 textarea (한 줄에 한 fqn)
- Step 3 — violet 박스 「🔗 관련 메서드 영향 (N개)」 — 각 메서드: java 변경 여부 + severity 배지 + per-case summary

### H — 테스트 (65 PASS)
- `tests/test_diff_reporter.py` (NEW, **28 tests**) — value_diff / decimal_diff / mutation_diff / exception_diff / mock_diff / perf_diff / classify / report_diff (integration)
- `tests/test_sandbox_runner.py` (NEW, **21 tests**) — _default_value_for_type / _SampleDict fallback / literal anchor parsing / SyntheticInputGenerator / RestrictedPython 실행 (한국어 변수, Decimal, mock, mutation, exception, compile error, underscore attr block)
- `tests/test_relation_store_and_change_spec.py` (NEW, **10 tests**) — OntologyRelation put/get/list_by_repo/list_by_node/delete/derive_id, ChangeSpec put/get/list_by_method/status filter/delete/utf8 round-trip
- `tests/test_ontology_graph_api.py` (NEW, **6 tests**) — empty graph, term + rule nodes, include_unconfirmed, create relation (정상 + 잘못된 kind 400), delete relation (정상 + 404)

각 테스트 파일 isolation: `_isolated_db` fixture (tmp_path SQLite + database 모듈 reset).

## 검증 (전체 65/65)
```
tests/test_diff_reporter.py ............................  [ 43%]
tests/test_sandbox_runner.py .....................        [ 75%]
tests/test_relation_store_and_change_spec.py ..........   [ 90%]
tests/test_ontology_graph_api.py ......                   [100%]
============================== 65 passed in 0.59s ==============================
```

## 사이드바 변화

| Before | After |
|---|---|
| Repository (단순 manage) | Repository **hub** (manage + DI 그래프 sub-tab) |
| DI 그래프 (active) | DI 그래프 (deprecated banner) |

## 다음 (보류)
- P27 — `SdFinalLengthRangeAction.execute` E2E walkthrough
- P28 — 사용자 가이드 v4 HTML
