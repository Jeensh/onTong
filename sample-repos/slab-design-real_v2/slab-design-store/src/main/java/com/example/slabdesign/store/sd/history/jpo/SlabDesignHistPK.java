package com.example.slabdesign.store.sd.history.jpo;

import java.io.Serializable;
import java.util.Objects;

/**
 * sd · history · SLAB_DESIGN_HIST composite PK.
 * (회사코드, 소코드, 이력 ID) — 3 컬럼.
 */
public class SlabDesignHistPK implements Serializable {

    private static final long serialVersionUID = 1L;

    private String cmpCd;
    private String orgCd;
    private String histId;

    public SlabDesignHistPK() {}

    public SlabDesignHistPK(String cmpCd, String orgCd, String histId) {
        this.cmpCd = cmpCd;
        this.orgCd = orgCd;
        this.histId = histId;
    }

    public String getCmpCd() { return cmpCd; }
    public void setCmpCd(String v) { this.cmpCd = v; }
    public String getOrgCd() { return orgCd; }
    public void setOrgCd(String v) { this.orgCd = v; }
    public String getHistId() { return histId; }
    public void setHistId(String v) { this.histId = v; }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof SlabDesignHistPK)) return false;
        SlabDesignHistPK that = (SlabDesignHistPK) o;
        return Objects.equals(cmpCd, that.cmpCd)
            && Objects.equals(orgCd, that.orgCd)
            && Objects.equals(histId, that.histId);
    }

    @Override
    public int hashCode() {
        return Objects.hash(cmpCd, orgCd, histId);
    }
}
