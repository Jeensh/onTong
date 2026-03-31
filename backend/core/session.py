"""In-memory session and pending action store."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from .schemas import ApprovalAction


@dataclass
class PendingAction:
    action_id: str
    session_id: str
    action: ApprovalAction
    created_at: datetime = field(default_factory=datetime.utcnow)
    resolved: bool = False
    approved: bool | None = None


@dataclass
class SessionState:
    session_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    messages: list[dict] = field(default_factory=list)


class SessionStore:
    """In-memory session storage. Sufficient for Phase 1."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._pending: dict[str, PendingAction] = {}

    def get_or_create_session(self, session_id: str) -> SessionState:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState(session_id=session_id)
        return self._sessions[session_id]

    def add_pending_action(
        self, session_id: str, action: ApprovalAction
    ) -> str:
        action_id = str(uuid.uuid4())
        self._pending[action_id] = PendingAction(
            action_id=action_id,
            session_id=session_id,
            action=action,
        )
        return action_id

    def resolve_action(self, action_id: str, approved: bool) -> PendingAction | None:
        pending = self._pending.get(action_id)
        if pending is None or pending.resolved:
            return None
        pending.resolved = True
        pending.approved = approved
        return pending

    def get_pending(self, action_id: str) -> PendingAction | None:
        return self._pending.get(action_id)


session_store = SessionStore()
