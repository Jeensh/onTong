# Phase 11 — Session History Browser (Option B)

**날짜**: 2026-05-18
**브랜치**: `section3/chat-agent-redesign`
**출발점**: 사용자 질문 "지금 시뮬레이션 섹션에서 대시보드가 필요한지?에 대해 분석해줘"

## 1. 분석 단계

먼저 두 갈래 병렬 조사로 Section 3 의 frontend 화면 / backend metric 인벤토리 수행.

### 발견

- **현재 UI**: Multiturn Chat (primary) + Orientation Dashboard (ontology 통계). past session 누적 뷰 0.
- **backend 데이터 가용성**:
  - ✅ `section3_session` + `section3_decision_log` SQLite — session 단위 + per-turn gate 결정
  - ⚠ payload JSON 내부에 idiom_diffs / fixtures / sim results 가 있으나 정규화 미흡
  - ❌ LLMResponse / OracleResult / ProposalEvent 는 in-memory 만 — 영속성 부재
- **결론**: A (현재 유지) + B (Session History Browser) 가 데이터-비용-가치 모두 최우선. C/D/E 는 persistence 후속.

## 2. 인터랙티브 가치 분석 HTML

사용자가 "각각의 가치를 내가 더 이해하기 쉽도록 html로 인터렉티브하게 잘 시각화 해서 알려줄래?" 요청.

`toClaude/simulation/dashboard_value_analysis.html` 작성:

- 5 옵션 카드 (A/B/C/D/E) × 각각 토글 + mockup + 시그널 + 도입/보류 양면 이유
- 3 페르소나 시나리오 (데모 발표자 / 3 인 팀 운영자 / 디버거) — 토글에 따라 활성/비활성 라인 흐려짐
- 비용 × 가치 SVG matrix scatter
- 4 프리셋 (보류 / 최소 / 중간 / 풀) + localStorage 자동 저장 결정 박스

사용자 결정: **"추천대로 진행하자"** = "최소 (권장)" 프리셋 = A + B.

## 3. 구현 (TDD)

### 3.1. 테스트 작성 (RED)

`tests/simulation/test_multiturn_session_list.py` 신규 — 14 tests:

- **persistence.list_recent_sessions** (8):
  - empty
  - turn_count + last_gate_kind aggregate
  - last_activity_at desc 정렬
  - repo_id filter
  - search substring
  - case-insensitive search
  - limit
  - last_gate_kind = latest turn

- **GET /api/section3/multiturn/sessions** (6):
  - empty
  - /start 후 latest first
  - repo_id filter
  - search filter
  - limit
  - turn_count + status + last_gate_kind 포함

초기 실행: 1 fail (no `list_recent_sessions` attribute) — RED 확인.

### 3.2. Backend 구현 (GREEN)

**`backend/section3/agents/multiturn/persistence.py`**:

```python
@dataclass(frozen=True)
class SessionSummary:
    id: str
    repo_id: str
    status: str
    user_query: str | None
    created_at: datetime
    last_activity_at: datetime
    turn_count: int
    last_gate_kind: str | None


def list_recent_sessions(
    *, limit: int = 50, repo_id: str | None = None, search: str | None = None,
) -> list[SessionSummary]:
    # last_activity_at desc + ilike substring
    # 단일 query 로 decision rows 모두 fetch → in-memory aggregate (N+1 회피)
```

**`backend/section3/api/multiturn_router.py`**:

```python
class SessionSummaryView(BaseModel):
    id: str
    repo_id: str
    status: str
    user_query: str | None
    created_at: str
    last_activity_at: str
    turn_count: int
    last_gate_kind: str | None

class SessionsListResponse(BaseModel):
    sessions: list[SessionSummaryView]

@router.get("/sessions", response_model=SessionsListResponse)
def list_sessions(limit: int = 50, repo_id: str | None = None, search: str | None = None) -> SessionsListResponse:
    limit = max(1, min(limit, 200))   # clamp
    rows = p.list_recent_sessions(limit=limit, repo_id=repo_id, search=search)
    ...
```

GREEN: 14/14 tests PASS.

### 3.3. Frontend 구현

**API client** (`frontend/src/lib/section3/multiturn.ts`):

```typescript
export interface SessionSummary { id; repo_id; status; user_query; created_at; last_activity_at; turn_count; last_gate_kind; }
export async function listSessions(opts: { limit?; repo_id?; search? } = {}): Promise<SessionsListResponse> { ... }
```

**hook 확장** (`useMultiturnSession.ts`):

```typescript
const loadSession = useCallback(async (sid: string) => {
  esRef.current?.close();
  setState({ ...INITIAL, pending: true });
  await refresh(sid);
  setState((prev) => ({ ...prev, pending: false }));
}, [refresh]);

return { state, start, respond, confirm, reset, loadSession };
```

