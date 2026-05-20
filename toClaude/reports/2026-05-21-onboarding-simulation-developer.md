# 시뮬레이션 담당자 Onboarding 가이드

> **목적**: Section 2 (modeling) 의 업그레이드 된 ontology 위에서, 본인이 만든 시뮬레이션 에이전트를 Section 3 의 새 탭으로 추가
> **브랜치**: `share/section2-modeling-foundation`
> **From**: jeensh · **Date**: 2026-05-21
> **선행 자료**: `toClaude/reports/2026-05-20-handoff-section2-modeling-foundation.md` (깊은 컨텍스트)

---

## TL;DR

1. 브랜치 받기 → 환경 셋업 (5분)
2. slab-design-real-v2 import + snapshot reapply → **136/136 sim_verified 즉시 복구** (3분)
3. backend + frontend 기동 → http://localhost:3000 에서 동작 확인
4. 본인 에이전트 추가 위치: `backend/section3/agents/` + `frontend/src/components/section3/` (탭형 nav 확장)

---

## 1️⃣ 브랜치 받기

```bash
git clone https://github.com/Jeensh/onTong.git   # 또는 fetch
cd onTong
git checkout share/section2-modeling-foundation
```

---

## 2️⃣ 환경 셋업

### Backend (Python 3.12)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Frontend (Node 18+)

```bash
cd frontend
npm install   # 또는 pnpm / bun
cd ..
```

### LLM API key (Section 3 멀티턴 agent intent classifier 가 사용)

`.env` 파일 (프로젝트 루트) 에 추가:

```bash
OPENAI_API_KEY=sk-...
```

→ 없으면 multiturn 의 intent classification 이 `ambiguous` 만 반환하고 candidates 가 비어요. simulate / impact 분기 위해 필수.

---

## 3️⃣ 데이터 복구 — slab-design-real-v2

> 실제 `data/ontology.db` (5.4MB) 는 `.gitignored` 라 git 에 없음. snapshot JSON 으로 복구.

```bash
# (a) Java repo import — slab-design-real-v2 가 있어야 함
#     없으면 jeensh 에게 sample-repos/slab-design-real_v2/ 압축 요청
ls sample-repos/slab-design-real_v2/  # 확인

# (b) backend 한 번 띄워서 UI Import 사용, 또는 직접 호출
PYTHONPATH=. .venv/bin/python -c "
from backend.modeling.code_layer.importer import ImportJob, RepoImporter
job = ImportJob(
    id='onboard-import',
    repo_id='slab-design-real-v2',
    repo_path='/full/path/to/sample-repos/slab-design-real_v2',
)
RepoImporter().run(job)
print('import done')
"

# (c) snapshot reapply — 136/136 sim_verified 복구
.venv/bin/python scripts/reapply_modeling_enrichment.py \
  --db data/ontology.db \
  --snapshot data/enrichment_snapshot_slab_design_real_v2_20260520_152937.json \
  --hybrid
```

**`--hybrid` flag 핵심**: native parser 가 `single_impl` / `annotation` 으로 ≥0.85 conf 분류한 1,435 행은 그대로 두고, `static_unresolved` 만 snapshot 의 manual cleanup 라벨로 채움. 결과:

| 영역 | 값 |
|---|---|
| code_types | 150 |
| code_methods | 1,081 |
| call_sites | 2,298 (needs_user_confirm 51 = 외부 JDK only) |
| **actions** | **136 / 136 sim_verified (100%)** |
| business_terms | 83 |
| business_rules | 22 |
| realizations | 148 |
| anchor_bindings | 163 |

---

## 4️⃣ 기동 + 확인

### Backend (port 8001)

```bash
.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8001 --log-level info
```

### Frontend (port 3000)

```bash
cd frontend && npm run dev
```

### 동작 확인

```bash
# 데이터 정상 surface 확인
curl http://127.0.0.1:8001/api/section3/repos | jq
# → {"repos":[{"repo_id":"slab-design-real-v2","counts":{"actions":136,...}}]}

# 멀티턴 에이전트 동작
curl -X POST http://127.0.0.1:8001/api/section3/multiturn/start \
  -H "Content-Type: application/json" \
  -d '{"user_query":"thickness 검증 시뮬레이션","repo_id":"slab-design-real-v2"}'
```

