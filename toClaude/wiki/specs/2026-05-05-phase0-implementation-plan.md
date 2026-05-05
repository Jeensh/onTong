# Phase 0 — Infrastructure Abstraction & Backends Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish backend abstraction layer (Profile, Lock, EventBus, KV Store, MetadataIndex, TaskQueue) + Postgres + Arq so subsequent phases (P1~P6) can plug into multi-host enterprise topology without code rewrites.

**Architecture:** Each infrastructure dependency sits behind a `Protocol`. A central `Profile` resolver maps env vars (`ONTONG_PROFILE` + per-component overrides) to concrete backends. `dev` profile keeps current in-memory / file behavior; `team` switches to Redis + Postgres; `enterprise` is `team` + Elasticsearch readiness (ES wiring lands in P6). New Postgres tables (`wiki_references`, `wiki_versions`, `wiki_snapshots`, `wiki_audit`, `wiki_jobs`) created via Alembic. Arq workers split into `path-worker` + `content-worker` queues (Redis broker).

**Tech Stack:** Python 3.10+, FastAPI, asyncio, Pydantic v2, redis-py 5+, Postgres 15+, asyncpg, SQLAlchemy 2.x async, Alembic, Arq, pytest, pytest-asyncio, fakeredis (test), pytest-postgresql (test).

**Spec reference:** `toClaude/wiki/specs/2026-05-05-rename-concurrency-design.md` §13 Phase 0 (작업 0-1 ~ 0-9).

---

## File Structure

```
backend/
├── core/
│   ├── config.py                          # MODIFY: ONTONG_PROFILE, *_BACKEND env vars
│   ├── profile.py                         # NEW: Profile resolver (env → backend names)
│   └── backends.py                        # NEW: Backend factory (singletons)
│
├── infrastructure/
│   ├── events/
│   │   ├── event_bus.py                   # MODIFY: split into protocol + InProcess impl
│   │   ├── event_bus_inproc.py            # NEW: extracted in-process impl
│   │   └── event_bus_redis.py             # NEW: Redis Pub/Sub adapter
│   │
│   ├── locks/                             # NEW DIR (refactor from application/)
│   │   ├── __init__.py
│   │   ├── lock_protocol.py               # NEW: LockBackend Protocol
│   │   ├── memory.py                      # NEW: InMemory (move + small refactor)
│   │   └── redis.py                       # NEW: Redis (move + small refactor)
│   │
│   ├── kv/                                # NEW DIR
│   │   ├── __init__.py
│   │   ├── kv_protocol.py                 # NEW: KVStore Protocol
│   │   ├── memory.py                      # NEW
│   │   └── redis.py                       # NEW
│   │
│   ├── queue/                             # NEW DIR
│   │   ├── __init__.py
│   │   ├── task_queue_protocol.py         # NEW
│   │   ├── asyncio_queue.py               # NEW: dev profile
│   │   ├── arq_queue.py                   # NEW: team/enterprise profile
│   │   └── workers/
│   │       ├── __init__.py
│   │       ├── path_worker.py             # NEW: skeleton (real fns in P3+)
│   │       └── content_worker.py          # NEW: skeleton
│   │
│   └── db/                                # NEW DIR
│       ├── __init__.py
│       ├── engine.py                      # NEW: SQLAlchemy async engine
│       └── session.py                     # NEW: async session factory
│
├── application/
│   ├── lock_service.py                    # MODIFY: delegate to backends.get_lock_backend()
│   ├── metadata/
│   │   ├── metadata_index.py              # MODIFY: backend abstraction
│   │   └── backends/
│   │       ├── __init__.py
│   │       ├── metadata_protocol.py       # NEW
│   │       ├── json_file.py               # NEW: extracted current
│   │       └── redis_hash.py              # NEW
│   └── (rest unchanged)
│
├── api/
│   └── wiki.py                            # MODIFY: add /profile-status endpoint
│
└── cli/
    ├── __init__.py
    ├── __main__.py                        # NEW: ontong CLI entry
    ├── migrate.py                         # NEW: migrate subcommand framework
    └── reindex_metadata.py                # EXISTING (no change)

migrations/                                # NEW DIR (alembic)
├── alembic.ini
├── env.py
├── script.py.mako
└── versions/
    └── 2026_05_05_001_initial_schema.py   # 5 tables + 1 view

tests/
├── conftest.py                            # NEW: redis/postgres fixtures
├── test_profile.py                        # NEW
├── test_event_bus_redis.py                # NEW
├── test_lock_backend_integration.py       # NEW (extends existing lock tests)
├── test_kv_store.py                       # NEW
├── test_metadata_index_redis.py           # NEW
├── test_alembic_migration.py              # NEW
├── test_task_queue.py                     # NEW
├── test_profile_status_api.py             # NEW
└── test_cli_migrate.py                    # NEW

pyproject.toml                             # MODIFY: add deps
```

**Naming convention**: backend protocol files use `*_protocol.py`; concrete impls use the backend name (`memory.py`, `redis.py`).

---

## Task 1: Profile Resolver + Settings Extension

**Goal**: Centralized resolution from `ONTONG_PROFILE` + per-component env vars to backend names.

**Files:**
- Modify: `backend/core/config.py`
- Create: `backend/core/profile.py`
- Test: `tests/test_profile.py`

- [ ] **Step 1: Write failing test for profile resolver**

Create `tests/test_profile.py`:

```python
"""Profile resolver tests."""
from __future__ import annotations

import pytest
from backend.core.profile import Profile, resolve_profile


def test_dev_profile_defaults():
    p = resolve_profile(profile="dev", overrides={})
    assert p.lock_backend == "memory"
    assert p.event_bus_backend == "inproc"
    assert p.metadata_index_backend == "json_file"
    assert p.kv_backend == "memory"
    assert p.task_queue_backend == "asyncio"
    assert p.fulltext_backend == "bm25_inmem"


def test_team_profile_defaults():
    p = resolve_profile(profile="team", overrides={})
    assert p.lock_backend == "redis"
    assert p.event_bus_backend == "redis_pubsub"
    assert p.metadata_index_backend == "redis_hash"
    assert p.kv_backend == "redis"
    assert p.task_queue_backend == "arq"
    assert p.fulltext_backend == "bm25_inmem"  # ES is enterprise-only (P6)


def test_enterprise_profile_defaults():
    p = resolve_profile(profile="enterprise", overrides={})
    assert p.lock_backend == "redis"
    assert p.fulltext_backend == "elasticsearch"


def test_per_component_override():
    p = resolve_profile(
        profile="team",
        overrides={"ONTONG_LOCK_BACKEND": "memory"},
    )
    assert p.lock_backend == "memory"
    # Others stay at team default
    assert p.event_bus_backend == "redis_pubsub"


def test_invalid_profile_raises():
    with pytest.raises(ValueError, match="unknown profile"):
        resolve_profile(profile="bogus", overrides={})


def test_invalid_backend_value_raises():
    with pytest.raises(ValueError, match="invalid lock backend"):
        resolve_profile(
            profile="dev",
            overrides={"ONTONG_LOCK_BACKEND": "not_a_thing"},
        )
```

- [ ] **Step 2: Run test, expect ImportError / NameError**

```bash
.venv/bin/pytest tests/test_profile.py -v
```

Expected: collection error (`backend.core.profile` does not exist).

- [ ] **Step 3: Implement Profile resolver**

Create `backend/core/profile.py`:

```python
"""Profile resolver — maps env vars to concrete backend selection.

Profiles:
  dev:        InMemory + filesystem (single process, no external deps)
  team:       Redis + Postgres + Arq (single host, ≤100 concurrent users)
  enterprise: team + Elasticsearch ready (multi-host, ≤30K concurrent)
"""
from __future__ import annotations

from dataclasses import dataclass

VALID_PROFILES = {"dev", "team", "enterprise"}

VALID_BACKENDS = {
    "lock": {"memory", "redis"},
    "event_bus": {"inproc", "redis_pubsub"},
    "metadata_index": {"json_file", "redis_hash"},
    "kv": {"memory", "redis"},
    "task_queue": {"asyncio", "arq"},
    "fulltext": {"bm25_inmem", "pg_fts", "elasticsearch"},
}


@dataclass(frozen=True)
class Profile:
    name: str
    lock_backend: str
    event_bus_backend: str
    metadata_index_backend: str
    kv_backend: str
    task_queue_backend: str
    fulltext_backend: str


_DEFAULTS: dict[str, dict[str, str]] = {
    "dev": {
        "lock": "memory",
        "event_bus": "inproc",
        "metadata_index": "json_file",
        "kv": "memory",
        "task_queue": "asyncio",
        "fulltext": "bm25_inmem",
    },
    "team": {
        "lock": "redis",
        "event_bus": "redis_pubsub",
        "metadata_index": "redis_hash",
        "kv": "redis",
        "task_queue": "arq",
        "fulltext": "bm25_inmem",
    },
    "enterprise": {
        "lock": "redis",
        "event_bus": "redis_pubsub",
        "metadata_index": "redis_hash",
        "kv": "redis",
        "task_queue": "arq",
        "fulltext": "elasticsearch",
    },
}

_OVERRIDE_KEYS = {
    "lock": "ONTONG_LOCK_BACKEND",
    "event_bus": "ONTONG_EVENT_BUS_BACKEND",
    "metadata_index": "ONTONG_METADATA_INDEX_BACKEND",
    "kv": "ONTONG_KV_BACKEND",
    "task_queue": "ONTONG_TASK_QUEUE_BACKEND",
    "fulltext": "ONTONG_FULLTEXT_BACKEND",
}


def resolve_profile(profile: str, overrides: dict[str, str]) -> Profile:
    """Resolve a Profile from `ONTONG_PROFILE` + per-component env vars.

    Args:
        profile: dev | team | enterprise
        overrides: dict of env vars (typically os.environ-like). Component-specific
                   override keys take precedence over the profile's defaults.
    """
    if profile not in VALID_PROFILES:
        raise ValueError(f"unknown profile: {profile!r}, expected one of {VALID_PROFILES}")

    defaults = _DEFAULTS[profile]
    chosen: dict[str, str] = {}
    for component, default_value in defaults.items():
        env_key = _OVERRIDE_KEYS[component]
        value = overrides.get(env_key, default_value)
        if value not in VALID_BACKENDS[component]:
            raise ValueError(
                f"invalid {component} backend: {value!r}, "
                f"expected one of {VALID_BACKENDS[component]}"
            )
        chosen[component] = value

    return Profile(
        name=profile,
        lock_backend=chosen["lock"],
        event_bus_backend=chosen["event_bus"],
        metadata_index_backend=chosen["metadata_index"],
        kv_backend=chosen["kv"],
        task_queue_backend=chosen["task_queue"],
        fulltext_backend=chosen["fulltext"],
    )
```

