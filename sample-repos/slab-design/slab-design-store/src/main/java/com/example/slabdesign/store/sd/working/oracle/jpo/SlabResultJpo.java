package com.example.slabdesign.store.sd.working.oracle.jpo;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.IdClass;
import jakarta.persistence.Table;
import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * sd · working · SLAB_RESULT — Slab 설계 결과 JPO.
 * Composite PK: (CMP_CD, ORG_CD, SLAB_NO).
 *
 * 원본/조정 패턴:
 *   - SLAB_WIDTH/LENGTH/WGT (+_HIGH/_LOW): 최초 설계 결과 (size 원복용)
 *   - SLAB_WIDTH_1/LENGTH_1/WGT_1 (+_HIGH/_LOW): 사이즈 조정 후 현재 값
 *   - SLAB_THICKNESS: 조정 안 함 (단일 컬럼만)
 *
 * FAIL 시 이 테이블 미저장. SLAB_DESIGN_HIST 에만 에러코드와 함께 이력.
 *
 * 확정/가능통과공장코드는 설계 시점 snapshot (주문이 나중에 변경되어도 결과는 보존).
 */
@Entity
@Table(name = "SLAB_RESULT")
@IdClass(SlabResultPK.class)
public class SlabResultJpo {

    @Id @Column(name = "CMP_CD", length = 2)
    private String cmpCd;

    @Id @Column(name = "ORG_CD", length = 1)
    private String orgCd;

    @Id @Column(name = "SLAB_NO", length = 20)
    private String slabNo;

    // FK to ORDER_OS — composite (CMP_CD + ORG_CD + ORDER_NO). 회사·소코드는 PK 와 공유.
    @Column(name = "ORDER_NO", length = 20)
    private String orderNo;

    // Snapshot at design time
    @Column(name = "CONFIRMED_PLANT_CD", length = 8)
    private String confirmedPlantCd;

    @Column(name = "POSSIBLE_PLANT_CD", length = 16)
    private String possiblePlantCd;

    // 두께 (조정 없음)
    @Column(name = "SLAB_THICKNESS", precision = 6, scale = 2)
    private BigDecimal slabThickness;

    // 원본 (최초 설계)
    @Column(name = "SLAB_WIDTH", precision = 10, scale = 2)
    private BigDecimal slabWidth;
    @Column(name = "SLAB_WIDTH_HIGH", precision = 10, scale = 2)
    private BigDecimal slabWidthHigh;
    @Column(name = "SLAB_WIDTH_LOW", precision = 10, scale = 2)
    private BigDecimal slabWidthLow;
    @Column(name = "SLAB_LENGTH", precision = 10, scale = 2)
    private BigDecimal slabLength;
    @Column(name = "SLAB_LENGTH_HIGH", precision = 10, scale = 2)
    private BigDecimal slabLengthHigh;
    @Column(name = "SLAB_LENGTH_LOW", precision = 10, scale = 2)
    private BigDecimal slabLengthLow;
    @Column(name = "SLAB_WGT", precision = 10, scale = 3)
    private BigDecimal slabWgt;
    @Column(name = "SLAB_WGT_HIGH", precision = 10, scale = 3)
    private BigDecimal slabWgtHigh;
    @Column(name = "SLAB_WGT_LOW", precision = 10, scale = 3)
    private BigDecimal slabWgtLow;

    // 조정 (사이즈 변경 후 — _1 suffix)
    @Column(name = "SLAB_WIDTH_1", precision = 10, scale = 2)
    private BigDecimal slabWidth1;
    @Column(name = "SLAB_WIDTH_HIGH_1", precision = 10, scale = 2)
    private BigDecimal slabWidthHigh1;
    @Column(name = "SLAB_WIDTH_LOW_1", precision = 10, scale = 2)
    private BigDecimal slabWidthLow1;
    @Column(name = "SLAB_LENGTH_1", precision = 10, scale = 2)
    private BigDecimal slabLength1;
    @Column(name = "SLAB_LENGTH_HIGH_1", precision = 10, scale = 2)
    private BigDecimal slabLengthHigh1;
    @Column(name = "SLAB_LENGTH_LOW_1", precision = 10, scale = 2)
    private BigDecimal slabLengthLow1;
    @Column(name = "SLAB_WGT_1", precision = 10, scale = 3)
    private BigDecimal slabWgt1;
    @Column(name = "SLAB_WGT_HIGH_1", precision = 10, scale = 3)
    private BigDecimal slabWgtHigh1;
    @Column(name = "SLAB_WGT_LOW_1", precision = 10, scale = 3)
    private BigDecimal slabWgtLow1;

    @Column(name = "SPLIT_COUNT")
    private Integer splitCount;

    @Column(name = "CREATED_AT")
    private LocalDateTime createdAt;

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
}
