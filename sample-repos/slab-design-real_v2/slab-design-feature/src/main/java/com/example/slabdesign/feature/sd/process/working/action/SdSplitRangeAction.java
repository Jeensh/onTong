package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.feature.sd.process.working.wrapper.AlgorithmException;
import com.example.slabdesign.feature.sd.process.working.wrapper.SdErrorCode;
import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.math.MathContext;

/**
 * sd · working · step 8: 분할수 고려 단중 범위 + 최적 분할수 계산.
 *
 *   주문단중 범위 (실수율 고려) = (orderWgtLow / productivity) ~ (orderWgtHigh / productivity)
 *   × currentSplitCount 적용한 범위
 *   ∩ 2차 slab단중 범위 (secondWgtLow ~ secondWgtHigh)
 *
 *   splitWgtLow  = max(orderWgtLow  × split / productivity, secondWgtLow)
 *   splitWgtHigh = min(orderWgtHigh × split / productivity, secondWgtHigh)
 *
 *   최적분할수 = currentSplitCount (slab단중 최대화 목적식 — Q3 답변에 따라 단일 모드).
 *
 * splitWgtLow > splitWgtHigh (공통 범위 없음) → DG108 (P2.2.D 에서 iteration 처리 예정).
 */
@Component
public class SdSplitRangeAction {

    private static final int STEP_NO = 8;
    private static final String STEP_NAME = "SPLIT_RANGE";

    public void execute(SDOrderEntity order, SDSlabEntity slab) {
        BigDecimal split = BigDecimal.valueOf(slab.getCurrentSplitCount());
        BigDecimal productivity = order.getProductivity();

        BigDecimal orderRangeLow = order.getOrderWgtLow()
            .multiply(split)
            .divide(productivity, MathContext.DECIMAL64);
        BigDecimal orderRangeHigh = order.getOrderWgtHigh()
            .multiply(split)
            .divide(productivity, MathContext.DECIMAL64);

        BigDecimal splitWgtLow = orderRangeLow.max(slab.getSecondWgtLow());
        BigDecimal splitWgtHigh = orderRangeHigh.min(slab.getSecondWgtHigh());

        if (splitWgtLow.compareTo(splitWgtHigh) > 0) {
            throw new AlgorithmException(STEP_NO, STEP_NAME, SdErrorCode.ALG_ITERATION_NEEDED,
                "분할수=" + slab.getCurrentSplitCount() + " 에서 공통 단중범위 없음"
                    + " (splitLow=" + splitWgtLow + " > splitHigh=" + splitWgtHigh + ")");
        }

        slab.setOptimalSplitCount(slab.getCurrentSplitCount()); // 단일 목적식 — current 가 곧 optimal
        slab.setSplitWgtLow(splitWgtLow);
        slab.setSplitWgtHigh(splitWgtHigh);
    }
}
