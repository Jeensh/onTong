package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Unit tests for {@link SdFinalWidthRangeAction} (step 16: 최종 폭범위).
 */
class SdFinalWidthRangeActionTest {

    private final SdFinalWidthRangeAction action = new SdFinalWidthRangeAction();

    @Test
    void normalCase_setsFinalWidthRange() {
        SDOrderEntity order = new SDOrderEntity();
        order.setSpecificGravity(new BigDecimal("7.82"));

        SDSlabEntity slab = new SDSlabEntity();
        slab.setSlabWgtInProgress(new BigDecimal("20000")); // kg
        slab.setSlabThickness(new BigDecimal("250"));        // mm
        slab.setFirstLengthLow(new BigDecimal("6000"));      // mm
        slab.setFirstLengthHigh(new BigDecimal("10000"));    // mm

        action.execute(order, slab);

        // numerator = 20000 * 1e6 = 2e10
        // widthLow = ceil(2e10 / (10000 * 250 * 7.82)) = ceil(1023.018...) = 1024
        // widthHigh = floor(2e10 / (6000 * 250 * 7.82)) = floor(1705.030...) = 1705
        assertThat(slab.getFinalWidthLow()).isEqualByComparingTo("1024");
        assertThat(slab.getFinalWidthHigh()).isEqualByComparingTo("1705");
    }

    @Test
    void widthLowAlwaysCeilingWidthHighAlwaysFloor() {
        SDOrderEntity order = new SDOrderEntity();
        order.setSpecificGravity(new BigDecimal("8.0"));

        SDSlabEntity slab = new SDSlabEntity();
        slab.setSlabWgtInProgress(new BigDecimal("16000"));
        slab.setSlabThickness(new BigDecimal("200"));
        slab.setFirstLengthLow(new BigDecimal("5000"));
        slab.setFirstLengthHigh(new BigDecimal("8000"));

        action.execute(order, slab);

        // numerator = 16000 * 1e6 = 1.6e10
        // widthLow = ceil(1.6e10 / (8000*200*8.0)) = ceil(1250) = 1250 (exact integer)
        // widthHigh = floor(1.6e10 / (5000*200*8.0)) = floor(2000) = 2000
        assertThat(slab.getFinalWidthLow()).isEqualByComparingTo("1250");
        assertThat(slab.getFinalWidthHigh()).isEqualByComparingTo("2000");
    }
}
