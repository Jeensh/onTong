package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.feature.sd.process.working.wrapper.AlgorithmException;
import com.example.slabdesign.feature.sd.process.working.wrapper.SdErrorCode;
import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.math.MathContext;

/**
 * sd · working · step 12 + 13 통합 — 매수 +1 + slab 단중 재산정 + 검증.
 *
 *   step 12: 분할수고려 매수 +1
 *   step 13: slab단중 = 설계대기량상한 / 실수율 / 매수
 *            검증 1) 단중정합성: slab단중 ∈ [splitWgtLow, splitWgtHigh]
 *            검증 2) 설계대기량 정합성: slab단중 × 매수 ∈ 실수율고려 설계대기량 범위
 *            둘 다 만족 → step 15 success (slab.slabWgtInProgress + slabCountInProgress 갱신)
 *            하나라도 실패 → DG108 (A-a 외부 loop 으로 → split-1 retry)
 *
 *   user Q4 답변 반영: step 13 fail 시 step 14 (모드 변경) 없이 직접 A-a 외부 loop.
 */
@Component
public class SdSlabWgtRecalcAction {

    private static final int STEP_NO = 13;
    private static final String STEP_NAME = "SLAB_WGT_RECALC";

    public void execute(SDOrderEntity order, SDSlabEntity slab) {
        // step 12: 매수 +1
        int newCount = slab.getSlabCountInProgress() + 1;

        // step 13: slab단중 = 설계대기량상한 / 실수율 / 매수
        BigDecimal newSlabWgt = order.getDesignPendQtyHigh()
            .divide(order.getProductivity(), MathContext.DECIMAL64)
            .divide(BigDecimal.valueOf(newCount), MathContext.DECIMAL64);

        // 검증 1) 단중정합성
        boolean weightInRange = newSlabWgt.compareTo(slab.getSplitWgtLow()) >= 0
                             && newSlabWgt.compareTo(slab.getSplitWgtHigh()) <= 0;

        // 검증 2) 설계대기량 정합성 (실수율 고려)
        BigDecimal totalProduced = newSlabWgt.multiply(BigDecimal.valueOf(newCount));
        BigDecimal yieldAdjustedLow = order.getDesignPendQtyLow()
            .divide(order.getProductivity(), MathContext.DECIMAL64);
        BigDecimal yieldAdjustedHigh = order.getDesignPendQtyHigh()
            .divide(order.getProductivity(), MathContext.DECIMAL64);
        boolean pendQtySatisfied = totalProduced.compareTo(yieldAdjustedLow) >= 0
                                && totalProduced.compareTo(yieldAdjustedHigh) <= 0;

        if (!weightInRange || !pendQtySatisfied) {
            throw new AlgorithmException(STEP_NO, STEP_NAME, SdErrorCode.ALG_ITERATION_NEEDED,
                "step 13 fail — weightInRange=" + weightInRange
                    + ", pendQtySatisfied=" + pendQtySatisfied
                    + ", split=" + slab.getCurrentSplitCount()
                    + ", newCount=" + newCount + ", newSlabWgt=" + newSlabWgt);
        }

        // step 15 success: 결정값 set
        slab.setSlabCountInProgress(newCount);
        slab.setSlabWgtInProgress(newSlabWgt);
    }
}
