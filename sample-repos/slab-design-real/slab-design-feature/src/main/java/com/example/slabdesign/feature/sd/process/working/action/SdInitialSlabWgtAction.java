package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.feature.sd.process.working.wrapper.AlgorithmException;
import com.example.slabdesign.feature.sd.process.working.wrapper.SdErrorCode;
import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.math.MathContext;

/**
 * sd · working · step 10: 분할수 고려 slab 단중 산정 + 설계대기량 만족 점검.
 *
 *   slab단중 = 분할수고려단중범위상한 (= splitWgtHigh)
 *   분기) 설계대기량 만족? = (slab단중 × 매수) ∈ 실수율고려 설계대기량 범위
 *     실수율고려 설계대기량 범위 = (designPendQtyLow / productivity) ~ (designPendQtyHigh / productivity)
 *
 *   YES → 그대로 통과 → step 11 (decided values 는 이미 set 되어 있음)
 *   NO  → DG108 (P2.2.D 에서 iteration: step 12 매수+1, step 13 재산정)
 *
 * NOTE: P2.2.C 는 1 iteration 만. 분기 NO 는 P2.2.D 에서 step 12-15 추가 후 처리.
 */
@Component
public class SdInitialSlabWgtAction {

    private static final int STEP_NO = 10;
    private static final String STEP_NAME = "INITIAL_SLAB_WGT";

    public void execute(SDOrderEntity order, SDSlabEntity slab) {
        BigDecimal slabWgt = slab.getSplitWgtHigh();
        slab.setSlabWgtInProgress(slabWgt);

        BigDecimal slabCount = BigDecimal.valueOf(slab.getSlabCountInProgress());
        BigDecimal totalProduced = slabWgt.multiply(slabCount); // slab단중 × 매수

        // 실수율고려 설계대기량 범위
        BigDecimal yieldAdjustedPendLow = order.getDesignPendQtyLow()
            .divide(order.getProductivity(), MathContext.DECIMAL64);
        BigDecimal yieldAdjustedPendHigh = order.getDesignPendQtyHigh()
            .divide(order.getProductivity(), MathContext.DECIMAL64);

        boolean satisfies = totalProduced.compareTo(yieldAdjustedPendLow) >= 0
                         && totalProduced.compareTo(yieldAdjustedPendHigh) <= 0;

        if (!satisfies) {
            throw new AlgorithmException(STEP_NO, STEP_NAME, SdErrorCode.ALG_ITERATION_NEEDED,
                "step 10 NO branch — 분할수=" + slab.getCurrentSplitCount()
                    + ", totalProduced=" + totalProduced
                    + ", 실수율고려 설계대기량 범위=[" + yieldAdjustedPendLow + ", " + yieldAdjustedPendHigh + "]"
                    + " — P2.2.D 에서 iteration 처리 예정");
        }
        // YES branch — step 11 효과: slabWgtInProgress + slabCountInProgress 가 결정값.
        // splitWgtLow/High 는 이미 step 8 에서 set.
    }
}
