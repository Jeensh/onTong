package com.example.slabdesign.store.sd.std.jpo;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.IdClass;
import jakarta.persistence.Table;
import java.math.BigDecimal;

/**
 * sd · std · CUSTOMER_STD — 특정 고객사 설계 제한 JPO.
 * Composite PK: (CMP_CD, ORG_CD, PRIORITY).
 *
 * 알고리즘 매핑:
 *   step 5 단중하한 = max(..., PKG_WGT_LOW (특정고객사 단중하한), ...)
 *   step 6 단중상한 = min(..., PKG_WGT_HIGH (특정고객사 단중상한), ...)
 */
@Entity
@Table(name = "CUSTOMER_STD")
@IdClass(CustomerStdPK.class)
public class CustomerStdJpo {

    @Id @Column(name = "CMP_CD", length = 2)
    private String cmpCd;

    @Id @Column(name = "ORG_CD", length = 1)
    private String orgCd;

    @Id @Column(name = "PRIORITY")
    private Integer priority;       // 우선순위 (tiebreaker)

    @Column(name = "PRODUCT_CD", length = 3)
    private String productCd;   // 품명

    @Column(name = "CUSTOMER_CD", length = 10)
    private String customerCd;

    @Column(name = "PKG_WGT_HIGH", precision = 10, scale = 3)
    private BigDecimal pkgWgtHigh;  // 포장단중상한 = 특정고객사 단중제한 상한

    @Column(name = "PKG_WGT_LOW", precision = 10, scale = 3)
    private BigDecimal pkgWgtLow;   // 포장단중하한 = 특정고객사 단중제한 하한

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
