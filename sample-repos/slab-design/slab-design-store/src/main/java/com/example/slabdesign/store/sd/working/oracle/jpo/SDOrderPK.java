package com.example.slabdesign.store.sd.working.oracle.jpo;

import java.io.Serializable;
import java.util.Objects;

/**
 * sd · working · ORDER 4종 공통 복합키 (회사코드, 소코드, 주문번호).
 * @IdClass 로 4 JPO (OS/OM/QD/CHEMICAL) 가 공유.
 * 필드명·타입은 각 @Entity 의 @Id 필드와 정확히 일치해야 한다 (JPA 규약).
 */
public class SDOrderPK implements Serializable {

    private static final long serialVersionUID = 1L;

    private String cmpCd;
    private String orgCd;
    private String orderNo;

    public SDOrderPK() {}

    public SDOrderPK(String cmpCd, String orgCd, String orderNo) {
        this.cmpCd = cmpCd;
        this.orgCd = orgCd;
        this.orderNo = orderNo;
    }

    public String getCmpCd() { return cmpCd; }
    public void setCmpCd(String cmpCd) { this.cmpCd = cmpCd; }
    public String getOrgCd() { return orgCd; }
    public void setOrgCd(String orgCd) { this.orgCd = orgCd; }
    public String getOrderNo() { return orderNo; }
    public void setOrderNo(String orderNo) { this.orderNo = orderNo; }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof SDOrderPK)) return false;
        SDOrderPK that = (SDOrderPK) o;
        return Objects.equals(cmpCd, that.cmpCd)
            && Objects.equals(orgCd, that.orgCd)
            && Objects.equals(orderNo, that.orderNo);
    }

    @Override
    public int hashCode() {
        return Objects.hash(cmpCd, orgCd, orderNo);
    }
}