브라우저: `http://localhost:3000?section=modeling` (Section 2) / `?section=simulation` (Section 3 멀티턴).

---

## 5️⃣ 본인 에이전트를 Section 3 탭으로 추가

> 이 PR 에 이미 들어 있는 **멀티턴 에이전트** 는 reference. 본인 에이전트를 같은 ontology base 위 다른 탭으로 자유롭게 추가.

### 패턴 (3-step)

#### Step A — 백엔드 router 신설

`backend/section3/api/myagent_router.py` 신설. 패턴 참고: `backend/section3/api/multiturn_router.py`

```python
from fastapi import APIRouter
router = APIRouter(prefix="/api/section3/myagent", tags=["section3-myagent"])

@router.post("/start")
def start(...): ...

@router.post("/respond/{session_id}")
def respond(...): ...
```

등록: `backend/main.py` 에 `app.include_router(myagent_router.router)`

#### Step B — 에이전트 로직

`backend/section3/agents/myagent/` 폴더 신설. 패턴 참고: `backend/section3/agents/multiturn/` (17 파일 구조)

**ontology 읽기** — 이미 도구가 정리돼 있음:

```python
from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import load_actions
from backend.modeling.code_layer.store import session_scope

with session_scope() as s:
    actions = load_actions(s, repo_id='slab-design-real-v2')
    # → 136 actions 모두 surface (description, effects, code_method_fqn, ...)
```

**시뮬레이션 실행** — translator + sandbox 도구:

```python
from backend.sim_v2.core.synthesizer.java_translator import JavaToPythonTranslator
from backend.sim_v2.core.verification.behavior_twin_runner import BehaviorTwinRunner
from backend.sim_v2.core.verification.sandbox_stubs import build_stub_namespace
```

130 actions 모두 valid Python emit + 6 stuck actions runtime exec 검증됨.

#### Step C — Frontend 탭 추가

`frontend/src/components/section3/myagent/` 폴더 신설. 패턴: `multiturn/` (13 컴포넌트).

`frontend/src/components/section3/Section3Section.tsx` 의 `MAIN_NAV` 에 새 view 추가:

```tsx
const MAIN_NAV = [
  // ...
  { id: 'myagent', label: '본인 에이전트', icon: ... },
];
```

URL routing 패턴은 이미 `?view=myagent&sid=<session-id>` 로 동작.

---

## 6️⃣ 핵심 코드 위치

### Section 2 (modeling — 데이터 base)
| 위치 | 역할 |
|---|---|
| `backend/modeling/code_analysis/java_parser.py` | Java → 코드 그래프 (receiver_type 자동 채움) |
| `backend/modeling/code_analysis/method_symbol_table.py` | per-method symbol scope (param/local/field) |
| `backend/modeling/code_layer/store.py` | code_types / code_methods / code_fields / call_sites ORM |
| `backend/modeling/mapping_layer/schema.py` + `store.py` | actions / realizations / type_realizations / anchor_bindings |
| `backend/modeling/domain_layer/store.py` | business_terms / business_rules |
| `backend/modeling/audit/`, `memos/` | Coverage / Impact 추적 + entity 메모 |
| `backend/modeling/api/*` | 30+ REST endpoint (graph / ontology / queue / coverage / impact / memo 등) |

### Section 3 (시뮬레이션 — 본인 탭이 들어갈 곳)
| 위치 | 역할 |
|---|---|
| `backend/section3/agents/multiturn/` | reference 멀티턴 에이전트 (17 모듈) |
| `backend/section3/agents/{bridge,sandbox}_agent.py` | 옛 v1 에이전트 (deprecate notice 있음) |
| `backend/section3/sim_v2_bridge.py` | sim_v2 함수 wrap |
| `backend/section3/api/multiturn_router.py` | 멀티턴 REST 진입점 (참고) |
| `frontend/src/components/section3/multiturn/` | reference 13 컴포넌트 |
| `frontend/src/components/section3/Section3Section.tsx` | nav + view routing |
| `frontend/src/lib/section3/multiturn.ts` | HTTP client 패턴 |

