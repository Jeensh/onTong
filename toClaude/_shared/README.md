# toClaude/_shared/

세 섹션(위키 / 모델링 / 시뮬레이션) 모두가 참조하는 공용 문서.

## 권한
- **수정**: 사용자의 명시적 승인 없이는 어떤 Claude 세션도 수정 금지
- **읽기**: 모든 세션 자유롭게 참조

## 파일
- `agent_bible_analysis/` — Claude Code 내부 구조 분석 (참조용)
- `agent_tools_schema.md` — 에이전트 툴 스키마 레퍼런스
- `plan/` — 프로젝트 전체 마스터 플랜 / 컨셉
- `reports/` — 아키텍처, 브리핑, 페이즈 리포트 (프로젝트 전역)
- `verify.sh` — 전체 프로젝트 검증 스크립트 (pytest + tsc + API)

## 변경이 필요할 때
1. 사용자에게 먼저 변경 필요성 보고
2. 명시적 승인 후 진행
3. 변경 후 영향받는 섹션의 `CHANGES.md`에 기록

## 상위 룰
`CLAUDE.md`의 **🔒 Section Isolation Rule** 참고.
