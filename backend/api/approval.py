"""Approval API — Human-in-the-loop action handling."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from backend.core.auth import User, get_current_user
from backend.core.schemas import ApprovalRequest
from backend.core.session import session_store
from backend.application.wiki.wiki_service import WikiService

logger = logging.getLogger(__name__)

from backend.core.auth import get_current_user

router = APIRouter(prefix="/api/approval", tags=["approval"], dependencies=[Depends(get_current_user)])

_wiki_service: WikiService | None = None


def init(wiki_service: WikiService) -> None:
    global _wiki_service
    _wiki_service = wiki_service


def _svc() -> WikiService:
    if _wiki_service is None:
        raise RuntimeError("WikiService not initialized")
    return _wiki_service


@router.post("/resolve")
async def resolve_approval(request: ApprovalRequest, user: User = Depends(get_current_user)):
    """Resolve a pending approval action (approve or reject)."""
    pending = session_store.resolve_action(request.action_id, request.approved)

    if pending is None:
        raise HTTPException(
            status_code=404,
            detail=f"Pending action not found or already resolved: {request.action_id}",
        )

    if not request.approved:
        return {"status": "rejected", "action_id": request.action_id}

    # Execute the approved action
    action = pending.action
    if action.type in ("wiki_write", "wiki_edit"):
        await _svc().save_file(action.path, action.content, user_name=user.name)
        logger.info(f"Approved {action.type}: {action.path}")
        return {"status": "approved", "action_id": request.action_id, "path": action.path}
    elif action.type == "wiki_delete":
        await _svc().delete_file(action.path)
        logger.info(f"Approved wiki delete: {action.path}")
        return {"status": "approved", "action_id": request.action_id, "path": action.path}
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action type: {action.type}")
