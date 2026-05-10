package com.example.slabdesign.store.sd.std.jpo;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.IdClass;
import jakarta.persistence.Table;
import java.math.BigDecimal;

/**
 * sd · std · HR_SPEC — 열연설비사양기준 JPO.
 * Composite PK: (CMP_CD, ORG_CD, HR_PLANT_CD, PRODUCT_CD).
 * 룩업 시 ORDER_OS.CONFIRMED_PLANT_CD 의 2자리(열연위치) → HR_PLANT_CD 매칭.
 * 압연 단중 한도는 HR_MIN_WGT / HR_MAX_WGT (Step 3 별도 테이블) 에 있음.
 */
@Entity
@Table(name = "HR_SPEC")
@IdClass(HrSpecPK.class)
public class HrSpecJpo {

    @Id @Column(name = "CMP_CD", length = 2)
    private String cmpCd;

    @Id @Column(name = "ORG_CD", length = 1)
    private String orgCd;

    @Id @Column(name = "HR_PLANT_CD", length = 1)
    private String hrPlantCd;       // 열연공장코드 (확통2자리)

    @Id @Column(name = "PRODUCT_CD", length = 4)
    private String productCd;

    @Column(name = "WIDTH_LOW", precision = 10, scale = 2)
    private BigDecimal widthLow;    // step 2 폭하한 계산

    @Column(name = "WIDTH_HIGH", precision = 10, scale = 2)
    private BigDecimal widthHigh;   // step 2 폭상한 계산

    @Column(name = "LENGTH_LOW", precision = 10, scale = 2)
    private BigDecimal lengthLow;   // step 3 길이하한 계산

    @Column(name = "LENGTH_HIGH", precision = 10, scale = 2)
    private BigDecimal lengthHigh;  // step 3 길이상한 계산

    public String getCmpCd() { return cmpCd; }
    public void setCmpCd(String v) { this.cmpCd = v; }
    public String getOrgCd() { return orgCd; }
    public void setOrgCd(String v) { this.orgCd = v; }
    public String getHrPlantCd() { return hrPlantCd; }
    public void setHrPlantCd(String v) { this.hrPlantCd = v; }
    public String getProductCd() { return productCd; }
    public void setProductCd(String v) { this.productCd = v; }
    public BigDecimal getWidthLow() { return widthLow; }
    public void setWidthLow(BigDecimal v) { this.widthLow = v; }
    public BigDecimal getWidthHigh() { return widthHigh; }
    public void setWidthHigh(BigDecimal v) { this.widthHigh = v; }
    public BigDecimal getLengthLow() { return lengthLow; }
    public void setLengthLow(BigDecimal v) { this.lengthLow = v; }
    public BigDecimal getLengthHigh() { return lengthHigh; }
    public void setLengthHigh(BigDecimal v) { this.lengthHigh = v; }
}
