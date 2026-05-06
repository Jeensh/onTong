# slab-design 데모 시나리오 — 드라마 DNA 활용 시연 케이스

이 문서는 **슬랩 설계 메타 툴 (온톨로지 매핑 + 영향도 분석 + 샌드박스 시뮬레이션) 의 시연 시나리오**를 정리합니다. 각 시나리오는 코드에 심어진 "드라마 DNA 시드"를 활용해 "이거 바꾸면 저기가 터진다" 또는 "겉보기에는 분리되어 있지만 도메인적으로 연결된 짝"을 시연합니다.

해커톤 영상에서 사용 권장: **시나리오 1, 3, 5, 8** (가장 시각적이고 즉시 공감되는 장면).

---

## 시나리오 1: 비표준 컬럼명 통합 (온톨로지 매핑 핵심)

### 시드
- ORDER_OM.PRODUCT_TYPE_CD VARCHAR2(4)
- CAST_SPEC.PRODUCT_TYPE_CD VARCHAR2(4)
- HR_SPEC.PRODUCT_TYPE_CD VARCHAR2(4)
- EDGING_GROUP.PRODUCT_TYPE_CD VARCHAR2(4)
- **CUSTOMER_STD.PRODUCT_NAME_CD VARCHAR2(3)**  ← 다른 이름·다른 크기
- **SD_PRODUCTIVITY_STD.PROD_KIND_CD VARCHAR2(4)**  ← 또 다른 이름

### 트리거
도구로 코드 + DB 스키마 분석.

### 도구가 보여줘야 할 것
- "이 6개 컬럼은 모두 동일한 도메인 개념(품명) 입니다" 라는 매핑 제안
- 사용자가 매핑 승인 → 온톨로지 모델에 통합 개념으로 등록
- 영향도 분석: "PRODUCT_NAME_CD VARCHAR2(3) 을 VARCHAR2(4) 로 확장하면, 다른 5 테이블도 동시에 보정해야 함" 같은 인사이트

### 시연 효과
- 심사원이 "정적 분석 도구는 이걸 절대 못 잡음" 인지
- 도구가 도메인 의미 기반으로 **표준화 안 된 레거시를 정렬**한다는 핵심 명제 입증

---

## 시나리오 2: 열연 코드 mismatch (HR_PLANT_CD vs HR_CD)

### 시드
- HR_SPEC.HR_PLANT_CD CHAR(1)
- HR_MIN_WGT.HR_CD CHAR(1)
- HR_MAX_WGT.HR_CD CHAR(1)

### 트리거
사용자가 HR_PLANT_CD 컬럼을 HR_PLANT_CODE 로 변경 시도.

### 도구가 보여줘야 할 것
- "HR_PLANT_CD 와 HR_CD 는 동일 도메인. 하나만 바꾸면 정합성 깨짐"
- 영향도: 변경되지 않는 HR_CD 사용처 (HR_MIN_WGT, HR_MAX_WGT 룩업) 목록
- 자동 제안: "HR_CD 도 같이 변경할까요?"

### 시연 효과
- 정적 도구는 "동명 컬럼"만 잡지만, 우리 도구는 "동의 컬럼"을 잡는다는 차별점

---

## 시나리오 3: 우선순위 룰 변경 → 영향도 시각화

### 시드
- EDGING_GROUP — PRIORITY ASC 매칭 (가장 작은 우선순위 1개 선택)
- CUSTOMER_STD — PRIORITY ASC 매칭

### 트리거
사용자가 EDGING_GROUP 의 특정 row 의 PRIORITY 값을 변경.

### 도구가 보여줘야 할 것
- 매칭 시뮬레이션: 변경 전 vs 변경 후 어느 row 가 선택되는지 비교
- 영향받는 주문: 매칭 결과가 달라지는 주문 N건 — 상세 목록
- 샌드박스: 변경 후 알고리즘 재실행 → 새 슬랩 설계 결과 비교

### 시연 효과
- "룰 1줄 변경 → 100건 주문 설계 결과 변동" 같은 충격적 임팩트
- 운영자가 "야, 이거 함부로 못 바꾸겠네" 하는 반응

