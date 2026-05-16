package com.example.slabdesign.store.sd.std.domain.logic;

import com.example.slabdesign.store.sd.std.domain.entity.CastSpecEntity;
import com.example.slabdesign.store.sd.std.jpo.CastSpecJpo;
import org.springframework.stereotype.Component;

/**
 * sd · std · CAST_SPEC JPO ↔ Entity 변환.
 * 1:1 미러이므로 명시적 setter 호출 (std 는 단순 lookup, 리플렉션 불필요).
 */
@Component
public class CastSpecLogic {

    public CastSpecEntity toEntity(CastSpecJpo jpo) {
        if (jpo == null) return null;
        CastSpecEntity e = new CastSpecEntity();
        e.setCmpCd(jpo.getCmpCd());
        e.setOrgCd(jpo.getOrgCd());
        e.setSmCd(jpo.getSmCd());
        e.setCastCd(jpo.getCastCd());
        e.setMachineCd(jpo.getMachineCd());
        e.setProductCd(jpo.getProductCd());
        e.setSlabThickness(jpo.getSlabThickness());
        e.setWidthLow(jpo.getWidthLow());
        e.setWidthHigh(jpo.getWidthHigh());
        e.setLengthLow(jpo.getLengthLow());
        e.setLengthHigh(jpo.getLengthHigh());
        e.setWgtLow(jpo.getWgtLow());
        e.setWgtHigh(jpo.getWgtHigh());
        return e;
    }
}
