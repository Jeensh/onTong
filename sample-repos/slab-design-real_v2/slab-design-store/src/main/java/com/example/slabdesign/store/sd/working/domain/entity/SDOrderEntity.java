package com.example.slabdesign.store.sd.working.domain.entity;

import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * sd · working · 통합 주문 도메인 Entity.
 *
 * 4개 JPO (ORDER_OS / ORDER_OM / ORDER_QD / ORDER_CHEMICAL) 의 값을 하나의 도메인 객체로 통합.
 * SDOrderLogic 이 리플렉션 + 직접 계산 조합으로 JPO ↔ Entity 변환.
 *
 * 두 종류 필드 분리 (dev notes):
 * 1) DB 값 필드: 4 JPO 의 컬럼들. 동명 필드 충돌 시 OS → OM → QD → CHEMICAL 순서로 first-non-null wins
 * 2) 작업용 필드: 21-step 런타임 메모리 (DB 미저장) — Q-B 결정 후 추가
 *
 * feature 레이어가 영속 데이터에 접근하는 유일한 진입점은 SDOrderLogic.
 */
public class SDOrderEntity {

    // ============================================================
    // 1) DB 값 필드 — 4 JPO 통합
    // ============================================================

    // --- 복합 PK (4 JPO 공유) ---
    private String cmpCd;
    private String orgCd;
    private String orderNo;

    // --- ORDER_OS ---
    private String osProgress;
    private Integer closeFlag;
    private Integer stockCode;          // 재고주문 (1=재고주문, NULL=일반) — Q2/DG001 기준
    private BigDecimal designPendQtyHigh;
    private BigDecimal designPendQtyLow;
    private BigDecimal designPendQty;
    private String confirmedPlantCd;
    private String possiblePlantCd;
    private LocalDate smDue;
    private LocalDate hrDue;
    private LocalDate hrfDue;
    private LocalDate crDue;
    private LocalDate anl1Due;
    private LocalDate anl2Due;
    private LocalDate galDue;
    private LocalDate crfDue;

    // --- ORDER_OM ---
    private BigDecimal orderWgtLow;
    private BigDecimal orderWgtHigh;
    private BigDecimal orderWidth;
    private BigDecimal orderLength;
    // designPendQty 는 OS 와 동명 — 위에서 단일 필드로 통합 (OS 값 우선)
    private LocalDate workDue;
    private BigDecimal pkgWgtLow;
    private BigDecimal pkgWgtHigh;
    private String productCd;
    private String customerCd;
    private LocalDate prodDue;
    private LocalDate deliveryDue;

    // --- ORDER_QD ---
    private String gradeCd;
    private BigDecimal hrTgtWidth1;
    private BigDecimal hrTgtWidth2;
    private BigDecimal hrTgtWidth3;
    private BigDecimal hrTgtWidth4;
    private BigDecimal hrTgtWidth5;

    // --- ORDER_CHEMICAL (8 성분 × min/max/aim = 24) ---
    private BigDecimal cMin, cMax, cAim;
    private BigDecimal siMin, siMax, siAim;
    private BigDecimal mnMin, mnMax, mnAim;
    private BigDecimal pMin, pMax, pAim;
    private BigDecimal sMin, sMax, sAim;
    private BigDecimal crMin, crMax, crAim;
    private BigDecimal niMin, niMax, niAim;
    private BigDecimal alMin, alMax, alAim;

    // ============================================================
    // 2) 작업용 필드 (런타임 메모리만 — DB 미저장)
    //    Service 가 알고리즘 진행 중 set, JPO ↔ Entity 변환에는 미참여.
    // ============================================================

    /** 5 열연공장 목표 폭 중 confirmedPlantCd 의 열연 위치 기준으로 선택된 단일 값 (P2.1 에서 set). */
    private BigDecimal selectedHrTgtWidth;

    /** 비중 (Service 위임 — 일단 7.82 상수, 향후 std 테이블 가능). */
    private BigDecimal specificGravity;

    /** 실수율 (Service 위임 — SD_PRODUCTIVITY_STD 룩업 결과). */
    private BigDecimal productivity;

    // ============================================================
    // Getters / Setters
    // ============================================================

    public String getCmpCd() { return cmpCd; }
    public void setCmpCd(String v) { this.cmpCd = v; }
    public String getOrgCd() { return orgCd; }
    public void setOrgCd(String v) { this.orgCd = v; }
    public String getOrderNo() { return orderNo; }
    public void setOrderNo(String v) { this.orderNo = v; }

    public String getOsProgress() { return osProgress; }
    public void setOsProgress(String v) { this.osProgress = v; }
    public Integer getCloseFlag() { return closeFlag; }
    public void setCloseFlag(Integer v) { this.closeFlag = v; }
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

