"""Helpers for Two-Phase batch lock with deadlock-avoidance ordering.

The acquisition rule: always lock paths in alphabetical sorted order. Every
caller obeys this rule, so circular wait is impossible.
"""
from __future__ import annotations

import logging
from typing import Iterable

from backend.application.lock_service import get_lock_service

logger = logging.getLogger(__name__)

DEFAULT_TTL = 5  # seconds


def lock_set_in_order(
    paths: Iterable[str], user: str, *, ttl: int = DEFAULT_TTL
) -> tuple[list[str], list[str]]:
    """Acquire locks on `paths` in alphabetical order to prevent deadlocks.

    Returns (acquired_paths, missed_paths). On any failure, releases everything
    acquired so far and returns the first conflicting path in missed_paths.

    Implementation: sort paths, dedupe, attempt acquire one at a time. If any
    path is held by someone else (returns None), abort and roll back all acquired
    locks before returning.
    """
    svc = get_lock_service()
    sorted_paths = sorted(set(paths))
    acquired: list[str] = []

    for path in sorted_paths:
        info = svc.acquire(path, user, ttl=ttl)
        if info is None:
            # Roll back all locks acquired so far
            for p in acquired:
                svc.release(p, user)
            missed = [p for p in sorted_paths if p not in acquired]
            # Report only first conflict path
            return [], missed[:1] if missed else []
        acquired.append(path)

    return acquired, []


def lock_set_release_all(paths: Iterable[str], user: str) -> int:
    """Release all locks held by user across the given paths.

    Returns the count of successful releases. Idempotent — releasing an
    already-released lock is a no-op and is not counted.
    """
    svc = get_lock_service()
    count = 0
    for p in paths:
        if svc.release(p, user):
            count += 1
    return count
