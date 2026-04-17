# toClaude/wiki/

위키 섹션(Section 1) Claude 세션 전용 작업 공간.

## 소유 세션
위키 담당 Claude 세션.

## 권한
- **쓰기**: 위키 세션만
- **읽기**: 모든 세션 가능 (참조 허용)
- **수정 금지**: 모델링/시뮬레이션 세션은 이 폴더를 절대 수정하지 않는다.

## 권장 파일 구조
```
TODO.md           # 위키 섹션 할 일 목록
CHANGES.md        # 위키 섹션 변경 로그
HANDOFF.md        # 다음 세션 인계 문서
demo_guide.md     # 위키 기능 데모 시나리오
CHECKLIST.md      # 위키 검증 체크리스트
log/              # 스텝 로그
archive/          # 완료된 스텝 요약
```

## 상위 룰
`CLAUDE.md`의 **🔒 Section Isolation Rule** 참고.
