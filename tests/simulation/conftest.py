"""Shared fixtures for tests/simulation.

Phase 21b — intent confirmation step 은 production default 가 True (사용자
vision: stub → intent_classified → confirm → target_selected). 그러나 이 디렉토리의
26+ 기존 테스트는 1-step (stub → target_selected) flow 가정으로 작성됨.

autouse 로 INTENT_CONFIRM_REQUIRED 를 False 로 토글 → 기존 테스트는 legacy 흐름
유지. Phase 21b 새 흐름 테스트는 별도 파일 (test_multiturn_phase21b_*.py) 에서
이 fixture 를 override 하여 True 모드 검증.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _legacy_intent_confirm_flag(monkeypatch):
    from backend.section3.api import multiturn_router as mr
    monkeypatch.setattr(mr, "INTENT_CONFIRM_REQUIRED", False)
    yield
