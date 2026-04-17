# Phase 4-D/E/F/G Summary

## Phase 4-D: 편집 잠금 (Edit Locking) — 4 tasks ✅
- **P4D-1**: `LockService` 인메모리 잠금 관리 (TTL=300s 자동 해제)
- **P4D-2**: Lock REST API (`POST /lock`, `DELETE /unlock`, `GET /status`, `POST /refresh`)
- **P4D-3**: MarkdownEditor 잠금 UI (다른 사용자 편집 시 읽기전용 + amber 배너)
- **P4D-4**: 탭 닫기/세션 종료 시 잠금 해제, 2분 주기 자동 갱신

**산출물**: `lock_service.py`, `api/lock.py`, `wiki.ts` Lock API, `MarkdownEditor.tsx` lock UI

## Phase 4-E: 권한 관리 RBAC — 7 tasks ✅
- **P4E-1**: Role/Permission 모델 (admin/editor/viewer), ACL 구조
- **P4E-2**: `ACLStore` — JSON 파일 기반 폴더/문서별 ACL 관리 (`wiki/.acl.json`)
- **P4E-3**: `require_read`/`require_write` FastAPI 의존성 미들웨어
- **P4E-4**: Wiki API에 권한 체크 적용 (읽기/쓰기 분리)
- **P4E-5**: RAG 검색 결과 ACL 필터링 (사용자 역할 기반)
- **P4E-6**: 프론트엔드 권한 반영 (읽기전용 표시, 접근 불가 폴더 숨김)
- **P4E-7**: `PermissionEditor.tsx` 관리자용 ACL 설정 패널

**산출물**: `acl_store.py`, `permission.py`, `acl.py`, `rag_agent.py` ACL filter, `PermissionEditor.tsx`

## Phase 4-F: 보안 강화 — 5 tasks ✅
- **P4F-1**: `.env.example`/`.env.production.example` 시크릿 분리, `.gitignore` 강화
- **P4F-2**: CORS 강화 — 와일드카드 제거, 명시적 메서드/헤더 화이트리스트
- **P4F-3**: 구조화 로깅 — JSON 포맷 + request_id ContextVar 추적
- **P4F-4**: 입력 검증 — path traversal 차단 (`_validate_path`), 요청 크기 제한 (10MB)
- **P4F-5**: 전역 예외 핸들러 — Exception→500, ValueError→400, 일관된 에러 응답

**산출물**: `logging_config.py`, `main.py` 미들웨어/핸들러, `wiki.py` 검증 로직

## Phase 4-G: 대규모 대응 — 4 tasks ✅
- **P4G-1**: 검색 인덱스 offset/limit 페이지네이션
- **P4G-2**: 트리 지연 로딩 — depth 파라미터 + subtree API (`GET /tree/{path}`)
- **P4G-3**: ChromaDB 배치 upsert (batch_size=100)
- **P4G-4**: ETag/304 캐싱 (tree API MD5 해시)

**산출물**: `search.py` pagination, `wiki.py` depth/subtree/ETag, `chroma.py` batch upsert

## 총 Phase 4 결과
- **34 tasks 전체 완료** (Phase 4-A~G)
- **누적 211+ tasks** (Phase 1~3: 177 + Phase 4: 34)
