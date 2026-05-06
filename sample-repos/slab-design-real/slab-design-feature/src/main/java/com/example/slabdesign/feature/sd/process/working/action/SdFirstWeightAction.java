package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;

/**
 * sd · working · step 4: 1차 설계가능 단중범위 산정.
 *
 *   단중하한 = 1차두께 × 1차폭하한 × 1차길이하한 × 비중
 *   단중상한 = 1차두께 × 1차폭상한 × 1차길이상한 × 비중
 *
 * 단위 변환: thickness/width/length(mm) × density(g/cm³) → kg
 *   mm³ × g/cm³ × 1e-6 = kg
 *
 * 순수 계산 — 외부 룩업 없음. fail 케이스 없음.
 */
@Component
public class SdFirstWeightAction {

    /** mm³ × g/cm³ → kg 변환 인자. */
    private static final BigDecimal UNIT_FACTOR = new BigDecimal("0.000001");

    public void execute(SDOrderEntity order, SDSlabEntity slab) {
        BigDecimal thickness = slab.getSlabThickness();
        BigDecimal density = order.getSpecificGravity();

        BigDecimal wgtLow = thickness
            .multiply(slab.getFirstWidthLow())
            .multiply(slab.getFirstLengthLow())
            .multiply(density)
            .multiply(UNIT_FACTOR);

        BigDecimal wgtHigh = thickness
            .multiply(slab.getFirstWidthHigh())
            .multiply(slab.getFirstLengthHigh())
            .multiply(density)
            .multiply(UNIT_FACTOR);

        slab.setFirstWgtLow(wgtLow);
        slab.setFirstWgtHigh(wgtHigh);
    }
}
