-- ============================================================
-- 01_master.sql -- spec & rule master rows for 5 golden scenarios
-- Loaded by spring.sql.init after JPA ddl-auto creates schema.
-- All scenarios use cmpCd='K' orgCd='1'.
-- See SeedService for TRUNCATE order; this file populates only master tables.
-- ============================================================

-- ------------------------------------------------------------
-- CAST_SPEC -- 연주설비사양기준 (제강+품종 -> slab thickness, width range, length range)
-- PK: (CMP_CD, ORG_CD, SM_CD, CAST_CD, MACHINE_CD, PRODUCT_CD)
-- All 5 scenarios use confirmedPlantCd[0]='K' -> SM_CD='K'.
-- PlantMappingService is hard-coded to A/B/C/D so for U13 we just use the same SM='K'
-- with placeholder CAST_CD/MACHINE_CD ('CC1','M1') -- algorithm still works once the
-- mapping is updated; for now no-row-found triggers DG10x at run time, not at INSERT.
-- ------------------------------------------------------------
INSERT INTO CAST_SPEC (CMP_CD, ORG_CD, SM_CD, CAST_CD, MACHINE_CD, PRODUCT_CD,
                       SLAB_THICKNESS, WIDTH_LOW, WIDTH_HIGH, LENGTH_LOW, LENGTH_HIGH,
                       WGT_LOW, WGT_HIGH)
VALUES ('K', '1', 'K', 'CC1', 'M1', 'COIL',
        230.00, 800.00, 2000.00, 4000.00, 12000.00,
        10000.000, 30000.000);

INSERT INTO CAST_SPEC (CMP_CD, ORG_CD, SM_CD, CAST_CD, MACHINE_CD, PRODUCT_CD,
                       SLAB_THICKNESS, WIDTH_LOW, WIDTH_HIGH, LENGTH_LOW, LENGTH_HIGH,
                       WGT_LOW, WGT_HIGH)
VALUES ('K', '1', 'K', 'CC1', 'M1', 'FS',
        250.00, 800.00, 2200.00, 4000.00, 12000.00,
        10000.000, 32000.000);

-- SS41-specific row in case PlantMapping pulls a different cast for SS41 paths
-- (we use the SAME PK for COIL+SS41 since PK has no GRADE column; redundant entries
-- with GRADE-bearing tables handle SS41 sizing). The single COIL row above suffices
-- because CAST_SPEC has no GRADE column -- thickness depends only on (SM,CAST,MACHINE,PRODUCT).

-- ------------------------------------------------------------
-- HR_SPEC -- 열연설비사양기준 (열연공장+품종 -> width / length range)
-- PK: (CMP_CD, ORG_CD, HR_PLANT_CD, PRODUCT_CD)
-- All HR-active scenarios (S1/S2/S3/S5) use confirmedPlantCd[1]='1' so HR_PLANT_CD='1'
-- (the digit also doubles as the HR_TGT_WIDTH_N column index in SelectedHrTgtWidthResolver).
-- S4 short-circuits at validation (DG004) so HR_SPEC is never consulted there.
-- ------------------------------------------------------------
INSERT INTO HR_SPEC (CMP_CD, ORG_CD, HR_PLANT_CD, PRODUCT_CD,
                     WIDTH_LOW, WIDTH_HIGH, LENGTH_LOW, LENGTH_HIGH)
VALUES ('K', '1', '1', 'COIL',
        750.00, 2100.00, 3500.00, 13000.00);

INSERT INTO HR_SPEC (CMP_CD, ORG_CD, HR_PLANT_CD, PRODUCT_CD,
                     WIDTH_LOW, WIDTH_HIGH, LENGTH_LOW, LENGTH_HIGH)
VALUES ('K', '1', '1', 'FS',
        750.00, 2300.00, 3500.00, 13000.00);

-- ------------------------------------------------------------
-- EDGING_GROUP -- (강종, 품종, 고객사, 열연목표폭) -> EDGING_GROUP_CD
-- PK: (CMP_CD, ORG_CD, PRIORITY)
-- One row per (grade, customer) combination used by the 5 scenarios.
-- ------------------------------------------------------------
INSERT INTO EDGING_GROUP (CMP_CD, ORG_CD, PRIORITY,
                          EDGING_GROUP_CD, GRADE_CD, PRODUCT_CD, CUSTOMER_CD,
                          HR_TGT_WIDTH_LOW, HR_TGT_WIDTH_HIGH)
VALUES ('K', '1', 1,
        'EG-A', 'SS400', 'COIL', 'CUST-001',
        500.00, 2500.00);

INSERT INTO EDGING_GROUP (CMP_CD, ORG_CD, PRIORITY,
                          EDGING_GROUP_CD, GRADE_CD, PRODUCT_CD, CUSTOMER_CD,
                          HR_TGT_WIDTH_LOW, HR_TGT_WIDTH_HIGH)
