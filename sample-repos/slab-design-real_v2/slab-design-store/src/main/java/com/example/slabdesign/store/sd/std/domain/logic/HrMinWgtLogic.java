package com.example.slabdesign.store.sd.std.domain.logic;

import com.example.slabdesign.store.sd.std.domain.entity.HrMinWgtEntity;
import com.example.slabdesign.store.sd.std.jpo.HrMinWgtJpo;
import org.springframework.stereotype.Component;

@Component
public class HrMinWgtLogic {

    public HrMinWgtEntity toEntity(HrMinWgtJpo jpo) {
        if (jpo == null) return null;
        HrMinWgtEntity e = new HrMinWgtEntity();
        e.setCmpCd(jpo.getCmpCd());
        e.setOrgCd(jpo.getOrgCd());
        e.setHrCd(jpo.getHrCd());
        e.setThickness(jpo.getThickness());
        e.setWidth(jpo.getWidth());
        e.setMinWgt(jpo.getMinWgt());
        return e;
    }
}
