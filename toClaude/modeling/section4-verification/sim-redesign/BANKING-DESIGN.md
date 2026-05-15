# BANKING-DESIGN — Banking 가상 시스템의 design specification

작성일: 2026-05-13 (implementation plan session)
관련 ADR: ADR-002 (Two-Engine + plugin), ADR-011 (3 systems), ADR-013 (Extensibility)
Track 위치: Track B Phase B3 (W4-W10) + Phase B5 (W12-W20) — MILESTONES-2track.md
Plugin 위치: `backend/sim_v2/plugins/banking/`
Cost estimate: 250-400h (ADR-011 §4) — 도메인 설계 100h + 구현 100-200h + plugin 작성 50-100h

---

## 0. TL;DR

Banking loan origination 의 controlled 가상 system. 본 doc 는 framework 의 stress test 를 위한 의도적 design — Drools / BPMN / multi-tenant / saga 의 4 meta-programming 영역 모두 cover.

**Scope**:
- 도메인: loan origination workflow + regulatory compliance
- LOC: ~30-50K Java (가상 — `sample-repos/banking-loan-twin/` 에 생성)
- Entity: ~20 (Applicant / Loan / LoanProduct / Tenant / CreditScore / Application / Underwriting / Approval / Disbursement / Payment / AuditLog / ComplianceCheck 등)
- Service: 6 layer
- Workflow: 6-step BPMN (Activiti)
- Meta-programming 영역 cover: ADR-006/007/008/009 모두

**Plugin extensions expected** (ADR-013):
- `banking.drools_kbase_lookup` (dispatch)
- `@Compensable` (annotation, saga pattern)
- `@TenantContext` (AOP, multi-tenant)
- `banking.bpmn_dynamic_class` (bytecode, Activiti deployment)

---

## 1. 도메인 — Loan Origination Process

### 1.1 Business workflow

```
Applicant submits loan application
  ↓
Application 등록 + 초기 validation
  ↓
Credit check (external bureau lookup)
  ↓
Underwriting (Drools rules engine)
  ├── Approved → Approval generation → Disbursement schedule
  ├── Conditional → Re-validation loop
  └── Rejected → Notification (terminal)
  ↓
Disbursement (배출) on approval
  ↓
Payment schedule generation
  ↓
[Lifecycle ongoing: Payment events / late notifications / closure]
```

### 1.2 Multi-tenant 요구

- Bank 별 tenant 분리 (Bank A, B, C, ...)
- Loan product 의 tenant-specific 정책 (interest rate, fee, eligibility)
- Underwriting rule 의 tenant-specific override
- 전체 data isolation: row-level `tenant_id` filter

### 1.3 Compliance / Audit 요구

- 모든 state transition 의 audit log (immutable append-only)
- Regulatory event (KYC, AML, OFAC) 의 별도 compliance log
- 모든 service call 의 @Aspect audit (`@TenantContext` aspect 와 동시)

---

## 2. Entity Model — ~20 entities

### 2.1 Tenant (multi-tenant 의 root)

```java
@Entity
@Table(name = "TENANT")
public class Tenant {
    @Id @GeneratedValue
    private Long id;
    
    @Column(unique = true)
    private String code;  // "BANK_A", "BANK_B", ...
    
    private String name;
    private String regulatoryRegion;  // "US", "EU", "KR"
    
    @OneToMany(mappedBy = "tenant")
    private List<LoanProduct> products;
    
    @OneToMany(mappedBy = "tenant")
    private List<UnderwritingRule> rules;
}
```

### 2.2 Applicant

```java
@Entity
@Table(name = "APPLICANT")
public class Applicant {
    @Id @GeneratedValue
    private Long id;
    
    private String tenantId;          // multi-tenant filter
    private String externalId;        // bank 내부 ID
    
    private String name;
    private String taxId;             // hashed
    private LocalDate birthDate;
    
    @Embedded
    private Address address;
    
    private BigDecimal annualIncome;
    private String employmentStatus;  // FULL_TIME / PART_TIME / SELF_EMPLOYED / UNEMPLOYED
}
```

### 2.3 LoanProduct

```java
@Entity
@Table(name = "LOAN_PRODUCT")
public class LoanProduct {
    @Id @GeneratedValue
    private Long id;
    
    @ManyToOne
    private Tenant tenant;
    
    private String code;              // "HOME_30Y_FIXED", "AUTO_60M", ...
    private String type;              // MORTGAGE / AUTO / PERSONAL / BUSINESS
    
    private BigDecimal minPrincipal;
    private BigDecimal maxPrincipal;
    private BigDecimal baseInterestRate;
    private Integer termMonths;
    
    @Embedded
    private Eligibility eligibility;  // minCreditScore, maxLTV, minIncome
}
```

### 2.4 Application + ApplicationStatus

