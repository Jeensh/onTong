package com.example.slabdesign.store.sd.std.domain.logic;

import com.example.slabdesign.store.sd.std.domain.entity.EdgingSpecEntity;
import com.example.slabdesign.store.sd.std.jpo.EdgingSpecJpo;
import org.springframework.stereotype.Component;

/**
 * sd · std · EDGING_SPEC JPO ↔ Entity 변환.
 */
@Component
public class EdgingSpecLogic {

    public EdgingSpecEntity toEntity(EdgingSpecJpo jpo) {
        if (jpo == null) return null;
        EdgingSpecEntity e = new EdgingSpecEntity();
        e.setCmpCd(jpo.getCmpCd());
        e.setOrgCd(jpo.getOrgCd());
        e.setEdgingGroupCd(jpo.getEdgingGroupCd());
        e.setEdgingCapLow(jpo.getEdgingCapLow());
        e.setEdgingCapHigh(jpo.getEdgingCapHigh());
        return e;
    }
}
