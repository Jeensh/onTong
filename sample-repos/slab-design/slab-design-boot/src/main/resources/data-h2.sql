-- slab-design 데모 시드 데이터 (H2 프로파일 전용)
-- 회사: '01' (cmpCd, length=2)
-- 소  : 'K' (광양제철소) / 'P' (포항제철소) — orgCd length=1
-- smCd: 'A' / 'B' 사용 (PlantMappingService: A→CC1/M1, B→CC2/M2 매핑)
--
-- ★ 시나리오 9건 — 정상 / 경계 / 에러 / step별 fail 커버.
-- TC01~TC08 = 광양 (orgCd='K') · TC09 = 포항 (orgCd='P') 로 cross-site 테스트 가능.
-- 각 orderNo 의 의도된 결과는 §slab-design.html Postman 가이드 §시나리오 표 참조.

------------------------------------------------------------
-- 1) ORDER_OS — 9건 후보 (모두 progress=C, closeFlag NULL)
------------------------------------------------------------
INSERT INTO ORDER_OS (
  CMP_CD, ORG_CD, ORDER_NO,
  OS_PROGRESS, CLOSE_FLAG, STOCK_CODE,
  DESIGN_PEND_QTY, DESIGN_PEND_QTY_LOW, DESIGN_PEND_QTY_HIGH,
  CONFIRMED_PLANT_CD, POSSIBLE_PLANT_CD,
  SM_DUE, HR_DUE, HRF_DUE, CR_DUE, ANL1_DUE, ANL2_DUE, GAL_DUE, CRF_DUE
) VALUES
  -- TC01 정상: SM=A (idx0) + HR='1' (idx1, hrTgtWidth_1 선택자). 나머지 비활성
  -- ※ confirmedPlantCd[1] 은 '1'~'5' 코드여야 SelectedHrTgtWidthResolver 가 hrTgtWidth_N 선택.
  --   'A' 같은 알파벳이면 selectedHrTgtWidth=null → step 2 DG103 보장.
  -- ★ 단위 통일 (2026-05-10): slab-design 코드는 모든 단중을 kg 단위로 처리
  --   (SdFirstWeightAction: mm³ × g/cm³ × 1e-6 = kg). 따라서 모든 wgt/qty 시드를 kg 단위로.
  --   도메인 의도 (slab-design.md):
  --     - 한 슬랩 = 8~32 ton (= 8000~32000 kg) → HR_MIN/MAX_WGT 단중 한도
  --     - 한 코일 = 5~28 ton → orderWgt/pkgWgt
  --     - 총 주문량 = N 슬랩 × yieldHi → designPendQty
  --
  -- TC01 도메인 의도 (kg 단위):
  --   secondWgtLow = max(firstWgtLow≈8903, hrMinWgt 8000, custStd.pkgWgtLow 5000) ≈ 8903
  --   secondWgtHigh = min(firstWgtHigh≈26494, hrMaxWgt 25000, custStd.pkgWgtHigh 30000, pendHigh/0.95) = 25000
  --   maxSplit = ceil(25000/15000/0.95) = 2
  --   N=1: splitWgtHigh = min(15000/0.95, 25000) = 15789
  --   step 9: slabCount = floor(100000/0.95/15789) = 6
  --   step 10: totalProduced = 94737, yieldRange=[84210, 105263] → satisfy → break
  ('01','K','TC01-NORMAL    ','C', NULL, 0,
   100000.000, 80000.000, 100000.000,
   'A1      ',
   'A1      ',
   DATE '2026-08-01', DATE '2026-08-15', NULL, NULL, NULL, NULL, NULL, NULL),

  -- TC02 정상 (smCd=B + HR='2'): SM=B → CC2/M2 매핑 (thickness=250).
  --   ★ HR_CD='2' 사용 (HR_MIN_WGT 격자 thickness=250 매칭). HR='1' 격자는 thickness=220 만 있음.
  --   designPendQty=120 ton 으로 매수 4~5장 수렴.
  ('01','K','TC02-NORMAL-B  ','C', NULL, 0,
   120000.000, 100000.000, 120000.000,
   'B2      ',
   'B2      ',
   DATE '2026-09-01', DATE '2026-09-15', NULL, NULL, NULL, NULL, NULL, NULL),

  -- TC03 경계: pkgWgtLow == pkgWgtHigh (DG003 경계 통과). designPendQty=80 ton
  ('01','K','TC03-BOUNDARY  ','C', NULL, 0,
   80000.000, 65000.000, 80000.000,
   'A1      ',
   'A1      ',
   DATE '2026-08-10', DATE '2026-08-20', NULL, NULL, NULL, NULL, NULL, NULL),

  -- TC04 ★ DG001 트리거: stockCode=1 (재고주문) — 다른 필드는 무관
  ('01','K','TC04-ERR-DG001 ','C', NULL, 1,
   10000.000, 10000.000, 10000.000,
   'A1      ',
   'A1      ',
   DATE '2026-08-30', DATE '2026-09-10', NULL, NULL, NULL, NULL, NULL, NULL),

  -- TC05 ★ DG005 트리거: HRF 활성인데 hrfDue NULL
  ('01','K','TC05-ERR-DG005 ','C', NULL, 0,
   30000.000, 20000.000, 35000.000,
   'A1A     ',  -- SM,HR,HRF 활성. HRF=A 활성인데 hrfDue 가 NULL → DG005
   'A1A     ',
   DATE '2026-08-05', DATE '2026-08-15', NULL, NULL, NULL, NULL, NULL, NULL),

  -- TC06 ★ DG101 (step 1) 트리거: 미존재 productTypeCd → CAST_SPEC 미매칭
  ('01','K','TC06-ERR-DG101 ','C', NULL, 0,
   40000.000, 25000.000, 45000.000,
   'A1      ',
   'A1      ',
   DATE '2026-09-01', DATE '2026-09-15', NULL, NULL, NULL, NULL, NULL, NULL),

  -- TC07 ★ DG102 (step 2) 트리거: HR 비활성 (확통[1]=' ') → 열연 폭 산정 불가
  ('01','K','TC07-ERR-DG102 ','C', NULL, 0,
   35000.000, 20000.000, 40000.000,
   'A       ',  -- SM 만 활성, HR 비활성
   'A       ',
   DATE '2026-08-10', NULL, NULL, NULL, NULL, NULL, NULL, NULL),

  -- TC08 ★ HR_MIN_WGT 격자 외 (step 5/6 fail): 큰 폭 (1900)
  ('01','K','TC08-ERR-WIDE  ','C', NULL, 0,
   55000.000, 40000.000, 60000.000,
   'A1      ',
   'A1      ',
   DATE '2026-09-05', DATE '2026-09-20', NULL, NULL, NULL, NULL, NULL, NULL),

  -- TC09 정상 (3 공정 활성): SM+HR+HRF (포항). HRF 0.93 누적 → productivity ≈ 0.8835
  ('01','P','TC09-NORMAL-3P ','C', NULL, 0,
   90000.000, 70000.000, 90000.000,
   'A1A     ',
   'A1A     ',
   DATE '2026-09-10', DATE '2026-09-20', DATE '2026-09-30', NULL, NULL, NULL, NULL, NULL);