```java
@Entity
@Table(name = "APPLICATION")
public class Application {
    @Id @GeneratedValue
    private Long id;
    
    private String tenantId;
    
    @ManyToOne
    private Applicant applicant;
    
    @ManyToOne
    private LoanProduct product;
    
    private BigDecimal requestedPrincipal;
    private LocalDate submittedAt;
    private LocalDate decisionDeadline;
    
    @Enumerated(EnumType.STRING)
    private ApplicationStatus status;  // SUBMITTED / IN_REVIEW / APPROVED / CONDITIONAL / REJECTED / CLOSED
    
    @OneToOne
    private CreditReport creditReport;
    
    @OneToOne
    private UnderwritingDecision underwritingDecision;
    
    @OneToMany(mappedBy = "application")
    private List<ApplicationDocument> documents;
}

public enum ApplicationStatus {
    SUBMITTED, IN_REVIEW, APPROVED, CONDITIONAL, REJECTED, CLOSED;
}
```

### 2.5 CreditScore / CreditReport / CreditBureau

```java
@Entity
@Table(name = "CREDIT_BUREAU")
public class CreditBureau {
    @Id
    private String code;              // "EXPERIAN", "EQUIFAX", "KOREA_CB"
    
    private String name;
    private String regulatoryRegion;
}

@Entity
@Table(name = "CREDIT_REPORT")
public class CreditReport {
    @Id @GeneratedValue
    private Long id;
    
    private String tenantId;
    
    @ManyToOne
    private CreditBureau bureau;
    
    @ManyToOne
    private Applicant applicant;
    
    private Integer fico;             // 300-850
    private Integer vantage;
    
    private LocalDate reportDate;
    private String reportPayload;     // raw JSON
}
```

### 2.6 UnderwritingRule / UnderwritingDecision

```java
@Entity
@Table(name = "UNDERWRITING_RULE")
public class UnderwritingRule {
    @Id @GeneratedValue
    private Long id;
    
    @ManyToOne
    private Tenant tenant;
    
    @ManyToOne
    private LoanProduct product;
    
    private String name;
    private String drlSource;         // Drools .drl source
    private String kieKbaseName;      // KIE base 식별자
    private Integer priority;
    
    private LocalDate effectiveFrom;
    private LocalDate effectiveTo;
}

@Entity
@Table(name = "UNDERWRITING_DECISION")
public class UnderwritingDecision {
    @Id @GeneratedValue
    private Long id;
    
    @OneToOne
    private Application application;
    
    @Enumerated(EnumType.STRING)
    private DecisionType type;        // APPROVED / CONDITIONAL / REJECTED
    
    private BigDecimal approvedPrincipal;
    private BigDecimal interestRate;
    private Integer termMonths;
    
    private String drlFiringTrace;    // Drools 발사된 rule sequence
    private String rationale;
}
```

### 2.7 Approval / Disbursement / Disbursement schedule

```java
@Entity
@Table(name = "APPROVAL")
public class Approval {
    @Id @GeneratedValue
    private Long id;
    
    @OneToOne
    private UnderwritingDecision decision;
    
    private LocalDate approvedAt;
    private String approvedBy;        // user
    
    private BigDecimal finalPrincipal;
    private BigDecimal finalInterestRate;
}

@Entity
@Table(name = "DISBURSEMENT")
public class Disbursement {
    @Id @GeneratedValue
    private Long id;
    
    @ManyToOne
    private Approval approval;
    
    private LocalDate scheduledAt;
    private LocalDate actualAt;
    private BigDecimal amount;
    
    @Enumerated(EnumType.STRING)
    private DisbursementStatus status;  // SCHEDULED / EXECUTED / FAILED / REVERSED
}

@Entity
@Table(name = "DISBURSEMENT_SCHEDULE")
public class DisbursementSchedule {
    // 분할 disbursement (e.g., 건설 자금 단계별)
    @Id @GeneratedValue
    private Long id;
    
    @ManyToOne
    private Approval approval;
    
    @OneToMany
    private List<Disbursement> tranches;
}
```

### 2.8 Payment / PaymentSchedule / PaymentEvent

```java
@Entity
@Table(name = "PAYMENT_SCHEDULE")
public class PaymentSchedule {
    @Id @GeneratedValue
    private Long id;
    
    @ManyToOne
    private Approval approval;
    
    @OneToMany(mappedBy = "schedule")
    private List<Payment> installments;
    
    private BigDecimal principalBalance;
    private BigDecimal interestBalance;
}

@Entity
@Table(name = "PAYMENT")
public class Payment {
    @Id @GeneratedValue
    private Long id;
    
    @ManyToOne
    private PaymentSchedule schedule;
    
    private Integer installmentNo;    // 1, 2, ..., termMonths
    private LocalDate dueDate;
    
    private BigDecimal principalPortion;
    private BigDecimal interestPortion;
    private BigDecimal totalAmount;
    
    @Enumerated(EnumType.STRING)
    private PaymentStatus status;     // PENDING / PAID / LATE / DEFAULTED
}

@Entity
@Table(name = "PAYMENT_EVENT")
public class PaymentEvent {
    // event sourcing — payment 의 모든 state transition log
    @Id @GeneratedValue
    private Long id;
    
    @ManyToOne
    private Payment payment;
    
    @Enumerated(EnumType.STRING)
    private PaymentEventType type;    // PAID / LATE / WAIVED / REVERSED
    
    private LocalDateTime occurredAt;
    private BigDecimal amount;
    private String memo;
}
```