- [ ] **Step 4: Run tests, expect PASS**

```bash
.venv/bin/pytest tests/test_profile.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Wire Profile into Settings**

Modify `backend/core/config.py` — add fields to the `Settings` class (after the `redis_url` line):

```python
    # ── Profile / Backend selection (Phase 0) ─────────────────────────
    ontong_profile: str = "dev"  # dev | team | enterprise

    # Per-component overrides (empty = use profile default)
    ontong_lock_backend: str = ""
    ontong_event_bus_backend: str = ""
    ontong_metadata_index_backend: str = ""
    ontong_kv_backend: str = ""
    ontong_task_queue_backend: str = ""
    ontong_fulltext_backend: str = ""

    # Postgres (team / enterprise)
    postgres_dsn: str = ""  # e.g. postgresql+asyncpg://user:pass@localhost:5432/ontong
```

Add a method to the same class (place after the field definitions, before any existing methods):

```python
    def resolve_profile(self):
        """Return resolved Profile (calls backend.core.profile.resolve_profile)."""
        from backend.core.profile import resolve_profile as _resolve

        overrides: dict[str, str] = {}
        for env_key, attr in [
            ("ONTONG_LOCK_BACKEND", "ontong_lock_backend"),
            ("ONTONG_EVENT_BUS_BACKEND", "ontong_event_bus_backend"),
            ("ONTONG_METADATA_INDEX_BACKEND", "ontong_metadata_index_backend"),
            ("ONTONG_KV_BACKEND", "ontong_kv_backend"),
            ("ONTONG_TASK_QUEUE_BACKEND", "ontong_task_queue_backend"),
            ("ONTONG_FULLTEXT_BACKEND", "ontong_fulltext_backend"),
        ]:
            val = getattr(self, attr)
            if val:
                overrides[env_key] = val
        return _resolve(self.ontong_profile, overrides)
```

- [ ] **Step 6: Verify settings still load**

```bash
.venv/bin/python -c "from backend.core.config import settings; p = settings.resolve_profile(); print(p)"
```

Expected: `Profile(name='dev', lock_backend='memory', ...)` printed without error.

- [ ] **Step 7: Commit**

```bash
git add backend/core/profile.py backend/core/config.py tests/test_profile.py
git commit -m "feat(infra): add Profile resolver for dev/team/enterprise backend selection"
```

---

## Task 2: Backend Factory + Lock Service Integration

**Goal**: Single source of truth (`backends.py`) returns concrete backend instances per Profile. Lock service delegates here.

**Files:**
- Create: `backend/core/backends.py`
- Create: `backend/infrastructure/locks/__init__.py`, `lock_protocol.py`, `memory.py`, `redis.py`
- Modify: `backend/application/lock_service.py`
- Test: `tests/test_lock_backend_integration.py`

- [ ] **Step 1: Add `redis` dependency**

```bash
poetry add 'redis>=5.0,<6.0'
poetry add --group dev 'fakeredis>=2.20'
```

Verify in `pyproject.toml`:

```toml
redis = "^5.0"
# ...
fakeredis = "^2.20"  # under [tool.poetry.group.dev.dependencies] or dev extras
```

- [ ] **Step 2: Write failing test for lock backend selection**

Create `tests/test_lock_backend_integration.py`:

```python
"""Lock backend integration with Profile."""
from __future__ import annotations

import pytest
from backend.core.profile import Profile
from backend.core.backends import get_lock_backend, _reset_for_test


@pytest.fixture(autouse=True)
def reset_backends():
    _reset_for_test()
    yield
    _reset_for_test()


def test_dev_profile_returns_inmemory_lock():
    p = Profile(
        name="dev", lock_backend="memory", event_bus_backend="inproc",
        metadata_index_backend="json_file", kv_backend="memory",
        task_queue_backend="asyncio", fulltext_backend="bm25_inmem",
    )
    backend = get_lock_backend(p)
    from backend.infrastructure.locks.memory import InMemoryLockBackend
    assert isinstance(backend, InMemoryLockBackend)


def test_team_profile_returns_redis_lock(monkeypatch):
    import fakeredis
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(
        "backend.infrastructure.locks.redis._build_client",
        lambda url: fake,
    )
    p = Profile(
        name="team", lock_backend="redis", event_bus_backend="redis_pubsub",
        metadata_index_backend="redis_hash", kv_backend="redis",
        task_queue_backend="arq", fulltext_backend="bm25_inmem",
    )
    backend = get_lock_backend(p, redis_url="redis://fake")
    from backend.infrastructure.locks.redis import RedisLockBackend
    assert isinstance(backend, RedisLockBackend)


def test_acquire_release_via_factory():
    p = Profile(
        name="dev", lock_backend="memory", event_bus_backend="inproc",
        metadata_index_backend="json_file", kv_backend="memory",
        task_queue_backend="asyncio", fulltext_backend="bm25_inmem",
    )
    backend = get_lock_backend(p)
    lock = backend.acquire("test/path", "alice", ttl=5)
    assert lock is not None
    assert lock.user == "alice"
    assert backend.release("test/path", "alice") is True
