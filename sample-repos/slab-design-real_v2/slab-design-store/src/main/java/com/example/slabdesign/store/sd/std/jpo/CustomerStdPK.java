package com.example.slabdesign.store.sd.std.jpo;

import java.io.Serializable;
import java.util.Objects;

/**
 * sd · std · CUSTOMER_STD composite PK.
 * (회사, 소구분, 우선순위) — EDGING_GROUP 과 동일한 우선순위 tiebreaker 패턴.
 */
public class CustomerStdPK implements Serializable {

    private static final long serialVersionUID = 1L;

    private String cmpCd;
    private String orgCd;
    private Integer priority;

    public CustomerStdPK() {}

    public CustomerStdPK(String cmpCd, String orgCd, Integer priority) {
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
        if (!(o instanceof CustomerStdPK)) return false;
        CustomerStdPK that = (CustomerStdPK) o;
        return Objects.equals(cmpCd, that.cmpCd)
            && Objects.equals(orgCd, that.orgCd)
            && Objects.equals(priority, that.priority);
    }

    @Override
    public int hashCode() {
        return Objects.hash(cmpCd, orgCd, priority);
    }
}
