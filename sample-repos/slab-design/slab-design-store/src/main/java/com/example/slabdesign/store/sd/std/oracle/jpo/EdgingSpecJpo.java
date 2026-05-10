package com.example.slabdesign.store.sd.std.oracle.jpo;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.IdClass;
import jakarta.persistence.Table;
import java.math.BigDecimal;

/**
 * sd · std · EDGING_SPEC — Edging 능력 기준 JPO.
 * Composite PK: (CMP_CD, ORG_CD, EDGING_GROUP_CD).
 * EDGING_GROUP_CD = '*' 면 catchall (전체 그룹). 룩업 시 정확매칭 우선, 미존재 시 '*' fallback.
 */
@Entity
@Table(name = "EDGING_SPEC")
@IdClass(EdgingSpecPK.class)
public class EdgingSpecJpo {

    @Id @Column(name = "CMP_CD", length = 2)
    private String cmpCd;

    @Id @Column(name = "ORG_CD", length = 1)
    private String orgCd;

    @Id @Column(name = "EDGING_GROUP_CD", length = 10)
    private String edgingGroupCd;       // '*' wildcard 가능

    @Column(name = "EDGING_CAP_LOW", precision = 10, scale = 2)
    private BigDecimal edgingCapLow;    // step 2 폭하한 계산 (열연목표폭 + 이 값)

    @Column(name = "EDGING_CAP_HIGH", precision = 10, scale = 2)
    private BigDecimal edgingCapHigh;   // step 2 폭상한 계산 (열연목표폭 + 이 값)

    public String getCmpCd() { return cmpCd; }
    public void setCmpCd(String v) { this.cmpCd = v; }
    public String getOrgCd() { return orgCd; }
    public void setOrgCd(String v) { this.orgCd = v; }
    public String getEdgingGroupCd() { return edgingGroupCd; }
    public void setEdgingGroupCd(String v) { this.edgingGroupCd = v; }
    public BigDecimal getEdgingCapLow() { return edgingCapLow; }
    public void setEdgingCapLow(BigDecimal v) { this.edgingCapLow = v; }
    public BigDecimal getEdgingCapHigh() { return edgingCapHigh; }
    public void setEdgingCapHigh(BigDecimal v) { this.edgingCapHigh = v; }
}
