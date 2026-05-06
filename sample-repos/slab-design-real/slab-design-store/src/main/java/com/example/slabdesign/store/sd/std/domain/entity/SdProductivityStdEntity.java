package com.example.slabdesign.store.sd.std.domain.entity;

import java.math.BigDecimal;

/**
 * sd · std · SD_PRODUCTIVITY_STD 도메인 Entity. SdProductivityStdJpo 와 1:1 미러.
 */
public class SdProductivityStdEntity {

    private String cmpCd;
    private String orgCd;
    private String procCd;
    private String gradeCd;
    private String prodKindCd;
    private String customerCd;
    private BigDecimal productivity;

    public String getCmpCd() { return cmpCd; }
    public void setCmpCd(String v) { this.cmpCd = v; }
    public String getOrgCd() { return orgCd; }
    public void setOrgCd(String v) { this.orgCd = v; }
    public String getProcCd() { return procCd; }
    public void setProcCd(String v) { this.procCd = v; }
    public String getGradeCd() { return gradeCd; }
    public void setGradeCd(String v) { this.gradeCd = v; }
    public String getProdKindCd() { return prodKindCd; }
    public void setProdKindCd(String v) { this.prodKindCd = v; }
    public String getCustomerCd() { return customerCd; }
    public void setCustomerCd(String v) { this.customerCd = v; }
    public BigDecimal getProductivity() { return productivity; }
    public void setProductivity(BigDecimal v) { this.productivity = v; }
}