---

## 시나리오 4: 2차원 sheet 룩업 (HR_MIN/MAX_WGT) 셀 변경

### 시드
- HR_MIN_WGT 2D sheet (THICKNESS × WIDTH → MIN_WGT)
- HR_MAX_WGT 2D sheet (동일 패턴)
- 룩업: cell.thickness ≥ input AND cell.width ≥ input, ORDER BY thickness ASC, width ASC LIMIT 1

### 트리거
사용자가 HR_MAX_WGT 의 (두께=200, 폭=1500) 셀의 단중을 30 → 25 톤 으로 변경.

### 도구가 보여줘야 할 것
- "이 셀이 cover 하는 입력 범위" 시각화 (해당 셀로 매칭되는 (두께, 폭) 영역)
- 영향받는 주문 = 그 영역에 떨어지는 슬랩들 → step 6 의 단중상한이 변동
- 샌드박스 재실행 → 매수·단중 변경 폭 수치화

### 시연 효과
- 2차원 룩업의 "셀 1개 변경의 fan-out" 을 그래픽으로 시연
- IntelliJ Call Hierarchy 로는 절대 불가능한 시각화

---

## 시나리오 5: 누적 실수율 — 한 공정 변경 → 전체 공정 영향

### 시드
- ProductivityService.cumulativeProductivity = 활성 공정 모두의 실수율 곱
- 각 활성 공정 (SM, HR, HRF, CR, ANL1, ANL2, GAL, CRF) 의 SD_PRODUCTIVITY_STD 룩업

### 트리거
열연 (HR) 공정의 특정 강종+품종+고객 조합 실수율을 0.95 → 0.92 로 하향.

### 도구가 보여줘야 할 것
- 변경된 row 가 곱셈에 들어가는 모든 공정 통과 주문 (HR 활성) 의 누적 실수율 변동
- 영향: step 6 (실수율고려 designPendQtyHigh = pendHigh / productivity) → 단중상한 변경
- 영향: step 9 (매수 = pendHigh / productivity / splitWgtHigh) → 매수 변경
- 영향: step 13 (slab단중 = pendHigh / productivity / 매수) → 결정 단중 변경
- 즉 한 공정 row 변경 → 알고리즘 3 군데에서 출력 변동 → 최종 슬랩 결과 영향

### 시연 효과
- 1 곱셈자 변경 → 알고리즘 전체에 fan-out
- "도메인 의미 기반 영향도" 의 정수

---

## 시나리오 6: '*' wildcard fallback 의존성 추적

### 시드
- EDGING_SPEC EDGING_GROUP_CD 의 `'*'` row = catchall fallback
- 정확매칭 우선 → 없으면 '*' 적용
- '*' 도 없으면 IllegalStateException

### 트리거
사용자가 EDGING_SPEC 의 '*' row 를 삭제.

### 도구가 보여줘야 할 것
- "이 '*' fallback 에 의존하는 (정확매칭 row 없는) edgingGroup 코드들" 식별
- 삭제 시 IllegalStateException 던지는 (즉 슬랩 설계 자체가 불가능해지는) 주문 N건
- 경고: "삭제 전에 [groupCd1, groupCd2, ...] 에 대한 정확매칭 row 를 먼저 추가하세요"

### 시연 효과
- 코드만 보면 보이지 않는 '*' fallback 의존성을 도구가 매핑
- 운영 사고 예방 (실제 SCM 에서 자주 발생하는 패턴)

---

## 시나리오 7: 하드코딩 매핑 (PlantMappingService) 도메인적 의미

### 시드
- PlantMappingService 의 `Map<제강코드, (연주코드, 머신코드)>` 하드코딩
- 알고리즘 step 1 (CAST_SPEC 룩업) 의 6-축 키 중 (연주, 머신) 출처

### 트리거
사용자가 "이 하드코딩 매핑을 std 테이블로 옮기고 싶다"

