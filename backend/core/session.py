"""Session store with JSONL persistence.

Messages are kept in-memory for fast access and appended to per-session
JSONL files so conversations survive server restarts.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from .schemas import ApprovalAction

logger = logging.getLogger(__name__)

_DEFAULT_DATA_DIR = Path("data/sessions")


@dataclass
class PendingAction:
    action_id: str
    session_id: str
    action: ApprovalAction
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    resolved: bool = False
    approved: bool | None = None


@dataclass
class SessionState:
    session_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    messages: list[dict] = field(default_factory=list)
    # L3 Path-Aware RAG: accumulated path preferences from disambiguation
    path_preferences: list[str] = field(default_factory=list)


class SessionStore:
    """Session storage with JSONL file persistence.

    Each session maps to ``data/sessions/{session_id}.jsonl``.
    Every message append is immediately flushed to disk.
    On startup, existing JSONL files are loaded back into memory.
    """

    def __init__(self, data_dir: Path | str | None = None) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._pending: dict[str, PendingAction] = {}
        self._data_dir = Path(data_dir) if data_dir else _DEFAULT_DATA_DIR
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._load_all()

    # ── Public API ───────────────────────────────────────────────

    def get_or_create_session(self, session_id: str) -> SessionState:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState(session_id=session_id)
        return self._sessions[session_id]

    def append_message(self, session_id: str, message: dict) -> None:
        """Add a message to the session and persist to JSONL."""
        session = self.get_or_create_session(session_id)
        session.messages.append(message)
        self._persist(session_id, message)

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

    # ── Persistence ──────────────────────────────────────────────

    def _session_path(self, session_id: str) -> Path:
        # Sanitize session_id to prevent path traversal
        safe_id = "".join(c for c in session_id if c.isalnum() or c in "-_")
        return self._data_dir / f"{safe_id}.jsonl"

    def _persist(self, session_id: str, message: dict) -> None:
        """Append a single message to the session's JSONL file."""
        path = self._session_path(session_id)
        try:
            record = {
                "ts": datetime.now(UTC).isoformat(),
                "role": message.get("role", ""),
                "content": message.get("content", ""),
            }
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            logger.warning(f"Failed to persist message for session {session_id}", exc_info=True)

    def _load_all(self) -> None:
        """Load all existing JSONL session files into memory."""
        if not self._data_dir.exists():
            return
        count = 0
        for path in self._data_dir.glob("*.jsonl"):
            session_id = path.stem
            messages = self._load_session_file(path)
            if messages:
                session = SessionState(session_id=session_id, messages=messages)
                self._sessions[session_id] = session
                count += 1
        if count:
            logger.info(f"Restored {count} sessions from {self._data_dir}")

    def _load_session_file(self, path: Path) -> list[dict]:
        """Parse a single JSONL file into a list of message dicts."""
        messages: list[dict] = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        messages.append({
                            "role": record.get("role", ""),
                            "content": record.get("content", ""),
                        })
                    except json.JSONDecodeError:
                        logger.warning(f"Skipping corrupt line in {path}")
        except Exception:
            logger.warning(f"Failed to load session file {path}", exc_info=True)
        return messages


session_store = SessionStore()
