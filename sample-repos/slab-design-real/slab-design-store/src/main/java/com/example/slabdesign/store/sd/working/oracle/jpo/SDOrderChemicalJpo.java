package com.example.slabdesign.store.sd.working.oracle.jpo;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.IdClass;
import jakarta.persistence.Table;
import java.math.BigDecimal;

/**
 * sd · working · ORDER_CHEMICAL — 주문 성분 JPO.
 * Composite PK: (CMP_CD, ORG_CD, ORDER_NO) via SDOrderPK.
 * 8 성분 (C, Si, Mn, P, S, Cr, Ni, Al) × {MIN, MAX, AIM} = 24 컬럼.
 * 21-step 알고리즘에서 직접 참조 안 됨 — 추후 강종 분류·검증 시나리오 확장 여지.
 */
@Entity
@Table(name = "ORDER_CHEMICAL")
@IdClass(SDOrderPK.class)
public class SDOrderChemicalJpo {

    @Id
    @Column(name = "CMP_CD", length = 2)
    private String cmpCd;

    @Id
    @Column(name = "ORG_CD", length = 1)
    private String orgCd;

    @Id
    @Column(name = "ORDER_NO", length = 20)
    private String orderNo;

    @Column(name = "C_MIN",  precision = 8, scale = 4) private BigDecimal cMin;
    @Column(name = "C_MAX",  precision = 8, scale = 4) private BigDecimal cMax;
    @Column(name = "C_AIM",  precision = 8, scale = 4) private BigDecimal cAim;

    @Column(name = "SI_MIN", precision = 8, scale = 4) private BigDecimal siMin;
    @Column(name = "SI_MAX", precision = 8, scale = 4) private BigDecimal siMax;
    @Column(name = "SI_AIM", precision = 8, scale = 4) private BigDecimal siAim;

    @Column(name = "MN_MIN", precision = 8, scale = 4) private BigDecimal mnMin;
    @Column(name = "MN_MAX", precision = 8, scale = 4) private BigDecimal mnMax;
    @Column(name = "MN_AIM", precision = 8, scale = 4) private BigDecimal mnAim;

    @Column(name = "P_MIN",  precision = 8, scale = 4) private BigDecimal pMin;
    @Column(name = "P_MAX",  precision = 8, scale = 4) private BigDecimal pMax;
    @Column(name = "P_AIM",  precision = 8, scale = 4) private BigDecimal pAim;

    @Column(name = "S_MIN",  precision = 8, scale = 4) private BigDecimal sMin;
    @Column(name = "S_MAX",  precision = 8, scale = 4) private BigDecimal sMax;
    @Column(name = "S_AIM",  precision = 8, scale = 4) private BigDecimal sAim;

    @Column(name = "CR_MIN", precision = 8, scale = 4) private BigDecimal crMin;
    @Column(name = "CR_MAX", precision = 8, scale = 4) private BigDecimal crMax;
    @Column(name = "CR_AIM", precision = 8, scale = 4) private BigDecimal crAim;

    @Column(name = "NI_MIN", precision = 8, scale = 4) private BigDecimal niMin;
    @Column(name = "NI_MAX", precision = 8, scale = 4) private BigDecimal niMax;
    @Column(name = "NI_AIM", precision = 8, scale = 4) private BigDecimal niAim;

    @Column(name = "AL_MIN", precision = 8, scale = 4) private BigDecimal alMin;
    @Column(name = "AL_MAX", precision = 8, scale = 4) private BigDecimal alMax;
    @Column(name = "AL_AIM", precision = 8, scale = 4) private BigDecimal alAim;

    public String getCmpCd() { return cmpCd; }
    public void setCmpCd(String cmpCd) { this.cmpCd = cmpCd; }
    public String getOrgCd() { return orgCd; }
    public void setOrgCd(String orgCd) { this.orgCd = orgCd; }
    public String getOrderNo() { return orderNo; }
    public void setOrderNo(String orderNo) { this.orderNo = orderNo; }

    public BigDecimal getCMin()  { return cMin; }   public void setCMin(BigDecimal v)  { this.cMin = v; }
    public BigDecimal getCMax()  { return cMax; }   public void setCMax(BigDecimal v)  { this.cMax = v; }
    public BigDecimal getCAim()  { return cAim; }   public void setCAim(BigDecimal v)  { this.cAim = v; }
    public BigDecimal getSiMin() { return siMin; }  public void setSiMin(BigDecimal v) { this.siMin = v; }
    public BigDecimal getSiMax() { return siMax; }  public void setSiMax(BigDecimal v) { this.siMax = v; }
    public BigDecimal getSiAim() { return siAim; }  public void setSiAim(BigDecimal v) { this.siAim = v; }
    public BigDecimal getMnMin() { return mnMin; }  public void setMnMin(BigDecimal v) { this.mnMin = v; }
    public BigDecimal getMnMax() { return mnMax; }  public void setMnMax(BigDecimal v) { this.mnMax = v; }
    public BigDecimal getMnAim() { return mnAim; }  public void setMnAim(BigDecimal v) { this.mnAim = v; }
    public BigDecimal getPMin()  { return pMin; }   public void setPMin(BigDecimal v)  { this.pMin = v; }
    public BigDecimal getPMax()  { return pMax; }   public void setPMax(BigDecimal v)  { this.pMax = v; }
    public BigDecimal getPAim()  { return pAim; }   public void setPAim(BigDecimal v)  { this.pAim = v; }
    public BigDecimal getSMin()  { return sMin; }   public void setSMin(BigDecimal v)  { this.sMin = v; }
    public BigDecimal getSMax()  { return sMax; }   public void setSMax(BigDecimal v)  { this.sMax = v; }
    public BigDecimal getSAim()  { return sAim; }   public void setSAim(BigDecimal v)  { this.sAim = v; }
    public BigDecimal getCrMin() { return crMin; }  public void setCrMin(BigDecimal v) { this.crMin = v; }
    public BigDecimal getCrMax() { return crMax; }  public void setCrMax(BigDecimal v) { this.crMax = v; }
    public BigDecimal getCrAim() { return crAim; }  public void setCrAim(BigDecimal v) { this.crAim = v; }
    public BigDecimal getNiMin() { return niMin; }  public void setNiMin(BigDecimal v) { this.niMin = v; }
    public BigDecimal getNiMax() { return niMax; }  public void setNiMax(BigDecimal v) { this.niMax = v; }
    public BigDecimal getNiAim() { return niAim; }  public void setNiAim(BigDecimal v) { this.niAim = v; }
    public BigDecimal getAlMin() { return alMin; }  public void setAlMin(BigDecimal v) { this.alMin = v; }
    public BigDecimal getAlMax() { return alMax; }  public void setAlMax(BigDecimal v) { this.alMax = v; }
    public BigDecimal getAlAim() { return alAim; }  public void setAlAim(BigDecimal v) { this.alAim = v; }
}
