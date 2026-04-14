# ACL 기반 도메인 스코핑 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 엔터프라이즈 ECM 수준의 ACL 시스템을 도입하여 개인 공간, 세밀한 문서/폴더/스킬 접근 제어, ACL 기반 검색 스코핑을 구현한다.

**Architecture:** 기존 단일 ChromaDB 컬렉션 유지. 문서 저장 시 access_scope를 사전 계산하여 ChromaDB 청크 메타데이터에 주입. 검색/충돌감지 시 사용자의 scope와 매칭하는 `$or`+`$contains` where 절로 필터링. 그룹 멤버십 변동은 ChromaDB 갱신 불필요 (scope에 그룹명 저장, 사용자 scope가 실시간 반영).

**Tech Stack:** Python/FastAPI, Pydantic, ChromaDB, React/TypeScript, Next.js, shadcn/ui

**Spec:** `docs/superpowers/specs/2026-04-14-acl-domain-scoping-design.md`

---

## File Structure

### Backend — New Files

| Path | Responsibility |
|------|---------------|
| `backend/core/auth/group_store.py` | Group 모델, GroupStore ABC + JSONGroupStore 구현 |
| `backend/core/auth/scope.py` | access_scope 계산, get_user_scope(), 배치 갱신 |
| `backend/api/group.py` | 그룹 CRUD REST API |
| `data/users.json` | 개발용 사용자 목록 (NoOp 프로바이더용) |
| `data/groups.json` | 그룹 데이터 저장소 |
| `tests/test_group_store.py` | GroupStore 단위 테스트 |
| `tests/test_acl_v2.py` | ACL v2 (owner, manage, inherited, default-deny) 테스트 |
| `tests/test_scope.py` | access_scope 계산 테스트 |
| `tests/test_search_scoping.py` | 검색 ACL 스코핑 통합 테스트 |
| `tests/test_group_api.py` | 그룹 API 테스트 |

### Backend — Modified Files

| Path | Changes |
|------|---------|
| `backend/core/auth/models.py` | User에 groups 필드 추가 |
| `backend/core/auth/base.py` | AuthProvider에 resolve_groups() 추가 |
| `backend/core/auth/noop_provider.py` | 다중 사용자 지원, users.json 로드 |
| `backend/core/auth/factory.py` | noop 프로바이더에 users_path 전달 |
| `backend/core/auth/deps.py` | get_current_user에서 groups resolve |
| `backend/core/auth/acl_store.py` | ACLEntry 확장, default-deny, manage 권한, 상속 체인 |
| `backend/core/auth/permission.py` | require_manage 추가, 개인공간 하드코딩 |
| `backend/api/acl.py` | 문서별 ACL CRUD, manage 권한 체크 |
| `backend/api/auth.py` | /me에 groups 포함 |
| `backend/application/wiki/wiki_indexer.py` | _metadata_to_chroma에 access_read, access_write 추가 |
| `backend/application/wiki/wiki_service.py` | save_file에서 scope 계산 호출 |
| `backend/application/agent/skills/wiki_search.py` | where절에 access_read 필터 추가 |
| `backend/application/agent/rag_agent.py` | where절에 access_read 필터 추가 |
| `backend/application/conflict/conflict_service.py` | check_file, full_scan에 user_scope 전달 |
| `backend/application/metadata/metadata_index.py` | access_scope 역참조 인덱스 |
| `backend/infrastructure/events/event_bus.py` | 비동기 콜백 지원 추가 |
| `backend/main.py` | GroupStore 초기화, scope 핸들러 등록 |

### Frontend — New Files

| Path | Responsibility |
|------|---------------|
| `frontend/src/types/auth.ts` | User, Group, ACLEntry, Permission 타입 |
| `frontend/src/lib/api/acl.ts` | ACL API 클라이언트 |
| `frontend/src/lib/api/groups.ts` | 그룹 API 클라이언트 |
| `frontend/src/lib/api/auth.ts` | 인증 API 클라이언트 |
| `frontend/src/hooks/useAuth.ts` | 현재 사용자 + 권한 체크 훅 |
| `frontend/src/components/ContextMenu.tsx` | 공통 컨텍스트 메뉴 (위치 보정) |
| `frontend/src/components/ShareDialog.tsx` | 공유 설정 다이얼로그 |
| `frontend/src/components/PropertiesPanel.tsx` | 속성 패널 |

### Frontend — Modified Files

| Path | Changes |
|------|---------|
| `frontend/src/types/wiki.ts` | WikiTreeNode에 ACL 힌트 추가 |
| `frontend/src/types/index.ts` | auth 타입 re-export |
| `frontend/src/components/TreeNav.tsx` | 섹션 분리, ACL 필터링, 권한 아이콘, 새 ContextMenu 연동 |

---

## Task 1: User 모델 확장 + Group 모델 & GroupStore

**Files:**
- Modify: `backend/core/auth/models.py`
- Create: `backend/core/auth/group_store.py`
- Create: `tests/test_group_store.py`

- [ ] **Step 1: Write failing tests for Group model and GroupStore**

```python
# tests/test_group_store.py
"""GroupStore unit tests."""
import json
import pytest
from pathlib import Path
from backend.core.auth.group_store import Group, GroupStore, JSONGroupStore


@pytest.fixture
def tmp_groups_path(tmp_path: Path) -> Path:
    return tmp_path / "groups.json"


@pytest.fixture
def store(tmp_groups_path: Path) -> JSONGroupStore:
    return JSONGroupStore(tmp_groups_path)


class TestGroupModel:
    def test_create_department(self):
        g = Group(id="infra-team", name="인프라팀", type="department",
                  members=["user-1", "user-2"], created_by="admin",
                  managed_by=["admin"])
        assert g.type == "department"
        assert len(g.members) == 2

    def test_create_custom_group(self):
        g = Group(id="project-x", name="프로젝트X", type="custom",
                  members=["user-1"], created_by="user-1",
                  managed_by=["user-1"])
        assert g.type == "custom"
        assert "user-1" in g.managed_by


class TestJSONGroupStore:
    def test_create_and_get(self, store: JSONGroupStore):
        g = Group(id="infra-team", name="인프라팀", type="department",
                  members=["u1"], created_by="admin", managed_by=["admin"])
        store.create(g)
        result = store.get("infra-team")
        assert result is not None
        assert result.name == "인프라팀"

    def test_get_nonexistent_returns_none(self, store: JSONGroupStore):
        assert store.get("nope") is None

    def test_list_all(self, store: JSONGroupStore):
        store.create(Group(id="a", name="A", type="department",
                           members=[], created_by="admin", managed_by=["admin"]))
        store.create(Group(id="b", name="B", type="custom",
                           members=[], created_by="u1", managed_by=["u1"]))
        assert len(store.list_all()) == 2

    def test_add_member(self, store: JSONGroupStore):
        store.create(Group(id="t", name="T", type="department",
                           members=["u1"], created_by="admin", managed_by=["admin"]))
        store.add_member("t", "u2")
        g = store.get("t")
        assert "u2" in g.members

    def test_add_member_idempotent(self, store: JSONGroupStore):
        store.create(Group(id="t", name="T", type="department",
                           members=["u1"], created_by="admin", managed_by=["admin"]))
        store.add_member("t", "u1")
        assert store.get("t").members.count("u1") == 1

    def test_remove_member(self, store: JSONGroupStore):
        store.create(Group(id="t", name="T", type="department",
                           members=["u1", "u2"], created_by="admin",
                           managed_by=["admin"]))
        store.remove_member("t", "u1")
        g = store.get("t")
        assert "u1" not in g.members
        assert "u2" in g.members

    def test_rename_group(self, store: JSONGroupStore):
        store.create(Group(id="old", name="Old", type="department",
                           members=["u1"], created_by="admin", managed_by=["admin"]))
        store.rename("old", "New Name")
        assert store.get("old").name == "New Name"

    def test_delete_group(self, store: JSONGroupStore):
        store.create(Group(id="del", name="Del", type="custom",
                           members=[], created_by="u1", managed_by=["u1"]))
        store.delete("del")
        assert store.get("del") is None

    def test_get_user_groups(self, store: JSONGroupStore):
        store.create(Group(id="a", name="A", type="department",
                           members=["u1", "u2"], created_by="admin",
                           managed_by=["admin"]))
        store.create(Group(id="b", name="B", type="custom",
                           members=["u1"], created_by="u1", managed_by=["u1"]))
        store.create(Group(id="c", name="C", type="department",
                           members=["u3"], created_by="admin",
                           managed_by=["admin"]))
        groups = store.get_user_groups("u1")
        ids = [g.id for g in groups]
        assert "a" in ids
        assert "b" in ids
        assert "c" not in ids

    def test_persistence(self, tmp_groups_path: Path):
        store1 = JSONGroupStore(tmp_groups_path)
        store1.create(Group(id="p", name="P", type="department",
                            members=["u1"], created_by="admin",
                            managed_by=["admin"]))
        store2 = JSONGroupStore(tmp_groups_path)
        assert store2.get("p") is not None

    def test_get_groups_referencing(self, store: JSONGroupStore):
        """For batch operations: find groups by name."""
        store.create(Group(id="infra", name="인프라팀", type="department",
                           members=["u1"], created_by="admin",
                           managed_by=["admin"]))
        result = store.get_by_name("인프라팀")
        assert result is not None
        assert result.id == "infra"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_group_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.core.auth.group_store'`

- [ ] **Step 3: Extend User model with groups field**

In `backend/core/auth/models.py`, add `groups` field:

```python
class User(BaseModel):
    """Authenticated user."""
    id: str
    name: str
    email: str = ""
    roles: list[str] = []
    groups: list[str] = []  # group names the user belongs to
```

- [ ] **Step 4: Implement Group model and JSONGroupStore**

