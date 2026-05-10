package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.math.MathContext;
import java.math.RoundingMode;

/**
 * sd · working · step 16: 최종 slab 폭 범위 산정.
 *
 *   slab폭하한 = ceil(slab단중 / (1차길이상한 × 두께 × 비중))    [1자리 올림]
 *   slab폭상한 = floor(slab단중 / (1차길이하한 × 두께 × 비중))   [1자리 내림]
 *
 * slab단중 = slabWgtInProgress (step 11/15 결정값).
 * 단위: kg / (mm × mm × g/cm³) = mm × 1e6 → ÷ 1e-6 = mm (즉 분자에 ×1e6).
 */
@Component
public class SdFinalWidthRangeAction {

    /** 1 / unit_factor (= 1e6) — kg / (mm² × g/cm³) → mm 변환 시 분자 multiplier. */
    private static final BigDecimal INVERSE_UNIT = new BigDecimal("1000000");

    public void execute(SDOrderEntity order, SDSlabEntity slab) {
        BigDecimal slabWgt = slab.getSlabWgtInProgress();
        BigDecimal thickness = slab.getSlabThickness();
        BigDecimal density = order.getSpecificGravity();

        BigDecimal numerator = slabWgt.multiply(INVERSE_UNIT);

        BigDecimal denomLow = slab.getFirstLengthHigh().multiply(thickness).multiply(density);
        BigDecimal widthLow = numerator.divide(denomLow, MathContext.DECIMAL64)
            .setScale(0, RoundingMode.CEILING);

        BigDecimal denomHigh = slab.getFirstLengthLow().multiply(thickness).multiply(density);
        BigDecimal widthHigh = numerator.divide(denomHigh, MathContext.DECIMAL64)
            .setScale(0, RoundingMode.FLOOR);

        slab.setFinalWidthLow(widthLow);
        slab.setFinalWidthHigh(widthHigh);
    }
}
