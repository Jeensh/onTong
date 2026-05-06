package com.example.slabdesign.store.sd.std.domain.entity;

import java.math.BigDecimal;

/**
 * sd · std · EDGING_GROUP 도메인 Entity.
 * EdgingGroupJpo 와 1:1 미러.
 */
public class EdgingGroupEntity {

    private String cmpCd;
    private String orgCd;
    private Integer priority;
    private String edgingGroupCd;
    private String gradeCd;
    private String productTypeCd;
    private String customerCd;
    private BigDecimal hrTgtWidthHigh;
    private BigDecimal hrTgtWidthLow;

    public String getCmpCd() { return cmpCd; }
    public void setCmpCd(String v) { this.cmpCd = v; }
    public String getOrgCd() { return orgCd; }
    public void setOrgCd(String v) { this.orgCd = v; }
    public Integer getPriority() { return priority; }
    public void setPriority(Integer v) { this.priority = v; }
    public String getEdgingGroupCd() { return edgingGroupCd; }
    public void setEdgingGroupCd(String v) { this.edgingGroupCd = v; }
    public String getGradeCd() { return gradeCd; }
    public void setGradeCd(String v) { this.gradeCd = v; }
    public String getProductTypeCd() { return productTypeCd; }
    public void setProductTypeCd(String v) { this.productTypeCd = v; }
    public String getCustomerCd() { return customerCd; }
    public void setCustomerCd(String v) { this.customerCd = v; }
    public BigDecimal getHrTgtWidthHigh() { return hrTgtWidthHigh; }
    public void setHrTgtWidthHigh(BigDecimal v) { this.hrTgtWidthHigh = v; }
    public BigDecimal getHrTgtWidthLow() { return hrTgtWidthLow; }
    public void setHrTgtWidthLow(BigDecimal v) { this.hrTgtWidthLow = v; }
}
