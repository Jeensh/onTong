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
 * Unit tests for {@link SdSlabWgtRecalcAction} (steps 12-13: 매수+1 후 재산정).
 */
class SdSlabWgtRecalcActionTest {

    private final SdSlabWgtRecalcAction action = new SdSlabWgtRecalcAction();

    @Test
    void valid_updatesCountAndWgt() {
        // newCount = 4 + 1 = 5
        // newSlabWgt = 100000 / 1 / 5 = 20000 ; ∈ [10000, 25000]
        // total = 5 * 20000 = 100000 ∈ [80000, 100000]
        SDOrderEntity order = new SDOrderEntity();
        order.setDesignPendQtyLow(new BigDecimal("80000"));
        order.setDesignPendQtyHigh(new BigDecimal("100000"));
        order.setProductivity(BigDecimal.ONE);

        SDSlabEntity slab = new SDSlabEntity();
        slab.setCurrentSplitCount(2);
        slab.setSlabCountInProgress(4);
        slab.setSplitWgtLow(new BigDecimal("10000"));
        slab.setSplitWgtHigh(new BigDecimal("25000"));

        action.execute(order, slab);

        assertThat(slab.getSlabCountInProgress()).isEqualTo(5);
        assertThat(slab.getSlabWgtInProgress()).isEqualByComparingTo("20000");
    }

    @Test
    void dg108_weightAboveSplitRange_throws() {
        // newCount = 5, newSlabWgt = 100000/5 = 20000 — NOT in [25000, 30000]
        SDOrderEntity order = new SDOrderEntity();
        order.setDesignPendQtyLow(new BigDecimal("80000"));
        order.setDesignPendQtyHigh(new BigDecimal("100000"));
        order.setProductivity(BigDecimal.ONE);

        SDSlabEntity slab = new SDSlabEntity();
        slab.setCurrentSplitCount(2);
        slab.setSlabCountInProgress(4);
        slab.setSplitWgtLow(new BigDecimal("25000"));
        slab.setSplitWgtHigh(new BigDecimal("30000"));

        assertThatThrownBy(() -> action.execute(order, slab))
            .isInstanceOf(AlgorithmException.class)
            .extracting("errorCode")
            .isEqualTo(SdErrorCode.ALG_ITERATION_NEEDED);
    }

    @Test
    void dg108_weightBelowSplitRange_throws() {
        // newCount = 5, newSlabWgt = 100000/5 = 20000 — NOT in [100, 500]
        SDOrderEntity order = new SDOrderEntity();
        order.setDesignPendQtyLow(new BigDecimal("80000"));
        order.setDesignPendQtyHigh(new BigDecimal("100000"));
        order.setProductivity(BigDecimal.ONE);

        SDSlabEntity slab = new SDSlabEntity();
        slab.setCurrentSplitCount(2);
        slab.setSlabCountInProgress(4);
        slab.setSplitWgtLow(new BigDecimal("100"));
        slab.setSplitWgtHigh(new BigDecimal("500"));

        assertThatThrownBy(() -> action.execute(order, slab))
            .isInstanceOf(AlgorithmException.class)
            .extracting("errorCode")
            .isEqualTo(SdErrorCode.ALG_ITERATION_NEEDED);
    }
}
