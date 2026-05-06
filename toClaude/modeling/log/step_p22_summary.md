# P22 — ChangeSpec 모델 + 시뮬레이션 bottom drawer (3 단계 wizard)

## 목적
시뮬레이션 *입력 명세* 와 *UI 진입점* 을 먼저 만든다. 엔진(P23 PythonGenerator,
P24 SandboxRunner, P25 DiffReporter)은 이 ChangeSpec 을 받아 실행하면 된다.

Q-U5 = 시뮬레이션 bottom drawer 3 단계 = 정의 → 실행 → diff/적용.

## 산출물

### Backend
- `backend/modeling/persistence/models.py` — `ChangeSpecRow` 추가 (11번째 ORM 테이블)
- `backend/modeling/simulation/__init__.py` (NEW) — 모듈 노출
- `backend/modeling/simulation/change_spec.py` (NEW)
  - `ChangeSpecKind` enum 5 종 — `rule_statement / rule_severity / anchor_value / method_body / term_binding`
  - `ChangeSpecStatus` enum 7 종 — `draft / ready / simulating / completed / applied / discarded / error`
  - `ChangeSpec` Pydantic + `derive_id` (sha1(repo|fqn|kind|desc|now)[:16])
  - `SqliteChangeSpecStore` — put/get/list_by_repo/list_by_method/delete
- `backend/modeling/api/change_specs_api.py` (NEW) — 7 엔드포인트
  - `POST   /change-specs` — 신규
  - `GET    /repos/{repo_id}/change-specs?status=...`
  - `GET    /methods/{method_fqn:path}/change-specs?repo_id=...`
  - `GET    /change-specs/{spec_id}`
  - `PUT    /change-specs/{spec_id}` — description/payload/status 부분 갱신
  - `DELETE /change-specs/{spec_id}`
  - `POST   /change-specs/{spec_id}/simulate` — **stub** (P23~P25 후 실제 엔진)
- `backend/modeling/api/modeling.py` + `backend/main.py` — wiring

### Frontend
- `frontend/src/lib/api/modeling.ts` — `ChangeSpecKind` / `ChangeSpecStatus` / `ChangeSpecDto` 타입 + 6 함수 (`createChangeSpec` / `listChangeSpecsByMethod` / `updateChangeSpec` / `deleteChangeSpec` / `simulateChangeSpec`)
- `frontend/src/components/sections/modeling/SimulationDrawer.tsx` (NEW) — bottom drawer 55vh 높이
  - **Step 1 정의** : kind 그리드 선택 (5종 카드, 색깔 + 아이콘 + 설명) + description 입력 + kind 별 payload 에디터
    - rule_statement / rule_severity → rule dropdown + 변경 전/후
    - anchor_value → anchor dropdown (literal/branch/local) + old/new 값
    - method_body → old/new snippet textarea
    - term_binding → action(add/remove) + term_fqn + code_fqn
  - **Step 2 실행** : ChangeSpec 요약 + 「Sandbox 실행 (mock)」 버튼 (P23~P25 안내)
  - **Step 3 결과** : Before/After 2-column + Diff 카드 + 「폐기」 / 「적용 (Java PR)」
  - 헤더 step badges (1.정의 / 2.실행 / 3.결과) — current=blue, past=emerald, future=muted
  - 푸터 wizard nav (이전 / 진행 버튼)
- `frontend/src/components/sections/modeling/MethodWorkbench.tsx`
  - R 「🔬 시뮬」 탭 placeholder → 「+ 새 시뮬레이션」 launcher + 3 단계 안내
  - `simDrawerOpen` state + `<SimulationDrawer ... />` 렌더 (메서드 선택 시만)

## 검증 (curl)

```
POST /api/modeling/change-specs
body: {repo_id:..., target_method_fqn:..., kind:"rule_severity", description:"lookup rule 을 hard 로 격상", payload:{rule_fqn:..., old:"soft", new:"hard"}}
→ 201 ChangeSpecDto (id=1be8f0b59f7d7efe, status=draft)

GET /api/modeling/repos/slab-design-real/change-specs
→ [{...}] list

POST /api/modeling/change-specs/{id}/simulate
→ status=completed, simulation_result={engine:"stub", before:{...}, after:{...}, diff:{...}}

DELETE /api/modeling/change-specs/{id}
→ {deleted: true}
```

## UI 변화
- **R 패널 「🔬 시뮬」 탭** : placeholder 제거, 「+ 새 시뮬레이션」 활성화 (메서드 선택 시), 3 단계 안내 추가
- **Bottom drawer** : 「+ 새 시뮬레이션」 클릭 시 화면 하단에서 expand, ESC 로 닫힘
- **Step 1** : 5 종 kind 카드, kind 별 payload 에디터 (rule dropdown + 변경 전/후, anchor dropdown + 값, method body textarea, term binding)
- **Step 2** : ChangeSpec 요약 + mock 실행
- **Step 3** : Before/After + diff + 적용/폐기

## 시뮬레이션 backbone 진척도

| 단계 | 상태 | 다음 |
|---|---|---|
| ChangeSpec 모델 + 영속 | ✅ P22 | — |
| 시뮬레이션 wizard UI | ✅ P22 | — |
| Java→Python 변환 | ❌ stub | **P23** PythonGenerator |
| SyntheticInput + SandboxRunner | ❌ stub | **P24** RestrictedPython |
| Before/After Diff | ❌ stub | **P25** DiffReporter |
| Java patch draft PR | ❌ stub | **P26** Apply 워크플로우 |

## 다음 (P23 — 가장 큰 위험)
PythonGenerator (Q-D=D1) — Java method body → 한국어 변수명 Python LLM 변환.
Slab `SdLengthRangeAction.execute()` 한 메서드 1~2 일 spike 권장.
실패 시 Q-D 결정 자체 재고 (Java JVM in-process? Java AST → Python AST 직역?).
