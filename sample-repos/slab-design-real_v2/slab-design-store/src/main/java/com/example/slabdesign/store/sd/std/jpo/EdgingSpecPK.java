package com.example.slabdesign.store.sd.std.jpo;

import java.io.Serializable;
import java.util.Objects;

/**
 * sd · std · EDGING_SPEC composite PK.
 * (회사코드, 소구분코드, edging그룹코드).
 * EDGING_GROUP_CD 가 '*' 인 row 는 catchall (전체).
 */
public class EdgingSpecPK implements Serializable {

    private static final long serialVersionUID = 1L;

    private String cmpCd;
    private String orgCd;
    private String edgingGroupCd;

    public EdgingSpecPK() {}

    public EdgingSpecPK(String cmpCd, String orgCd, String edgingGroupCd) {
        this.cmpCd = cmpCd;
        this.orgCd = orgCd;
        this.edgingGroupCd = edgingGroupCd;
    }

    public String getCmpCd() { return cmpCd; }
    public void setCmpCd(String v) { this.cmpCd = v; }
    public String getOrgCd() { return orgCd; }
    public void setOrgCd(String v) { this.orgCd = v; }
    public String getEdgingGroupCd() { return edgingGroupCd; }
    public void setEdgingGroupCd(String v) { this.edgingGroupCd = v; }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof EdgingSpecPK)) return false;
        EdgingSpecPK that = (EdgingSpecPK) o;
        return Objects.equals(cmpCd, that.cmpCd)
            && Objects.equals(orgCd, that.orgCd)
            && Objects.equals(edgingGroupCd, that.edgingGroupCd);
    }

    @Override
    public int hashCode() {
        return Objects.hash(cmpCd, orgCd, edgingGroupCd);
    }
}
