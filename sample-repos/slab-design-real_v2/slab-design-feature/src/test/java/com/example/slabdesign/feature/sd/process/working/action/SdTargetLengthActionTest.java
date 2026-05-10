package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Unit tests for {@link SdTargetLengthAction} (step 19: 목표 길이, 1mm 내림).
 */
class SdTargetLengthActionTest {

    private final SdTargetLengthAction action = new SdTargetLengthAction();

    @Test
    void normalCase_setsTargetLengthFloored() {
        SDOrderEntity order = new SDOrderEntity();
        order.setSpecificGravity(new BigDecimal("7.82"));

        SDSlabEntity slab = new SDSlabEntity();
        slab.setSlabWgtInProgress(new BigDecimal("20000"));
        slab.setSlabThickness(new BigDecimal("250"));
        slab.setTargetSlabWidth(new BigDecimal("1300"));

        action.execute(order, slab);

        // raw = 2e10 / (1300 * 250 * 7.82) = 2e10 / 2541500 ≈ 7869.95
        // floor = 7869
        assertThat(slab.getTargetSlabLength()).isEqualByComparingTo("7869");
    }

    @Test
    void exactInteger_returnsExact() {
        SDOrderEntity order = new SDOrderEntity();
        order.setSpecificGravity(new BigDecimal("8.0"));

        SDSlabEntity slab = new SDSlabEntity();
        slab.setSlabWgtInProgress(new BigDecimal("16000"));
        slab.setSlabThickness(new BigDecimal("200"));
        slab.setTargetSlabWidth(new BigDecimal("1000"));

        action.execute(order, slab);

        // raw = 1.6e10 / (1000*200*8.0) = 10000 exact
        assertThat(slab.getTargetSlabLength()).isEqualByComparingTo("10000");
    }
}
