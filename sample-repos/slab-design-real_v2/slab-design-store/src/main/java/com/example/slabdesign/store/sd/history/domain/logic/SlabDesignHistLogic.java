package com.example.slabdesign.store.sd.history.domain.logic;

import com.example.slabdesign.store.sd.history.domain.entity.SlabDesignHistEntity;
import com.example.slabdesign.store.sd.history.jpo.SlabDesignHistJpo;
import org.springframework.stereotype.Component;

/**
 * sd · history · SLAB_DESIGN_HIST JPO ↔ Entity 변환.
 */
@Component
public class SlabDesignHistLogic {

    public SlabDesignHistEntity toEntity(SlabDesignHistJpo jpo) {
        if (jpo == null) return null;
        SlabDesignHistEntity e = new SlabDesignHistEntity();
        e.setCmpCd(jpo.getCmpCd());
        e.setOrgCd(jpo.getOrgCd());
        e.setHistId(jpo.getHistId());
        e.setOrderNo(jpo.getOrderNo());
        e.setSlabNo(jpo.getSlabNo());
        e.setStepNo(jpo.getStepNo());
        e.setStepName(jpo.getStepName());
        e.setErrorCode(jpo.getErrorCode());
        e.setSnapshot(jpo.getSnapshot());
        e.setEventTime(jpo.getEventTime());
        return e;
    }

    public SlabDesignHistJpo toJpo(SlabDesignHistEntity e) {
        if (e == null) return null;
        SlabDesignHistJpo j = new SlabDesignHistJpo();
        j.setCmpCd(e.getCmpCd());
        j.setOrgCd(e.getOrgCd());
        j.setHistId(e.getHistId());
        j.setOrderNo(e.getOrderNo());
        j.setSlabNo(e.getSlabNo());
        j.setStepNo(e.getStepNo());
        j.setStepName(e.getStepName());
        j.setErrorCode(e.getErrorCode());
        j.setSnapshot(e.getSnapshot());
        j.setEventTime(e.getEventTime());
        return j;
    }
}
