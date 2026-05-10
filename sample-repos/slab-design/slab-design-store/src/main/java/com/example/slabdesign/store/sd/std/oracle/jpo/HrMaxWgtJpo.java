package com.example.slabdesign.store.sd.std.oracle.jpo;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.IdClass;
import jakarta.persistence.Table;
import java.math.BigDecimal;

/**
 * sd · std · HR_MAX_WGT — 압연 MAX 단중 기준 (2차원 sheet) JPO.
 * Composite PK: (CMP_CD, ORG_CD, HR_CD, THICKNESS, WIDTH).
 *
 * 룩업 패턴:
 *   주문의 (입력두께, 입력폭) → 다음 cell 을 찾음:
 *     THICKNESS >= 입력두께 AND WIDTH >= 입력폭
 *     ORDER BY THICKNESS ASC, WIDTH ASC LIMIT 1
 *   = 입력값을 cover 하는 가장 작은 cell 의 MAX_WGT 반환.
 *
 * NOTE: HR_CD 는 HR_SPEC.HR_PLANT_CD 와 동일 도메인 (열연공장 1자리). 레거시 비표준 컬럼명.
 */
@Entity
@Table(name = "HR_MAX_WGT")
@IdClass(HrMaxWgtPK.class)
public class HrMaxWgtJpo {

    @Id @Column(name = "CMP_CD", length = 2)
    private String cmpCd;

    @Id @Column(name = "ORG_CD", length = 1)
    private String orgCd;

    @Id @Column(name = "HR_CD", length = 1)
    private String hrCd;            // 열연코드 (확통2자리)

    @Id @Column(name = "THICKNESS", precision = 6, scale = 2)
    private BigDecimal thickness;   // cell 좌표 - 두께

    @Id @Column(name = "WIDTH", precision = 10, scale = 2)
    private BigDecimal width;       // cell 좌표 - 폭

    @Column(name = "MAX_WGT", precision = 10, scale = 3)
    private BigDecimal maxWgt;      // 최대 단중

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
    public BigDecimal getMaxWgt() { return maxWgt; }
    public void setMaxWgt(BigDecimal v) { this.maxWgt = v; }
}
