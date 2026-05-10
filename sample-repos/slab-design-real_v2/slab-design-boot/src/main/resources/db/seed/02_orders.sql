-- ============================================================
-- 02_orders.sql -- 5 golden scenario orders (ORDER_OS / OM / QD / CHEMICAL)
-- Loaded by spring.sql.init after 01_master.sql.
-- All 5 use cmpCd='K', orgCd='1'.
-- osProgress='C' (designable), closeFlag NULL (not closed) -- so findDesignable() picks them up.
-- stockCode=0 (not stock; 1 would trigger DG001).
-- ============================================================

-- ============================================================
-- ORDER_OS rows -- 진도/포장 위치/단중 한도
-- ============================================================
INSERT INTO ORDER_OS (CMP_CD, ORG_CD, ORDER_NO,
                      OS_PROGRESS, CLOSE_FLAG, STOCK_CODE,
                      DESIGN_PEND_QTY_HIGH, DESIGN_PEND_QTY_LOW, DESIGN_PEND_QTY,
                      CONFIRMED_PLANT_CD, POSSIBLE_PLANT_CD,
                      SM_DUE, HR_DUE, HRF_DUE, CR_DUE, ANL1_DUE, ANL2_DUE, GAL_DUE, CRF_DUE)
VALUES ('K', '1', 'ORD20260510001',
        'C', NULL, 0,
        12.000, 8.000, 10.000,
        'K   K   ', 'K   K   ',
        DATE '2026-12-31', NULL, NULL, DATE '2026-12-31', NULL, NULL, NULL, NULL);

INSERT INTO ORDER_OS (CMP_CD, ORG_CD, ORDER_NO,
                      OS_PROGRESS, CLOSE_FLAG, STOCK_CODE,
                      DESIGN_PEND_QTY_HIGH, DESIGN_PEND_QTY_LOW, DESIGN_PEND_QTY,
                      CONFIRMED_PLANT_CD, POSSIBLE_PLANT_CD,
                      SM_DUE, HR_DUE, HRF_DUE, CR_DUE, ANL1_DUE, ANL2_DUE, GAL_DUE, CRF_DUE)
VALUES ('K', '1', 'ORD20260510002',
        'C', NULL, 0,
        80.000, 60.000, 70.000,
        'KK      ', 'KK      ',
        DATE '2026-12-31', DATE '2026-12-31', NULL, NULL, NULL, NULL, NULL, NULL);

INSERT INTO ORDER_OS (CMP_CD, ORG_CD, ORDER_NO,
                      OS_PROGRESS, CLOSE_FLAG, STOCK_CODE,
                      DESIGN_PEND_QTY_HIGH, DESIGN_PEND_QTY_LOW, DESIGN_PEND_QTY,
                      CONFIRMED_PLANT_CD, POSSIBLE_PLANT_CD,
                      SM_DUE, HR_DUE, HRF_DUE, CR_DUE, ANL1_DUE, ANL2_DUE, GAL_DUE, CRF_DUE)
VALUES ('K', '1', 'ORD20260510003',
        'C', NULL, 0,
        25.000, 20.000, 22.000,
        'KKKK    ', 'KKKK    ',
        DATE '2026-12-31', DATE '2026-12-31', DATE '2026-12-31', DATE '2026-12-31', NULL, NULL, NULL, NULL);

INSERT INTO ORDER_OS (CMP_CD, ORG_CD, ORDER_NO,
                      OS_PROGRESS, CLOSE_FLAG, STOCK_CODE,
                      DESIGN_PEND_QTY_HIGH, DESIGN_PEND_QTY_LOW, DESIGN_PEND_QTY,
                      CONFIRMED_PLANT_CD, POSSIBLE_PLANT_CD,
                      SM_DUE, HR_DUE, HRF_DUE, CR_DUE, ANL1_DUE, ANL2_DUE, GAL_DUE, CRF_DUE)
VALUES ('K', '1', 'ORD20260510004',
        'C', NULL, 0,
        12.000, 8.000, 10.000,
        'KK      ', 'KK      ',
        DATE '2026-12-31', DATE '2026-12-31', NULL, NULL, NULL, NULL, NULL, NULL);