```

- [ ] **Step 3: Run test, expect ImportError**

```bash
.venv/bin/pytest tests/test_lock_backend_integration.py -v
```

Expected: collection error.

- [ ] **Step 4: Create lock package + extract existing impls**

Create `backend/infrastructure/locks/__init__.py` (empty file is fine).

Create `backend/infrastructure/locks/lock_protocol.py`:

```python
"""LockBackend protocol — moved from application/lock_service.py."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

DEFAULT_TTL = 300


@dataclass
class LockInfo:
    path: str
    user: str
    acquired_at: float = field(default_factory=time.time)
    ttl: int = DEFAULT_TTL

    @property
    def is_expired(self) -> bool:
        return time.time() - self.acquired_at > self.ttl

    @property
    def remaining(self) -> int:
        r = self.ttl - (time.time() - self.acquired_at)
        return max(0, int(r))

    def refresh(self) -> None:
        self.acquired_at = time.time()

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "user": self.user,
            "acquired_at": self.acquired_at,
            "ttl": self.ttl,
            "remaining": self.remaining,
            "is_expired": self.is_expired,
        }


class LockBackend(ABC):
    @abstractmethod
    def acquire(self, path: str, user: str, ttl: int) -> LockInfo | None: ...

    @abstractmethod
    def release(self, path: str, user: str) -> bool: ...

    @abstractmethod
    def status(self, path: str) -> LockInfo | None: ...

    @abstractmethod
    def refresh(self, path: str, user: str) -> bool: ...

    @abstractmethod
    def release_all_by_user(self, user: str) -> int: ...

    def batch_refresh(self, paths: list[str], user: str) -> int:
        count = 0
        for p in paths:
            if self.refresh(p, user):
                count += 1
        return count
```

Create `backend/infrastructure/locks/memory.py` (copy `InMemoryLockBackend` from current `application/lock_service.py`, change import to use the new protocol):

```python
"""In-memory lock backend (single process)."""
from __future__ import annotations

import logging
from .lock_protocol import LockBackend, LockInfo, DEFAULT_TTL

logger = logging.getLogger(__name__)


class InMemoryLockBackend(LockBackend):
    def __init__(self) -> None:
        self._locks: dict[str, LockInfo] = {}

    def acquire(self, path: str, user: str, ttl: int = DEFAULT_TTL) -> LockInfo | None:
        self._cleanup_expired()
        existing = self._locks.get(path)
        if existing and not existing.is_expired:
            if existing.user == user:
                existing.refresh()
                return existing
            return None
        lock = LockInfo(path=path, user=user, ttl=ttl)
        self._locks[path] = lock
        logger.info(f"Lock acquired: {path} by {user}")
        return lock

    def release(self, path: str, user: str) -> bool:
        existing = self._locks.get(path)
        if not existing:
            return True
        if existing.user != user and not existing.is_expired:
            return False
        del self._locks[path]
        logger.info(f"Lock released: {path} by {user}")
        return True

    def status(self, path: str) -> LockInfo | None:
        self._cleanup_expired()
        lock = self._locks.get(path)
        if lock and lock.is_expired:
            del self._locks[path]
            return None
        return lock

    def refresh(self, path: str, user: str) -> bool:
        lock = self._locks.get(path)
        if not lock or lock.is_expired:
            return False
        if lock.user != user:
            return False
        lock.refresh()
        return True

    def release_all_by_user(self, user: str) -> int:
        to_remove = [p for p, l in self._locks.items() if l.user == user]
        for path in to_remove:
            del self._locks[path]
        if to_remove:
            logger.info(f"Released {len(to_remove)} locks for user {user}")
        return len(to_remove)

    def _cleanup_expired(self) -> None:
        expired = [p for p, l in self._locks.items() if l.is_expired]
        for path in expired:
            logger.info(f"Lock expired: {path} (was held by {self._locks[path].user})")
            del self._locks[path]
```

Create `backend/infrastructure/locks/redis.py`:

```python
"""Redis lock backend."""
from __future__ import annotations

import json
import logging
import time
from .lock_protocol import LockBackend, LockInfo, DEFAULT_TTL

logger = logging.getLogger(__name__)


def _build_client(url: str):
    """Factory function — monkey-patchable in tests."""
    import redis
    return redis.from_url(url, decode_responses=True)


class RedisLockBackend(LockBackend):
    KEY_PREFIX = "ontong:lock:"
    USER_INDEX_PREFIX = "ontong:user_locks:"

    def __init__(self, redis_url: str) -> None:
        self._redis = _build_client(redis_url)
        logger.info(f"Redis lock backend connected: {redis_url}")

    def _key(self, path: str) -> str:
        return f"{self.KEY_PREFIX}{path}"

    def acquire(self, path: str, user: str, ttl: int = DEFAULT_TTL) -> LockInfo | None:
        key = self._key(path)
        now = time.time()
        lock_data = json.dumps({"user": user, "acquired_at": now, "ttl": ttl})

        if self._redis.set(key, lock_data, nx=True, ex=ttl):
            self._redis.sadd(f"{self.USER_INDEX_PREFIX}{user}", path)
            logger.info(f"Lock acquired (Redis): {path} by {user}")
            return LockInfo(path=path, user=user, acquired_at=now, ttl=ttl)

        existing_raw = self._redis.get(key)
        if not existing_raw:
            if self._redis.set(key, lock_data, nx=True, ex=ttl):
                self._redis.sadd(f"{self.USER_INDEX_PREFIX}{user}", path)
                return LockInfo(path=path, user=user, acquired_at=now, ttl=ttl)
            return None

        existing = json.loads(existing_raw)
        if existing["user"] == user:
            self._redis.set(key, lock_data, ex=ttl)
            return LockInfo(path=path, user=user, acquired_at=now, ttl=ttl)

        return None

    def release(self, path: str, user: str) -> bool:
        key = self._key(path)
        existing_raw = self._redis.get(key)
        if not existing_raw:
            return True
        existing = json.loads(existing_raw)
        if existing["user"] != user:
            return False
        self._redis.delete(key)
        self._redis.srem(f"{self.USER_INDEX_PREFIX}{user}", path)
        logger.info(f"Lock released (Redis): {path} by {user}")
        return True

    def status(self, path: str) -> LockInfo | None:
        raw = self._redis.get(self._key(path))
        if not raw:
            return None
        data = json.loads(raw)
        return LockInfo(
            path=path, user=data["user"],
            acquired_at=data["acquired_at"], ttl=data["ttl"],
        )

    def refresh(self, path: str, user: str) -> bool:
        key = self._key(path)
        raw = self._redis.get(key)
        if not raw:
            return False
        data = json.loads(raw)
        if data["user"] != user:
            return False
        now = time.time()
        ttl = data["ttl"]
        new_data = json.dumps({"user": user, "acquired_at": now, "ttl": ttl})
        self._redis.set(key, new_data, ex=ttl)
        return True

    def release_all_by_user(self, user: str) -> int:
        index_key = f"{self.USER_INDEX_PREFIX}{user}"
        paths = self._redis.smembers(index_key)
        count = 0
        for path in paths:
            key = self._key(path)
            raw = self._redis.get(key)
            if raw:
                data = json.loads(raw)
                if data["user"] == user:
                    self._redis.delete(key)
                    count += 1
        self._redis.delete(index_key)
        if count:
            logger.info(f"Released {count} locks for user {user} (Redis)")
        return count

    def batch_refresh(self, paths: list[str], user: str) -> int:
        pipe = self._redis.pipeline()
        for path in paths:
            pipe.get(self._key(path))
        results = pipe.execute()

        now = time.time()
        refresh_pipe = self._redis.pipeline()
        count = 0
        for path, raw in zip(paths, results):
            if not raw:
                continue
            data = json.loads(raw)
            if data["user"] != user:
                continue
            ttl = data["ttl"]
            new_data = json.dumps({"user": user, "acquired_at": now, "ttl": ttl})
            refresh_pipe.set(self._key(path), new_data, ex=ttl)
            count += 1
        if count:
            refresh_pipe.execute()
        return count
```

- [ ] **Step 5: Implement backend factory**

Create `backend/core/backends.py`:

```python
"""Singleton factory for infrastructure backends. Resolved once per process."""
from __future__ import annotations

import logging
from typing import Any

from backend.core.profile import Profile

logger = logging.getLogger(__name__)

_singletons: dict[str, Any] = {}


def _reset_for_test() -> None:
    """Clear cached backends — test-only helper."""
    _singletons.clear()


def get_lock_backend(profile: Profile, *, redis_url: str = ""):
    """Return a LockBackend matching the profile."""
    if "lock" in _singletons:
        return _singletons["lock"]

    if profile.lock_backend == "memory":
        from backend.infrastructure.locks.memory import InMemoryLockBackend
        backend = InMemoryLockBackend()
    elif profile.lock_backend == "redis":
        from backend.infrastructure.locks.redis import RedisLockBackend
        if not redis_url:
            raise RuntimeError("redis_url required for Redis lock backend")
        backend = RedisLockBackend(redis_url)
    else:
        raise ValueError(f"unknown lock backend: {profile.lock_backend}")

    _singletons["lock"] = backend
    logger.info(f"Lock backend initialized: {profile.lock_backend}")
    return backend
```

- [ ] **Step 6: Refactor LockService to use backend factory**

Modify `backend/application/lock_service.py` — replace the bottom of the file (everything from `class LockService:` to end) with:

```python
class LockService:
    """Lock service facade — delegates to backend selected by Profile."""

    def __init__(self, backend=None) -> None:
        if backend is None:
            from backend.core.config import settings
            from backend.core.backends import get_lock_backend
            profile = settings.resolve_profile()
            backend = get_lock_backend(profile, redis_url=settings.redis_url)
        self._backend = backend

    def acquire(self, path: str, user: str, ttl: int = 300):
        return self._backend.acquire(path, user, ttl)

    def release(self, path: str, user: str) -> bool:
        return self._backend.release(path, user)

    def status(self, path: str):
        return self._backend.status(path)

    def refresh(self, path: str, user: str) -> bool:
        return self._backend.refresh(path, user)

    def release_all_by_user(self, user: str) -> int:
        return self._backend.release_all_by_user(user)

    def batch_refresh(self, paths: list[str], user: str) -> int:
        return self._backend.batch_refresh(paths, user)


_lock_service: LockService | None = None


def get_lock_service() -> LockService:
    global _lock_service
    if _lock_service is None:
        _lock_service = LockService()
    return _lock_service
```

Also remove the now-duplicate `InMemoryLockBackend` and `RedisLockBackend` classes from `lock_service.py` — keep only the imports they use that are now needed (`from .infrastructure.locks.lock_protocol import LockInfo, LockBackend` if any consumer of `lock_service.py` imports `LockInfo`). Update the top of the file:

```python
"""Document lock service — facade over LockBackend.

Backend selection is driven by ONTONG_PROFILE / ONTONG_LOCK_BACKEND.
See backend.infrastructure.locks for concrete implementations.
"""
from __future__ import annotations

import logging
from backend.infrastructure.locks.lock_protocol import LockInfo, LockBackend, DEFAULT_TTL

logger = logging.getLogger(__name__)
```

- [ ] **Step 7: Run tests, expect PASS**

```bash
.venv/bin/pytest tests/test_lock_backend_integration.py tests/test_profile.py -v
```

Expected: 8 passed. Also run full lock-related regression:

```bash
.venv/bin/pytest tests/ -k "lock" -v
```

Expected: existing lock tests still pass.

- [ ] **Step 8: Commit**

```bash
git add backend/core/backends.py backend/infrastructure/locks/ backend/application/lock_service.py tests/test_lock_backend_integration.py pyproject.toml poetry.lock
git commit -m "feat(infra): extract lock backends + add factory bound to Profile"
```

---

## Task 3: EventBus Redis Pub/Sub

**Goal**: Cross-process SSE fan-out. Same `event_bus.publish(...)` API; backend toggle via Profile.

**Files:**
- Modify: `backend/infrastructure/events/event_bus.py`
- Create: `backend/infrastructure/events/event_bus_inproc.py`
- Create: `backend/infrastructure/events/event_bus_redis.py`
- Modify: `backend/core/backends.py` (add `get_event_bus`)
- Test: `tests/test_event_bus_redis.py`

- [ ] **Step 1: Write failing test for cross-process Redis pub/sub**

Create `tests/test_event_bus_redis.py`:

```python
"""Redis Pub/Sub event bus tests."""
from __future__ import annotations

import asyncio
import pytest

import fakeredis.aioredis as fake_async


@pytest.mark.asyncio
async def test_publish_subscribe_round_trip(monkeypatch):
    fake = fake_async.FakeRedis(decode_responses=True)
    monkeypatch.setattr(
        "backend.infrastructure.events.event_bus_redis._build_async_client",
        lambda url: fake,
    )

    from backend.infrastructure.events.event_bus_redis import RedisEventBus

    bus = RedisEventBus(redis_url="redis://fake")
    await bus.start()

    received: list[dict] = []

    async def collect():
        async for ev in bus.subscribe():
            received.append({"type": ev.type, "data": ev.data})
            if len(received) >= 1:
                break

    task = asyncio.create_task(collect())
    await asyncio.sleep(0.05)  # subscriber ready
    bus.publish("tree_change", {"path": "foo.md"})
    await asyncio.wait_for(task, timeout=2.0)

    assert received == [{"type": "tree_change", "data": {"path": "foo.md"}}]
    await bus.stop()


@pytest.mark.asyncio
async def test_callbacks_run_inline_for_publisher(monkeypatch):
    fake = fake_async.FakeRedis(decode_responses=True)
    monkeypatch.setattr(
        "backend.infrastructure.events.event_bus_redis._build_async_client",
        lambda url: fake,
    )
    from backend.infrastructure.events.event_bus_redis import RedisEventBus

    bus = RedisEventBus(redis_url="redis://fake")
    await bus.start()

    seen: list[dict] = []
    bus.on("index_status", lambda d: seen.append(d))
    bus.publish("index_status", {"path": "x", "action": "done"})

    assert seen == [{"path": "x", "action": "done"}]
    await bus.stop()
```

- [ ] **Step 2: Run test, expect ImportError**

```bash
.venv/bin/pytest tests/test_event_bus_redis.py -v
```

Expected: collection error.

- [ ] **Step 3: Extract InProcess EventBus from existing file**

Create `backend/infrastructure/events/event_bus_inproc.py` by moving the existing `EventBus` class body from `event_bus.py`:

```python
"""In-process EventBus — original implementation, single Python process only."""
from __future__ import annotations

import asyncio
import inspect
import logging
from typing import AsyncGenerator

from .event_bus import Event  # Event dataclass stays in event_bus.py

logger = logging.getLogger(__name__)


class InProcessEventBus:
    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[Event]] = []
        self._callbacks: dict[str, list] = {}

    async def start(self) -> None: ...
    async def stop(self) -> None: ...

    def on(self, event_type: str, callback) -> None:
        self._callbacks.setdefault(event_type, []).append(callback)

    def publish(self, event_type: str, data: dict) -> None:
        event = Event(type=event_type, data=data)
        for cb in self._callbacks.get(event_type, []):
            if inspect.iscoroutinefunction(cb):
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(cb(data))
                except RuntimeError:
                    pass
            else:
                try:
                    cb(data)
                except Exception as e:
                    logger.warning("Event callback error for %s: %s", event_type, e)

        dead: list[asyncio.Queue] = []
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._subscribers.remove(q)

    async def subscribe(self) -> AsyncGenerator[Event, None]:
        q: asyncio.Queue[Event] = asyncio.Queue(maxsize=256)
        self._subscribers.append(q)
        try:
            while True:
                event = await q.get()
                yield event
        finally:
            if q in self._subscribers:
                self._subscribers.remove(q)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)
```

- [ ] **Step 4: Implement Redis EventBus**

Create `backend/infrastructure/events/event_bus_redis.py`:

```python
"""Redis Pub/Sub-backed EventBus for multi-host SSE fan-out."""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
from typing import AsyncGenerator

from .event_bus import Event

logger = logging.getLogger(__name__)

CHANNEL = "ontong:events"


def _build_async_client(url: str):
    """Factory function — monkey-patchable in tests."""
    import redis.asyncio as aioredis
    return aioredis.from_url(url, decode_responses=True)


class RedisEventBus:
    def __init__(self, redis_url: str) -> None:
        self._url = redis_url
        self._redis = _build_async_client(redis_url)
        self._pubsub = None
        self._listener_task: asyncio.Task | None = None
        self._subscribers: list[asyncio.Queue[Event]] = []
        self._callbacks: dict[str, list] = {}

    async def start(self) -> None:
        if self._listener_task is not None:
            return
        self._pubsub = self._redis.pubsub()
        await self._pubsub.subscribe(CHANNEL)
        self._listener_task = asyncio.create_task(self._listen())

    async def stop(self) -> None:
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None
        if self._pubsub:
            await self._pubsub.unsubscribe(CHANNEL)
            await self._pubsub.aclose()
            self._pubsub = None
        await self._redis.aclose()

    async def _listen(self) -> None:
        try:
            async for msg in self._pubsub.listen():
                if msg.get("type") != "message":
                    continue
                try:
                    payload = json.loads(msg["data"])
                except (json.JSONDecodeError, KeyError):
                    continue
                event = Event(type=payload["type"], data=payload["data"])
                self._fanout_to_local(event)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Redis pubsub listener crashed: {e}")

    def _fanout_to_local(self, event: Event) -> None:
        dead: list[asyncio.Queue] = []
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._subscribers.remove(q)

    def on(self, event_type: str, callback) -> None:
        self._callbacks.setdefault(event_type, []).append(callback)

    def publish(self, event_type: str, data: dict) -> None:
        # 1. Run local callbacks inline (cache invalidation etc)
        for cb in self._callbacks.get(event_type, []):
            if inspect.iscoroutinefunction(cb):
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(cb(data))
                except RuntimeError:
                    pass
            else:
                try:
                    cb(data)
                except Exception as e:
                    logger.warning("Event callback error for %s: %s", event_type, e)

        # 2. Publish to Redis (fan-out across hosts)
        payload = json.dumps({"type": event_type, "data": data}, ensure_ascii=False)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._redis.publish(CHANNEL, payload))
        except RuntimeError:
            asyncio.run(self._redis.publish(CHANNEL, payload))

    async def subscribe(self) -> AsyncGenerator[Event, None]:
        q: asyncio.Queue[Event] = asyncio.Queue(maxsize=256)
        self._subscribers.append(q)
        try:
            while True:
                event = await q.get()
                yield event
        finally:
            if q in self._subscribers:
                self._subscribers.remove(q)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)
```

- [ ] **Step 5: Refactor `event_bus.py` to keep only `Event` + module-level singleton wired via factory**

Modify `backend/infrastructure/events/event_bus.py`:

```python
"""SSE event bus.