### sim_v2 (Java → Python + sandbox)
| 위치 | 역할 |
|---|---|
| `backend/sim_v2/core/synthesizer/java_translator.py` | Java → Python (W75 idiom 포함, 5 patches) |
| `backend/sim_v2/core/verification/behavior_twin_runner.py` | sandbox exec |
| `backend/sim_v2/core/verification/sandbox_stubs.py` | stub namespace 합성 |
| `backend/sim_v2/core/verification/action_method_verifier.py` | translator gate (VERIFIED 판정) |
| `backend/sim_v2/core/ontology/domain_layer/production_domain_loader.py` | actions 일괄 로드 |

---

## 7️⃣ 추가 자료

| 문서 | 용도 |
|---|---|
| `toClaude/reports/2026-05-20-handoff-section2-modeling-foundation.md` | 이 가이드의 long-form 버전 |
| `toClaude/simulation/MODELING_DATA_AUDIT.md` | Phase A~E + E-C arc 누적 (130 → 136 sim_verified 도달 과정) |
| `toClaude/simulation/CHAT_REDESIGN_SPEC.md` | 멀티턴 에이전트 spec (6-gate 흐름) |
| `toClaude/simulation/log/step_chat_redesign_phase*.md` | Phase 1~11 단계별 작업 요약 |
| `toClaude/simulation/log/step_ec_parser_translator_rework.md` | parser + translator rework 상세 |
| `toClaude/simulation/HANDOFF_phase21_for_artifact_session.md` | 발표/리포트 산출물 컨텍스트 |
| `toClaude/simulation/CHANGES.md` | 변경 로그 |
| `toClaude/_shared/agent_tools_schema.md` | agent 가 호출 가능한 ontology tool 카탈로그 |

---

## 8️⃣ 알아두면 좋은 것 (caveat)

- **`OPENAI_API_KEY` 없으면** intent classifier 가 항상 `ambiguous` → multiturn 데모 불가. `.env` 에 키 추가 필수.
- **재 import 시 enrichment 보호**: 매 import 직전 `python scripts/export_modeling_enrichment.py --repo-id slab-design-real-v2` 로 snapshot 갱신, 그 다음 import → reapply `--hybrid`. 안 그러면 본인이 쌓은 작업도 같이 날아감.
- **`data/ontology.db.bak-pre-*`**: jeensh 가 남겨둔 백업들. 문제 생기면 복구 가능.
- **51개 needs_user_confirm**: 외부 JDK 호출 (Objects.equals, JDBC 등) — 의도된 보류. 추가 처리 불필요.
- **6개 SQL-promoted sim_verified (`confirmed_by='translator_e_c3_runtime_verified'`)**: test/utility 코드 (SdDesigner.*, TraceCollector.* 등). 본인 에이전트가 이들을 사용해도 OK. Runtime 실제 exec 까지 확인 완료.
- **light theme**: 프로젝트 UI 가 light theme 이라 amber 등 색상 변경 시 amber-900 같은 진한 색 사용 (밝게 가면 invisible).
- **cross-section 권한**: jeensh 가 modeling + simulation 양쪽 작업했음. 본인 작업도 양쪽 손볼 수 있으면 좋고, 충돌 우려 시 분담 합의 권장.

---

## 9️⃣ 막히면

- `toClaude/_shared/verify.sh` 실행: pytest + tsc + API + 채팅 + 충돌 오탐 일괄 체크.
- 멀티턴 회귀: `.venv/bin/python -m pytest tests/simulation/ -q`
- Section 2 회귀: `.venv/bin/python -m pytest tests/code_layer/ tests/api/test_ontology_router.py -q`
- sim_v2 합성기: `.venv/bin/python -m pytest backend/sim_v2/tests/core/synthesizer/ -q` (399/399)
- 6 stuck action runtime: `PYTHONPATH=. .venv/bin/python scripts/verify_stuck_actions_runtime.py`

Slack/메신저로 jeensh 핑.

---

**Welcome aboard. 같은 ontology 위에서 두 에이전트가 나란히 동작하는 그림이 목표입니다.**
