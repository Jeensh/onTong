# Slab 설계 Spring Boot 시스템 — 개발 명세서

> **대상**: Claude Code
> **목적**: Slab 설계 자동화를 수행하는 **Spring Boot 시스템**을 구축한다. 이 시스템의 소스코드와 DB 테이블이 **온톨로지의 Layer 3 (Code Ontology) 대상**이 된다.
> **선결 자료**: `slab-design-domain-knowledge.md`
> **위치**: `sample-repos/scm-demo/` (또는 별도 모듈)
> **버전**: v1.0

---

## 0. 목표

이 문서대로 구현하면 다음이 만들어진다.

```
완성품:
1. Spring Boot 3.x 기반 RESTful 시스템
2. Slab 설계 14단계를 모두 수행하는 비즈니스 로직
3. 14개 SC 기준 테이블 + 매핑 클래스
4. Layer 3 온톨로지 추출 대상이 되는 코드 구조
   - Class 50+개 (Service, Form, Entity, Repository)
   - Method 100+개
   - Table 14개

→ 이후 jQAssistant가 이 시스템의 소스를 자동 분석하여
   온톨로지 Layer 3로 등록한다.
```

---

## 1. 기술 스택

| 항목 | 선택 |
|------|------|
| 프레임워크 | Spring Boot 3.2+ |
| 빌드 도구 | Maven |
| Java 버전 | Java 17 |
| DB | H2 (개발) / PostgreSQL (운영) |
| ORM | Spring Data JPA |
| API | Spring Web MVC (REST) |
| 검증 | Bean Validation (Jakarta) |
| 문서화 | SpringDoc OpenAPI (Swagger) |
| 테스트 | JUnit 5 + Mockito |
| 로깅 | SLF4J + Logback |
| 코드 분석 | jQAssistant (온톨로지 자동 추출용) |

---

## 2. 프로젝트 구조

```
sample-repos/scm-demo/
├── pom.xml
├── src/main/
│   ├── java/com/ontong/scm/slab/
│   │   ├── SlabDesignApplication.java        ← Main
│   │   │
│   │   ├── api/                              ← Controller
│   │   │   ├── SlabDesignController.java
│   │   │   ├── StandardController.java
│   │   │   └── dto/
│   │   │       ├── SlabDesignRequest.java
│   │   │       ├── SlabDesignResponse.java
│   │   │       └── SlabDesignStepResult.java
│   │   │
│   │   ├── service/                          ← 비즈니스 로직 (핵심)
│   │   │   ├── SlabDesignService.java
│   │   │   ├── SplitCountCalculator.java
│   │   │   ├── WeightRangeCalculator.java
│   │   │   ├── WidthRangeCalculator.java
│   │   │   ├── LengthRangeCalculator.java
│   │   │   └── DesignPolicyResolver.java
│   │   │
│   │   ├── domain/                           ← Entity (JPA)
│   │   │   ├── Order.java
│   │   │   ├── SlabDesignResult.java
│   │   │   ├── DesignStepLog.java
│   │   │   └── standards/                    ← 14개 Standard Entity
│   │   │       ├── ContinuousCasterSpec.java   (SC030)
│   │   │       ├── HotRollingMillSpec.java     (SC040)
│   │   │       ├── CoilOuterDiameterRestric.java (SC060)
│   │   │       ├── HsmEdgingSpec.java          (SC070)
│   │   │       ├── HrEdgingSpecGroup.java      (SC071)
│   │   │       ├── HsmWeightMin.java           (SC080)
│   │   │       ├── StdRollMaxUnit.java         (SC090)
│   │   │       ├── CsmMinWgt.java              (SC100)
│   │   │       ├── OemWgtMaxRange.java         (SC110)
│   │   │       ├── WgtSatisfactionConst.java   (SC160)
│   │   │       ├── HotCoilNotCuttableSpec.java (SC170)
│   │   │       ├── SlabDesignLimitation.java   (SC270)
│   │   │       ├── SpecificCustomerWgtRestri.java (SC290)
│   │   │       └── DeliveryAllowance.java      (SC370)
│   │   │
│   │   ├── repository/                       ← Spring Data JPA Repository
│   │   │   ├── OrderRepository.java
│   │   │   ├── SlabDesignResultRepository.java
│   │   │   └── standards/                    ← 14개 Repository
│   │   │       └── ... (각 Standard별)
│   │   │
│   │   ├── form/                             ← CRUD Form 클래스 (도메인 매핑 대상)
│   │   │   ├── SDCastMachineSpecForm.java       (SC030)
│   │   │   ├── SDHsmMachineSpecForm.java        (SC040)
│   │   │   ├── SDCoilOutDiaRestricForm.java     (SC060)
│   │   │   ├── SDHsmEdgingSpecForm.java         (SC070)
│   │   │   ├── SDHrEdgingSpecGroupForm.java     (SC071)
│   │   │   ├── SDHsmWeightMinForm.java          (SC080)
│   │   │   ├── SDStdRollMaxUnitForm.java        (SC090)
│   │   │   ├── SDCsmMinWgtForm.java             (SC100)
│   │   │   ├── SDOemWgtMaxRangeForm.java        (SC110)
│   │   │   ├── SDWgtSatisfactionConstForm.java  (SC160)
│   │   │   ├── SDHotCoilNotCuttableSpecForm.java (SC170)
│   │   │   ├── SDSlabDesignLimitationForm.java  (SC270)
│   │   │   ├── SDSpecificCustomerWgtRestriForm.java (SC290)
│   │   │   └── SDDeliveryAllowanceForm.java     (SC370)
│   │   │
│   │   ├── exception/
│   │   │   ├── SlabDesignException.java
│   │   │   ├── DG320Exception.java          ← Edging 매칭 불가
│   │   │   └── GlobalExceptionHandler.java
│   │   │
│   │   └── common/
│   │       ├── DensityConstant.java          ← 7.82
│   │       └── RoundingUtil.java             ← 10mm 절상/절사
│   │
│   └── resources/
│       ├── application.yml
│       ├── application-dev.yml
│       ├── data.sql                          ← 시드 데이터 (14개 SC 기준)
│       └── schema.sql                        ← 테이블 스키마
│
├── src/test/java/com/ontong/scm/slab/
│   ├── service/
│   │   ├── SlabDesignServiceTest.java
│   │   └── ...
│   └── api/
│       └── SlabDesignControllerTest.java
│
└── jqassistant/                              ← jQAssistant 설정
    └── index.adoc                             ← 커스텀 추출 규칙
```

