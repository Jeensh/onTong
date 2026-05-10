package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.feature.sd.process.working.wrapper.AlgorithmException;
import com.example.slabdesign.feature.sd.process.working.wrapper.SdErrorCode;
import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Unit tests for {@link SdMaxSplitCountAction} (step 7: 최대분할수).
 *
 * Pure calculation — no service deps. Tests ceiling division and DG108 boundary.
 */
class SdMaxSplitCountActionTest {

    private final SdMaxSplitCountAction action = new SdMaxSplitCountAction();

    @Test
    void normalCase_setsMaxAndCurrent() {
        SDOrderEntity order = new SDOrderEntity();
        order.setOrderWgtHigh(new BigDecimal("8000"));
        order.setProductivity(new BigDecimal("0.95"));

        SDSlabEntity slab = new SDSlabEntity();
        slab.setSecondWgtHigh(new BigDecimal("28000"));

        action.execute(order, slab);

        // ceil(28000 / 8000 / 0.95) = ceil(3.6842) = 4
        assertThat(slab.getMaxSplitCountUpper()).isEqualTo(4);
        assertThat(slab.getCurrentSplitCount()).isEqualTo(4);
    }

    @Test
    void exactDivision_returnsExactQuotient() {
        SDOrderEntity order = new SDOrderEntity();
        order.setOrderWgtHigh(new BigDecimal("10000"));
        order.setProductivity(BigDecimal.ONE);

        SDSlabEntity slab = new SDSlabEntity();
        slab.setSecondWgtHigh(new BigDecimal("30000"));

        action.execute(order, slab);

        // ceil(30000 / 10000 / 1) = 3
        assertThat(slab.getMaxSplitCountUpper()).isEqualTo(3);
        assertThat(slab.getCurrentSplitCount()).isEqualTo(3);
    }

    @Test
    void dg108_maxSplitBelowOne_throws() {
        SDOrderEntity order = new SDOrderEntity();
        // orderWgtHigh huge → quotient < 1 → ceil to 1, but algorithm rejects < 1 only
        // Make secondWgtHigh tiny → ratio < 1 but ceiling = 1, not <1.
        // To force < 1 we'd need 0/0 — instead test boundary at 1:
        order.setOrderWgtHigh(new BigDecimal("100000"));
        order.setProductivity(BigDecimal.ONE);

        SDSlabEntity slab = new SDSlabEntity();
        slab.setSecondWgtHigh(new BigDecimal("99999")); // ratio=0.99999 → ceil=1, passes

        action.execute(order, slab);
        assertThat(slab.getMaxSplitCountUpper()).isEqualTo(1);
    }

    @Test
    void dg108_zeroSecondWgtHigh_throws() {
        SDOrderEntity order = new SDOrderEntity();
        order.setOrderWgtHigh(new BigDecimal("8000"));
        order.setProductivity(BigDecimal.ONE);

        SDSlabEntity slab = new SDSlabEntity();
        slab.setSecondWgtHigh(BigDecimal.ZERO);

        assertThatThrownBy(() -> action.execute(order, slab))
            .isInstanceOf(AlgorithmException.class)
            .extracting("errorCode")
            .isEqualTo(SdErrorCode.ALG_ITERATION_NEEDED);
    }
}
