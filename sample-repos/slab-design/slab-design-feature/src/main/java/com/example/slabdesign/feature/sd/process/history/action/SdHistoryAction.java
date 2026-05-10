package com.example.slabdesign.feature.sd.process.history.action;

import com.example.slabdesign.feature.sd.process.working.wrapper.ValidationResult;
import com.example.slabdesign.store.sd.history.domain.entity.SlabDesignHistEntity;
import com.example.slabdesign.store.sd.history.domain.logic.SlabDesignHistLogic;
import com.example.slabdesign.store.sd.history.oracle.repository.SlabDesignHistRepository;
import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * sd · history · 설계 과정 이력 적재 액션.
 *
 * 세 종류 적재:
 *   1) recordValidationFailure — Phase 1 정합성 점검 실패 (slab_no=NULL, errorCode 채움)
 *   2) recordStep — 알고리즘 단계 실행 성공 (P2.2 이후 활용)
 *   3) recordAlgorithmFailure — 알고리즘 실패 (slab_no=NULL, errorCode 채움)
 *
 * 모든 이력은 SLAB_DESIGN_HIST 단일 테이블에 적재.
 */
@Component
public class SdHistoryAction {

    private final SlabDesignHistRepository repository;
    private final SlabDesignHistLogic logic;

    @Autowired
    public SdHistoryAction(SlabDesignHistRepository repository, SlabDesignHistLogic logic) {
        this.repository = repository;
        this.logic = logic;
    }

    /**
     * 정합성 점검 실패 이력 적재. SLAB_RESULT 미저장 케이스.
     * step_no = 0 (Phase 1 — 알고리즘 시작 전 검증), slab_no = NULL.
     */
    @Transactional
    public void recordValidationFailure(SDOrderEntity order, ValidationResult result) {
        SlabDesignHistEntity hist = new SlabDesignHistEntity();
        hist.setCmpCd(order.getCmpCd());
        hist.setOrgCd(order.getOrgCd());
        hist.setHistId(generateHistId());
        hist.setOrderNo(order.getOrderNo());
        hist.setSlabNo(null);                               // FAIL — slab 미생성
        hist.setStepNo(0);                                  // Phase 1 = step 0
        hist.setStepName("VALIDATION_FAILED");
        hist.setErrorCode(result.getErrorCode());
        hist.setSnapshot(result.getMessage());              // 메시지를 snapshot 으로 저장
        hist.setEventTime(LocalDateTime.now());
        repository.save(logic.toJpo(hist));
    }

    /**
     * 알고리즘 단계 실행 이력 (성공). P2.2 이후 활용.
     */
    @Transactional
    public void recordStep(SDOrderEntity order, String slabNo, int stepNo, String stepName, String snapshotJson) {
        SlabDesignHistEntity hist = new SlabDesignHistEntity();
        hist.setCmpCd(order.getCmpCd());
        hist.setOrgCd(order.getOrgCd());
        hist.setHistId(generateHistId());
        hist.setOrderNo(order.getOrderNo());
        hist.setSlabNo(slabNo);
        hist.setStepNo(stepNo);
        hist.setStepName(stepName);
        hist.setErrorCode(null);
        hist.setSnapshot(snapshotJson);
        hist.setEventTime(LocalDateTime.now());
        repository.save(logic.toJpo(hist));
    }

    /**
     * 알고리즘 단계 실패 이력. SLAB_RESULT 미저장.
     */
    @Transactional
    public void recordAlgorithmFailure(SDOrderEntity order, int stepNo, String stepName,
                                       String errorCode, String snapshotJson) {
        SlabDesignHistEntity hist = new SlabDesignHistEntity();
        hist.setCmpCd(order.getCmpCd());
        hist.setOrgCd(order.getOrgCd());
        hist.setHistId(generateHistId());
        hist.setOrderNo(order.getOrderNo());
        hist.setSlabNo(null);
        hist.setStepNo(stepNo);
        hist.setStepName(stepName);
        hist.setErrorCode(errorCode);
        hist.setSnapshot(snapshotJson);
        hist.setEventTime(LocalDateTime.now());
        repository.save(logic.toJpo(hist));
    }

    /** 단순 UUID 기반 이력 ID. 추후 시퀀스 또는 타임스탬프+counter 로 교체 가능. */
    private String generateHistId() {
        return UUID.randomUUID().toString().replace("-", "").substring(0, 30);
    }
}