------------------------------------------------------------
-- 2) ORDER_OM — 9 row 매칭
------------------------------------------------------------
INSERT INTO ORDER_OM (
  CMP_CD, ORG_CD, ORDER_NO,
  ORDER_WGT_LOW, ORDER_WGT_HIGH, ORDER_WIDTH, ORDER_LENGTH,
  DESIGN_PEND_QTY, WORK_DUE, PKG_WGT_LOW, PKG_WGT_HIGH,
  PRODUCT_TYPE_CD, CUSTOMER_CD, PROD_DUE, DELIVERY_DUE
) VALUES
  -- ★ ORDER_OM 도 모든 단중 시드 kg 단위로 ×1000 (slab-design 코드 일관성).
  -- TC01: orderWgt 10~15 ton (=10000~15000kg), pkgWgt 10~15 ton, designPendQty 100 ton.
  --   N=1 분할에서 slabCount=6 매로 수렴.
  ('01','K','TC01-NORMAL    ', 10000.000, 15000.000, 1200.00, 6000.00, 100000.000, DATE '2026-07-25', 10000.000, 15000.000, 'A001', 'CUST00001', DATE '2026-08-10', DATE '2026-08-20'),
  ('01','K','TC02-NORMAL-B  ',  6000.000, 28000.000, 1300.00, 7000.00, 120000.000, DATE '2026-08-25',  9000.000, 26000.000, 'A001', 'CUST00002', DATE '2026-09-10', DATE '2026-09-20'),
  ('01','K','TC03-BOUNDARY  ',  8000.000, 25000.000, 1400.00, 8000.00,  80000.000, DATE '2026-08-05', 20000.000, 20000.000, 'A001', 'CUST00001', DATE '2026-08-15', DATE '2026-08-25'),  -- pkgLow==pkgHigh
  ('01','K','TC04-ERR-DG001 ',  5000.000, 20000.000, 1000.00, 5000.00,  10000.000, DATE '2026-08-25',  5000.000, 15000.000, 'A001', 'CUST00001', DATE '2026-09-05', DATE '2026-09-15'),
  ('01','K','TC05-ERR-DG005 ',  7000.000, 27000.000, 1250.00, 6500.00,  30000.000, DATE '2026-08-01', 10000.000, 25000.000, 'A001', 'CUST00001', DATE '2026-08-15', DATE '2026-08-25'),
  ('01','K','TC06-ERR-DG101 ',  5000.000, 25000.000, 1100.00, 5500.00,  40000.000, DATE '2026-08-25',  8000.000, 20000.000, 'X999', 'CUST00001', DATE '2026-09-05', DATE '2026-09-15'),  -- X999 = 미시드 productType
  ('01','K','TC07-ERR-DG102 ',  6000.000, 22000.000, 1050.00, 5200.00,  35000.000, DATE '2026-08-05',  7000.000, 18000.000, 'A001', 'CUST00001', DATE '2026-08-15', DATE '2026-08-25'),
  ('01','K','TC08-ERR-WIDE  ',  8000.000, 30000.000, 1900.00, 9000.00,  55000.000, DATE '2026-09-01', 12000.000, 28000.000, 'A001', 'CUST00001', DATE '2026-09-15', DATE '2026-09-25'),  -- 1900 너무 넓음
  ('01','P','TC09-NORMAL-3P ',  7000.000, 28000.000, 1300.00, 7500.00,  90000.000, DATE '2026-09-05', 10000.000, 26000.000, 'A001', 'CUST00001', DATE '2026-09-15', DATE '2026-09-25');