### 도구가 보여줘야 할 것
- 현재 매핑이 영향을 주는 모든 알고리즘 호출 지점 (CAST_SPEC 룩업 → step 1, step 2, step 3, step 4 등)
- 마이그레이션 청사진: PROC_MAPPING std 테이블 신설 + Service 변경 + 테스트 시드 데이터
- 샌드박스: std 테이블에 매핑 row 추가 → 결과 동일성 검증

### 시연 효과
- "레거시 하드코딩 → std 테이블 마이그레이션" 은 SCM 흔한 작업
- 도구가 마이그레이션의 영향 범위와 안전 검증을 자동화

---

## 시나리오 8: A-a 루프 분기 시뮬레이션 (드라마 DNA 핵심 무대)

### 시드
- SdDesigner.runAaLoop — 분할수 max → 1, step 8-10 (+ 12-13 fallback)
- 분할수 변경 시 splitWgtRange 재계산 → 매수 재계산 → slab단중 재계산
- 한 슬랩의 결정 (단중·매수·분할수) 이 분할수 1 차이만으로 크게 변동

### 트리거
사용자가 특정 주문에 대해 "분할수 = 3 으로 강제 설정" 을 시뮬레이션.

### 도구가 보여줘야 할 것
- A-a 루프의 "이 주문에 대해 자연 수렴 분할수 = 5" 인데 강제 3 으로 바꾸면:
  - splitWgtRange 변경
  - 매수 변경
  - slab단중 변경
  - 최종 폭/길이 변경
  - 결과: 주문당 슬랩 5장 → 3장 (재료 수율 변동)
- 샌드박스 실행: 강제 분할수로 재설계 → 결과 비교

### 시연 효과
- A-a 루프의 "한 변수 변경의 cascading effect" 시연
- 운영자가 "이래서 분할수 수동 조정이 위험하군" 이해

---

## 시나리오 9: cross-table validation (DG004) 의 의존성

### 시드
- SdOrderValidator DG004: 설계대기량 상한(ORDER_OS) ≥ 포장단중 하한(ORDER_OM)
- 두 다른 테이블의 컬럼이 도메인 규칙으로 결합

### 트리거
사용자가 ORDER_OM.PKG_WGT_LOW 를 일괄 +10% 상향.

### 도구가 보여줘야 할 것
- DG004 검증에 새로 fail 할 ORDER_OS 행들 식별 (영향도)
- "이 변경은 50건의 주문을 새로 fail 시킵니다 (DG004)" 경고
- 샌드박스: 한 주문 sample 로 fail 흐름 시연

### 시연 효과
- 두 테이블 사이 도메인 규칙 결합을 도구가 인식
- "ORDER_OM 한 컬럼 변경 → ORDER_OS 검증 영향" 같은 코드만 봐선 안 보이는 연결

---

## 시나리오 10: 원본/조정 패턴 (size 원복) 의 안전 검증

### 시드
- SLAB_RESULT 의 컬럼 쌍: SLAB_WIDTH ↔ SLAB_WIDTH_1, SLAB_LENGTH ↔ SLAB_LENGTH_1, ...
- 원본은 최초 설계 결과, _1 은 사이즈 조정 후 현재 값
- size 원복 = _1 값을 원본 값으로 되돌림

### 트리거
사용자가 "이 슬랩의 사이즈 조정을 원복" 시뮬레이션.

### 도구가 보여줘야 할 것
- 도메인 규칙: "_1 컬럼은 원본의 짝" 인식
- 원복 SQL 자동 생성: `UPDATE SLAB_RESULT SET WIDTH_1 = WIDTH, LENGTH_1 = LENGTH, ... WHERE SLAB_NO = ...`
- 샌드박스: 원복 후 슬랩 매수·단중 변경 시각화

### 시연 효과
- "원본/조정 짝" 의 도메인적 의미를 도구가 인식
- 짝 관계가 코드 명명 규칙 (suffix _1) 으로만 표현되는데, 도구가 이를 도메인 모델로 끌어올림

---

## 시나리오 11: 리플렉션 매핑 추적 (SDOrderLogic)

