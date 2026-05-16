package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.math.MathContext;
import java.math.RoundingMode;

/**
 * sd · working · step 19: 목표 slab 길이 계산.
 *
 *   목표slab길이 = (1단위 내림) slabWgtInProgress × 1e6 / (목표slab폭 × 두께 × 비중)
 */
@Component
public class SdTargetLengthAction {

    private static final BigDecimal INVERSE_UNIT = new BigDecimal("1000000");

    public void execute(SDOrderEntity order, SDSlabEntity slab) {
        BigDecimal density = order.getSpecificGravity();
        BigDecimal thickness = slab.getSlabThickness();

        BigDecimal raw = slab.getSlabWgtInProgress().multiply(INVERSE_UNIT)
            .divide(slab.getTargetSlabWidth().multiply(thickness).multiply(density),
                MathContext.DECIMAL64);

        BigDecimal floored = raw.setScale(0, RoundingMode.FLOOR);
        slab.setTargetSlabLength(floored);
    }
}
