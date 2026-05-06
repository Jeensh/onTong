package com.example.slabdesign.store.sd.std.oracle.jpo;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.IdClass;
import jakarta.persistence.Table;
import java.math.BigDecimal;

/**
 * sd · std · EDGING_GROUP — Edging 능력 그룹 매칭 룰 JPO.
 *
 * 매칭 규칙:
 *   주문의 (강종 = GRADE_CD)
 *     AND (품종 = PRODUCT_TYPE_CD)
 *     AND (고객사 = CUSTOMER_CD)
 *     AND (열연목표폭 BETWEEN HR_TGT_WIDTH_LOW AND HR_TGT_WIDTH_HIGH)
 *   → 매칭되는 row 들 중 PRIORITY 기준으로 1건 선택 → EDGING_GROUP_CD 출력.
 *
 * 출력 EDGING_GROUP_CD 는 EDGING_SPEC.EDGING_GROUP_CD 룩업 키로 사용.
 */
@Entity
@Table(name = "EDGING_GROUP")
@IdClass(EdgingGroupPK.class)
public class EdgingGroupJpo {

    @Id @Column(name = "CMP_CD", length = 2)
    private String cmpCd;

    @Id @Column(name = "ORG_CD", length = 1)
    private String orgCd;

    @Id @Column(name = "PRIORITY")
    private Integer priority;       // 우선순위 (tiebreaker)

    @Column(name = "EDGING_GROUP_CD", length = 10)
    private String edgingGroupCd;   // 출력값

    @Column(name = "GRADE_CD", length = 10)
    private String gradeCd;

    @Column(name = "PRODUCT_TYPE_CD", length = 4)
    private String productTypeCd;

    @Column(name = "CUSTOMER_CD", length = 10)
    private String customerCd;

    @Column(name = "HR_TGT_WIDTH_HIGH", precision = 10, scale = 2)
    private BigDecimal hrTgtWidthHigh;  // 주문 열연목표폭이 이 값 이하일 때 매칭

    @Column(name = "HR_TGT_WIDTH_LOW", precision = 10, scale = 2)
    private BigDecimal hrTgtWidthLow;   // 주문 열연목표폭이 이 값 이상일 때 매칭

    public String getCmpCd() { return cmpCd; }
    public void setCmpCd(String v) { this.cmpCd = v; }
    public String getOrgCd() { return orgCd; }
    public void setOrgCd(String v) { this.orgCd = v; }
    public Integer getPriority() { return priority; }
    public void setPriority(Integer v) { this.priority = v; }
    public String getEdgingGroupCd() { return edgingGroupCd; }
    public void setEdgingGroupCd(String v) { this.edgingGroupCd = v; }
    public String getGradeCd() { return gradeCd; }
    public void setGradeCd(String v) { this.gradeCd = v; }
    public String getProductTypeCd() { return productTypeCd; }
    public void setProductTypeCd(String v) { this.productTypeCd = v; }
    public String getCustomerCd() { return customerCd; }
    public void setCustomerCd(String v) { this.customerCd = v; }
    public BigDecimal getHrTgtWidthHigh() { return hrTgtWidthHigh; }
    public void setHrTgtWidthHigh(BigDecimal v) { this.hrTgtWidthHigh = v; }
    public BigDecimal getHrTgtWidthLow() { return hrTgtWidthLow; }
    public void setHrTgtWidthLow(BigDecimal v) { this.hrTgtWidthLow = v; }
}