**MultiturnChat** — `initialSid` / `onNewSession` props 추가:

```typescript
const loadedSidRef = useRef<string | null>(null);
useEffect(() => {
  if (initialSid && loadedSidRef.current !== initialSid) {
    loadedSidRef.current = initialSid;
    loadSession(initialSid);
  }
}, [initialSid, loadSession]);
```

"새 대화" 시 `loadedSidRef.current = null` + `onNewSession?.()`.

**Section3Section** — URL `?sid=` routing:

```typescript
const [initialSid, setInitialSid] = useState<string | null>(readInitialSid);

const openSession = (sid: string) => {
  setActive("multiturn");
  setInitialSid(sid);
  pushUrlState("multiturn", sid);
};

const clearSid = () => {
  setInitialSid(null);
  pushUrlState("multiturn", null);
};
```

**DashboardPanel** — `RecentSessionsSection` 신설:

- debounced 200ms search input
- `SessionRow` 카드: timestamp pad2 + status tone 3종 + turn_count + Gate 라벨 + sid8 + repo_id
- Gate 라벨 매핑: target_selected→Gate I / bundle_prepared→Gate II / executed_simulation→Gate III·sim / executed_impact→Gate III·impact

## 4. 검증

### 4.1. pytest

```
tests/simulation/test_multiturn_session_list.py    14 PASS
tests/simulation/test_multiturn_router.py          32 PASS
tests/simulation/test_multiturn_persistence.py     13 PASS
─────────────────────────────────────────────────────────
                                                   59 PASS
```

regression 0.

### 4.2. TypeScript

```
$ cd frontend && npx tsc --noEmit
(clean)
```

### 4.3. 실 백엔드 sanity (localhost:8001)

```bash
# 16+ 기존 세션 surface
GET /api/section3/multiturn/sessions?limit=3 → 200
  efbbc532  active  turns=2  gate=target_selected   "cumulativeProductivity 바꾸면 영향?"
  507bd56f  active  turns=3  gate=bundle_prepared   "thickness 액션 시뮬해줘 SdThicknessAction"
  74eccb23  active  turns=3  gate=bundle_prepared   ...

# 새 세션 만들면 즉시 latest first
POST /multiturn/start ("테스트 세션 — dashboard browser 검증")
  → 9d2bec88
GET /sessions
  9d2bec88  active  turns=1  gate=target_selected   "테스트 세션 — dashboard browser 검증"  ← top

# Korean search filter
GET /sessions?search=테스트 → 1 match

# repo_id filter
GET /sessions?repo_id=nonexistent → 0
```

## 5. 변경 파일

### Backend (3)
- `backend/section3/agents/multiturn/persistence.py` (+90 lines: SessionSummary + list_recent_sessions)
- `backend/section3/api/multiturn_router.py` (+45 lines: SessionSummaryView + /sessions endpoint)
- `tests/simulation/test_multiturn_session_list.py` (new, 240 lines)

### Frontend (5)
- `frontend/src/lib/section3/multiturn.ts` (+30 lines: SessionSummary + listSessions)
- `frontend/src/components/section3/multiturn/useMultiturnSession.ts` (+22 lines: loadSession)
- `frontend/src/components/section3/multiturn/MultiturnChat.tsx` (+22 lines: initialSid/onNewSession)
- `frontend/src/components/section3/Section3Section.tsx` (+35 lines: ?sid= URL routing)
- `frontend/src/components/section3/DashboardPanel.tsx` (+120 lines: RecentSessionsSection + SessionRow)

### Docs
- `toClaude/simulation/dashboard_value_analysis.html` (new, 977 lines — 5 옵션 인터랙티브 분석)
- `toClaude/simulation/CHANGES.md` — Phase 11 섹션 추가
- `toClaude/simulation/TODO.md` — Phase 11 task 행렬 추가
- `toClaude/simulation/demo_guide.md` — Phase 11 시연 / 트러블슈팅 추가
- `toClaude/simulation/HANDOFF.md` — Phase 11 결과 surface
- `~/.claude/.../memory/project_chat_redesign_phase11_session_history.md` (new)
- `~/.claude/.../memory/MEMORY.md` — Phase 11 인덱스 추가
- `~/.claude/.../memory/project_status.md` — 최신 갱신 entry 추가

## 6. 다음 후보

- **Maturity badge** (대시보드 상단 — UC36 capstone 통과 시각 + MERGED proposal 수, modeling 시드 hook 필요)
- **Option C** (Verification metric dashboard — backend persistence 새 테이블 verification_result 필요)
- **Option D** (Proposal Pipeline — proposal_audit_log + integrator hook)
- **Option E** (Cost / Latency — llm_call_log)
