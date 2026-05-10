# 06 — 다음 개발자 onboarding 가이드 (Section 3 시뮬 에이전트 구현자용)

> **목적**: `00`~`05` 의 spec doc 5개 + 실제 onTong 코드/DB 사이 의 **bridge**. spec 만 있고 어디부터 어떻게 손대야 할지 막막한 상태를 없앤다.
>
> **상태**: 2026-05-10 작성. Phase D 종결 직전 인계 가능 상태에서.
>
> **읽기 순서**: 본 문서 → 00 README → 01~05 spec → 본 문서로 돌아와 STEP 3~4 코드 추가.

---

## 0. 본 문서가 답하는 질문

| 질문 | 답하는 절 |
|---|---|
| 코드/DB/UI 가 인계 시점에 무슨 상태인지 어떻게 검증? | STEP 2 |
| Section 3 (`backend/simulation/`) 첫 파일은 어디부터 만드나? | STEP 3 |
| 첫 ChangeSpec → SimResult 흐름은 어떻게 통과시키나? | STEP 4 |
| 운영 사고 회귀 시뮬은 어떻게 굴리나? | STEP 4.4 |
| Phase E 의 미결정 11건은 어디서 부딪히나? | Section 6 |
| 백엔드 import 깨졌을 때 무엇을 다시 돌리나? | Section 5 |

---

## 1. 인계 시점 시스템 한 화면 요약

```
┌──────────────────────────────────────────────────────────┐
│  onTong (단일 FastAPI process, port 8001)                 │
│                                                          │
│  ┌─────────────────┐   ┌──────────────────┐              │
│  │  Section 1      │   │  Section 2       │              │
│  │  wiki           │   │  modeling ★      │              │
│  │  (별 세션)      │   │  (이 인계 영역)  │              │
│  │                 │   │                  │              │
│  │ /api/wiki/*     │   │ /api/ontology/*  │              │
│  │ /api/search/*   │   │ /api/modules/*   │              │
│  └─────────────────┘   └──────────────────┘              │
│                                                          │
│  ┌──────────────────────────────────────┐                │
│  │  Section 3                           │                │
│  │  simulation ☆ (당신이 만들 영역)     │                │
│  │  /api/simulation/* (router 신규)     │                │
│  │  backend/simulation/* (코드 신규)    │                │
│  └──────────────────────────────────────┘                │
│                                                          │
│  data/ontology.db (80MB, SQLite)                         │
│   ├─ business_terms (16 atomic + 29 composite)           │
│   ├─ actions (38, all signature_locked)                  │
│   ├─ realizations (43, 35 confirmed)                     │
│   ├─ business_rules (17, all confirmed, enforced_by 100%)│
│   ├─ anchor_bindings (9, all confirmed, line filled)     │
│   ├─ call_sites (992 total, 109 ambiguous queue)         │
│   ├─ type_realizations (1428)                            │
│   └─ code_types / code_methods / code_fields (Java mirror)│
└──────────────────────────────────────────────────────────┘
```

★ = 인계자 (modeling 세션) 가 빌드 / 검증 완료
☆ = 인수자 (당신, simulation 세션) 가 빌드할 영역 — **폴더 자체가 아예 없음** (modeling 세션이 plug-in 방식으로 분리하면서 삭제). STEP 3.0 의 mkdir 부터 시작.

---

## STEP 1 — Repo orientation

### 1.1 디렉토리 지도

