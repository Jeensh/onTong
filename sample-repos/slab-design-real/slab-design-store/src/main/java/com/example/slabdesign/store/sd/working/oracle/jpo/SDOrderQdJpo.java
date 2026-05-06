package com.example.slabdesign.store.sd.working.oracle.jpo;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.IdClass;
import jakarta.persistence.Table;
import java.math.BigDecimal;

/**
 * sd · working · ORDER_QD — 주문 품질설계 JPO.
 * Composite PK: (CMP_CD, ORG_CD, ORDER_NO) via SDOrderPK.
 * HR_TGT_WIDTH_1~5 : 열연공장별 목표 폭. ORDER_OS.CONFIRMED_PLANT_CD 의 열연 위치(2번째 자리)를 보고
 * 5개 중 매칭 컬럼을 선택하는 매핑 로직은 P2.2 알고리즘 단계 (step 2 폭범위 산정) 에서 구현.
 */
@Entity
@Table(name = "ORDER_QD")
@IdClass(SDOrderPK.class)
public class SDOrderQdJpo {

    @Id
    @Column(name = "CMP_CD", length = 2)
    private String cmpCd;

    @Id
    @Column(name = "ORG_CD", length = 1)
    private String orgCd;

    @Id
    @Column(name = "ORDER_NO", length = 20)
    private String orderNo;

    @Column(name = "GRADE_CD", length = 10)
    private String gradeCd;

    @Column(name = "HR_TGT_WIDTH_1", precision = 10, scale = 2)
    private BigDecimal hrTgtWidth1;

    @Column(name = "HR_TGT_WIDTH_2", precision = 10, scale = 2)
    private BigDecimal hrTgtWidth2;

    @Column(name = "HR_TGT_WIDTH_3", precision = 10, scale = 2)
    private BigDecimal hrTgtWidth3;

    @Column(name = "HR_TGT_WIDTH_4", precision = 10, scale = 2)
    private BigDecimal hrTgtWidth4;

    @Column(name = "HR_TGT_WIDTH_5", precision = 10, scale = 2)
    private BigDecimal hrTgtWidth5;

    public String getCmpCd() { return cmpCd; }
    public void setCmpCd(String cmpCd) { this.cmpCd = cmpCd; }
    public String getOrgCd() { return orgCd; }
    public void setOrgCd(String orgCd) { this.orgCd = orgCd; }
    public String getOrderNo() { return orderNo; }
    public void setOrderNo(String orderNo) { this.orderNo = orderNo; }
    public String getGradeCd() { return gradeCd; }
    public void setGradeCd(String v) { this.gradeCd = v; }
    public BigDecimal getHrTgtWidth1() { return hrTgtWidth1; }
    public void setHrTgtWidth1(BigDecimal v) { this.hrTgtWidth1 = v; }
    public BigDecimal getHrTgtWidth2() { return hrTgtWidth2; }
    public void setHrTgtWidth2(BigDecimal v) { this.hrTgtWidth2 = v; }
    public BigDecimal getHrTgtWidth3() { return hrTgtWidth3; }
    public void setHrTgtWidth3(BigDecimal v) { this.hrTgtWidth3 = v; }
    public BigDecimal getHrTgtWidth4() { return hrTgtWidth4; }
    public void setHrTgtWidth4(BigDecimal v) { this.hrTgtWidth4 = v; }
    public BigDecimal getHrTgtWidth5() { return hrTgtWidth5; }
    public void setHrTgtWidth5(BigDecimal v) { this.hrTgtWidth5 = v; }
}
