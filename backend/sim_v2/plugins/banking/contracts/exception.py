"""Banking domain exception hierarchy.

BANKING-DESIGN.md §3 + §7 — Banking loan origination 의 exception base + saga + compliance.
"""
from __future__ import annotations


class BankingException(Exception):
    """Root exception for Banking plugin."""


class LoanApprovalException(BankingException):
    """Underwriting / Approval decision exception."""


class ComplianceException(BankingException):
    """KYC / AML / OFAC / GDPR compliance check failure."""


class MissingTenantException(BankingException):
    """@TenantContext aspect 가 tenant_id 부재 시 발동 (BANKING-DESIGN §6.1)."""


class SagaCompensatedException(BankingException):
    """@Compensable saga 의 compensation 실행 시 raise (BANKING-DESIGN §7.2)."""


class DroolsEvaluationException(BankingException):
    """Underwriting rule fire 시 발생한 Drools 평가 오류."""


class BpmnDeploymentException(BankingException):
    """Activiti BPMN deploy 시 dynamic class 생성 실패."""