```
onTong/
├─ backend/
│  ├─ main.py                      ← FastAPI entry (port 8001). simulation router 추가는 여기 56-67 라인 참고
│  ├─ core/config.py               ← settings.fastapi_port = 8001
│  ├─ shared/contracts/
│  │  └─ ontology_query.py         ← TermDTO/ActionDTO/CallSiteDTO 등 (당신이 ★ import 하는 DTO)
│  │  └─ simulation.py             ← ☆ 신설할 ChangeSpec/SimResult/BREvidence
│  ├─ modeling/                    ← Section 2 — read-only 로 사용. 수정 금지.
│  │  ├─ api/                      ← /api/ontology/*, /api/modules/* 등 router (8개)
│  │  │  ├─ ontology_router.py     ← 18+ endpoint (terms / actions / BR / anchor / delegates-to-tree)
│  │  │  ├─ ontology_query.py      ← OntologyQueryClientImpl Python facade (HTTP 우회 가능)
│  │  │  ├─ modules_api.py         ← /api/modules/* (트리 + inventory)
│  │  │  └─ ...
│  │  ├─ code_layer/               ← Code 4-Layer. Java mirror.
│  │  ├─ domain_layer/             ← BusinessTerm + Composition + Inheritance + Rule
│  │  ├─ mapping_layer/            ← Action + Realization + AnchorBinding + TypeRealization
│  │  └─ persistence/database.py   ← bootstrap_database() — main.py 가 startup 시 호출
│  ├─ simulation/                  ← ☆ 당신이 만들 영역. **현재 폴더 자체가 존재하지 않음** — STEP 3.0 의 mkdir 으로 신설.
│  │  ├─ api/                      ← 신설 — router.py / run_handle.py 등
│  │  ├─ runner/                   ← 신설 — python_generator / java_sandbox / lookup_source / orchestrator
│  │  └─ __init__.py               ← 신설
│  ├─ application/                 ← Section 1 (wiki) + Agent registry. Section 3 의 SimulatorAgent 가 등록되는 곳.
│  └─ api/                         ← Section 1 (wiki / agent / search 등) router.
├─ data/
│  ├─ ontology.db                  ← ★ 인계받는 SQLite. 검증은 STEP 2.3.
│  └─ wiki/                        ← Section 1 위키 (인계 영역 외).
├─ scripts/
│  ├─ import_phase_archive.py      ← ontology DB 재import (STEP 5).
│  ├─ promote_actions.py           ← Action verification_level 진급.
│  ├─ extend_br_schema.py          ← BR enforced_by/operational_history 컬럼 보강.
│  └─ fix_action_output_anchor_line.py  ← Action.output_json + anchor.line 자동 채움.
├─ frontend/                       ← Next.js. Modeling Workbench 는 sections/modeling/.
├─ tools/
│  └─ check_agent_isolation.py     ← ★ "modeling 직접 import 금지" 정적 검사. CI 권장.
└─ toClaude/modeling/handoff-spec/ ← ★ 본 폴더. 본 문서 포함 6 doc.
```

### 1.2 의존성 방향 (절대 어기지 말 것)

```
simulation/  ─────── import OK ──────►  modeling/
                                       (read-only API + DTO)

modeling/    ─────── import 금지 ──►  simulation/
                                       (역방향 차단)
```

검증 도구: `python3 tools/check_agent_isolation.py`. CI 에 박아두면 사고 방지.

### 1.3 핵심 spec 5개 (이 폴더 안)

| 파일 | 무엇 | 언제 펼쳐보나 |
|---|---|---|
| `00-README.md` | 전체 가이드 + 18 endpoint 카탈로그 + 5 결정 | 처음 1번 + 임의 시점 reference |
| `01-schema-extensions.md` | BR/Action/BusinessTerm 컬럼 추가 + DesignGap/SimulationScenario 신규 | DB 마이그레이션 작성 시 |
| `02-ontology-api-additions.md` | `/api/ontology/*` 신규 endpoint 약 12개 | modeling 측에 endpoint 추가 요청 시 (당신은 호출만) |
| `03-simulation-api-spec.md` | `/api/simulation/*` 신규 router 약 10 endpoint | STEP 3 router 작성 시 |
| `04-changespec-simresult-schema.md` | ChangeSpec / SimResult / verdict 6 조건 / anchor invalidation | STEP 4 의 입출력 모델 정의 시 |
| `05-runner-interface.md` | PythonGenerator + JavaSandbox + LookupDataSource + Orchestrator | STEP 4 의 runner 코드 작성 시 |

### 1.4 도메인 primer (Java SCM 알고리즘)

