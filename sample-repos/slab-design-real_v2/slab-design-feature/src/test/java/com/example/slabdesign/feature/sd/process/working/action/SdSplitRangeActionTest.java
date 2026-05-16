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
 * Unit tests for {@link SdSplitRangeAction} (step 8: 분할수 고려 단중범위).
 */
class SdSplitRangeActionTest {

    private final SdSplitRangeAction action = new SdSplitRangeAction();

    @Test
    void normalCase_setsSplitRangeAndOptimal() {
        SDOrderEntity order = order(new BigDecimal("8000"), new BigDecimal("12000"), new BigDecimal("0.95"));
        SDSlabEntity slab = slab(2, new BigDecimal("13000"), new BigDecimal("28000"));

        action.execute(order, slab);

        // orderRangeLow = 8000 * 2 / 0.95 ≈ 16842.10
        // orderRangeHigh = 12000 * 2 / 0.95 ≈ 25263.15
        // splitWgtLow = max(16842, 13000) = 16842
        // splitWgtHigh = min(25263, 28000) = 25263
        assertThat(slab.getSplitWgtLow()).isGreaterThan(new BigDecimal("16800"));
        assertThat(slab.getSplitWgtHigh()).isLessThan(new BigDecimal("25300"));
        assertThat(slab.getOptimalSplitCount()).isEqualTo(2);
    }

    @Test
    void clampedToSecondRange() {
        // small order range, large second range — order range becomes the binding constraint
        SDOrderEntity order = order(new BigDecimal("5000"), new BigDecimal("6000"), BigDecimal.ONE);
        SDSlabEntity slab = slab(1, new BigDecimal("4000"), new BigDecimal("10000"));

        action.execute(order, slab);

        // splitLow = max(5000, 4000) = 5000
        // splitHigh = min(6000, 10000) = 6000
        assertThat(slab.getSplitWgtLow()).isEqualByComparingTo("5000");
        assertThat(slab.getSplitWgtHigh()).isEqualByComparingTo("6000");
    }

    @Test
    void dg108_noOverlap_throws() {
        // order range is way above second range — no overlap
        SDOrderEntity order = order(new BigDecimal("50000"), new BigDecimal("60000"), BigDecimal.ONE);
        SDSlabEntity slab = slab(1, new BigDecimal("1000"), new BigDecimal("5000"));

        assertThatThrownBy(() -> action.execute(order, slab))
            .isInstanceOf(AlgorithmException.class)
            .extracting("errorCode")
            .isEqualTo(SdErrorCode.ALG_ITERATION_NEEDED);
    }

    private SDOrderEntity order(BigDecimal wgtLow, BigDecimal wgtHigh, BigDecimal productivity) {
        SDOrderEntity o = new SDOrderEntity();
        o.setOrderWgtLow(wgtLow);
        o.setOrderWgtHigh(wgtHigh);
        o.setProductivity(productivity);
        return o;
    }

    private SDSlabEntity slab(int splitCount, BigDecimal secondWgtLow, BigDecimal secondWgtHigh) {
        SDSlabEntity s = new SDSlabEntity();
        s.setCurrentSplitCount(splitCount);
        s.setSecondWgtLow(secondWgtLow);
        s.setSecondWgtHigh(secondWgtHigh);
        return s;
    }
}
