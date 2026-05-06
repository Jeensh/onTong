package com.example.slabdesign.store.sd.std.oracle.jpo;

import java.io.Serializable;
import java.util.Objects;

/**
 * sd · std · SD_PRODUCTIVITY_STD composite PK.
 * (회사, 소구분, 공정구분, 강종, 품종코드, 고객사) — 6 컬럼.
 */
public class SdProductivityStdPK implements Serializable {

    private static final long serialVersionUID = 1L;

    private String cmpCd;
    private String orgCd;
    private String procCd;
    private String gradeCd;
    private String prodKindCd;
    private String customerCd;

    public SdProductivityStdPK() {}

    public SdProductivityStdPK(String cmpCd, String orgCd, String procCd,
                               String gradeCd, String prodKindCd, String customerCd) {
        this.cmpCd = cmpCd;
        this.orgCd = orgCd;
        this.procCd = procCd;
        this.gradeCd = gradeCd;
        this.prodKindCd = prodKindCd;
        this.customerCd = customerCd;
    }

    public String getCmpCd() { return cmpCd; }
    public void setCmpCd(String v) { this.cmpCd = v; }
    public String getOrgCd() { return orgCd; }
    public void setOrgCd(String v) { this.orgCd = v; }
    public String getProcCd() { return procCd; }
    public void setProcCd(String v) { this.procCd = v; }
    public String getGradeCd() { return gradeCd; }
    public void setGradeCd(String v) { this.gradeCd = v; }
    public String getProdKindCd() { return prodKindCd; }
    public void setProdKindCd(String v) { this.prodKindCd = v; }
    public String getCustomerCd() { return customerCd; }
    public void setCustomerCd(String v) { this.customerCd = v; }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof SdProductivityStdPK)) return false;
        SdProductivityStdPK that = (SdProductivityStdPK) o;
        return Objects.equals(cmpCd, that.cmpCd)
            && Objects.equals(orgCd, that.orgCd)
            && Objects.equals(procCd, that.procCd)
            && Objects.equals(gradeCd, that.gradeCd)
            && Objects.equals(prodKindCd, that.prodKindCd)
            && Objects.equals(customerCd, that.customerCd);
    }

    @Override
    public int hashCode() {
        return Objects.hash(cmpCd, orgCd, procCd, gradeCd, prodKindCd, customerCd);
    }
}