### 2.9 AuditLog / ComplianceCheck / ApplicationDocument

```java
@Entity
@Table(name = "AUDIT_LOG")
public class AuditLog {
    // immutable append-only
    @Id @GeneratedValue
    private Long id;
    
    private String tenantId;
    private String entityType;        // "Application", "Disbursement", ...
    private Long entityId;
    
    private String operation;         // "CREATE", "UPDATE", "STATUS_CHANGE", ...
    private String before;            // JSON
    private String after;             // JSON
    
    private String actor;             // user or system
    private LocalDateTime timestamp;
}

@Entity
@Table(name = "COMPLIANCE_CHECK")
public class ComplianceCheck {
    @Id @GeneratedValue
    private Long id;
    
    private String tenantId;
    
    @ManyToOne
    private Application application;
    
    @Enumerated(EnumType.STRING)
    private ComplianceCheckType type;  // KYC / AML / OFAC / GDPR
    
    @Enumerated(EnumType.STRING)
    private ComplianceCheckStatus status;  // PASS / FAIL / WAIVE
    
    private String findings;
    private LocalDateTime checkedAt;
}

@Entity
@Table(name = "APPLICATION_DOCUMENT")
public class ApplicationDocument {
    @Id @GeneratedValue
    private Long id;
    
    @ManyToOne
    private Application application;
    
    private String type;              // "ID_PROOF", "INCOME_PROOF", "TAX_RETURN", ...
    private String storagePath;
    private String hash;
    private LocalDateTime uploadedAt;
}
```

### 2.10 Entity 총계

| Group | Entity |
|---|---|
| Tenant + Product | Tenant, LoanProduct (2) |
| Applicant | Applicant, ApplicationDocument (2) |
| Credit | CreditBureau, CreditReport, CreditScore (3, CreditScore 는 별도 entity 또는 CreditReport.fico 컬럼) |
| Application | Application, ApplicationStatus (2; enum 포함) |
| Underwriting | UnderwritingRule, UnderwritingDecision (2) |
| Approval / Disbursement | Approval, Disbursement, DisbursementSchedule (3) |
| Payment | Payment, PaymentSchedule, PaymentEvent (3) |
| Audit / Compliance | AuditLog, ComplianceCheck (2) |
| **Total** | **~20 entity** (enum 제외 시 18, 포함 시 22) |

---

## 3. Service Layers — 6 layer

```
ApplicationService           ← 진입점, BPMN orchestration
  ↓
CreditCheckService           ← external bureau lookup
  ↓
UnderwritingService          ← Drools KIE container 호출
  ↓
ApprovalService              ← decision → approval
  ↓
DisbursementService          ← schedule 생성 + actual 실행
  ↓
PaymentService               ← lifecycle ongoing (event sourcing)

(직교 layer)
ComplianceService            ← KYC/AML/OFAC, 모든 service call 의 @Aspect 로 호출
```

### 3.1 ApplicationService

```java
@Service
@TenantContext  // multi-tenant aspect
public class ApplicationService {
    @Autowired
    private ApplicationRepository applicationRepo;
    
    @Autowired
    private RuntimeService activitiRuntime;  // Activiti BPMN engine
    
    @Transactional
    public Application submit(SubmitApplicationCommand cmd) {
        // 1. Validate
        // 2. Create Application
        // 3. Start BPMN process: deployBpmn("loan_origination") 후 startProcessInstanceByKey
        // 4. Audit log
        return application;
    }
}
```

### 3.2 UnderwritingService

```java
@Service
@TenantContext
public class UnderwritingService {
    @Autowired
    private KieContainer kieContainer;        // Drools
    
    @Autowired
    private UnderwritingRuleRepository ruleRepo;
    
    @Transactional
    public UnderwritingDecision underwrite(Application app) {
        // 1. Tenant 의 active rule 조회
        // 2. Drools KieSession 생성: kieContainer.newKieSession(kbaseName + "-session")
        // 3. Insert facts (Application + Applicant + CreditReport + LoanProduct)
        // 4. Fire rules: session.fireAllRules()
        // 5. Extract decision from working memory
        // 6. drlFiringTrace 수집 (kie audit log)
        return decision;
    }
}
```

---

## 4. BPMN Workflow — Loan Origination (Activiti)

### 4.1 Process definition (`loan_origination.bpmn20.xml`)

