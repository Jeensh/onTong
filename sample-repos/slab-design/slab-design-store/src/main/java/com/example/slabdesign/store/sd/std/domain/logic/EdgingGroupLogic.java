package com.example.slabdesign.store.sd.std.domain.logic;

import com.example.slabdesign.store.sd.std.domain.entity.EdgingGroupEntity;
import com.example.slabdesign.store.sd.std.oracle.jpo.EdgingGroupJpo;
import org.springframework.stereotype.Component;

/**
 * sd · std · EDGING_GROUP JPO ↔ Entity 변환.
 */
@Component
public class EdgingGroupLogic {

    public EdgingGroupEntity toEntity(EdgingGroupJpo jpo) {
        if (jpo == null) return null;
        EdgingGroupEntity e = new EdgingGroupEntity();
        e.setCmpCd(jpo.getCmpCd());
        e.setOrgCd(jpo.getOrgCd());
        e.setPriority(jpo.getPriority());
        e.setEdgingGroupCd(jpo.getEdgingGroupCd());
        e.setGradeCd(jpo.getGradeCd());
        e.setProductTypeCd(jpo.getProductTypeCd());
        e.setCustomerCd(jpo.getCustomerCd());
        e.setHrTgtWidthHigh(jpo.getHrTgtWidthHigh());
        e.setHrTgtWidthLow(jpo.getHrTgtWidthLow());
        return e;
    }
}
