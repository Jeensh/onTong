"""Persona API — per-user AI persona customization (ontong.local.md).

The persona file is a regular wiki document that users edit with the Tiptap editor.
This API only provides:
  - POST /api/persona/ensure — create the file with a guide template if it doesn't exist
  - POST /api/persona/invalidate — clear the prompt cache after edits
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends

from backend.core.auth import User, get_current_user

logger = logging.getLogger(__name__)

_storage: Any = None  # StorageProvider


def init(storage: Any) -> None:
    global _storage
    _storage = storage


router = APIRouter(
    prefix="/api/persona",
    tags=["persona"],
    dependencies=[Depends(get_current_user)],
)


def _persona_path(username: str) -> str:
    return f"_personas/@{username}/ontong.local.md"


_TEMPLATE = """\
# 내 AI 설정

> 이 문서에 작성한 내용이 AI 어시스턴트의 응답 스타일에 반영됩니다.
> 자유롭게 마크다운으로 작성하세요. 저장하면 다음 대화부터 적용됩니다.
> 기본 규칙(출처 명시, 충돌 감지 등)은 항상 유지됩니다.

## 나에 대해

<!-- 나의 역할, 팀, 주로 보는 문서 영역 등을 적어주세요 -->
<!-- 예: 물류팀 DevOps 엔지니어. 인프라/배포 관련 문서를 주로 본다. -->

## 응답 스타일

<!-- AI가 답변할 때 지켜줬으면 하는 규칙을 적어주세요 -->
<!-- 예:
- 캐주얼하게 답변해줘
- 코드 예시를 항상 포함해줘
- 영어 기술 용어는 번역하지 마
- 표 형식으로 정리하는 걸 선호해
- 3줄 이내로 요약부터 보여줘
-->

## 참고 사항

<!-- 기타 AI가 알았으면 하는 컨텍스트를 적어주세요 -->
<!-- 예:
- SCM 도메인 지식이 있으니 기초 설명은 생략해도 됨
- 모르는 건 솔직히 모른다고 해줘
- 관련 담당자 이름이 있으면 알려줘
-->
"""


@router.post("/ensure")
async def ensure_persona(user: User = Depends(get_current_user)) -> dict:
    """Create persona file with guide template if it doesn't exist.

    Returns the file path so the frontend can open it in the workspace editor.
    """
    if not _storage:
        return {"status": "error", "message": "Storage not initialized"}

    path = _persona_path(user.name)
    existing = await _storage.read(path)

    if not existing:
        await _storage.write(path, _TEMPLATE, user_name=user.name)
        logger.info(f"Created persona template for user '{user.name}'")

    return {"path": path, "created": existing is None}


@router.post("/invalidate")
async def invalidate_persona(user: User = Depends(get_current_user)) -> dict:
    """Clear cached persona after the user edits their file."""
    from backend.application.agent.rag_agent import invalidate_persona_cache
    invalidate_persona_cache(user.name)
    return {"status": "ok"}