The concrete implementation is selected by Profile (see backend.core.backends).
Module-level `event_bus` singleton is initialized on first access.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field


@dataclass
class Event:
    type: str
    data: dict
    timestamp: float = field(default_factory=time.time)

    def to_sse(self) -> str:
        payload = json.dumps(self.data, ensure_ascii=False)
        return f"event: {self.type}\ndata: {payload}\n\n"


class _EventBusProxy:
    """Lazy proxy — resolves backend on first call."""
    def __init__(self) -> None:
        self._impl = None

    def _get(self):
        if self._impl is None:
            from backend.core.config import settings
            from backend.core.backends import get_event_bus
            self._impl = get_event_bus(settings.resolve_profile(), redis_url=settings.redis_url)
        return self._impl

    def __getattr__(self, name):
        return getattr(self._get(), name)


event_bus = _EventBusProxy()
```

- [ ] **Step 6: Add `get_event_bus` to factory**

Append to `backend/core/backends.py`:

```python
def get_event_bus(profile: Profile, *, redis_url: str = ""):
    """Return an EventBus matching the profile."""
    if "event_bus" in _singletons:
        return _singletons["event_bus"]

    if profile.event_bus_backend == "inproc":
        from backend.infrastructure.events.event_bus_inproc import InProcessEventBus
        bus = InProcessEventBus()
    elif profile.event_bus_backend == "redis_pubsub":
        from backend.infrastructure.events.event_bus_redis import RedisEventBus
        if not redis_url:
            raise RuntimeError("redis_url required for redis_pubsub event bus")
        bus = RedisEventBus(redis_url)
    else:
        raise ValueError(f"unknown event bus backend: {profile.event_bus_backend}")

    _singletons["event_bus"] = bus
    logger.info(f"EventBus backend initialized: {profile.event_bus_backend}")
    return bus
```

- [ ] **Step 7: Wire `start()` into FastAPI lifespan**

Modify `backend/main.py` — find the `@asynccontextmanager async def lifespan(app)` block (or `@app.on_event("startup")` / `shutdown`) and add:

```python
    # Existing init ...
    from backend.infrastructure.events.event_bus import event_bus
    await event_bus.start()
    yield
    await event_bus.stop()
```

If no lifespan exists yet, add one:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    from backend.infrastructure.events.event_bus import event_bus
    await event_bus.start()
    yield
    await event_bus.stop()

app = FastAPI(lifespan=lifespan)
```

- [ ] **Step 8: Run tests, expect PASS**

```bash
.venv/bin/pytest tests/test_event_bus_redis.py -v
```

Expected: 2 passed.

Also run regression:

```bash
.venv/bin/pytest tests/ -k "event_bus or sse" -v
```

- [ ] **Step 9: Commit**

```bash
git add backend/infrastructure/events/ backend/core/backends.py backend/main.py tests/test_event_bus_redis.py
git commit -m "feat(infra): redis pub/sub event bus + lazy proxy + lifespan hook"
```

---

## Task 4: KV Store (FileHashStore + IndexStatus migration)

**Goal**: Generic `KVStore` protocol with memory + Redis backends. Migrate `FileHashStore` and `IndexStatus._pending` to use it.

**Files:**
- Create: `backend/infrastructure/kv/__init__.py`, `kv_protocol.py`, `memory.py`, `redis.py`
- Modify: `backend/infrastructure/storage/file_hash.py`
- Modify: `backend/application/wiki/wiki_service.py` (IndexStatus)
- Modify: `backend/core/backends.py` (`get_kv_store`)
- Test: `tests/test_kv_store.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_kv_store.py`:

```python
"""KVStore tests — both memory and Redis backends behave identically."""
from __future__ import annotations

import pytest


def _build_memory():
    from backend.infrastructure.kv.memory import MemoryKVStore
    return MemoryKVStore()


def _build_redis(monkeypatch):
    import fakeredis
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(
        "backend.infrastructure.kv.redis._build_client",
        lambda url: fake,
    )
    from backend.infrastructure.kv.redis import RedisKVStore
    return RedisKVStore(redis_url="redis://fake", namespace="test")


@pytest.fixture(params=["memory", "redis"])
def kv(request, monkeypatch):
    if request.param == "memory":
        return _build_memory()
    return _build_redis(monkeypatch)


def test_set_get(kv):
    kv.set("a", "1")
    assert kv.get("a") == "1"


def test_get_missing_returns_none(kv):
    assert kv.get("nope") is None


def test_delete(kv):
    kv.set("a", "1")
    kv.delete("a")
    assert kv.get("a") is None


def test_keys_with_prefix(kv):
    kv.set("foo:1", "a")
    kv.set("foo:2", "b")
    kv.set("bar:1", "c")
    assert sorted(kv.keys(prefix="foo:")) == ["foo:1", "foo:2"]


def test_clear(kv):
    kv.set("a", "1")
    kv.set("b", "2")
    kv.clear()
    assert kv.get("a") is None
    assert kv.get("b") is None
```

- [ ] **Step 2: Run, expect ImportError**

```bash
.venv/bin/pytest tests/test_kv_store.py -v
```

- [ ] **Step 3: Implement protocol + backends**

Create `backend/infrastructure/kv/__init__.py` (empty).

Create `backend/infrastructure/kv/kv_protocol.py`:

```python
"""KVStore protocol — simple string KV with prefix scan."""
from __future__ import annotations

from abc import ABC, abstractmethod


class KVStore(ABC):
    @abstractmethod
    def get(self, key: str) -> str | None: ...

    @abstractmethod
    def set(self, key: str, value: str) -> None: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def keys(self, prefix: str) -> list[str]: ...

    @abstractmethod
    def clear(self) -> None: ...
```

Create `backend/infrastructure/kv/memory.py`:

```python
"""In-memory KV store — single process only."""
from __future__ import annotations

from threading import RLock
from .kv_protocol import KVStore


class MemoryKVStore(KVStore):
    def __init__(self) -> None:
        self._d: dict[str, str] = {}
        self._lock = RLock()

    def get(self, key: str) -> str | None:
        with self._lock:
            return self._d.get(key)

    def set(self, key: str, value: str) -> None:
        with self._lock:
            self._d[key] = value

    def delete(self, key: str) -> None:
        with self._lock:
            self._d.pop(key, None)

    def keys(self, prefix: str) -> list[str]:
        with self._lock:
            return [k for k in self._d if k.startswith(prefix)]

    def clear(self) -> None:
        with self._lock:
            self._d.clear()
```

Create `backend/infrastructure/kv/redis.py`:

```python
"""Redis KV store with namespace prefix."""
from __future__ import annotations

from .kv_protocol import KVStore


def _build_client(url: str):
    """Factory — monkey-patchable in tests."""
    import redis
    return redis.from_url(url, decode_responses=True)


class RedisKVStore(KVStore):
    def __init__(self, redis_url: str, namespace: str) -> None:
        self._r = _build_client(redis_url)
        self._ns = f"ontong:kv:{namespace}:"

    def _key(self, key: str) -> str:
        return f"{self._ns}{key}"

    def get(self, key: str) -> str | None:
        return self._r.get(self._key(key))

    def set(self, key: str, value: str) -> None:
        self._r.set(self._key(key), value)

    def delete(self, key: str) -> None:
        self._r.delete(self._key(key))

    def keys(self, prefix: str) -> list[str]:
        full_prefix = self._key(prefix)
        ns_len = len(self._ns)
        return [k[ns_len:] for k in self._r.scan_iter(match=f"{full_prefix}*")]

    def clear(self) -> None:
        for k in list(self._r.scan_iter(match=f"{self._ns}*")):
            self._r.delete(k)
```