------------------------------------------------------------
-- 3) ORDER_QD — 강종 + HR 목표폭 후보
------------------------------------------------------------
INSERT INTO ORDER_QD (CMP_CD, ORG_CD, ORDER_NO, GRADE_CD,
  HR_TGT_WIDTH_1, HR_TGT_WIDTH_2, HR_TGT_WIDTH_3, HR_TGT_WIDTH_4, HR_TGT_WIDTH_5
) VALUES
  ('01','K','TC01-NORMAL    ','G01', 1200.00, 1250.00, 1300.00, NULL, NULL),
  ('01','K','TC02-NORMAL-B  ','G02', 1300.00, 1350.00, NULL, NULL, NULL),
  ('01','K','TC03-BOUNDARY  ','G01', 1400.00, NULL, NULL, NULL, NULL),
  ('01','K','TC04-ERR-DG001 ','G01', 1000.00, NULL, NULL, NULL, NULL),
  ('01','K','TC05-ERR-DG005 ','G01', 1250.00, 1300.00, NULL, NULL, NULL),
  ('01','K','TC06-ERR-DG101 ','G01', 1100.00, NULL, NULL, NULL, NULL),
  ('01','K','TC07-ERR-DG102 ','G01', 1050.00, NULL, NULL, NULL, NULL),
  ('01','K','TC08-ERR-WIDE  ','G01', 1900.00, NULL, NULL, NULL, NULL),
  ('01','P','TC09-NORMAL-3P ','G01', 1300.00, 1350.00, NULL, NULL, NULL);

