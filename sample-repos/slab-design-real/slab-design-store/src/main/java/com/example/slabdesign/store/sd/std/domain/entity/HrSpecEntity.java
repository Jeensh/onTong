package com.example.slabdesign.store.sd.std.domain.entity;

import java.math.BigDecimal;

/**
 * sd · std · HR_SPEC 도메인 Entity.
 * HrSpecJpo 와 1:1 미러.
 */
public class HrSpecEntity {

    private String cmpCd;
    private String orgCd;
    private String hrPlantCd;
    private String productTypeCd;
    private BigDecimal widthLow;
    private BigDecimal widthHigh;
    private BigDecimal lengthLow;
    private BigDecimal lengthHigh;

    public String getCmpCd() { return cmpCd; }
    public void setCmpCd(String v) { this.cmpCd = v; }
    public String getOrgCd() { return orgCd; }
    public void setOrgCd(String v) { this.orgCd = v; }
    public String getHrPlantCd() { return hrPlantCd; }
    public void setHrPlantCd(String v) { this.hrPlantCd = v; }
    public String getProductTypeCd() { return productTypeCd; }
    public void setProductTypeCd(String v) { this.productTypeCd = v; }
    public BigDecimal getWidthLow() { return widthLow; }
    public void setWidthLow(BigDecimal v) { this.widthLow = v; }
    public BigDecimal getWidthHigh() { return widthHigh; }
    public void setWidthHigh(BigDecimal v) { this.widthHigh = v; }
    public BigDecimal getLengthLow() { return lengthLow; }
    public void setLengthLow(BigDecimal v) { this.lengthLow = v; }
    public BigDecimal getLengthHigh() { return lengthHigh; }
    public void setLengthHigh(BigDecimal v) { this.lengthHigh = v; }
}