```xml
<process id="loan_origination" name="Loan Origination Process">
  <startEvent id="start"/>
  
  <serviceTask id="initialValidation" 
               activiti:class="bank.workflow.InitialValidationDelegate"/>
  <sequenceFlow sourceRef="start" targetRef="initialValidation"/>
  
  <serviceTask id="creditCheck"
               activiti:class="bank.workflow.CreditCheckDelegate"/>
  <sequenceFlow sourceRef="initialValidation" targetRef="creditCheck"/>
  
  <serviceTask id="underwriting"
               activiti:class="bank.workflow.UnderwritingDelegate"/>
  <sequenceFlow sourceRef="creditCheck" targetRef="underwriting"/>
  
  <exclusiveGateway id="decisionGateway"/>
  <sequenceFlow sourceRef="underwriting" targetRef="decisionGateway"/>
  
  <serviceTask id="approval"
               activiti:class="bank.workflow.ApprovalDelegate"/>
  <sequenceFlow sourceRef="decisionGateway" targetRef="approval">
    <conditionExpression>${decision == 'APPROVED'}</conditionExpression>
  </sequenceFlow>
  
  <userTask id="conditionalReview"/>
  <sequenceFlow sourceRef="decisionGateway" targetRef="conditionalReview">
    <conditionExpression>${decision == 'CONDITIONAL'}</conditionExpression>
  </sequenceFlow>
  
  <endEvent id="rejected"/>
  <sequenceFlow sourceRef="decisionGateway" targetRef="rejected">
    <conditionExpression>${decision == 'REJECTED'}</conditionExpression>
  </sequenceFlow>
  
  <serviceTask id="disbursement"
               activiti:class="bank.workflow.DisbursementDelegate"/>
  <sequenceFlow sourceRef="approval" targetRef="disbursement"/>
  
  <serviceTask id="paymentScheduleGen"
               activiti:class="bank.workflow.PaymentScheduleDelegate"/>
  <sequenceFlow sourceRef="disbursement" targetRef="paymentScheduleGen"/>
  
  <endEvent id="completed"/>
  <sequenceFlow sourceRef="paymentScheduleGen" targetRef="completed"/>
</process>
```

### 4.2 Meta-programming implications

- Activiti runtime 이 BPMN deploy 시 dynamic class 생성 — `bank.workflow.InitialValidationDelegate` 등의 reference 가 deploy 시점에 instantiated
- ADR-009 (bytecode generation) 의 적용 영역
- Plugin extension: `banking.bpmn_dynamic_class` — Activiti 의 dynamic class loading 의 Python emulator

---

## 5. Drools Rule Sample — Underwriting

### 5.1 Rule sample (`underwriting/BANK_A/HOME_30Y_FIXED.drl`)

```drools
package bank.underwriting.bank_a

import bank.domain.Application
import bank.domain.Applicant
import bank.domain.CreditReport
import bank.domain.LoanProduct
import bank.domain.UnderwritingDecision

global UnderwritingDecisionBuilder decisionBuilder

// Rule 1: Hard reject — credit score too low
rule "Reject if FICO < 580"
    salience 100
    when
        $app: Application(status == "IN_REVIEW")
        $report: CreditReport(applicant.id == $app.applicant.id, fico < 580)
    then
        decisionBuilder.setType("REJECTED");
        decisionBuilder.setRationale("FICO score below product minimum: " + $report.getFico());
end

// Rule 2: Income / payment ratio (DTI) — soft conditional
rule "Conditional if DTI > 43%"
    salience 80
    when
        $app: Application(requestedPrincipal != null)
        $applicant: Applicant(annualIncome != null, this == $app.applicant)
        eval(($app.estimateMonthlyPayment().doubleValue() * 12.0) / 
             $applicant.getAnnualIncome().doubleValue() > 0.43)
    then
        decisionBuilder.setType("CONDITIONAL");
        decisionBuilder.appendCondition("DTI exceeds 43% — requires manual review");
end

// Rule 3: LTV check (for mortgage)
rule "Conditional if LTV > 90% (mortgage)"
    salience 70
    when
        $app: Application()
        $product: LoanProduct(type == "MORTGAGE", this == $app.product)
        eval($app.getRequestedPrincipal().doubleValue() / 
             $app.getCollateralValue().doubleValue() > 0.90)
    then
        decisionBuilder.setType("CONDITIONAL");
        decisionBuilder.appendCondition("LTV exceeds 90% — requires PMI");
end

// Rule 4: Default approve if no other rule fired
rule "Approve by default"
    salience 1
    when
        $app: Application(status == "IN_REVIEW")
        not (UnderwritingDecisionBuilder(type == "REJECTED"))
    then
        decisionBuilder.setType("APPROVED");
end
```

### 5.2 Meta-programming implications

- Drools KIE container 가 `.drl` 파일을 runtime 에 compile + load
- Rule 의 LHS / RHS 가 Java reflection 기반 fact-matching
- ADR-006 (polymorphic dispatch) 의 적용 — Drools dispatch 는 8 dispatch_kind 외 9번째 candidate
- Plugin extension: `banking.drools_kbase_lookup` — Drools KIE container 의 Python equivalent emit

**Python twin 합성 시점**:
- Default: SIGNATURE_LOCKED (Drools 자체의 Python 구현 없음)
- Extension: `backend/sim_v2/plugins/banking/dispatchers/drools_kbase_lookup.py` 가 .drl 파일 의 simple decision tree 추출, Python if-elif chain 으로 emit

