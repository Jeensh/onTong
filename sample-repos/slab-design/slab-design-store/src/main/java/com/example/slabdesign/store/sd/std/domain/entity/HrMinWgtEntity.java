package com.example.slabdesign.store.sd.std.domain.entity;

import java.math.BigDecimal;

/**
 * sd · std · HR_MIN_WGT 도메인 Entity. HrMinWgtJpo 와 1:1 미러.
 */
public class HrMinWgtEntity {

    private String cmpCd;
    private String orgCd;
    private String hrCd;
    private BigDecimal thickness;
    private BigDecimal width;
    private BigDecimal minWgt;

    public String getCmpCd() { return cmpCd; }
    public void setCmpCd(String v) { this.cmpCd = v; }
    public String getOrgCd() { return orgCd; }
    public void setOrgCd(String v) { this.orgCd = v; }
    public String getHrCd() { return hrCd; }
    public void setHrCd(String v) { this.hrCd = v; }
    public BigDecimal getThickness() { return thickness; }
    public void setThickness(BigDecimal v) { this.thickness = v; }
    public BigDecimal getWidth() { return width; }
    public void setWidth(BigDecimal v) { this.width = v; }
    public BigDecimal getMinWgt() { return minWgt; }
    public void setMinWgt(BigDecimal v) { this.minWgt = v; }
}
