package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.feature.sd.process.working.service.SlabNoSequence;
import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
import com.example.slabdesign.store.sd.working.domain.logic.SDSlabLogic;
import com.example.slabdesign.store.sd.working.jpo.SlabResultJpo;
import com.example.slabdesign.store.sd.working.repository.SlabResultRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

/**
 * sd · working · step 20: SLAB_RESULT 저장.
 *
 *   알고리즘 결정값을 SLAB_RESULT 컬럼에 매핑:
 *     - 원본 (no suffix) + 조정 (_1) 모두 동일 값으로 set (알고리즘 직후 — 추후 사이즈 조정 시 _1 만 갱신)
 *     - SLAB_THICKNESS, SLAB_WIDTH/LENGTH/WGT (+ HIGH/LOW)
 *     - SPLIT_COUNT, CREATED_AT
 *
 *   매수 (slabCountInProgress) 만큼 row 저장:
 *     - 1번째 row: SDSlab.slabNo (Designer 가 createInitialSlab 시 pre-generate)
 *     - 2~매수번째 row: SlabNoSequence.next() 로 추가 발급
 *     - 모든 row: 동일 도메인값 + 다른 SLAB_NO
 */
@Component
public class SdSlabSaveAction {

    private final SlabResultRepository repository;
    private final SDSlabLogic logic;
    private final SlabNoSequence slabNoSequence;

    @Autowired
    public SdSlabSaveAction(SlabResultRepository repository, SDSlabLogic logic,
                            SlabNoSequence slabNoSequence) {
        this.repository = repository;
        this.logic = logic;
        this.slabNoSequence = slabNoSequence;
    }

    /**
     * @return 저장된 SLAB_NO 리스트 (매수개).
     */
    @Transactional
    public List<String> execute(SDOrderEntity order, SDSlabEntity slab) {
        applyAlgorithmResultsToFinalFields(slab);
        slab.setCreatedAt(LocalDateTime.now());

        int count = slab.getSlabCountInProgress();
        List<String> savedSlabNos = new ArrayList<>(count);

        for (int i = 0; i < count; i++) {
            String slabNo = (i == 0) ? slab.getSlabNo() : slabNoSequence.next();
            slab.setSlabNo(slabNo);
            SlabResultJpo jpo = logic.toJpo(slab);
            repository.save(jpo);
            savedSlabNos.add(slabNo);
        }

        // 마지막 저장된 slabNo 가 SDSlab 의 현재 값 — Designer 의 hist 적재 시 사용 가능
        return savedSlabNos;
    }

    /**
     * 알고리즘 결정값을 SLAB_RESULT 컬럼 (원본 + _1 모두) 으로 복사.
     * 알고리즘 직후 = 원본 = 조정. 추후 사이즈 조정 시 _1 만 갱신될 자리.
     */
    private void applyAlgorithmResultsToFinalFields(SDSlabEntity slab) {
        // 폭
        slab.setSlabWidth(slab.getTargetSlabWidth());
        slab.setSlabWidth1(slab.getTargetSlabWidth());
        slab.setSlabWidthHigh(slab.getFinalWidthHigh());
        slab.setSlabWidthHigh1(slab.getFinalWidthHigh());
        slab.setSlabWidthLow(slab.getFinalWidthLow());
        slab.setSlabWidthLow1(slab.getFinalWidthLow());
        // 길이
        slab.setSlabLength(slab.getTargetSlabLength());
        slab.setSlabLength1(slab.getTargetSlabLength());
        slab.setSlabLengthHigh(slab.getFinalLengthHigh());
        slab.setSlabLengthHigh1(slab.getFinalLengthHigh());
        slab.setSlabLengthLow(slab.getFinalLengthLow());
        slab.setSlabLengthLow1(slab.getFinalLengthLow());
        // 단중
        slab.setSlabWgt(slab.getSlabWgtInProgress());
        slab.setSlabWgt1(slab.getSlabWgtInProgress());
        slab.setSlabWgtHigh(slab.getSplitWgtHigh());
        slab.setSlabWgtHigh1(slab.getSplitWgtHigh());
        slab.setSlabWgtLow(slab.getSplitWgtLow());
        slab.setSlabWgtLow1(slab.getSplitWgtLow());
        // 분할수
        slab.setSplitCount(slab.getOptimalSplitCount());
    }
}
