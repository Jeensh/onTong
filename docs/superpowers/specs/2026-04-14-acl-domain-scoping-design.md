# ACL 기반 도메인 스코핑 설계 스펙

> 날짜: 2026-04-14
> 상태: 승인됨

---

## 1. 목표

현재 onTong 위키는 모든 문서가 단일 풀에서 검색·충돌감지·추천됩니다. 이를 엔터프라이즈 ECM 수준의 접근 제어 기반 시스템으로 전환하여:

1. **개인 공간** — 비공개 작업 영역 제공
2. **세밀한 ACL** — 문서·폴더·스킬 단위 접근 제어 (개인, 그룹, 역할)
3. **성능 향상** — 접근 가능 범위만 검색·충돌감지하여 노이즈 감소 및 속도 향상
4. **사이드바 구조화** — 특수 폴더(스킬, 페르소나)를 섹션으로 분리한 통합 탐색기 UX

B~E(도메인별 AI 튜닝, 커스텀 메타데이터 스키마, 워크플로우, 대시보드)는 이번 범위가 아닙니다.

---

## 2. 사용자·그룹·인증 모델

### 2.1 User 모델 (확장)

```python
class User:
    id: str              # 고유 식별자
    name: str            # 표시 이름
    email: str
    roles: list[str]     # 시스템 역할: ["admin"], ["viewer"] 등
    groups: list[str]    # 소속 그룹: ["인프라팀", "프로젝트X팀"]
```

기존 `roles`에 `groups` 필드를 추가합니다. `roles`는 시스템 권한(admin, viewer 등), `groups`는 조직·프로젝트 단위입니다.

### 2.2 Group 모델 (신규)

```python
class Group:
    id: str              # "infra-team", "project-x" 등
    name: str            # "인프라팀"
    type: "department" | "custom"
    members: list[str]   # user ID 목록
    created_by: str
    managed_by: list[str]  # 그룹 관리 권한자 (admin + 지정자)
```

- **department**: 관리자만 생성·삭제. 조직도 반영.
- **custom**: 인증된 사용자 누구나 생성 가능. 프로젝트 단위 협업용. 생성자가 자동으로 managed_by에 포함.
- 그룹 멤버십 변경은 이벤트로 전파됩니다.

### 2.3 저장소

`data/groups.json`에 파일 기반 저장 (현재 `data/.acl.json`과 동일 패턴). `GroupStore` 인터페이스로 추상화하여 추후 DB 교체 가능.

### 2.4 AuthProvider 확장

```python
class AuthProvider(ABC):
    async def authenticate(request) -> User        # 기존
    async def resolve_groups(user_id) -> list[str]  # 신규: 그룹 조회
    async def on_startup() / on_shutdown()          # 기존
```

`NoOpProvider`에서는 설정 파일 기반으로 유저·그룹 매핑. 추후 OIDC/LDAP 프로바이더로 교체하면 `resolve_groups`가 외부 시스템에서 가져옵니다.

---

## 3. ACL 모델 (문서·폴더·스킬 통합)

### 3.1 ACLEntry 구조

```python
class ACLEntry:
    path: str            # "인프라/", "인프라/서버-가이드.md", "_skills/shared/검색.md"
    owner: str           # 생성자 user ID
    read: list[str]      # ["인프라팀", "@kim", "all"]
    write: list[str]     # ["인프라팀", "@donghae"]
    manage: list[str]    # ["@donghae", "admin"] — ACL 자체를 수정할 수 있는 권한
    inherited: bool      # True면 부모 폴더에서 상속받은 것
```

### 3.2 권한 해석 규칙

```
1. @username/ 하위     → 무조건 본인만. ACL 불필요 (하드코딩)
2. 문서에 자체 ACL 있음 → 그것을 사용 (inherited=False)
3. 문서에 자체 ACL 없음 → 부모 폴더 ACL 상속, 재귀적으로 올라감
4. 루트까지 ACL 없음    → 접근 불가 (기본값 = 비공개)
5. admin 역할          → 항상 모든 접근 가능
6. owner               → 자기 소유 리소스에 항상 read + write + manage
```

### 3.3 manage 권한

- **최상위 공유 폴더** (`인프라/`, `ERP/` 등): `manage: ["admin"]` — 관리자만 ACL 변경
- **하위 폴더**: 생성자가 owner + manage. 상위 manage 권한자도 가능
- **문서**: 작성자가 owner + manage

