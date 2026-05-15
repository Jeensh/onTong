# ADR-011: 2nd reference systems selection and onboarding plan

작성일: 2026-05-13
상태: 확정 (사용자 결정, 2026-05-13 spec session)
선행: ADR-001 (Python twin), ADR-002 (Two-Engine + plugin)
관련 결정: D3 (실제 2nd system), M-D3 (병행), D6 (50-400h 수용), M-D4 (확장)

## 컨텍스트

Round 2 종합 (`SYNTHESIS-ROUND2.html`) 의 Two-Engine Plugin Framework 가 system-agnostic 을 주장하나, 검증 대상이 v2 하나 뿐:
- Skeptic M1 ("category error") 의 정면 risk — v2 의 specifics 가 framework 의 hidden assumption 으로 굳어질 위험
- ADR-002 의 plugin 추상화가 실제 universality 인지 falsifiable test 부재

DECISIONS-CONFIRMED.md 의 D3 (`실제 2nd system 선정`) 가 이 risk 의 명시적 해소:
> spec 단계에서 실제 2nd system 선정 + onboarding 시작. v2 + 실제 2nd system 동시 onboarding 으로 framework universality 검증

M-D3 (병행) 는 v2 verification 과 framework generalization 의 2 track 동시 진행 결정. D6 (50-400h 수용) 는 per-system onboarding cost 의 명시적 수용. 사용자 메모리 `feedback_simulation_design.md` ("no MVP, 풀 시연 필수") 와 결합 시 strong universality test 필요.

## 결정

**Hybrid 전략, 3 reference systems 완전 병렬 onboarding**.

### 1. 3 systems selection

| # | System | Type | LOC | 도메인 | 주요 meta-programming 영역 |
|---|---|---|---|---|---|
| 1 | **v2** (onTong slab-design twin) | Internal Java | ~5-10K | onTong 자체 도메인 (slab manufacturing) | Phase α 학습 자산 reference 후 새 plugin 처음부터 (D2 폐기) |
| 2 | **Broadleaf Commerce (community)** | Real OSS legacy | ~200K+ | E-commerce | Spring DI / JPA / @Aspect / CGLib proxy / @Configurable / production-grade meta-programming |
| 3 | **Banking loan origination** | 가상 (controlled) | 추정 ~30-50K | Banking workflow + regulatory | Drools rules engine / Activiti BPMN / multi-tenant / saga pattern / @Aspect audit log |

### 2. Selection criteria (post-hoc justification)

| 기준 | v2 | Broadleaf | Banking |
|---|---|---|---|
| Spring DI / JPA / @Transactional | ✓ | ✓ (heavy) | ✓ |
| 50-100K LOC (meaningful onboarding test) | △ (~10K, baseline) | ✓ (200K+, stress test) | ✓ (~30-50K, mid-range) |
| 도메인 이해 가능 | ✓ (internal) | ✓ (universal) | ✓ (사용자 설계) |
| Public access | △ (internal, controlled) | ✓ (community OSS) | ✓ (자체 작성) |
| Meta-programming coverage (ADR-006~009) | △ (Case 1-2 minimal) | ✓ (4 영역 모두) | ✓ (의도적 포함) |

3 systems 는 **complementary coverage** — Broadleaf 가 real-world stress, Banking 이 의도 설계로 보완, v2 가 internal baseline.

### 3. Onboarding strategy: 완전 병렬

3 system 모두 동시 onboarding. M-D3 (병행) 의 가장 aggressive 적용.

**근거**:
- Cross-validate 압력 최대 — framework 의 v2-specific bias 가 즉시 노출
- Plugin contract 의 strict 정의 강제 — sequential 이면 v2 가 leaked
- 사용자 메모리 `feedback_simulation_design.md` ("no MVP, 풀 시연 필수") 와 일관

### 4. Onboarding cost (D6 범위 명시)

| System | 추정 cost | 분해 |
|---|---|---|
| v2 | 100-200h | Phase α reference 50h + plugin 재작성 50-150h |
| Broadleaf | 300-400h | Codebase 학습 100h + plugin 작성 200-300h |
| Banking | 250-400h | 도메인 설계 100h + 구현 100-200h + plugin 작성 50-100h |
| **Total** | **650-1000h** | 3인 팀, 6-12 month |

### 5. Cross-validate gates (M-D3 병행 일관)

```
G1 (Month 1) — Framework core contract 검증
  - 3 system 각각 UC1 (풀 시연) 1건 성공
  - plugin contract 의 7 artifact 모두 작성됨
  - 동일 input → 동일 output (R3) 보장 확인

G2 (Month 2) — Meta-programming 4 영역 coverage
  - ADR-006 (polymorphic): 8 dispatch_kind 각 system 에서 등장 빈도
  - ADR-007 (annotation): Lombok / custom processor 각 system 처리
  - ADR-008 (AOP): @Aspect weaving 각 system 처리
  - ADR-009 (bytecode): CGLib / custom plugin 각 system 처리

G3 (Month 3) — Recommendation Engine 검증
  - 3 system 모두에서 LLM 의 reasonable proposal 생성 (LLM-agnostic, D5)
  - Recommendation Engine 의 4 방어 mechanism (ADR-005) 작동
  - LLM provider 최소 2개 (Claude + GPT) 에서 동등 quality

G4+ (Month 4+) — Extension architecture validation
  - Banking 의 Drools integration 이 plugin extension 으로 흡수
  - Broadleaf 의 enterprise-specific meta-programming case 가 SIGNATURE_LOCKED 또는 extension 으로 처리
  - 새 meta-programming case 추가 시 framework 자체 변경 X (M-D4 확인)
```

