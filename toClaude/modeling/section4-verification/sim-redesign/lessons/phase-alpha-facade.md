# Phase α Lesson 4 — Facade Abstraction Failure

작성일: 2026-05-13 (implementation plan session)
대상: Phase α `backend/modeling/sim_verify/runtime/` 4 hand-written substrate modules
관련 ADR: ADR-002 (Two-Engine + plugin contract), ADR-010 (Phase α discard)
Phase α 산출물 reference:
- commit `5642a57 feat(sec4/runtime): slab_design_runtime Python substrate`
- `backend/modeling/sim_verify/runtime/` 의 4 module (bigdecimal / algorithm_exception / confirmed_plant_cd / lookup_source)

---

## 1. 사실 — Phase α 의 facade approach

α1 (runtime) 이 Java 의 substrate (BigDecimal / AlgorithmException / 도메인 namespace / Spring repository emulator) 를 Python facade 로 hand-author 한 접근:

| Facade module | Java 의 대응 | Slab-specific 의 정도 |
|---|---|---|
| `bigdecimal.py` | `java.math.BigDecimal` + `MathContext` + `RoundingMode` | semi-generic (slab numeric scale convention 의 hardcode 일부 있음) |
| `algorithm_exception.py` | slab 의 `AlgorithmException` | slab-specific (step_no/step_name/error_code structure) |
| `confirmed_plant_cd.py` | slab 의 `SdConstants.POS_SM` 등 8-position string helpers | **완전 slab-specific** |
| `lookup_source.py` | Spring `JpaRepository.findById` / derived-query emulator | semi-generic (Spring 부분) + slab entity 의존 |

총 4 module ~500 LOC of facade. ADR-010 의 "5 facade" 표현은 4 module + `SdDesigner` orchestrator 추정.

---

## 2. Facade 의 reusability test — 3 system 적용 시

ADR-011 의 3 reference systems 적용 시 facade 의 재사용성 평가:

### 2.1 v2 (slab manufacturing)

원본 — facade 가 작성된 도메인. 100% 적용.

### 2.2 Broadleaf Commerce (e-commerce, 200K+ LOC)

| Facade | 적용 시 변화 |
|---|---|
| `bigdecimal.py` | 50-70% 재사용 가능. e-commerce 의 numeric scale (price = 2 decimal, weight = 3 decimal) 이 slab manufacturing 의 scale 과 다름 — `set_scale` 의 default 변경 필요 |
| `algorithm_exception.py` | 0% — Broadleaf 의 exception 은 `BroadleafException` + `OrderException` 등 별도 hierarchy. step_no/step_name 의미 없음 |
| `confirmed_plant_cd.py` | 0% — slab plant code 가 e-commerce 에 없음. `SkuCode`, `CategoryCode` 등 별도 |
| `lookup_source.py` | 30-50% — Spring `findById` 부분 재사용 가능, but Broadleaf 의 `BroadleafLookupCriteria` extension 추가 필요 |

평균: ~20-30% 재사용. 70%+ 의 substrate 재작성 필요.

### 2.3 Banking loan origination (가상, ~30-50K LOC, ADR-011 §6)

| Facade | 적용 시 변화 |
|---|---|
| `bigdecimal.py` | 60-80% 재사용. banking 의 currency precision (4-6 decimal) 이 slab 와 다름 |
| `algorithm_exception.py` | 10-20% — banking 의 exception (`LoanApprovalException`, `ComplianceException`) 별도. Step 개념 자체가 slab algorithm step 과 다름 (workflow step ≠ algorithm step) |
| `confirmed_plant_cd.py` | 0% — banking 에 없음. `TenantId`, `ApplicantId` 별도 |
| `lookup_source.py` | 30-50% — Spring 부분 재사용, but Drools KIE container + Activiti deployment lookup 추가 필요 (ADR-011 의 banking 의 의도 포함 meta-programming) |

평균: ~20-30% 재사용.

**3 system 종합:**
- bigdecimal.py: **semi-generic** (60-80% across) → generic facade base + plugin override delta
- algorithm_exception.py: **0-20% across** → plugin-specific 영역
- confirmed_plant_cd.py: **slab-only** → plugin-specific
- lookup_source.py: **30-50% generic** → Spring base + plugin extension