---

## 3. 핵심 명명 규칙 (★ 온톨로지 자동 매핑 키)

> **이 명명 규칙은 절대 어기지 말 것.** jQAssistant가 메서드명 패턴으로 Step을 자동 매핑하기 때문.

### 3-1. 메서드 명명 (Step 자동 매핑용)

```
calculateThickness()              → Step 1
calculatePrimaryWidthRange()      → Step 2
calculatePrimaryLengthRange()     → Step 3
calculatePrimaryWeightRange()     → Step 4
calculateSecondaryWeightLower()   → Step 5
calculateSecondaryWeightUpper()   → Step 6
calculateSplitCount()             → Step 7
calculateUnitCountAndTargetWeight() → Step 8
checkTargetWeightSatisfaction()   → Step 9
calculateSecondaryWidthRange()    → Step 10
calculateSecondaryLengthRange()   → Step 11
calculateTargetWidth()            → Step 12
calculateTargetWidthFor3Pass()    → Step 13
calculateTargetLength()           → Step 14
```

### 3-2. Form 클래스 명명 (Standard 자동 매핑용)

```
SDCastMachineSpecForm        → SC030
SDHsmMachineSpecForm         → SC040
SDCoilOutDiaRestricForm      → SC060
SDHsmEdgingSpecForm          → SC070
SDHrEdgingSpecGroupForm      → SC071
SDHsmWeightMinForm           → SC080
SDStdRollMaxUnitForm         → SC090
SDCsmMinWgtForm              → SC100
SDOemWgtMaxRangeForm         → SC110
SDWgtSatisfactionConstForm   → SC160
SDHotCoilNotCuttableSpecForm → SC170
SDSlabDesignLimitationForm   → SC270
SDSpecificCustomerWgtRestriForm → SC290
SDDeliveryAllowanceForm      → SC370
```

### 3-3. 테이블 명명

```
TB_C40_050SC030 ~ TB_C40_050SC370  (총 14개)
```

### 3-4. Entity 명명 (테이블 → Entity)

```java
@Entity
@Table(name = "TB_C40_050SC070")
public class HsmEdgingSpec { ... }
```

---

## 4. 핵심 도메인 모델

### 4-1. Order (주문)

```java
package com.ontong.scm.slab.domain;

import jakarta.persistence.*;
import lombok.Data;

@Entity
@Table(name = "TB_ORDER")
@Data
public class Order {
    @Id
    @Column(name = "ORDER_NO", length = 30)
    private String orderNo;            // 예: "01S3047892010"
    
    @Column(name = "PRODUCT_TYPE", length = 10)
    private String productType;        // FAB, FHE 등
    
    @Column(name = "ORDER_QUANTITY")
    private Double orderQuantity;      // 주문량 (톤)
    
    @Column(name = "TARGET_WIDTH")
    private Integer targetWidth;       // 주문 목표폭 (mm)
    
    @Column(name = "HR_TARGET_WIDTH")
    private Double hrTargetWidth;      // 열연목표폭 (mm)
    
    @Column(name = "PRODUCT_THICKNESS")
    private Double productThickness;   // 제품 두께 (mm)
    
    @Column(name = "YIELD_RATE")
    private Double yieldRate;          // 실수율
    
    @Column(name = "TARGET_WEIGHT")
    private Double targetWeight;       // Target단중 (kg, 0이면 미입력)
    
    @Column(name = "PACKAGING_WEIGHT_LOWER")
    private Double packagingWeightLower;
    
    @Column(name = "PACKAGING_WEIGHT_UPPER")
    private Double packagingWeightUpper;
    
    @Column(name = "PACKAGING_CORRECTION_LOWER")
    private Double packagingCorrectionLower;  // 보정상수 하한
    
    @Column(name = "PACKAGING_CORRECTION_UPPER")
    private Double packagingCorrectionUpper;  // 보정상수 상한
    
    @Column(name = "BACKING_MATERIAL")
    private String backingMaterial;    // 배쪽재 여부 (Y/N)
    
    @Column(name = "FACTORY_DECISION")
    private String factoryDecision;    // 공장결정 (예: "1연주-1열연-1PCM-7CGL")
    
    @Column(name = "DESIGN_CAPACITY_LOWER")
    private Double designCapacityLower;  // 설계대기량 하한
    
    @Column(name = "DESIGN_CAPACITY_UPPER")
    private Double designCapacityUpper;  // 설계대기량 상한
    
    @Column(name = "CUSTOMER_CODE", length = 10)
    private String customerCode;
    
    @Column(name = "AUTO_DESIGN")
    private String autoDesign;         // Y/N
}
```

### 4-2. SlabDesignResult (설계 결과)

```java
@Entity
@Table(name = "TB_SLAB_DESIGN_RESULT")
@Data
public class SlabDesignResult {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @Column(name = "ORDER_NO")
    private String orderNo;
    
    @Column(name = "DESIGN_DATE")
    private LocalDateTime designDate;
    
    // 최종 설계 결과
    @Column(name = "SLAB_THICKNESS")
    private Integer slabThickness;
    
    @Column(name = "TARGET_SLAB_WIDTH")
    private Integer targetSlabWidth;
    
    @Column(name = "TARGET_SLAB_LENGTH")
    private Integer targetSlabLength;
    
    @Column(name = "SLAB_WEIGHT")
    private Double slabWeight;
    
    @Column(name = "SPLIT_COUNT")
    private Integer splitCount;
    
    @Column(name = "UNIT_COUNT")
    private Integer unitCount;         // 매수
    
    @Column(name = "DESIGN_STATUS", length = 20)
    private String designStatus;       // SUCCESS, FAILED, ERROR
    
    @Column(name = "ERROR_CODE", length = 10)
    private String errorCode;          // DG320 등
    
    @OneToMany(mappedBy = "result", cascade = CascadeType.ALL)
    private List<DesignStepLog> stepLogs = new ArrayList<>();
}
```

### 4-3. DesignStepLog (단계별 로그)