### 3.4 현재 ACLStore와의 차이

| 항목 | 현재 | 변경 |
|------|------|------|
| 대상 | 경로 패턴만 | 문서·폴더·스킬 통합 |
| 권한 종류 | read, write | read, write, **manage** |
| 기본값 | ACL 없으면 허용 | ACL 없으면 **거부** (비공개 기본) |
| 상속 | 부모→자식 워크업 | 동일하되 **문서별 오버라이드** 명시 |
| owner 개념 | 없음 | **소유자 = 항상 접근 + manage** |
| 개인 공간 | 없음 | `@username/` 하드코딩 비공개 |

### 3.5 스킬 적용

스킬 파일도 경로가 있으므로 (`_skills/shared/검색.md`, `_skills/@donghae/내전용.md`) 동일한 ACL 해석 규칙이 적용됩니다.

---

## 4. Materialized Access Scope (검색 성능)

### 4.1 핵심 개념

문서 저장 시점에 "이 문서에 접근 가능한 주체 목록"을 미리 계산해서 ChromaDB 청크 메타데이터에 저장합니다. 검색 시 사용자의 소속 정보로 `where` 필터만 걸면 됩니다.

### 4.2 ChromaDB 메타데이터 확장

```
기존: domain, process, tags, path_depth_1, path_depth_2, status ...
추가: access_read, access_write
형식: "|인프라팀|@kim|admin|@donghae|"  (pipe-delimited, 기존 tags와 동일 패턴)
```

### 4.3 사용자의 scope 계산

```python
def get_user_scope(user: User) -> list[str]:
    return [
        f"@{user.id}",       # 개인
        *user.groups,         # 소속 그룹 ["인프라팀", "프로젝트X팀"]
        *user.roles,          # 시스템 역할 ["admin"]
        "all",                # 전체 공개 문서 매칭용
    ]
```

### 4.4 검색 시 적용

```python
# 벡터 검색 — pipe-delimited 문자열에 $contains 사용
# access_read: "|인프라팀|@donghae|admin|" 형태로 저장
# user_scope 각 항목을 $or로 결합
where = { "$or": [
    { "access_read": { "$contains": f"|{scope_item}|" } }
    for scope_item in user_scope
] }
results = collection.query(embedding, where=where, n=10)

# BM25 검색도 동일 스코프 필터 적용
# 충돌감지, 관련 문서 추천도 동일 where 필터
```

### 4.5 그룹 변동 시 동작

**멤버 추가/제거 (대다수 케이스):**
- ChromaDB 메타데이터 갱신 불필요
- access_scope에는 그룹명이 저장되어 있고, `get_user_scope()`가 실시간으로 현재 소속을 반영하므로 즉시 적용

**그룹 이름 변경:**
- 시스템이 자동으로 ACL 엔트리 + ChromaDB access_scope 메타데이터를 일괄 치환
- 관리자는 그룹 관리 UI에서 이름 변경 버튼만 누르면 됨
- 진행 상황 표시 후 완료 알림

**그룹 삭제:**
- "이 그룹을 참조하는 ACL이 N건 있습니다" 경고 후 확인
- 확인 시 해당 그룹을 참조하는 ACL 엔트리와 access_scope에서 일괄 제거

### 4.6 성능 기대치 (100K 문서 기준)

| 시나리오 | 현재 (전체 검색) | 변경 후 (스코프 검색) |
|---------|----------------|-------------------|
| 검색 대상 | 100K 청크 | 접근 가능 범위만 (예: 5K~20K) |
| 충돌감지 full_scan | O(n^2) 전체 | O(m^2) 접근 범위 내 |
| ChromaDB 필터링 | 없음 | where 절로 HNSW 검색 전 필터 |

---

## 5. 사이드바 UI 구조

### 5.1 섹션 레이아웃

하나의 사이드바 패널 안에 접을 수 있는 섹션 헤더로 구분. 각 섹션 내부는 동일한 트리 탐색기 UX.

