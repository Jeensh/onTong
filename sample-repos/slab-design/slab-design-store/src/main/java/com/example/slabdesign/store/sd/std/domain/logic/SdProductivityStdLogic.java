package com.example.slabdesign.store.sd.std.domain.logic;

import com.example.slabdesign.store.sd.std.domain.entity.SdProductivityStdEntity;
import com.example.slabdesign.store.sd.std.oracle.jpo.SdProductivityStdJpo;
import org.springframework.stereotype.Component;

@Component
public class SdProductivityStdLogic {

    public SdProductivityStdEntity toEntity(SdProductivityStdJpo jpo) {
        if (jpo == null) return null;
        SdProductivityStdEntity e = new SdProductivityStdEntity();
        e.setCmpCd(jpo.getCmpCd());
        e.setOrgCd(jpo.getOrgCd());
        e.setProcCd(jpo.getProcCd());
        e.setGradeCd(jpo.getGradeCd());
        e.setProdKindCd(jpo.getProdKindCd());
        e.setCustomerCd(jpo.getCustomerCd());
        e.setProductivity(jpo.getProductivity());
        return e;
    }
}