---

## 6. Multi-tenant via Spring AOP — @TenantContext

### 6.1 Aspect 정의

```java
@Aspect
@Component
public class TenantContextAspect {
    @Around("@within(bank.annotation.TenantContext) || @annotation(bank.annotation.TenantContext)")
    public Object enforceTenant(ProceedingJoinPoint pjp) throws Throwable {
        String tenantId = TenantContextHolder.getCurrentTenantId();
        if (tenantId == null) {
            throw new MissingTenantException();
        }
        
        // Hibernate filter 설정
        Session session = entityManager.unwrap(Session.class);
        Filter filter = session.enableFilter("tenantFilter");
        filter.setParameter("tenantId", tenantId);
        
        try {
            return pjp.proceed();
        } finally {
            session.disableFilter("tenantFilter");
        }
    }
}
```

### 6.2 Hibernate filter (entity 의 @FilterDef)

```java
@FilterDef(name = "tenantFilter", parameters = @ParamDef(name = "tenantId", type = "string"))
@Filter(name = "tenantFilter", condition = "tenant_id = :tenantId")
@MappedSuperclass
public abstract class TenantOwnedEntity {
    @Column(name = "tenant_id", nullable = false)
    private String tenantId;
}
```

### 6.3 Meta-programming implications

- @TenantContext annotation 의 custom processor (annotation processing)
- @Aspect 의 @Around weaving (AOP)
- Hibernate filter 의 dynamic activation
- ADR-007 (annotation) + ADR-008 (AOP) 의 적용
- Plugin extension: `@TenantContext` 의 aspect handler — `backend/sim_v2/plugins/banking/aop/tenant_context.py`

---

## 7. Saga Pattern — @Compensable

### 7.1 Annotation + handler

```java
public @interface Compensable {
    String compensationMethod() default "";
}

@Service
public class DisbursementService {
    @Compensable(compensationMethod = "reverseDisbursement")
    @Transactional
    public void execute(Disbursement disbursement) {
        // 실제 자금 이체
    }
    
    public void reverseDisbursement(Disbursement disbursement) {
        // compensation — 이체 reversal
    }
}
```

### 7.2 Saga orchestrator

```java
@Component
public class SagaOrchestrator {
    public <T> T executeWithSaga(Supplier<T> primaryAction, Runnable compensation) {
        try {
            return primaryAction.get();
        } catch (Exception e) {
            compensation.run();
            throw new SagaCompensatedException(e);
        }
    }
}
```

### 7.3 Meta-programming implications

- @Compensable annotation 의 custom processor
- Saga orchestrator 가 reflection 으로 compensationMethod 호출 — bytecode 영역
- ADR-007 (annotation) + ADR-009 (bytecode) 의 적용
- Plugin extension: `@Compensable` 의 annotation handler — `backend/sim_v2/plugins/banking/annotations/compensable.py`

---

## 8. DDL — Database Schema

### 8.1 Core tables (PostgreSQL convention)