### 6. Risk + mitigation

| Risk | Impact | Mitigation |
|---|---|---|
| Cost spike (650-1000h 동시) | High | M1 gate 후 cost re-estimate 의무. 3인 팀 6-12 month 분산 |
| 3-way churn (conflicting signal) | Medium | plugin contract strict from day 1. Cross-validate gate 빈도 ↑ |
| Banking 가상 → real-world 검증력 약함 | Medium | Drools + multi-tenant + saga 의도적 포함. Broadleaf 가 real-world 보완 |
| Broadleaf enterprise-only feature 결손 | Low | Community edition 한정. Enterprise-only case 는 SIGNATURE_LOCKED + extension path (M-D4) |
| 1 system 만 stuck → 전체 지연 | Medium | Per-system independent track. Stuck system 은 partial onboarding 로 G2/G3 통과 |

## v2 처리 (D2 폐기 결정 반영)

v2 의 Phase α 산출물 (`backend/modeling/sim_verify/runtime/`, `idioms/P*.md`, 27 카드, 5 facade, 5 fixture S1-S5) 는 **학습 자산만 reference, 새 plugin 처음부터 재작성**.

상세는 ADR-010 (Phase α discard rationale) 참조.

## Broadleaf 의 scope 한정

- **Version**: Broadleaf Commerce community edition (BroadleafFramework v6.x 기준)
- **Scope**: core + cart + order + pricing + offer 모듈 (admin / search 는 phase 2)
- **Onboarding boundary**: 200K+ 전부가 아닌 약 80-100K 의 core path 우선
- **Enterprise-specific exclude**: BLC enterprise 의 dynamic field / sandbox / workflow override 는 SIGNATURE_LOCKED 후보

## Banking 도메인 의 design specifics (가상 설계 scope)

15-25 entities, Drools+BPMN+multi-tenant 의도 포함:

```
Domain entities (~20개 예상):
  Applicant, Loan, LoanProduct, Tenant
  CreditScore, CreditReport, CreditBureau
  Application, ApplicationStatus, ApplicationDocument
  UnderwritingDecision, UnderwritingRule
  Approval, Disbursement, DisbursementSchedule
  Payment, PaymentSchedule, PaymentEvent
  AuditLog, ComplianceCheck

Service layers (~6개):
  ApplicationService, UnderwritingService, ApprovalService
  DisbursementService, PaymentService, ComplianceService

Workflow:
  Application submit → Credit check → Underwriting (Drools) → Approval → Disbursement → Payment schedule
  각 transition: BPMN (Activiti) + @Transactional + @Aspect audit log

Meta-programming 의도 포함:
  - Drools KIE container loading (dynamic class loading)
  - Activiti BPMN deployment (dynamic class generation by Activiti)
  - Multi-tenant via Spring AOP (@TenantContext aspect)
  - Saga pattern with @Compensable (custom annotation processor)
  - Custom validator (@Valid + ConstraintValidator with reflection)
```

상세 entity model + Drools rule sample + BPMN definition 은 별도 design doc (`BANKING-DESIGN.md`, spec 작성 단계에서 생성 — 본 ADR 작성 직후).

## 결과 / 영향

- Framework 의 falsifiable test 확립 — 3-way universality 검증
- ADR-002 의 plugin abstraction 의 stress test 진행
- Phase α 의 ~50h 작업물은 학습 자산화 (ADR-010 참조)
- Cost 명시 → 사용자가 D6 결정 시점에 이미 수용
- M-D4 의 extension architecture 가 G4 에서 검증됨 (ADR-013 참조)
- Per-system 7 artifact 작성 가이드 = plugin contract (ADR-002)

## 후속 작업 (spec session 안에서)

1. `BANKING-DESIGN.md` — Banking 가상 system 의 entity / service / workflow / rule 명세 (spec session 후속, 별도 sub-document)
2. `BROADLEAF-ONBOARDING.md` — Broadleaf community 의 onboarding path + module scope (implementation plan session)
3. `V2-MIGRATION.md` — v2 의 Phase α → 새 plugin 재작성 절차 (implementation plan session)
4. spec.md 의 MILESTONES section 에 G1-G4 cross-validate gates 통합 (본 spec session)

## 참조

- DECISIONS-CONFIRMED.md (D3, M-D3, D6)
- ADR-001 (Python twin)
- ADR-002 (Two-Engine + plugin)
- ADR-006~009 (4 meta-programming 영역)
- ADR-010 (Phase α discard — sibling)
- ADR-013 (Extensibility — sibling, M-D4)
- 메모리 `feedback_simulation_design.md` (no MVP, 풀 시연 필수)
- 메모리 `project_decisions_v4_action.md` (4-layer + 7-case)
- `explorations/round2/4-skeptic.md` (M1 category error 의 motivation)
