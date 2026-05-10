package com.example.slabdesign.store.sd.std.domain.entity;

import java.math.BigDecimal;

/**
 * sd · std · EDGING_SPEC 도메인 Entity.
 * EdgingSpecJpo 와 1:1 미러. edgingGroupCd '*' = catchall.
 */
public class EdgingSpecEntity {

    private String cmpCd;
    private String orgCd;
    private String edgingGroupCd;
    private BigDecimal edgingCapLow;
    private BigDecimal edgingCapHigh;

    public String getCmpCd() { return cmpCd; }
    public void setCmpCd(String v) { this.cmpCd = v; }
    public String getOrgCd() { return orgCd; }
    public void setOrgCd(String v) { this.orgCd = v; }
    public String getEdgingGroupCd() { return edgingGroupCd; }
    public void setEdgingGroupCd(String v) { this.edgingGroupCd = v; }
    public BigDecimal getEdgingCapLow() { return edgingCapLow; }
    public void setEdgingCapLow(BigDecimal v) { this.edgingCapLow = v; }
    public BigDecimal getEdgingCapHigh() { return edgingCapHigh; }
    public void setEdgingCapHigh(BigDecimal v) { this.edgingCapHigh = v; }
}