```java
@Entity
@Table(name = "TB_DESIGN_STEP_LOG")
@Data
public class DesignStepLog {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @ManyToOne
    @JoinColumn(name = "RESULT_ID")
    private SlabDesignResult result;
    
    @Column(name = "STEP_NUMBER")
    private Integer stepNumber;        // 1 ~ 14
    
    @Column(name = "STEP_NAME", length = 50)
    private String stepName;
    
    @Column(name = "FROM_VALUE")
    private Double fromValue;
    
    @Column(name = "TO_VALUE")
    private Double toValue;
    
    @Column(name = "DETAIL", columnDefinition = "TEXT")
    private String detail;             // 계산 상세 내용
    
    @Column(name = "EXECUTED_AT")
    private LocalDateTime executedAt;
}
```

---

## 5. 핵심 서비스 구현

### 5-1. SlabDesignService (메인 오케스트레이터)

```java
package com.ontong.scm.slab.service;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

@Service
@Transactional
@RequiredArgsConstructor
@Slf4j
public class SlabDesignService {
    
    private final WidthRangeCalculator widthRangeCalculator;
    private final LengthRangeCalculator lengthRangeCalculator;
    private final WeightRangeCalculator weightRangeCalculator;
    private final SplitCountCalculator splitCountCalculator;
    private final DesignPolicyResolver policyResolver;
    
    /**
     * Slab 설계 메인 진입점.
     * Step 1 ~ 14를 순차 실행한다.
     *
     * @param order 주문 정보
     * @return 설계 결과
     * @throws DG320Exception Edging 매칭 불가 시
     */
    public SlabDesignResult design(Order order) {
        log.info("Slab 설계 시작 — orderNo: {}", order.getOrderNo());
        SlabDesignResult result = new SlabDesignResult();
        
        try {
            // Step 1: 두께 결정
            int thickness = calculateThickness(order, result);
            
            // Step 2: 1차 폭범위
            WidthRange primaryWidth = calculatePrimaryWidthRange(order, result);
            
            // Step 3: 1차 길이범위
            LengthRange primaryLength = calculatePrimaryLengthRange(order, result);
            
            // Step 4: 1차 단중범위
            WeightRange primaryWeight = calculatePrimaryWeightRange(
                thickness, primaryWidth, primaryLength, result
            );
            
            // Step 5: 2차 단중하한
            double secondaryWeightLower = calculateSecondaryWeightLower(
                order, primaryWeight, result
            );
            
            // Step 6: 2차 단중상한
            double secondaryWeightUpper = calculateSecondaryWeightUpper(
                order, primaryWeight, result
            );
            
            // Step 7: 분할수
            int maxSplitCount = calculateSplitCount(
                order, secondaryWeightUpper, result
            );
            
            // Step 8: 매수 및 목표단중 (Loop)
            UnitCountAndWeight uw = calculateUnitCountAndTargetWeight(
                order, secondaryWeightLower, secondaryWeightUpper, 
                maxSplitCount, result
            );
            
            // Step 9: Target단중 만족여부
            checkTargetWeightSatisfaction(order, uw, result);
            
            // Step 10: 2차 폭범위 (단중 역산)
            WidthRange secondaryWidth = calculateSecondaryWidthRange(
                uw.getSlabWeight(), thickness, primaryLength, primaryWidth, result
            );
            
            // Step 11: 2차 길이범위 (단중 역산)
            LengthRange secondaryLength = calculateSecondaryLengthRange(
                uw.getSlabWeight(), thickness, secondaryWidth, primaryLength, result
            );
            
            // Step 12: Target폭
            int targetWidth = calculateTargetWidth(
                uw.getSlabWeightUpper(), thickness, secondaryLength, secondaryWidth, result
            );
            
            // Step 13: Target폭 재계산 (3pass)
            if (order.is3PassEnabled()) {
                targetWidth = calculateTargetWidthFor3Pass(
                    order, targetWidth, secondaryWidth, result
                );
            }
            
            // Step 14: Target길이
            int targetLength = calculateTargetLength(
                uw.getSlabWeight(), targetWidth, thickness, result
            );
            
            // 결과 저장
            result.setSlabThickness(thickness);
            result.setTargetSlabWidth(targetWidth);
            result.setTargetSlabLength(targetLength);
            result.setSlabWeight(uw.getSlabWeight());
            result.setSplitCount(uw.getSplitCount());
            result.setUnitCount(uw.getUnitCount());
            result.setDesignStatus("SUCCESS");
            
            log.info("Slab 설계 완료 — orderNo: {}", order.getOrderNo());
            return result;
            
        } catch (DG320Exception e) {
            result.setDesignStatus("ERROR");
            result.setErrorCode("DG320");
            log.error("DG320 발생 — orderNo: {}, msg: {}", order.getOrderNo(), e.getMessage());
            throw e;
        }
    }
    
    // ─── Step 1 ──────────────────────────────────────────
    private int calculateThickness(Order order, SlabDesignResult result) {
        // 연주설비 mold 두께 조회
        // 250 등의 값 반환
        // ... (구현)
    }
    
    // ─── Step 2 ──────────────────────────────────────────
    private WidthRange calculatePrimaryWidthRange(Order order, SlabDesignResult result) {
        return widthRangeCalculator.calculatePrimary(order, result);
    }
    
    // ... 이하 각 Step별 메서드
}
```

### 5-2. WidthRangeCalculator (Step 2, 10, 12, 13)

