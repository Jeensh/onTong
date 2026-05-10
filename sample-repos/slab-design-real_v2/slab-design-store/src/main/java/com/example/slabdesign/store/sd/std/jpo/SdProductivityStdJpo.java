package com.example.slabdesign.store.sd.std.jpo;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.IdClass;
import jakarta.persistence.Table;
import java.math.BigDecimal;

/**
 * sd · std · SD_PRODUCTIVITY_STD — 실수율 기준 JPO.
 * Composite PK: (CMP_CD, ORG_CD, PROC_CD, GRADE_CD, PRODUCT_CD, CUSTOMER_CD).
 *
 * PROC_CD 값: SM / HR / HRF / CR / ANL1 / ANL2 / GAL / CRF (8 공정 약어).
 *
 * NOTE: PRODUCT_CD 는 다른 테이블의 PRODUCT_CD / PRODUCT_CD 와 동일 도메인 (품명/품종/품종코드).
 *       레거시 비표준화 그대로 보존.
 */
@Entity
@Table(name = "SD_PRODUCTIVITY_STD")
@IdClass(SdProductivityStdPK.class)
public class SdProductivityStdJpo {

    @Id @Column(name = "CMP_CD", length = 2)
    private String cmpCd;

    @Id @Column(name = "ORG_CD", length = 1)
    private String orgCd;

    @Id @Column(name = "PROC_CD", length = 4)
    private String procCd;          // 공정구분 (SM/HR/HRF/CR/ANL1/ANL2/GAL/CRF)

    @Id @Column(name = "GRADE_CD", length = 10)
    private String gradeCd;

    @Id @Column(name = "PRODUCT_CD", length = 4)
    private String productCd;      // 품종코드 — 동일 의미, 레거시 비표준 컬럼명

    @Id @Column(name = "CUSTOMER_CD", length = 10)
    private String customerCd;

    @Column(name = "PRODUCTIVITY", precision = 7, scale = 4)
    private BigDecimal productivity;    // 실수율 (0.0 ~ 1.0)

    public String getCmpCd() { return cmpCd; }
    public void setCmpCd(String v) { this.cmpCd = v; }
    public String getOrgCd() { return orgCd; }
    public void setOrgCd(String v) { this.orgCd = v; }
    public String getProcCd() { return procCd; }
    public void setProcCd(String v) { this.procCd = v; }
    public String getGradeCd() { return gradeCd; }
    public void setGradeCd(String v) { this.gradeCd = v; }
    public String getProductCd() { return productCd; }
    public void setProductCd(String v) { this.productCd = v; }
    public String getCustomerCd() { return customerCd; }
    public void setCustomerCd(String v) { this.customerCd = v; }
    public BigDecimal getProductivity() { return productivity; }
    public void setProductivity(BigDecimal v) { this.productivity = v; }
}
