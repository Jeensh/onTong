"""Section 3 configuration — mock toggle and Section 2 connection settings."""

from __future__ import annotations

import os


def use_mock() -> bool:
    """Whether to use the mock modeling client."""
    return os.getenv("SIMULATION_USE_MOCK", "true").lower() in ("true", "1", "yes")


def modeling_api_base_url() -> str:
    """Base URL for Section 2 Modeling API (used when mock is off)."""
    return os.getenv("MODELING_API_URL", "http://localhost:8001/api/modeling")