VALUES ('K', '1', 2,
        'EG-B', 'SS41', 'COIL', 'CUST-FAIL',
        500.00, 2500.00);

-- ------------------------------------------------------------
-- EDGING_SPEC -- edging cap_low/high per group
-- PK: (CMP_CD, ORG_CD, EDGING_GROUP_CD).  '*' is catchall fallback.
-- ------------------------------------------------------------
INSERT INTO EDGING_SPEC (CMP_CD, ORG_CD, EDGING_GROUP_CD,
                         EDGING_CAP_LOW, EDGING_CAP_HIGH)
VALUES ('K', '1', 'EG-A', -50.00, 50.00);

INSERT INTO EDGING_SPEC (CMP_CD, ORG_CD, EDGING_GROUP_CD,
                         EDGING_CAP_LOW, EDGING_CAP_HIGH)
VALUES ('K', '1', 'EG-B', -50.00, 50.00);

INSERT INTO EDGING_SPEC (CMP_CD, ORG_CD, EDGING_GROUP_CD,
                         EDGING_CAP_LOW, EDGING_CAP_HIGH)
VALUES ('K', '1', '*', -100.00, 100.00);

-- ------------------------------------------------------------
-- CUSTOMER_STD -- 고객사 단중 제한 (단위: kg)
-- PK: (CMP_CD, ORG_CD, PRIORITY)
-- CUST-001: comfortable range 5,000-25,000 kg per coil (admits S1/S2/S3/S5).
-- CUST-FAIL: NOT consulted at runtime — S4 short-circuits at validator (DG004) before
--            algorithm reaches CUSTOMER_STD lookup. Kept here for completeness.
-- NOTE: All weights stored as kg to align with SdFirstWeightAction's mm³×g/cm³×1e-6 = kg.
-- ------------------------------------------------------------
INSERT INTO CUSTOMER_STD (CMP_CD, ORG_CD, PRIORITY,
                          PRODUCT_CD, CUSTOMER_CD,
                          PKG_WGT_LOW, PKG_WGT_HIGH)
VALUES ('K', '1', 1,
        'COI', 'CUST-001',
        5000.000, 25000.000);

INSERT INTO CUSTOMER_STD (CMP_CD, ORG_CD, PRIORITY,
                          PRODUCT_CD, CUSTOMER_CD,
                          PKG_WGT_LOW, PKG_WGT_HIGH)
VALUES ('K', '1', 2,
        'COI', 'CUST-FAIL',
        100.000, 200.000);

-- ------------------------------------------------------------
-- HR_MIN_WGT -- 압연 MIN 단중 (2D sheet on thickness x width); 단위: kg
-- PK: (CMP_CD, ORG_CD, HR_CD, THICKNESS, WIDTH)
-- Typical slab MIN weight ~5,000 kg (5 tonnes) at 230mm thickness.
-- ------------------------------------------------------------
INSERT INTO HR_MIN_WGT (CMP_CD, ORG_CD, HR_CD, THICKNESS, WIDTH, MIN_WGT)
VALUES ('K', '1', '1', 230.00, 1200.00, 5000.000);
INSERT INTO HR_MIN_WGT (CMP_CD, ORG_CD, HR_CD, THICKNESS, WIDTH, MIN_WGT)
VALUES ('K', '1', '1', 230.00, 1500.00, 5000.000);
INSERT INTO HR_MIN_WGT (CMP_CD, ORG_CD, HR_CD, THICKNESS, WIDTH, MIN_WGT)
VALUES ('K', '1', '1', 230.00, 2200.00, 5000.000);
INSERT INTO HR_MIN_WGT (CMP_CD, ORG_CD, HR_CD, THICKNESS, WIDTH, MIN_WGT)
VALUES ('K', '1', '1', 250.00, 1500.00, 5000.000);
INSERT INTO HR_MIN_WGT (CMP_CD, ORG_CD, HR_CD, THICKNESS, WIDTH, MIN_WGT)
VALUES ('K', '1', '1', 250.00, 2200.00, 5000.000);

