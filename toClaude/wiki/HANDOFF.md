# 위키 세션 인계 문서 (HANDOFF)

> 다른 환경에서 이어서 작업할 때 가장 먼저 읽어야 하는 파일.
> 순서: 이 문서 → `CHANGES.md`의 `[ ]` → `TODO.md`.

마지막 업데이트: 2026-04-25 (채팅 충돌 배너 / wiki_write 승인 흐름 잔버그 정리)

---

## 1. 다음 세션 첫 작업

### 즉시 처리 (브라우저 검증 + 커밋)
이번 세션에서 코드까지 끝낸 잔버그 정리 4건 중 3건은 커밋, 1건은 **WIP 상태로 미커밋**.

1. **(WIP·미커밋) 충돌 배너 본문 마크다운 렌더링** — `frontend/src/components/AICopilot.tsx:~1265`
   - `msg.conflictWarning.details`를 `<p>`에 raw 텍스트로 꽂아 `**bold**`/`- bullet`/`\n\n`이 그대로 보였음. `ReactMarkdown remarkPlugins={[remarkGfm]}`로 교체하고 앰버 톤 prose 클래스(prose-p:my-1, prose-strong:text-slate-900, prose-code:bg-amber-100/60 등) 부착.
   - `cd frontend && npx tsc --noEmit` 통과.
   - **다음 세션 첫 작업**:
     1. 백엔드 PID 확인 (`lsof -i:8001`) — 이번 세션 종료 시점 PID 8887 (uvicorn `--reload` 미사용)
     2. 브라우저에서 `품질 기준에서 균열 구간 온도 편차 가능 범위가 얼마야?` → `표준` 클러리피케이션으로 충돌 배너 띄우고 **`**` 마커 사라지고 줄바꿈/볼드/리스트가 정상 렌더되는지** 확인
     3. 통과 시 `frontend/src/components/AICopilot.tsx`만 stash → 마크다운 hunk만 적용 → 단일 커밋(`fix(ui): render conflict_warning details as markdown`) → `git stash pop`. 다른 WIP(`appliedFilters` Phase 4 잔여 wiring 등)는 건드리지 말 것.

2. **(완료·커밋 b5cd714)** 충돌 페어 과다 표시 → 스킬 출력의 `conflicting_docs`를 `unique_sources`보다 우선 사용. 검증 끝 (실 SSE에서 1 pair = 균열관리 vs 대안적접근법).

3. **(완료·커밋 cf4ed53)** AI write 미리보기 탭 404 → `MarkdownEditor`의 load `useEffect`에서 `agentWrite.filePath === filePath`일 때 fetch 스킵 + `agentWrite` deps 추가.

4. **(완료·커밋 6eba772)** wiki_write 응답 메시지 과거형 정정 → "생성했습니다" 류 거짓 저장 주장 제거, `ontong.md` 응답 규칙에 §7 거짓 저장 주장 금지 추가.

### 잔여 후순위 (Phase 4 이후)
- 페어 summary 동일 문장 반복 — `_extract_pair_summary` 폴백이 `details` 첫 문장을 재사용. 페어별 핵심 차이를 추출하도록 LLM 또는 패턴 강화 필요.
- 브라우저에서 `demo_guide.md` D-P4-01~08 시나리오 수동 재확인 (UI 렌더링/프리셋 영속성/Escape 체감).
- 팀 공유 프리셋(서버 저장)은 별도 스펙으로 분리 가능.

### 메타데이터 검색 설계 — 전체 Phase 완료
- Phase 1(MS-1~MS-7) + Phase 2(MS-8~MS-10) + Phase 3(MS-11~MS-15) + Phase 4(MS-16~MS-20) 모두 완료.
  - 누적 백엔드 테스트: **105 PASS** (filter_compiler 35 + filter_dsl 24 + wiki_search_filters 6 + nl_filter_extractor 20 + Phase 2 신규 12 + Phase 3 신규 8)
  - 프론트 TS 0 에러
  - SSE 수동 QA 5건 모두 PASS (`toClaude/wiki/log/step_metadata_search_phase4_summary.md` §검증)
  - 데모 시나리오 8개 + 트러블슈팅 5개 → `demo_guide.md`
- 각 Phase 요약:
  - Phase 1: `log/step_metadata_search_phase1_summary.md`
  - Phase 2: `log/step_metadata_search_phase2_summary.md`
  - Phase 3: `log/step_metadata_search_phase3_summary.md`
  - Phase 4: `log/step_metadata_search_phase4_summary.md`

### 남은 플래그 (낮은 우선순위)
- `authors=@이서연` smoke test에서 0 결과 — 실제 데이터에 해당 handle을 가진 문서가 적어서인지 `$contains` 의미 차이인지 운영 데이터로 재검증.
- 프론트 DSL은 quoted value(`tag:"인사 평가"`) 미지원 — FilterSheet에서만 입력 가능.
- Pydantic AI ReAct tool-call 경로의 `filters` 활용은 **통합 테스트(`tests/test_react_agent_filters.py`)로 계약 확인 완료 (2026-04-18, 3건 PASS)**. 실제 live 사용은 SimulatorAgent/TracerAgent 등 신규 에이전트 도입 시.