INSERT INTO ORDER_OS (CMP_CD, ORG_CD, ORDER_NO,
                      OS_PROGRESS, CLOSE_FLAG, STOCK_CODE,
                      DESIGN_PEND_QTY_HIGH, DESIGN_PEND_QTY_LOW, DESIGN_PEND_QTY,
                      CONFIRMED_PLANT_CD, POSSIBLE_PLANT_CD,
                      SM_DUE, HR_DUE, HRF_DUE, CR_DUE, ANL1_DUE, ANL2_DUE, GAL_DUE, CRF_DUE)
VALUES ('K', '1', 'ORD20260510005',
        'C', NULL, 0,
        10.000, 6.000, 8.000,
        'K      K', 'K      K',
        DATE '2026-12-31', NULL, NULL, NULL, NULL, NULL, NULL, DATE '2026-12-31');

-- ============================================================
-- ORDER_OM rows -- 폭/길이/단중/품종/고객사
-- ============================================================
INSERT INTO ORDER_OM (CMP_CD, ORG_CD, ORDER_NO,
                      ORDER_WGT_LOW, ORDER_WGT_HIGH, ORDER_WIDTH, ORDER_LENGTH,
                      DESIGN_PEND_QTY, WORK_DUE,
                      PKG_WGT_LOW, PKG_WGT_HIGH,
                      PRODUCT_CD, CUSTOMER_CD, PROD_DUE, DELIVERY_DUE)
VALUES ('K', '1', 'ORD20260510001',
        8.000, 12.000, 1200.00, 8500.00,
        10.000, DATE '2026-12-31',
        8.000, 18.000,
        'COIL', 'CUST-001', DATE '2026-12-15', DATE '2026-12-31');

INSERT INTO ORDER_OM (CMP_CD, ORG_CD, ORDER_NO,
                      ORDER_WGT_LOW, ORDER_WGT_HIGH, ORDER_WIDTH, ORDER_LENGTH,
                      DESIGN_PEND_QTY, WORK_DUE,
                      PKG_WGT_LOW, PKG_WGT_HIGH,
                      PRODUCT_CD, CUSTOMER_CD, PROD_DUE, DELIVERY_DUE)
VALUES ('K', '1', 'ORD20260510002',
        60.000, 80.000, 1100.00, 32000.00,
        70.000, DATE '2026-12-31',
        15.000, 22.000,
        'COIL', 'CUST-001', DATE '2026-12-15', DATE '2026-12-31');

INSERT INTO ORDER_OM (CMP_CD, ORG_CD, ORDER_NO,
                      ORDER_WGT_LOW, ORDER_WGT_HIGH, ORDER_WIDTH, ORDER_LENGTH,
                      DESIGN_PEND_QTY, WORK_DUE,
                      PKG_WGT_LOW, PKG_WGT_HIGH,
                      PRODUCT_CD, CUSTOMER_CD, PROD_DUE, DELIVERY_DUE)
VALUES ('K', '1', 'ORD20260510003',
        20.000, 25.000, 1300.00, 16000.00,
        22.000, DATE '2026-12-31',
        20.000, 23.000,
        'COIL', 'CUST-001', DATE '2026-12-15', DATE '2026-12-31');

INSERT INTO ORDER_OM (CMP_CD, ORG_CD, ORDER_NO,
                      ORDER_WGT_LOW, ORDER_WGT_HIGH, ORDER_WIDTH, ORDER_LENGTH,
                      DESIGN_PEND_QTY, WORK_DUE,
                      PKG_WGT_LOW, PKG_WGT_HIGH,
                      PRODUCT_CD, CUSTOMER_CD, PROD_DUE, DELIVERY_DUE)
VALUES ('K', '1', 'ORD20260510004',
        8.000, 12.000, 1200.00, 8000.00,
        10.000, DATE '2026-12-31',
        8.000, 18.000,
        'COIL', 'CUST-FAIL', DATE '2026-12-15', DATE '2026-12-31');

INSERT INTO ORDER_OM (CMP_CD, ORG_CD, ORDER_NO,
                      ORDER_WGT_LOW, ORDER_WGT_HIGH, ORDER_WIDTH, ORDER_LENGTH,
                      DESIGN_PEND_QTY, WORK_DUE,
                      PKG_WGT_LOW, PKG_WGT_HIGH,
                      PRODUCT_CD, CUSTOMER_CD, PROD_DUE, DELIVERY_DUE)