```
┌─ 사이드바 ──────────────────┐
│ ▾ 내 문서                    │  ← @username/ (항상 최상단)
│   📄 작업 메모.md            │
│   📁 초안/                   │
│                              │
│ ▾ 위키                       │  ← 공유 폴더 (접근 가능한 것만)
│   📁 인프라/                 │
│   📁 ERP/                    │
│   📁 기획/                   │
│                              │
│ ▸ 스킬                       │  ← _skills/ (접혀 있음)
│ ▸ 내 설정                    │  ← _personas/@username/
└──────────────────────────────┘
```

### 5.2 동작 규칙

| 항목 | 동작 |
|------|------|
| 섹션 접기/펼치기 | 헤더 클릭으로 토글, 상태 localStorage 유지 |
| 트리 동작 | 모든 섹션에서 동일 — 펼치기, 우클릭 메뉴, 드래그앤드롭, 인라인 이름 변경 |
| 위키 섹션 필터링 | 내가 read 이상 접근 가능한 폴더만 표시 |
| 내 문서 섹션 | @username/ 고정. 다른 사람의 개인 공간은 표시 안 됨 |
| 스킬 섹션 | 내가 접근 가능한 공유 스킬 + 내 개인 스킬. 별도 아이콘 |
| 내 설정 섹션 | 페르소나 파일 등. 보통 접혀 있음 |
| 크기 | 스킬/설정은 기본 접힌 상태로 위키 영역이 좁아지지 않음 |

### 5.3 공유 상태 아이콘

| 아이콘 | 의미 |
|--------|------|
| 🔒 | 내가 read-only (쓰기 불가) |
| 👥 | 내가 owner이고 다른 사람에게 공유 중 |
| (없음) | 상속된 기본 권한 |

---

## 6. 컨텍스트 메뉴 + 속성 패널

### 6.1 문서 우클릭 메뉴

| 항목 | 필요 권한 |
|------|----------|
| 열기 / 새 탭에서 열기 | 항상 |
| 이름 변경 / 이동 / 삭제 | write |
| 공유 설정... | manage |
| 링크 복사 | 항상 |
| 속성 | 항상 |

### 6.2 폴더 우클릭 메뉴

| 항목 | 필요 권한 |
|------|----------|
| 새 문서 / 새 폴더 | write |
| 이름 변경 / 이동 / 삭제 | owner 또는 manage |
| 공유 설정... | manage |
| 속성 | 항상 |

### 6.3 권한 없는 항목

권한 없는 메뉴 항목은 숨김 처리 (회색 비활성화가 아니라 아예 안 보임).

### 6.4 컨텍스트 메뉴 위치 보정

- 메뉴 렌더링 후 `getBoundingClientRect()`로 크기 측정
- `window.innerHeight/innerWidth` 및 사이드바 패널 경계와 비교
- 하단 공간 부족 시 위쪽으로 플립, 우측 부족 시 좌측으로 플립
- 상하좌우 모두 부족한 극단 케이스 → 뷰포트 안에 고정 + `max-height`로 스크롤
- 공통 `<ContextMenu>` 컴포넌트로 모든 섹션에서 재사용

### 6.5 공유 설정 다이얼로그

manage 권한이 있는 사용자가 컨텍스트 메뉴 또는 속성 패널에서 진입합니다.

- 현재 권한 목록 (사용자·그룹별 읽기/쓰기 표시, 제거 버튼)
- 사용자 또는 그룹 추가 (자동완성 검색)
- "폴더 권한 상속 해제" 체크박스 (inherited 플래그 전환)

### 6.6 속성 패널

누구나 접근 가능. 소유자, 생성일, 수정일, 최종 수정자, 상태, 내 권한, 권한 출처(어느 폴더에서 상속)를 표시합니다. manage 권한이 있으면 "공유 설정" 버튼도 표시됩니다.

---

## 7. 데이터 흐름 시나리오

### 7.1 문서 저장

```
save_file(path, content, user)
  → 기존 로직 (frontmatter, metadata, 파일 쓰기)
  → scope.compute_access_scope(path)  [신규]
  → wiki_indexer.index_file(path, content, metadata, access_scope)
  → event_bus.emit("wiki:file-saved", path)
```

### 7.2 검색 (RAG)

```
rag_agent.search(query, user)
  → get_user_scope(user)  → ["@donghae", "인프라팀", "admin", "all"]
  → ChromaDB where: access_read containsAny user_scope
  → BM25도 동일 스코프 필터
  → RRF 합산 → 리랭크
```

### 7.3 공유 설정 변경

