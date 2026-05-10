package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Unit tests for {@link SdFirstWeightAction} (step 4: 1차 단중범위).
 *
 * Pure calculation — no service deps, no DG codes. Only normal path tests with
 * varied numerical inputs.
 */
class SdFirstWeightActionTest {

    private final SdFirstWeightAction action = new SdFirstWeightAction();

    @Test
    void normalCase_setsWeightRange() {
        SDSlabEntity slab = new SDSlabEntity();
        slab.setSlabThickness(new BigDecimal("250"));   // mm
        slab.setFirstWidthLow(new BigDecimal("1150"));  // mm
        slab.setFirstWidthHigh(new BigDecimal("1250")); // mm
        slab.setFirstLengthLow(new BigDecimal("6000")); // mm
        slab.setFirstLengthHigh(new BigDecimal("10000")); // mm

        SDOrderEntity order = new SDOrderEntity();
        order.setSpecificGravity(new BigDecimal("7.82"));

        action.execute(order, slab);

        // wgtLow = 250*1150*6000*7.82*1e-6 = 13,489.5 kg
        // wgtHigh = 250*1250*10000*7.82*1e-6 = 24,437.5 kg
        assertThat(slab.getFirstWgtLow()).isEqualByComparingTo("13489.5");
        assertThat(slab.getFirstWgtHigh()).isEqualByComparingTo("24437.5");
    }

    @Test
    void differentDensity_scalesProportionally() {
        SDSlabEntity slab = new SDSlabEntity();
        slab.setSlabThickness(new BigDecimal("200"));
        slab.setFirstWidthLow(new BigDecimal("1000"));
        slab.setFirstWidthHigh(new BigDecimal("1000"));
        slab.setFirstLengthLow(new BigDecimal("5000"));
        slab.setFirstLengthHigh(new BigDecimal("5000"));

        SDOrderEntity order = new SDOrderEntity();
        order.setSpecificGravity(new BigDecimal("8.00"));

        action.execute(order, slab);

        // 200*1000*5000*8.00*1e-6 = 8,000 kg
        assertThat(slab.getFirstWgtLow()).isEqualByComparingTo("8000.000000");
        assertThat(slab.getFirstWgtHigh()).isEqualByComparingTo("8000.000000");
    }
}
