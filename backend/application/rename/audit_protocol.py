"""AuditStore Protocol — abstract base for wiki_audit + wiki_jobs persistence."""
from __future__ import annotations
from abc import ABC, abstractmethod
from .types import RenameAuditRow, RenameJobRow


class AuditStore(ABC):
    @abstractmethod
    def create_audit(self, op: str, actor: str, payload: dict) -> int:
        """Insert a new audit row with status='running', started_at=now(). Returns the id."""

    @abstractmethod
    def update_audit_status(self, audit_id: int, status: str, error: str | None = None) -> None:
        """Update status (success/partial/failed) + finished_at=now() + error."""

    @abstractmethod
    def get_audit(self, audit_id: int) -> RenameAuditRow | None: ...

    @abstractmethod
    def list_audits(self, *, actor: str | None = None, since: float | None = None,
                    op: str | None = None, status: str | None = None,
                    limit: int = 50) -> list[RenameAuditRow]: ...

    @abstractmethod
    def add_jobs(self, audit_id: int, jobs: list[tuple[str, str]]) -> int:
        """Insert pending jobs. jobs = [(kind, target_path), ...]. Returns count."""

    @abstractmethod
    def update_job(self, job_id: int, *, status: str, last_error: str | None = None,
                   increment_attempts: bool = True) -> None: ...

    @abstractmethod
    def list_jobs(self, audit_id: int, *, status: str | None = None) -> list[RenameJobRow]: ...

    @abstractmethod
    def progress(self, audit_id: int) -> dict:
        """Return { total, pending, running, done, failed } counts."""

    @abstractmethod
    def clear(self) -> None: ...