------------------------------------------------------------
-- 4) ORDER_CHEMICAL — 8 성분 표준값
------------------------------------------------------------
INSERT INTO ORDER_CHEMICAL (
  CMP_CD, ORG_CD, ORDER_NO,
  C_MIN, C_MAX, C_AIM, SI_MIN, SI_MAX, SI_AIM,
  MN_MIN, MN_MAX, MN_AIM, P_MIN, P_MAX, P_AIM,
  S_MIN, S_MAX, S_AIM, CR_MIN, CR_MAX, CR_AIM,
  NI_MIN, NI_MAX, NI_AIM, AL_MIN, AL_MAX, AL_AIM
) VALUES
  ('01','K','TC01-NORMAL    ', 0.05,0.15,0.10, 0.01,0.05,0.03, 0.30,0.80,0.55, 0.001,0.020,0.015, 0.001,0.020,0.010, 0.001,0.050,0.025, 0.001,0.050,0.025, 0.010,0.050,0.030),
  ('01','K','TC02-NORMAL-B  ', 0.05,0.15,0.10, 0.01,0.05,0.03, 0.30,0.80,0.55, 0.001,0.020,0.015, 0.001,0.020,0.010, 0.001,0.050,0.025, 0.001,0.050,0.025, 0.010,0.050,0.030),
  ('01','K','TC03-BOUNDARY  ', 0.05,0.15,0.10, 0.01,0.05,0.03, 0.30,0.80,0.55, 0.001,0.020,0.015, 0.001,0.020,0.010, 0.001,0.050,0.025, 0.001,0.050,0.025, 0.010,0.050,0.030),
  ('01','K','TC04-ERR-DG001 ', 0.05,0.15,0.10, 0.01,0.05,0.03, 0.30,0.80,0.55, 0.001,0.020,0.015, 0.001,0.020,0.010, 0.001,0.050,0.025, 0.001,0.050,0.025, 0.010,0.050,0.030),
  ('01','K','TC05-ERR-DG005 ', 0.05,0.15,0.10, 0.01,0.05,0.03, 0.30,0.80,0.55, 0.001,0.020,0.015, 0.001,0.020,0.010, 0.001,0.050,0.025, 0.001,0.050,0.025, 0.010,0.050,0.030),
  ('01','K','TC06-ERR-DG101 ', 0.05,0.15,0.10, 0.01,0.05,0.03, 0.30,0.80,0.55, 0.001,0.020,0.015, 0.001,0.020,0.010, 0.001,0.050,0.025, 0.001,0.050,0.025, 0.010,0.050,0.030),
  ('01','K','TC07-ERR-DG102 ', 0.05,0.15,0.10, 0.01,0.05,0.03, 0.30,0.80,0.55, 0.001,0.020,0.015, 0.001,0.020,0.010, 0.001,0.050,0.025, 0.001,0.050,0.025, 0.010,0.050,0.030),
  ('01','K','TC08-ERR-WIDE  ', 0.05,0.15,0.10, 0.01,0.05,0.03, 0.30,0.80,0.55, 0.001,0.020,0.015, 0.001,0.020,0.010, 0.001,0.050,0.025, 0.001,0.050,0.025, 0.010,0.050,0.030),
  ('01','P','TC09-NORMAL-3P ', 0.05,0.15,0.10, 0.01,0.05,0.03, 0.30,0.80,0.55, 0.001,0.020,0.015, 0.001,0.020,0.010, 0.001,0.050,0.025, 0.001,0.050,0.025, 0.010,0.050,0.030);

------------------------------------------------------------
-- 5) CAST_SPEC — step 1 thickness 룩업 (smCd=A/B, PlantMapping 호환)
--    PlantMappingService 매핑: A → CC1/M1, B → CC2/M2
------------------------------------------------------------
INSERT INTO CAST_SPEC (
  CMP_CD, ORG_CD, SM_CD, CAST_CD, MACHINE_CD, PRODUCT_TYPE_CD,
  SLAB_THICKNESS, WIDTH_LOW, WIDTH_HIGH, LENGTH_LOW, LENGTH_HIGH, WGT_LOW, WGT_HIGH
) VALUES
  -- ★ CAST_CD/MACHINE_CD 는 PlantMappingService 의 castCd()/machineCd() 와 일치해야 룩업 성공.
  --   PlantMappingService.createMapping(): A→PlantMapping("CC1","M1"), B→("CC2","M2"). trailing space X.
  ('01','K','A','CC1','M1','A001', 220.00,  900.00, 1900.00, 4000.00, 12000.00,  6.000, 35.000),
  ('01','K','B','CC2','M2','A001', 250.00,  950.00, 2000.00, 4500.00, 13000.00,  7.000, 38.000),
  ('01','P','A','CC1','M1','A001', 220.00,  900.00, 1900.00, 4000.00, 12000.00,  6.000, 35.000);  -- 포항