```python
# backend/core/auth/group_store.py
"""Group management store with JSON file persistence."""
from __future__ import annotations

import json
import logging
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class Group(BaseModel):
    """Organization or project group."""
    id: str
    name: str
    type: Literal["department", "custom"]
    members: list[str] = []
    created_by: str = ""
    managed_by: list[str] = []


class GroupStore(ABC):
    """Abstract group store — swap for DB-backed impl later."""

    @abstractmethod
    def create(self, group: Group) -> None: ...

    @abstractmethod
    def get(self, group_id: str) -> Group | None: ...

    @abstractmethod
    def get_by_name(self, name: str) -> Group | None: ...

    @abstractmethod
    def list_all(self) -> list[Group]: ...

    @abstractmethod
    def add_member(self, group_id: str, user_id: str) -> None: ...

    @abstractmethod
    def remove_member(self, group_id: str, user_id: str) -> None: ...

    @abstractmethod
    def rename(self, group_id: str, new_name: str) -> str: ...

    @abstractmethod
    def delete(self, group_id: str) -> None: ...

    @abstractmethod
    def get_user_groups(self, user_id: str) -> list[Group]: ...


class JSONGroupStore(GroupStore):
    """File-based group store persisted to JSON."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or Path("data/groups.json")
        self._lock = threading.Lock()
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load groups: %s", e)
                self._data = {}
        else:
            self._data = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def create(self, group: Group) -> None:
        with self._lock:
            self._data[group.id] = group.model_dump()
            self._save()

    def get(self, group_id: str) -> Group | None:
        raw = self._data.get(group_id)
        return Group(**raw) if raw else None

    def get_by_name(self, name: str) -> Group | None:
        for raw in self._data.values():
            if raw.get("name") == name:
                return Group(**raw)
        return None

    def list_all(self) -> list[Group]:
        return [Group(**v) for v in self._data.values()]

    def add_member(self, group_id: str, user_id: str) -> None:
        with self._lock:
            raw = self._data.get(group_id)
            if not raw:
                return
            if user_id not in raw["members"]:
                raw["members"].append(user_id)
                self._save()

    def remove_member(self, group_id: str, user_id: str) -> None:
        with self._lock:
            raw = self._data.get(group_id)
            if not raw:
                return
            if user_id in raw["members"]:
                raw["members"].remove(user_id)
                self._save()

    def rename(self, group_id: str, new_name: str) -> str:
        with self._lock:
            raw = self._data.get(group_id)
            if not raw:
                return ""
            old_name = raw["name"]
            raw["name"] = new_name
            self._save()
            return old_name

    def delete(self, group_id: str) -> None:
        with self._lock:
            self._data.pop(group_id, None)
            self._save()

    def get_user_groups(self, user_id: str) -> list[Group]:
        return [
            Group(**raw) for raw in self._data.values()
            if user_id in raw.get("members", [])
        ]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_group_store.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add backend/core/auth/models.py backend/core/auth/group_store.py tests/test_group_store.py
git commit -m "feat: add Group model and JSONGroupStore with user groups field"
```

---

## Task 2: ACL Store v2 (owner, manage, inherited, default-deny)

**Files:**
- Modify: `backend/core/auth/acl_store.py`
- Modify: `backend/core/auth/permission.py`
- Create: `tests/test_acl_v2.py`

- [ ] **Step 1: Write failing tests for ACL v2**

```python
# tests/test_acl_v2.py
"""ACL v2 tests: owner, manage, inherited, default-deny, personal space."""
import json
import pytest
from pathlib import Path
from backend.core.auth.acl_store import ACLEntry, ACLStore
from backend.core.auth.models import User


@pytest.fixture
def acl_path(tmp_path: Path) -> Path:
    return tmp_path / "acl.json"


@pytest.fixture
def store(acl_path: Path) -> ACLStore:
    return ACLStore(acl_path=acl_path)


def make_user(uid: str, roles: list[str] | None = None,
              groups: list[str] | None = None) -> User:
    return User(id=uid, name=uid, roles=roles or [], groups=groups or [])


class TestDefaultDeny:
    """No ACL entry → access denied (except admin/owner)."""

    def test_no_acl_denies_read(self, store: ACLStore):
        user = make_user("u1")
        assert store.check_permission("wiki/secret.md", user, "read") is False

    def test_admin_always_allowed(self, store: ACLStore):
        admin = make_user("adm", roles=["admin"])
        assert store.check_permission("wiki/anything.md", admin, "read") is True
        assert store.check_permission("wiki/anything.md", admin, "write") is True


class TestPersonalSpace:
    """@username/ is always private to that user."""

    def test_owner_can_access(self, store: ACLStore):
        user = make_user("donghae")
        assert store.check_permission("@donghae/notes.md", user, "read") is True
        assert store.check_permission("@donghae/notes.md", user, "write") is True

    def test_other_user_denied(self, store: ACLStore):
        other = make_user("kim")
        assert store.check_permission("@donghae/notes.md", other, "read") is False

    def test_admin_can_access_personal(self, store: ACLStore):
        admin = make_user("adm", roles=["admin"])
        assert store.check_permission("@donghae/notes.md", admin, "read") is True

    def test_nested_personal(self, store: ACLStore):
        user = make_user("donghae")
        assert store.check_permission("@donghae/drafts/idea.md", user, "read") is True


class TestFolderInheritance:
    """Documents inherit parent folder ACL."""

    def test_child_inherits_folder_read(self, store: ACLStore):
        store.set_acl(ACLEntry(
            path="인프라/", owner="admin",
            read=["인프라팀"], write=["인프라팀"], manage=["admin"],
        ))
        user = make_user("u1", groups=["인프라팀"])
        assert store.check_permission("인프라/서버-가이드.md", user, "read") is True

    def test_child_inherits_folder_write(self, store: ACLStore):
        store.set_acl(ACLEntry(
            path="인프라/", owner="admin",
            read=["인프라팀"], write=["인프라팀"], manage=["admin"],
        ))
        user = make_user("u1", groups=["인프라팀"])
        assert store.check_permission("인프라/서버-가이드.md", user, "write") is True

    def test_non_member_denied(self, store: ACLStore):
        store.set_acl(ACLEntry(
            path="인프라/", owner="admin",
            read=["인프라팀"], write=["인프라팀"], manage=["admin"],
        ))
        outsider = make_user("u2", groups=["재무팀"])
        assert store.check_permission("인프라/서버-가이드.md", outsider, "read") is False

    def test_nested_folder_inheritance(self, store: ACLStore):
        store.set_acl(ACLEntry(
            path="인프라/", owner="admin",
            read=["인프라팀"], write=["인프라팀"], manage=["admin"],
        ))
        user = make_user("u1", groups=["인프라팀"])
        assert store.check_permission("인프라/서버/config.md", user, "read") is True


class TestDocumentOverride:
    """Document-level ACL overrides folder ACL."""

    def test_doc_override_narrows_access(self, store: ACLStore):
        store.set_acl(ACLEntry(
            path="인프라/", owner="admin",
            read=["인프라팀"], write=["인프라팀"], manage=["admin"],
        ))
        store.set_acl(ACLEntry(
            path="인프라/비밀.md", owner="donghae",
            read=["@donghae"], write=["@donghae"], manage=["@donghae"],
            inherited=False,
        ))
        team_member = make_user("u1", groups=["인프라팀"])
        assert store.check_permission("인프라/비밀.md", team_member, "read") is False

        owner = make_user("donghae")
        assert store.check_permission("인프라/비밀.md", owner, "read") is True

    def test_doc_override_widens_access(self, store: ACLStore):
        store.set_acl(ACLEntry(
            path="인프라/", owner="admin",
            read=["인프라팀"], write=["인프라팀"], manage=["admin"],
        ))
        store.set_acl(ACLEntry(
            path="인프라/공개.md", owner="donghae",
            read=["all"], write=["인프라팀"], manage=["@donghae"],
            inherited=False,
        ))
        outsider = make_user("u2", groups=["재무팀"])
        assert store.check_permission("인프라/공개.md", outsider, "read") is True


class TestOwnerAccess:
    """Owner always has read + write + manage on their resources."""

    def test_owner_always_has_access(self, store: ACLStore):
        store.set_acl(ACLEntry(
            path="인프라/doc.md", owner="donghae",
            read=["인프라팀"], write=["인프라팀"], manage=["@donghae"],
        ))
        owner = make_user("donghae")
        assert store.check_permission("인프라/doc.md", owner, "read") is True
        assert store.check_permission("인프라/doc.md", owner, "write") is True
        assert store.check_permission("인프라/doc.md", owner, "manage") is True


class TestManagePermission:
    """manage permission controls who can change ACL."""

    def test_manage_granted(self, store: ACLStore):
        store.set_acl(ACLEntry(
            path="인프라/", owner="admin",
            read=["인프라팀"], write=["인프라팀"], manage=["admin", "@lead"],
        ))
        lead = make_user("lead")
        assert store.check_permission("인프라/", lead, "manage") is True

    def test_manage_denied(self, store: ACLStore):
        store.set_acl(ACLEntry(
            path="인프라/", owner="admin",
            read=["인프라팀"], write=["인프라팀"], manage=["admin"],
        ))
        member = make_user("u1", groups=["인프라팀"])
        assert store.check_permission("인프라/", member, "manage") is False


class TestAllKeyword:
    """'all' in read/write grants access to everyone."""

    def test_all_grants_read(self, store: ACLStore):
        store.set_acl(ACLEntry(
            path="공지/", owner="admin",
            read=["all"], write=["admin"], manage=["admin"],
        ))
        anyone = make_user("random")
        assert store.check_permission("공지/안내.md", anyone, "read") is True
        assert store.check_permission("공지/안내.md", anyone, "write") is False


class TestUserDirectGrant:
    """@username in ACL grants access to specific user."""

    def test_user_direct_read(self, store: ACLStore):
        store.set_acl(ACLEntry(
            path="비밀/report.md", owner="donghae",
            read=["@kim"], write=["@donghae"], manage=["@donghae"],
            inherited=False,
        ))
        kim = make_user("kim")
        assert store.check_permission("비밀/report.md", kim, "read") is True
        assert store.check_permission("비밀/report.md", kim, "write") is False


class TestComputeAccessScope:
    """compute_access_scope returns the full list of principals with access."""

    def test_folder_scope(self, store: ACLStore):
        store.set_acl(ACLEntry(
            path="인프라/", owner="admin",
            read=["인프라팀", "all"], write=["인프라팀"], manage=["admin"],
        ))
        scope = store.compute_access_scope("인프라/서버.md")
        assert "인프라팀" in scope["read"]
        assert "all" in scope["read"]

    def test_doc_override_scope(self, store: ACLStore):
        store.set_acl(ACLEntry(
            path="인프라/", owner="admin",
            read=["인프라팀"], write=["인프라팀"], manage=["admin"],
        ))
        store.set_acl(ACLEntry(
            path="인프라/비밀.md", owner="donghae",
            read=["@donghae"], write=["@donghae"], manage=["@donghae"],
            inherited=False,
        ))
        scope = store.compute_access_scope("인프라/비밀.md")
        assert "@donghae" in scope["read"]
        assert "인프라팀" not in scope["read"]

    def test_personal_scope(self, store: ACLStore):
        scope = store.compute_access_scope("@donghae/notes.md")
        assert scope["read"] == ["@donghae"]
        assert scope["write"] == ["@donghae"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_acl_v2.py -v`
