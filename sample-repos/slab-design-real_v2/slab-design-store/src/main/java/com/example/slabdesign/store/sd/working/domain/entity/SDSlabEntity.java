package com.example.slabdesign.store.sd.working.domain.entity;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * sd · working · 통합 슬랩 도메인 Entity.
 *
 * dev notes 패턴 (SDOrder 와 동일):
 *   1) DB값 필드: SLAB_RESULT 컬럼 매핑 (영속화)
 *      - 두께: 단일 (조정 없음)
 *      - 폭/길이/단중: 원본(SLAB_*) + 조정(SLAB_*_1) 양쪽
 *      - confirmedPlantCd / possiblePlantCd: 설계 시점 snapshot
 *   2) 작업용 필드: 21-step 알고리즘 런타임 메모리 (DB 미저장)
 *      - 1차/2차 범위, 분할수 카운터, 임시 단중·매수, 최종 폭·길이 범위, 목표값, 설계 상태
 *
 * SDSlabLogic 이 SLAB_RESULT JPO ↔ SDSlabEntity 변환 (DB값 portion 만).
 * 작업용 필드는 알고리즘 진행 중 SDDesigner/SDDriver 가 set/get.
 *
 * FAIL 시 SLAB_RESULT 미저장 → DB값 필드는 비어있고 designStatus + errorCode 만 채워짐.
 * 이력은 SLAB_DESIGN_HIST 별도 적재.
 */
public class SDSlabEntity {

    // ============================================================
    // 1) DB값 필드 (SLAB_RESULT 매핑)
    // ============================================================

    private String cmpCd;
    private String orgCd;
    private String slabNo;

    private String orderNo;
    private String confirmedPlantCd;
    private String possiblePlantCd;

    // 두께 (조정 없음)
    private BigDecimal slabThickness;

    // 원본 (최초 설계)
    private BigDecimal slabWidth;
    private BigDecimal slabWidthHigh;
    private BigDecimal slabWidthLow;
    private BigDecimal slabLength;
    private BigDecimal slabLengthHigh;
    private BigDecimal slabLengthLow;
    private BigDecimal slabWgt;
    private BigDecimal slabWgtHigh;
    private BigDecimal slabWgtLow;

    // 조정 (사이즈 변경 후 — _1 suffix)
    private BigDecimal slabWidth1;
    private BigDecimal slabWidthHigh1;
    private BigDecimal slabWidthLow1;
    private BigDecimal slabLength1;
    private BigDecimal slabLengthHigh1;
    private BigDecimal slabLengthLow1;
    private BigDecimal slabWgt1;
    private BigDecimal slabWgtHigh1;
    private BigDecimal slabWgtLow1;

    private Integer splitCount;
    private LocalDateTime createdAt;

    // ============================================================
    // 2) 작업용 필드 (런타임 메모리 — DB 미저장)
    //    21-step 중간값 + 설계 상태
    // ============================================================

    // step 2-4: 1차 범위
    private BigDecimal firstWidthLow;
    private BigDecimal firstWidthHigh;
    private BigDecimal firstLengthLow;
    private BigDecimal firstLengthHigh;
    private BigDecimal firstWgtLow;
    private BigDecimal firstWgtHigh;

    // step 5-6: 2차 단중 범위
    private BigDecimal secondWgtLow;
    private BigDecimal secondWgtHigh;

    // step 7: 최대분할수
    private Integer maxSplitCountUpper;
    /** A-a 루프 카운터 — 매 사이클 1씩 감소. */
    private Integer currentSplitCount;

    // step 8-10: 분할수 고려 결과
    private Integer optimalSplitCount;
    private BigDecimal splitWgtLow;
    private BigDecimal splitWgtHigh;
    /** step 9 결과 — 매수 (분할수 고려). */
    private Integer slabCountInProgress;
    /** step 10/13 결과 — slab 단중 (작업 중). */
    private BigDecimal slabWgtInProgress;

    // step 16-17: 최종 폭·길이 범위
    private BigDecimal finalWidthLow;
    private BigDecimal finalWidthHigh;
    private BigDecimal finalLengthLow;
    private BigDecimal finalLengthHigh;

