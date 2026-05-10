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
 * Unit tests for {@link SdInitialSlabWgtAction} (step 10: 초기 slab 단중 + 설계대기량 점검).
 */
class SdInitialSlabWgtActionTest {

    private final SdInitialSlabWgtAction action = new SdInitialSlabWgtAction();

    @Test
    void satisfies_setsSlabWgt() {
        SDOrderEntity order = new SDOrderEntity();
        order.setDesignPendQtyLow(new BigDecimal("80000"));
        order.setDesignPendQtyHigh(new BigDecimal("100000"));
        order.setProductivity(BigDecimal.ONE);

        SDSlabEntity slab = new SDSlabEntity();
        slab.setSplitWgtHigh(new BigDecimal("25000"));
        slab.setSlabCountInProgress(4); // 25000 * 4 = 100000 — equal to pendHigh

        action.execute(order, slab);

        // slabWgt = splitWgtHigh = 25000
        assertThat(slab.getSlabWgtInProgress()).isEqualByComparingTo("25000");
    }

    @Test
    void dg108_belowDesignPendLow_throws() {
        SDOrderEntity order = new SDOrderEntity();
        order.setDesignPendQtyLow(new BigDecimal("80000"));
        order.setDesignPendQtyHigh(new BigDecimal("100000"));
        order.setProductivity(BigDecimal.ONE);

        SDSlabEntity slab = new SDSlabEntity();
        slab.setSplitWgtHigh(new BigDecimal("10000"));
        slab.setSlabCountInProgress(2); // 20000 << 80000 → fail

        assertThatThrownBy(() -> action.execute(order, slab))
            .isInstanceOf(AlgorithmException.class)
            .extracting("errorCode")
            .isEqualTo(SdErrorCode.ALG_ITERATION_NEEDED);
    }

    @Test
    void dg108_aboveDesignPendHigh_throws() {
        SDOrderEntity order = new SDOrderEntity();
        order.setDesignPendQtyLow(new BigDecimal("80000"));
        order.setDesignPendQtyHigh(new BigDecimal("100000"));
        order.setProductivity(BigDecimal.ONE);

        SDSlabEntity slab = new SDSlabEntity();
        slab.setSplitWgtHigh(new BigDecimal("50000"));
        slab.setSlabCountInProgress(3); // 150000 > 100000 → fail

        assertThatThrownBy(() -> action.execute(order, slab))
            .isInstanceOf(AlgorithmException.class)
            .extracting("errorCode")
            .isEqualTo(SdErrorCode.ALG_ITERATION_NEEDED);
    }
}