```java
package com.ontong.scm.slab.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import com.ontong.scm.slab.repository.standards.*;
import com.ontong.scm.slab.exception.DG320Exception;
import com.ontong.scm.slab.common.RoundingUtil;
import static com.ontong.scm.slab.common.DensityConstant.STEEL_DENSITY;

@Service
@RequiredArgsConstructor
public class WidthRangeCalculator {
    
    private final ContinuousCasterSpecRepository ccSpecRepo;       // SC030
    private final HotRollingMillSpecRepository hrSpecRepo;         // SC040
    private final HsmEdgingSpecRepository edgingSpecRepo;          // SC070
    
    /**
     * Step 2: 1차 폭범위 산정
     * 
     * 공식:
     *   폭하한 = max(연주설비하한폭, 열연설비하한폭, 열연목표폭+Edging하한)
     *   폭상한 = min(연주설비상한폭, 열연설비상한폭, 열연목표폭+Edging상한)
     */
    public WidthRange calculatePrimary(Order order, SlabDesignResult result) {
        // 1. 연주/열연 사양 조회
        var ccSpec = ccSpecRepo.findByProductType(order.getProductType())
            .orElseThrow();
        var hrSpec = hrSpecRepo.findByProductType(order.getProductType())
            .orElseThrow();
        
        // 2. Edging 능력 조회 (목표폭 구간 매칭)
        var edgingSpec = edgingSpecRepo.findByTargetWidth(order.getHrTargetWidth())
            .orElseThrow(() -> new DG320Exception(
                "Edging 기준 매칭 불가 - 목표폭(" + order.getHrTargetWidth() + 
                ")이 Edging 기준 범위 외"
            ));
        
        // 3. 폭하한 계산
        int lower = (int) Math.max(
            Math.max(ccSpec.getWidthLower(), hrSpec.getWidthLower()),
            order.getHrTargetWidth() + edgingSpec.getEdgingMin()
        );
        lower = RoundingUtil.ceilTo10mm(lower);    // 10mm 단위 절상
        
        // 4. 폭상한 계산
        int upper = (int) Math.min(
            Math.min(ccSpec.getWidthUpper(), hrSpec.getWidthUpper()),
            order.getHrTargetWidth() + edgingSpec.getEdgingMax()
        );
        upper = RoundingUtil.floorTo10mm(upper);   // 10mm 단위 절사
        
        // 5. 로깅
        logStep(result, 2, "1차 폭범위 계산", lower, upper, 
            String.format("Max(%.1f+%d, %d, %d) ~ Min(%.1f+%d, %d, %d)",
                order.getHrTargetWidth(), edgingSpec.getEdgingMin(), 
                ccSpec.getWidthLower(), hrSpec.getWidthLower(),
                order.getHrTargetWidth(), edgingSpec.getEdgingMax(),
                ccSpec.getWidthUpper(), hrSpec.getWidthUpper())
        );
        
        return new WidthRange(lower, upper);
    }
    
    /**
     * Step 10: 2차 폭범위 (단중 역산)
     * 
     * 공식:
     *   폭하한 = Slab단중 / (1차길이상한 × 두께 × 비중) × 1,000,000 [10mm 절상]
     *   폭상한 = Slab단중 / (1차길이하한 × 두께 × 비중) × 1,000,000 [10mm 절사]
     */
    public WidthRange calculateSecondary(double slabWeight, int thickness,
                                          LengthRange primaryLength, 
                                          WidthRange primaryWidth,
                                          SlabDesignResult result) {
        double lowerCalc = slabWeight / 
            (primaryLength.getUpper() * thickness * STEEL_DENSITY) * 1_000_000;
        double upperCalc = slabWeight / 
            (primaryLength.getLower() * thickness * STEEL_DENSITY) * 1_000_000;
        
        // 1차 범위로 제약
        int lower = Math.max(RoundingUtil.ceilTo10mm((int) lowerCalc), 
                             primaryWidth.getLower());
        int upper = Math.min(RoundingUtil.floorTo10mm((int) upperCalc), 
                             primaryWidth.getUpper());
        
        logStep(result, 10, "2차 폭범위 계산", lower, upper, "단중 역산");
        return new WidthRange(lower, upper);
    }
    
    /**
     * Step 12: Target 폭 산정
     */
    public int calculateTarget(double slabWeightUpper, int thickness,
                                LengthRange secondaryLength,
                                WidthRange secondaryWidth,
                                SlabDesignResult result) {
        double calc = slabWeightUpper / 
            (secondaryLength.getUpper() * thickness * STEEL_DENSITY) * 1_000_000;
        int targetWidth = RoundingUtil.ceilTo10mm((int) calc);
        
        // 범위 제약
        if (targetWidth < secondaryWidth.getLower() || 
            targetWidth > secondaryWidth.getUpper()) {
            targetWidth = secondaryWidth.getLower();
        }
        
        logStep(result, 12, "Target폭 계산", targetWidth, 0, 
            "Target폭 = " + targetWidth + "mm");
        return targetWidth;
    }
    
    /**
     * Step 13: Target폭 재계산 (3pass 적용)
     */
    public int calculateFor3Pass(Order order, int currentTargetWidth,
                                  WidthRange secondaryWidth,
                                  SlabDesignResult result) {
        // 3pass 가능한 Edging 능력으로 재계산
        // RmPass별 Edging 능력 조회 후 적용
        // ... (구현)
        return currentTargetWidth;  // 또는 재계산된 값
    }
    
    // 헬퍼 메서드
    private void logStep(SlabDesignResult result, int stepNumber, String stepName,
                         double from, double to, String detail) {
        var log = new DesignStepLog();
        log.setStepNumber(stepNumber);
        log.setStepName(stepName);
        log.setFromValue(from);
        log.setToValue(to);
        log.setDetail(detail);
        log.setExecutedAt(LocalDateTime.now());
        log.setResult(result);
        result.getStepLogs().add(log);
    }
}
```

### 5-3. WeightRangeCalculator (Step 4, 5, 6)

