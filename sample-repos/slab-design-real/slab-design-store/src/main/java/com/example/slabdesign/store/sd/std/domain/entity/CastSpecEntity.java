package com.example.slabdesign.store.sd.std.domain.entity;

import java.math.BigDecimal;

/**
 * sd · std · CAST_SPEC 도메인 Entity.
 * CastSpecJpo 와 1:1 미러. feature 레이어 진입점은 CastSpecLogic.
 */
public class CastSpecEntity {

    private String cmpCd;
    private String orgCd;
    private String smCd;
    private String castCd;
    private String machineCd;
    private String productTypeCd;
    private BigDecimal slabThickness;
    private BigDecimal widthLow;
    private BigDecimal widthHigh;
    private BigDecimal lengthLow;
    private BigDecimal lengthHigh;
    private BigDecimal wgtLow;
    private BigDecimal wgtHigh;

    public String getCmpCd() { return cmpCd; }
    public void setCmpCd(String v) { this.cmpCd = v; }
    public String getOrgCd() { return orgCd; }
    public void setOrgCd(String v) { this.orgCd = v; }
    public String getSmCd() { return smCd; }
    public void setSmCd(String v) { this.smCd = v; }
    public String getCastCd() { return castCd; }
    public void setCastCd(String v) { this.castCd = v; }
    public String getMachineCd() { return machineCd; }
    public void setMachineCd(String v) { this.machineCd = v; }
    public String getProductTypeCd() { return productTypeCd; }
    public void setProductTypeCd(String v) { this.productTypeCd = v; }
    public BigDecimal getSlabThickness() { return slabThickness; }
    public void setSlabThickness(BigDecimal v) { this.slabThickness = v; }
    public BigDecimal getWidthLow() { return widthLow; }
    public void setWidthLow(BigDecimal v) { this.widthLow = v; }
    public BigDecimal getWidthHigh() { return widthHigh; }
    public void setWidthHigh(BigDecimal v) { this.widthHigh = v; }
    public BigDecimal getLengthLow() { return lengthLow; }
    public void setLengthLow(BigDecimal v) { this.lengthLow = v; }
    public BigDecimal getLengthHigh() { return lengthHigh; }
    public void setLengthHigh(BigDecimal v) { this.lengthHigh = v; }
    public BigDecimal getWgtLow() { return wgtLow; }
    public void setWgtLow(BigDecimal v) { this.wgtLow = v; }
    public BigDecimal getWgtHigh() { return wgtHigh; }
    public void setWgtHigh(BigDecimal v) { this.wgtHigh = v; }
}
