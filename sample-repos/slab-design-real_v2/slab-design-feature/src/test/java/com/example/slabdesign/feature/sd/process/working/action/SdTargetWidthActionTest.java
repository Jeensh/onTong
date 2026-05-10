package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Unit tests for {@link SdTargetWidthAction} (step 18: 목표 폭, 10mm 단위 올림).
 */
class SdTargetWidthActionTest {

    private final SdTargetWidthAction action = new SdTargetWidthAction();

    @Test
    void normalCase_setsTargetWidthRoundedTo10mm() {
        SDOrderEntity order = new SDOrderEntity();
        order.setSpecificGravity(new BigDecimal("7.82"));

        SDSlabEntity slab = new SDSlabEntity();
        slab.setSplitWgtHigh(new BigDecimal("25263.15"));
        slab.setSlabThickness(new BigDecimal("250"));
        slab.setFinalLengthHigh(new BigDecimal("9990"));
        slab.setFinalWidthLow(new BigDecimal("1024"));
        slab.setFinalWidthHigh(new BigDecimal("1705"));

        action.execute(order, slab);

        // raw = 25263.15 * 1e6 / (9990 * 250 * 7.82) ≈ 1294.6...
        // ceil(/10)*10 = 1300
        // 1300 ∈ [1024, 1705] → use 1300
        assertThat(slab.getTargetSlabWidth()).isEqualByComparingTo("1300");
    }

    @Test
    void outOfRange_clampsToFinalWidthLow() {
        // Configure so raw rounds to a value outside [finalWidthLow, finalWidthHigh].
        SDOrderEntity order = new SDOrderEntity();
        order.setSpecificGravity(new BigDecimal("7.82"));

        SDSlabEntity slab = new SDSlabEntity();
        slab.setSplitWgtHigh(new BigDecimal("100000")); // huge → raw width huge → > finalWidthHigh
        slab.setSlabThickness(new BigDecimal("250"));
        slab.setFinalLengthHigh(new BigDecimal("8000"));
        slab.setFinalWidthLow(new BigDecimal("1024"));
        slab.setFinalWidthHigh(new BigDecimal("1500"));

        action.execute(order, slab);

        // raw = 1e11 / (8000*250*7.82) ≈ 6394 → out of [1024, 1500] → fallback finalWidthLow
        assertThat(slab.getTargetSlabWidth()).isEqualByComparingTo("1024");
    }
}
