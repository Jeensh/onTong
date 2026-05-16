-- ============================================================
-- 02_orders.sql -- 5 golden scenario orders (ORDER_OS / OM / QD / CHEMICAL)
-- Loaded by spring.sql.init after 01_master.sql.
-- All 5 use cmpCd='K', orgCd='1'.
-- osProgress='C' (designable), closeFlag NULL (not closed) -- so findDesignable() picks them up.
-- stockCode=0 (not stock; 1 would trigger DG001).
-- All weight units: **kg** (consistent with SdFirstWeightAction's mm³×g/cm³×1e-6).
--   orderWgt = target weight per coil ~10,000-25,000 kg
--   designPendQty = total order weight in kg
--   pkgWgt = packaging cap weight per coil in kg
-- ============================================================

-- ============================================================
-- ORDER_OS rows -- 진도/포장 위치/단중 한도
-- ============================================================
INSERT INTO ORDER_OS (CMP_CD, ORG_CD, ORDER_NO,
                      OS_PROGRESS, CLOSE_FLAG, STOCK_CODE,
                      DESIGN_PEND_QTY_HIGH, DESIGN_PEND_QTY_LOW, DESIGN_PEND_QTY,
                      CONFIRMED_PLANT_CD, POSSIBLE_PLANT_CD,
                      SM_DUE, HR_DUE, HRF_DUE, CR_DUE, ANL1_DUE, ANL2_DUE, GAL_DUE, CRF_DUE)
-- S1 — golden path. SM (pos 0='K'), HR (pos 1='1'), CR (pos 3='K') active; rest inactive.
-- confirmedPlantCd layout = 8 chars: pos 0..7 = SM HR HRF CR ANL1 ANL2 GAL CRF.
-- Step 2 requires HR active (' ' at pos 1 → DG102), so HR is always '1'.
-- DESIGN_PEND_QTY in kg: 10,000 ~ 12,000 (≈ 1 slab worth).
VALUES ('K', '1', 'ORD20260510001',
        'C', NULL, 0,
        12000.000, 8000.000, 10000.000,
        'K1 K    ', 'K1 K    ',
        DATE '2026-12-31', DATE '2026-12-31', NULL, DATE '2026-12-31', NULL, NULL, NULL, NULL);

INSERT INTO ORDER_OS (CMP_CD, ORG_CD, ORDER_NO,
                      OS_PROGRESS, CLOSE_FLAG, STOCK_CODE,
                      DESIGN_PEND_QTY_HIGH, DESIGN_PEND_QTY_LOW, DESIGN_PEND_QTY,
                      CONFIRMED_PLANT_CD, POSSIBLE_PLANT_CD,
                      SM_DUE, HR_DUE, HRF_DUE, CR_DUE, ANL1_DUE, ANL2_DUE, GAL_DUE, CRF_DUE)
-- S2 — multi-slab scenario. designPendQty ~50-60 tonnes → ~4 slabs at ~13t each.
-- Active: SM=K, HR=1.
VALUES ('K', '1', 'ORD20260510002',
        'C', NULL, 0,
        60000.000, 50000.000, 55000.000,
        'K1      ', 'K1      ',
        DATE '2026-12-31', DATE '2026-12-31', NULL, NULL, NULL, NULL, NULL, NULL);

INSERT INTO ORDER_OS (CMP_CD, ORG_CD, ORDER_NO,
                      OS_PROGRESS, CLOSE_FLAG, STOCK_CODE,
                      DESIGN_PEND_QTY_HIGH, DESIGN_PEND_QTY_LOW, DESIGN_PEND_QTY,
                      CONFIRMED_PLANT_CD, POSSIBLE_PLANT_CD,
                      SM_DUE, HR_DUE, HRF_DUE, CR_DUE, ANL1_DUE, ANL2_DUE, GAL_DUE, CRF_DUE)
-- S3 — A-a inner-loop fallback. SM/HR/HRF/CR active.
-- Setup: step 9 yields slabCount=1, step 10 NO (totalProduced < yieldAdjustedLow),
-- step 13 PASS (newCount=2). So output = 2 slabs via A-a recalc path.
-- designPendQtyLow=30,000 / High=45,000 — wide enough that pendHigh/(prod*newCount=2)
-- lands inside [splitWgtLow, splitWgtHigh].
VALUES ('K', '1', 'ORD20260510003',
        'C', NULL, 0,
        45000.000, 30000.000, 35000.000,
        'K1KK    ', 'K1KK    ',
        DATE '2026-12-31', DATE '2026-12-31', DATE '2026-12-31', DATE '2026-12-31', NULL, NULL, NULL, NULL);

INSERT INTO ORDER_OS (CMP_CD, ORG_CD, ORDER_NO,
                      OS_PROGRESS, CLOSE_FLAG, STOCK_CODE,
                      DESIGN_PEND_QTY_HIGH, DESIGN_PEND_QTY_LOW, DESIGN_PEND_QTY,
                      CONFIRMED_PLANT_CD, POSSIBLE_PLANT_CD,
                      SM_DUE, HR_DUE, HRF_DUE, CR_DUE, ANL1_DUE, ANL2_DUE, GAL_DUE, CRF_DUE)
-- S4 — DG004 scenario. designPendQtyHigh=12,000 < pkgWgtLow=20,000 → validator fires DG004.
-- pkgWgtLow/High are set in ORDER_OM (below).
VALUES ('K', '1', 'ORD20260510004',
        'C', NULL, 0,
        12000.000, 8000.000, 10000.000,
        'K1      ', 'K1      ',
        DATE '2026-12-31', DATE '2026-12-31', NULL, NULL, NULL, NULL, NULL, NULL);

INSERT INTO ORDER_OS (CMP_CD, ORG_CD, ORDER_NO,
                      OS_PROGRESS, CLOSE_FLAG, STOCK_CODE,
                      DESIGN_PEND_QTY_HIGH, DESIGN_PEND_QTY_LOW, DESIGN_PEND_QTY,
                      CONFIRMED_PLANT_CD, POSSIBLE_PLANT_CD,
                      SM_DUE, HR_DUE, HRF_DUE, CR_DUE, ANL1_DUE, ANL2_DUE, GAL_DUE, CRF_DUE)
-- S5 — minimal active processes. Step 2 needs HR active; CRF also active.
-- confirmedPlantCd[1]='1' makes HR active; CRF position 7 = 'K'. designPendQty ~8 tonnes.
VALUES ('K', '1', 'ORD20260510005',
        'C', NULL, 0,
        10000.000, 6000.000, 8000.000,
        'K1     K', 'K1     K',
        DATE '2026-12-31', DATE '2026-12-31', NULL, NULL, NULL, NULL, NULL, DATE '2026-12-31');

-- ============================================================
-- ORDER_OM rows -- 폭/길이/단중/품종/고객사
-- ============================================================
INSERT INTO ORDER_OM (CMP_CD, ORG_CD, ORDER_NO,
                      ORDER_WGT_LOW, ORDER_WGT_HIGH, ORDER_WIDTH, ORDER_LENGTH,
                      DESIGN_PEND_QTY, WORK_DUE,
                      PKG_WGT_LOW, PKG_WGT_HIGH,
                      PRODUCT_CD, CUSTOMER_CD, PROD_DUE, DELIVERY_DUE)
-- S1 — single coil from one slab; per-coil weight ~10-12 tonnes.
VALUES ('K', '1', 'ORD20260510001',
        10000.000, 12000.000, 1200.00, 8500.00,
        10000.000, DATE '2026-12-31',
        8000.000, 18000.000,
        'COIL', 'CUST-001', DATE '2026-12-15', DATE '2026-12-31');

INSERT INTO ORDER_OM (CMP_CD, ORG_CD, ORDER_NO,
                      ORDER_WGT_LOW, ORDER_WGT_HIGH, ORDER_WIDTH, ORDER_LENGTH,
                      DESIGN_PEND_QTY, WORK_DUE,
                      PKG_WGT_LOW, PKG_WGT_HIGH,
                      PRODUCT_CD, CUSTOMER_CD, PROD_DUE, DELIVERY_DUE)
-- S2 — multi-slab; per-coil ~10-13 tonnes target. Total ~50-60t → ~4 slabs.
-- ORDER_LENGTH 32000 (long coil) gives big firstWgtHigh — algorithm caps at HR_MAX/secondWgt.
VALUES ('K', '1', 'ORD20260510002',
        10000.000, 13000.000, 1100.00, 32000.00,
        55000.000, DATE '2026-12-31',
        8000.000, 25000.000,
        'COIL', 'CUST-001', DATE '2026-12-15', DATE '2026-12-31');

INSERT INTO ORDER_OM (CMP_CD, ORG_CD, ORDER_NO,
                      ORDER_WGT_LOW, ORDER_WGT_HIGH, ORDER_WIDTH, ORDER_LENGTH,
                      DESIGN_PEND_QTY, WORK_DUE,
                      PKG_WGT_LOW, PKG_WGT_HIGH,
                      PRODUCT_CD, CUSTOMER_CD, PROD_DUE, DELIVERY_DUE)
-- S3 — A-a fallback. orderWgt 20-25t per coil — relatively narrow band so initial
-- max-split estimate fails step 10's pendQty range, A-a loop falls back to lower split.
VALUES ('K', '1', 'ORD20260510003',
        20000.000, 25000.000, 1300.00, 16000.00,
        22000.000, DATE '2026-12-31',
        18000.000, 26000.000,
        'COIL', 'CUST-001', DATE '2026-12-15', DATE '2026-12-31');

INSERT INTO ORDER_OM (CMP_CD, ORG_CD, ORDER_NO,
                      ORDER_WGT_LOW, ORDER_WGT_HIGH, ORDER_WIDTH, ORDER_LENGTH,
                      DESIGN_PEND_QTY, WORK_DUE,
                      PKG_WGT_LOW, PKG_WGT_HIGH,
                      PRODUCT_CD, CUSTOMER_CD, PROD_DUE, DELIVERY_DUE)
-- S4 — pkgWgtLow=20,000 > designPendQtyHigh=12,000 → validator's checkDesignPendQty fires DG004.
VALUES ('K', '1', 'ORD20260510004',
        8000.000, 12000.000, 1200.00, 8000.00,
        10000.000, DATE '2026-12-31',
        20000.000, 22000.000,
        'COIL', 'CUST-FAIL', DATE '2026-12-15', DATE '2026-12-31');

INSERT INTO ORDER_OM (CMP_CD, ORG_CD, ORDER_NO,
                      ORDER_WGT_LOW, ORDER_WGT_HIGH, ORDER_WIDTH, ORDER_LENGTH,
                      DESIGN_PEND_QTY, WORK_DUE,
                      PKG_WGT_LOW, PKG_WGT_HIGH,
                      PRODUCT_CD, CUSTOMER_CD, PROD_DUE, DELIVERY_DUE)
-- S5 — minimal active-process scenario; per-coil ~6-10 tonnes; small order.
VALUES ('K', '1', 'ORD20260510005',
        6000.000, 10000.000, 1100.00, 7000.00,
        8000.000, DATE '2026-12-31',
        5000.000, 12000.000,
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
