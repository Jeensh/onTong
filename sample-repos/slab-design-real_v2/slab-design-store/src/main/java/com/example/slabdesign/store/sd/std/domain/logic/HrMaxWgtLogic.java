package com.example.slabdesign.store.sd.std.domain.logic;

import com.example.slabdesign.store.sd.std.domain.entity.HrMaxWgtEntity;
import com.example.slabdesign.store.sd.std.jpo.HrMaxWgtJpo;
import org.springframework.stereotype.Component;

@Component
public class HrMaxWgtLogic {

    public HrMaxWgtEntity toEntity(HrMaxWgtJpo jpo) {
        if (jpo == null) return null;
        HrMaxWgtEntity e = new HrMaxWgtEntity();
        e.setCmpCd(jpo.getCmpCd());
        e.setOrgCd(jpo.getOrgCd());
        e.setHrCd(jpo.getHrCd());
        e.setThickness(jpo.getThickness());
        e.setWidth(jpo.getWidth());
        e.setMaxWgt(jpo.getMaxWgt());
        return e;
    }
}
