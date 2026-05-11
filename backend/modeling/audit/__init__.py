"""Audit log infrastructure for modeling section PATCH endpoints.

Wave 1 (this module):
    - ORM (`AuditLogRow`) registered into Base.metadata
    - `record_audit` / `record_patch` recorder helpers
    - `audit_patch` context manager for PATCH handler integration

Wave 2 will hook `audit_patch` into each PATCH handler in queue_actions_api.py.

Designed for Phase 1 (1-3 users) but indexed for Phase 2 (5+ users, 100K docs).
"""
from backend.modeling.audit.orm import AuditLogRow
from backend.modeling.audit.recorder import record_audit, record_patch
from backend.modeling.audit.middleware import audit_patch

__all__ = ("AuditLogRow", "record_audit", "record_patch", "audit_patch")