`toClaude/modeling/phase-d-handoff-package.html` D.1 절을 한 번 펼쳐 도메인 4 sub-domain (`scm.std` / `scm.spec` / `scm.order` / `scm.slab`) 와 21-step slab-design 알고리즘 흐름 이해.

운영 사고 7건 (P-2018-0098 / P-2018-0237 / P-2018-0721 / P-2019-0445 / P-2020-0411 / 2017 회의 / 정XX 2018-12-04) 은 BR 17개 의 `operational_history_json` 에 들어있음. 회귀 시나리오 후보.

---

## STEP 2 — 환경 setup + 인계 상태 검증

### 2.1 의존성 설치

```bash
cd /path/to/onTong

# 1) Python 의존성
pip install -r backend/requirements.txt

# 2) Frontend 의존성
cd frontend && npm install && cd ..

# 3) 환경변수 — 최소 필요
export PYTHONPATH=/path/to/onTong          # backend.* import 가능하게

# 4) (선택) STEP 3~4 의 echo-stub 단계는 LLM 호출 없음. 단순 PythonGenerator 첫 흐름까지 LLM 키 불필요.
#    PythonGenerator 가 실 LLM 으로 코드 생성하는 단계로 진입할 때 (Phase E 후반):
#    backend/.env 에 ANTHROPIC_API_KEY 등 (기존 Section 1 wiki 가 이미 사용 중인 키 그대로 활용 가능 —
#    backend/core/config.py 의 settings 참조).
```

### 2.2 백엔드 구동

```bash
# (background 권장)
PYTHONPATH=$(pwd) python3 backend/main.py
# → uvicorn 0.0.0.0:8001 + reload (development)
# → ontology DB bootstrap_database() 자동 호출 (data/ontology.db 가 없으면 신설, 있으면 그대로)
```

확인: `curl http://localhost:8001/docs` → FastAPI Swagger UI.

### 2.3 ★ Ontology DB 인계 검증 (가장 중요)

다음 카운트가 모두 일치해야 정상 인계 상태:

```bash
PYTHONPATH=$(pwd) python3 - <<'PY'
import sqlite3
conn = sqlite3.connect('data/ontology.db')
c = conn.cursor()
checks = [
  ("business_terms WHERE repo_id='slab-design-real' AND kind='atomic'",                 16, "atomic"),
  ("business_terms WHERE repo_id='slab-design-real' AND kind='composite'",              29, "composite"),
  ("actions       WHERE repo_id='slab-design-real'",                                    38, "actions"),
  ("actions       WHERE repo_id='slab-design-real' AND verification_level NOT IN ('unmapped','draft')", 38, "verified actions"),
  ("realizations  WHERE repo_id='slab-design-real'",                                    43, "realizations"),
  ("business_rules WHERE repo_id='slab-design-real' AND confirmed=1",                   17, "BR confirmed"),
  ("business_rules WHERE repo_id='slab-design-real' AND enforced_by_json != '[]'",      17, "BR with enforced_by"),
  ("anchor_bindings WHERE repo_id='slab-design-real' AND confirmed=1",                  9,  "anchor confirmed"),
  ("anchor_bindings WHERE repo_id='slab-design-real' AND line IS NOT NULL",             9,  "anchor with line"),
]
for sql, expected, label in checks:
  c.execute(f"SELECT count(*) FROM {sql}")
  got = c.fetchone()[0]
  ok = "✅" if got == expected else "❌"
  print(f"  {ok} {label:30s} {got} (expected {expected})")
conn.close()
PY
```

**모두 ✅ → 인계 검증 통과.** 하나라도 ❌ 면 STEP 5 의 회복 명령 참고.

### 2.4 REST API smoke test

