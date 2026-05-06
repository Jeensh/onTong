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
 * sd · working · step 7: 최대분할수 산정 + A-a 루프 시작점 설정.
 *
 *   최대분할수상한 = ceil(2차설계가능단중상한 / 주문단중상한 / 실수율)
 *
 * A-a 루프는 currentSplitCount 가 maxSplitCountUpper 부터 1 씩 감소.
 * 루프 자체는 P2.2.D 에서 도입.
 *
 * 산정 결과 ≤ 0 이면 알고리즘 fail (DG108 임시 코드).
 */
@Component
public class SdMaxSplitCountAction {

    private static final int STEP_NO = 7;
    private static final String STEP_NAME = "MAX_SPLIT_COUNT";

    public void execute(SDOrderEntity order, SDSlabEntity slab) {
        // ceil(secondWgtHigh / orderWgtHigh / productivity)
        BigDecimal raw = slab.getSecondWgtHigh()
            .divide(order.getOrderWgtHigh(), MathContext.DECIMAL64)
            .divide(order.getProductivity(), MathContext.DECIMAL64);

        int maxSplit = raw.setScale(0, RoundingMode.CEILING).intValueExact();

        if (maxSplit < 1) {
            throw new AlgorithmException(STEP_NO, STEP_NAME, SdErrorCode.ALG_ITERATION_NEEDED,
                "최대분할수상한 < 1 (raw=" + raw + ") — 분할 불가");
        }

        slab.setMaxSplitCountUpper(maxSplit);
        slab.setCurrentSplitCount(maxSplit); // A-a 루프 시작점
    }
}