---

## 3. Facade 의 도메인 trap — Slab-specific 의 hidden assumption

### 3.1 8-position string format (confirmed_plant_cd.py)

slab 의 plant code 는 8-position string (POS_SM = "SM______", POS_HR = "HR______" 등). 이 format 자체가 slab manufacturing 의 ERP integration 의 convention. 다른 도메인은 plant code 자체가 없거나 다른 format.

### 3.2 step_no / step_name / error_code triplet (algorithm_exception.py)

slab algorithm 의 21-step loop 의 각 step 의 자리. Broadleaf 의 order processing 도 step 개념 있지만 sequence 가 다름 (cart → checkout → payment → fulfillment). banking 의 workflow 는 BPMN-driven, step 의미 자체가 다름.

### 3.3 Spring repository 의 slab entity tying (lookup_source.py)

`LookupDataSource` 의 method signature 가 slab entity (SDOrder, SDSlab) 와 직접 tied. Spring 의 generic mechanism 은 재사용 가능하나, entity 의존 부분은 rewrite.

### 3.4 BigDecimal scale 의 slab convention (bigdecimal.py)

bigdecimal.py 가 `MathContext.DECIMAL64` (16 significant digits, HALF_EVEN) 을 default 로 설정 — slab manufacturing 의 long-precision multiply (productivity × weight × time) 에 적합. e-commerce 의 price (HALF_UP, 2 decimal) 또는 banking 의 currency (HALF_EVEN but 4-6 decimal scale) 에서는 mismatch.

---

## 4. 왜 facade 가 generalization 실패했나

### 4.1 Bottom-up authoring 의 specifics 흡수

Facade 작성 motivation: "Java 의 BigDecimal 을 Python 에 재현". 시작점이 Java specifics — Python 의 generic substrate (decimal 모듈) 를 Java 의 specific signature 에 맞춤. 결과: facade 자체가 source language (Java) 의 abstraction 안에 갇힘.

### 4.2 Plugin contract 의 부재

새 system onboarding 시 "facade 의 어디까지 generic / plugin" 의 boundary 미명시. 모두 한 디렉토리 (`runtime/`) 에 mixed. Plugin scope 의 first-class decision 부재는 Lesson 2 와 같은 패턴.

### 4.3 Single-system 의 over-fit risk

Phase α 의 검증 대상이 v2 하나뿐. Facade 의 abstraction level 이 v2 의 specifics 에 over-fit — multi-system 검증 (ADR-011 의 G1 gate) 의 부재가 trap 노출 막음. Skeptic M1 ("category error") 의 직접적 동기.

### 4.4 Facade vs contract 의 mental model 혼동

Facade = "Java 의 method-level mirror Python 함수". Contract = "system 의 onboarding 시 작성하는 interface".

Phase α 는 facade 만 작성하고 contract 미작성. 새 system onboarding 시 facade 처음부터 재작성 — contract 가 base 가 되어야 reusable.

---

## 5. 새 framework 의 적용 — Plugin contract design

### 5.1 Generic Java contract (`backend/sim_v2/core/contracts/base.py`)

```python
# backend/sim_v2/core/contracts/base.py

class JavaContract:
    """Generic Spring + JPA + TX contract base.
    
    모든 plugin 의 base. Plugin 은 system-specific subclass.
    """
    spring_di: SpringDI                   # @Autowired, @Service, @Component
    jpa_repository: JPARepositoryBase     # JpaRepository<T, ID> 의 base method
    transaction: TransactionBase          # @Transactional propagation
    exception_base: type[Exception]       # 모든 도메인 exception 의 root

    @abstractmethod
    def domain_namespace(self) -> dict[str, Any]:
        """System-specific namespace constants (slab 의 SdConstants, banking 의 TenantContext 등)."""
        ...
```

### 5.2 Plugin contract override (`backend/sim_v2/plugins/<sys>/contracts/`)