```
PUT /api/acl/{path}
  → 권한 확인 (manage)
  → acl_store.set_acl(path, entry)  → inherited: false
  → scope.recompute_access_scope(path)
  → wiki_indexer.update_metadata(path, access_scope)  [재임베딩 불필요]
  → event_bus.emit("acl:changed", path)
```

### 7.4 그룹 멤버십 변경

```
PUT /api/groups/{id}/members
  → group_store.update_members()
  → ChromaDB 갱신 불필요 (access_scope는 그룹명 기반)
  → 즉시 반영: 사용자의 get_user_scope()가 실시간 소속 반영
```

### 7.5 그룹 이름 변경/삭제

```
PUT /api/groups/{id}  (이름 변경)
  → group_store.rename()
  → acl_store.rename_group_references()  [일괄 치환]
  → scope.batch_update_access_scope(old_name, new_name)  [ChromaDB 배치]
  → 관리자에게 진행 상황 표시 → 완료 알림

DELETE /api/groups/{id}  (삭제)
  → 경고: "N건의 ACL이 영향받습니다"
  → 확인 후 일괄 제거
```

---

## 8. 모듈 구조

### 8.1 신규 모듈

| 경로 | 역할 |
|------|------|
| `backend/core/auth/group_store.py` | GroupStore 인터페이스 + JSON 파일 구현 |
| `backend/core/auth/scope.py` | access_scope 계산 + 갱신 로직 |
| `backend/api/group.py` | 그룹 CRUD API |
| `frontend/src/components/ContextMenu.tsx` | 공통 컨텍스트 메뉴 (위치 보정, 권한 필터링) |
| `frontend/src/components/ShareDialog.tsx` | 공유 설정 다이얼로그 |
| `frontend/src/components/PropertiesPanel.tsx` | 속성 패널 |
| `frontend/src/lib/api/acl.ts` | ACL API 클라이언트 |
| `frontend/src/lib/api/groups.ts` | 그룹 API 클라이언트 |

### 8.2 기존 모듈 수정

| 모듈 | 변경 내용 |
|------|----------|
| `core/auth/models.py` | User에 groups 필드 추가 |
| `core/auth/acl_store.py` | ACLEntry 확장 (owner, manage, inherited), 기본값 거부 |
| `core/auth/permission.py` | 상속 체인 해석, 개인공간 하드코딩, manage 권한 체크 |
| `core/auth/base.py` | AuthProvider에 resolve_groups 추가 |
| `core/auth/noop_provider.py` | 설정 파일 기반 유저·그룹 매핑 |
| `core/auth/deps.py` | get_current_user에서 groups 포함 |
| `api/acl.py` | 문서별 ACL CRUD 확장, manage 권한 체크 |
| `api/auth.py` | /me에 groups 포함 |
| `wiki_indexer.py` | 청크 메타데이터에 access_read, access_write 주입 |
| `wiki_service.py` | 저장 시 scope.compute_access_scope 호출 |
| `rag_agent.py` | 검색 where절에 user_scope 필터 추가 |
| `wiki_search.py` | 동일 where절 필터 |
| `conflict_service.py` | check_file, full_scan에 user_scope 전달 |
| `metadata_index.py` | access_scope 역참조 인덱스 추가 |
| `event_bus.py` | group_membership_changed, acl_changed 이벤트 추가 |
| `main.py` | GroupStore 초기화, scope 갱신 핸들러 등록 |
| `TreeNav.tsx` | 섹션 분리, ACL 기반 필터링, 권한 아이콘 |

### 8.3 변경하지 않는 것

- ChromaDB 인프라: 단일 컬렉션 유지, 메타데이터 스키마만 확장
- 기존 메타데이터 (domain, process, tags 등): 그대로 유지
- 에디터, AI 코파일럿: 검색 결과가 스코프되면 자동 반영
- 인증 프로바이더 실구현 (OIDC 등): NoOp 확장으로 설정 파일 기반

---

## 9. 범위 외 (명시적 제외)

- 도메인별 AI 프롬프트 튜닝
- 도메인별 커스텀 메타데이터 스키마
- 도메인별 워크플로우 (승인 단계 등)
- 도메인별 대시보드/통계
- 실제 OIDC/LDAP/SAML 프로바이더 구현
- 감사 로그 (audit log)
- 시간 기반 접근 만료