- [ ] **Step 4: Add `get_kv_store` to factory**

Append to `backend/core/backends.py`:

```python
def get_kv_store(profile: Profile, namespace: str, *, redis_url: str = ""):
    """Return a KVStore for the given namespace (e.g. 'hash', 'pending')."""
    cache_key = f"kv:{namespace}"
    if cache_key in _singletons:
        return _singletons[cache_key]

    if profile.kv_backend == "memory":
        from backend.infrastructure.kv.memory import MemoryKVStore
        store = MemoryKVStore()
    elif profile.kv_backend == "redis":
        from backend.infrastructure.kv.redis import RedisKVStore
        if not redis_url:
            raise RuntimeError("redis_url required for Redis KV store")
        store = RedisKVStore(redis_url, namespace=namespace)
    else:
        raise ValueError(f"unknown kv backend: {profile.kv_backend}")

    _singletons[cache_key] = store
    return store
```

- [ ] **Step 5: Migrate FileHashStore to KVStore**

Replace the body of `backend/infrastructure/storage/file_hash.py` (read it first to confirm structure, then) with:

```python
"""File content hash store — backed by KVStore."""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class FileHashStore:
    """Tracks per-file content hash to detect unchanged content during reindex.

    Backed by KVStore so it survives multi-worker / multi-host deployments.
    The `path` argument to `__init__` is retained for backward compat (legacy
    file-based callsites) but ignored when KV backend is 'redis'.
    """

    def __init__(self, path: Path | None = None) -> None:
        from backend.core.config import settings
        from backend.core.backends import get_kv_store
        profile = settings.resolve_profile()
        self._kv = get_kv_store(profile, namespace="hash", redis_url=settings.redis_url)
        # Legacy migration: load existing JSON file into KV on first init
        if path and path.exists() and profile.kv_backend == "memory":
            try:
                import json
                data = json.loads(path.read_text(encoding="utf-8"))
                for k, v in data.items():
                    if self._kv.get(k) is None:
                        self._kv.set(k, v)
            except Exception as e:
                logger.warning(f"Legacy hash file load failed: {e}")

    def has_changed(self, file_path: str, content: str) -> bool:
        new_hash = _hash(content)
        old_hash = self._kv.get(file_path)
        return old_hash != new_hash

    def update(self, file_path: str, content: str) -> None:
        self._kv.set(file_path, _hash(content))

    def remove(self, file_path: str) -> None:
        self._kv.delete(file_path)

    def clear(self) -> None:
        self._kv.clear()
```

- [ ] **Step 6: Migrate IndexStatus to KVStore**

Modify `backend/application/wiki/wiki_service.py` — replace the existing `IndexStatus` class with:

```python
class IndexStatus:
    """Track indexing status for files. Backed by KVStore (multi-worker safe)."""

    NAMESPACE = "pending"

    def __init__(self) -> None:
        from backend.core.config import settings
        from backend.core.backends import get_kv_store
        profile = settings.resolve_profile()
        self._kv = get_kv_store(profile, namespace=self.NAMESPACE, redis_url=settings.redis_url)

    def mark_pending(self, path: str) -> None:
        self._kv.set(path, str(time.time()))

    def mark_done(self, path: str) -> None:
        self._kv.delete(path)

    def is_pending(self, path: str) -> bool:
        return self._kv.get(path) is not None

    def get_pending(self) -> dict[str, float]:
        return {k: float(self._kv.get(k) or "0") for k in self._kv.keys(prefix="")}

    def pending_count(self) -> int:
        return len(self._kv.keys(prefix=""))
```

- [ ] **Step 7: Run tests**

```bash
.venv/bin/pytest tests/test_kv_store.py tests/ -k "file_hash or index_status" -v
```

Expected: kv tests pass; existing file_hash / index_status tests still pass.

- [ ] **Step 8: Commit**

```bash
git add backend/infrastructure/kv/ backend/core/backends.py backend/infrastructure/storage/file_hash.py backend/application/wiki/wiki_service.py tests/test_kv_store.py
git commit -m "feat(infra): KVStore protocol + migrate FileHashStore/IndexStatus"
```

---

## Task 5: MetadataIndex Redis Hash Backend

**Goal**: Replace per-process JSON file cache with Redis hash + Pub/Sub invalidation. Single source of truth across workers.

**Files:**
- Create: `backend/application/metadata/backends/__init__.py`, `metadata_protocol.py`, `json_file.py`, `redis_hash.py`
- Modify: `backend/application/metadata/metadata_index.py`
- Modify: `backend/core/backends.py` (`get_metadata_index`)
- Test: `tests/test_metadata_index_redis.py`

- [ ] **Step 1: Write failing test for Redis hash backend**

Create `tests/test_metadata_index_redis.py`:

```python
"""MetadataIndex backend equivalence tests."""
from __future__ import annotations

import pytest


def _build_json_file(tmp_path):
    from backend.application.metadata.backends.json_file import JsonFileBackend
    return JsonFileBackend(tmp_path / "metadata_index.json")


def _build_redis(monkeypatch):
    import fakeredis
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(
        "backend.application.metadata.backends.redis_hash._build_client",
        lambda url: fake,
    )
    from backend.application.metadata.backends.redis_hash import RedisHashBackend
    return RedisHashBackend(redis_url="redis://fake")


@pytest.fixture(params=["json_file", "redis"])
def backend(request, tmp_path, monkeypatch):
    if request.param == "json_file":
        return _build_json_file(tmp_path)
    return _build_redis(monkeypatch)


def test_save_load_round_trip(backend):
    data = {
        "files": {"a.md": {"domain": "ops", "tags": ["x"]}},
        "tags": {"x": 1},
    }
    backend.save(data)
    loaded = backend.load()
    assert loaded == data


def test_load_empty_returns_default(backend):
    loaded = backend.load()
    # Both backends return the empty default shape
    assert loaded.get("files") == {}
```

- [ ] **Step 2: Run, expect ImportError**

```bash
.venv/bin/pytest tests/test_metadata_index_redis.py -v
```

- [ ] **Step 3: Implement protocol + JSON backend (extracted)**

Create `backend/application/metadata/backends/__init__.py` (empty).

Create `backend/application/metadata/backends/metadata_protocol.py`:

```python
"""MetadataIndex backend protocol — opaque dict load/save."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


_EMPTY = {
    "domains": {}, "domain_processes": {}, "tags": {}, "untagged": [],
    "files": {}, "domain_files": {}, "process_files": {}, "tag_files": {},
    "status_files": {}, "supersedes_index": {}, "related_index": {},
}


def empty_default() -> dict[str, Any]:
    return {k: (dict(v) if isinstance(v, dict) else list(v)) for k, v in _EMPTY.items()}


class MetadataBackend(ABC):
    @abstractmethod
    def load(self) -> dict[str, Any]: ...

    @abstractmethod
    def save(self, data: dict[str, Any]) -> None: ...
```

Create `backend/application/metadata/backends/json_file.py`:

```python
"""JSON file backend — original behavior."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .metadata_protocol import MetadataBackend, empty_default

logger = logging.getLogger(__name__)


class JsonFileBackend(MetadataBackend):
    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._cache: dict[str, Any] | None = None

    def load(self) -> dict[str, Any]:
        if self._cache is not None:
            return self._cache
        if self._path.exists():
            try:
                self._cache = json.loads(self._path.read_text(encoding="utf-8"))
                return self._cache
            except Exception as e:
                logger.warning(f"Failed to load metadata index: {e}")
        self._cache = empty_default()
        return self._cache

    def save(self, data: dict[str, Any]) -> None:
        self._cache = data
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to save metadata index: {e}")
```

Create `backend/application/metadata/backends/redis_hash.py`:

```python
"""Redis-backed metadata index — single hash key for the entire blob.

Uses a single Redis key holding the JSON blob (same shape as the JSON file).
For 100K files this is ~10-20MB; well within Redis limits and atomic for
single-key reads/writes. If size becomes an issue, this can be sharded later
(e.g. one hash per file).
"""
from __future__ import annotations

import json
import logging
from typing import Any

from .metadata_protocol import MetadataBackend, empty_default

logger = logging.getLogger(__name__)

KEY = "ontong:metadata_index"


def _build_client(url: str):
    import redis
    return redis.from_url(url, decode_responses=True)


class RedisHashBackend(MetadataBackend):
    def __init__(self, redis_url: str) -> None:
        self._r = _build_client(redis_url)

    def load(self) -> dict[str, Any]:
        raw = self._r.get(KEY)
        if not raw:
            return empty_default()
        try:
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"Corrupt metadata index in Redis, returning empty: {e}")
            return empty_default()

    def save(self, data: dict[str, Any]) -> None:
        self._r.set(KEY, json.dumps(data, ensure_ascii=False))
```

- [ ] **Step 4: Refactor `MetadataIndex` to delegate**

Modify `backend/application/metadata/metadata_index.py` — replace the `__init__` and `_load`/`_save` methods (lines 35-37, 488-506) with:

```python
    def __init__(self, wiki_dir: str) -> None:
        from backend.core.config import settings
        from backend.core.backends import get_metadata_index_backend
        from pathlib import Path
        profile = settings.resolve_profile()
        legacy_path = Path(wiki_dir) / ".ontong" / "metadata_index.json"
        self._backend = get_metadata_index_backend(profile, legacy_path=legacy_path, redis_url=settings.redis_url)
        self._lock = threading.Lock()

    def _load(self) -> dict:
        return self._backend.load()

    def _save(self, d: dict) -> None:
        self._backend.save(d)
```

Remove `self._path` and `self._data` lines (now handled inside backend).

- [ ] **Step 5: Add `get_metadata_index_backend` to factory**

Append to `backend/core/backends.py`:

```python
def get_metadata_index_backend(profile: Profile, *, legacy_path=None, redis_url: str = ""):
    """Return a MetadataBackend matching the profile."""
    if "metadata_index" in _singletons:
        return _singletons["metadata_index"]

    if profile.metadata_index_backend == "json_file":
        from backend.application.metadata.backends.json_file import JsonFileBackend
        if legacy_path is None:
            raise RuntimeError("legacy_path required for json_file backend")
        backend = JsonFileBackend(legacy_path)
    elif profile.metadata_index_backend == "redis_hash":
        from backend.application.metadata.backends.redis_hash import RedisHashBackend
        if not redis_url:
            raise RuntimeError("redis_url required for redis_hash backend")
        backend = RedisHashBackend(redis_url)
    else:
        raise ValueError(f"unknown metadata_index backend: {profile.metadata_index_backend}")

    _singletons["metadata_index"] = backend
    logger.info(f"MetadataIndex backend initialized: {profile.metadata_index_backend}")
    return backend
```

