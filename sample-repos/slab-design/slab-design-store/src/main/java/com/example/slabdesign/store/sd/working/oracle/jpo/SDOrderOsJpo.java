package com.example.slabdesign.store.sd.working.oracle.jpo;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.IdClass;
import jakarta.persistence.Table;
import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * sd · working · ORDER_OS — 주문 진행관리 JPO.
 * Composite PK: (CMP_CD, ORG_CD, ORDER_NO) via SDOrderPK.
 * feature 레이어에서 직접 접근 금지 — SDOrderLogic 을 통해 SDOrderEntity 로 변환.
 */
@Entity
@Table(name = "ORDER_OS")
@IdClass(SDOrderPK.class)
public class SDOrderOsJpo {

    @Id
    @Column(name = "CMP_CD", length = 2)
    private String cmpCd;

    @Id
    @Column(name = "ORG_CD", length = 1)
    private String orgCd;

    @Id
    @Column(name = "ORDER_NO", length = 20)
    private String orderNo;

    @Column(name = "OS_PROGRESS", length = 1)
    private String osProgress;

    @Column(name = "CLOSE_FLAG")
    private Integer closeFlag;

    @Column(name = "STOCK_CODE")
    private Integer stockCode;          // 재고주문 (1=재고주문, NULL=일반)

    @Column(name = "DESIGN_PEND_QTY_HIGH", precision = 10, scale = 3)
    private BigDecimal designPendQtyHigh;

    @Column(name = "DESIGN_PEND_QTY_LOW", precision = 10, scale = 3)
    private BigDecimal designPendQtyLow;

    @Column(name = "DESIGN_PEND_QTY", precision = 10, scale = 3)
    private BigDecimal designPendQty;

    @Column(name = "CONFIRMED_PLANT_CD", length = 8)
    private String confirmedPlantCd;

    @Column(name = "POSSIBLE_PLANT_CD", length = 16)
    private String possiblePlantCd;

    @Column(name = "SM_DUE")
    private LocalDate smDue;

    @Column(name = "HR_DUE")
    private LocalDate hrDue;

    @Column(name = "HRF_DUE")
    private LocalDate hrfDue;

    @Column(name = "CR_DUE")
    private LocalDate crDue;

    @Column(name = "ANL1_DUE")
    private LocalDate anl1Due;

    @Column(name = "ANL2_DUE")
    private LocalDate anl2Due;

    @Column(name = "GAL_DUE")
    private LocalDate galDue;

    @Column(name = "CRF_DUE")
    private LocalDate crfDue;

    public String getCmpCd() { return cmpCd; }
    public void setCmpCd(String cmpCd) { this.cmpCd = cmpCd; }
    public String getOrgCd() { return orgCd; }
    public void setOrgCd(String orgCd) { this.orgCd = orgCd; }
    public String getOrderNo() { return orderNo; }
    public void setOrderNo(String orderNo) { this.orderNo = orderNo; }
    public String getOsProgress() { return osProgress; }
    public void setOsProgress(String osProgress) { this.osProgress = osProgress; }
    public Integer getCloseFlag() { return closeFlag; }
    public void setCloseFlag(Integer closeFlag) { this.closeFlag = closeFlag; }
    public Integer getStockCode() { return stockCode; }
    public void setStockCode(Integer v) { this.stockCode = v; }
    public BigDecimal getDesignPendQtyHigh() { return designPendQtyHigh; }
    public void setDesignPendQtyHigh(BigDecimal v) { this.designPendQtyHigh = v; }
    public BigDecimal getDesignPendQtyLow() { return designPendQtyLow; }
    public void setDesignPendQtyLow(BigDecimal v) { this.designPendQtyLow = v; }
    public BigDecimal getDesignPendQty() { return designPendQty; }
    public void setDesignPendQty(BigDecimal v) { this.designPendQty = v; }
    public String getConfirmedPlantCd() { return confirmedPlantCd; }
    public void setConfirmedPlantCd(String v) { this.confirmedPlantCd = v; }
    public String getPossiblePlantCd() { return possiblePlantCd; }
    public void setPossiblePlantCd(String v) { this.possiblePlantCd = v; }
    public LocalDate getSmDue() { return smDue; }
    public void setSmDue(LocalDate v) { this.smDue = v; }
    public LocalDate getHrDue() { return hrDue; }
    public void setHrDue(LocalDate v) { this.hrDue = v; }
    public LocalDate getHrfDue() { return hrfDue; }
    public void setHrfDue(LocalDate v) { this.hrfDue = v; }
    public LocalDate getCrDue() { return crDue; }
    public void setCrDue(LocalDate v) { this.crDue = v; }
    public LocalDate getAnl1Due() { return anl1Due; }
    public void setAnl1Due(LocalDate v) { this.anl1Due = v; }
    public LocalDate getAnl2Due() { return anl2Due; }
    public void setAnl2Due(LocalDate v) { this.anl2Due = v; }
    public LocalDate getGalDue() { return galDue; }
    public void setGalDue(LocalDate v) { this.galDue = v; }
    public LocalDate getCrfDue() { return crfDue; }
    public void setCrfDue(LocalDate v) { this.crfDue = v; }
}
