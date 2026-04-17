# Step 0: 프론트엔드 환경 세팅 — 작업 요약

> 완료일: 2026-03-25

---

## 환경 이슈 해결

1. **Node.js 버전 문제 발견**: 기존 `v18.12.1` → Next.js 15+, shadcn 모두 Node 20+ 필요
2. **nvm 설치**: `curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash`
3. **Node 20 설치**: `nvm install 20` → `v20.20.2` 적용
4. brew로 Node 20 설치 시도했으나 macOS 12 호환 문제로 실패 → nvm 우회

> **주의**: 이후 모든 npm/npx 명령 실행 전 `export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use 20` 필요

---

## 0-1. Next.js 프로젝트 초기화

- `npx create-next-app@15` 사용 (최초 v16 시도 → Node 20 필수로 v15로 변경)
- 옵션: `--typescript --tailwind --eslint --app --src-dir --import-alias "@/*" --use-npm`
- Tailwind v4 설치됨 (CSS-only config, `tailwind.config.ts` 없음 — 정상)
- 기본 보일러플레이트 정리:
  - `page.tsx` → 심플한 onTong placeholder
  - `layout.tsx` → title "onTong", lang="ko"
  - 기본 SVG 에셋 삭제 (next.svg, vercel.svg, file.svg, window.svg, globe.svg, favicon.ico)
  - 중첩 `.git` 디렉토리 삭제

## 0-2. shadcn/ui 설치

- `npx shadcn@latest init -d` → components.json + button.tsx + utils.ts 생성
- `npx shadcn@latest add command badge select dropdown-menu popover dialog sonner -y`
- 생성된 컴포넌트: button, badge, command, select, dropdown-menu, popover, dialog, sonner, input, textarea, input-group

## 0-3. Zustand + dnd-kit 설치

- `npm install zustand @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities`
- zustand@5.0.12, @dnd-kit/core@6.3.1

## 0-4. API 프록시 설정

- `next.config.ts`에 rewrites 추가:
  - `/api/:path*` → `http://localhost:8001/api/:path*`

## 0-5. TypeScript 타입 정의

- `src/types/wiki.ts`: WikiFile, WikiTreeNode, SearchIndexEntry, BacklinkMap, TagIndex
- `src/types/agent.ts`: ChatRequest, RouterDecision, SSE 이벤트 (ContentDelta, SourcesEvent, ApprovalRequestEvent, ErrorEvent, DoneEvent), ApprovalRequest, ErrorResponse
- `src/types/workspace.ts`: FileType, Tab, DocumentMetadata
- `src/types/index.ts`: barrel export

---

## 검증 결과

| 항목 | 결과 |
|------|------|
| package.json deps | ✅ next, react, react-dom, typescript, @types/react |
| shadcn/ui 컴포넌트 8개 | ✅ 전부 존재 |
| zustand + @dnd-kit/core | ✅ 버전 출력 확인 |
| API 프록시 config | ✅ rewrite 규칙 확인 |
| tsc --noEmit | ✅ 에러 0건 |
| npm run build | ✅ 성공 |
| dev 서버 + curl 프록시 | ⏳ 백엔드 기동 후 테스트 |

---

## 생성/수정된 파일

```
frontend/                          # 신규 생성
├── package.json
├── next.config.ts                 # rewrites 추가
├── src/
│   ├── app/
│   │   ├── page.tsx               # 보일러플레이트 정리
│   │   ├── layout.tsx             # title, lang 수정
│   │   └── globals.css            # shadcn init으로 재작성
│   ├── components/ui/             # shadcn 컴포넌트 11개
│   ├── lib/utils.ts               # shadcn cn() 유틸
│   └── types/
│       ├── index.ts
│       ├── wiki.ts
│       ├── agent.ts
│       └── workspace.ts
└── components.json                # shadcn 설정
```
