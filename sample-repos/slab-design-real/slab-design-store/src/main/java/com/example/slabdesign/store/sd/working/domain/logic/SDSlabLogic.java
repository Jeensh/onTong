package com.example.slabdesign.store.sd.working.domain.logic;

import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
import com.example.slabdesign.store.sd.working.oracle.jpo.SlabResultJpo;
import org.springframework.stereotype.Component;

/**
 * sd · working · 슬랩 도메인 변환 로직.
 *
 * SLAB_RESULT JPO ↔ SDSlabEntity 변환 (DB값 portion 만).
 * 작업용 필드는 변환 대상 외 — 알고리즘이 메모리에서 직접 set/get.
 *
 * SDOrderLogic 과 달리 1 JPO ↔ 1 Entity 단순 매핑이라 명시적 setter 사용 (리플렉션 불필요).
 */
@Component
public class SDSlabLogic {

    /**
     * SLAB_RESULT JPO → SDSlabEntity (DB값 채움). 작업용 필드는 null 로 초기화.
     */
    public SDSlabEntity toEntity(SlabResultJpo jpo) {
        if (jpo == null) return null;
        SDSlabEntity e = new SDSlabEntity();

        e.setCmpCd(jpo.getCmpCd());
        e.setOrgCd(jpo.getOrgCd());
        e.setSlabNo(jpo.getSlabNo());
        e.setOrderNo(jpo.getOrderNo());
        e.setConfirmedPlantCd(jpo.getConfirmedPlantCd());
        e.setPossiblePlantCd(jpo.getPossiblePlantCd());
        e.setSlabThickness(jpo.getSlabThickness());

        // 원본
        e.setSlabWidth(jpo.getSlabWidth());
        e.setSlabWidthHigh(jpo.getSlabWidthHigh());
        e.setSlabWidthLow(jpo.getSlabWidthLow());
        e.setSlabLength(jpo.getSlabLength());
        e.setSlabLengthHigh(jpo.getSlabLengthHigh());
        e.setSlabLengthLow(jpo.getSlabLengthLow());
        e.setSlabWgt(jpo.getSlabWgt());
        e.setSlabWgtHigh(jpo.getSlabWgtHigh());
        e.setSlabWgtLow(jpo.getSlabWgtLow());

        // 조정
        e.setSlabWidth1(jpo.getSlabWidth1());
        e.setSlabWidthHigh1(jpo.getSlabWidthHigh1());
        e.setSlabWidthLow1(jpo.getSlabWidthLow1());
        e.setSlabLength1(jpo.getSlabLength1());
        e.setSlabLengthHigh1(jpo.getSlabLengthHigh1());
        e.setSlabLengthLow1(jpo.getSlabLengthLow1());
        e.setSlabWgt1(jpo.getSlabWgt1());
        e.setSlabWgtHigh1(jpo.getSlabWgtHigh1());
        e.setSlabWgtLow1(jpo.getSlabWgtLow1());

        e.setSplitCount(jpo.getSplitCount());
        e.setCreatedAt(jpo.getCreatedAt());
        return e;
    }

    /**
     * SDSlabEntity → SLAB_RESULT JPO (DB값 portion 만 추출).
     * 작업용 필드는 영속 대상 X.
     */
    public SlabResultJpo toJpo(SDSlabEntity e) {
        if (e == null) return null;
        SlabResultJpo j = new SlabResultJpo();

        j.setCmpCd(e.getCmpCd());
        j.setOrgCd(e.getOrgCd());
        j.setSlabNo(e.getSlabNo());
        j.setOrderNo(e.getOrderNo());
        j.setConfirmedPlantCd(e.getConfirmedPlantCd());
        j.setPossiblePlantCd(e.getPossiblePlantCd());
        j.setSlabThickness(e.getSlabThickness());

        j.setSlabWidth(e.getSlabWidth());
        j.setSlabWidthHigh(e.getSlabWidthHigh());
        j.setSlabWidthLow(e.getSlabWidthLow());
        j.setSlabLength(e.getSlabLength());
        j.setSlabLengthHigh(e.getSlabLengthHigh());
        j.setSlabLengthLow(e.getSlabLengthLow());
        j.setSlabWgt(e.getSlabWgt());
        j.setSlabWgtHigh(e.getSlabWgtHigh());
        j.setSlabWgtLow(e.getSlabWgtLow());

        j.setSlabWidth1(e.getSlabWidth1());
        j.setSlabWidthHigh1(e.getSlabWidthHigh1());
        j.setSlabWidthLow1(e.getSlabWidthLow1());
        j.setSlabLength1(e.getSlabLength1());
        j.setSlabLengthHigh1(e.getSlabLengthHigh1());
        j.setSlabLengthLow1(e.getSlabLengthLow1());
        j.setSlabWgt1(e.getSlabWgt1());
        j.setSlabWgtHigh1(e.getSlabWgtHigh1());
        j.setSlabWgtLow1(e.getSlabWgtLow1());

        j.setSplitCount(e.getSplitCount());
        j.setCreatedAt(e.getCreatedAt());
        return j;
    }
}
