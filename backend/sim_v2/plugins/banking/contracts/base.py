"""BankingContract — plugin contract for Banking loan origination 가상 system.

BANKING-DESIGN.md §11 + Lesson 4 §5.1.
"""
from __future__ import annotations

from typing import Any

from backend.sim_v2.core.contracts.base import (
    JavaContract,
    NumericConvention,
    RoundingMode,
)

from .domain_namespace import (
    ApplicationStatus,
    BankingConstants,
    ComplianceCheckType,
    DecisionType,
    DisbursementStatus,
    LoanType,
    PaymentStatus,
    TenantContextHolder,
)
from .exception import (
    BankingException,
    BpmnDeploymentException,
    ComplianceException,
    DroolsEvaluationException,
    LoanApprovalException,
    MissingTenantException,
    SagaCompensatedException,
)


class BankingContract(JavaContract):
    """Banking loan origination (가상) plugin contract.

    BANKING-DESIGN.md §1 — loan origination workflow + multi-tenant + Drools + BPMN + saga.
    4 plugin extension (ADR-013 §3): drools_kbase_lookup / @Compensable / @TenantContext / bpmn_dynamic_class.
    """

    @property
    def exception_base(self) -> type[Exception]:
        return BankingException

    def domain_namespace(self) -> dict[str, Any]:
        return {
            "BankingConstants":          BankingConstants,
            "ApplicationStatus":         ApplicationStatus,
            "DecisionType":              DecisionType,
            "LoanType":                  LoanType,
            "ComplianceCheckType":       ComplianceCheckType,
            "PaymentStatus":             PaymentStatus,
            "DisbursementStatus":        DisbursementStatus,
            "TenantContextHolder":       TenantContextHolder,
            "BankingException":          BankingException,
            "LoanApprovalException":     LoanApprovalException,
            "ComplianceException":       ComplianceException,
            "MissingTenantException":    MissingTenantException,
            "SagaCompensatedException":  SagaCompensatedException,
            "DroolsEvaluationException": DroolsEvaluationException,
            "BpmnDeploymentException":   BpmnDeploymentException,
        }

    def numeric_convention(self) -> NumericConvention:
        return NumericConvention(
            bigdecimal_precision=16,
            bigdecimal_rounding=RoundingMode.HALF_EVEN,
            domain_scales={
                "currency.usd":     BankingConstants.CURRENCY_SCALE_USD,    # 2
                "currency.krw":     BankingConstants.CURRENCY_SCALE_KRW,    # 0
                "interest.rate":    BankingConstants.INTEREST_RATE_SCALE,   # 6
                "ltv":              BankingConstants.LTV_SCALE,             # 4
                "dti":              BankingConstants.DTI_SCALE,             # 4
                "loan.principal":   2,                                       # USD scale
            },
        )
