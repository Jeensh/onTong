-- Section 3 (Simulation) 마스터 데이터 + 주문 스키마.
-- slab-design JPA Entity 그대로 미러 (camelCase → snake_case).
-- BigDecimal → NUMERIC(18, 6) 통일. VARCHAR 길이는 운영 DB 관행 추정 (cmpCd/orgCd 8, 식별 코드 32).
-- 모든 DDL idempotent (IF NOT EXISTS) — 멱등 적용.

-- ─── 1. cast_spec (CastSpecEntity, step 1 룩업) ─────────────────────
CREATE TABLE IF NOT EXISTS cast_spec (
    cmp_cd          VARCHAR(8)  NOT NULL,
    org_cd          VARCHAR(8)  NOT NULL,
    sm_plant_cd     VARCHAR(32) NOT NULL,
    cast_cd         VARCHAR(32) NOT NULL,
    machine_cd      VARCHAR(32) NOT NULL,
    prod_type_cd    VARCHAR(32) NOT NULL,
    slab_thickness  NUMERIC(18, 6),
    width_low       NUMERIC(18, 6),
    width_high      NUMERIC(18, 6),
    length_low      NUMERIC(18, 6),
    length_high     NUMERIC(18, 6),
    wgt_low         NUMERIC(18, 6),
    wgt_high        NUMERIC(18, 6),
    PRIMARY KEY (cmp_cd, org_cd, sm_plant_cd, cast_cd, machine_cd, prod_type_cd)
);

-- ─── 2. hr_spec (HrSpecEntity, step 2-3 룩업) ─────────────────────────
CREATE TABLE IF NOT EXISTS hr_spec (
    cmp_cd          VARCHAR(8)  NOT NULL,
    org_cd          VARCHAR(8)  NOT NULL,
    hr_plant_cd     VARCHAR(32) NOT NULL,
    prod_type_cd    VARCHAR(32) NOT NULL,
    width_low       NUMERIC(18, 6),
    width_high      NUMERIC(18, 6),
    length_low      NUMERIC(18, 6),
    length_high     NUMERIC(18, 6),
    PRIMARY KEY (cmp_cd, org_cd, hr_plant_cd, prod_type_cd)
);

-- ─── 3. edging_spec (EdgingSpecEntity, '*' wildcard fallback) ─────────
CREATE TABLE IF NOT EXISTS edging_spec (
    cmp_cd          VARCHAR(8)  NOT NULL,
    org_cd          VARCHAR(8)  NOT NULL,
    edging_group_cd VARCHAR(32) NOT NULL,
    edging_cap_low  NUMERIC(18, 6),
    edging_cap_high NUMERIC(18, 6),
    PRIMARY KEY (cmp_cd, org_cd, edging_group_cd)
);

-- ─── 4. edging_group (EdgingGroupEntity, priority ASC) ────────────────
CREATE TABLE IF NOT EXISTS edging_group (
    cmp_cd            VARCHAR(8)  NOT NULL,
    org_cd            VARCHAR(8)  NOT NULL,
    priority          INTEGER     NOT NULL,
    edging_group_cd   VARCHAR(32) NOT NULL,
    grade_cd          VARCHAR(32) NOT NULL,
    prod_type_cd      VARCHAR(32) NOT NULL,
    customer_cd       VARCHAR(32) NOT NULL,
    hr_tgt_width_low  NUMERIC(18, 6),
    hr_tgt_width_high NUMERIC(18, 6),
    PRIMARY KEY (cmp_cd, org_cd, priority, edging_group_cd, grade_cd, prod_type_cd, customer_cd)
);
CREATE INDEX IF NOT EXISTS idx_edging_group_match
    ON edging_group (cmp_cd, org_cd, grade_cd, prod_type_cd, customer_cd, priority);

-- ─── 5. plant_mapping (PlantMappingService 미러, sm_cd 단일키) ────────
CREATE TABLE IF NOT EXISTS plant_mapping (
    sm_cd      VARCHAR(8)  NOT NULL,
    cast_cd    VARCHAR(32) NOT NULL,
    machine_cd VARCHAR(32) NOT NULL,
    PRIMARY KEY (sm_cd)
);

-- ─── 6. hr_min_wgt (HrMinWgtEntity, 2D sheet) ─────────────────────────
CREATE TABLE IF NOT EXISTS hr_min_wgt (
    cmp_cd     VARCHAR(8)     NOT NULL,
    org_cd     VARCHAR(8)     NOT NULL,
    hr_cd      VARCHAR(32)    NOT NULL,
    thickness  NUMERIC(18, 6) NOT NULL,
    width      NUMERIC(18, 6) NOT NULL,
    min_wgt    NUMERIC(18, 6),
    PRIMARY KEY (cmp_cd, org_cd, hr_cd, thickness, width)
);
CREATE INDEX IF NOT EXISTS idx_hr_min_wgt_lookup
    ON hr_min_wgt (cmp_cd, org_cd, hr_cd, thickness ASC, width ASC);