```sql
-- Tenant
CREATE TABLE tenant (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    regulatory_region VARCHAR(20) NOT NULL
);

-- Applicant
CREATE TABLE applicant (
    id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(50) NOT NULL,
    external_id VARCHAR(100),
    name VARCHAR(200) NOT NULL,
    tax_id_hash VARCHAR(128),
    birth_date DATE,
    address_street VARCHAR(200),
    address_city VARCHAR(100),
    address_state VARCHAR(50),
    address_country VARCHAR(2),
    address_zip VARCHAR(20),
    annual_income NUMERIC(15, 2),
    employment_status VARCHAR(30),
    CONSTRAINT fk_applicant_tenant FOREIGN KEY (tenant_id) REFERENCES tenant(code)
);

CREATE INDEX idx_applicant_tenant ON applicant(tenant_id);

-- LoanProduct
CREATE TABLE loan_product (
    id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(50) NOT NULL,
    code VARCHAR(50) NOT NULL,
    type VARCHAR(30) NOT NULL,
    min_principal NUMERIC(15, 2) NOT NULL,
    max_principal NUMERIC(15, 2) NOT NULL,
    base_interest_rate NUMERIC(7, 4) NOT NULL,
    term_months INTEGER NOT NULL,
    min_credit_score INTEGER,
    max_ltv NUMERIC(5, 4),
    min_income NUMERIC(15, 2),
    UNIQUE (tenant_id, code),
    CONSTRAINT fk_product_tenant FOREIGN KEY (tenant_id) REFERENCES tenant(code)
);

-- Application
CREATE TABLE application (
    id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(50) NOT NULL,
    applicant_id BIGINT NOT NULL REFERENCES applicant(id),
    product_id BIGINT NOT NULL REFERENCES loan_product(id),
    requested_principal NUMERIC(15, 2) NOT NULL,
    submitted_at DATE NOT NULL,
    decision_deadline DATE,
    status VARCHAR(20) NOT NULL,
    credit_report_id BIGINT REFERENCES credit_report(id),
    underwriting_decision_id BIGINT REFERENCES underwriting_decision(id)
);

CREATE INDEX idx_application_tenant ON application(tenant_id);
CREATE INDEX idx_application_status ON application(tenant_id, status);

-- CreditBureau / CreditReport
CREATE TABLE credit_bureau (
    code VARCHAR(30) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    regulatory_region VARCHAR(20)
);

CREATE TABLE credit_report (
    id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(50) NOT NULL,
    bureau_code VARCHAR(30) NOT NULL REFERENCES credit_bureau(code),
    applicant_id BIGINT NOT NULL REFERENCES applicant(id),
    fico INTEGER,
    vantage INTEGER,
    report_date DATE NOT NULL,
    report_payload TEXT
);

CREATE INDEX idx_credit_report_applicant ON credit_report(tenant_id, applicant_id, report_date DESC);

-- UnderwritingRule
CREATE TABLE underwriting_rule (
    id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(50) NOT NULL,
    product_id BIGINT NOT NULL REFERENCES loan_product(id),
    name VARCHAR(100) NOT NULL,
    drl_source TEXT NOT NULL,
    kie_kbase_name VARCHAR(100) NOT NULL,
    priority INTEGER NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE
);

-- UnderwritingDecision
CREATE TABLE underwriting_decision (
    id SERIAL PRIMARY KEY,
    application_id BIGINT UNIQUE NOT NULL REFERENCES application(id),
    type VARCHAR(20) NOT NULL,
    approved_principal NUMERIC(15, 2),
    interest_rate NUMERIC(7, 4),
    term_months INTEGER,
    drl_firing_trace TEXT,
    rationale TEXT
);

-- Approval
CREATE TABLE approval (
    id SERIAL PRIMARY KEY,
    decision_id BIGINT UNIQUE NOT NULL REFERENCES underwriting_decision(id),
    approved_at DATE NOT NULL,
    approved_by VARCHAR(100) NOT NULL,
    final_principal NUMERIC(15, 2) NOT NULL,
    final_interest_rate NUMERIC(7, 4) NOT NULL
);

-- Disbursement
CREATE TABLE disbursement_schedule (
    id SERIAL PRIMARY KEY,
    approval_id BIGINT NOT NULL REFERENCES approval(id)
);

CREATE TABLE disbursement (
    id SERIAL PRIMARY KEY,
    schedule_id BIGINT NOT NULL REFERENCES disbursement_schedule(id),
    scheduled_at DATE NOT NULL,
    actual_at DATE,
    amount NUMERIC(15, 2) NOT NULL,
    status VARCHAR(20) NOT NULL
);

-- Payment / Schedule / Event
CREATE TABLE payment_schedule (
    id SERIAL PRIMARY KEY,
    approval_id BIGINT UNIQUE NOT NULL REFERENCES approval(id),
    principal_balance NUMERIC(15, 2) NOT NULL,
    interest_balance NUMERIC(15, 2) NOT NULL
);

CREATE TABLE payment (
    id SERIAL PRIMARY KEY,
    schedule_id BIGINT NOT NULL REFERENCES payment_schedule(id),
    installment_no INTEGER NOT NULL,
    due_date DATE NOT NULL,
    principal_portion NUMERIC(15, 2) NOT NULL,
    interest_portion NUMERIC(15, 2) NOT NULL,
    total_amount NUMERIC(15, 2) NOT NULL,
    status VARCHAR(20) NOT NULL,
    UNIQUE (schedule_id, installment_no)
);

CREATE TABLE payment_event (
    id SERIAL PRIMARY KEY,
    payment_id BIGINT NOT NULL REFERENCES payment(id),
    type VARCHAR(20) NOT NULL,
    occurred_at TIMESTAMP NOT NULL,
    amount NUMERIC(15, 2),
    memo TEXT
);

CREATE INDEX idx_payment_event_payment ON payment_event(payment_id, occurred_at);

-- Audit / Compliance
CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(50) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id BIGINT NOT NULL,
    operation VARCHAR(30) NOT NULL,
    before_json TEXT,
    after_json TEXT,
    actor VARCHAR(100) NOT NULL,
    timestamp TIMESTAMP NOT NULL
);

CREATE INDEX idx_audit_entity ON audit_log(tenant_id, entity_type, entity_id);
CREATE INDEX idx_audit_timestamp ON audit_log(tenant_id, timestamp DESC);

CREATE TABLE compliance_check (
    id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(50) NOT NULL,
    application_id BIGINT NOT NULL REFERENCES application(id),
    type VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    findings TEXT,
    checked_at TIMESTAMP NOT NULL
);

CREATE TABLE application_document (
    id SERIAL PRIMARY KEY,
    application_id BIGINT NOT NULL REFERENCES application(id),
    type VARCHAR(50) NOT NULL,
    storage_path VARCHAR(500) NOT NULL,
    hash VARCHAR(128) NOT NULL,
    uploaded_at TIMESTAMP NOT NULL
);
```

총 17 table + index. ADR-004 의 Schema Layer 의 첫 stress test.

