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
 * Unit tests for {@link SdSlabCountAction} (step 9: 분할수 고려 매수).
 */
class SdSlabCountActionTest {

    private final SdSlabCountAction action = new SdSlabCountAction();

    @Test
    void normalCase_floorsCount() {
        SDOrderEntity order = new SDOrderEntity();
        order.setDesignPendQtyHigh(new BigDecimal("100000"));
        order.setProductivity(new BigDecimal("0.95"));

        SDSlabEntity slab = new SDSlabEntity();
        slab.setSplitWgtHigh(new BigDecimal("25000"));
        slab.setCurrentSplitCount(2);

        action.execute(order, slab);

        // floor(100000 / 0.95 / 25000) = floor(4.21) = 4
        assertThat(slab.getSlabCountInProgress()).isEqualTo(4);
    }

    @Test
    void exactDivision_floorsToInteger() {
        SDOrderEntity order = new SDOrderEntity();
        order.setDesignPendQtyHigh(new BigDecimal("60000"));
        order.setProductivity(BigDecimal.ONE);

        SDSlabEntity slab = new SDSlabEntity();
        slab.setSplitWgtHigh(new BigDecimal("20000"));
        slab.setCurrentSplitCount(1);

        action.execute(order, slab);

        // floor(60000 / 1 / 20000) = 3
        assertThat(slab.getSlabCountInProgress()).isEqualTo(3);
    }

    @Test
    void dg108_belowOne_throws() {
        SDOrderEntity order = new SDOrderEntity();
        order.setDesignPendQtyHigh(new BigDecimal("100"));  // tiny demand
        order.setProductivity(BigDecimal.ONE);

        SDSlabEntity slab = new SDSlabEntity();
        slab.setSplitWgtHigh(new BigDecimal("50000"));      // huge slab
        slab.setCurrentSplitCount(1);

        // floor(100 / 1 / 50000) = 0 → DG108
        assertThatThrownBy(() -> action.execute(order, slab))
            .isInstanceOf(AlgorithmException.class)
            .extracting("errorCode")
            .isEqualTo(SdErrorCode.ALG_ITERATION_NEEDED);
    }
}