### 시드
- SDOrderLogic.copyByReflection — 4 JPO 필드명 매칭으로 SDOrderEntity 통합
- 정적 분석 도구가 "어떤 JPO 필드가 어떤 Entity 필드로 가는지" 추적 어려움
- "designPendQty" 같은 동명 필드의 first-non-null wins precedence

### 트리거
사용자가 ORDER_OS.DESIGN_PEND_QTY 컬럼명을 ORDER_OS.PEND_QTY 로 변경.

### 도구가 보여줘야 할 것
- 리플렉션 매핑 분석: SDOrderEntity.designPendQty 필드가 더 이상 OS JPO 에서 채워지지 않음
- 영향: ORDER_OM.designPendQty 가 winner 가 됨 (precedence 변경)
- 알고리즘 행동 변경: step 5/6/9 의 designPendQty 값이 OM 값으로 바뀜
- 샌드박스: 변경 전/후 알고리즘 결과 비교

### 시연 효과
- 리플렉션 매핑은 정적 분석 도구가 "암실" 영역
- 우리 도구가 이를 도메인 의미로 매핑해서 영향도 추적

---

## 시나리오 12: 비활성 공정 변경 → 알고리즘 흐름 변동

### 시드
- ORDER_OS.CONFIRMED_PLANT_CD 8자리 — 빈칸 ' ' 은 비활성
- SdOrderValidator (DG005) — 활성 공정 due date 점검
- ProductivityService.cumulativeProductivity — 활성 공정만 곱
- SdThicknessAction — 1자리 (제강) 활성 필수

### 트리거
사용자가 한 주문의 CONFIRMED_PLANT_CD 의 도금(GAL) 위치를 ' ' (비활성) 로 변경.

### 도구가 보여줘야 할 것
- 영향: DG005 (작업기한일) 점검에서 GAL_DUE 가 더 이상 점검되지 않음
- 영향: 누적 실수율 곱에서 GAL 공정이 제외 → 실수율 상승
- 영향: step 6 의 designPendQtyHigh / productivity 변동 → 단중상한 변경
- 영향: step 9 의 매수 변동 → 슬랩 매수 감소
- 결과: 같은 주문이 더 적은 슬랩으로 처리 가능

### 시연 효과
- "1자리 코드 변경 → 알고리즘 5군데 fan-out"
- CONFIRMED_PLANT_CD 의 도메인 의미 (8 공정 위치) 를 도구가 인식

---

## 시나리오 13: 재고주문 (DG001) 분기 시뮬레이션

### 시드
- ORDER_OS.STOCK_CODE = 1 → 재고주문 → DG001 fail (SdOrderValidator)
- 재고주문은 새 슬랩 설계 대상 아님 (기존 재고에서 출고)

### 트리거
사용자가 "이 주문을 재고주문으로 변경 시뮬레이션" (STOCK_CODE = 1 set).

### 도구가 보여줘야 할 것
- 영향: 이 주문은 SdOrderExtractor → SdOrderValidator 에서 DG001 fail
- 슬랩 설계 미실행, SLAB_RESULT 미저장
- HIST 에 DG001 errorCode 적재만
- 샌드박스: 재고주문 변경 → 알고리즘 진입 차단 시연

### 시연 효과
- 도메인 분기 (재고 vs 신규) 를 도구가 인식
- "이 1 비트 변경으로 알고리즘 자체가 안 돈다" 시연

---

# 시나리오 우선순위 (해커톤 영상 추천)

| 영상 시간 | 시나리오 | 이유 |
|---|---|---|
| 1분 (오프닝) | **#1 비표준 컬럼명 통합** | 데모의 핵심 가치 명제 즉시 입증 |
| 1.5분 | **#3 우선순위 룰 변경** | 시각적 임팩트 가장 큼 (대량 영향도 fan-out) |
| 1분 | **#5 누적 실수율** | 알고리즘 fan-out 의 정수 |
| 1분 | **#8 A-a 루프 분기** | 알고리즘 자체의 깊이 시연 |
| 30초 (마무리) | **#10 원본/조정 패턴** | 짧지만 인상적 — 도메인 모델링 깊이 |

총 5분 분량. 나머지 시나리오는 Q&A 또는 사후 자료로 활용.