-- ─── 7. hr_max_wgt (HrMaxWgtEntity, 2D sheet) ─────────────────────────
CREATE TABLE IF NOT EXISTS hr_max_wgt (
    cmp_cd     VARCHAR(8)     NOT NULL,
    org_cd     VARCHAR(8)     NOT NULL,
    hr_cd      VARCHAR(32)    NOT NULL,
    thickness  NUMERIC(18, 6) NOT NULL,
    width      NUMERIC(18, 6) NOT NULL,
    max_wgt    NUMERIC(18, 6),
    PRIMARY KEY (cmp_cd, org_cd, hr_cd, thickness, width)
);
CREATE INDEX IF NOT EXISTS idx_hr_max_wgt_lookup
    ON hr_max_wgt (cmp_cd, org_cd, hr_cd, thickness ASC, width ASC);

-- ─── 8. productivity_std (SdProductivityStdEntity, P1.3.c 누적 실수율) ─
CREATE TABLE IF NOT EXISTS productivity_std (
    cmp_cd        VARCHAR(8)  NOT NULL,
    org_cd        VARCHAR(8)  NOT NULL,
    proc_cd       VARCHAR(32) NOT NULL,
    grade_cd      VARCHAR(32) NOT NULL,
    prod_kind_cd  VARCHAR(32) NOT NULL,
    customer_cd   VARCHAR(32) NOT NULL,
    productivity  NUMERIC(18, 6),
    PRIMARY KEY (cmp_cd, org_cd, proc_cd, grade_cd, prod_kind_cd, customer_cd)
);

-- ─── 9. customer_std (CustomerStdEntity, priority + wildcard) ────────
CREATE TABLE IF NOT EXISTS customer_std (
    cmp_cd          VARCHAR(8)  NOT NULL,
    org_cd          VARCHAR(8)  NOT NULL,
    priority        INTEGER     NOT NULL,
    product_name_cd VARCHAR(32) NOT NULL,
    customer_cd     VARCHAR(32) NOT NULL,
    pkg_wgt_low     NUMERIC(18, 6),
    pkg_wgt_high    NUMERIC(18, 6),
    PRIMARY KEY (cmp_cd, org_cd, priority, product_name_cd, customer_cd)
);

-- ─── 10. order_os (SDOrderEntity, 사용자가 직접 등록하는 테스트 주문) ─
-- ORDER_OS / ORDER_OM / ORDER_QD / ORDER_CHEMICAL 4 JPO 통합 단일 테이블.
CREATE TABLE IF NOT EXISTS order_os (
    cmp_cd                VARCHAR(8)  NOT NULL,
    org_cd                VARCHAR(8)  NOT NULL,
    order_no              VARCHAR(32) NOT NULL,
    -- ORDER_OS
    os_progress           VARCHAR(8),
    close_flag            INTEGER,
    stock_code            INTEGER,
    design_pend_qty_high  NUMERIC(18, 6),
    design_pend_qty_low   NUMERIC(18, 6),
    design_pend_qty       NUMERIC(18, 6),
    confirmed_plant_cd    VARCHAR(8),
    possible_plant_cd     VARCHAR(8),
    sm_due                DATE,
    hr_due                DATE,
    hrf_due               DATE,
    cr_due                DATE,
    anl1_due              DATE,
    anl2_due              DATE,
    gal_due               DATE,
    crf_due               DATE,
    -- ORDER_OM
    order_wgt_low         NUMERIC(18, 6),
    order_wgt_high        NUMERIC(18, 6),
    order_width           NUMERIC(18, 6),
    order_length          NUMERIC(18, 6),
    work_due              DATE,
    pkg_wgt_low           NUMERIC(18, 6),
    pkg_wgt_high          NUMERIC(18, 6),
    product_type_cd       VARCHAR(32),
    customer_cd           VARCHAR(32),
    prod_due              DATE,
    delivery_due          DATE,
    grade_cd              VARCHAR(32),
    -- ORDER_QD (HR 목표 폭 5종)
    hr_tgt_width1         NUMERIC(18, 6),
    hr_tgt_width2         NUMERIC(18, 6),
    hr_tgt_width3         NUMERIC(18, 6),
    hr_tgt_width4         NUMERIC(18, 6),
    hr_tgt_width5         NUMERIC(18, 6),
    -- ORDER_CHEMICAL (8 성분 × min/max/aim)
    c_min  NUMERIC(18, 6), c_max  NUMERIC(18, 6), c_aim  NUMERIC(18, 6),
    si_min NUMERIC(18, 6), si_max NUMERIC(18, 6), si_aim NUMERIC(18, 6),
    mn_min NUMERIC(18, 6), mn_max NUMERIC(18, 6), mn_aim NUMERIC(18, 6),
    p_min  NUMERIC(18, 6), p_max  NUMERIC(18, 6), p_aim  NUMERIC(18, 6),
    s_min  NUMERIC(18, 6), s_max  NUMERIC(18, 6), s_aim  NUMERIC(18, 6),
    cr_min NUMERIC(18, 6), cr_max NUMERIC(18, 6), cr_aim NUMERIC(18, 6),
    ni_min NUMERIC(18, 6), ni_max NUMERIC(18, 6), ni_aim NUMERIC(18, 6),
    al_min NUMERIC(18, 6), al_max NUMERIC(18, 6), al_aim NUMERIC(18, 6),
    -- 메타
    created_at            TIMESTAMP DEFAULT NOW(),
    updated_at            TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (cmp_cd, org_cd, order_no)
);
CREATE INDEX IF NOT EXISTS idx_order_os_plant ON order_os (confirmed_plant_cd);
CREATE INDEX IF NOT EXISTS idx_order_os_grade ON order_os (grade_cd);
