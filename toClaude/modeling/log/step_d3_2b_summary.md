# Step OD-11-D3-2-b — CONFLICTS_WITH LLM Comparator (pydantic-ai Agent)

완료일: 2026-04-21

## 스코프

D3-2 2-subphase 의 2/2 (D3-2-b). D3-2-a 에서 Protocol 만 정의했던 `LLMComparator`
의 운영 구현체. `HierarchicalGapEngine` 의 stage 3 (의미 비교 + severity 재평가)
를 담당. 실 OpenAI / Ollama / Anthropic 호출은 `llm_factory.get_model()` 재사용
으로 환경 변수 스위치 (`settings.litellm_model`) 한 곳에서 제어.

## 신규 산출물

### Backend (1 신규 + 2 edit)

1. `backend/modeling/gap_detection/llm_comparator.py` (~210 LOC)
   - `LLMComparisonResult(BaseModel)` — pydantic-ai 구조화 출력 타입
     - `severity: Literal["low","medium","high","critical"]` — 4 값 강제
     - `reasoning: str` — LLM 판단 근거 한두 문장
   - `_SYSTEM_PROMPT` — ERP/MES/SCM 비즈니스 규칙 충돌 분석가 역할,
     severity decision guide (low/medium/high/critical), hallucination 금지 지침
   - `_render_user_message(rule, fragment, prior_severity)` — rule FQN/terms_ref/
     statement + fragment FQN/section_fqn/kind/text + prior severity 직렬화.
     LLM 이 결정적 선행 판단을 참고할 수 있도록 prior severity 노출.
   - `_default_agent_factory()` — lazy import of pydantic-ai `Agent` +
     `llm_factory.get_model()`, `retries=2`, `defer_model_check=True`.
   - `PydanticAILLMComparator(agent_factory=None)` — `LLMComparator` Protocol 구현
     - `agent_factory` 주입 가능 (테스트에서 Fake Agent 치환)
     - `compare()` → `agent.run_sync()` 블로킹 호출
     - **Graceful degrade** : 어떤 예외도 재발생 안 함 → `(prior_severity,
       "LLM error: {ExcType}: {msg}")` 반환 → scan 파이프라인 안정성 우선
     - `result.output` 없으면 `"LLM error: empty output"` + prior 유지
   - `_coerce_conflict_severity(raw)` — Belt-and-suspenders 이차 방어:
     Literal 을 우회한 raw 문자열을 GapSeverity 로 변환하면서 CONFLICTS_WITH
     카테고리 (LOW/MEDIUM/HIGH/CRITICAL) 만 허용. "hard"/"soft" 같은 MISSING_IN
     카테고리 → `None` → `MEDIUM` fallback + reasoning 에 경고 문구.
   - `_CONFLICT_SEVERITIES = frozenset({LOW, MEDIUM, HIGH, CRITICAL})` — 이차
     방어용 화이트리스트.

2. `backend/modeling/gap_detection/__init__.py` — public re-export 확장
   - `LLMComparisonResult`, `PydanticAILLMComparator` 추가.

3. `backend/main.py` lifespan — `ONTONG_LLM_COMPARATOR=openai` 분기
   - D2-2 `manuals_api.init(...)` 직후 위치.
   - `os.getenv("ONTONG_LLM_COMPARATOR","").lower() == "openai"` 일 때만
     `PydanticAILLMComparator()` 생성. 실패 시 try/except 로 `None` 로 폴백.
   - 현재는 변수 보관만. D3-3 에서 `create_gap_engine(llm=_llm_comparator)` 로
     주입 예정. 기본은 `None` → Hierarchical 엔진이 prior_severity 유지.

4. `pyproject.toml` — `[tool.pytest.ini_options].markers` 추가
   - `integration: marks tests that hit external services (real LLM, network)`
   - Unregistered marker warning 억제 + 명시적 게이트.

### Tests (1 신규)

5. `tests/test_llm_comparator.py` (13 tests, 12 pass + 1 integration skipped)
   - **Output schema (2)** : Literal 4값 accept / "apocalyptic" rejection (ValidationError)
   - **Protocol conformance (1)** : `isinstance(comp, LLMComparator)`
   - **Successful compare (2)** : 기본 경로 + 4 severity 네 모두 매핑
   - **Graceful errors (3)** : `ValidationError` / `TimeoutError` / 임의 `RuntimeError`
     모두 prior severity 보존 + reasoning 에 `"LLM error: {ExcType}"` 포함
   - **Prompt rendering (2)** : 본문에 rule/fragment 실제 값 포함 + prior severity
     소문자 노출
   - **Defensive fallbacks (2)** : "hard" (MISSING_IN 카테고리) / "apocalyptic"
     (unknown) → `MEDIUM` 폴백 + reasoning 에 "invalid"
   - **Integration smoke (1)** : `@pytest.mark.integration` +
     `@pytest.mark.skipif(not ONTONG_LLM_INTEGRATION)` 이중 게이트. 기본 스위트
     에서 SKIP.

