package com.example.slabdesign.store.sd.working.jpo;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.IdClass;
import jakarta.persistence.Table;
import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * sd · working · ORDER_OM — 주문 처리 JPO.
 * Composite PK: (CMP_CD, ORG_CD, ORDER_NO) via SDOrderPK.
 * 품종(PRODUCT_CD) 으로 Coil 식별: 'FS' = 외판, 그 외 = Coil.
 */
@Entity
@Table(name = "ORDER_OM")
@IdClass(SDOrderPK.class)
public class SDOrderOmJpo {

    @Id
    @Column(name = "CMP_CD", length = 2)
    private String cmpCd;

    @Id
    @Column(name = "ORG_CD", length = 1)
    private String orgCd;

    @Id
    @Column(name = "ORDER_NO", length = 20)
    private String orderNo;

    @Column(name = "ORDER_WGT_LOW", precision = 10, scale = 3)
    private BigDecimal orderWgtLow;

    @Column(name = "ORDER_WGT_HIGH", precision = 10, scale = 3)
    private BigDecimal orderWgtHigh;

    @Column(name = "ORDER_WIDTH", precision = 10, scale = 2)
    private BigDecimal orderWidth;

    @Column(name = "ORDER_LENGTH", precision = 10, scale = 2)
    private BigDecimal orderLength;

    @Column(name = "DESIGN_PEND_QTY", precision = 10, scale = 3)
    private BigDecimal designPendQty;

    @Column(name = "WORK_DUE")
    private LocalDate workDue;

    @Column(name = "PKG_WGT_LOW", precision = 10, scale = 3)
    private BigDecimal pkgWgtLow;

    @Column(name = "PKG_WGT_HIGH", precision = 10, scale = 3)
    private BigDecimal pkgWgtHigh;

    @Column(name = "PRODUCT_CD", length = 4)
    private String productCd;

    @Column(name = "CUSTOMER_CD", length = 10)
    private String customerCd;

    @Column(name = "PROD_DUE")
    private LocalDate prodDue;

    @Column(name = "DELIVERY_DUE")
    private LocalDate deliveryDue;

    public String getCmpCd() { return cmpCd; }
    public void setCmpCd(String cmpCd) { this.cmpCd = cmpCd; }
    public String getOrgCd() { return orgCd; }
    public void setOrgCd(String orgCd) { this.orgCd = orgCd; }
    public String getOrderNo() { return orderNo; }
    public void setOrderNo(String orderNo) { this.orderNo = orderNo; }
    public BigDecimal getOrderWgtLow() { return orderWgtLow; }
    public void setOrderWgtLow(BigDecimal v) { this.orderWgtLow = v; }
    public BigDecimal getOrderWgtHigh() { return orderWgtHigh; }
    public void setOrderWgtHigh(BigDecimal v) { this.orderWgtHigh = v; }
    public BigDecimal getOrderWidth() { return orderWidth; }
    public void setOrderWidth(BigDecimal v) { this.orderWidth = v; }
    public BigDecimal getOrderLength() { return orderLength; }
    public void setOrderLength(BigDecimal v) { this.orderLength = v; }
    public BigDecimal getDesignPendQty() { return designPendQty; }
    public void setDesignPendQty(BigDecimal v) { this.designPendQty = v; }
    public LocalDate getWorkDue() { return workDue; }
    public void setWorkDue(LocalDate v) { this.workDue = v; }
    public BigDecimal getPkgWgtLow() { return pkgWgtLow; }
    public void setPkgWgtLow(BigDecimal v) { this.pkgWgtLow = v; }
    public BigDecimal getPkgWgtHigh() { return pkgWgtHigh; }
    public void setPkgWgtHigh(BigDecimal v) { this.pkgWgtHigh = v; }
    public String getProductCd() { return productCd; }
    public void setProductCd(String v) { this.productCd = v; }
    public String getCustomerCd() { return customerCd; }
    public void setCustomerCd(String v) { this.customerCd = v; }
    public LocalDate getProdDue() { return prodDue; }
    public void setProdDue(LocalDate v) { this.prodDue = v; }
    public LocalDate getDeliveryDue() { return deliveryDue; }
    public void setDeliveryDue(LocalDate v) { this.deliveryDue = v; }
}