```bash
# 1) 도메인 별 term list
curl -s 'http://localhost:8001/api/ontology/terms?repo_id=slab-design-real&kind=atomic' | python3 -m json.tool | head -20

# 2) workflow Action 의 sub_actions 펼침 (★ Section 3 에서 자주 호출)
curl -s 'http://localhost:8001/api/ontology/actions/action.scm.slab.design_orchestrator/delegates-to-tree?max_depth=5' | python3 -m json.tool | head -30

# 3) BR 전체 (당신이 verdict 판정 시 참고)
curl -s 'http://localhost:8001/api/ontology/business-rules?repo_id=slab-design-real' | python3 -m json.tool | head -30

# 4) 9 anchor binding 모두
curl -s 'http://localhost:8001/api/ontology/anchor-bindings?repo_id=slab-design-real' | python3 -m json.tool | head -40
```

### 2.5 프론트엔드 구동 + UI 확인 (선택 — backend-only 작업이면 skip)

> Section 3 작업이 백엔드 simulation 만 만지는 PR 이라면 frontend 띄우지 않아도 됨. UI 검증은 modeling 측 변경 시만 필요.

```bash
cd frontend
npm install   # 첫 1회 만
npm run dev
# → http://localhost:3000 (port 3000)
```

Modeling Workbench (`/modeling`) 좌측 패널에서:

- **📦 코드** 탭 — Java 패키지 트리 + Action leaf 인라인. `com.example.slabdesign.feature.sd.process.std.service.ProductivityService` 클릭 시 우측 detail.
- **🧬 온톨로지** 탭 — Term/Action/BR/Anchor 4 섹션. 각 카운트 합계가 STEP 2.3 의 카운트와 일치하는지 시각 확인.
- **❗ 큐** 탭 — ambiguous call_sites 109 건. 운영 시 사용자가 confirm.

### 2.6 Section isolation 정적 검사

```bash
python3 tools/check_agent_isolation.py
# → "OK" 출력 시 modeling/ 직접 import 0건 (당신이 simulation 코드 추가 후에도 여기 통과해야 함)
```

---

## STEP 3 — Section 3 boilerplate (코드 추가 시작점)

### 3.0 폴더 신설 (★ 첫 단계)

```bash
mkdir -p backend/simulation/api backend/simulation/runner
touch backend/simulation/__init__.py
touch backend/simulation/api/__init__.py
touch backend/simulation/runner/__init__.py
```

### 3.1 신설 파일 6개 (★ 표시 = 본 spec 의 필수 구성품)

```
backend/shared/contracts/simulation.py            ★ 04-changespec-simresult-schema.md 따라 생성
backend/simulation/api/router.py                  ★ 03-simulation-api-spec.md 의 10 endpoint
backend/simulation/api/run_handle.py              ★ 03 의 run lifecycle state machine
backend/simulation/runner/orchestrator.py         ★ 05 Section 4.5 entry
backend/simulation/runner/python_generator.py     ★ 05 Section 1
backend/simulation/runner/java_sandbox.py         ★ 05 Section 2 (3-tier: stub / jvm_subprocess / graalvm)
backend/simulation/runner/lookup_source.py        ★ 05 Section 3 (3-mode: fixture / fixture_with_db_fallback / db_snapshot)
```

### 3.2 main.py wiring (2 위치 추가)

**위치 1 — import 블록**: `backend/main.py` 라인 67 (현재 modeling import 마지막 줄, `from backend.modeling.persistence.database import bootstrap_database` 다음 줄) 에 추가:

```python
# Section 3 (simulation) — 본 PR 추가
from backend.simulation.api import router as simulation_api
```

**위치 2 — router 등록 블록**: `backend/main.py` 라인 ~453 (`app.include_router(perspective_api.router)` 다음 줄). 현재 modeling router 들이 라인 448~453 에 등록되어 있으므로 그 다음에:

```python
app.include_router(simulation_api.router)
```

→ 새 PR 의 main.py diff 는 이 2 줄만 추가. 기존 modeling/wiki wiring 절대 변경 금지.

`tools/check_agent_isolation.py` 가 자동 통과해야 함 (당신은 `backend.modeling.api` 의 ontology_router / facade 만 import, internal layer 는 import 금지).

### 3.3 ChangeSpec / SimResult 모델 (`shared/contracts/simulation.py`)

`04-changespec-simresult-schema.md` 의 schema 그대로 Pydantic v2 BaseModel 로 옮긴다.

