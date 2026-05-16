package com.example.slabdesign.store.sd.std.jpo;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.IdClass;
import jakarta.persistence.Table;
import java.math.BigDecimal;

/**
 * sd · std · CAST_SPEC — 연주설비사양기준 JPO.
 * Composite PK: (CMP_CD, ORG_CD, SM_CD, CAST_CD, MACHINE_CD, PRODUCT_CD).
 * 룩업 시 ORDER_OS.CONFIRMED_PLANT_CD 의 1자리(제강위치) → SM_CD 매칭.
 * (CAST_CD, MACHINE_CD) 는 PlantMappingService 가 SM_CD 기반으로 하드코딩 매핑 제공.
 */
@Entity
@Table(name = "CAST_SPEC")
@IdClass(CastSpecPK.class)
public class CastSpecJpo {

    @Id @Column(name = "CMP_CD", length = 2)
    private String cmpCd;

    @Id @Column(name = "ORG_CD", length = 1)
    private String orgCd;

    @Id @Column(name = "SM_CD", length = 1)
    private String smCd;            // 제강코드 (확통1자리)

    @Id @Column(name = "CAST_CD", length = 4)
    private String castCd;          // 연주코드

    @Id @Column(name = "MACHINE_CD", length = 4)
    private String machineCd;       // 머신코드

    @Id @Column(name = "PRODUCT_CD", length = 4)
    private String productCd;   // 품종

    @Column(name = "SLAB_THICKNESS", precision = 6, scale = 2)
    private BigDecimal slabThickness;   // step 1 두께

    @Column(name = "WIDTH_LOW", precision = 10, scale = 2)
    private BigDecimal widthLow;        // step 2 폭하한 계산

    @Column(name = "WIDTH_HIGH", precision = 10, scale = 2)
    private BigDecimal widthHigh;       // step 2 폭상한 계산

    @Column(name = "LENGTH_LOW", precision = 10, scale = 2)
    private BigDecimal lengthLow;       // step 3 길이하한 계산

    @Column(name = "LENGTH_HIGH", precision = 10, scale = 2)
    private BigDecimal lengthHigh;      // step 3 길이상한 계산

    @Column(name = "WGT_LOW", precision = 10, scale = 3)
    private BigDecimal wgtLow;          // 21-step 미참조 (참고용)

    @Column(name = "WGT_HIGH", precision = 10, scale = 3)
    private BigDecimal wgtHigh;         // 21-step 미참조 (참고용)

    public String getCmpCd() { return cmpCd; }
    public void setCmpCd(String v) { this.cmpCd = v; }
    public String getOrgCd() { return orgCd; }
    public void setOrgCd(String v) { this.orgCd = v; }
    public String getSmCd() { return smCd; }
    public void setSmCd(String v) { this.smCd = v; }
    public String getCastCd() { return castCd; }
    public void setCastCd(String v) { this.castCd = v; }
    public String getMachineCd() { return machineCd; }
    public void setMachineCd(String v) { this.machineCd = v; }
    public String getProductCd() { return productCd; }
    public void setProductCd(String v) { this.productCd = v; }
    public BigDecimal getSlabThickness() { return slabThickness; }
    public void setSlabThickness(BigDecimal v) { this.slabThickness = v; }
    public BigDecimal getWidthLow() { return widthLow; }
    public void setWidthLow(BigDecimal v) { this.widthLow = v; }
    public BigDecimal getWidthHigh() { return widthHigh; }
    public void setWidthHigh(BigDecimal v) { this.widthHigh = v; }
    public BigDecimal getLengthLow() { return lengthLow; }
    public void setLengthLow(BigDecimal v) { this.lengthLow = v; }
    public BigDecimal getLengthHigh() { return lengthHigh; }
    public void setLengthHigh(BigDecimal v) { this.lengthHigh = v; }
    public BigDecimal getWgtLow() { return wgtLow; }
    public void setWgtLow(BigDecimal v) { this.wgtLow = v; }
    public BigDecimal getWgtHigh() { return wgtHigh; }
    public void setWgtHigh(BigDecimal v) { this.wgtHigh = v; }
}
