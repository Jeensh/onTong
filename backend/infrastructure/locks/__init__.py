"""Lock backends. Import concrete implementations from submodules:

    from backend.infrastructure.locks.memory import InMemoryLockBackend
    from backend.infrastructure.locks.redis import RedisLockBackend

Backend selection is done by backend.core.backends.get_lock_backend(profile).
"""