    // step 18-19: 목표값
    private BigDecimal targetSlabWidth;
    private BigDecimal targetSlabLength;

    // 설계 상태
    /** SUCCESS / FAIL / IN_PROGRESS. */
    private String designStatus;
    /** FAIL 시 에러 코드. */
    private String errorCode;

    // ============================================================
    // Getters / Setters
    // ============================================================

    public String getCmpCd() { return cmpCd; }
    public void setCmpCd(String v) { this.cmpCd = v; }
    public String getOrgCd() { return orgCd; }
    public void setOrgCd(String v) { this.orgCd = v; }
    public String getSlabNo() { return slabNo; }
    public void setSlabNo(String v) { this.slabNo = v; }
    public String getOrderNo() { return orderNo; }
    public void setOrderNo(String v) { this.orderNo = v; }
    public String getConfirmedPlantCd() { return confirmedPlantCd; }
    public void setConfirmedPlantCd(String v) { this.confirmedPlantCd = v; }
    public String getPossiblePlantCd() { return possiblePlantCd; }
    public void setPossiblePlantCd(String v) { this.possiblePlantCd = v; }
    public BigDecimal getSlabThickness() { return slabThickness; }
    public void setSlabThickness(BigDecimal v) { this.slabThickness = v; }
    public BigDecimal getSlabWidth() { return slabWidth; }
    public void setSlabWidth(BigDecimal v) { this.slabWidth = v; }
    public BigDecimal getSlabWidthHigh() { return slabWidthHigh; }
    public void setSlabWidthHigh(BigDecimal v) { this.slabWidthHigh = v; }
    public BigDecimal getSlabWidthLow() { return slabWidthLow; }
    public void setSlabWidthLow(BigDecimal v) { this.slabWidthLow = v; }
    public BigDecimal getSlabLength() { return slabLength; }
    public void setSlabLength(BigDecimal v) { this.slabLength = v; }
    public BigDecimal getSlabLengthHigh() { return slabLengthHigh; }
    public void setSlabLengthHigh(BigDecimal v) { this.slabLengthHigh = v; }
    public BigDecimal getSlabLengthLow() { return slabLengthLow; }
    public void setSlabLengthLow(BigDecimal v) { this.slabLengthLow = v; }
    public BigDecimal getSlabWgt() { return slabWgt; }
    public void setSlabWgt(BigDecimal v) { this.slabWgt = v; }
    public BigDecimal getSlabWgtHigh() { return slabWgtHigh; }
    public void setSlabWgtHigh(BigDecimal v) { this.slabWgtHigh = v; }
    public BigDecimal getSlabWgtLow() { return slabWgtLow; }
    public void setSlabWgtLow(BigDecimal v) { this.slabWgtLow = v; }
    public BigDecimal getSlabWidth1() { return slabWidth1; }
    public void setSlabWidth1(BigDecimal v) { this.slabWidth1 = v; }
    public BigDecimal getSlabWidthHigh1() { return slabWidthHigh1; }
    public void setSlabWidthHigh1(BigDecimal v) { this.slabWidthHigh1 = v; }
    public BigDecimal getSlabWidthLow1() { return slabWidthLow1; }
    public void setSlabWidthLow1(BigDecimal v) { this.slabWidthLow1 = v; }
    public BigDecimal getSlabLength1() { return slabLength1; }
    public void setSlabLength1(BigDecimal v) { this.slabLength1 = v; }
    public BigDecimal getSlabLengthHigh1() { return slabLengthHigh1; }
    public void setSlabLengthHigh1(BigDecimal v) { this.slabLengthHigh1 = v; }
    public BigDecimal getSlabLengthLow1() { return slabLengthLow1; }
    public void setSlabLengthLow1(BigDecimal v) { this.slabLengthLow1 = v; }
    public BigDecimal getSlabWgt1() { return slabWgt1; }
    public void setSlabWgt1(BigDecimal v) { this.slabWgt1 = v; }
    public BigDecimal getSlabWgtHigh1() { return slabWgtHigh1; }
    public void setSlabWgtHigh1(BigDecimal v) { this.slabWgtHigh1 = v; }
    public BigDecimal getSlabWgtLow1() { return slabWgtLow1; }
    public void setSlabWgtLow1(BigDecimal v) { this.slabWgtLow1 = v; }
    public Integer getSplitCount() { return splitCount; }
    public void setSplitCount(Integer v) { this.splitCount = v; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime v) { this.createdAt = v; }

