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
