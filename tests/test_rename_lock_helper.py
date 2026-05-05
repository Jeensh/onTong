"""lock_helper.py tests — alphabetical ordering + rollback."""
from __future__ import annotations
import pytest


@pytest.fixture(autouse=True)
def reset_lock_service():
    from backend.core.backends import _reset_for_test
    _reset_for_test()
    yield
    _reset_for_test()


def test_lock_set_in_order_acquires_all():
    from backend.application.rename.lock_helper import lock_set_in_order, lock_set_release_all
    paths = ["zeta.md", "alpha.md", "mu.md"]
    acquired, missed = lock_set_in_order(paths, user="rename:alice")
    assert acquired == ["alpha.md", "mu.md", "zeta.md"]
    assert missed == []
    n = lock_set_release_all(paths, user="rename:alice")
    assert n == 3


def test_lock_set_in_order_rolls_back_on_conflict():
    from backend.application.lock_service import get_lock_service
    from backend.application.rename.lock_helper import lock_set_in_order, lock_set_release_all
    # Bob holds beta.md
    get_lock_service().acquire("beta.md", "bob")
    acquired, missed = lock_set_in_order(["alpha.md", "beta.md", "gamma.md"], user="rename:alice")
    # Should have rolled back — acquired list should be empty after rollback
    assert acquired == []
    assert missed == ["beta.md"]
    # Verify alpha.md is NOT held by alice anymore (released on rollback)
    info = get_lock_service().status("alpha.md")
    assert info is None or info.user == "bob"
    # Cleanup
    get_lock_service().release("beta.md", "bob")


def test_lock_set_release_all_idempotent():
    from backend.application.rename.lock_helper import lock_set_in_order, lock_set_release_all
    paths = ["a.md", "b.md"]
    lock_set_in_order(paths, user="rename:alice")
    n1 = lock_set_release_all(paths, user="rename:alice")
    n2 = lock_set_release_all(paths, user="rename:alice")
    assert n1 == 2
    # Second call: locks already gone — no exception
    assert n2 >= 0


def test_lock_set_in_order_dedupes():
    """Duplicate paths should be deduped."""
    from backend.application.rename.lock_helper import lock_set_in_order, lock_set_release_all
    acquired, missed = lock_set_in_order(["a.md", "a.md", "b.md"], user="alice")
    assert sorted(acquired) == ["a.md", "b.md"]
    lock_set_release_all(acquired, "alice")
