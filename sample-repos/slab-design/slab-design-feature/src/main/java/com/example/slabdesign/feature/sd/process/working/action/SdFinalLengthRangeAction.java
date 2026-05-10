package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.math.MathContext;

/**
 * sd · working · step 17: 최종 slab 길이 범위 산정.
 *
 *   slab길이하한 = max((slab단중 / (최종폭상한 × 두께 × 비중)), 1차길이하한)
 *   slab길이상한 = min((slab단중 / (최종폭하한 × 두께 × 비중)), 1차길이상한)
 */
@Component
public class SdFinalLengthRangeAction {

    private static final BigDecimal INVERSE_UNIT = new BigDecimal("1000000");

    public void execute(SDOrderEntity order, SDSlabEntity slab) {
        BigDecimal slabWgt = slab.getSlabWgtInProgress();
        BigDecimal thickness = slab.getSlabThickness();
        BigDecimal density = order.getSpecificGravity();

        BigDecimal numerator = slabWgt.multiply(INVERSE_UNIT);

        BigDecimal lengthFromWidthHigh = numerator.divide(
            slab.getFinalWidthHigh().multiply(thickness).multiply(density),
            MathContext.DECIMAL64);
        BigDecimal lengthFromWidthLow = numerator.divide(
            slab.getFinalWidthLow().multiply(thickness).multiply(density),
            MathContext.DECIMAL64);

        BigDecimal lengthLow = lengthFromWidthHigh.max(slab.getFirstLengthLow());
        BigDecimal lengthHigh = lengthFromWidthLow.min(slab.getFirstLengthHigh());

        slab.setFinalLengthLow(lengthLow);
        slab.setFinalLengthHigh(lengthHigh);
    }
}