Expected: FAIL — `ImportError` (ACLEntry model doesn't exist yet in new form)

- [ ] **Step 3: Rewrite ACLStore with v2 model**

Replace `backend/core/auth/acl_store.py` with the new implementation. Key changes:
- `ACLEntry` Pydantic model with owner, read, write, manage, inherited
- `Permission` extended to include "manage"
- `check_permission(path, user, permission)` — takes User instead of roles list
- Personal space hardcoded check (`@username/`)
- Default-deny when no ACL found
- Admin bypass
- Owner bypass
- `compute_access_scope(path)` — returns `{read: [...], write: [...]}`
- `rename_group_references(old_name, new_name)` — batch rename for group changes
- `remove_group_references(group_name)` — batch remove for group deletion
- `get_paths_with_group(group_name)` — find affected paths

```python
# backend/core/auth/acl_store.py
"""ACL Store v2 — owner, manage, inherited, default-deny, personal space."""
from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from backend.core.auth.models import User

logger = logging.getLogger(__name__)

Permission = Literal["read", "write", "manage"]


class ACLEntry(BaseModel):
    """Access control entry for a path (folder or document)."""
    path: str
    owner: str = ""
    read: list[str] = []       # principals: group names, @userID, "all"
    write: list[str] = []
    manage: list[str] = []     # who can change this ACL
    inherited: bool = True     # True = inherited from parent folder


class ACLStore:
    """Path-based ACL with inheritance, personal space, and default-deny."""

    _CACHE_TTL = 60
    _FILE_POLL_INTERVAL = 30

    def __init__(self, acl_path: Path | None = None) -> None:
        self._path = acl_path or Path("data/.acl.json")
        self._lock = threading.Lock()
        self._acl: dict[str, dict] = {}
        self._perm_cache: dict[tuple, tuple[bool, float]] = {}
        self._last_mtime: float = 0
        self._load()
        self._start_watcher()

    # ── Persistence ──────────────────────────────────────────────────

    def _load(self) -> None:
        if self._path.exists():
            try:
                self._acl = json.loads(self._path.read_text(encoding="utf-8"))
                self._last_mtime = self._path.stat().st_mtime
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load ACL: %s", e)
                self._acl = {}
        else:
            self._acl = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._acl, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._last_mtime = self._path.stat().st_mtime
        self._invalidate_cache()

    def _invalidate_cache(self) -> None:
        self._perm_cache.clear()

    def _check_file_changed(self) -> None:
        try:
            if self._path.exists():
                mtime = self._path.stat().st_mtime
                if mtime > self._last_mtime:
                    self._load()
                    self._invalidate_cache()
        except OSError:
            pass

    def _start_watcher(self) -> None:
        def _poll():
            while True:
                time.sleep(self._FILE_POLL_INTERVAL)
                self._check_file_changed()
        t = threading.Thread(target=_poll, daemon=True)
        t.start()

    # ── ACL CRUD ─────────────────────────────────────────────────────

    def set_acl(self, entry: ACLEntry) -> None:
        with self._lock:
            self._acl[entry.path] = entry.model_dump()
            self._save()

    def remove_acl(self, path: str) -> bool:
        with self._lock:
            if path in self._acl:
                del self._acl[path]
                self._save()
                return True
            return False

    def get_entry(self, path: str) -> ACLEntry | None:
        raw = self._acl.get(path)
        return ACLEntry(**raw) if raw else None

    def get_all(self) -> dict[str, dict]:
        return dict(self._acl)

    # ── Permission Check ─────────────────────────────────────────────

    def check_permission(self, path: str, user: User,
                         permission: Permission) -> bool:
        cache_key = (path, user.id, tuple(user.roles), tuple(user.groups),
                     permission)
        now = time.time()
        cached = self._perm_cache.get(cache_key)
        if cached and (now - cached[1]) < self._CACHE_TTL:
            return cached[0]
        result = self._check_uncached(path, user, permission)
        self._perm_cache[cache_key] = (result, now)
        return result

    def _check_uncached(self, path: str, user: User,
                        permission: Permission) -> bool:
        # Rule 5: admin always allowed
        if "admin" in user.roles:
            return True

        # Rule 1: personal space — @username/ only accessible by owner
        if path.startswith("@"):
            owner_name = path.split("/")[0][1:]  # strip @
            return user.id == owner_name

        # Rule 6: owner always has full access
        entry = self._acl.get(path)
        if entry and entry.get("owner") == user.id:
            return True

        # Rule 2: document-level ACL exists and is not inherited
        if entry and not entry.get("inherited", True):
            return self._principals_match(
                entry.get(permission, []), user
            )

        # Rule 3: walk up parent folders
        parts = path.rstrip("/").split("/")
        for i in range(len(parts) - 1, 0, -1):
            parent = "/".join(parts[:i]) + "/"
            parent_entry = self._acl.get(parent)
            if parent_entry:
                # Check owner of parent
                if parent_entry.get("owner") == user.id:
                    return True
                return self._principals_match(
                    parent_entry.get(permission, []), user
                )

        # Rule 4: no ACL found → deny
        return False

    @staticmethod
    def _principals_match(allowed: list[str], user: User) -> bool:
        """Check if user matches any principal in allowed list."""
        if "all" in allowed:
            return True
        user_ref = f"@{user.id}"
        for principal in allowed:
            if principal == user_ref:
                return True
            if principal in user.groups:
                return True
            if principal in user.roles:
                return True
        return False

    # ── Access Scope ─────────────────────────────────────────────────

    def compute_access_scope(self, path: str) -> dict[str, list[str]]:
        """Compute materialized access scope for a path.

        Returns {"read": [...principals...], "write": [...principals...]}.
        Used to populate ChromaDB chunk metadata.
        """
        # Personal space
        if path.startswith("@"):
            owner_name = path.split("/")[0][1:]
            owner_ref = f"@{owner_name}"
            return {"read": [owner_ref], "write": [owner_ref]}

        # Check document-level override
        entry = self._acl.get(path)
        if entry and not entry.get("inherited", True):
            owner_ref = f"@{entry.get('owner', '')}" if entry.get("owner") else None
            read_scope = list(entry.get("read", []))
            write_scope = list(entry.get("write", []))
            if owner_ref and owner_ref not in read_scope:
                read_scope.append(owner_ref)
            if owner_ref and owner_ref not in write_scope:
                write_scope.append(owner_ref)
            return {"read": read_scope, "write": write_scope}

        # Walk up to find folder ACL
        parts = path.rstrip("/").split("/")
        for i in range(len(parts) - 1, 0, -1):
            parent = "/".join(parts[:i]) + "/"
            parent_entry = self._acl.get(parent)
            if parent_entry:
                owner_ref = (f"@{parent_entry.get('owner', '')}"
                             if parent_entry.get("owner") else None)
                read_scope = list(parent_entry.get("read", []))
                write_scope = list(parent_entry.get("write", []))
                if owner_ref and owner_ref not in read_scope:
                    read_scope.append(owner_ref)
                if owner_ref and owner_ref not in write_scope:
                    write_scope.append(owner_ref)
                return {"read": read_scope, "write": write_scope}

        # No ACL → empty scope (deny all)
        return {"read": [], "write": []}

    # ── Batch Operations (Group Rename/Delete) ───────────────────────

    def get_paths_with_group(self, group_name: str) -> list[str]:
        """Find all paths where group_name appears in read/write/manage."""
        paths = []
        for path, raw in self._acl.items():
            for field in ("read", "write", "manage"):
                if group_name in raw.get(field, []):
                    paths.append(path)
                    break
        return paths

    def rename_group_references(self, old_name: str, new_name: str) -> int:
        """Rename group in all ACL entries. Returns count of changed entries."""
        changed = 0
        with self._lock:
            for raw in self._acl.values():
                entry_changed = False
                for field in ("read", "write", "manage"):
                    lst = raw.get(field, [])
                    for i, v in enumerate(lst):
                        if v == old_name:
                            lst[i] = new_name
                            entry_changed = True
                if entry_changed:
                    changed += 1
            if changed:
                self._save()
        return changed

    def remove_group_references(self, group_name: str) -> int:
        """Remove group from all ACL entries. Returns count of changed entries."""
        changed = 0
        with self._lock:
            for raw in self._acl.values():
                entry_changed = False
                for field in ("read", "write", "manage"):
                    lst = raw.get(field, [])
                    if group_name in lst:
                        lst.remove(group_name)
                        entry_changed = True
                if entry_changed:
                    changed += 1
            if changed:
                self._save()
        return changed

    # ── Legacy Compatibility ─────────────────────────────────────────

    def get_accessible_prefixes(self, user: User,
                                permission: Permission) -> list[str]:
        """Return path prefixes the user can access. Used for RAG fallback."""
        prefixes = []
        if "admin" in user.roles:
            return [""]  # admin sees everything
        prefixes.append(f"@{user.id}/")  # personal space
        for path, raw in self._acl.items():
            if path.endswith("/") and self._principals_match(
                raw.get(permission, []), user
            ):
                prefixes.append(path)
        return prefixes
```

- [ ] **Step 4: Update permission.py with require_manage and new User-based checks**

```python
# backend/core/auth/permission.py
"""FastAPI permission dependencies."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from backend.core.auth.acl_store import acl_store
from backend.core.auth.deps import get_current_user
from backend.core.auth.models import User


async def require_read(
    request: Request, user: User = Depends(get_current_user),
) -> User:
    path = _extract_path(request)
    if path and not acl_store.check_permission(path, user, "read"):
        raise HTTPException(403, "Read permission denied")
    return user


async def require_write(
    request: Request, user: User = Depends(get_current_user),
) -> User:
    path = _extract_path(request)
    if path and not acl_store.check_permission(path, user, "write"):
        raise HTTPException(403, "Write permission denied")
    return user


async def require_manage(
    request: Request, user: User = Depends(get_current_user),
) -> User:
    path = _extract_path(request)
    if path and not acl_store.check_permission(path, user, "manage"):
        raise HTTPException(403, "Manage permission denied")
    return user


def _extract_path(request: Request) -> str | None:
    return request.path_params.get("path")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_acl_v2.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add backend/core/auth/acl_store.py backend/core/auth/permission.py tests/test_acl_v2.py
git commit -m "feat: ACL Store v2 with owner, manage, inherited, default-deny, personal space"
```

---

## Task 3: NoOpProvider 다중 사용자 지원

**Files:**
- Modify: `backend/core/auth/noop_provider.py`
- Modify: `backend/core/auth/base.py`
- Modify: `backend/core/auth/deps.py`
- Create: `data/users.json`

- [ ] **Step 1: Add resolve_groups to AuthProvider ABC**

In `backend/core/auth/base.py`, add the new abstract method:

```python
class AuthProvider(ABC):
    @abstractmethod
    async def authenticate(self, request: Request) -> User:
        ...

    @abstractmethod
    async def resolve_groups(self, user_id: str) -> list[str]:
        """Return group names the user belongs to."""
        ...

    @abstractmethod
    async def on_startup(self) -> None:
        ...

    @abstractmethod
    async def on_shutdown(self) -> None:
        ...
```

- [ ] **Step 2: Create dev users config**

```json
// data/users.json
{
  "users": [
    {
      "id": "donghae",
      "name": "동해",
      "email": "donghae@ontong.local",
      "roles": ["admin"]
    },
    {
      "id": "kim",
      "name": "김팀원",
      "email": "kim@ontong.local",
      "roles": []
    },
    {
      "id": "lee",
      "name": "이팀원",
      "email": "lee@ontong.local",
      "roles": []
    }
  ]
}
```

- [ ] **Step 3: Rewrite NoOpProvider for multi-user dev mode**

```python
# backend/core/auth/noop_provider.py
"""Development auth provider — multi-user from config file.

Selects user via X-User-Id header (default: first user in config).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import Request

from backend.core.auth.base import AuthProvider
from backend.core.auth.models import User

logger = logging.getLogger(__name__)

_DEFAULT_USER = User(
    id="dev-user", name="개발자", email="dev@ontong.local", roles=["admin"],
)


class NoOpAuthProvider(AuthProvider):
    def __init__(self, users_path: Path | None = None,
                 group_store=None) -> None:
        self._users_path = users_path or Path("data/users.json")
        self._users: dict[str, User] = {}
        self._group_store = group_store

    async def on_startup(self) -> None:
        if self._users_path.exists():
            try:
                data = json.loads(
                    self._users_path.read_text(encoding="utf-8")
                )
                for u in data.get("users", []):
                    user = User(**u)
                    self._users[user.id] = user
                logger.info("Loaded %d dev users", len(self._users))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load users: %s", e)
        if not self._users:
            self._users[_DEFAULT_USER.id] = _DEFAULT_USER

    async def on_shutdown(self) -> None:
        pass

    async def authenticate(self, request: Request) -> User:
        user_id = request.headers.get("X-User-Id", "")
        user = self._users.get(user_id)
        if not user:
            # Default to first user
            user = next(iter(self._users.values()))
        # Resolve groups
        groups = await self.resolve_groups(user.id)
        return user.model_copy(update={"groups": groups})

    async def resolve_groups(self, user_id: str) -> list[str]:
        if not self._group_store:
            return []
        user_groups = self._group_store.get_user_groups(user_id)
        return [g.name for g in user_groups]
```

- [ ] **Step 4: Update factory to pass group_store**

In `backend/core/auth/factory.py`:

```python
from backend.core.auth.base import AuthProvider


def create_auth_provider(provider_name: str, **kwargs) -> AuthProvider:
    if provider_name == "noop":
        from backend.core.auth.noop_provider import NoOpAuthProvider
        return NoOpAuthProvider(**kwargs)
    raise ValueError(f"Unknown auth provider: {provider_name}")
```

- [ ] **Step 5: Commit**

```bash
git add backend/core/auth/base.py backend/core/auth/noop_provider.py \
       backend/core/auth/factory.py backend/core/auth/deps.py data/users.json
git commit -m "feat: multi-user NoOpProvider with X-User-Id header and group resolution"
```

---

## Task 4: Access Scope 계산 모듈

**Files:**
- Create: `backend/core/auth/scope.py`
- Create: `tests/test_scope.py`

- [ ] **Step 1: Write failing tests for scope module**

```python
# tests/test_scope.py
"""Access scope computation tests."""
import pytest
from backend.core.auth.models import User
from backend.core.auth.scope import get_user_scope, format_scope_for_chroma


def make_user(uid: str, roles=None, groups=None) -> User:
    return User(id=uid, name=uid, roles=roles or [], groups=groups or [])


class TestGetUserScope:
    def test_basic_scope(self):
        user = make_user("donghae", roles=["admin"], groups=["인프라팀"])
        scope = get_user_scope(user)
        assert "@donghae" in scope
        assert "인프라팀" in scope
        assert "admin" in scope
        assert "all" in scope

    def test_no_groups_no_roles(self):
        user = make_user("viewer")
        scope = get_user_scope(user)
        assert scope == ["@viewer", "all"]

    def test_multiple_groups(self):
        user = make_user("u1", groups=["인프라팀", "프로젝트X"])
        scope = get_user_scope(user)
        assert "인프라팀" in scope
        assert "프로젝트X" in scope


class TestFormatScopeForChroma:
    def test_pipe_delimited(self):
        principals = ["인프라팀", "@donghae", "admin"]
        result = format_scope_for_chroma(principals)
        assert result == "|인프라팀|@donghae|admin|"

    def test_empty(self):
        assert format_scope_for_chroma([]) == ""

    def test_single(self):
        assert format_scope_for_chroma(["@kim"]) == "|@kim|"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_scope.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement scope module**

```python
# backend/core/auth/scope.py
"""Access scope computation for ChromaDB metadata."""
from __future__ import annotations

from backend.core.auth.models import User


def get_user_scope(user: User) -> list[str]:
    """Compute the list of principals this user matches.

    Used at query time to filter ChromaDB results:
    where: access_read contains any of user_scope.
    """
    scope = [f"@{user.id}"]
    scope.extend(user.groups)
    scope.extend(user.roles)
    scope.append("all")
    return scope


def format_scope_for_chroma(principals: list[str]) -> str:
    """Convert principal list to pipe-delimited string for ChromaDB.

    Example: ["인프라팀", "@kim"] → "|인프라팀|@kim|"
    Matches existing pipe-delimited convention for tags field.
    """
    if not principals:
        return ""
    return "|" + "|".join(principals) + "|"


def build_scope_where_clause(user_scope: list[str]) -> dict | None:
    """Build ChromaDB where clause for access_read filtering.

    Returns $or clause checking if access_read contains any scope item.
    Returns None if user has admin role (no filtering needed).
    """
    if "admin" in user_scope:
        return None  # admin sees everything
    if not user_scope:
        return {"access_read": {"$eq": "__never_match__"}}
    conditions = [
        {"access_read": {"$contains": f"|{item}|"}}
        for item in user_scope
    ]
    if len(conditions) == 1:
        return conditions[0]
    return {"$or": conditions}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_scope.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/core/auth/scope.py tests/test_scope.py
git commit -m "feat: access scope computation module for ChromaDB filtering"
```

---

## Task 5: ChromaDB 메타데이터 확장 + 인덱서 연동

**Files:**
- Modify: `backend/application/wiki/wiki_indexer.py` (lines 204-228: `_metadata_to_chroma`)
- Modify: `backend/application/wiki/wiki_service.py` (lines 104-151: `save_file`, lines 335-353: `_bg_index`)

- [ ] **Step 1: Extend _metadata_to_chroma to include access_scope**

In `backend/application/wiki/wiki_indexer.py`, modify the `_metadata_to_chroma` method to accept and include access_scope:

Add `access_scope` parameter to `index_file()` signature:

```python
# In WikiIndexer.index_file() — add access_scope parameter
async def index_file(self, wiki_file: WikiFile, force: bool = False,
                     access_scope: dict[str, str] | None = None) -> int:
```

In `_metadata_to_chroma()`, after existing metadata conversion, add:

```python
# After existing metadata conversion (around line 225)
if access_scope:
    meta["access_read"] = access_scope.get("read", "")
    meta["access_write"] = access_scope.get("write", "")
else:
    meta["access_read"] = ""
    meta["access_write"] = ""
```

- [ ] **Step 2: Modify wiki_service.py to compute and pass access_scope**

In `WikiService.save_file()`, after the storage write and before `_bg_index`:

```python
# After storage.write() in save_file, compute access_scope
from backend.core.auth.acl_store import acl_store
from backend.core.auth.scope import format_scope_for_chroma

scope = acl_store.compute_access_scope(path)
access_scope = {
    "read": format_scope_for_chroma(scope["read"]),
    "write": format_scope_for_chroma(scope["write"]),
}
```

Pass `access_scope` to `_bg_index` and then to `indexer.index_file()`.

In `_bg_index()`:

```python
async def _bg_index(self, wiki_file: WikiFile,
                    access_scope: dict[str, str] | None = None) -> None:
    # ...existing code...
    await self._indexer.index_file(wiki_file, access_scope=access_scope)
    # ...rest of existing code...
```

- [ ] **Step 3: Add update_metadata method to WikiIndexer for ACL-only updates**

Add to `WikiIndexer`:

```python
async def update_access_scope(self, file_path: str,
                               access_scope: dict[str, str]) -> int:
    """Update only access_scope metadata for existing chunks (no re-embedding)."""
    if not self.chroma.is_connected:
        return 0
    data = self.chroma._collection.get(
        where={"file_path": file_path},
        include=["metadatas"],
    )
    if not data["ids"]:
        return 0
    updated_metadatas = []
    for meta in data["metadatas"]:
        meta["access_read"] = access_scope.get("read", "")
        meta["access_write"] = access_scope.get("write", "")
        updated_metadatas.append(meta)
    self.chroma._collection.update(
        ids=data["ids"],
        metadatas=updated_metadatas,
    )
    return len(data["ids"])
```

- [ ] **Step 4: Commit**

```bash
git add backend/application/wiki/wiki_indexer.py backend/application/wiki/wiki_service.py
git commit -m "feat: inject access_scope into ChromaDB chunk metadata on index"
```

---

## Task 6: 검색 ACL 스코핑 (wiki_search + rag_agent + conflict)

**Files:**
- Modify: `backend/application/agent/skills/wiki_search.py`
- Modify: `backend/application/agent/rag_agent.py`
- Modify: `backend/application/conflict/conflict_service.py`

- [ ] **Step 1: Add scope filter to wiki_search.py**

In `WikiSearchSkill.execute()`, after building `effective_filter` (around line 51), merge with scope filter:

```python
from backend.core.auth.scope import get_user_scope, build_scope_where_clause

# After existing filter construction (line ~51)
# Add access_read filter if user_roles provided
if user_roles:
    # Build a temporary User for scope calculation
    # user_roles is passed as list[str] — extract user info from context
    scope_filter = build_scope_where_clause(user_roles)
    if scope_filter:
        effective_filter = _merge_where_filters(effective_filter, scope_filter)
```

Modify the `execute` method signature to accept `user_scope: list[str] | None = None` instead of using `user_roles` for ACL filtering. The ACL post-filter at lines 113-123 can be kept as a safety fallback but the primary filtering is now done via ChromaDB where clause.

- [ ] **Step 2: Add scope filter to rag_agent.py**

In `RAGAgent.__init__`, accept `current_user_scope: list[str] | None = None`.

In `_handle_qa()`, when building the where clause (around line 591-626), merge scope filter:

```python
from backend.core.auth.scope import build_scope_where_clause

# After existing filter construction
scope_filter = build_scope_where_clause(self._current_user_scope or [])
if scope_filter:
    effective_filter = self._merge_where_filters(effective_filter, scope_filter)
```

Update the `api/agent.py` to pass user scope when creating RAGAgent context:

```python
from backend.core.auth.scope import get_user_scope

# In chat endpoint, after getting user:
user_scope = get_user_scope(user)
# Pass to RAGAgent
agent.set_user_scope(user_scope)
```

- [ ] **Step 3: Add scope filter to conflict_service.py**

In `ConflictDetectionService.check_file()`, add `user_scope` parameter:

```python
def check_file(self, file_path: str,
               threshold: float = SIMILARITY_THRESHOLD,
               user_scope: list[str] | None = None) -> list[StoredConflict]:
```

When querying HNSW candidates (around line 83), add where clause:

```python
from backend.core.auth.scope import build_scope_where_clause

# When querying for candidates
where = build_scope_where_clause(user_scope) if user_scope else None
if where:
    results = self._chroma.query_by_embedding(
        avg_embedding, n_results=HNSW_N_RESULTS, where=where
    )
else:
    results = self._chroma.query_by_embedding(
        avg_embedding, n_results=HNSW_N_RESULTS
    )
```

Note: `query_by_embedding` in `chroma.py` (line 179) needs a `where` parameter added:

```python
def query_by_embedding(self, embedding, n_results=5, where=None):
    kwargs = {"query_embeddings": [embedding], "n_results": n_results}
    if where:
        kwargs["where"] = where
    return self._collection.query(**kwargs)
```

- [ ] **Step 4: Commit**

```bash
git add backend/application/agent/skills/wiki_search.py \
       backend/application/agent/rag_agent.py \
       backend/application/conflict/conflict_service.py \
       backend/infrastructure/vectordb/chroma.py
git commit -m "feat: ACL scope filtering in search, RAG agent, and conflict detection"
```

---

## Task 7: Group API + ACL API 확장

**Files:**
- Create: `backend/api/group.py`
- Modify: `backend/api/acl.py`
- Modify: `backend/api/auth.py`
- Create: `tests/test_group_api.py`

- [ ] **Step 1: Write failing tests for Group API**

```python
# tests/test_group_api.py
"""Group API endpoint tests."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client with initialized app."""
    from backend.main import app
    return TestClient(app)


class TestGroupAPI:
    def test_list_groups(self, client):
        resp = client.get("/api/groups")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_group(self, client):
        resp = client.post("/api/groups", json={
            "id": "test-team",
            "name": "테스트팀",
            "type": "custom",
            "members": ["dev-user"],
        })
        assert resp.status_code == 201

    def test_get_group(self, client):
        client.post("/api/groups", json={
            "id": "get-test", "name": "조회테스트",
            "type": "custom", "members": [],
        })
        resp = client.get("/api/groups/get-test")
        assert resp.status_code == 200
        assert resp.json()["name"] == "조회테스트"

    def test_add_member(self, client):
        client.post("/api/groups", json={
            "id": "mem-test", "name": "멤버테스트",
            "type": "custom", "members": [],
        })
        resp = client.put("/api/groups/mem-test/members",
                          json={"add": ["new-user"]})
        assert resp.status_code == 200

    def test_remove_member(self, client):
        client.post("/api/groups", json={
            "id": "rem-test", "name": "제거테스트",
            "type": "custom", "members": ["u1"],
        })
        resp = client.put("/api/groups/rem-test/members",
                          json={"remove": ["u1"]})
        assert resp.status_code == 200

    def test_delete_group(self, client):
        client.post("/api/groups", json={
            "id": "del-test", "name": "삭제테스트",
            "type": "custom", "members": [],
        })
        resp = client.delete("/api/groups/del-test")
        assert resp.status_code == 200
```

- [ ] **Step 2: Implement Group API**

```python
# backend/api/group.py
"""Group management API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.core.auth import User, get_current_user
from backend.core.auth.group_store import Group, GroupStore

router = APIRouter(prefix="/api/groups", tags=["groups"])

_group_store: GroupStore | None = None


def init(group_store: GroupStore) -> None:
    global _group_store
    _group_store = group_store


def _require_admin(user: User = Depends(get_current_user)) -> User:
    if "admin" not in user.roles:
        raise HTTPException(403, "Admin role required")
    return user


class CreateGroupRequest(BaseModel):
    id: str
    name: str
    type: str = "custom"
    members: list[str] = []


class MemberUpdateRequest(BaseModel):
    add: list[str] = []
    remove: list[str] = []


class RenameRequest(BaseModel):
    name: str


@router.get("")
async def list_groups(user: User = Depends(get_current_user)):
    return [g.model_dump() for g in _group_store.list_all()]


@router.post("", status_code=201)
async def create_group(body: CreateGroupRequest,
                       user: User = Depends(get_current_user)):
    if body.type == "department":
        if "admin" not in user.roles:
            raise HTTPException(403, "Only admin can create department groups")
    group = Group(
        id=body.id, name=body.name, type=body.type,
        members=body.members, created_by=user.id,
        managed_by=[f"@{user.id}", "admin"],
    )
    _group_store.create(group)
    return group.model_dump()


@router.get("/{group_id}")
async def get_group(group_id: str,
                    user: User = Depends(get_current_user)):
    group = _group_store.get(group_id)
    if not group:
        raise HTTPException(404, "Group not found")
    return group.model_dump()


@router.put("/{group_id}/members")
async def update_members(group_id: str, body: MemberUpdateRequest,
                         user: User = Depends(get_current_user)):
    group = _group_store.get(group_id)
    if not group:
        raise HTTPException(404, "Group not found")
    # Check manage permission
    user_ref = f"@{user.id}"
    if user_ref not in group.managed_by and "admin" not in user.roles:
        raise HTTPException(403, "Not authorized to manage this group")
    for uid in body.add:
        _group_store.add_member(group_id, uid)
    for uid in body.remove:
        _group_store.remove_member(group_id, uid)
    return _group_store.get(group_id).model_dump()


@router.put("/{group_id}")
async def rename_group(group_id: str, body: RenameRequest,
                       user: User = Depends(_require_admin)):
    group = _group_store.get(group_id)
    if not group:
        raise HTTPException(404, "Group not found")
    from backend.core.auth.acl_store import acl_store
    old_name = _group_store.rename(group_id, body.name)
    if old_name:
        changed = acl_store.rename_group_references(old_name, body.name)
        return {"group": _group_store.get(group_id).model_dump(),
                "acl_entries_updated": changed}
    return {"group": _group_store.get(group_id).model_dump(),
            "acl_entries_updated": 0}


@router.delete("/{group_id}")
async def delete_group(group_id: str,
                       user: User = Depends(_require_admin)):
    group = _group_store.get(group_id)
    if not group:
        raise HTTPException(404, "Group not found")
    from backend.core.auth.acl_store import acl_store
    affected = acl_store.get_paths_with_group(group.name)
    acl_store.remove_group_references(group.name)
    _group_store.delete(group_id)
    return {"deleted": group_id, "acl_entries_affected": len(affected)}
```

- [ ] **Step 3: Extend ACL API for document-level ACL and manage permission**

Rewrite `backend/api/acl.py`:

```python
# backend/api/acl.py
"""ACL management API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.core.auth import User, get_current_user
from backend.core.auth.acl_store import ACLEntry, acl_store
from backend.core.auth.permission import require_manage

router = APIRouter(prefix="/api/acl", tags=["acl"])


def _require_admin(user: User = Depends(get_current_user)) -> User:
    if "admin" not in user.roles:
        raise HTTPException(403, "Admin role required")
    return user


class SetACLRequest(BaseModel):
    path: str
    read: list[str] = []
    write: list[str] = []
    manage: list[str] = []
    inherited: bool = True


# Admin: view all ACLs
@router.get("", dependencies=[Depends(_require_admin)])
async def get_all_acl():
    return acl_store.get_all()


# Get ACL for specific path
@router.get("/{path:path}")
async def get_acl(path: str, user: User = Depends(get_current_user)):
    entry = acl_store.get_entry(path)
    if not entry:
        # Return computed scope from inheritance
        scope = acl_store.compute_access_scope(path)
        return {"path": path, "inherited": True, **scope}
    return entry.model_dump()


# Set ACL — requires manage permission on the path
@router.put("/{path:path}")
async def set_acl(path: str, body: SetACLRequest,
                  user: User = Depends(get_current_user)):
    # Check manage permission
    if not acl_store.check_permission(path, user, "manage"):
        raise HTTPException(403, "Manage permission required")
    entry = ACLEntry(
        path=path, owner=body.path if not acl_store.get_entry(path)
        else acl_store.get_entry(path).owner or user.id,
        read=body.read, write=body.write, manage=body.manage,
        inherited=body.inherited,
    )
    # Preserve existing owner
    existing = acl_store.get_entry(path)
    if existing:
        entry.owner = existing.owner
    else:
        entry.owner = user.id
    acl_store.set_acl(entry)
    # Trigger access_scope recomputation for ChromaDB
    from backend.infrastructure.events.event_bus import event_bus
    event_bus.publish("acl_changed", {"path": path})
    return entry.model_dump()


# Remove ACL — admin only
@router.delete("", dependencies=[Depends(_require_admin)])
async def remove_acl(path: str = Query(...)):
    if acl_store.remove_acl(path):
        return {"removed": path}
    raise HTTPException(404, "ACL entry not found")
```

- [ ] **Step 4: Commit**

```bash
git add backend/api/group.py backend/api/acl.py tests/test_group_api.py
git commit -m "feat: Group CRUD API and document-level ACL API with manage permission"
```

---

## Task 8: main.py 통합 + 이벤트 핸들러

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/infrastructure/events/event_bus.py`

- [ ] **Step 1: Add async callback support to EventBus**

In `event_bus.py`, extend the `on()` method to support async callbacks, and add an `emit_async()` method:

```python
import asyncio
import inspect

def on(self, event_type: str, callback) -> None:
    """Register callback (sync or async) for event type."""
    self._callbacks.setdefault(event_type, []).append(callback)

def publish(self, event_type: str, data: dict) -> None:
    # Fire synchronous callbacks
    for cb in self._callbacks.get(event_type, []):
        if inspect.iscoroutinefunction(cb):
            # Schedule async callbacks
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(cb(data))
            except RuntimeError:
                pass  # No event loop running
        else:
            try:
                cb(data)
            except Exception as e:
                logger.warning("Callback error for %s: %s", event_type, e)
    # ... rest of existing fan-out code ...
```

- [ ] **Step 2: Wire GroupStore and scope handlers in main.py**

In the lifespan function of `main.py`, add after auth init (around line 71):

```python
# After auth init, before storage init:
from backend.core.auth.group_store import JSONGroupStore
from backend.api import group as group_api

group_store = JSONGroupStore()
group_api.init(group_store)

# Pass group_store to auth provider
auth_provider = create_auth_provider(
    settings.auth_provider, group_store=group_store
)
await auth_provider.on_startup()
init_auth(auth_provider)
```

Register the `acl_changed` event handler:

```python
# After event_bus setup:
async def _on_acl_changed(data: dict):
    """Recompute access_scope in ChromaDB when ACL changes."""
    path = data.get("path", "")
    if not path:
        return
    from backend.core.auth.acl_store import acl_store
    from backend.core.auth.scope import format_scope_for_chroma
    scope = acl_store.compute_access_scope(path)
    access_scope = {
        "read": format_scope_for_chroma(scope["read"]),
        "write": format_scope_for_chroma(scope["write"]),
    }
    await indexer.update_access_scope(path, access_scope)

event_bus.on("acl_changed", _on_acl_changed)
```

Include the group API router:

```python
# With other router includes:
from backend.api import group as group_api
app.include_router(group_api.router)
```

- [ ] **Step 3: Commit**

```bash
git add backend/main.py backend/infrastructure/events/event_bus.py
git commit -m "feat: wire GroupStore, ACL event handler, and scope recomputation in main.py"
```

---

## Task 9: Frontend 타입 + API 클라이언트 + useAuth 훅

**Files:**
- Create: `frontend/src/types/auth.ts`
- Modify: `frontend/src/types/index.ts`
- Create: `frontend/src/lib/api/auth.ts`
- Create: `frontend/src/lib/api/acl.ts`
- Create: `frontend/src/lib/api/groups.ts`
- Create: `frontend/src/hooks/useAuth.ts`

- [ ] **Step 1: Create auth types**

```typescript
// frontend/src/types/auth.ts
export interface User {
  id: string;
  name: string;
  email: string;
  roles: string[];
  groups: string[];
}

export interface Group {
  id: string;
  name: string;
  type: "department" | "custom";
  members: string[];
  created_by: string;
  managed_by: string[];
}

export type Permission = "read" | "write" | "manage";

export interface ACLEntry {
  path: string;
  owner: string;
  read: string[];
  write: string[];
  manage: string[];
  inherited: boolean;
}

export interface AccessInfo {
  canRead: boolean;
  canWrite: boolean;
  canManage: boolean;
  isOwner: boolean;
}
```

- [ ] **Step 2: Update types index**

In `frontend/src/types/index.ts`, add:

```typescript
export * from "./auth";
```

- [ ] **Step 3: Create API clients**

```typescript
// frontend/src/lib/api/auth.ts
import type { User } from "@/types/auth";

export async function fetchCurrentUser(): Promise<User> {
  const res = await fetch("/api/auth/me");
  if (!res.ok) throw new Error("Failed to fetch user");
  return res.json();
}
```

```typescript
// frontend/src/lib/api/acl.ts
import type { ACLEntry } from "@/types/auth";

export async function fetchACL(path: string): Promise<ACLEntry & { inherited: boolean }> {
  const res = await fetch(`/api/acl/${encodeURIComponent(path)}`);
  if (!res.ok) throw new Error("Failed to fetch ACL");
  return res.json();
}

export async function setACL(
  path: string,
  acl: { read: string[]; write: string[]; manage: string[]; inherited: boolean },
): Promise<ACLEntry> {
  const res = await fetch(`/api/acl/${encodeURIComponent(path)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, ...acl }),
  });
  if (!res.ok) throw new Error("Failed to set ACL");
  return res.json();
}
```

```typescript
// frontend/src/lib/api/groups.ts
import type { Group } from "@/types/auth";