```java
@Service
@RequiredArgsConstructor
public class WeightRangeCalculator {
    
    private final HsmWeightMinRepository hsmMinRepo;          // SC080
    private final StdRollMaxUnitRepository hsmMaxRepo;        // SC090
    private final CsmMinWgtRepository csmMinRepo;             // SC100
    private final OemWgtMaxRangeRepository oemMaxRepo;        // SC110
    private final HotCoilNotCuttableSpecRepository ncRepo;    // SC170
    private final SlabDesignLimitationRepository slabLimitRepo; // SC270
    private final SpecificCustomerWgtRestriRepository custRepo;  // SC290
    private final CoilOuterDiameterRestricRepository codrRepo;   // SC060
    
    /**
     * Step 4: 1차 단중범위
     * 
     * 공식:
     *   하한 = 두께 × 폭하한 × 길이하한 × 비중 [절상]
     *   상한 = 두께 × 폭상한 × 길이상한 × 비중 [절사]
     */
    public WeightRange calculatePrimary(int thickness, WidthRange width, 
                                         LengthRange length, 
                                         SlabDesignResult result) {
        double lower = (double) thickness * width.getLower() 
                       * length.getLower() * STEEL_DENSITY / 1_000_000;
        double upper = (double) thickness * width.getUpper() 
                       * length.getUpper() * STEEL_DENSITY / 1_000_000;
        
        int lowerInt = (int) Math.ceil(lower);
        int upperInt = (int) Math.floor(upper);
        
        logStep(result, 4, "1차 단중범위", lowerInt, upperInt, 
            String.format("두께(%d) × 폭(%d~%d) × 길이(%d~%d) × 비중(%.2f)",
                thickness, width.getLower(), width.getUpper(),
                length.getLower(), length.getUpper(), STEEL_DENSITY));
        
        return new WeightRange(lowerInt, upperInt);
    }
    
    /**
     * Step 5: 2차 단중하한
     * 
     * 공식:
     *   = max(1차단중범위하한, 특정고객사제한, 냉연최소(PO재 제외), 열연Min)
     */
    public double calculateSecondaryLower(Order order, WeightRange primary,
                                          SlabDesignResult result) {
        double customerLower = custRepo.findLowerByCustomer(order.getCustomerCode())
            .orElse(0.0);
        double csmMin = order.isPOMaterial() ? 0.0 :
            csmMinRepo.findMinWeightLower(order).orElse(0.0);
        double hsmMin = hsmMinRepo.findMinWeight(order).orElse(-1.0);
        
        double result_value = Math.max(
            Math.max(primary.getLower(), customerLower),
            Math.max(csmMin, hsmMin)
        );
        
        // 체크: 0 이하면 에러
        if (result_value <= 0) {
            // 처리...
        }
        
        logStep(result, 5, "2차 단중하한", result_value, 0,
            String.format("Max(1차하한(%d), 고객사(%.1f), 냉연(%.1f), 열연Min(%.1f))",
                primary.getLower(), customerLower, csmMin, hsmMin));
        
        return result_value;
    }
    
    /**
     * Step 6: 2차 단중상한
     */
    public double calculateSecondaryUpper(Order order, WeightRange primary,
                                          SlabDesignResult result) {
        // 여러 제약 조건의 MIN 산정 (도메인 문서 5절 참고)
        double customerUpper = custRepo.findUpperByCustomer(order.getCustomerCode())
            .orElse(99999.0);
        double designCapUpper = order.getDesignCapacityUpper();
        double hsmMaxCorrected = hsmMaxRepo.findMaxByThicknessAndWidth(
            order.getProductThickness(), order.getHrTargetWidth()
        ).orElse(99999.0) - getRollingMaxCorrection();
        // ... 이하 다수 제약
        
        double result_value = Math.min(
            Math.min(primary.getUpper(), customerUpper),
            // ... 모든 제약 비교
            designCapUpper
        );
        
        logStep(result, 6, "2차 단중상한", 0, result_value, "Min(다수 제약)");
        return result_value;
    }
}
```

### 5-4. SplitCountCalculator (Step 7, 8)

```java
@Service
@RequiredArgsConstructor
public class SplitCountCalculator {
    
    private final WgtSatisfactionConstRepository constRepo;       // SC160
    private final DeliveryAllowanceRepository deliveryRepo;       // SC370
    private final DesignPolicyResolver policyResolver;
    
    /**
     * Step 7: 분할수 계산
     * 
     * 공식:
     *   최대분할수 = 소수점절상(2차단중상한 / 주문단중상한(배폭고려) / 보정상수상한 / 실수율)
     */
    public int calculateMaxSplitCount(Order order, double secondaryWeightUpper,
                                       SlabDesignResult result) {
        double packagingUpper = order.getPackagingWeightUpper() * 1000;  // kg
        double correctionUpper = order.getPackagingCorrectionUpper();
        double yieldRate = order.getYieldRate();
        
        double calc = secondaryWeightUpper / packagingUpper 
                      / correctionUpper / yieldRate;
        int maxSplit = (int) Math.ceil(calc);
        
        // 분할수 검증: <= 0 이면 에러
        if (maxSplit <= 0) {
            // 에러 처리
        }
        
        logStep(result, 7, "분할수 계산", maxSplit, 0,
            String.format("ceil(%.1f / %.1f / %.2f / %.3f) = %d",
                secondaryWeightUpper, packagingUpper, correctionUpper, 
                yieldRate, maxSplit));
        return maxSplit;
    }
    
    /**
     * Step 8: 매수 및 목표단중 계산 (Loop)
     */
    public UnitCountAndWeight calculateUnitCountAndTargetWeight(
            Order order, double weightLower, double weightUpper,
            int maxSplitCount, SlabDesignResult result) {
        
        // Slab설계방침 결정 (단중최대화 vs 제품단중최대화)
        DesignPolicy policy = policyResolver.resolve(order);
        
        // Loop: 최대분할수에서 1씩 감소하며 검증
        for (int splitCount = maxSplitCount; splitCount >= 1; splitCount--) {
            // 분할수별 단중범위 계산
            double rangeLower = order.getPackagingWeightLower() * 1000 * splitCount;
            double rangeUpper = order.getPackagingWeightUpper() * 1000 * splitCount;
            
            // 2차 Slab단중 설계범위와 교집합
            double commonLower = Math.max(weightLower, rangeLower);
            double commonUpper = Math.min(weightUpper, rangeUpper);
            
            if (commonUpper < commonLower) continue;
            
            // 단중만족율 계산
            double satisfaction = (commonUpper - commonLower) / 
                                  (rangeUpper - rangeLower);
            
            // 매수 산정
            int unitCount = (int) Math.floor(
                order.getDesignCapacityUpper() / order.getYieldRate() / commonUpper
            );
            
            // 설계대기량 만족 검증
            if (unitCount * commonUpper >= order.getDesignCapacityLower() &&
                unitCount * commonUpper <= order.getDesignCapacityUpper()) {
                
                logStep(result, 8, "매수 및 목표단중", commonLower, commonUpper,
                    String.format("분할수(%d), 매수(%d), 단중(%.0f)",
                        splitCount, unitCount, commonUpper));
                
                return new UnitCountAndWeight(
                    splitCount, unitCount, commonUpper, commonLower, commonUpper
                );
            }
        }
        
        throw new SlabDesignException("설계대기량 범위 만족 실패");
    }
}
```

---

## 6. SC 기준 Entity 예시

### 6-1. HsmEdgingSpec (SC070)