-- 의도적 미시드: productTypeCd='X999' → TC06 step 1 fail (DG101)

------------------------------------------------------------
-- 6) HR_SPEC — step 2/3/16/17 폭/길이 ∩ (hrPlantCd=A/B)
------------------------------------------------------------
INSERT INTO HR_SPEC (
  CMP_CD, ORG_CD, HR_PLANT_CD, PRODUCT_TYPE_CD,
  WIDTH_LOW, WIDTH_HIGH, LENGTH_LOW, LENGTH_HIGH
) VALUES
  -- ★ HR_PLANT_CD = confirmedPlantCd[1]. '1' 코드가 SelectedHrTgtWidthResolver 와 매칭.
  ('01','K','1','A001',  900.00, 1800.00, 4500.00, 11000.00),
  ('01','K','2','A001',  950.00, 1850.00, 4800.00, 11500.00),
  ('01','P','1','A001',  900.00, 1800.00, 4500.00, 11000.00);  -- 포항

------------------------------------------------------------
-- 7) HR_MIN_WGT / HR_MAX_WGT — 2D 격자 (hrCd=A/B, thickness×width)
--    조건 cell.thickness ≥ inputThickness AND cell.width ≥ inputWidth → ASC LIMIT 1
--    정상 시나리오: 1100 ≤ width ≤ 1500 + thickness 220/250
--    TC08 (width=1900) 는 1800 까지만 격자 → fail
------------------------------------------------------------
INSERT INTO HR_MIN_WGT (CMP_CD, ORG_CD, HR_CD, THICKNESS, WIDTH, MIN_WGT) VALUES
  -- HR_CD = confirmedPlantCd[1] = '1' (또는 '2'). MIN_WGT 단위 kg (×1000 from ton-style).
  ('01','K','1', 220.00, 1100.00,  8000.000),
  ('01','K','1', 220.00, 1300.00,  9000.000),
  ('01','K','1', 220.00, 1500.00, 10000.000),
  ('01','K','1', 220.00, 1800.00, 11000.000),
  ('01','K','2', 250.00, 1100.00,  9000.000),
  ('01','K','2', 250.00, 1300.00, 10000.000),
  ('01','K','2', 250.00, 1500.00, 11000.000),
  ('01','K','2', 250.00, 1800.00, 12000.000),
  ('01','P','1', 220.00, 1300.00,  9000.000),  -- 포항
  ('01','P','1', 220.00, 1500.00, 10000.000),
  ('01','P','1', 220.00, 1800.00, 11000.000);

INSERT INTO HR_MAX_WGT (CMP_CD, ORG_CD, HR_CD, THICKNESS, WIDTH, MAX_WGT) VALUES
  -- MAX_WGT 단위 kg.
  ('01','K','1', 220.00, 1100.00, 25000.000),
  ('01','K','1', 220.00, 1300.00, 28000.000),
  ('01','K','1', 220.00, 1500.00, 30000.000),
  ('01','K','1', 220.00, 1800.00, 32000.000),
  ('01','K','2', 250.00, 1100.00, 28000.000),
  ('01','K','2', 250.00, 1300.00, 30000.000),
  ('01','K','2', 250.00, 1500.00, 32000.000),
  ('01','K','2', 250.00, 1800.00, 35000.000),
  ('01','P','1', 220.00, 1300.00, 28000.000),  -- 포항
  ('01','P','1', 220.00, 1500.00, 30000.000),
  ('01','P','1', 220.00, 1800.00, 32000.000);

