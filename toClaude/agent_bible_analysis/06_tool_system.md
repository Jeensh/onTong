# 06. Tool System 분석 — claw-code-parity

## 핵심 아키텍처: 3-Tier 툴 계층

### 계층 구조
```
Tier 1: MVP (Built-in) Tools — 하드코딩, ~50개, 즉시 사용 가능
Tier 2: Plugin Tools — 동적 로드, 충돌 감지, 외부 확장
Tier 3: Runtime Tools — 런타임 동적 등록 (MCP, 커스텀)
```

### GlobalToolRegistry
- 3개 계층 통합 관리, 이름 중복 시 fail-fast
- `with_plugin_tools()` / `with_runtime_tools()` — 충돌 감지 후 등록
- OnceLock 싱글턴 패턴으로 세션 수준 상태 관리

### Tool Spec 구조
```rust
ToolSpec {
    name: &'static str,
    description: &'static str,
    input_schema: Value,              // JSON Schema (LLM용 문서화)
    required_permission: PermissionMode,  // ReadOnly / WorkspaceWrite / DangerFullAccess
}
```

---

## 실행 플로우

```
execute_tool_with_enforcer(enforcer, name, input)
  → permission_check(enforcer, name, input)?    // 권한 게이트
  → from_value::<SpecificInput>(input)?          // 타입 안전 역직렬화
  → run_<tool_name>(input)                       // 핸들러 실행
  → to_pretty_json(result)                       // 결과 포맷팅
```

### 권한 3단계
| Level | 포함 도구 | 위험도 |
|-------|----------|--------|
| ReadOnly | read, glob, grep, web_fetch | 낮음 |
| WorkspaceWrite | write, edit, notebook, config | 중간 |
| DangerFullAccess | bash, agent, task, worker | 높음 |

### 에러 핸들링
- 모든 핸들러 `Result<String, String>` — 일관된 에러 타입
- 역직렬화 실패 → serde 에러 문자열
- IO 에러 → `.to_string()` 변환
- 미지원 도구 → `"unsupported tool: {name}"`
- MCP 서버 에러 → JSON-RPC error 래핑

---

## 혁신적 패턴

### 1. Deferred Tool Search (지연 검색)
- MVP 도구는 즉시 로드, 나머지는 lazy-load
- `ToolSearch` 도구로 검색 시 스코어링:
  - `select:tool1,tool2` — 명시적 선택
  - `+term` — 필수 포함
  - 정확 매치 +12점, 부분 +4점, 설명 +2~3점

### 2. 도구 이름 정규화
```
read → read_file
write → write_file
edit → edit_file
```
- 대소문자 무시, 언더스코어/대시 정규화
- 사용자 편의성 극대화

### 3. MCP 통합
```json
{
    "server": "string",
    "tool": "string",
    "result": <nested_result>,
    "status": "success|error"
}
```
- 네임스페이스: `{server}:{tool_name}`
- 연결 상태 추적: Disconnected → Connecting → Connected
- 스레드 스폰 + 30초 타임아웃

### 4. Tool Pool 조합
- `simple_mode`: Bash + FileRead + FileEdit만 허용
- `include_mcp`: MCP 도구 포함/제외 토글
- 필터 기반 조합으로 상황별 도구 세트 구성

---

## 🔄 온통 에이전트 적용 인사이트

### 현재 온통 vs claw-code-parity

| 항목 | 온통 (현재) | claw-code-parity |
|------|-----------|------------------|
| 도구 정의 | Python Protocol + to_tool_schema() | Rust ToolSpec + JSON Schema |
| 권한 | 없음 (모든 스킬 동등) | 3단계 퍼미션 |
| 에러 처리 | 스킬별 개별 처리 | 일관된 Result<String, String> |
| 이름 해석 | 정확 매치만 | 별칭 + 정규화 + 퍼지 매치 |
| 도구 풀 | 전체 노출 | 상황별 필터 조합 |
| MCP | 없음 | 네임스페이스 기반 통합 |

### 도입 가능한 전략

#### 1. 스킬 권한 레벨 도입
```python
class SkillPermission(Enum):
    READ = "read"       # wiki_search, wiki_read
    WRITE = "write"     # wiki_write, wiki_edit
    EXECUTE = "execute" # llm_generate, conflict_check
```
- 액션 타입(question/write/edit)에 따라 허용 스킬 필터

#### 2. 일관된 에러 포맷
```python
@dataclass
class SkillResult:
    success: bool
    data: Any
    error: str | None = None
    error_code: str | None = None
```
- 현재: 스킬마다 다른 에러 형태 → 통일

#### 3. 도구 풀 동적 조합
- 인텐트별 사용 가능 스킬 세트 제한
- WIKI_QA → wiki_search + wiki_read + llm_generate만
- SIMULATION → simulation 스킬만
- 불필요한 도구 노출 줄이기 → LLM 혼란 감소

#### 4. 스킬 이름 정규화
- "검색" → wiki_search, "위키 찾기" → wiki_search
- 한국어 별칭 매핑 테이블
