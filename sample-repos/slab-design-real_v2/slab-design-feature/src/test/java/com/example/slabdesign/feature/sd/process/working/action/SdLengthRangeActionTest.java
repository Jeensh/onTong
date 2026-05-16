package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.feature.sd.process.std.service.CastSpecService;
import com.example.slabdesign.feature.sd.process.std.service.HrSpecService;
import com.example.slabdesign.feature.sd.process.std.service.PlantMappingService;
import com.example.slabdesign.feature.sd.process.std.service.PlantMappingService.PlantMapping;
import com.example.slabdesign.feature.sd.process.working.wrapper.AlgorithmException;
import com.example.slabdesign.feature.sd.process.working.wrapper.SdErrorCode;
import com.example.slabdesign.store.sd.std.domain.entity.CastSpecEntity;
import com.example.slabdesign.store.sd.std.domain.entity.HrSpecEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link SdLengthRangeAction} (step 3: 길이범위).
 */
@ExtendWith(MockitoExtension.class)
class SdLengthRangeActionTest {

    @Mock CastSpecService castSpecService;
    @Mock HrSpecService hrSpecService;
    @Mock PlantMappingService plantMapping;

    @Test
    void normalCase_setsLengthRange() {
        when(plantMapping.getMapping("A")).thenReturn(new PlantMapping("CC1", "M1"));
        when(castSpecService.lookup(any(), any(), any(), any(), any(), any())).thenReturn(castSpec("5000", "11000"));
        when(hrSpecService.lookup(any(), any(), any(), any())).thenReturn(hrSpec("6000", "10000"));

        SdLengthRangeAction action = new SdLengthRangeAction(castSpecService, hrSpecService, plantMapping);
        SDSlabEntity slab = new SDSlabEntity();
        action.execute(sampleOrder(), slab);

        // lengthLow = max(5000, 6000) = 6000 ; lengthHigh = min(11000, 10000) = 10000
        assertThat(slab.getFirstLengthLow()).isEqualByComparingTo("6000");
        assertThat(slab.getFirstLengthHigh()).isEqualByComparingTo("10000");
    }

    @Test
    void dg102_hrSpecMisses_throws() {
        when(plantMapping.getMapping("A")).thenReturn(new PlantMapping("CC1", "M1"));
        when(castSpecService.lookup(any(), any(), any(), any(), any(), any())).thenReturn(castSpec("5000", "11000"));
        when(hrSpecService.lookup(any(), any(), any(), any())).thenReturn(null);

        SdLengthRangeAction action = new SdLengthRangeAction(castSpecService, hrSpecService, plantMapping);
        SDSlabEntity slab = new SDSlabEntity();

        assertThatThrownBy(() -> action.execute(sampleOrder(), slab))
            .isInstanceOf(AlgorithmException.class)
            .extracting("errorCode")
            .isEqualTo(SdErrorCode.ALG_HR_SPEC_NOT_FOUND);
    }

    @Test
    void dg105_invalidLengthRange_throws() {
        when(plantMapping.getMapping("A")).thenReturn(new PlantMapping("CC1", "M1"));
        // cast lengthLow=12000, hr lengthHigh=10000 → low=12000 > high=10000
        when(castSpecService.lookup(any(), any(), any(), any(), any(), any())).thenReturn(castSpec("12000", "13000"));
        when(hrSpecService.lookup(any(), any(), any(), any())).thenReturn(hrSpec("6000", "10000"));

        SdLengthRangeAction action = new SdLengthRangeAction(castSpecService, hrSpecService, plantMapping);
        SDSlabEntity slab = new SDSlabEntity();

        assertThatThrownBy(() -> action.execute(sampleOrder(), slab))
            .isInstanceOf(AlgorithmException.class)
            .extracting("errorCode")
            .isEqualTo(SdErrorCode.ALG_INVALID_LENGTH_RANGE);
    }

    private SDOrderEntity sampleOrder() {
        SDOrderEntity o = new SDOrderEntity();
        o.setCmpCd("K");
        o.setOrgCd("K01");
        o.setOrderNo("ORD-1");
        o.setProductCd("COIL");
        o.setConfirmedPlantCd("A1234567");
        return o;
    }

    private CastSpecEntity castSpec(String lengthLow, String lengthHigh) {
        CastSpecEntity c = new CastSpecEntity();
        c.setLengthLow(new BigDecimal(lengthLow));
        c.setLengthHigh(new BigDecimal(lengthHigh));
        return c;
    }

    private HrSpecEntity hrSpec(String lengthLow, String lengthHigh) {
        HrSpecEntity h = new HrSpecEntity();
        h.setLengthLow(new BigDecimal(lengthLow));
        h.setLengthHigh(new BigDecimal(lengthHigh));
        return h;
    }
}
