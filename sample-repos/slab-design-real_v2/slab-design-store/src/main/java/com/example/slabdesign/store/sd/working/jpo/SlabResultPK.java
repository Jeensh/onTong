package com.example.slabdesign.store.sd.working.jpo;

import java.io.Serializable;
import java.util.Objects;

/**
 * sd · working · SLAB_RESULT composite PK.
 * (회사코드, 소코드, slab 번호) — 3 컬럼.
 */
public class SlabResultPK implements Serializable {

    private static final long serialVersionUID = 1L;

    private String cmpCd;
    private String orgCd;
    private String slabNo;

    public SlabResultPK() {}

    public SlabResultPK(String cmpCd, String orgCd, String slabNo) {
        this.cmpCd = cmpCd;
        this.orgCd = orgCd;
        this.slabNo = slabNo;
    }

    public String getCmpCd() { return cmpCd; }
    public void setCmpCd(String v) { this.cmpCd = v; }
    public String getOrgCd() { return orgCd; }
    public void setOrgCd(String v) { this.orgCd = v; }
    public String getSlabNo() { return slabNo; }
    public void setSlabNo(String v) { this.slabNo = v; }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof SlabResultPK)) return false;
        SlabResultPK that = (SlabResultPK) o;
        return Objects.equals(cmpCd, that.cmpCd)
            && Objects.equals(orgCd, that.orgCd)
            && Objects.equals(slabNo, that.slabNo);
    }

    @Override
    public int hashCode() {
        return Objects.hash(cmpCd, orgCd, slabNo);
    }
}
