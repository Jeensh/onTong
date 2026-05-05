"""Shared pytest fixtures and hooks for the onTong test suite."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def reset_backend_singletons():
    """Clear the backends singleton cache before every test.

    MetadataIndex (and other backends) are cached in `backends._singletons`
    as a process-wide singleton. Tests that instantiate these classes directly
    (e.g. MetadataIndex(tmp_path)) must start with a clean cache so each test
    gets an isolated backend pointing to its own tmp_path.
    """
    from backend.core.backends import _reset_for_test
    _reset_for_test()
    yield
    _reset_for_test()