### 8.2 Migration version

```sql
-- migrations/banking/v1__initial_schema.sql
-- (위 DDL 의 모든 CREATE TABLE / INDEX)

-- Schema layer 등록 (ADR-004)
INSERT INTO schema_migration (system, version, sha256) 
VALUES ('banking', 'v1', '<sha256 of v1.sql>');
```

---

## 9. Plugin 의 7 artifact 매핑

| # | Artifact | 내용 |
|---|---|---|
| 1 | `contracts/base.py` | BankingContract — `BankingException` exception base, NumericConvention (currency 2 decimal HALF_EVEN), TenantContext namespace |
| 2 | `entities/` | Java AST 자동 추출 (sample-repos/banking-loan-twin/) ~20 entity |
| 3 | `mappings/` | Section 2 ontology 자동 import, BANKING-DESIGN 의 BusinessTerm 매핑 (Loan, Approval, Disbursement 등) |
| 4 | `emitters/` | 17 generic emitter + 4-6 plugin-specific (drools_kbase_lookup, bpmn_dynamic_class 등) |
| 5 | `fixtures/` | 5 fixture — BK1 (happy path), BK2 (rejected), BK3 (conditional + manual review loop), BK4 (saga compensation), BK5 (multi-tenant + Drools rule firing) |
| 6 | `aspects/` | TenantContextAspect, ComplianceAspect, AuditAspect, CompensableAspect |
| 7 | `manifest.toml` | extensions: 4 plugin-specific (drools_kbase_lookup, compensable, tenant_context, bpmn_dynamic_class) |

---

## 10. Plugin extensions (ADR-013 §3 의 banking row 정식)

### 10.1 `banking.drools_kbase_lookup` (dispatcher extension)

```python
# backend/sim_v2/plugins/banking/dispatchers/drools_kbase_lookup.py

from core.synthesizer.dispatchers import DispatcherBase, register_dispatcher

class DroolsKbaseLookupDispatcher(DispatcherBase):
    """Drools KIE container 의 fireAllRules() 의 Python equivalent emit.
    
    .drl 파일 의 LHS pattern matching → Python decision tree (if-elif chain).
    Strong assumption: rule 의 LHS 가 simple eval / equality / range — complex Drools backward chaining 은 SIGNATURE_LOCKED.
    """
    kind = "banking.drools_kbase_lookup"
    
    def synthesize(self, call_site):
        # 1. Drools .drl source 추출 (UnderwritingRule.drl_source)
        # 2. Parse LHS into decision tree
        # 3. Emit Python equivalent
        ...

register_dispatcher("banking.drools_kbase_lookup", DroolsKbaseLookupDispatcher())
```

### 10.2 `@Compensable` (annotation extension)

```python
# backend/sim_v2/plugins/banking/annotations/compensable.py

from core.synthesizer.annotations import AnnotationHandlerBase, register_annotation_handler

class CompensableHandler(AnnotationHandlerBase):
    """@Compensable annotation 의 Python equivalent.
    
    Saga pattern: primaryAction 실행 후 exception 시 compensationMethod 호출.
    """
    annotation = "Compensable"
    
    def emit_wrapper(self, method_ast, annotation_args):
        # 1. method 의 wrapper 생성 — try/except 에 compensationMethod 호출
        ...

register_annotation_handler("Compensable", CompensableHandler())
```

### 10.3 `@TenantContext` (AOP extension)

```python
# backend/sim_v2/plugins/banking/aop/tenant_context.py

from core.synthesizer.aop import AspectBase, register_aspect

class TenantContextAspect(AspectBase):
    """@TenantContext aspect 의 Python equivalent.
    
    @Around weaving — service method 실행 시 tenantId 검사 + Hibernate filter 활성화.
    """
    name = "banking.tenant_context"
    
    def weave(self, method_ast):
        # 1. method 의 wrapper 생성 — tenantId 검사
        # 2. Hibernate filter 호출 (Python: SQL WHERE tenant_id = ?)
        ...

register_aspect("banking.tenant_context", TenantContextAspect())
```

### 10.4 `banking.bpmn_dynamic_class` (bytecode extension)

```python
# backend/sim_v2/plugins/banking/bytecode/bpmn_dynamic_class.py

from core.synthesizer.bytecode import BytecodeHandlerBase, register_bytecode_handler

class BpmnDynamicClassHandler(BytecodeHandlerBase):
    """Activiti BPMN deployment 시 dynamic class 생성 의 Python equivalent.
    
    .bpmn20.xml 의 activiti:class reference → Python class registry lookup.
    """
    pattern = "activiti_bpmn_deploy"
    
    def synthesize(self, deployment_context):
        # 1. .bpmn20.xml parse
        # 2. activiti:class reference 추출
        # 3. Python class registry 생성 (모든 referenced JavaDelegate)
        ...

register_bytecode_handler("activiti_bpmn_deploy", BpmnDynamicClassHandler())
```

---

## 11. 5 fixture scenarios (BK1-BK5)

