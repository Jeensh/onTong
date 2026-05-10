package com.example.slabdesign.store.sd.std.jpo;

import java.io.Serializable;
import java.util.Objects;

/**
 * sd · std · HR_SPEC composite PK.
 * (회사코드, 소구분코드, 열연공장코드, 품종) — 4 컬럼.
 */
public class HrSpecPK implements Serializable {

    private static final long serialVersionUID = 1L;

    private String cmpCd;
    private String orgCd;
    private String hrPlantCd;
    private String productCd;

    public HrSpecPK() {}

    public HrSpecPK(String cmpCd, String orgCd, String hrPlantCd, String productCd) {
        this.cmpCd = cmpCd;
        this.orgCd = orgCd;
        this.hrPlantCd = hrPlantCd;
        this.productCd = productCd;
    }

    public String getCmpCd() { return cmpCd; }
    public void setCmpCd(String v) { this.cmpCd = v; }
    public String getOrgCd() { return orgCd; }
    public void setOrgCd(String v) { this.orgCd = v; }
    public String getHrPlantCd() { return hrPlantCd; }
    public void setHrPlantCd(String v) { this.hrPlantCd = v; }
    public String getProductCd() { return productCd; }
    public void setProductCd(String v) { this.productCd = v; }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof HrSpecPK)) return false;
        HrSpecPK that = (HrSpecPK) o;
        return Objects.equals(cmpCd, that.cmpCd)
            && Objects.equals(orgCd, that.orgCd)
            && Objects.equals(hrPlantCd, that.hrPlantCd)
            && Objects.equals(productCd, that.productCd);
    }

    @Override
    public int hashCode() {
        return Objects.hash(cmpCd, orgCd, hrPlantCd, productCd);
    }
}
