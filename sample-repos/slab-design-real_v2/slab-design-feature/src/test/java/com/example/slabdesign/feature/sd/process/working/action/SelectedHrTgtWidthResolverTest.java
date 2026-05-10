package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Unit tests for {@link SelectedHrTgtWidthResolver}.
 *
 * confirmedPlantCd[1] (열연 위치) → HrTgtWidth1~5 매핑.
 */
class SelectedHrTgtWidthResolverTest {

    private final SelectedHrTgtWidthResolver resolver = new SelectedHrTgtWidthResolver();

    @Test
    void hr2_returnsHrTgtWidth2() {
        SDOrderEntity order = orderWithWidths();
        order.setConfirmedPlantCd("12345678"); // hr position = '2'
        assertThat(resolver.resolve(order)).isEqualByComparingTo("1100");
    }

    @Test
    void hr5_returnsHrTgtWidth5() {
        SDOrderEntity order = orderWithWidths();
        order.setConfirmedPlantCd("15345678"); // hr position = '5'
        assertThat(resolver.resolve(order)).isEqualByComparingTo("1400");
    }

    @Test
    void inactive_returnsNull() {
        SDOrderEntity order = orderWithWidths();
        order.setConfirmedPlantCd("1 345678"); // hr position = ' '
        assertThat(resolver.resolve(order)).isNull();
    }

    @Test
    void resolveAndSet_setsField() {
        SDOrderEntity order = orderWithWidths();
        order.setConfirmedPlantCd("13345678"); // hr = '3'
        resolver.resolveAndSet(order);
        assertThat(order.getSelectedHrTgtWidth()).isEqualByComparingTo("1200");
    }

    @Test
    void nullInput_returnsNull() {
        assertThat(resolver.resolve(null)).isNull();
        SDOrderEntity short_ = new SDOrderEntity();
        short_.setConfirmedPlantCd("1");
        assertThat(resolver.resolve(short_)).isNull();
    }

    private SDOrderEntity orderWithWidths() {
        SDOrderEntity o = new SDOrderEntity();
        o.setHrTgtWidth1(new BigDecimal("1000"));
        o.setHrTgtWidth2(new BigDecimal("1100"));
        o.setHrTgtWidth3(new BigDecimal("1200"));
        o.setHrTgtWidth4(new BigDecimal("1300"));
        o.setHrTgtWidth5(new BigDecimal("1400"));
        return o;
    }
}
