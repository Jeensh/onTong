package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Unit tests for {@link SdFinalLengthRangeAction} (step 17: 최종 길이범위).
 */
class SdFinalLengthRangeActionTest {

    private final SdFinalLengthRangeAction action = new SdFinalLengthRangeAction();

    @Test
    void normalCase_clampedToFirstRange() {
        SDOrderEntity order = new SDOrderEntity();
        order.setSpecificGravity(new BigDecimal("7.82"));

        SDSlabEntity slab = new SDSlabEntity();
        slab.setSlabWgtInProgress(new BigDecimal("20000"));
        slab.setSlabThickness(new BigDecimal("250"));
        slab.setFinalWidthLow(new BigDecimal("1024"));
        slab.setFinalWidthHigh(new BigDecimal("1705"));
        slab.setFirstLengthLow(new BigDecimal("6000"));
        slab.setFirstLengthHigh(new BigDecimal("10000"));

        action.execute(order, slab);

        // numerator = 2e10
        // lengthFromWidthHigh = 2e10 / (1705*250*7.82) ≈ 6000.106 → max with firstLow 6000 → 6000.106
        // lengthFromWidthLow = 2e10 / (1024*250*7.82) ≈ 9990.405 → min with firstHigh 10000 → 9990.405
        assertThat(slab.getFinalLengthLow()).isGreaterThanOrEqualTo(new BigDecimal("6000"));
        assertThat(slab.getFinalLengthHigh()).isLessThanOrEqualTo(new BigDecimal("10000"));
    }

    @Test
    void clampedHardByFirstRange() {
        // Case where computed range is wider than firstRange — clamped to firstRange.
        SDOrderEntity order = new SDOrderEntity();
        order.setSpecificGravity(new BigDecimal("7.82"));

        SDSlabEntity slab = new SDSlabEntity();
        slab.setSlabWgtInProgress(new BigDecimal("100000"));    // huge wgt
        slab.setSlabThickness(new BigDecimal("250"));
        slab.setFinalWidthLow(new BigDecimal("500"));            // narrow → length goes huge
        slab.setFinalWidthHigh(new BigDecimal("3000"));          // wide → length goes small
        slab.setFirstLengthLow(new BigDecimal("6000"));
        slab.setFirstLengthHigh(new BigDecimal("10000"));

        action.execute(order, slab);

        // lengthFromWidthHigh ≈ 1e11 / (3000*250*7.82) ≈ 17050 → max(17050, 6000) = 17050 (>= firstHigh, OK)
        // lengthFromWidthLow ≈ 1e11 / (500*250*7.82) ≈ 102301 → min(102301, 10000) = 10000
        assertThat(slab.getFinalLengthHigh()).isEqualByComparingTo("10000");
    }
}