```java
@Entity
@Table(name = "TB_C40_050SC070")
@Data
public class HsmEdgingSpec {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @Column(name = "GROUP_CODE", length = 5)
    private String groupCode;          // *, A, B, C, D, E, F, J, K, P, U, Z
    
    @Column(name = "SLAB_THICKNESS")
    private Integer slabThickness;     // 400 등
    
    @Column(name = "HCOIL_WIDTH")
    private Integer hcoilWidth;        // 810, 1100, 1650, 1970 등
    
    @Column(name = "EDGING_MIN")
    private Integer edgingMin;         // 20
    
    @Column(name = "EDGING_MAX")
    private Integer edgingMax;         // 130, 100, 80, 29 등
    
    @Column(name = "FACTORY_CODE")
    private String factoryCode;        // 광양/포항
}
```

### 6-2. HsmEdgingSpecRepository

```java
package com.ontong.scm.slab.repository.standards;

import org.springframework.data.jpa.repository.*;
import com.ontong.scm.slab.domain.standards.HsmEdgingSpec;

public interface HsmEdgingSpecRepository extends JpaRepository<HsmEdgingSpec, Long> {
    
    /**
     * 목표폭이 어느 그룹/규격에 매칭되는지 찾기.
     * 매칭 안 되면 빈 Optional → DG320 에러로 이어짐.
     */
    @Query("""
        SELECT e FROM HsmEdgingSpec e
        WHERE :targetWidth <= e.hcoilWidth
        ORDER BY e.hcoilWidth ASC
    """)
    Optional<HsmEdgingSpec> findByTargetWidth(@Param("targetWidth") Double targetWidth);
}
```

### 6-3. SDHsmEdgingSpecForm (CRUD Form)

```java
package com.ontong.scm.slab.form;

import org.springframework.web.bind.annotation.*;
import com.ontong.scm.slab.domain.standards.HsmEdgingSpec;

/**
 * SC070 - 열연Edging능력기준 CRUD Form.
 * 이 클래스가 jQAssistant에 의해 SC070 기준에 자동 매핑된다.
 */
@RestController
@RequestMapping("/api/standards/sc070")
@RequiredArgsConstructor
public class SDHsmEdgingSpecForm {
    
    private final HsmEdgingSpecRepository repository;
    
    @GetMapping
    public List<HsmEdgingSpec> findAll() { return repository.findAll(); }
    
    @PostMapping
    public HsmEdgingSpec create(@RequestBody HsmEdgingSpec spec) {
        return repository.save(spec);
    }
    
    @PutMapping("/{id}")
    public HsmEdgingSpec update(@PathVariable Long id, 
                                 @RequestBody HsmEdgingSpec spec) {
        spec.setId(id);
        return repository.save(spec);
    }
    
    @DeleteMapping("/{id}")
    public void delete(@PathVariable Long id) {
        repository.deleteById(id);
    }
}
```

---

## 7. REST API

### 7-1. SlabDesignController

```java
package com.ontong.scm.slab.api;

@RestController
@RequestMapping("/api/slab-design")
@RequiredArgsConstructor
public class SlabDesignController {
    
    private final SlabDesignService slabDesignService;
    private final OrderRepository orderRepository;
    
    /**
     * 주문 기반 자동 Slab 설계 실행.
     */
    @PostMapping("/execute/{orderNo}")
    public SlabDesignResponse execute(@PathVariable String orderNo) {
        Order order = orderRepository.findById(orderNo)
            .orElseThrow();
        
        SlabDesignResult result = slabDesignService.design(order);
        return SlabDesignResponse.from(result);
    }
    
    /**
     * Slab 설계 상세내역 조회 (자동Slab설계 상세내역 화면).
     */
    @GetMapping("/detail/{orderNo}")
    public SlabDesignResponse getDetail(@PathVariable String orderNo) {
        // 결과 + Step 로그 반환
        // ... 
    }
}
```

---

## 8. 시드 데이터

### 8-1. data.sql 일부

```sql
-- SC030: 연주설비사양기준
INSERT INTO TB_C40_050SC030 (PRODUCT_TYPE, FACTORY, MOLD_THICKNESS, 
    WIDTH_LOWER, WIDTH_UPPER, LENGTH_LOWER, LENGTH_UPPER, 
    WEIGHT_LOWER, WEIGHT_UPPER, THICKNESS_LOWER, THICKNESS_UPPER) 
VALUES ('*', '광양', 250, 900, 1950, 5500, 11880, 0, 35000, 200, 310);

INSERT INTO TB_C40_050SC030 VALUES (...);

-- SC070: 열연Edging능력기준
INSERT INTO TB_C40_050SC070 (GROUP_CODE, SLAB_THICKNESS, HCOIL_WIDTH, 
    EDGING_MIN, EDGING_MAX, FACTORY_CODE) 
VALUES ('*', 400, 810, 20, 130, '광양');
INSERT INTO TB_C40_050SC070 VALUES ('*', 400, 1100, 20, 130, '광양');
INSERT INTO TB_C40_050SC070 VALUES ('*', 400, 1650, 20, 130, '광양');
INSERT INTO TB_C40_050SC070 VALUES ('A', 400, 1650, 20, 29, '광양');
-- ... 도메인 문서의 SC070 표 전체 입력

-- 예제 주문
INSERT INTO TB_ORDER (ORDER_NO, PRODUCT_TYPE, ORDER_QUANTITY,
    TARGET_WIDTH, HR_TARGET_WIDTH, PRODUCT_THICKNESS, YIELD_RATE,
    TARGET_WEIGHT, PACKAGING_WEIGHT_LOWER, PACKAGING_WEIGHT_UPPER,
    PACKAGING_CORRECTION_LOWER, PACKAGING_CORRECTION_UPPER,
    BACKING_MATERIAL, FACTORY_DECISION, DESIGN_CAPACITY_LOWER,
    DESIGN_CAPACITY_UPPER, AUTO_DESIGN)
VALUES ('01S3047892010', 'FAB', 60.0,
    1500, 1529.0, 0.65, 0.954436,
    0.0, 8000, 12000, 0.98, 1.01,
    'N', '1연주-1열연-1PCM-7CGL', 51000, 69000, 'N');
```

---

## 9. jQAssistant 연동 (★ 온톨로지 자동 추출 키)

