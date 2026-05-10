package com.example.slabdesign.store.sd.std.jpo;

import java.io.Serializable;
import java.util.Objects;

/**
 * sd · std · EDGING_GROUP composite PK.
 * (회사코드, 소구분코드, 우선순위) — 우선순위가 unique sequence 가정.
 * 룩업 시 (강종, 품종, 고객사, 열연목표폭) 으로 매칭되는 행이 여러 개일 수 있고,
 * 그 중 우선순위 가장 낮은(또는 높은) 1건을 선택.
 */
public class EdgingGroupPK implements Serializable {

    private static final long serialVersionUID = 1L;

    private String cmpCd;
    private String orgCd;
    private Integer priority;

    public EdgingGroupPK() {}

    public EdgingGroupPK(String cmpCd, String orgCd, Integer priority) {
        this.cmpCd = cmpCd;
        this.orgCd = orgCd;
        this.priority = priority;
    }

    public String getCmpCd() { return cmpCd; }
    public void setCmpCd(String v) { this.cmpCd = v; }
    public String getOrgCd() { return orgCd; }
    public void setOrgCd(String v) { this.orgCd = v; }
    public Integer getPriority() { return priority; }
    public void setPriority(Integer v) { this.priority = v; }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof EdgingGroupPK)) return false;
        EdgingGroupPK that = (EdgingGroupPK) o;
        return Objects.equals(cmpCd, that.cmpCd)
            && Objects.equals(orgCd, that.orgCd)
            && Objects.equals(priority, that.priority);
    }

    @Override
    public int hashCode() {
        return Objects.hash(cmpCd, orgCd, priority);
    }
}
