package com.example.slabdesign.store.sd.std.domain.entity;

import java.math.BigDecimal;

/**
 * sd · std · CUSTOMER_STD 도메인 Entity. CustomerStdJpo 와 1:1 미러.
 */
public class CustomerStdEntity {

    private String cmpCd;
    private String orgCd;
    private Integer priority;
    private String productCd;   // 품명 — 다른 테이블 PRODUCT_CD/PRODUCT_CD 와 동일 도메인
    private String customerCd;
    private BigDecimal pkgWgtHigh;
    private BigDecimal pkgWgtLow;

    public String getCmpCd() { return cmpCd; }
    public void setCmpCd(String v) { this.cmpCd = v; }
    public String getOrgCd() { return orgCd; }
    public void setOrgCd(String v) { this.orgCd = v; }
    public Integer getPriority() { return priority; }
    public void setPriority(Integer v) { this.priority = v; }
    public String getProductCd() { return productCd; }
    public void setProductCd(String v) { this.productCd = v; }
    public String getCustomerCd() { return customerCd; }
    public void setCustomerCd(String v) { this.customerCd = v; }
    public BigDecimal getPkgWgtHigh() { return pkgWgtHigh; }
    public void setPkgWgtHigh(BigDecimal v) { this.pkgWgtHigh = v; }
    public BigDecimal getPkgWgtLow() { return pkgWgtLow; }
    public void setPkgWgtLow(BigDecimal v) { this.pkgWgtLow = v; }
}