- [ ] **Step 6: Run tests**

```bash
.venv/bin/pytest tests/test_metadata_index_redis.py tests/ -k "metadata_index" -v
```

Expected: 4+ passed (depending on existing metadata tests).

- [ ] **Step 7: Commit**

```bash
git add backend/application/metadata/backends/ backend/application/metadata/metadata_index.py backend/core/backends.py tests/test_metadata_index_redis.py
git commit -m "feat(infra): MetadataIndex backend abstraction + Redis hash impl"
```

---

## Task 6: Postgres Schema + Alembic

**Goal**: Migrations directory with initial schema for `wiki_references`, `wiki_versions`, `wiki_snapshots`, `wiki_audit`, `wiki_jobs` + `wiki_broken_refs` view.

**Files:**
- Create: `migrations/alembic.ini`, `migrations/env.py`, `migrations/script.py.mako`, `migrations/versions/2026_05_05_001_initial_schema.py`
- Create: `backend/infrastructure/db/__init__.py`, `engine.py`, `session.py`
- Modify: `pyproject.toml` (deps)
- Test: `tests/test_alembic_migration.py`

- [ ] **Step 1: Add deps**

```bash
poetry add 'sqlalchemy>=2.0,<3.0' 'asyncpg>=0.29' 'alembic>=1.13'
poetry add --group dev 'pytest-postgresql>=6.0'
```

- [ ] **Step 2: Initialize Alembic**

```bash
.venv/bin/alembic init -t async migrations
```

This creates `migrations/alembic.ini`, `env.py`, `script.py.mako`, `versions/`.

- [ ] **Step 3: Configure `migrations/env.py`**

Replace contents of `migrations/env.py`:

```python
"""Alembic env — async, reads DSN from settings.postgres_dsn."""
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool

from backend.core.config import settings

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = None  # We use raw SQL ops in migrations


def run_migrations_offline() -> None:
    url = settings.postgres_dsn
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    cfg = config.get_section(config.config_ini_section) or {}
    cfg["sqlalchemy.url"] = settings.postgres_dsn
    connectable = async_engine_from_config(cfg, prefix="sqlalchemy.", poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 4: Write initial migration**

Create `migrations/versions/2026_05_05_001_initial_schema.py`:

```python
"""initial schema: refs / versions / snapshots / audit / jobs

Revision ID: 2026_05_05_001
Revises:
Create Date: 2026-05-05
"""
from alembic import op


revision = "2026_05_05_001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE wiki_references (
            id           BIGSERIAL PRIMARY KEY,
            source_path  TEXT NOT NULL,
            target_path  TEXT NOT NULL,
            kind         SMALLINT NOT NULL,
            location     JSONB NOT NULL,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX idx_refs_target ON wiki_references (target_path);")
    op.execute("CREATE INDEX idx_refs_source ON wiki_references (source_path);")
    op.execute("""
        CREATE UNIQUE INDEX idx_refs_unique
        ON wiki_references (source_path, target_path, kind, (location->>'offset'));
    """)

    op.execute("""
        CREATE TABLE wiki_versions (
            path        TEXT PRIMARY KEY,
            version     TEXT NOT NULL,
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_by  TEXT
        );
    """)

    op.execute("""
        CREATE TABLE wiki_snapshots (
            id          BIGSERIAL PRIMARY KEY,
            path        TEXT NOT NULL,
            version     TEXT NOT NULL,
            content     BYTEA NOT NULL,
            user_name   TEXT NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            reason      TEXT
        );
    """)
    op.execute("CREATE INDEX idx_snap_path_time ON wiki_snapshots (path, created_at DESC);")

    op.execute("""
        CREATE TABLE wiki_audit (
            id           BIGSERIAL PRIMARY KEY,
            op           TEXT NOT NULL,
            actor        TEXT NOT NULL,
            payload      JSONB NOT NULL,
            started_at   TIMESTAMPTZ NOT NULL,
            finished_at  TIMESTAMPTZ,
            status       TEXT NOT NULL,
            error        TEXT
        );
    """)

    op.execute("""
        CREATE TABLE wiki_jobs (
            id           BIGSERIAL PRIMARY KEY,
            audit_id     BIGINT REFERENCES wiki_audit(id),
            kind         TEXT NOT NULL,
            target_path  TEXT NOT NULL,
            status       TEXT NOT NULL,
            attempts     SMALLINT DEFAULT 0,
            last_error   TEXT,
            updated_at   TIMESTAMPTZ DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX idx_jobs_audit ON wiki_jobs (audit_id);")
    op.execute("""
        CREATE INDEX idx_jobs_status ON wiki_jobs (status)
        WHERE status IN ('pending', 'failed');
    """)

    op.execute("""
        CREATE VIEW wiki_broken_refs AS
        SELECT r.* FROM wiki_references r
        LEFT JOIN wiki_versions v ON v.path = r.target_path
        WHERE v.path IS NULL;
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS wiki_broken_refs;")
    op.execute("DROP TABLE IF EXISTS wiki_jobs;")
    op.execute("DROP TABLE IF EXISTS wiki_audit;")
    op.execute("DROP TABLE IF EXISTS wiki_snapshots;")
    op.execute("DROP TABLE IF EXISTS wiki_versions;")
    op.execute("DROP TABLE IF EXISTS wiki_references;")
```

- [ ] **Step 5: Implement async engine helper**

Create `backend/infrastructure/db/__init__.py` (empty).

Create `backend/infrastructure/db/engine.py`:

```python
"""SQLAlchemy async engine — singleton."""
from __future__ import annotations

import logging
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is not None:
        return _engine
    from backend.core.config import settings
    if not settings.postgres_dsn:
        raise RuntimeError("settings.postgres_dsn is empty; team/enterprise profile requires it")
    _engine = create_async_engine(settings.postgres_dsn, pool_pre_ping=True, pool_size=10)
    logger.info("Postgres async engine initialized")
    return _engine


async def dispose() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
```

Create `backend/infrastructure/db/session.py`:

```python
"""Async session factory."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from .engine import get_engine

_session_factory = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


async def get_session() -> AsyncSession:
    return get_session_factory()()
```

- [ ] **Step 6: Write smoke test for migration**

Create `tests/test_alembic_migration.py`:

```python
"""Smoke test: alembic upgrade creates all expected tables + view."""
from __future__ import annotations

import pytest
from pytest_postgresql import factories

postgres = factories.postgresql_proc(port=None)
postgres_db = factories.postgresql("postgres")


def _run_alembic(dsn: str):
    from alembic.config import Config
    from alembic import command
    cfg = Config("migrations/alembic.ini")
    cfg.set_main_option("script_location", "migrations")
    cfg.set_main_option("sqlalchemy.url", dsn)
    command.upgrade(cfg, "head")


@pytest.mark.skipif(
    not pytest.importorskip("pytest_postgresql", reason="pytest-postgresql not installed"),
    reason="needs pytest-postgresql",
)
def test_initial_migration_creates_all_tables(postgres_db, monkeypatch):
    info = postgres_db.info
    sync_dsn = f"postgresql://{info.user}:{info.password}@{info.host}:{info.port}/{info.dbname}"
    async_dsn = sync_dsn.replace("postgresql://", "postgresql+asyncpg://")
    monkeypatch.setenv("POSTGRES_DSN", async_dsn)
    # Reload settings
    import importlib, backend.core.config
    importlib.reload(backend.core.config)

    _run_alembic(sync_dsn)

    cur = postgres_db.cursor()
    cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema='public' ORDER BY table_name;
    """)
    tables = [r[0] for r in cur.fetchall()]
    assert "wiki_references" in tables
    assert "wiki_versions" in tables
    assert "wiki_snapshots" in tables
    assert "wiki_audit" in tables
    assert "wiki_jobs" in tables

    cur.execute("""
        SELECT table_name FROM information_schema.views WHERE table_schema='public';
    """)
    views = [r[0] for r in cur.fetchall()]
    assert "wiki_broken_refs" in views
```

- [ ] **Step 7: Run migration test**

```bash
.venv/bin/pytest tests/test_alembic_migration.py -v
```

Expected: 1 passed (or skipped if PG not installed locally — note in handoff).

- [ ] **Step 8: Commit**

```bash
git add migrations/ backend/infrastructure/db/ tests/test_alembic_migration.py pyproject.toml poetry.lock
git commit -m "feat(infra): postgres schema + alembic + async engine"
```

---

## Task 7: TaskQueue + Arq Workers

**Goal**: Protocol + asyncio (dev) + Arq (team/enterprise) backends. Two queue names: `path` and `content`. Worker skeletons with stub functions (real impls in P1+).

**Files:**
- Create: `backend/infrastructure/queue/__init__.py`, `task_queue_protocol.py`, `asyncio_queue.py`, `arq_queue.py`
- Create: `backend/infrastructure/queue/workers/__init__.py`, `path_worker.py`, `content_worker.py`
- Modify: `backend/core/backends.py` (`get_task_queue`)
- Test: `tests/test_task_queue.py`

- [ ] **Step 1: Add Arq dep**

```bash
poetry add 'arq>=0.26'
```

- [ ] **Step 2: Write failing test**

Create `tests/test_task_queue.py`:

```python
"""TaskQueue tests — both backends behave equivalently for basic enqueue."""
from __future__ import annotations

import asyncio
import pytest


@pytest.mark.asyncio
async def test_asyncio_queue_runs_task():
    from backend.infrastructure.queue.asyncio_queue import AsyncioTaskQueue

    received: list[tuple] = []

    async def my_task(arg1: str, arg2: int) -> None:
        received.append((arg1, arg2))

    q = AsyncioTaskQueue(handlers={"my_task": my_task})
    await q.start()
    job_id = await q.enqueue("path", "my_task", "hello", 42)
    await asyncio.sleep(0.1)
    await q.stop()

    assert received == [("hello", 42)]
    assert job_id


