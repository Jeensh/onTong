package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.feature.sd.process.working.wrapper.AlgorithmException;
import com.example.slabdesign.feature.sd.process.working.wrapper.SdErrorCode;
import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.math.MathContext;
import java.math.RoundingMode;

/**
 * sd · working · step 9: 분할수 고려 slab 매수 산정.
 *
 *   매수 = floor(설계대기량상한 / 실수율 / 분할수고려단중범위상한)
 *        = floor(designPendQtyHigh / productivity / splitWgtHigh)
 *
 * 매수 < 1 (이론상 가능) → DG108 (iteration 필요).
 */
@Component
public class SdSlabCountAction {

    private static final int STEP_NO = 9;
    private static final String STEP_NAME = "SLAB_COUNT";

    public void execute(SDOrderEntity order, SDSlabEntity slab) {
        BigDecimal raw = order.getDesignPendQtyHigh()
            .divide(order.getProductivity(), MathContext.DECIMAL64)
            .divide(slab.getSplitWgtHigh(), MathContext.DECIMAL64);

        int slabCount = raw.setScale(0, RoundingMode.FLOOR).intValueExact();

        if (slabCount < 1) {
            throw new AlgorithmException(STEP_NO, STEP_NAME, SdErrorCode.ALG_ITERATION_NEEDED,
                "분할수=" + slab.getCurrentSplitCount() + " 에서 매수 < 1 (raw=" + raw + ")");
        }

        slab.setSlabCountInProgress(slabCount);
    }
}
