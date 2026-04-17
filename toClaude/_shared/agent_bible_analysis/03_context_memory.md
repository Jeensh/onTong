# 03. Context & Memory 관리 — claw-code-parity

## 핵심 아키텍처: 3단계 컨텍스트 압축

### 전체 흐름
```
대화 시작
  → 메시지 축적 (full history)
  → 100K 토큰 도달 시 Auto-Compaction 트리거
  → 오래된 메시지 → 구조화된 요약으로 압축
  → 최근 4개 메시지는 원문 유지
  → 요약 + 최근 메시지로 세션 재구성
  → 다시 축적 → 다시 압축 (체이닝)
```

### 1단계: 윈도잉 (Python 레이어)
```python
# 단순 tail: 최근 N개만 유지
def compact(self, keep_last: int = 10):
    self.entries[:] = self.entries[-keep_last:]
```
- 가장 단순, 정보 손실 큼

### 2단계: 스마트 요약 (Rust Compaction)
```rust
CompactionConfig {
    preserve_recent_messages: 4,   // 최근 4개 원문 유지
    max_estimated_tokens: 10_000,  // 요약 예산
}
```

**요약 구조:**
```
<summary>
Conversation summary:
- Scope: 18 messages compacted (user=8, assistant=8, tool=2)
- Tools mentioned: Bash, Read, Grep
- Recent user requests:
  - "파일 검색해줘" (160자 제한)
  - "버그 수정해줘"
- Pending work:
  - 아직 완료되지 않은 작업 (todo/next/pending 키워드 감지)
- Key files referenced: /path/to/file1, /path/to/file2
- Current work: 가장 최근 비어있지 않은 메시지 (200자 제한)
- Key timeline:
  - user: [첫 블록, 160자]
  - assistant: [첫 블록, 160자]
  ...
</summary>
```

**핵심**: 단순 "요약해줘"가 아니라 **구조화된 추출**
- Scope (규모), Tools (사용 도구), Requests (요청), Pending (미완료), Files (파일), Timeline (타임라인)

### 3단계: 요약 압축 (Summary Compression)
```rust
SummaryCompressionBudget {
    max_chars: 1_200,
    max_lines: 24,
    max_line_chars: 160,
}
```

**우선순위 기반 라인 선택:**
```
Priority 0 (핵심): Scope, Current work, Pending work, Key files, Tools, Recent requests
Priority 1: 섹션 헤더 (`:` 로 끝남)
Priority 2: 리스트 항목 (`- `, `  - `)
Priority 3: 나머지
```
- 예산 내에서 높은 우선순위부터 채움
- 중복 라인 제거
- 초과 시 `"… N additional line(s) omitted."` 추가

### 요약 체이닝 (재압축 시)
```
- Previously compacted context:
  [이전 압축의 하이라이트]
- Newly compacted context:
  [현재 압축의 하이라이트]
- Key timeline:
  [현재 타임라인]
```
- 이전 요약을 버리지 않고 **레이어링**

### Continuation Message (압축 후 모델에게 주는 지시)
```
"This session is being continued from a previous conversation that ran out of context.
The summary below covers the earlier portion of the conversation.

[요약]

Recent messages are preserved verbatim.

Continue the conversation from where it left off without asking the user any
further questions. Resume directly — do not acknowledge the summary, do not recap
what was happening, and do not preface with continuation text."
```

**핵심**: "요약을 인정하지 마라, 그냥 이어서 해라" — 메타 대화 방지

---

## 세션 영속성: JSONL 스트리밍

```jsonl
{"type":"session_meta","version":1,"session_id":"abc123","created_at_ms":1000}
{"type":"message","message":{"role":"user","blocks":[{"type":"text","text":"..."}]}}
{"type":"message","message":{"role":"assistant",...}}
{"type":"compaction","count":1,"removed_message_count":18,"summary":"..."}
```

- 메시지 추가 시 append만 (전체 재작성 없음)
- 256KB 이후 로테이션, 최대 3개 보관
- 크래시 복구 가능

---

## 🔄 온통 에이전트 적용 인사이트

### 현재 온통 vs claw-code-parity

| 항목 | 온통 (현재) | claw-code-parity |
|------|-----------|------------------|
| 히스토리 | `history[-6:]` 고정 슬라이스 | 전체 유지 + 스마트 압축 |
| 압축 방식 | 없음 (단순 잘림) | 구조화된 요약 + 우선순위 압축 |
| 압축 트리거 | 없음 | 100K 토큰 자동 |
| 요약 내용 | 없음 | Scope/Tools/Requests/Pending/Files/Timeline |
| 요약 체이닝 | 없음 | Previously + Newly compacted |
| 세션 영속성 | 인메모리 dict | JSONL append + rotation |

### 도입 우선순위

#### 1. (즉시) 히스토리 슬라이스 → 토큰 기반 윈도우
```python
# Before
messages = history[-6:]

# After
messages = []
token_count = 0
for msg in reversed(history):
    token_count += estimate_tokens(msg)
    if token_count > MAX_CONTEXT_TOKENS:
        break
    messages.insert(0, msg)
```

#### 2. (단기) 구조화된 요약 도입
- 오래된 메시지를 LLM이 아닌 **규칙 기반**으로 요약
- Scope, 사용된 스킬, 최근 요청, 미완료 작업, 참조 문서 추출
- 요약을 시스템 프롬프트에 주입

#### 3. (단기) Continuation Instruction
- 압축 후 "이어서 해라, 요약 인정하지 마라" 지시 추가
- 현재 온통에는 이런 지시 없음

#### 4. (중기) 세션 영속성 개선
- 인메모리 → SQLite 또는 JSONL
- 서버 재시작 후에도 대화 이어가기 가능