```python
# 04 의 ChangeSpec.scenario_fixture.lookups 형식이 한 곳 placeholder 인 점은
# Phase E backlog #41 에 등록된 미결정 — 당신이 첫 시나리오 잡으며 형식 확정.
```

### 3.4 PythonGenerator stub

`05-runner-interface.md` Section 1 의 인터페이스로:

```python
class PythonGenerator(Protocol):
    def generate(self, action_fqn: str, change_spec: ChangeSpec) -> GeneratedScript: ...
```

첫 구현은 단순화: action 의 primary realization 의 Java method body 를 LLM 으로 1:1 옮기지 않고, **action.output_json 의 default value 를 echo 하는 echo-stub** 부터.

(실 LLM 호출은 나중. 첫 흐름이 router → orchestrator → python_generator → java_sandbox → SimResult 까지 통과한 다음.)

### 3.5 JavaSandbox `stub_dispatch` tier

`05-runner-interface.md` Section 2 의 3-tier 중 가장 가벼운 `stub_dispatch` 부터:
- input AnchorBinding 의 expected runtime type 으로 무조건 dispatch
- 결과 type 은 action.output_json 따라 가짜 값 반환
- BR violation 검사 X (다음 tier 에서)

이 정도면 첫 흐름 통과 가능.

---

## STEP 4 — 첫 ChangeSpec → SimResult 흐름

### 4.1 시나리오 선정 — `action.scm.std.match_customer_limit_for_order` (Customer 표준 first-match 조회)

DB 검증 (당신이 STEP 2.3 통과 후 직접 실행 가능):

```bash
sqlite3 data/ontology.db "
  SELECT a.fqn, a.kind, a.label, a.params_json, a.output_json
  FROM actions a WHERE a.fqn='action.scm.std.match_customer_limit_for_order';
  SELECT r.code_method_fqn, r.scope, r.confidence
  FROM realizations r WHERE r.action_fqn='action.scm.std.match_customer_limit_for_order';
  SELECT id, anchor_locator, target_slot, line, confirmed
  FROM anchor_bindings WHERE target_action_fqn='action.scm.std.match_customer_limit_for_order';
  SELECT fqn, severity, statement, enforced_by_json
  FROM business_rules WHERE fqn='rule.scm.std.customer_find_first_match_strategy';
"
```

기대:
- Action: `kind=pure_function`, `label=고객표준 매칭 (first match)`, `params=[]`, `output={"type":"object_ref","object_ref_term":"term.scm.customer_std"}`
- Realization 1: `CustomerStdService.findFirstMatch(String,String,String,String)` — `scope=primary`, `confidence=1.0`
- Anchor 2: `anchor_customer_empty_check` (line 35, `matches.isEmpty() → null`) + `anchor_customer_first_match` (line 36, `matches.get(0)`)
- BR: `rule.scm.std.customer_find_first_match_strategy` — `severity=hard`, enforced_by 는 위 findFirstMatch method

이 시나리오를 첫 흐름으로 잡는 이유: 1 BR + 2 anchor 로 verdict 6 조건 (b, d) 을 실제로 굴리되, params 는 비어있어 atomic_overrides 노이즈 최소.

**다음 사람이 STEP 4 시작 전 확인할 결정** (사용자 합의 필요):
- Phase E backlog #41 (lookups row 형식) — 본 STEP 4 가 첫 시나리오로 spec 05 §3.3 형식을 굳히는 PR 이 됨. 사용자/팀 합의 후 진행.

### 4.2 ChangeSpec 작성 (spec 04 + 05 정합)