-- ------------------------------------------------------------
-- HR_MAX_WGT -- 압연 MAX 단중 (same shape as HR_MIN_WGT); 단위: kg
-- Typical slab MAX weight ~30,000 kg (30 tonnes).
-- ------------------------------------------------------------
INSERT INTO HR_MAX_WGT (CMP_CD, ORG_CD, HR_CD, THICKNESS, WIDTH, MAX_WGT)
VALUES ('K', '1', '1', 230.00, 1200.00, 30000.000);
INSERT INTO HR_MAX_WGT (CMP_CD, ORG_CD, HR_CD, THICKNESS, WIDTH, MAX_WGT)
VALUES ('K', '1', '1', 230.00, 1500.00, 30000.000);
INSERT INTO HR_MAX_WGT (CMP_CD, ORG_CD, HR_CD, THICKNESS, WIDTH, MAX_WGT)
VALUES ('K', '1', '1', 230.00, 2200.00, 30000.000);
INSERT INTO HR_MAX_WGT (CMP_CD, ORG_CD, HR_CD, THICKNESS, WIDTH, MAX_WGT)
VALUES ('K', '1', '1', 250.00, 1500.00, 30000.000);
INSERT INTO HR_MAX_WGT (CMP_CD, ORG_CD, HR_CD, THICKNESS, WIDTH, MAX_WGT)
VALUES ('K', '1', '1', 250.00, 2200.00, 30000.000);

-- ------------------------------------------------------------
-- SD_PRODUCTIVITY_STD -- 공정별 실수율
-- PK: (CMP_CD, ORG_CD, PROC_CD, GRADE_CD, PRODUCT_CD, CUSTOMER_CD)
-- Coverage:
--   S1 active SM,CR with SS400+COIL+CUST-001
--   S2 active SM,HR with SS400+COIL+CUST-001
--   S3 active SM,HR,HRF,CR with SS400+COIL+CUST-001
--   S4 active SM,HR with SS41+COIL+CUST-FAIL
--   S5 active SM,CRF with SS400+COIL+CUST-001
-- ------------------------------------------------------------
INSERT INTO SD_PRODUCTIVITY_STD (CMP_CD, ORG_CD, PROC_CD, GRADE_CD, PRODUCT_CD, CUSTOMER_CD, PRODUCTIVITY)
VALUES ('K', '1', 'SM',  'SS400', 'COIL', 'CUST-001', 0.9800);
INSERT INTO SD_PRODUCTIVITY_STD (CMP_CD, ORG_CD, PROC_CD, GRADE_CD, PRODUCT_CD, CUSTOMER_CD, PRODUCTIVITY)
VALUES ('K', '1', 'HR',  'SS400', 'COIL', 'CUST-001', 0.9700);
INSERT INTO SD_PRODUCTIVITY_STD (CMP_CD, ORG_CD, PROC_CD, GRADE_CD, PRODUCT_CD, CUSTOMER_CD, PRODUCTIVITY)
VALUES ('K', '1', 'HRF', 'SS400', 'COIL', 'CUST-001', 0.9600);
INSERT INTO SD_PRODUCTIVITY_STD (CMP_CD, ORG_CD, PROC_CD, GRADE_CD, PRODUCT_CD, CUSTOMER_CD, PRODUCTIVITY)
VALUES ('K', '1', 'CR',  'SS400', 'COIL', 'CUST-001', 0.9500);
INSERT INTO SD_PRODUCTIVITY_STD (CMP_CD, ORG_CD, PROC_CD, GRADE_CD, PRODUCT_CD, CUSTOMER_CD, PRODUCTIVITY)
VALUES ('K', '1', 'ANL1','SS400', 'COIL', 'CUST-001', 0.9900);
INSERT INTO SD_PRODUCTIVITY_STD (CMP_CD, ORG_CD, PROC_CD, GRADE_CD, PRODUCT_CD, CUSTOMER_CD, PRODUCTIVITY)
VALUES ('K', '1', 'ANL2','SS400', 'COIL', 'CUST-001', 0.9900);
INSERT INTO SD_PRODUCTIVITY_STD (CMP_CD, ORG_CD, PROC_CD, GRADE_CD, PRODUCT_CD, CUSTOMER_CD, PRODUCTIVITY)
VALUES ('K', '1', 'GAL', 'SS400', 'COIL', 'CUST-001', 0.9700);
INSERT INTO SD_PRODUCTIVITY_STD (CMP_CD, ORG_CD, PROC_CD, GRADE_CD, PRODUCT_CD, CUSTOMER_CD, PRODUCTIVITY)
VALUES ('K', '1', 'CRF', 'SS400', 'COIL', 'CUST-001', 0.9400);

-- SS41 + CUST-FAIL coverage for S4
INSERT INTO SD_PRODUCTIVITY_STD (CMP_CD, ORG_CD, PROC_CD, GRADE_CD, PRODUCT_CD, CUSTOMER_CD, PRODUCTIVITY)
VALUES ('K', '1', 'SM', 'SS41', 'COIL', 'CUST-FAIL', 0.9800);
INSERT INTO SD_PRODUCTIVITY_STD (CMP_CD, ORG_CD, PROC_CD, GRADE_CD, PRODUCT_CD, CUSTOMER_CD, PRODUCTIVITY)
VALUES ('K', '1', 'HR', 'SS41', 'COIL', 'CUST-FAIL', 0.9700);
