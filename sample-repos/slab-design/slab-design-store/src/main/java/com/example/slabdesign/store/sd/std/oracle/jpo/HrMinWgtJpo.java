package com.example.slabdesign.store.sd.std.oracle.jpo;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.IdClass;
import jakarta.persistence.Table;
import java.math.BigDecimal;

/**
 * sd · std · HR_MIN_WGT — 압연 MIN 단중 기준 (2차원 sheet) JPO.
 * Composite PK: (CMP_CD, ORG_CD, HR_CD, THICKNESS, WIDTH).
 * HR_MAX_WGT 와 동일한 룩업 패턴 (사용자 사양 — semantically 특이하지만 사용자 룰 준수).
 */
@Entity
@Table(name = "HR_MIN_WGT")
@IdClass(HrMinWgtPK.class)
public class HrMinWgtJpo {

    @Id @Column(name = "CMP_CD", length = 2)
    private String cmpCd;

    @Id @Column(name = "ORG_CD", length = 1)
    private String orgCd;

    @Id @Column(name = "HR_CD", length = 1)
    private String hrCd;

    @Id @Column(name = "THICKNESS", precision = 6, scale = 2)
    private BigDecimal thickness;

    @Id @Column(name = "WIDTH", precision = 10, scale = 2)
    private BigDecimal width;

    @Column(name = "MIN_WGT", precision = 10, scale = 3)
    private BigDecimal minWgt;      // 최소 단중

    public String getCmpCd() { return cmpCd; }
    public void setCmpCd(String v) { this.cmpCd = v; }
    public String getOrgCd() { return orgCd; }
    public void setOrgCd(String v) { this.orgCd = v; }
    public String getHrCd() { return hrCd; }
    public void setHrCd(String v) { this.hrCd = v; }
    public BigDecimal getThickness() { return thickness; }
    public void setThickness(BigDecimal v) { this.thickness = v; }
    public BigDecimal getWidth() { return width; }
    public void setWidth(BigDecimal v) { this.width = v; }
    public BigDecimal getMinWgt() { return minWgt; }
    public void setMinWgt(BigDecimal v) { this.minWgt = v; }
}