```python
from backend.shared.contracts.simulation import ChangeSpec

ChangeSpec(
  repo_id="slab-design-real",
  action_fqn="action.scm.std.match_customer_limit_for_order",

  # action.params_json=[] 이라 atomic_overrides 는 realization 의 method 인자에
  # broadcast 적용 (spec 04 §1.2 algorithm 4: atomic 슬롯 가진 모든 row 에 적용).
  # CustomerStdService.findFirstMatch(cmp, org, proc, grade) 의 4 인자가
  # term.scm.shared.{cmp, org, proc, grade} 와 1:1 매핑.
  atomic_overrides={
    "term.scm.shared.cmp":   "01",
    "term.scm.shared.org":   "20",
    "term.scm.shared.proc":  "S2",
    "term.scm.shared.grade": "S45C",
  },

  # spec 05 §3.3 형식 — key="{table_spec_fqn}:{pk}" + row 는 {pk, table_spec_fqn, columns}.
  scenario_fixture={
    "lookups": {
      "scm.std.CustomerStd:7": {
        "table_spec_fqn": "scm.std.CustomerStd",
        "pk": 7,
        "columns": {
          "cmp":      "01",
          "org":      "20",
          "proc":     "S2",
          "grade":    "S45C",
          "priority": 1,
          "customer": "정XX",
        },
      },
      "scm.std.CustomerStd:8": {
        "table_spec_fqn": "scm.std.CustomerStd",
        "pk": 8,
        "columns": {
          "cmp":      "01",
          "org":      "20",
          "proc":     "S2",
          "grade":    "S45C",
          "priority": 2,
          "customer": "박XX",
        },
      },
    },
  },
)
```

### 4.3 흐름 통과 기대값

```
POST /api/simulation/runs
  body = ChangeSpec (위)
  → 200 { run_id }

GET /api/simulation/runs/{run_id}
  → status: pending → running → completed
  → 내부 흐름:
    Orchestrator.start(change_spec)
      → PythonGenerator.generate("action.scm.std.match_customer_limit_for_order", change_spec)
        → echo-stub: CustomerStdService.findFirstMatch("01","20","S2","S45C") 호출 코드
      → JavaSandbox.stub_dispatch("CustomerStdService.findFirstMatch", ...)
        → LookupDataSource 가 CustomerStd:7 / :8 두 row 중
          BR (priority ASC 정렬 후 first) 적용 → priority=1 row 선택 → 정XX 반환
      → verdict 판정 (spec 04 §3.2):
        (b) 직접 BR `customer_find_first_match_strategy` evidence=passed (정렬 + first row 정상)
        (d) anchors `empty_check` (분기 안 탐) + `first_match` (탐) 모두 outcome=hit
      → SimResult 생성 — verdict=sim_verified

GET /api/simulation/runs/{run_id}/sim-result
  → SimResult { verdict: "sim_verified", artifact: {...}, evidence: [BR..., Anchor...] }
```

> ⚠ **위 ChangeSpec 의 atomic_overrides 키 형식** 은 spec 04 §1.2 의 algorithm 4 (bare token → OntologyQuery 로 atomic FQN resolve) 에 의해 `"grade": "S45C"` 형태로 단축 가능. 단축 form 의 첫 PR 합의는 Phase E #41 결정 시 함께.

### 4.4 다음으로 넓힐 시나리오

- **운영 사고 회귀** — `rule.scm.order.no_stock_order` (P-2018-0098 정XX 슬랩 중복 사고): order 가 stock 수량 초과로 생성 시도 → BR violation verdict
- **A-a 루프 회귀** — `rule.scm.slab.aa_loop_max_iter_cap` (P-2018-0721): max_iter 초과 시 verdict=violation
- **A-a 루프 정상 흐름** — workflow `action.scm.slab.aa_loop` 의 sub_actions 21단계가 sim_verified 로 통과하는지

### 4.5 verdict 6 조건 적용

`04-changespec-simresult-schema.md` Section 3.2 의 6 조건 (a~f) 을 verdict 판정 코드로 옮김. 각 조건마다 unit test 1개씩.

### 4.6 anchor invalidation 흐름