export async function fetchGroups(): Promise<Group[]> {
  const res = await fetch("/api/groups");
  if (!res.ok) throw new Error("Failed to fetch groups");
  return res.json();
}

export async function createGroup(
  body: { id: string; name: string; type: string; members: string[] },
): Promise<Group> {
  const res = await fetch("/api/groups", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Failed to create group");
  return res.json();
}

export async function updateMembers(
  groupId: string,
  body: { add?: string[]; remove?: string[] },
): Promise<Group> {
  const res = await fetch(`/api/groups/${groupId}/members`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Failed to update members");
  return res.json();
}

export async function deleteGroup(groupId: string): Promise<void> {
  const res = await fetch(`/api/groups/${groupId}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete group");
}
```

- [ ] **Step 4: Create useAuth hook**

```typescript
// frontend/src/hooks/useAuth.ts
"use client";

import { useEffect, useState } from "react";
import type { User, AccessInfo } from "@/types/auth";
import { fetchCurrentUser } from "@/lib/api/auth";

let cachedUser: User | null = null;

export function useAuth() {
  const [user, setUser] = useState<User | null>(cachedUser);
  const [loading, setLoading] = useState(!cachedUser);

  useEffect(() => {
    if (cachedUser) return;
    fetchCurrentUser()
      .then((u) => {
        cachedUser = u;
        setUser(u);
      })
      .finally(() => setLoading(false));
  }, []);

  function checkAccess(
    acl: { owner?: string; read?: string[]; write?: string[]; manage?: string[] } | null,
  ): AccessInfo {
    if (!user) return { canRead: false, canWrite: false, canManage: false, isOwner: false };
    if (user.roles.includes("admin")) {
      return { canRead: true, canWrite: true, canManage: true, isOwner: false };
    }
    const isOwner = acl?.owner === user.id;
    const userPrincipals = [`@${user.id}`, ...user.groups, ...user.roles, "all"];

    const matches = (allowed: string[]) =>
      allowed.some((p) => userPrincipals.includes(p));

    return {
      canRead: isOwner || matches(acl?.read ?? []),
      canWrite: isOwner || matches(acl?.write ?? []),
      canManage: isOwner || matches(acl?.manage ?? []),
      isOwner,
    };
  }

  return { user, loading, checkAccess };
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/auth.ts frontend/src/types/index.ts \
       frontend/src/lib/api/auth.ts frontend/src/lib/api/acl.ts \
       frontend/src/lib/api/groups.ts frontend/src/hooks/useAuth.ts
git commit -m "feat: frontend auth types, API clients, and useAuth hook"
```

---

## Task 10: 공통 ContextMenu 컴포넌트

**Files:**
- Create: `frontend/src/components/ContextMenu.tsx`

- [ ] **Step 1: Create reusable ContextMenu with position correction**

```tsx
// frontend/src/components/ContextMenu.tsx
"use client";

import { useEffect, useRef, useState } from "react";

export interface MenuItemDef {
  label: string;
  icon?: React.ReactNode;
  action: () => void;
  visible?: boolean;   // default true — false hides the item entirely
  separator?: boolean;  // render separator before this item
}

interface ContextMenuProps {
  x: number;
  y: number;
  items: MenuItemDef[];
  onClose: () => void;
}

export function ContextMenu({ x, y, items, onClose }: ContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ x, y });

  // Position correction after mount
  useEffect(() => {
    const el = menuRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    let nx = x;
    let ny = y;
    // Flip horizontal if overflows right
    if (x + rect.width > vw - 8) nx = Math.max(8, x - rect.width);
    // Flip vertical if overflows bottom
    if (y + rect.height > vh - 8) ny = Math.max(8, y - rect.height);
    // Clamp to viewport
    nx = Math.min(nx, vw - rect.width - 8);
    ny = Math.min(ny, vh - rect.height - 8);
    setPos({ x: nx, y: ny });
  }, [x, y]);

  // Close on click outside or Escape
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [onClose]);

  const visibleItems = items.filter((item) => item.visible !== false);
  if (visibleItems.length === 0) return null;

  return (
    <div
      ref={menuRef}
      className="fixed z-50 min-w-[180px] rounded-md border bg-popover p-1 shadow-lg"
      style={{ left: pos.x, top: pos.y }}
    >
      {visibleItems.map((item, i) => (
        <div key={i}>
          {item.separator && i > 0 && (
            <div className="my-1 h-px bg-border" />
          )}
          <button
            className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm
                       hover:bg-accent hover:text-accent-foreground"
            onClick={() => {
              item.action();
              onClose();
            }}
          >
            {item.icon && (
              <span className="h-4 w-4 flex-shrink-0">{item.icon}</span>
            )}
            {item.label}
          </button>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ContextMenu.tsx
git commit -m "feat: reusable ContextMenu component with viewport position correction"
```

---

## Task 11: ShareDialog + PropertiesPanel

**Files:**
- Create: `frontend/src/components/ShareDialog.tsx`
- Create: `frontend/src/components/PropertiesPanel.tsx`

- [ ] **Step 1: Create ShareDialog**

```tsx
// frontend/src/components/ShareDialog.tsx
"use client";

import { useEffect, useState } from "react";
import { X, UserPlus, Trash2 } from "lucide-react";
import type { ACLEntry } from "@/types/auth";
import { fetchACL, setACL } from "@/lib/api/acl";
import { fetchGroups } from "@/lib/api/groups";

interface ShareDialogProps {
  path: string;
  onClose: () => void;
}

type PermLevel = "read" | "readwrite";

interface ShareEntry {
  principal: string;  // "@kim" or "인프라팀"
  level: PermLevel;
}

export function ShareDialog({ path, onClose }: ShareDialogProps) {
  const [entries, setEntries] = useState<ShareEntry[]>([]);
  const [inherited, setInherited] = useState(true);
  const [owner, setOwner] = useState("");
  const [search, setSearch] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchACL(path).then((acl) => {
      setOwner(acl.owner || "");
      setInherited(acl.inherited);
      // Build entries from read/write lists
      const map = new Map<string, PermLevel>();
      for (const p of acl.write || []) {
        if (p !== "all") map.set(p, "readwrite");
      }
      for (const p of acl.read || []) {
        if (p !== "all" && !map.has(p)) map.set(p, "read");
      }
      setEntries(Array.from(map, ([principal, level]) => ({ principal, level })));
    });
    fetchGroups().then((groups) => {
      setSuggestions(groups.map((g) => g.name));
    });
  }, [path]);

  async function handleSave() {
    setSaving(true);
    const read = entries.map((e) => e.principal);
    const write = entries.filter((e) => e.level === "readwrite").map((e) => e.principal);
    try {
      await setACL(path, { read, write, manage: [`@${owner}`], inherited });
    } finally {
      setSaving(false);
      onClose();
    }
  }

  function addPrincipal(name: string) {
    if (!name.trim()) return;
    const principal = name.startsWith("@") ? name : name;
    if (entries.some((e) => e.principal === principal)) return;
    setEntries([...entries, { principal, level: "read" }]);
    setSearch("");
  }

  function removePrincipal(principal: string) {
    setEntries(entries.filter((e) => e.principal !== principal));
  }

  function toggleLevel(principal: string) {
    setEntries(entries.map((e) =>
      e.principal === principal
        ? { ...e, level: e.level === "read" ? "readwrite" : "read" }
        : e
    ));
  }

  const filtered = suggestions.filter(
    (s) => s.includes(search) && !entries.some((e) => e.principal === s),
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-[420px] rounded-lg border bg-background p-4 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-semibold">공유 설정</h3>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mb-3 text-xs text-muted-foreground">
          소유자: <span className="font-medium text-foreground">{owner || "—"}</span>
        </div>

        {/* Current permissions */}
        <div className="mb-3 max-h-[200px] space-y-1 overflow-y-auto">
          {entries.map((e) => (
            <div key={e.principal} className="flex items-center justify-between rounded px-2 py-1 hover:bg-muted">
              <span className="text-sm">{e.principal}</span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => toggleLevel(e.principal)}
                  className="rounded px-2 py-0.5 text-xs border hover:bg-accent"
                >
                  {e.level === "readwrite" ? "읽기/쓰기" : "읽기"}
                </button>
                <button onClick={() => removePrincipal(e.principal)}
                        className="text-muted-foreground hover:text-destructive">
                  <Trash2 className="h-3 w-3" />
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Add principal */}
        <div className="relative mb-3">
          <div className="flex gap-2">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && search.trim()) {
                  addPrincipal(search.trim());
                }
              }}
              placeholder="사용자(@이름) 또는 그룹 추가"
              className="flex-1 rounded border px-2 py-1 text-sm"
            />
            <button
              onClick={() => addPrincipal(search.trim())}
              className="rounded border px-2 py-1 text-sm hover:bg-accent"
            >
              <UserPlus className="h-4 w-4" />
            </button>
          </div>
          {search && filtered.length > 0 && (
            <div className="absolute top-full z-10 mt-1 max-h-[120px] w-full overflow-y-auto rounded border bg-popover shadow-md">
              {filtered.slice(0, 8).map((s) => (
                <button
                  key={s}
                  onClick={() => addPrincipal(s)}
                  className="block w-full px-2 py-1 text-left text-sm hover:bg-accent"
                >
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Inheritance toggle */}
        <label className="mb-4 flex items-center gap-2 text-xs">
          <input
            type="checkbox"
            checked={!inherited}
            onChange={(e) => setInherited(!e.target.checked)}
          />
          폴더 권한 상속 해제 (직접 관리)
        </label>

        {/* Actions */}
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="rounded border px-3 py-1 text-sm hover:bg-muted">
            취소
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="rounded bg-primary px-3 py-1 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {saving ? "저장 중..." : "저장"}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create PropertiesPanel**

```tsx
// frontend/src/components/PropertiesPanel.tsx
"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { fetchACL } from "@/lib/api/acl";
import { useAuth } from "@/hooks/useAuth";

interface PropertiesPanelProps {
  path: string;
  metadata?: {
    created_by?: string;
    updated_by?: string;
    created?: string;
    updated?: string;
    status?: string;
  };
  onClose: () => void;
  onOpenShare?: () => void;
}

export function PropertiesPanel({
  path, metadata, onClose, onOpenShare,
}: PropertiesPanelProps) {
  const { user, checkAccess } = useAuth();
  const [acl, setAcl] = useState<{
    owner?: string; read?: string[]; write?: string[]; manage?: string[];
    inherited?: boolean;
  } | null>(null);

  useEffect(() => {
    fetchACL(path).then(setAcl);
  }, [path]);

  const access = checkAccess(acl);

  // Determine permission source
  const permSource = acl?.inherited !== false
    ? `📁 ${path.split("/").slice(0, -1).join("/") || "루트"}/ 에서 상속`
    : "직접 설정됨";

  const myPerms: string[] = [];
  if (access.canRead) myPerms.push("읽기");
  if (access.canWrite) myPerms.push("쓰기");
  if (access.canManage) myPerms.push("관리");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-[360px] rounded-lg border bg-background p-4 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-semibold">속성</h3>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-2 text-sm">
          <Row label="소유자" value={acl?.owner || "—"} />
          <Row label="생성일" value={metadata?.created || "—"} />
          <Row label="수정일" value={metadata?.updated || "—"} />
          <Row label="최종 수정자" value={metadata?.updated_by || "—"} />
          <Row label="상태" value={metadata?.status || "—"} />
          <div className="my-2 h-px bg-border" />
          <Row label="내 권한" value={myPerms.join(" · ") || "없음"} />
          <Row label="권한 출처" value={permSource} />
        </div>

        <div className="mt-4 flex justify-end gap-2">
          {access.canManage && onOpenShare && (
            <button
              onClick={() => { onClose(); onOpenShare(); }}
              className="rounded bg-primary px-3 py-1 text-sm text-primary-foreground hover:bg-primary/90"
            >
              공유 설정
            </button>
          )}
          <button onClick={onClose} className="rounded border px-3 py-1 text-sm hover:bg-muted">
            닫기
          </button>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ShareDialog.tsx \
       frontend/src/components/PropertiesPanel.tsx
git commit -m "feat: ShareDialog and PropertiesPanel components"
```

---

## Task 12: TreeNav 섹션 분리 + ACL 필터링 + 새 ContextMenu 연동

**Files:**
- Modify: `frontend/src/components/TreeNav.tsx`
- Modify: `frontend/src/types/wiki.ts`

This is the largest frontend task. Key changes:

- [ ] **Step 1: Add ACL hint to WikiTreeNode type**

In `frontend/src/types/wiki.ts`:

```typescript
interface WikiTreeNode {
  name: string;
  path: string;
  is_dir: boolean;
  children: WikiTreeNode[];
  has_children?: boolean | null;
  // ACL hints (populated by backend)
  owner?: string;
  my_permission?: "read" | "write" | "manage";
  shared?: boolean;  // true if owner shared with others
}
```

- [ ] **Step 2: Refactor TreeNav section layout**

Replace the current section toggle (line ~1562 `SidebarSection`) with a multi-section collapsible layout. The "files" section becomes two sections: "내 문서" (personal, `@username/`) and "위키" (shared folders).

Key changes in TreeNav:
1. Replace `SidebarSection` state with per-section collapse states
2. Add `useAuth` hook to get current user
3. Filter tree data: personal tree = nodes under `@{user.id}/`, wiki tree = shared folder nodes where user has read access
4. Replace inline ContextMenu component (lines 90-192) with new `<ContextMenu>` component
5. Add "공유 설정" and "속성" menu items with permission-based visibility
6. Add sharing/lock icons to DraggableTreeItem based on my_permission

The implementation should:
- Keep all existing functionality (drag-drop, inline rename, create, delete)
- Add collapsible section headers: "내 문서", "위키", "스킬", "내 설정"
- Section expand/collapse state persisted to localStorage
- Skills and Settings sections default to collapsed
- Wiki section filters to only show accessible folders

- [ ] **Step 3: Integrate new ContextMenu with permission-based items**

Replace the inline ContextMenu (lines 90-192) with the new `<ContextMenu>` component:

```tsx
import { ContextMenu, MenuItemDef } from "@/components/ContextMenu";
import { ShareDialog } from "@/components/ShareDialog";
import { PropertiesPanel } from "@/components/PropertiesPanel";

// In TreeNav, when context menu is shown:
const menuItems: MenuItemDef[] = [
  { label: "열기", icon: <FileText className="h-4 w-4" />, action: () => openFile(node) },
  { label: "새 탭에서 열기", icon: <ExternalLink className="h-4 w-4" />, action: () => openInNewTab(node) },
  { label: "이름 변경", icon: <Pencil className="h-4 w-4" />, action: () => startRename(node),
    visible: canWrite, separator: true },
  { label: "이동...", icon: <FolderInput className="h-4 w-4" />, action: () => startMove(node),
    visible: canWrite },
  { label: "삭제", icon: <Trash2 className="h-4 w-4" />, action: () => handleDelete(node),
    visible: canWrite },
  { label: "공유 설정...", icon: <Users className="h-4 w-4" />, action: () => openShareDialog(node.path),
    visible: canManage, separator: true },
  { label: "링크 복사", icon: <Link className="h-4 w-4" />, action: () => copyLink(node) },
  { label: "속성", icon: <Info className="h-4 w-4" />, action: () => openProperties(node) },
];
```

- [ ] **Step 4: Add permission icons to DraggableTreeItem**

In the DraggableTreeItem render, after the file name:

```tsx
{/* Permission indicators */}
{node.my_permission === "read" && (
  <Lock className="h-3 w-3 text-muted-foreground ml-auto flex-shrink-0" />
)}
{node.shared && node.owner === user?.id && (
  <Users className="h-3 w-3 text-blue-500 ml-auto flex-shrink-0" />
)}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/TreeNav.tsx frontend/src/types/wiki.ts
git commit -m "feat: TreeNav section layout with ACL filtering, new ContextMenu, and permission icons"
```

---

## Task 13: Backend tree API — ACL 필터링 + 권한 힌트

**Files:**
- Modify: `backend/api/wiki.py`
- Modify: `backend/core/schemas.py`

- [ ] **Step 1: Add ACL hints to WikiTreeNode schema**

In `backend/core/schemas.py`:

```python
class WikiTreeNode(BaseModel):
    name: str
    path: str
    is_dir: bool
    children: list[WikiTreeNode] = []
    has_children: bool | None = None
    owner: str = ""
    my_permission: str = ""    # "read" | "write" | "manage"
    shared: bool = False       # true if owner shared with others
```

- [ ] **Step 2: Filter tree API by user permissions**

In `backend/api/wiki.py`, modify the tree endpoint to filter nodes by ACL:

```python
from backend.core.auth.acl_store import acl_store

@router.get("/tree")
async def get_tree(user: User = Depends(get_current_user), depth: int = 1):
    raw_tree = wiki_service.get_tree(depth=depth)
    # Filter to accessible nodes and annotate permissions
    filtered = _filter_tree_by_acl(raw_tree, user)
    return filtered

def _filter_tree_by_acl(nodes: list[WikiTreeNode], user: User) -> list[WikiTreeNode]:
    """Recursively filter tree to accessible nodes and annotate permission level."""
    result = []
    for node in nodes:
        # Check read permission
        if not acl_store.check_permission(node.path, user, "read"):
            continue
        # Determine permission level
        if acl_store.check_permission(node.path, user, "manage"):
            perm = "manage"
        elif acl_store.check_permission(node.path, user, "write"):
            perm = "write"
        else:
            perm = "read"
        # Check if shared
        entry = acl_store.get_entry(node.path)
        owner = entry.owner if entry else ""
        shared = bool(entry and entry.owner == user.id and
                      (len(entry.read) > 1 or entry.read != [f"@{user.id}"]))
        # Annotate
        annotated = node.model_copy(update={
            "owner": owner,
            "my_permission": perm,
            "shared": shared,
            "children": _filter_tree_by_acl(node.children, user),
        })
        result.append(annotated)
    return result
```

- [ ] **Step 3: Separate personal space tree**

Add a new endpoint for personal space tree:

```python
@router.get("/tree/personal")
async def get_personal_tree(user: User = Depends(get_current_user)):
    """Return tree for @username/ personal space."""
    personal_path = f"@{user.id}"
    return wiki_service.get_tree(root=personal_path, depth=3)
```

- [ ] **Step 4: Commit**

```bash
git add backend/api/wiki.py backend/core/schemas.py
git commit -m "feat: ACL-filtered tree API with permission hints and personal space endpoint"
```

---

## Task 14: 마이그레이션 — 기존 데이터 + 초기 ACL 설정

**Files:**
- Create: `scripts/migrate_acl.py`

- [ ] **Step 1: Create migration script**

```python
# scripts/migrate_acl.py
"""One-time migration: set up initial ACLs for existing folders and reindex with access_scope."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.auth.acl_store import ACLEntry, ACLStore
from backend.core.auth.scope import format_scope_for_chroma


async def main():
    acl = ACLStore()
    wiki_dir = Path("wiki")

    # 1. Set up top-level shared folder ACLs (admin-managed, readable by all)
    top_folders = [d for d in wiki_dir.iterdir()
                   if d.is_dir() and not d.name.startswith((".", "_", "@"))]
    for folder in top_folders:
        rel = folder.name + "/"
        if not acl.get_entry(rel):
            print(f"Setting ACL for {rel}: read=all, write=all, manage=admin")
            acl.set_acl(ACLEntry(
                path=rel, owner="admin",
                read=["all"], write=["all"], manage=["admin"],
            ))

    # 2. Set up system folder ACLs
    for system_folder in ["_skills/", "_personas/"]:
        if not acl.get_entry(system_folder):
            print(f"Setting ACL for {system_folder}: read=all, write=all, manage=admin")
            acl.set_acl(ACLEntry(
                path=system_folder, owner="admin",
                read=["all"], write=["all"], manage=["admin"],
            ))

    # 3. Create personal space for dev user
    personal = "@donghae/"
    wiki_personal = wiki_dir / "@donghae"
    wiki_personal.mkdir(exist_ok=True)
    print(f"Created personal space: {personal}")

    print("\nMigration complete. Run full reindex to populate access_scope in ChromaDB:")
    print("  curl -X POST http://localhost:8001/api/wiki/reindex")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run migration**

Run: `cd /Users/donghae/workspace/ai/onTong && python scripts/migrate_acl.py`
Expected: ACL entries created for existing folders

- [ ] **Step 3: Trigger full reindex**

Run: `curl -X POST http://localhost:8001/api/wiki/reindex`
Expected: All documents re-indexed with access_read/access_write metadata

- [ ] **Step 4: Commit**

```bash
git add scripts/migrate_acl.py
git commit -m "feat: ACL migration script for existing wiki data"
```

---

## Task 15: 통합 검증

- [ ] **Step 1: Run full test suite**

```bash
cd /Users/donghae/workspace/ai/onTong
python -m pytest tests/ -v --tb=short
```

Expected: All existing tests + new tests pass.

- [ ] **Step 2: TypeScript build check**

```bash
cd /Users/donghae/workspace/ai/onTong/frontend && npx tsc --noEmit
```

Expected: No type errors.

- [ ] **Step 3: Manual E2E verification**

Start servers and verify:

```bash
# Backend
source venv/bin/activate && set -a && source .env && set +a
uvicorn backend.main:app --host 0.0.0.0 --port 8001

# Frontend
cd frontend && npm run dev
```

Verify:
1. `GET /api/auth/me` returns user with groups
2. `GET /api/groups` returns group list
3. `GET /api/wiki/tree` returns ACL-filtered tree
4. Search via AI copilot only returns accessible documents
5. Context menu shows permission-appropriate items
6. Share dialog opens and saves ACL
7. Properties panel shows correct owner/permission info

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: ACL-based domain scoping — complete integration"
```