### 9-1. pom.xml에 플러그인 추가

```xml
<plugin>
    <groupId>com.buschmais.jqassistant</groupId>
    <artifactId>jqassistant-maven-plugin</artifactId>
    <version>2.4.0</version>
    <executions>
        <execution>
            <goals>
                <goal>scan</goal>
                <goal>analyze</goal>
            </goals>
        </execution>
    </executions>
    <configuration>
        <storeUri>bolt://localhost:7687</storeUri>
        <storeUsername>neo4j</storeUsername>
        <storePassword>${env.NEO4J_PASSWORD}</storePassword>
        <scanIncludes>
            <scanInclude>
                <path>${project.build.outputDirectory}</path>
            </scanInclude>
        </scanIncludes>
    </configuration>
</plugin>
```

### 9-2. 커스텀 추출 규칙 (jqassistant/index.adoc)

```asciidoc
[[ontong:Form-Standard-Mapping]]
.Form 클래스 → SC 기준 자동 매핑
[source,cypher,role=concept]
----
MATCH (c:Class)
WHERE c.name IN [
  'SDCastMachineSpecForm', 'SDHsmMachineSpecForm', 
  'SDCoilOutDiaRestricForm', 'SDHsmEdgingSpecForm',
  'SDHrEdgingSpecGroupForm', 'SDHsmWeightMinForm',
  'SDStdRollMaxUnitForm', 'SDCsmMinWgtForm',
  'SDOemWgtMaxRangeForm', 'SDWgtSatisfactionConstForm',
  'SDHotCoilNotCuttableSpecForm', 'SDSlabDesignLimitationForm',
  'SDSpecificCustomerWgtRestriForm', 'SDDeliveryAllowanceForm'
]
WITH c, 
     CASE c.name
       WHEN 'SDCastMachineSpecForm' THEN 'SC030'
       WHEN 'SDHsmMachineSpecForm' THEN 'SC040'
       WHEN 'SDCoilOutDiaRestricForm' THEN 'SC060'
       WHEN 'SDHsmEdgingSpecForm' THEN 'SC070'
       WHEN 'SDHrEdgingSpecGroupForm' THEN 'SC071'
       WHEN 'SDHsmWeightMinForm' THEN 'SC080'
       WHEN 'SDStdRollMaxUnitForm' THEN 'SC090'
       WHEN 'SDCsmMinWgtForm' THEN 'SC100'
       WHEN 'SDOemWgtMaxRangeForm' THEN 'SC110'
       WHEN 'SDWgtSatisfactionConstForm' THEN 'SC160'
       WHEN 'SDHotCoilNotCuttableSpecForm' THEN 'SC170'
       WHEN 'SDSlabDesignLimitationForm' THEN 'SC270'
       WHEN 'SDSpecificCustomerWgtRestriForm' THEN 'SC290'
       WHEN 'SDDeliveryAllowanceForm' THEN 'SC370'
     END AS code
MERGE (std:Standard {code: code})
MERGE (c)-[:RELATES_TO_STANDARD]->(std)
RETURN c.name, std.code
----

[[ontong:Method-Step-Mapping]]
.메서드 → Step 자동 매핑
[source,cypher,role=concept]
----
MATCH (m:Method)
WITH m,
     CASE 
       WHEN m.name STARTS WITH 'calculateThickness' THEN 1
       WHEN m.name STARTS WITH 'calculatePrimaryWidth' THEN 2
       WHEN m.name STARTS WITH 'calculatePrimaryLength' THEN 3
       WHEN m.name STARTS WITH 'calculatePrimaryWeight' THEN 4
       WHEN m.name STARTS WITH 'calculateSecondaryWeightLower' THEN 5
       WHEN m.name STARTS WITH 'calculateSecondaryWeightUpper' THEN 6
       WHEN m.name = 'calculateMaxSplitCount' OR m.name = 'calculateSplitCount' THEN 7
       WHEN m.name STARTS WITH 'calculateUnitCount' THEN 8
       WHEN m.name STARTS WITH 'checkTargetWeightSatisfaction' THEN 9
       WHEN m.name STARTS WITH 'calculateSecondaryWidth' THEN 10
       WHEN m.name STARTS WITH 'calculateSecondaryLength' THEN 11
       WHEN m.name = 'calculateTargetWidth' THEN 12
       WHEN m.name = 'calculateTargetWidthFor3Pass' THEN 13
       WHEN m.name = 'calculateTargetLength' THEN 14
     END AS stepNum
WHERE stepNum IS NOT NULL
MERGE (s:Step {step_number: stepNum})
MERGE (m)-[:CALCULATES]->(s)
RETURN m.name, stepNum
----

[[ontong:Entity-Table-Mapping]]
.JPA Entity → Table 자동 매핑
[source,cypher,role=concept]
----
MATCH (c:Class)-[:ANNOTATED_BY]->(a:Annotation {fqn: 'jakarta.persistence.Table'})
MATCH (a)-[:HAS]->(v:Value {name: 'name'})
MERGE (t:Table {name: v.value})
MERGE (c)-[:PERSISTS_TO]->(t)
RETURN c.name, t.name
----
```

---

## 10. 테스트 케이스

### 10-1. SlabDesignServiceTest