------------------------------------------------------------
-- 8) EDGING_GROUP — Edging 그룹 매핑 (priority 우선순위)
------------------------------------------------------------
INSERT INTO EDGING_GROUP (
  CMP_CD, ORG_CD, PRIORITY, EDGING_GROUP_CD,
  GRADE_CD, PRODUCT_TYPE_CD, CUSTOMER_CD,
  HR_TGT_WIDTH_LOW, HR_TGT_WIDTH_HIGH
) VALUES
  -- EDGING_GROUP customer 컬럼은 '=' 정확매치 (wildcard 자동 처리 X). 고객별 row 명시 필요.
  ('01','K', 1, 'EG-G01-A1 ', 'G01', 'A001', 'CUST00001', 1000.00, 1500.00),
  ('01','K', 2, 'EG-G01-A1 ', 'G01', 'A001', 'CUST00002', 1000.00, 1500.00),
  ('01','K', 3, 'EG-G02-A1 ', 'G02', 'A001', 'CUST00001', 1100.00, 1600.00),
  ('01','K', 4, 'EG-G02-A1 ', 'G02', 'A001', 'CUST00002', 1100.00, 1600.00),
  ('01','K', 9, 'EG-DEFAULT', 'G01', 'A001', 'CUST00001',  500.00, 2500.00),
  ('01','P', 1, 'EG-G01-A1 ', 'G01', 'A001', 'CUST00001', 1000.00, 1500.00),  -- 포항
  ('01','P', 9, 'EG-DEFAULT', 'G01', 'A001', 'CUST00001',  500.00, 2500.00);

------------------------------------------------------------
-- 9) EDGING_SPEC — group_cd 별 edging cap
------------------------------------------------------------
-- ★ EDGING_CAP_LOW / EDGING_CAP_HIGH 는 selectedHrTgtWidth 에 더해질 보정값 (+/- 단위 mm).
--   widthLow  = max(castSpec.low,  hrSpec.low,  selectedWidth + edgingCapLow )
--   widthHigh = min(castSpec.high, hrSpec.high, selectedWidth + edgingCapHigh)
--   → 둘이 양수+큰값이면 widthLow > widthHigh 로 invalid (DG104). +/-50 ~ +200 정도가 자연스러움.
INSERT INTO EDGING_SPEC (CMP_CD, ORG_CD, EDGING_GROUP_CD, EDGING_CAP_LOW, EDGING_CAP_HIGH) VALUES
  ('01','K','EG-G01-A1 ',  -50.00,  200.00),
  ('01','K','EG-G02-A1 ',  -50.00,  200.00),
  ('01','K','EG-DEFAULT', -100.00,  300.00),
  ('01','P','EG-G01-A1 ',  -50.00,  200.00),  -- 포항
  ('01','P','EG-DEFAULT', -100.00,  300.00);

------------------------------------------------------------
-- 10) SD_PRODUCTIVITY_STD — 8 공정 실수율 default
------------------------------------------------------------
INSERT INTO SD_PRODUCTIVITY_STD (CMP_CD, ORG_CD, PROC_CD, GRADE_CD, PROD_KIND_CD, CUSTOMER_CD, PRODUCTIVITY) VALUES
  ('01','K','SM  ', '*', '*', '*', 1.0000),
  ('01','K','HR  ', '*', '*', '*', 0.9500),
  ('01','K','HRF ', '*', '*', '*', 0.9300),
  ('01','K','CR  ', '*', '*', '*', 0.9400),
  ('01','K','ANL1', '*', '*', '*', 0.9200),
  ('01','K','ANL2', '*', '*', '*', 0.9200),
  ('01','K','GAL ', '*', '*', '*', 0.9100),
  ('01','K','CRF ', '*', '*', '*', 0.9300),
  -- 포항 (orgCd='P')
  ('01','P','SM  ', '*', '*', '*', 1.0000),
  ('01','P','HR  ', '*', '*', '*', 0.9500),
  ('01','P','HRF ', '*', '*', '*', 0.9300);

------------------------------------------------------------
-- 11) CUSTOMER_STD — 고객 포장단중 한도
------------------------------------------------------------
INSERT INTO CUSTOMER_STD (CMP_CD, ORG_CD, PRIORITY, PRODUCT_NAME_CD, CUSTOMER_CD, PKG_WGT_LOW, PKG_WGT_HIGH) VALUES
  -- PKG_WGT 단위 kg (×1000 from ton-style).
  ('01','K', 1, 'A01', 'CUST00001', 5000.000, 30000.000),
  ('01','K', 2, 'A01', 'CUST00002', 8000.000, 35000.000),
  ('01','K', 9, '*',   '*',         5000.000, 40000.000),
  ('01','P', 1, 'A01', 'CUST00001', 5000.000, 30000.000),  -- 포항
  ('01','P', 9, '*',   '*',         5000.000, 40000.000);