    // 작업용 필드
    public BigDecimal getFirstWidthLow() { return firstWidthLow; }
    public void setFirstWidthLow(BigDecimal v) { this.firstWidthLow = v; }
    public BigDecimal getFirstWidthHigh() { return firstWidthHigh; }
    public void setFirstWidthHigh(BigDecimal v) { this.firstWidthHigh = v; }
    public BigDecimal getFirstLengthLow() { return firstLengthLow; }
    public void setFirstLengthLow(BigDecimal v) { this.firstLengthLow = v; }
    public BigDecimal getFirstLengthHigh() { return firstLengthHigh; }
    public void setFirstLengthHigh(BigDecimal v) { this.firstLengthHigh = v; }
    public BigDecimal getFirstWgtLow() { return firstWgtLow; }
    public void setFirstWgtLow(BigDecimal v) { this.firstWgtLow = v; }
    public BigDecimal getFirstWgtHigh() { return firstWgtHigh; }
    public void setFirstWgtHigh(BigDecimal v) { this.firstWgtHigh = v; }
    public BigDecimal getSecondWgtLow() { return secondWgtLow; }
    public void setSecondWgtLow(BigDecimal v) { this.secondWgtLow = v; }
    public BigDecimal getSecondWgtHigh() { return secondWgtHigh; }
    public void setSecondWgtHigh(BigDecimal v) { this.secondWgtHigh = v; }
    public Integer getMaxSplitCountUpper() { return maxSplitCountUpper; }
    public void setMaxSplitCountUpper(Integer v) { this.maxSplitCountUpper = v; }
    public Integer getCurrentSplitCount() { return currentSplitCount; }
    public void setCurrentSplitCount(Integer v) { this.currentSplitCount = v; }
    public Integer getOptimalSplitCount() { return optimalSplitCount; }
    public void setOptimalSplitCount(Integer v) { this.optimalSplitCount = v; }
    public BigDecimal getSplitWgtLow() { return splitWgtLow; }
    public void setSplitWgtLow(BigDecimal v) { this.splitWgtLow = v; }
    public BigDecimal getSplitWgtHigh() { return splitWgtHigh; }
    public void setSplitWgtHigh(BigDecimal v) { this.splitWgtHigh = v; }
    public Integer getSlabCountInProgress() { return slabCountInProgress; }
    public void setSlabCountInProgress(Integer v) { this.slabCountInProgress = v; }
    public BigDecimal getSlabWgtInProgress() { return slabWgtInProgress; }
    public void setSlabWgtInProgress(BigDecimal v) { this.slabWgtInProgress = v; }
    public BigDecimal getFinalWidthLow() { return finalWidthLow; }
    public void setFinalWidthLow(BigDecimal v) { this.finalWidthLow = v; }
    public BigDecimal getFinalWidthHigh() { return finalWidthHigh; }
    public void setFinalWidthHigh(BigDecimal v) { this.finalWidthHigh = v; }
    public BigDecimal getFinalLengthLow() { return finalLengthLow; }
    public void setFinalLengthLow(BigDecimal v) { this.finalLengthLow = v; }
    public BigDecimal getFinalLengthHigh() { return finalLengthHigh; }
    public void setFinalLengthHigh(BigDecimal v) { this.finalLengthHigh = v; }
    public BigDecimal getTargetSlabWidth() { return targetSlabWidth; }
    public void setTargetSlabWidth(BigDecimal v) { this.targetSlabWidth = v; }
    public BigDecimal getTargetSlabLength() { return targetSlabLength; }
    public void setTargetSlabLength(BigDecimal v) { this.targetSlabLength = v; }
    public String getDesignStatus() { return designStatus; }
    public void setDesignStatus(String v) { this.designStatus = v; }
    public String getErrorCode() { return errorCode; }
    public void setErrorCode(String v) { this.errorCode = v; }
}