    public BigDecimal getOrderWgtLow() { return orderWgtLow; }
    public void setOrderWgtLow(BigDecimal v) { this.orderWgtLow = v; }
    public BigDecimal getOrderWgtHigh() { return orderWgtHigh; }
    public void setOrderWgtHigh(BigDecimal v) { this.orderWgtHigh = v; }
    public BigDecimal getOrderWidth() { return orderWidth; }
    public void setOrderWidth(BigDecimal v) { this.orderWidth = v; }
    public BigDecimal getOrderLength() { return orderLength; }
    public void setOrderLength(BigDecimal v) { this.orderLength = v; }
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

    public String getGradeCd() { return gradeCd; }
    public void setGradeCd(String v) { this.gradeCd = v; }
    public BigDecimal getHrTgtWidth1() { return hrTgtWidth1; }
    public void setHrTgtWidth1(BigDecimal v) { this.hrTgtWidth1 = v; }
    public BigDecimal getHrTgtWidth2() { return hrTgtWidth2; }
    public void setHrTgtWidth2(BigDecimal v) { this.hrTgtWidth2 = v; }
    public BigDecimal getHrTgtWidth3() { return hrTgtWidth3; }
    public void setHrTgtWidth3(BigDecimal v) { this.hrTgtWidth3 = v; }
    public BigDecimal getHrTgtWidth4() { return hrTgtWidth4; }
    public void setHrTgtWidth4(BigDecimal v) { this.hrTgtWidth4 = v; }
    public BigDecimal getHrTgtWidth5() { return hrTgtWidth5; }
    public void setHrTgtWidth5(BigDecimal v) { this.hrTgtWidth5 = v; }

    public BigDecimal getCMin()  { return cMin; }   public void setCMin(BigDecimal v)  { this.cMin = v; }
    public BigDecimal getCMax()  { return cMax; }   public void setCMax(BigDecimal v)  { this.cMax = v; }
    public BigDecimal getCAim()  { return cAim; }   public void setCAim(BigDecimal v)  { this.cAim = v; }
    public BigDecimal getSiMin() { return siMin; }  public void setSiMin(BigDecimal v) { this.siMin = v; }
    public BigDecimal getSiMax() { return siMax; }  public void setSiMax(BigDecimal v) { this.siMax = v; }
    public BigDecimal getSiAim() { return siAim; }  public void setSiAim(BigDecimal v) { this.siAim = v; }
    public BigDecimal getMnMin() { return mnMin; }  public void setMnMin(BigDecimal v) { this.mnMin = v; }
    public BigDecimal getMnMax() { return mnMax; }  public void setMnMax(BigDecimal v) { this.mnMax = v; }
    public BigDecimal getMnAim() { return mnAim; }  public void setMnAim(BigDecimal v) { this.mnAim = v; }
    public BigDecimal getPMin()  { return pMin; }   public void setPMin(BigDecimal v)  { this.pMin = v; }
    public BigDecimal getPMax()  { return pMax; }   public void setPMax(BigDecimal v)  { this.pMax = v; }
    public BigDecimal getPAim()  { return pAim; }   public void setPAim(BigDecimal v)  { this.pAim = v; }
    public BigDecimal getSMin()  { return sMin; }   public void setSMin(BigDecimal v)  { this.sMin = v; }
    public BigDecimal getSMax()  { return sMax; }   public void setSMax(BigDecimal v)  { this.sMax = v; }
    public BigDecimal getSAim()  { return sAim; }   public void setSAim(BigDecimal v)  { this.sAim = v; }
    public BigDecimal getCrMin() { return crMin; }  public void setCrMin(BigDecimal v) { this.crMin = v; }
    public BigDecimal getCrMax() { return crMax; }  public void setCrMax(BigDecimal v) { this.crMax = v; }
    public BigDecimal getCrAim() { return crAim; }  public void setCrAim(BigDecimal v) { this.crAim = v; }
    public BigDecimal getNiMin() { return niMin; }  public void setNiMin(BigDecimal v) { this.niMin = v; }
    public BigDecimal getNiMax() { return niMax; }  public void setNiMax(BigDecimal v) { this.niMax = v; }
    public BigDecimal getNiAim() { return niAim; }  public void setNiAim(BigDecimal v) { this.niAim = v; }
    public BigDecimal getAlMin() { return alMin; }  public void setAlMin(BigDecimal v) { this.alMin = v; }
    public BigDecimal getAlMax() { return alMax; }  public void setAlMax(BigDecimal v) { this.alMax = v; }
    public BigDecimal getAlAim() { return alAim; }  public void setAlAim(BigDecimal v) { this.alAim = v; }

    // --- 작업용 필드 getters/setters ---
    public BigDecimal getSelectedHrTgtWidth() { return selectedHrTgtWidth; }
    public void setSelectedHrTgtWidth(BigDecimal v) { this.selectedHrTgtWidth = v; }
    public BigDecimal getSpecificGravity() { return specificGravity; }
    public void setSpecificGravity(BigDecimal v) { this.specificGravity = v; }
    public BigDecimal getProductivity() { return productivity; }
    public void setProductivity(BigDecimal v) { this.productivity = v; }
}