VALUES ('K', '1', 'ORD20260510005',
        6.000, 10.000, 1100.00, 7000.00,
        8.000, DATE '2026-12-31',
        6.000, 12.000,
        'COIL', 'CUST-001', DATE '2026-12-15', DATE '2026-12-31');

-- ============================================================
-- ORDER_QD rows -- 강종 + 5종 열연목표폭
-- HR_TGT_WIDTH_2 is consumed when confirmedPlantCd[1] is active (S2/S3/S4 cases).
-- All 5 columns filled with the same value to simplify SelectedHrTgtWidthResolver.
-- ============================================================
INSERT INTO ORDER_QD (CMP_CD, ORG_CD, ORDER_NO,
                      GRADE_CD,
                      HR_TGT_WIDTH_1, HR_TGT_WIDTH_2, HR_TGT_WIDTH_3, HR_TGT_WIDTH_4, HR_TGT_WIDTH_5)
VALUES ('K', '1', 'ORD20260510001',
        'SS400',
        1200.00, 1200.00, 1200.00, 1200.00, 1200.00);

INSERT INTO ORDER_QD (CMP_CD, ORG_CD, ORDER_NO,
                      GRADE_CD,
                      HR_TGT_WIDTH_1, HR_TGT_WIDTH_2, HR_TGT_WIDTH_3, HR_TGT_WIDTH_4, HR_TGT_WIDTH_5)
VALUES ('K', '1', 'ORD20260510002',
        'SS400',
        1100.00, 1100.00, 1100.00, 1100.00, 1100.00);

INSERT INTO ORDER_QD (CMP_CD, ORG_CD, ORDER_NO,
                      GRADE_CD,
                      HR_TGT_WIDTH_1, HR_TGT_WIDTH_2, HR_TGT_WIDTH_3, HR_TGT_WIDTH_4, HR_TGT_WIDTH_5)
VALUES ('K', '1', 'ORD20260510003',
        'SS400',
        1300.00, 1300.00, 1300.00, 1300.00, 1300.00);

INSERT INTO ORDER_QD (CMP_CD, ORG_CD, ORDER_NO,
                      GRADE_CD,
                      HR_TGT_WIDTH_1, HR_TGT_WIDTH_2, HR_TGT_WIDTH_3, HR_TGT_WIDTH_4, HR_TGT_WIDTH_5)
VALUES ('K', '1', 'ORD20260510004',
        'SS41',
        1200.00, 1200.00, 1200.00, 1200.00, 1200.00);

INSERT INTO ORDER_QD (CMP_CD, ORG_CD, ORDER_NO,
                      GRADE_CD,
                      HR_TGT_WIDTH_1, HR_TGT_WIDTH_2, HR_TGT_WIDTH_3, HR_TGT_WIDTH_4, HR_TGT_WIDTH_5)
VALUES ('K', '1', 'ORD20260510005',
        'SS400',
        1100.00, 1100.00, 1100.00, 1100.00, 1100.00);

-- ============================================================
-- ORDER_CHEMICAL rows -- 8 elements x {MIN,MAX,AIM} = 24 cols.
-- 21-step algorithm does not consult these directly; placeholder values for now.
-- All scenarios get the same plain-carbon profile.
-- ============================================================
INSERT INTO ORDER_CHEMICAL (CMP_CD, ORG_CD, ORDER_NO,
                            C_MIN, C_MAX, C_AIM,
                            SI_MIN, SI_MAX, SI_AIM,
                            MN_MIN, MN_MAX, MN_AIM,
                            P_MIN, P_MAX, P_AIM,
                            S_MIN, S_MAX, S_AIM,
                            CR_MIN, CR_MAX, CR_AIM,
                            NI_MIN, NI_MAX, NI_AIM,
                            AL_MIN, AL_MAX, AL_AIM)
VALUES ('K', '1', 'ORD20260510001',
        0.0500, 0.1500, 0.1000,
        0.0000, 0.3500, 0.1500,
        0.3000, 0.8000, 0.5500,
        0.0000, 0.0400, 0.0200,
        0.0000, 0.0400, 0.0200,
        0.0000, 0.2000, 0.0500,
        0.0000, 0.2000, 0.0500,
        0.0100, 0.0500, 0.0300);