@pytest.mark.asyncio
async def test_asyncio_queue_progress():
    from backend.infrastructure.queue.asyncio_queue import AsyncioTaskQueue

    async def slow_task() -> None:
        await asyncio.sleep(0.05)

    q = AsyncioTaskQueue(handlers={"slow_task": slow_task})
    await q.start()
    audit_id = "audit-1"
    await q.enqueue("path", "slow_task", audit_id=audit_id)
    await q.enqueue("path", "slow_task", audit_id=audit_id)
    p = await q.progress(audit_id)
    assert p["total"] == 2
    await asyncio.sleep(0.2)
    p = await q.progress(audit_id)
    assert p["done"] == 2
    await q.stop()
```

- [ ] **Step 3: Run, expect ImportError**

```bash
.venv/bin/pytest tests/test_task_queue.py -v
```

- [ ] **Step 4: Implement protocol**

Create `backend/infrastructure/queue/__init__.py` (empty).

Create `backend/infrastructure/queue/task_queue_protocol.py`:

```python
"""TaskQueue protocol — abstract over asyncio (dev) and Arq (team/enterprise)."""
from __future__ import annotations

from abc import ABC, abstractmethod


class TaskQueue(ABC):
    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def enqueue(self, queue: str, fn: str, *args, audit_id: str = "", **kwargs) -> str: ...

    @abstractmethod
    async def progress(self, audit_id: str) -> dict: ...
```

- [ ] **Step 5: Implement Asyncio backend**

Create `backend/infrastructure/queue/asyncio_queue.py`:

```python
"""In-process asyncio task queue — dev profile."""
from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict
from typing import Awaitable, Callable

from .task_queue_protocol import TaskQueue

logger = logging.getLogger(__name__)


class AsyncioTaskQueue(TaskQueue):
    def __init__(self, handlers: dict[str, Callable[..., Awaitable]] | None = None) -> None:
        self._handlers = handlers or {}
        self._queues: dict[str, asyncio.Queue] = {"path": asyncio.Queue(), "content": asyncio.Queue()}
        self._workers: list[asyncio.Task] = []
        # progress[audit_id] = {"total": int, "done": int, "failed": int}
        self._progress: dict[str, dict] = defaultdict(lambda: {"total": 0, "done": 0, "failed": 0})

    def register(self, fn_name: str, handler: Callable[..., Awaitable]) -> None:
        self._handlers[fn_name] = handler

    async def start(self) -> None:
        for qname in self._queues:
            self._workers.append(asyncio.create_task(self._worker_loop(qname)))

    async def stop(self) -> None:
        for w in self._workers:
            w.cancel()
        for w in self._workers:
            try:
                await w
            except asyncio.CancelledError:
                pass
        self._workers.clear()

    async def enqueue(self, queue: str, fn: str, *args, audit_id: str = "", **kwargs) -> str:
        if queue not in self._queues:
            raise ValueError(f"unknown queue: {queue}")
        if fn not in self._handlers:
            raise ValueError(f"no handler registered for {fn}")
        job_id = uuid.uuid4().hex
        if audit_id:
            self._progress[audit_id]["total"] += 1
        await self._queues[queue].put((job_id, fn, args, kwargs, audit_id))
        return job_id

    async def progress(self, audit_id: str) -> dict:
        return dict(self._progress[audit_id])

    async def _worker_loop(self, qname: str) -> None:
        q = self._queues[qname]
        while True:
            job_id, fn, args, kwargs, audit_id = await q.get()
            try:
                handler = self._handlers[fn]
                await handler(*args, **kwargs)
                if audit_id:
                    self._progress[audit_id]["done"] += 1
            except Exception as e:
                logger.error(f"Task {fn} ({job_id}) failed: {e}")
                if audit_id:
                    self._progress[audit_id]["failed"] += 1
            finally:
                q.task_done()
```

- [ ] **Step 6: Implement Arq backend**

Create `backend/infrastructure/queue/arq_queue.py`:

```python
"""Arq task queue — team/enterprise profile.

Workers run as separate processes via `arq backend.infrastructure.queue.workers.path_worker.WorkerSettings`.
This class is the producer side — schedules jobs into Redis.
"""
from __future__ import annotations

import logging
import uuid
from typing import Awaitable, Callable

from .task_queue_protocol import TaskQueue

logger = logging.getLogger(__name__)


class ArqTaskQueue(TaskQueue):
    def __init__(self, redis_url: str) -> None:
        self._url = redis_url
        self._pool = None

    async def start(self) -> None:
        from arq import create_pool
        from arq.connections import RedisSettings
        self._pool = await create_pool(RedisSettings.from_dsn(self._url))

    async def stop(self) -> None:
        if self._pool:
            await self._pool.aclose()
            self._pool = None

    def register(self, fn_name: str, handler: Callable[..., Awaitable]) -> None:
        # Arq registers handlers in WorkerSettings (separate file). No-op here.
        logger.debug(f"Arq.register noop for {fn_name} — workers register via WorkerSettings")

    async def enqueue(self, queue: str, fn: str, *args, audit_id: str = "", **kwargs) -> str:
        assert self._pool is not None, "ArqTaskQueue.start() not called"
        job_id = uuid.uuid4().hex
        # Use queue_name to route to path-worker or content-worker
        await self._pool.enqueue_job(
            fn, *args, _queue_name=f"arq:queue:{queue}", _job_id=job_id, audit_id=audit_id, **kwargs,
        )
        return job_id

    async def progress(self, audit_id: str) -> dict:
        # Progress is read from Postgres wiki_jobs in higher layers. Arq itself
        # doesn't track audit-level rollups, so this returns the live job state
        # by querying wiki_jobs (P3+ wires this in). For Phase 0 stub:
        return {"total": 0, "done": 0, "failed": 0}
```

- [ ] **Step 7: Worker skeletons**

Create `backend/infrastructure/queue/workers/__init__.py` (empty).

Create `backend/infrastructure/queue/workers/path_worker.py`:

```python
"""Path-worker — handles rename inbound patches and chunk metadata updates.

Phase 0 ships skeleton handlers that log and exit. Real implementations
land in Phase 3 (single-file rename) and Phase 4 (folder/bulk).
"""
from __future__ import annotations

import logging
from arq.connections import RedisSettings

logger = logging.getLogger(__name__)


async def patch_inbound(ctx: dict, source: str, old_target: str, new_target: str, audit_id: str = "") -> None:
    """Stub: patch a single inbound document. Real impl in Phase 3."""
    logger.info(f"[path-worker] patch_inbound stub: {source} {old_target}->{new_target} (audit={audit_id})")


async def update_chunk_metadata(ctx: dict, old_path: str, new_path: str, audit_id: str = "") -> None:
    """Stub: update chunk metadata in vector DB. Real impl in Phase 3."""
    logger.info(f"[path-worker] update_chunk_metadata stub: {old_path}->{new_path} (audit={audit_id})")


class WorkerSettings:
    """Arq worker config. Run with: `arq backend.infrastructure.queue.workers.path_worker.WorkerSettings`."""
    queue_name = "arq:queue:path"
    functions = [patch_inbound, update_chunk_metadata]

    @staticmethod
    def redis_settings():
        from backend.core.config import settings
        return RedisSettings.from_dsn(settings.redis_url)
```

Create `backend/infrastructure/queue/workers/content_worker.py`:

```python
"""Content-worker — handles BG indexing, embedding, snapshot persistence.

Phase 0 ships skeleton; real impls in Phase 1 (refindex extract) and Phase 2 (snapshot).
"""
from __future__ import annotations

import logging
from arq.connections import RedisSettings

logger = logging.getLogger(__name__)


async def bg_index(ctx: dict, path: str, audit_id: str = "") -> None:
    """Stub: index a file (chunking + embeddings + BM25). Real impl in P1+."""
    logger.info(f"[content-worker] bg_index stub: {path} (audit={audit_id})")


async def bg_remove_chunks(ctx: dict, path: str, audit_id: str = "") -> None:
    """Stub: remove chunks for a deleted file."""
    logger.info(f"[content-worker] bg_remove_chunks stub: {path} (audit={audit_id})")


async def bg_reembed_chunks(ctx: dict, path: str, audit_id: str = "") -> None:
    """Stub: regenerate embeddings after chunk-body path prefix change (OQ-4=A)."""
    logger.info(f"[content-worker] bg_reembed_chunks stub: {path} (audit={audit_id})")


class WorkerSettings:
    queue_name = "arq:queue:content"
    functions = [bg_index, bg_remove_chunks, bg_reembed_chunks]

    @staticmethod
    def redis_settings():
        from backend.core.config import settings
        return RedisSettings.from_dsn(settings.redis_url)
```

- [ ] **Step 8: Add `get_task_queue` to factory**

Append to `backend/core/backends.py`:

```python
def get_task_queue(profile: Profile, *, redis_url: str = ""):
    if "task_queue" in _singletons:
        return _singletons["task_queue"]

    if profile.task_queue_backend == "asyncio":
        from backend.infrastructure.queue.asyncio_queue import AsyncioTaskQueue
        q = AsyncioTaskQueue()
    elif profile.task_queue_backend == "arq":
        from backend.infrastructure.queue.arq_queue import ArqTaskQueue
        if not redis_url:
            raise RuntimeError("redis_url required for arq backend")
        q = ArqTaskQueue(redis_url)
    else:
        raise ValueError(f"unknown task_queue backend: {profile.task_queue_backend}")

    _singletons["task_queue"] = q
    logger.info(f"TaskQueue backend initialized: {profile.task_queue_backend}")
    return q
