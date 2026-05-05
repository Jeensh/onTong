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
    "ref_index": {"sqlite", "postgres"},
    "version_store": {"sqlite", "postgres"},
    "snapshot": {"sqlite", "postgres"},
    "audit_store": {"sqlite", "postgres"},
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
    ref_index_backend: str = "sqlite"      # default: sqlite (dev-safe)
    version_store_backend: str = "sqlite"  # OCC version store (Phase 2)
    snapshot_backend: str = "sqlite"       # Snapshot store (Phase 2 Tasks 2-4/2-5)
    audit_store_backend: str = "sqlite"    # Rename audit store (Phase 3)


_DEFAULTS: dict[str, dict[str, str]] = {
    "dev": {
        "lock": "memory",
        "event_bus": "inproc",
        "metadata_index": "json_file",
        "kv": "memory",
        "task_queue": "asyncio",
        "fulltext": "bm25_inmem",
        "ref_index": "sqlite",
        "version_store": "sqlite",
        "snapshot": "sqlite",
        "audit_store": "sqlite",
    },
    "team": {
        "lock": "redis",
        "event_bus": "redis_pubsub",
        "metadata_index": "redis_hash",
        "kv": "redis",
        "task_queue": "arq",
        "fulltext": "bm25_inmem",
        "ref_index": "postgres",
        "version_store": "postgres",
        "snapshot": "postgres",
        "audit_store": "postgres",
    },
    "enterprise": {
        "lock": "redis",
        "event_bus": "redis_pubsub",
        "metadata_index": "redis_hash",
        "kv": "redis",
        "task_queue": "arq",
        "fulltext": "elasticsearch",
        "ref_index": "postgres",
        "version_store": "postgres",
        "snapshot": "postgres",
        "audit_store": "postgres",
    },
}

_OVERRIDE_KEYS = {
    "lock": "ONTONG_LOCK_BACKEND",
    "event_bus": "ONTONG_EVENT_BUS_BACKEND",
    "metadata_index": "ONTONG_METADATA_INDEX_BACKEND",
    "kv": "ONTONG_KV_BACKEND",
    "task_queue": "ONTONG_TASK_QUEUE_BACKEND",
    "fulltext": "ONTONG_FULLTEXT_BACKEND",
    "ref_index": "ONTONG_REF_INDEX_BACKEND",
    "version_store": "ONTONG_VERSION_STORE_BACKEND",
    "snapshot": "ONTONG_SNAPSHOT_BACKEND",
    "audit_store": "ONTONG_AUDIT_STORE_BACKEND",
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
        ref_index_backend=chosen["ref_index"],
        version_store_backend=chosen["version_store"],
        snapshot_backend=chosen["snapshot"],
        audit_store_backend=chosen["audit_store"],
    )