INSERT INTO ORDER_CHEMICAL (CMP_CD, ORG_CD, ORDER_NO,
                            C_MIN, C_MAX, C_AIM,
                            SI_MIN, SI_MAX, SI_AIM,
                            MN_MIN, MN_MAX, MN_AIM,
                            P_MIN, P_MAX, P_AIM,
                            S_MIN, S_MAX, S_AIM,
                            CR_MIN, CR_MAX, CR_AIM,
                            NI_MIN, NI_MAX, NI_AIM,
                            AL_MIN, AL_MAX, AL_AIM)
VALUES ('K', '1', 'ORD20260510002',
        0.0500, 0.1500, 0.1000,
        0.0000, 0.3500, 0.1500,
        0.3000, 0.8000, 0.5500,
        0.0000, 0.0400, 0.0200,
        0.0000, 0.0400, 0.0200,
        0.0000, 0.2000, 0.0500,
        0.0000, 0.2000, 0.0500,
        0.0100, 0.0500, 0.0300);

INSERT INTO ORDER_CHEMICAL (CMP_CD, ORG_CD, ORDER_NO,
                            C_MIN, C_MAX, C_AIM,
                            SI_MIN, SI_MAX, SI_AIM,
                            MN_MIN, MN_MAX, MN_AIM,
                            P_MIN, P_MAX, P_AIM,
                            S_MIN, S_MAX, S_AIM,
                            CR_MIN, CR_MAX, CR_AIM,
                            NI_MIN, NI_MAX, NI_AIM,
                            AL_MIN, AL_MAX, AL_AIM)
VALUES ('K', '1', 'ORD20260510003',
        0.0500, 0.1500, 0.1000,
        0.0000, 0.3500, 0.1500,
        0.3000, 0.8000, 0.5500,
        0.0000, 0.0400, 0.0200,
        0.0000, 0.0400, 0.0200,
        0.0000, 0.2000, 0.0500,
        0.0000, 0.2000, 0.0500,
        0.0100, 0.0500, 0.0300);

INSERT INTO ORDER_CHEMICAL (CMP_CD, ORG_CD, ORDER_NO,
                            C_MIN, C_MAX, C_AIM,
                            SI_MIN, SI_MAX, SI_AIM,
                            MN_MIN, MN_MAX, MN_AIM,
                            P_MIN, P_MAX, P_AIM,
                            S_MIN, S_MAX, S_AIM,
                            CR_MIN, CR_MAX, CR_AIM,
                            NI_MIN, NI_MAX, NI_AIM,
                            AL_MIN, AL_MAX, AL_AIM)
VALUES ('K', '1', 'ORD20260510004',
        0.0700, 0.2000, 0.1500,
        0.0000, 0.4000, 0.2000,
        0.3000, 0.9000, 0.6500,
        0.0000, 0.0400, 0.0200,
        0.0000, 0.0400, 0.0200,
        0.0000, 0.2000, 0.0500,
        0.0000, 0.2000, 0.0500,
        0.0100, 0.0500, 0.0300);

INSERT INTO ORDER_CHEMICAL (CMP_CD, ORG_CD, ORDER_NO,
                            C_MIN, C_MAX, C_AIM,
                            SI_MIN, SI_MAX, SI_AIM,
                            MN_MIN, MN_MAX, MN_AIM,
                            P_MIN, P_MAX, P_AIM,
                            S_MIN, S_MAX, S_AIM,
                            CR_MIN, CR_MAX, CR_AIM,
                            NI_MIN, NI_MAX, NI_AIM,
                            AL_MIN, AL_MAX, AL_AIM)
VALUES ('K', '1', 'ORD20260510005',
        0.0500, 0.1500, 0.1000,
        0.0000, 0.3500, 0.1500,
        0.3000, 0.8000, 0.5500,
        0.0000, 0.0400, 0.0200,
        0.0000, 0.0400, 0.0200,
        0.0000, 0.2000, 0.0500,
        0.0000, 0.2000, 0.0500,
        0.0100, 0.0500, 0.0300);
