package com.example.slabdesign.store.sd.std.domain.logic;

import com.example.slabdesign.store.sd.std.domain.entity.HrSpecEntity;
import com.example.slabdesign.store.sd.std.oracle.jpo.HrSpecJpo;
import org.springframework.stereotype.Component;

/**
 * sd · std · HR_SPEC JPO ↔ Entity 변환.
 */
@Component
public class HrSpecLogic {

    public HrSpecEntity toEntity(HrSpecJpo jpo) {
        if (jpo == null) return null;
        HrSpecEntity e = new HrSpecEntity();
        e.setCmpCd(jpo.getCmpCd());
        e.setOrgCd(jpo.getOrgCd());
        e.setHrPlantCd(jpo.getHrPlantCd());
        e.setProductTypeCd(jpo.getProductTypeCd());
        e.setWidthLow(jpo.getWidthLow());
        e.setWidthHigh(jpo.getWidthHigh());
        e.setLengthLow(jpo.getLengthLow());
        e.setLengthHigh(jpo.getLengthHigh());
        return e;
    }
}
