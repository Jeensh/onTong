package com.example.slabdesign.store.sd.std.jpo;

import java.io.Serializable;
import java.math.BigDecimal;
import java.util.Objects;

/**
 * sd · std · HR_MAX_WGT composite PK.
 * (회사, 소구분, 열연코드, 두께, 폭) — 5 컬럼.
 * 두께·폭은 2차원 sheet 룩업의 cell 좌표.
 */
public class HrMaxWgtPK implements Serializable {

    private static final long serialVersionUID = 1L;

    private String cmpCd;
    private String orgCd;
    private String hrCd;
    private BigDecimal thickness;
    private BigDecimal width;

    public HrMaxWgtPK() {}

    public HrMaxWgtPK(String cmpCd, String orgCd, String hrCd, BigDecimal thickness, BigDecimal width) {
        this.cmpCd = cmpCd;
        this.orgCd = orgCd;
        this.hrCd = hrCd;
        this.thickness = thickness;
        this.width = width;
    }

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

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof HrMaxWgtPK)) return false;
        HrMaxWgtPK that = (HrMaxWgtPK) o;
        return Objects.equals(cmpCd, that.cmpCd)
            && Objects.equals(orgCd, that.orgCd)
            && Objects.equals(hrCd, that.hrCd)
            && Objects.equals(thickness, that.thickness)
            && Objects.equals(width, that.width);
    }

    @Override
    public int hashCode() {
        return Objects.hash(cmpCd, orgCd, hrCd, thickness, width);
    }
}
