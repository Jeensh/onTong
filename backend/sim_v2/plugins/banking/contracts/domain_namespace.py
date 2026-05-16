"""Banking 의 namespace constants + enums.

BANKING-DESIGN.md §2 + §6 — Banking 가상 system 의 namespace.
"""
from __future__ import annotations

import contextvars
from enum import Enum


class ApplicationStatus(str, Enum):
    """BANKING-DESIGN §2.4."""
    SUBMITTED = "SUBMITTED"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    CONDITIONAL = "CONDITIONAL"
    REJECTED = "REJECTED"
    CLOSED = "CLOSED"


class DecisionType(str, Enum):
    """Underwriting decision (BANKING-DESIGN §2.6)."""
    APPROVED = "APPROVED"
    CONDITIONAL = "CONDITIONAL"
    REJECTED = "REJECTED"


class LoanType(str, Enum):
    """Loan product type (BANKING-DESIGN §2.3)."""
    MORTGAGE = "MORTGAGE"
    AUTO = "AUTO"
    PERSONAL = "PERSONAL"
    BUSINESS = "BUSINESS"


class ComplianceCheckType(str, Enum):
    """Compliance check kind (BANKING-DESIGN §2.9)."""
    KYC = "KYC"
    AML = "AML"
    OFAC = "OFAC"
    GDPR = "GDPR"


class PaymentStatus(str, Enum):
    """Payment installment status (BANKING-DESIGN §2.8)."""
    PENDING = "PENDING"
    PAID = "PAID"
    LATE = "LATE"
    DEFAULTED = "DEFAULTED"


class DisbursementStatus(str, Enum):
    """Disbursement status (BANKING-DESIGN §2.7)."""
    SCHEDULED = "SCHEDULED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    REVERSED = "REVERSED"


class _TenantContextHolder:
    """ThreadLocal-equivalent tenant context.

    BANKING-DESIGN §6.1 — @TenantContext aspect 가 enforce 하는 contextvar.
    """
    _current: contextvars.ContextVar[str | None] = contextvars.ContextVar(
        "banking.tenant_id", default=None
    )

    def get_current_tenant_id(self) -> str | None:
        return self._current.get()

    def set(self, tenant_id: str | None) -> contextvars.Token:
        return self._current.set(tenant_id)

    def reset(self, token: contextvars.Token) -> None:
        self._current.reset(token)


TenantContextHolder = _TenantContextHolder()


class BankingConstants:
    """Banking 의 namespace constants (Java BankingConstants 의 mirror).

    BANKING-DESIGN.md §3 numeric convention — currency-specific decimal precision.
    """
    # Numeric scales
    CURRENCY_SCALE_USD = 2
    CURRENCY_SCALE_KRW = 0
    INTEREST_RATE_SCALE = 6     # 0.045500 (4.55%)
    LTV_SCALE = 4               # 0.9000 (90%)
    DTI_SCALE = 4

    # Underwriting thresholds (BANKING-DESIGN §5.1 sample rules)
    FICO_HARD_REJECT_BELOW = 580
    DTI_CONDITIONAL_ABOVE = 0.43
    LTV_PMI_REQUIRED_ABOVE = 0.90

    # Regulatory regions
    SUPPORTED_REGIONS = frozenset(["US", "EU", "KR"])

    # Tenant context holder reference (for emitter targeting)
    TENANT_HOLDER = TenantContextHolder
