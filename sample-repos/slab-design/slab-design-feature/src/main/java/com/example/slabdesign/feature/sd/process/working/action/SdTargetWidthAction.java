package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.math.MathContext;
import java.math.RoundingMode;

/**
 * sd · working · step 18: 목표 slab 폭 계산.
 *
 *   목표slab폭 = (10mm 단위 올림) splitWgtHigh × 1e6 / (최종길이상한 × 두께 × 비중)
 *
 *   계산값이 최종폭범위 [finalWidthLow, finalWidthHigh] 벗어나면
 *     → 목표slab폭 = finalWidthLow (사용자 사양)
 */
@Component
public class SdTargetWidthAction {

    private static final BigDecimal INVERSE_UNIT = new BigDecimal("1000000");
    private static final BigDecimal TEN_MM = BigDecimal.TEN;

    public void execute(SDOrderEntity order, SDSlabEntity slab) {
        BigDecimal density = order.getSpecificGravity();
        BigDecimal thickness = slab.getSlabThickness();

        BigDecimal raw = slab.getSplitWgtHigh().multiply(INVERSE_UNIT)
            .divide(slab.getFinalLengthHigh().multiply(thickness).multiply(density),
                MathContext.DECIMAL64);

        // 10mm 단위 올림: ceil(raw / 10) × 10
        BigDecimal rounded = raw.divide(TEN_MM, 0, RoundingMode.CEILING).multiply(TEN_MM);

        BigDecimal target;
        if (rounded.compareTo(slab.getFinalWidthLow()) < 0
         || rounded.compareTo(slab.getFinalWidthHigh()) > 0) {
            target = slab.getFinalWidthLow();
        } else {
            target = rounded;
        }
        slab.setTargetSlabWidth(target);
    }
}