```

- [ ] **Step 9: Run tests**

```bash
.venv/bin/pytest tests/test_task_queue.py -v
```

Expected: 2 passed.

- [ ] **Step 10: Commit**

```bash
git add backend/infrastructure/queue/ backend/core/backends.py tests/test_task_queue.py pyproject.toml poetry.lock
git commit -m "feat(infra): TaskQueue protocol + asyncio/arq impls + worker skeletons"
```

---

## Task 8: Profile Status API

**Goal**: `GET /api/wiki/profile-status` shows resolved profile + ping result for each backend.

**Files:**
- Modify: `backend/api/wiki.py`
- Test: `tests/test_profile_status_api.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_profile_status_api.py`:

```python
"""Profile status endpoint test."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_profile_status_dev(monkeypatch):
    monkeypatch.setenv("ONTONG_PROFILE", "dev")
    import importlib, backend.core.config
    importlib.reload(backend.core.config)
    from backend.main import app

    client = TestClient(app)
    r = client.get("/api/wiki/profile-status", headers={"X-User": "test"})
    assert r.status_code == 200
    body = r.json()
    assert body["profile"] == "dev"
    assert body["backends"]["lock"]["name"] == "memory"
    assert body["backends"]["lock"]["healthy"] is True
```

- [ ] **Step 2: Run, expect 404**

```bash
.venv/bin/pytest tests/test_profile_status_api.py -v
```

- [ ] **Step 3: Add endpoint**

Modify `backend/api/wiki.py` — add at the bottom of the file:

```python
@router.get("/profile-status")
async def get_profile_status():
    """Return current Profile + per-backend health."""
    from backend.core.config import settings

    profile = settings.resolve_profile()
    backends = {
        "lock": {"name": profile.lock_backend, "healthy": True},
        "event_bus": {"name": profile.event_bus_backend, "healthy": True},
        "metadata_index": {"name": profile.metadata_index_backend, "healthy": True},
        "kv": {"name": profile.kv_backend, "healthy": True},
        "task_queue": {"name": profile.task_queue_backend, "healthy": True},
        "fulltext": {"name": profile.fulltext_backend, "healthy": True},
    }

    # Ping Redis if any backend uses it
    needs_redis = any(
        getattr(profile, f"{k}_backend") in {"redis", "redis_pubsub", "redis_hash"}
        for k in ["lock", "event_bus", "metadata_index", "kv"]
    )
    if needs_redis and settings.redis_url:
        try:
            import redis
            r = redis.from_url(settings.redis_url, socket_timeout=1)
            r.ping()
        except Exception as e:
            for name in ["lock", "event_bus", "metadata_index", "kv"]:
                if backends[name]["name"] in {"redis", "redis_pubsub", "redis_hash"}:
                    backends[name]["healthy"] = False
                    backends[name]["error"] = str(e)

    # Ping Postgres if profile uses it
    if settings.postgres_dsn:
        try:
            from sqlalchemy import text
            from backend.infrastructure.db.engine import get_engine
            engine = get_engine()
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception as e:
            backends["postgres"] = {"healthy": False, "error": str(e)}
        else:
            backends["postgres"] = {"healthy": True}

    return {
        "profile": profile.name,
        "backends": backends,
        "redis_url_configured": bool(settings.redis_url),
        "postgres_dsn_configured": bool(settings.postgres_dsn),
    }
```

- [ ] **Step 4: Run test**

```bash
.venv/bin/pytest tests/test_profile_status_api.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/api/wiki.py tests/test_profile_status_api.py
git commit -m "feat(api): add /api/wiki/profile-status endpoint"
```

---

## Task 9: ontong CLI Entry + Migrate Skeleton

**Goal**: `ontong migrate <subcommand>` framework with `db-upgrade` (alembic head) and stubs for `refindex-build`, `snapshots-export`, `fulltext-export`.

**Files:**
- Create: `backend/cli/__init__.py`, `__main__.py`, `migrate.py`
- Modify: `pyproject.toml` (script entry)
- Test: `tests/test_cli_migrate.py`

- [ ] **Step 1: Add script entry to pyproject**

Modify `pyproject.toml` — append under `[tool.poetry]`:

```toml
[tool.poetry.scripts]
ontong = "backend.cli.__main__:main"
```

Then:

```bash
poetry install --no-root || poetry install
```

- [ ] **Step 2: Write failing test**

Create `tests/test_cli_migrate.py`:

```python
"""ontong CLI migrate test."""
from __future__ import annotations

import subprocess


def test_help_lists_migrate():
    r = subprocess.run(
        [".venv/bin/python", "-m", "backend.cli", "--help"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    assert "migrate" in r.stdout


def test_migrate_help_lists_subcommands():
    r = subprocess.run(
        [".venv/bin/python", "-m", "backend.cli", "migrate", "--help"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    assert "db-upgrade" in r.stdout
    assert "refindex-build" in r.stdout
```

- [ ] **Step 3: Run, expect failure**

```bash
.venv/bin/pytest tests/test_cli_migrate.py -v
```

- [ ] **Step 4: Implement CLI**

Create `backend/cli/__init__.py` (empty).

Create `backend/cli/__main__.py`:

```python
"""ontong CLI entry. Run via `python -m backend.cli` or `ontong` (after poetry install)."""
from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(prog="ontong", description="onTong administration CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    from backend.cli.migrate import register_migrate
    register_migrate(sub)

    args = parser.parse_args()
    if hasattr(args, "func"):
        return args.func(args) or 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

Create `backend/cli/migrate.py`:

```python
"""ontong migrate <subcommand> — schema/data migrations."""
from __future__ import annotations

import argparse
import logging

logger = logging.getLogger(__name__)


def cmd_db_upgrade(args: argparse.Namespace) -> int:
    """Run alembic upgrade head against settings.postgres_dsn."""
    from alembic.config import Config
    from alembic import command
    from backend.core.config import settings

    if not settings.postgres_dsn:
        print("ERROR: settings.postgres_dsn is empty (set POSTGRES_DSN env var)")
        return 2

    cfg = Config("migrations/alembic.ini")
    cfg.set_main_option("script_location", "migrations")
    sync_dsn = settings.postgres_dsn.replace("+asyncpg", "")
    cfg.set_main_option("sqlalchemy.url", sync_dsn)
    print(f"Running alembic upgrade head against {sync_dsn} ...")
    command.upgrade(cfg, "head")
    print("Done.")
    return 0


def cmd_refindex_build(args: argparse.Namespace) -> int:
    """Stub — real impl in Phase 1."""
    print("refindex-build is not yet implemented (lands in Phase 1).")
    return 0


def cmd_snapshots_export(args: argparse.Namespace) -> int:
    print("snapshots-export is not yet implemented (lands in Phase 2).")
    return 0


def cmd_fulltext_export(args: argparse.Namespace) -> int:
    print("fulltext-export is not yet implemented (lands in Phase 6).")
    return 0


def register_migrate(sub) -> None:
    p = sub.add_parser("migrate", help="Schema and data migrations")
    msub = p.add_subparsers(dest="migrate_cmd", required=True)

    db = msub.add_parser("db-upgrade", help="Run alembic upgrade head")
    db.set_defaults(func=cmd_db_upgrade)

    rb = msub.add_parser("refindex-build", help="Build ReferenceIndex from existing wiki content (Phase 1)")
    rb.add_argument("--batch", type=int, default=1000)
    rb.add_argument("--workers", type=int, default=4)
    rb.set_defaults(func=cmd_refindex_build)

    se = msub.add_parser("snapshots-export", help="Export snapshots between backends (Phase 2)")
    se.add_argument("--from", dest="from_", required=True)
    se.add_argument("--to", required=True)
    se.set_defaults(func=cmd_snapshots_export)

    fe = msub.add_parser("fulltext-export", help="Export search index between backends (Phase 6)")
    fe.add_argument("--from", dest="from_", required=True)
    fe.add_argument("--to", required=True)
    fe.set_defaults(func=cmd_fulltext_export)
```

- [ ] **Step 5: Run tests**

```bash
.venv/bin/pytest tests/test_cli_migrate.py -v
.venv/bin/python -m backend.cli --help
.venv/bin/python -m backend.cli migrate --help
```

Expected: 2 passed; help shows commands.

- [ ] **Step 6: Commit**

```bash
git add backend/cli/ tests/test_cli_migrate.py pyproject.toml poetry.lock
git commit -m "feat(cli): ontong CLI entry + migrate framework"
```

---

## Phase 0 Verification

- [ ] **Final regression**: run full test suite

```bash
.venv/bin/pytest tests/ -x --ignore=tests/test_alembic_migration.py -v
.venv/bin/pytest tests/test_alembic_migration.py -v  # only if PG installed
```

Target: 0 regressions vs baseline (105 wiki tests + others). New tests added: 5 files (~12 cases).

- [ ] **Profile sanity check**: dev profile still serves site

```bash
.venv/bin/python -m uvicorn backend.main:app --port 8001 &
sleep 2
curl -H "X-User: test" http://localhost:8001/api/wiki/profile-status | python -m json.tool
kill %1
```

Expected JSON: `{"profile": "dev", "backends": {...all healthy...}}`.

- [ ] **Team profile smoke** (only if Redis + Postgres running locally):

```bash
ONTONG_PROFILE=team \
  REDIS_URL=redis://localhost:6379/0 \
  POSTGRES_DSN=postgresql+asyncpg://ontong:ontong@localhost:5432/ontong \
  .venv/bin/python -m backend.cli migrate db-upgrade

ONTONG_PROFILE=team REDIS_URL=redis://localhost:6379/0 \
  .venv/bin/python -m uvicorn backend.main:app --port 8001 &
sleep 2
curl -H "X-User: test" http://localhost:8001/api/wiki/profile-status | python -m json.tool
kill %1
```

Expected: profile=team, all healthy. wiki_references / versions / snapshots / audit / jobs tables exist.

- [ ] **Step Completion Protocol** (`CLAUDE.md`):
  1. ✅ Code (Tasks 1-9 commits)
  2. ✅ Verification (above)
  3. Write `toClaude/wiki/log/step_phase0_summary.md` → move to `toClaude/wiki/archive/`
  4. Append Phase 0 demo scenarios to `toClaude/wiki/demo_guide.md`
  5. Mark Phase 0 row `[x]` in `toClaude/wiki/TODO.md`
  6. Update memory `project_status.md`
  7. Stop and report to user

---

## Open Questions / Notes for Engineer

- **CI**: pytest-postgresql may need `pg_ctl` on PATH. If unavailable, mark test as `xfail` instead of skip.
- **Redis URL**: existing `settings.redis_url` is used; if empty under team/enterprise profile, the factory raises. Document in the env file.
- **Existing `_lock_service` singleton**: legacy callsites `from backend.application.lock_service import _lock_service` continue working through the new `get_lock_service()`.
- **Arq worker process**: production runs need `arq backend.infrastructure.queue.workers.path_worker.WorkerSettings &` and the same for `content_worker` as separate processes. Document in deployment runbook (defer to operations team).
- **MetadataIndex Redis key size**: at 100K files the JSON blob is ~10-20MB. Single key, atomic R/W, OK for Phase 0. If Phase 6 load test shows latency, shard per-file (`ontong:metadata_index:files:<path>`).

---

## Self-Review Notes

This plan covers spec §13 Phase 0 작업 0-1 ~ 0-9 in order. Each task ends with a green test + commit. Dependencies between tasks (factory ← profile, kv ← factory, metadata_index ← kv-style abstraction, queue ← workers) are linear.

Possible follow-ups (not in scope of P0):
- Postgres connection pool tuning (defer to load test in P6)
- Redis Cluster support (currently single-node; P6 evaluation)
- Profile hot-reload: out of scope (OQ-7=A confirmed)
