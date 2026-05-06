# A~D 통합 보강 — 시뮬레이션 history / Code BFS / 갭 흡수 / Sim hardening

## 요약 (4 작업 일괄)
사용자 결정 「A → B → C → D 순서대로 다 작업」 일괄 적용.

| 작업 | 결과 |
|---|---|
| **A** 시뮬레이션 history UI | 메서드 단위 ChangeSpec 목록 + 다시 보기/재실행/삭제. SpecHistoryRow 컴포넌트 |
| **B** Multi-Layer Impact code layer 활성화 | query_engine_factory 주입 → repo 별 lazy QueryEngine. lookup 메서드 11 nodes (3 callers + 6 anchor + ...) |
| **C** 갭 큐 → Workbench R 「✅ 갭」 흡수 | 메서드 단위 자동 filter (target/counterpart 매칭) + confirm/unconfirm 인라인. 갭 큐 탭 deprecation banner |
| **D** 시뮬레이션 한계 해결 | temperature=0 + 결과 캐싱 (반복 비용 절약), anchor_value tree-sitter AST 변환 (정확한 위치 변경) |

## 산출물

### A — 시뮬레이션 history
- `SimulationDrawer.tsx`
  - 새 prop `existingSpec?: ChangeSpecDto | null` — 있으면 step 자동 jump (completed → step 3, simulating → step 2)
  - Step 3 「다시 실행」 버튼 — `simulateChangeSpec` 재호출 (cache hit 으로 즉시)
- `MethodWorkbench.tsx`
  - state : `activeSpec`, `methodSpecs`, `specsLoading`
  - `loadMethodSpecs()` — `listChangeSpecsByMethod(repoId, fqn)` 호출, 메서드 변경시 자동 re-fetch
  - 「🔬 시뮬」 탭 안 「📋 시뮬레이션 기록」 collapsible — 각 spec status badge + kind + description + timestamp + 「↻」 새로고침
  - `SpecHistoryRow` — 클릭 = drawer 열기 with existingSpec; hover 시 X 삭제
  - `SPEC_STATUS_META` — 7 status 별 색상

### B — Code layer 활성화
- `backend/modeling/impact/multi_layer_propagator.py`
  - `query_engine` (인스턴스) → `query_engine_factory` (Callable[[repo_id], QueryEngine])
  - `_bfs_code` 가 호출 시 factory(repo_id) → 빈 result 시 None 반환 (ImpactQuery 직접 사용)
- `backend/main.py`
  - `_query_engine_factory(repo_id)` 정의 — `_impact_api._get_view(repo_id)` 활용 (cached GraphView 재사용)
  - `MultiLayerImpactPropagator(query_engine_factory=_query_engine_factory, ...)`
- 검증: `lookup` 메서드 multi-layer → code: 11 nodes (3 callers + 6 param anchors + ...), 1ms 미만

### C — 갭 큐 흡수
- `MethodWorkbench.tsx`
  - rightTab 타입 확장: `"gaps"` 추가
  - 탭 라벨 `✅ 갭`
  - `GapsPanel` 컴포넌트 (NEW)
    - `methodFilters` set : selected.fqn + 모든 methodRules.qualified_name + method_fqn
    - `listGaps({includeConfirmed})` 호출 → target_fqn / counterpart_fqn / startsWith filter
    - 행별 severity 배지 (hard 빨강 / soft 노랑 / critical 진빨강 / high 주황 / etc)
    - 「확정」/「해제」 토글 (`confirmGap` / `unconfirmGap`)
    - `GAP_SEVERITY_COLOR` map
- `GapQueue.tsx` — amber deprecation banner ("Workbench R 「✅ 갭」 탭으로 메서드 단위 빠른 검토")
- `ModelingSection.tsx` — 갭 큐 description "(deprecated)" 표시

### D — 시뮬 hardening
- `python_generator.py`
  - `ClaudePythonGenerator` 에 `temperature: float = 0.0` (결정적), `_cache: dict` (instance-level)
  - `_cache_key(method_fqn, java_source, var_hints)` — sha1 hash
  - `generate()` 시작 시 cache lookup → hit 이면 즉시 반환 + warning "(cached: 동일 입력 재호출 절약)"
  - 호출 후 `messages.create(temperature=self.temperature, ...)`
  - 성공 결과 cache 저장
- `apply_change_spec_to_java` 분리 → `_apply_anchor_value_change` 도입
  - tree-sitter `Parser(JAVA_LANGUAGE)` 로 java AST 파싱
  - `_replace_var_value(root, source_bytes, var_name, new_value)` — `variable_declarator name=var_name value=...` OR `assignment_expression left=var_name right=...` 매칭
  - 정확 byte offset 으로 `value` 부분만 치환
  - 못 찾으면 fallback: 단순 text replace (compat)

## 검증 (E2E, slab-design-real)

### A — history
- 새 spec 생성 → 「📋 시뮬레이션 기록」 에 즉시 표시
- 클릭 → drawer 열림, status=completed 면 step 3 자동 jump
- Step 3 「다시 실행」 → cache hit (LLM 미호출, 즉시 동일 결과)
- X 버튼 → 삭제 + 목록 자동 refresh

### B — code layer
- `GET /impact/multi-layer?target_fqn=CastSpecService.lookup&target_kind=code`
- 결과: code 11 nodes
  ```
  d1 [method] execute ← ['calls (static)']     # 3건
  d0 [anchor] param[cmpCd] ← ['anchor:param']  # 6건
  ```
- ontology / manual layer 도 함께 (기존 P19 동작 유지)

### C — gaps
- `GapsPanel` 메서드 필터 정상 — methodFilters 가 fqn + rule_fqn 모두 포함
- 「확정」 / 「해제」 토글 → POST /gaps/{id}/(un)confirm 동작
- 「확정 포함」 체크박스 토글 시 listGaps 재호출

### D — hardening
**temperature=0 + cache**
- 같은 ChangeSpec 두번 simulate → 두번째 즉시 (LLM 미호출)
- warnings 에 "(cached: 동일 입력 재호출 절약)" 표시

**anchor_value AST 변환** (`SdFinalLengthRangeAction.execute` 의 `numerator` 변경)
```diff
- BigDecimal numerator = slabWgt.multiply(INVERSE_UNIT);
+ BigDecimal numerator = slabWgt.multiply(INVERSE_UNIT).multiply(BigDecimal.valueOf(2));
```
- 정확히 `numerator` 변수의 value 부분만 변경
- 다른 라인 (lengthFromWidthHigh, lengthFromWidthLow) 영향 없음
- patch_lines: 8 (context 7줄 + change 1줄)

## 사이드바 변화

| Before | After |
|---|---|
| 갭 큐 (active) | 갭 큐 (deprecated banner) |
| (Workbench R 4 탭) | Workbench R **5 탭** : 룰검토/참고/영향/**✅ 갭** /시뮬 |

## 다음 (P27/P28 보류 중)
- P27 E2E walkthrough 시나리오 (`SdFinalLengthRangeAction.execute` 풀 사이클)
- P28 사용자 가이드 v4 HTML