`04` Section 4 의 3-trigger (PR merge / manual / auto-detect) 중 첫 구현은 **manual** 만 — `POST /api/simulation/anchor-invalidate` body=`{anchor_ids: [...]}`. PR merge / auto-detect 는 Phase E (#39 IDE refactor 포함).

---

## 5. 회복 / 재import 명령

DB 깨졌거나 의심스러우면:

```bash
# 1) atomic 16 + BR 17 + AnchorBinding 9 재import (idempotent)
PYTHONPATH=$(pwd) python3 scripts/import_phase_archive.py --dry-run    # 검증
PYTHONPATH=$(pwd) python3 scripts/import_phase_archive.py              # 실행

# 2) BR enforced_by + operational_history 컬럼 + 데이터 17건 (idempotent)
PYTHONPATH=$(pwd) python3 scripts/extend_br_schema.py --dry-run
PYTHONPATH=$(pwd) python3 scripts/extend_br_schema.py

# 3) Action.output_json + anchor.line 자동 채움 (idempotent)
PYTHONPATH=$(pwd) python3 scripts/fix_action_output_anchor_line.py --dry-run
PYTHONPATH=$(pwd) python3 scripts/fix_action_output_anchor_line.py

# 4) Action verification_level 진급 (signature_locked 까지)
PYTHONPATH=$(pwd) python3 scripts/promote_actions.py
```

순서: 1 → 2 → 3 → 4. 각 스크립트는 idempotent (`INSERT OR IGNORE` + `ALTER ADD COLUMN IF NOT EXISTS` 패턴).

---

## 6. Phase E 결정 대기 항목 (어디서 부딪히나)

`toClaude/modeling/design-gaps-and-questions.md` 의 #37~#47 (총 11건) — 본 인계 시점 미결정. STEP 4 진행 중 부딪히면 그때 결정.

| # | 부딪히는 STEP | 가벼운 시작 옵션 |
|---|---|---|
| #37 4번째 verdict "advisory_warning" | STEP 4.5 verdict 판정 | 일단 3-tier (sim_verified/violation/inconclusive) 만. drama DNA 는 sim_verified 안에 sub-tag |
| #38 transitive BR 누락 정책 | STEP 4.5 | direct BR 누락 → inconclusive, transitive → warning 로 시작 |
| #39 anchor T4/T5 (Maven / IDE) | STEP 4.6 | manual + PR merge 만 first iteration |
| #40 재바인딩 알림 큐 | STEP 4.6 | 일단 stale 만 마킹, 알림 큐는 나중 |
| #41 lookups schema 형식 | STEP 4.2 ChangeSpec 작성 | `{"TableName": [row, ...]}` 로 첫 시나리오 잡고 굳히기 |
| #49 atomic ↔ method-arg 매핑 부재 | STEP 4.2 atomic_overrides 적용 | first match 시나리오 (cmp/org/proc/grade) 는 인자명 1:1 → broadcast 작동. 다른 시나리오 부딪히면 결정 |
| #42 BRException 구분 | STEP 4 verdict | 첫 iteration: BR.enforced_by method 의 throw 만 BRViolation. 일반 RuntimeException 은 inconclusive |
| #43 type_assignable | STEP 3.5 JavaSandbox | Java reflection `Class.isAssignableFrom` 만. generic 은 phase E |
| #44 LookupDataSource 3 mode | STEP 3.5 lookup_source | `fixture` 모드만 first iteration. fallback / snapshot 은 나중 |
| #45 drama_dna_columns 활용 | (현재 dead) | 무시 OK. 활용처는 verdict 후 explanation panel 에서 결정 |
| #46 artifact streaming | STEP 4.3 GET /artifacts | 일괄 dump 부터. streaming 은 나중 |
| #47 검증 7→12 step 보강 | (검증) | 첫 iteration 은 stub + jvm_subprocess 만 |

→ "Phase E 부딪힐 때 그때 결정" 자체가 인계자 합의. spec doc 만으로 막힐 위험 없음.

---

## 7. 자주 막히는 점

### Q1. `ModuleNotFoundError: No module named 'backend'`
A. PYTHONPATH 미설정. `export PYTHONPATH=$(pwd)` (onTong 루트에서) 또는 `PYTHONPATH=$(pwd) python3 ...` 명령 prefix.

### Q2. `bootstrap_database()` 가 ontology.db 를 덮어쓰지 않을까?
A. 안 덮어씀. 테이블 + 컬럼 누락 시만 ALTER. 데이터는 보존.

### Q3. `/api/ontology/business-rules` 가 404
A. main.py 에 ontology_router 가 include 됐는지 확인. STEP 2.4 의 curl 로 `terms` endpoint 가 응답하는지 우선 확인.

### Q4. modeling/ 의 코드를 Section 3 에서 부르고 싶을 때
A. 두 가지만 OK:
   - HTTP: `requests.get("http://localhost:8001/api/ontology/...")` (process 분리 가능)
   - Python facade: `from backend.modeling.api.ontology_query import OntologyQueryClientImpl` (DTO 만 의존, internal layer X)

  ❌ 금지: `from backend.modeling.mapping_layer.store import ...` 같은 internal import. CI 에서 `tools/check_agent_isolation.py` 가 차단.

### Q5. ChangeSpec.scenario_fixture.lookups 의 row 형식이 spec 에 명시 안 됨
A. Phase E backlog #41. 첫 시나리오 작성하면서 형식 굳혀서 `04` doc 보강 PR 제출.

### Q6. 1428 type_realization 중 무엇이 primary 인지?
A. `type_realizations.scope='primary'` 컬럼. `SELECT * FROM type_realizations WHERE scope='primary'`.

### Q7. 109 ambiguous call_sites 는 무시해도 되나?
A. STEP 4 첫 iteration 은 OK. `call_sites.user_confirmed_type IS NOT NULL` row 만 dispatch 에 활용. ambiguous 는 운영 시 사용자가 큐에서 confirm.

---

## 8. 도와줄 수 있는 곳

| 자료 | 위치 | 무엇 |
|---|---|---|
| 5 spec doc | `toClaude/modeling/handoff-spec/00-05` | 본 폴더 — 수만 자 정밀 명세 |
| 도메인 primer | `toClaude/modeling/phase-d-handoff-package.html` | 4 sub-domain + 21-step + 운영 사고 7건 + atomic 16 pool |
| Phase A/B/C ground truth | `toClaude/modeling/phase-c-archive-confirm.html` | 178 row 합의 표 |
| AnchorBinding 9건 deep-dive | `toClaude/modeling/anchor-binding-deep-dive.html` | 7 종 + 9 마커 (코드 레벨 매핑 의도) |
| design-gaps 47건 | `toClaude/modeling/design-gaps-and-questions.md` | Phase E backlog + 미결정 |
| Authoring agent (별 영역) | `toClaude/modeling/agent-graph-architecture.html` | 23 tool + per-cap 권한 (시뮬과 별개) |

---

## 9. 인계자 contact

본 명세 자체에 대한 질문 / Phase E 결정 / spec 충돌 발견 시:

- modeling 세션의 작업 자료는 모두 `toClaude/modeling/` 안에 있음 (HANDOFF.md / TODO.md / CHANGES.md / archive/)
- 섹션 격리: `backend/modeling/*` 와 `toClaude/modeling/*` 는 modeling 세션 책임. simulation 세션은 read-only 로 참조.

---

## 10. 인계 완료 정의 (이 문서 종료 조건)

다음 7 항목 모두 ✅ 면 인계 진짜 완료:

1. ✅ STEP 2.3 검증 9 항목 모두 통과
2. ✅ STEP 2.4 curl 4건 모두 200 응답
3. ✅ STEP 2.5 UI 의 3 탭 모두 정상 렌더 (코드 트리 + 온톨로지 탭 + 큐 탭)
4. ✅ STEP 2.6 isolation 검사 통과
5. ☐ STEP 3.1 신설 6 파일 골격 작성 (당신 PR)
6. ☐ STEP 4.3 첫 ChangeSpec → SimResult 흐름 통과 (당신 PR)
7. ☐ Phase E backlog #37~#47 중 STEP 4 에서 부딪힌 항목 결정 (필요 시)

1~4 = modeling 세션이 검증 완료한 인계 시점 상태. 5~7 = 당신이 빌드하면서 채울 부분.

---

마지막 업데이트: 2026-05-10