### (선택) 실 운영 재인덱싱 — 이번 세션에서 완료
```bash
source venv/bin/activate
python -m backend.cli.reindex_metadata --force             # 이번 세션 22 파일 / 140 청크 / 13.8s
```
`_rebuild_metadata_index`의 `abs_path` 누락 버그 수정 완료 (mtime fallback 동작).

---

## 2. 현재 섹션 상태

### 2026-04-17 기준
- **워크스페이스 세팅 완료**: `toClaude/wiki/`에 README/TODO/CHANGES/HANDOFF/specs/log/archive/ 생성
- **위키 과거 작업**: 2026-04-01 ~ 2026-04-17 사이 진행한 ACL, Image Search, Image Management, onTalk rebrand, Tiptap 개선, @동해 persona 등은 `toClaude/modeling/CHANGES.md` 및 `toClaude/modeling/HANDOFF.md`에 기록되어 있음 (섹션 재구성 이전 기록, 이관 불필요 — 역사적 기록으로 유지)

---

## 3. 중요 규칙 요약

### 섹션 격리 (`CLAUDE.md` 🔒)
- **쓰기**: `toClaude/wiki/` + `wiki/`(제품 콘텐츠)
- **읽기만**: `toClaude/modeling/`, `toClaude/_shared/`
- **승인 필요**: `toClaude/_shared/` 수정

### 스텝 완료 7단계 (`CLAUDE.md` 📋)
1. 코드 구현
2. 검증 (CHECKLIST 테스트)
3. `log/step{N}_summary.md` 작성 → `archive/` 이동
4. `demo_guide.md` 시나리오 추가
5. `TODO.md` `[x]` 체크
6. 메모리 `project_status.md` 갱신
7. 사용자 보고 & 중단

### 언어
- 사용자 소통: 한국어
- 내부/코드/ReAct: 영어

### 100K+ 문서 규모 가정 (메모리 `feedback_scale_100k.md`)
모든 설계는 100,000건+ 문서 기준으로 품질·성능 검증.

---

## 4. 환경 / 설정

- 백엔드: `backend/` (FastAPI, Chroma, BM25, Tesseract OCR)
- 프론트엔드: `frontend/` (Next.js 15, React 19, Tiptap, shadcn/ui)
- 위키 콘텐츠: `wiki/` (마크다운 + frontmatter)
- 테스트: `tests/` (pytest)
- 검증 스크립트: `toClaude/_shared/verify.sh`

---

## 5. 최근 커밋 (참고)

```
b5cd714 fix(agent): use skill's conflicting_docs instead of all retrieved sources
cf4ed53 fix(ui): skip fetch for AI write preview so tab doesn't 404
6eba772 fix(agent): clarify write message is approval-pending, not saved
0274f53 fix(agent): wire wiki_write skill for chat-initiated document creation
3c42375 style(ui): redesign conflict_warning banner for readability
80e1043 docs(readme): restructure README as navigation hub with split detail docs
33cf708 docs(handoff): prune completed phases from modeling HANDOFF
f519a9d Merge branch 'main' of https://github.com/Jeensh/onTong
```

`main` HEAD `b5cd714` — origin에 5 commits ahead (`b5cd714` 포함, 푸시는 다음 세션에서 결정).

## 6. 미커밋 WIP (이 세션 종료 시점)

### 위키 세션이 만진 파일
- `frontend/src/components/AICopilot.tsx` — 충돌 배너 markdown 렌더 (위 §1 #1 참고). **다른 hunk(`appliedFilters` import/wiring)는 이전 세션의 WIP**가 섞여 있으니 markdown hunk만 골라 커밋할 것. `git diff frontend/src/components/AICopilot.tsx | grep -B3 -A4 "ReactMarkdown\|conflictWarning.details"`로 대상 hunk 확인.
- `toClaude/wiki/HANDOFF.md`, `toClaude/wiki/CHANGES.md` — 이 인계 문서. 다음 세션 첫 작업 후 함께 커밋해도 OK.

### 모델링 세션 WIP (건드리지 말 것)
`backend/modeling/**` 다수 파일이 수정/삭제 상태. 이는 **모델링 Claude 세션의 진행 중 작업**이며 위키 세션 격리 규칙상 read-only. `git stash` 사용 시 path 명시로 위키 파일만 분리할 것 (`git stash push -- frontend/src/components/AICopilot.tsx`).

## 7. 백엔드 상태

- 이번 세션 종료 시점 uvicorn PID 8887 (`--reload` 미사용, 포트 8001).
- 코드 수정 → 재시작 필수: `kill <pid> && .venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8001 --log-level warning > /tmp/backend.log 2>&1 &`
