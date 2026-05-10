package com.example.slabdesign.store.sd.std.domain.entity;

import java.math.BigDecimal;

/**
 * sd · std · HR_MAX_WGT 도메인 Entity. HrMaxWgtJpo 와 1:1 미러.
 * 2차원 sheet 룩업 결과의 단일 cell 값.
 */
public class HrMaxWgtEntity {

    private String cmpCd;
    private String orgCd;
    private String hrCd;
    private BigDecimal thickness;
    private BigDecimal width;
    private BigDecimal maxWgt;

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
    public BigDecimal getMaxWgt() { return maxWgt; }
    public void setMaxWgt(BigDecimal v) { this.maxWgt = v; }
}