## 설계 결정

- **pydantic-ai Agent 선택 (Q1=A)** : `builder_service.py` 와 동일 패턴으로 팀
  친숙. `output_type=LLMComparisonResult` 로 구조화 출력을 프레임워크가 강제 →
  환각 1차 차단. OpenAI SDK 직결보다 provider-agnostic.
- **llm_factory.get_model() 재사용 (Q2=A)** : 모델 스위치 단일 지점
  (`settings.litellm_model="provider/model"`) 유지. OpenAI/Anthropic/Ollama/Google
  등 모두 같은 경로.
- **동기 Protocol + run_sync (Q3=minimal inputs)** : D3-2-a 에서 정의한 sync
  Protocol 유지. 호출자 (REST/SSE) 는 D3-3 에서 `asyncio.to_thread` 로 이벤트 루프
  블록 회피. Protocol 변경 없음 = D3-2-a 테스트 회귀 제로.
- **Graceful degrade (Never raise)** : scan 은 대량 candidate 처리 — 한 건의 LLM
  실패가 전체 스캔 중단으로 번지면 안 됨. 예외 포착 후 prior severity 유지 +
  reasoning 에 에러 타입 기록하여 운영 진단 가능.
- **Belt-and-suspenders (Literal + enum 화이트리스트)** : pydantic-ai Literal
  이 일차 방어 (프레임워크 강제). 테스트/버그/모킹으로 우회 시 `_coerce_
  conflict_severity` 가 GapSeverity 엔텀 체크 + 카테고리 화이트리스트 (LOW/
  MEDIUM/HIGH/CRITICAL) 로 이차 방어. MISSING_IN 카테고리 값 ("hard"/"soft") 은
  CONFLICTS_WITH 결과로 올 수 없으므로 MEDIUM 폴백.
- **Integration 격리 (Q4=A)** : 실 LLM 호출은 `@pytest.mark.integration`
  + 환경 변수 `ONTONG_LLM_INTEGRATION=1` 이중 게이트. 기본 `pytest` 는 skip, CI
  속도 및 비결정성 차단. `pytest -m integration` 로 수동 회귀 가능.
- **env 분기는 wiring 보류** : D3-2-b 는 comparator 인스턴스 생성까지만.
  Engine/API 에 실제 주입은 D3-3 에서 `create_gap_engine(llm=_llm_comparator)` +
  `gaps_api` 로 (API/UI 가 없으면 wiring 도 무의미). main.py 는 인스턴스 보관만.
- **prior severity 프롬프트 노출** : LLM 이 결정적 단계 판단을 override 할 수
  있도록 `[prior_severity_from_deterministic_stage]` 섹션 포함. 단, 보수적으로
  override — decision guide 는 4 카테고리 정의만 노출.

## 검증

- D3-2-b 범위 — `tests/test_llm_comparator.py` 13/13 선택 실행 : 12 PASS + 1
  SKIP (integration) (0.05s).
- 모델링 회귀 — `-k "modeling or manual or ... or llm_comparator or gap_engine"`
  747/747 PASS. D3-2-a 기준 735 → +12.
- 전체 suite — 1476 passed / 21 failed (Section 1 baseline, 무관) / 1 skipped
  (integration). D3-2-a 기준 1464 → +12.
- Runtime smoke — `python -c "from backend.modeling.gap_detection import
  PydanticAILLMComparator, LLMComparisonResult"` OK. main.py 구문 검사
  (`ast.parse`) OK. Routes 152 유지 (D3-2-b 도 API 미추가, D3-3 예정).

## 다음

- **D3-3 승인 큐 API + REST/SSE + 프런트 스텁** (Q5=A 승인 예정) :
  `backend/modeling/api/gaps_api.py` — `POST /api/modeling/gaps/scan` (mode 선택),
  `GET /gaps` (필터: direction / confirmed / severity / repo_id), `POST
  /gaps/{id}/confirm`, SSE `POST /gaps/scan/stream` (scanning/stage1/stage2/
  stage3/complete). 프런트 `ConflictsQueue` 페이지 (필터 + 행별 accept/reject
  + LLM reasoning 표시). `main.py` 에서 `_llm_comparator` 를
  `create_gap_engine()` 에 주입.
- **또는 D4 UI 디자인 스펙** — 전체 Gap 검증 UX 를 먼저 설계 후 D3-3 구현
  (프런트 first). 팀 리소스/일정에 따라 결정.

사용자 승인 대기.
