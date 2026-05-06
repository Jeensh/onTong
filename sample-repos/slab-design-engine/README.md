# Slab Design Engine (데모용)

onTong Section 2 모델링 엔진 실증용 Spring Boot 샘플. 직육면체 Slab 치수 설계 엔진으로 공정계획 단계에서 수주 사양을 받아 설비 제약을 만족하는 **최대 중량** 의 Slab 를 반환한다.

## 도메인 요약

- **Slab**: 길이×폭×두께(mm) + 강종. 중량 = 밀도 × 체적.
- **강종**: SS400 / SM490 / AH36 (밀도 7850~7860 kg/m³)
- **설비 제약** (`EquipmentProperties`):
  - 압연기 최대 폭 2400mm
  - 가열로 최대 길이 12000mm
  - 크레인 최대 하중 45000kg
  - 두께 범위 180~240mm
- **목적식**: `max ρ·L·W·T` s.t. 설비 제약 + 수주 범위
- **엔진**: 50mm 간격 그리드 탐색 → 제약 필터 → 최대 중량 선택

## 패키지 구조

```
com.ontong.slab
├── SlabDesignApplication        부팅 엔트리
├── config.EquipmentProperties   @ConfigurationProperties
├── domain.{Slab,OrderSpec,SteelGrade}
├── constraint.{ConstraintViolation,EquipmentConstraintChecker}
├── optimizer.{DesignCandidate,WeightMaximizer}
├── service.SlabDesignService
└── controller.SlabDesignController   POST /slabs/design
```

## 실행

```bash
mvn spring-boot:run
curl -X POST http://localhost:8090/slabs/design \
  -H "Content-Type: application/json" \
  -d '{
    "orderId":"OD-001",
    "grade":"SS400",
    "minLengthMm":8000, "maxLengthMm":11000,
    "minWidthMm":1800,  "maxWidthMm":2400,
    "minThicknessMm":200,"maxThicknessMm":240
  }'
```

## 의도적으로 심어둔 Gap 후보 (향후 기준서 비교용)

기준서가 아직 없어 현재 스캔 시 `code_only` / `manual_only` 양쪽 다 비어 있지만, 매뉴얼이 준비되면 아래 gap 이 자연스럽게 재현된다.

| # | 위치 | 코드 | (예상) 기준서 | Gap 유형 |
|---|------|------|---------------|----------|
| 1 | `EquipmentProperties.maxThicknessMm = 240.0` | 최대 두께 240mm | "최대 두께 250mm 이상 허용" | **CONFLICTS_WITH** (수량 mismatch) |
| 2 | `WeightMaximizer.WEIGHT_BIAS_FACTOR = 1.02` | 안전계수 1.02 | "압연 안전계수 1.05 적용" | **CONFLICTS_WITH** (수량 mismatch) |
| 3 | `WeightMaximizer.adjustWeightBias()` | 중량 편차 보정 메서드 | (기준서에 언급 없음) | **MISSING_IN** manual (code_only) |
| 4 | 크레인 재검증 누락 | `adjustWeightBias` 후 재검증 없음 | "보정 후 크레인 하중 재검증 필수" | **MISSING_IN** code (manual_only) |
| 5 | `EquipmentConstraintChecker.GRID_STEP_MM = 50.0` (optimizer) | 50mm 간격 그리드 | "그리드 간격 25mm 이하 권장" | **CONFLICTS_WITH** (수량 mismatch) |

## 데모 시나리오

1. 본 샘플을 코드 분석기에 등록 → 엔티티/관계 추출
2. 기준서(매뉴얼) 업로드 → ManualRegistry 에 fragments 등록
3. `POST /api/modeling/gaps/scan` → 위 5종 후보 자동 감지
4. `POST /api/modeling/gaps/{gap_id}/confirm` 으로 사람 검증

## 주의

- 실제 공정 로직은 훨씬 복잡함 (압연 패스 수, 냉각 프로파일, 재가열 여부 등). 본 샘플은 **파서·매핑·갭 탐지 엔진 실증**용 최소 구조.
- 매직넘버 5곳은 의도적으로 남겨둠 (240mm 상한 / 1.02 안전계수 / 50mm 그리드 등).