```java
@SpringBootTest
class SlabDesignServiceTest {
    
    @Autowired
    private SlabDesignService service;
    
    @Test
    void slab설계_정상케이스_FAB_60톤_주문() {
        // given (도메인 문서 Step 0 예제)
        Order order = Order.builder()
            .orderNo("01S3047892010")
            .productType("FAB")
            .orderQuantity(60.0)
            .targetWidth(1500)
            .hrTargetWidth(1529.0)
            .productThickness(0.65)
            .yieldRate(0.954436)
            .packagingWeightLower(8000.0)
            .packagingWeightUpper(12000.0)
            .build();
        
        // when
        SlabDesignResult result = service.design(order);
        
        // then
        assertEquals(250, result.getSlabThickness());
        assertEquals(1570, result.getTargetSlabWidth());  // 3pass 적용 후
        assertEquals(11300, result.getTargetSlabLength());
        assertEquals(34700.0, result.getSlabWeight(), 1.0);
        assertEquals(3, result.getSplitCount());
        assertEquals(2, result.getUnitCount());
        assertEquals("SUCCESS", result.getDesignStatus());
    }
    
    @Test
    void DG320에러_Edging매칭불가_케이스() {
        Order order = Order.builder()
            .orderNo("TEST-DG320")
            .hrTargetWidth(2500.0)  // 모든 Edging 기준 범위 외
            .build();
        
        assertThrows(DG320Exception.class, () -> service.design(order));
    }
    
    @Test
    void Step2_1차폭범위_올바른계산() {
        // given
        Order order = createOrderWithHrTargetWidth(939.5);
        
        // when
        WidthRange range = widthRangeCalculator.calculatePrimary(order, new SlabDesignResult());
        
        // then
        assertEquals(960, range.getLower());
        assertEquals(1110, range.getUpper());
    }
    
    @Test
    void Step10_2차폭범위_단중역산_검증() {
        // given
        double slabWeight = 23800;
        int thickness = 250;
        var primaryLength = new LengthRange(5500, 11880);
        var primaryWidth = new WidthRange(960, 1110);
        
        // when
        WidthRange result = widthRangeCalculator.calculateSecondary(
            slabWeight, thickness, primaryLength, primaryWidth, new SlabDesignResult()
        );
        
        // then
        assertEquals(1030, result.getLower());
        assertEquals(1110, result.getUpper());
    }
}
```

---

## 11. 작업 진행 순서

### Day 1: 프로젝트 셋업
- [ ] Spring Boot 3.2 프로젝트 생성 (Maven)
- [ ] 의존성 추가 (web, data-jpa, h2, validation, lombok, springdoc)
- [ ] application.yml 작성
- [ ] 패키지 구조 생성

### Day 2: 도메인 모델
- [ ] Order, SlabDesignResult, DesignStepLog Entity 작성
- [ ] WidthRange, LengthRange, WeightRange 값 객체
- [ ] 14개 Standard Entity 작성

### Day 3: Repository + 시드 데이터
- [ ] 14개 Standard Repository
- [ ] data.sql / schema.sql 작성
- [ ] 도메인 문서 SC070 예제 데이터 입력

### Day 4-5: 핵심 비즈니스 로직 (Step 1-7)
- [ ] WidthRangeCalculator (Step 2, 10, 12, 13)
- [ ] LengthRangeCalculator (Step 3, 11)
- [ ] WeightRangeCalculator (Step 4, 5, 6)
- [ ] SplitCountCalculator (Step 7, 8)
- [ ] DesignPolicyResolver (단중최대화 vs 제품단중최대화)

### Day 6: Step 8-14 + 통합
- [ ] SlabDesignService 메인 오케스트레이터
- [ ] DG320Exception 처리
- [ ] 통합 테스트 (예제 주문 01S3047892010)

### Day 7: API + Form
- [ ] SlabDesignController
- [ ] 14개 SDxxxForm CRUD 클래스
- [ ] OpenAPI/Swagger 자동 문서화

### Day 8: jQAssistant 통합
- [ ] pom.xml 플러그인 추가
- [ ] jqassistant/index.adoc 커스텀 규칙
- [ ] mvn jqassistant:scan 실행 → Neo4j 확인

### Day 9: 테스트 + 검증
- [ ] 단위 테스트 80% 커버리지
- [ ] 도메인 문서 예제 주문 4종 테스트 통과
- [ ] Postman 컬렉션 작성

---

## 12. 검증 시나리오 (필수 통과)

### 12-1. 정상 설계 시나리오 (도메인 문서 예제)

```
주문: 01S3047892010 (FAB, 60톤)
실행: POST /api/slab-design/execute/01S3047892010

기대 결과:
  slab_thickness: 250
  target_slab_width: 1570
  target_slab_length: 11300
  slab_weight: 34700
  split_count: 3
  unit_count: 2
  design_status: SUCCESS
  
  Step 로그 14개 모두 기록됨
```

### 12-2. DG320 에러 시나리오

```
주문: hrTargetWidth = 2500 (Edging 기준 범위 외)
실행: POST /api/slab-design/execute/...

기대 결과:
  HTTP 400
  error_code: DG320
  message: "Edging 기준 매칭 불가 - 목표폭(2500)이..."
```

### 12-3. Target단중 입력 시나리오

```
주문: 01S3018688050 (API-X52, Target단중 29.3)

기대 결과:
  target_slab_width: 1670 (3pass 적용)
  target_slab_length: 9080
  slab_weight: 29650
```

### 12-4. jQAssistant 추출 검증

```cypher
// Neo4j Browser에서 실행
MATCH (m:Method)-[:CALCULATES]->(s:Step)
RETURN s.step_number, m.name
ORDER BY s.step_number
```

기대: Step 1-14에 대해 각각 1개 이상의 메서드 매칭

```cypher
MATCH (c:Class)-[:RELATES_TO_STANDARD]->(std:Standard)
RETURN std.code, c.name
ORDER BY std.code
```

기대: 14개 Standard 모두에 Form 클래스 매칭

---

## 13. 주의사항

### 13-1. 명명 규칙 준수 ★★★
- **메서드명, Form 클래스명을 절대 임의로 바꾸지 말 것**
- 자동 매핑이 깨지면 온톨로지 Layer 3 구축이 실패함

### 13-2. 비중 상수
- 비중 7.82는 **`DensityConstant.STEEL_DENSITY`로만 사용**
- 코드에 7.82 매직 넘버 박지 말기

### 13-3. 10mm 단위 절상/절사
- 반드시 `RoundingUtil.ceilTo10mm()` / `floorTo10mm()` 사용
- 직접 `Math.ceil` 등 쓰지 말 것

### 13-4. 트랜잭션
- `SlabDesignService.design()`은 `@Transactional` 필수
- Step 로그가 함께 저장되어야 함

### 13-5. 로깅
- 각 Step 실행 시 SLF4J 로그 + DesignStepLog DB 기록 모두 필수

### 13-6. 다국어 처리
- 한글 메시지(에러 등)는 `messages.properties`에서 관리

---

## 14. 참고

- 도메인 지식 출처: `slab-design-domain-knowledge.md`
- Spring Boot 공식: https://spring.io/projects/spring-boot
- jQAssistant: https://jqassistant.github.io/
- 본 시스템은 **온톨로지 Layer 3의 자동 추출 대상**이 됨