```python
# backend/sim_v2/plugins/v2-slab-design/contracts/slab_contract.py

class SlabDesignContract(JavaContract):
    exception_base = AlgorithmException

    def domain_namespace(self) -> dict[str, Any]:
        return {
            "SdConstants": SdConstants,  # POS_SM, POS_HR, ...
            "MathContext.DECIMAL64": (16, "half_even"),
            "ValidationResult": ValidationResult,
        }

# backend/sim_v2/plugins/broadleaf/contracts/broadleaf_contract.py

class BroadleafContract(JavaContract):
    exception_base = BroadleafException

    def domain_namespace(self) -> dict[str, Any]:
        return {
            "BroadleafCommonUtils": BroadleafCommonUtils,
            "OrderStatus": OrderStatus,
            # ...
        }
```

### 5.3 Numeric precision 의 system-specific config

```python
# backend/sim_v2/plugins/<sys>/contracts/numeric.py

class NumericConvention:
    bigdecimal_precision: int           # MathContext.DECIMAL64 의 precision
    bigdecimal_rounding: RoundingMode   # default rounding
    domain_scales: dict[str, int]       # 도메인 type → scale (e.g., "price" → 2, "weight" → 3)
```

System-specific precision 이 contract first-class. bigdecimal.py 자체의 hardcode 없음.

### 5.4 Plugin 별 facade 의 분해

| Facade module | 새 framework 의 위치 |
|---|---|
| `bigdecimal.py` | `backend/sim_v2/core/contracts/numeric_base.py` (generic) + `backend/sim_v2/plugins/<sys>/contracts/numeric.py` (override) |
| `algorithm_exception.py` | `backend/sim_v2/plugins/v2-slab-design/contracts/exception.py` (plugin-specific) |
| `confirmed_plant_cd.py` | `backend/sim_v2/plugins/v2-slab-design/contracts/domain_namespace.py` (plugin-specific) |
| `lookup_source.py` | `backend/sim_v2/core/contracts/jpa_repository_base.py` (Spring generic) + `backend/sim_v2/plugins/<sys>/contracts/lookup.py` (system-specific) |

---

## 6. 학습 정수

1. **Facade ≠ contract.** Facade 는 source language 의 mirror, contract 는 system onboarding 의 spec. 새 framework 는 contract first.
2. **Generic 의 boundary 는 first-class decision.** 매 facade 의 어느 부분이 generic / system-specific 인지 명시 의무 — implicit 인 채로 두면 over-fit.
3. **Multi-system 검증의 timing.** Phase α 의 facade 가 v2 only 에서 valid 처럼 보였지만, 3 system 적용 시 ~20-30% reusable. G1 gate (ADR-011) 의 motivation.
4. **Bottom-up authoring 의 specifics trap.** Generic abstraction 은 top-down 결정 — system 의 multiple instance 의 commonality 추출. Bottom-up = single-system 의 specifics 누적.

---

## 7. 새 framework 의 적용 요약

| 영역 | 적용 항목 |
|---|---|
| `backend/sim_v2/core/contracts/base.py` | Generic Spring/JPA/TX contract base |
| `backend/sim_v2/core/contracts/numeric_base.py` | BigDecimal / MathContext / RoundingMode 의 generic Python equivalent |
| `backend/sim_v2/core/contracts/jpa_repository_base.py` | Spring `findById` / derived-query 의 generic part |
| `backend/sim_v2/plugins/<sys>/contracts/` | system-specific override (exception / domain namespace / numeric convention / entity-tied lookup) |
| Plugin manifest 의 `[contracts]` | system-specific contract 의 declaration |
| `backend/sim_v2/core/recommendation/anti_patterns/facade_over_fit.py` | "facade 가 single system 에 over-fit, multi-system 시 ~20-30% reusable" 의 anti-pattern entry |

---

## 8. 참조

- ADR-002 — Two-Engine + plugin (plugin contract source)
- ADR-011 — 3 systems (G1 gate 의 motivation, facade reusability stress test)
- ADR-010 — Phase α discard
- `backend/modeling/sim_verify/runtime/` — facade 4 module 실제 코드
- Lesson 1 (`phase-alpha-known-divergence.md`) — facade 의 implicit contract 가 만든 5 mismatch
- Lesson 2 (`phase-alpha-idiom-cards.md`) — plugin scope first-class decision 의 같은 패턴
- Lesson 3 (`phase-alpha-manual-twin.md`) — hand-crafted substrate 의 silent drift (facade 의 cost side)
- `explorations/round2/4-skeptic.md` — M1 ("category error") motivation
