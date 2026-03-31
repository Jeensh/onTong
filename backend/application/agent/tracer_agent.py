"""Tracer Agent — Mock for Phase 1."""

from __future__ import annotations

import json
from typing import AsyncGenerator

from backend.core.schemas import ChatRequest, ContentDelta, DoneEvent


class TracerAgent:
    name = "DEBUG_TRACE"

    async def execute(
        self, request: ChatRequest, **kwargs
    ) -> AsyncGenerator[str, None]:
        msg = (
            "디버그 추적 에이전트는 현재 Phase 2에서 개발 예정입니다.\n\n"
            "이 에이전트가 완성되면 다음을 수행합니다:\n"
            "- Git 커밋 히스토리 파싱\n"
            "- Spoon CLI로 Spring @Autowired 의존성 트리 순회\n"
            "- DB 유효성 검사로 데이터 불일치 경계 파악"
        )
        yield f"event: content_delta\ndata: {ContentDelta(delta=msg).model_dump_json()}\n\n"
        yield f"event: done\ndata: {DoneEvent().model_dump_json()}\n\n"
