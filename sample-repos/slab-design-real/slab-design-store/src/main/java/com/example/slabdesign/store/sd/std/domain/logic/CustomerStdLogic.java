package com.example.slabdesign.store.sd.std.domain.logic;

import com.example.slabdesign.store.sd.std.domain.entity.CustomerStdEntity;
import com.example.slabdesign.store.sd.std.oracle.jpo.CustomerStdJpo;
import org.springframework.stereotype.Component;

@Component
public class CustomerStdLogic {

    public CustomerStdEntity toEntity(CustomerStdJpo jpo) {
        if (jpo == null) return null;
        CustomerStdEntity e = new CustomerStdEntity();
        e.setCmpCd(jpo.getCmpCd());
        e.setOrgCd(jpo.getOrgCd());
        e.setPriority(jpo.getPriority());
        e.setProductNameCd(jpo.getProductNameCd());
        e.setCustomerCd(jpo.getCustomerCd());
        e.setPkgWgtHigh(jpo.getPkgWgtHigh());
        e.setPkgWgtLow(jpo.getPkgWgtLow());
        return e;
    }
}