| Fixture | 시나리오 | Meta-programming 의도 cover |
|---|---|---|
| BK1 | Happy path — Application submit → CR check → Underwrite (default approve) → Approval → Disbursement → PaymentSchedule | All 4 영역 light path |
| BK2 | Rejected — FICO < 580, Drools rule 1 발사 → REJECTED terminal | Drools rule firing (ADR-009 emulation) |
| BK3 | Conditional — DTI > 43%, rule 2 발사 → CONDITIONAL → user task → re-validation → APPROVED | BPMN user task 처리 + multi-step |
| BK4 | Saga compensation — Disbursement.execute() throws, @Compensable reverseDisbursement 발동, Approval rollback | @Compensable annotation + Saga orchestrator |
| BK5 | Multi-tenant — Bank A의 application 이 Bank B 의 rule 으로 검사 시도 → MissingTenantException, @TenantContext aspect 정상 차단 | @TenantContext aspect (ADR-008) + Hibernate filter |

5 fixture 가 ADR-006/007/008/009 4 영역 + multi-tenant + saga 모두 cover. ADR-011 의 G2 gate (W14) 의 Banking 의 입력.

---

## 12. Acceptance criteria

### 12.1 G1 gate (W10)

- 7 artifact 모두 작성 완료
- Entity 추출: ~20 entity (위 §2.10 의 총계)
- Mapping confirmed_rate >= 90%
- 5 fixture (BK1-BK5) pytest PASS
- Anti-pattern (Lesson 1 의 5 KNOWN_DIVERGENCE) 0 hit
- Multi-tenant Hibernate filter 의 R3 보장 (Bank A query 시 Bank B data 미반환)

### 12.2 G2 gate (W14)

- ADR-006 (polymorphic dispatch): Drools KIE container 의 banking.drools_kbase_lookup extension 작동
- ADR-007 (annotation): @Compensable + @TenantContext 의 plugin extension 작동
- ADR-008 (AOP): TenantContextAspect / AuditAspect 의 weaving 작동
- ADR-009 (bytecode): banking.bpmn_dynamic_class 의 BPMN deployment emulation 작동

### 12.3 G4 gate (W20+)

- 4 plugin extension (drools / compensable / tenant / bpmn) 의 framework core 변경 없이 흡수 — ADR-013 §6.3 의 Phase 2 통과
- 새 meta-programming case 추가 시 framework 자체 변경 X 의 검증

---

## 13. Risk + contingency

| Risk | Impact | Mitigation |
|---|---|---|
| 가상 system 의 design 이 100h 안에 못 끝남 | High | Iteration 1 — entity model + service layer + 1 BPMN process + 5 Drools rule sample 만 (~80h). Iteration 2 — 나머지 |
| Drools / Activiti 의 의도 부족 → meta-programming stress test 실패 | High | 본 doc 의 §5 / §4 / §6 / §7 / §10 의 4 plugin extension 명시 — 실제 .drl / .bpmn20.xml 작성 |
| Multi-tenant 의 Python twin 합성 trap | Medium | TenantContext 의 lazy filter activation 의 Python equivalent — emitter test 의 W6 prototype |
| Saga compensation 의 trace 보장 | Medium | @Compensable 의 wrapper 가 audit log emit 의무. Fixture BK4 의 expected_trace 가 compensation event 포함 |
| Banking 가상 → real-world 검증력 의 약함 | Medium (ADR-011 §6 risk) | Broadleaf 가 real-world 보완. Banking 은 의도된 meta-programming coverage 의 stress |
| Cost spike — 400h+ | Medium (D6 cost 명시) | M1 (W4) gate 후 cost re-estimate. 도메인 설계 100h 안에 entity model + 1 BPMN process + 5 Drools rule 만 — full coverage 는 W6-W8 |

---

## 14. 참조

### ADRs
- ADR-002 (plugin contract) — 7 artifact 의 source
- ADR-006 (polymorphic dispatch) — Drools dispatcher
- ADR-007 (annotation) — @Compensable / @TenantContext
- ADR-008 (AOP) — TenantContextAspect / AuditAspect
- ADR-009 (bytecode) — BPMN deployment + CGLib
- ADR-011 (3 systems) — Banking 의 의도 + cost 250-400h
- ADR-013 (extensibility) — 4 plugin extension

### Related plan artifacts
- `BROADLEAF-ONBOARDING.md` — Broadleaf community (sibling plugin)
- `V2-MIGRATION.md` — v2 plugin onboarding (sibling)
- `implementation-plan.md` — Track B Phase B3 의 본 design 의 sprint task
- `lessons/phase-alpha-*.md` — 5 lessons (사전 학습)

### External references (가상 system 의 design 참조 가능)
- Drools Documentation v8.x (KIE container, .drl syntax)
- Activiti BPMN 2.0 (process / service task / gateway)
- Hibernate @Filter (multi-tenant pattern)
- Saga orchestration pattern (Microservices.io, Chris Richardson)

### 메모리
- `feedback_simulation_design.md` — no MVP, 풀 시연 필수
