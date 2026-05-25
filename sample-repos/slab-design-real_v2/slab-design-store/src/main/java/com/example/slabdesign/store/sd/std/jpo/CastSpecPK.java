package com.example.slabdesign.store.sd.std.jpo;

import java.io.Serializable;
import java.util.Objects;

/**
 * sd · std · CAST_SPEC composite PK.
 * (온톨로지코드, 소구분코드, 제강코드, 연주코드, 머신코드, 품종) — 6 컬럼.
 */
public class CastSpecPK implements Serializable {

    private static final long serialVersionUID = 1L;

    private String cmpCd;
    private String orgCd;
    private String smCd;
    private String castCd;
    private String machineCd;
    private String productCd;

    public CastSpecPK() {}

    public CastSpecPK(String cmpCd, String orgCd, String smCd,
                      String castCd, String machineCd, String productCd) {
        this.cmpCd = cmpCd;
        this.orgCd = orgCd;
        this.smCd = smCd;
        this.castCd = castCd;
        this.machineCd = machineCd;
        this.productCd = productCd;
    }

    public String getCmpCd() { return cmpCd; }
    public void setCmpCd(String v) { this.cmpCd = v; }
    public String getOrgCd() { return orgCd; }
    public void setOrgCd(String v) { this.orgCd = v; }
    public String getSmCd() { return smCd; }
    public void setSmCd(String v) { this.smCd = v; }
    public String getCastCd() { return castCd; }
    public void setCastCd(String v) { this.castCd = v; }
    public String getMachineCd() { return machineCd; }
    public void setMachineCd(String v) { this.machineCd = v; }
    public String getProductCd() { return productCd; }
    public void setProductCd(String v) { this.productCd = v; }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof CastSpecPK)) return false;
        CastSpecPK that = (CastSpecPK) o;
        return Objects.equals(cmpCd, that.cmpCd)
            && Objects.equals(orgCd, that.orgCd)
            && Objects.equals(smCd, that.smCd)
            && Objects.equals(castCd, that.castCd)
            && Objects.equals(machineCd, that.machineCd)
            && Objects.equals(productCd, that.productCd);
    }

    @Override
    public int hashCode() {
        return Objects.hash(cmpCd, orgCd, smCd, castCd, machineCd, productCd);
    }
}
