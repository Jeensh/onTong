"""Banking plugin contract test — BANKING-DESIGN.md §11."""
from __future__ import annotations

from pathlib import Path

from backend.sim_v2.core.contracts.base import JavaContract, RoundingMode
from backend.sim_v2.core.plugin_loader import load_plugin
from backend.sim_v2.plugins.banking.contracts.base import BankingContract
from backend.sim_v2.plugins.banking.contracts.domain_namespace import (
    ApplicationStatus,
    BankingConstants,
    ComplianceCheckType,
    DecisionType,
    LoanType,
    PaymentStatus,
    TenantContextHolder,
)
from backend.sim_v2.plugins.banking.contracts.exception import (
    BankingException,
    BpmnDeploymentException,
    ComplianceException,
    DroolsEvaluationException,
    LoanApprovalException,
    MissingTenantException,
    SagaCompensatedException,
)

PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins" / "banking"


# ─────────────────────────────────────────────────────────────────────────────
# Plugin loader integration
# ─────────────────────────────────────────────────────────────────────────────


def test_plugin_loads_via_loader():
    info = load_plugin(PLUGIN_DIR, strict=True)
    assert info.name == "banking"
    assert info.manifest.fixtures.ids == ["BK1", "BK2", "BK3", "BK4", "BK5"]


def test_manifest_declares_4_extensions():
    info = load_plugin(PLUGIN_DIR, strict=True)
    exts = info.manifest.extensions
    assert exts.dispatchers == ["banking.drools_kbase_lookup"]
    assert exts.annotations == ["banking.compensable"]
    assert "banking.tenant_context" in exts.aop
    assert exts.bytecode == ["banking.bpmn_dynamic_class"]


# ─────────────────────────────────────────────────────────────────────────────
# BankingContract
# ─────────────────────────────────────────────────────────────────────────────


def test_banking_contract_is_java_contract():
    c = BankingContract()
    assert isinstance(c, JavaContract)


def test_exception_base_is_banking_exception():
    c = BankingContract()
    assert c.exception_base is BankingException


def test_exception_hierarchy():
    for sub in (
        LoanApprovalException,
        ComplianceException,
        MissingTenantException,
        SagaCompensatedException,
        DroolsEvaluationException,
        BpmnDeploymentException,
    ):
        assert issubclass(sub, BankingException), f"{sub.__name__} not subclass of BankingException"


def test_numeric_convention_decimal64_halfeven():
    c = BankingContract()
    nc = c.numeric_convention()
    assert nc.bigdecimal_precision == 16
    assert nc.bigdecimal_rounding == RoundingMode.HALF_EVEN
    # currency scale 2 (USD), 0 (KRW), 6 (interest rate)
    assert nc.domain_scales["currency.usd"] == 2
    assert nc.domain_scales["currency.krw"] == 0
    assert nc.domain_scales["interest.rate"] == 6
    assert nc.domain_scales["ltv"] == 4


def test_domain_namespace_exposes_all_enums():
    c = BankingContract()
    ns = c.domain_namespace()
    assert ns["BankingConstants"] is BankingConstants
    assert ns["ApplicationStatus"] is ApplicationStatus
    assert ns["DecisionType"] is DecisionType
    assert ns["LoanType"] is LoanType
    assert ns["ComplianceCheckType"] is ComplianceCheckType
    assert ns["PaymentStatus"] is PaymentStatus


def test_application_status_enum_values():
    assert {s.value for s in ApplicationStatus} == {
        "SUBMITTED", "IN_REVIEW", "APPROVED", "CONDITIONAL", "REJECTED", "CLOSED"
    }


def test_underwriting_thresholds():
    assert BankingConstants.FICO_HARD_REJECT_BELOW == 580
    assert BankingConstants.DTI_CONDITIONAL_ABOVE == 0.43
    assert BankingConstants.LTV_PMI_REQUIRED_ABOVE == 0.90


# ─────────────────────────────────────────────────────────────────────────────
# TenantContextHolder — BANKING-DESIGN §6.1
# ─────────────────────────────────────────────────────────────────────────────


def test_tenant_context_holder_default_none():
    # 새 context 에서 default tenant is None
    import contextvars
    ctx = contextvars.copy_context()
    def check():
        assert TenantContextHolder.get_current_tenant_id() is None
    ctx.run(check)


def test_tenant_context_holder_set_and_reset():
    token = TenantContextHolder.set("BANK_A")
    try:
        assert TenantContextHolder.get_current_tenant_id() == "BANK_A"
    finally:
        TenantContextHolder.reset(token)
    # After reset, back to None
    assert TenantContextHolder.get_current_tenant_id() is None


def test_banking_constants_exposes_tenant_holder():
    assert BankingConstants.TENANT_HOLDER is TenantContextHolder
